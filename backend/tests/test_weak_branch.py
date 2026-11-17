from pathlib import Path
import time
import numpy as np
from app.engine.ipol import CandidateConfig,CandidateResult
from app.engine.policy import evaluate_weak


def model(lines):
    return CandidateResult(CandidateConfig('pol',.8),(1.,0.,0.),(400.,300.),(800,600),lines,Path('.'))


def test_zero_param_not_significant():
    lines=[np.column_stack((np.linspace(10,790,100),np.full(100,y))) for y in (30,120,300,480,570)]
    lines += [np.column_stack((np.full(100,x),np.linspace(10,590,100))) for x in (30,180,600,770)]
    assert evaluate_weak(model(lines)) is None


def test_weak_budget_bounded():
    lines=[np.column_stack((np.linspace(10,790,64),np.full(64,10+i))) for i in range(500)]
    started=time.monotonic()
    assert evaluate_weak(model(lines)) is None
    assert time.monotonic()-started<2


def test_weak_corrects_small_distortion_without_strong_model():
    from test_robust_fit import make_data
    c,lines=make_data()
    # Independent radial deformation with weaker coefficient.
    radius=np.linspace(0,700,20000)
    warped=[]
    for y in (25,130,450,575):
        q=np.column_stack((np.linspace(15,785,180),np.full(180,y)))
        d=q-c.center;r=np.linalg.norm(d,axis=1)
        rd=np.interp(r,radius*(1+2e-7*radius**2),radius)
        warped.append(c.center+d*(rd/r)[:,None])
    for x in (30,770):
        q=np.column_stack((np.full(180,x),np.linspace(15,585,180)))
        d=q-c.center;r=np.linalg.norm(d,axis=1)
        rd=np.interp(r,radius*(1+2e-7*radius**2),radius)
        warped.append(c.center+d*(rd/r)[:,None])
    result=evaluate_weak(model(warped))
    assert result is not None
    assert result['candidate'].coefficients[2]==0
    assert abs(result['candidate'].coefficients[1]-2e-7)<3e-8


def test_curved_work_honors_deadline_inside_preprocessing():
    import pytest
    rng=np.random.default_rng(0)
    lines=[]
    t=np.linspace(0,1,80)
    for _ in range(500):
        p=rng.uniform([0,0],[900,600]);angle=rng.uniform(0,np.pi);length=rng.uniform(100,400)
        direction=np.array([np.cos(angle),np.sin(angle)])
        normal=np.array([-direction[1],direction[0]])
        lines.append(p+length*t[:,None]*direction+8*(t*(1-t))[:,None]*normal)
    c=CandidateResult(CandidateConfig('pol',.8),(1.,0.,0.),(450.,300.),(900,600),lines,Path('.'))
    started=time.monotonic()
    def check():
        if time.monotonic()-started>.01:raise TimeoutError('cancelled preprocessing')
    with pytest.raises(TimeoutError):evaluate_weak(c,check_deadline=check)
    assert time.monotonic()-started<.3


def test_curved_large_input_has_bounded_total_work():
    rng=np.random.default_rng(8);t=np.linspace(0,1,80);lines=[]
    for _ in range(500):
        p=rng.uniform([0,0],[900,600]);angle=rng.uniform(0,np.pi);length=rng.uniform(100,400)
        d=np.array([np.cos(angle),np.sin(angle)]);n=np.array([-d[1],d[0]])
        lines.append(p+length*t[:,None]*d+8*(t*(1-t))[:,None]*n)
    c=CandidateResult(CandidateConfig('pol',.8),(1.,0.,0.),(450.,300.),(900,600),lines,Path('.'))
    started=time.monotonic();evaluate_weak(c)
    assert time.monotonic()-started<2


def test_only_natural_arcs_not_corrected():
    a=np.linspace(-.6,.6,150)
    arcs=[np.column_stack((400+r*np.cos(a+t),300+r*np.sin(a+t))) for r in (140,230) for t in (0,np.pi/2,np.pi,3*np.pi/2)]
    assert evaluate_weak(model(arcs)) is None
