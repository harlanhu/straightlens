from pathlib import Path
import numpy as np
from app.engine.ipol import CandidateConfig,CandidateResult
from app.engine.policy import robust_fit


def make_data():
    c=CandidateResult(CandidateConfig('pol',.8),(1.,0.,0.),(400.,300.),(800,600),[],Path('.'))
    radius=np.linspace(0,700,20000)
    mapped=radius*(1+1.2e-6*radius**2)
    traces=[]
    for axis,value in [(0,60),(0,740),(1,50),(1,550),(0,180),(1,420)]:
        q=np.column_stack((np.full(120,value),np.linspace(15,585,120))) if axis==0 else np.column_stack((np.linspace(15,785,120),np.full(120,value)))
        d=q-c.center;r=np.linalg.norm(d,axis=1)
        r_distorted=np.interp(r,mapped,radius)
        traces.append(c.center+d*(r_distorted/r)[:,None])
    return c,traces


def test_arc_lines_are_outliers():
    c,straight=make_data()
    a=np.linspace(.15,1.1,120)
    arcs=[np.column_stack((400+220*np.cos(a),300+140*np.sin(a))),np.column_stack((400-220*np.cos(a),300-140*np.sin(a)))]
    result=robust_fit(straight+arcs,c,seed=4)
    assert sum(result.inlier_mask[:6])>=5
    assert not any(result.inlier_mask[6:])
    assert abs(result.model.coefficients[1]-1.2e-6)<2e-7


def test_subtitle_rect_not_dominant():
    c,straight=make_data()
    box=[np.column_stack((np.linspace(15,150,80),np.full(80,y))) for y in (15,50)]
    reference=robust_fit(straight,c,seed=4)
    result=robust_fit(straight+box,c,seed=4)
    assert abs(result.model.coefficients[1]-reference.model.coefficients[1])<abs(reference.model.coefficients[1])*.1


def test_robust_fit_repeatable():
    c,lines=make_data()
    first=robust_fit(lines,c,seed=3)
    second=robust_fit(lines,c,seed=3)
    np.testing.assert_allclose(first.model.coefficients,second.model.coefficients,atol=1e-12)
    np.testing.assert_array_equal(first.inlier_mask,second.inlier_mask)
