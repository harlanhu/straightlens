from pathlib import Path
from dataclasses import replace
import json
import numpy as np
import pytest
from PIL import Image
from app.engine.ipol import CandidateConfig,CandidateResult
from app.engine.transforms import TransformSpec,original_to_canvas,load_transform
from app.engine.remap import map_block


def candidate(kind='pol',center=(80.,50.)):
    return CandidateResult(CandidateConfig(kind,.8),(1.,1e-5,0.),center,(160,100),[],Path('.'))


@pytest.mark.parametrize('kind',['pol','div'])
def test_saved_transform_reproduces_map(tmp_path,kind):
    c=candidate(kind,(75.,47.))
    spec=TransformSpec.from_candidate(c,(320,200),(10,8,300,190))
    spec.save(tmp_path/'transform.json')
    Image.new('RGB',(320,200)).save(tmp_path/'normalized.png')
    Image.new('RGB',(290,182)).save(tmp_path/'result.png')
    loaded=load_transform(tmp_path)
    assert loaded.fingerprint==spec.fingerprint
    mx,my,valid=map_block(c,(320,200),0,200)
    y,x=np.mgrid[:200,:320]
    p=np.column_stack((mx[valid],my[valid]))
    actual=original_to_canvas(p,loaded)
    np.testing.assert_allclose(actual,np.column_stack((x[valid],y[valid])),atol=.1)


def test_cropped_pixels_equal_uncropped_roi(tmp_path):
    from types import SimpleNamespace
    from app.engine.remap import render_full_resolution
    array=np.random.default_rng(5).integers(0,256,(100,160,3),dtype=np.uint8)
    source=tmp_path/'source.png';Image.fromarray(array).save(source)
    result=render_full_resolution(SimpleNamespace(normalized_path=source),candidate(),tmp_path/'result.png')
    assert result.uncropped_path.exists()
    with Image.open(result.uncropped_path) as full:whole=np.array(full)
    x0,y0,x1,y1=result.crop
    with Image.open(tmp_path/'result.png') as cropped:
        np.testing.assert_array_equal(np.array(cropped),whole[y0:y1,x0:x1])
    assert whole.shape==(100,160,3)
    assert result.mask_path.exists()


def test_opaque_rgba_uncropped_is_reuploadable(tmp_path):
    from types import SimpleNamespace
    from app.engine.remap import render_full_resolution
    from app.engine.reverse import prepare_reverse_upload
    source=tmp_path/'opaque.png';Image.new('RGBA',(160,100),(20,50,80,255)).save(source)
    rendered=render_full_resolution(SimpleNamespace(normalized_path=source),candidate(),tmp_path/'result.png')
    with Image.open(rendered.mask_path) as mask:assert np.any(np.array(mask)==0)
    with Image.open(rendered.uncropped_path) as full:assert np.min(np.array(full.convert('RGBA'))[...,3])==255
    info=prepare_reverse_upload(rendered.uncropped_path,tmp_path/'upload')
    assert not info.transparent


def test_unknown_version_and_invalid_crop_rejected():
    spec=TransformSpec.from_candidate(candidate(),(320,200),(0,0,320,200))
    data=spec.to_dict();data['version']=999
    with pytest.raises(ValueError):TransformSpec.from_dict(data)
    with pytest.raises(ValueError):TransformSpec.from_candidate(candidate(),(320,200),(-1,0,320,200))


def test_fingerprint_tampering_rejected():
    spec=TransformSpec.from_candidate(candidate(),(320,200),(0,0,320,200))
    data=spec.to_dict();data['center']=[70.,50.]
    with pytest.raises(ValueError):TransformSpec.from_dict(data)
