from dataclasses import replace
from pathlib import Path
import numpy as np
from app.engine.ipol import CandidateConfig,CandidateResult
from app.engine.policy import assess_candidates,evaluate_weak


def small_distortion_lines():
    from test_robust_fit import make_data
    c,_=make_data()
    radius=np.linspace(0,700,20000)
    lines=[]
    for axis,value in ((0,30),(0,770),(1,25),(1,575)):
        q=np.column_stack((np.full(150,value),np.linspace(10,590,150))) if axis==0 else np.column_stack((np.linspace(10,790,150),np.full(150,value)))
        delta=q-c.center;r=np.linalg.norm(delta,axis=1)
        rd=np.interp(r,radius*(1+2e-7*radius**2),radius)
        lines.append(c.center+delta*(rd/r)[:,None])
    return replace(c,lines=lines)


def test_weak_candidates_reach_real_selection_and_render_model():
    c=small_distortion_lines()
    first=evaluate_weak(c)['candidate']
    second=evaluate_weak(replace(c,config=CandidateConfig('pol',.9)))['candidate']
    result=assess_candidates([first,second])
    assert result.outcome=='corrected'
    assert result.candidate.strategy=='weak'
    assert result.candidate.coefficients[2]==0
    assert abs(result.candidate.coefficients[1]-2e-7)<3e-8


def test_uncached_selection_returns_the_model_it_validated():
    c=replace(small_distortion_lines(),strategy='weak')
    second=replace(c,config=CandidateConfig('pol',.9))
    result=assess_candidates([c,second])
    assert result.outcome=='corrected'
    assert abs(result.candidate.coefficients[1]-2e-7)<3e-8


def test_single_weak_proposal_does_not_bypass_agreement():
    c=evaluate_weak(small_distortion_lines())['candidate']
    assert assess_candidates([c]).outcome=='unchanged'
