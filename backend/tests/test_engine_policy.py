from pathlib import Path
import numpy as np
import pytest
from app.engine.ipol import CandidateResult, CandidateConfig, parse_primitives, EngineError
from app.engine.policy import assess_candidates
from app.engine.remap import correct_points, valid_model


def candidate(coeff=(1.,0.,0.), lines=None):
    return CandidateResult(CandidateConfig('pol', .8), coeff, (320.,240.), (640,480), lines or [], Path('.'))


def test_empty_evidence_keeps_original():
    assert assess_candidates([]).reason_code == 'insufficient_evidence'


def test_identity_keeps_original():
    lines = [np.column_stack((np.arange(40,600), np.full(560,y))) for y in (50,140,330,430)]
    assert assess_candidates([candidate(lines=lines)]).outcome == 'unchanged'


def test_folded_mapping_rejected():
    assert not valid_model(candidate((1., -1e-4, 0.)))


def test_model_convention():
    c = candidate((1., 1e-6, 0.))
    p = np.array([[420.,240.]])
    np.testing.assert_allclose(correct_points(p,c), [[421.,240.]])
    c.config = CandidateConfig('div',.8)
    np.testing.assert_allclose(correct_points(p,c), [[320+100/1.01,240.]])


def test_candidate_comparison_ignores_global_translation_and_scale():
    from app.engine.policy import shape_disagreement
    points=np.array([[0.,0.],[100.,0.],[100.,100.],[0.,100.]])
    assert shape_disagreement(points,points*2+[50.,20.])<1e-8
    warped=points.copy();warped[-1]+=[30.,0.]
    assert shape_disagreement(points,warped)>5


def test_blank_skips_native_engine(tmp_path,monkeypatch):
    from PIL import Image
    from app.engine import pipeline
    def unexpected(*args,**kwargs): raise AssertionError('blank must not run native engine')
    monkeypatch.setattr(pipeline,'run_ipol',unexpected)
    source=tmp_path/'blank.png';Image.new('RGB',(160,120),'white').save(source)
    result=pipeline.process_image(source,tmp_path/'work')
    assert result['outcome']=='unchanged'
    assert result['reason_code']=='insufficient_evidence'


def test_final_native_model_must_improve_not_only_refitted_model(monkeypatch):
    from app.engine import policy
    good=candidate((1.,1e-6,0.))
    radii=np.linspace(0,500,10000)
    lines=[]
    for y in (30,90,160,300,390,450):
        target=np.column_stack((np.linspace(15,625,180),np.full(180,y)))
        delta=target-good.center;ru=np.linalg.norm(delta,axis=1)
        rd=np.interp(ru,radii*(1+1e-6*radii*radii),radii)
        lines.append(good.center+delta*(rd/ru)[:,None])
    bad=candidate((1.,1e-8,0.),lines)
    monkeypatch.setattr(policy,'refit',lambda *_:good)
    assert policy.evaluate(bad) is None


def test_missing_output_is_error(tmp_path):
    with pytest.raises(EngineError):
        parse_primitives(tmp_path/'missing.txt', CandidateConfig('div',.8), (640,480))
