"""Bounded deterministic consensus over whole contours, in IPOL coordinates."""
from dataclasses import dataclass,replace
import time
import numpy as np
from scipy.optimize import least_squares
from .ipol import CandidateResult
from .remap import correct_points,valid_model


@dataclass
class RobustFit:
    model: CandidateResult
    inlier_mask: np.ndarray
    inlier_fraction: float
    iterations: int = 0
    timed_out: bool = False


def batch_residuals(points):
    centered=points-np.mean(points,axis=-2,keepdims=True)
    x,y=centered[...,0],centered[...,1]
    angle=.5*np.arctan2(2*np.mean(x*y,axis=-1),np.mean(x*x-y*y,axis=-1))
    return -x*np.sin(angle)[...,None]+y*np.cos(angle)[...,None]


def sample_contours(lines,count=48):
    return np.array([points[np.linspace(0,len(points)-1,count,dtype=int)] for points in lines])


def fit_model(lines,candidate,degrees=2):
    scale=float(np.hypot(*candidate.size)**2)
    sampled=sample_contours(lines)
    start=np.array([candidate.coefficients[1]*scale,(candidate.coefficients[2] if len(candidate.coefficients)>2 else 0)*scale**2])[:degrees]
    bound=.45 if degrees==1 else 10.
    start=np.clip(start,-bound+.0001,bound-.0001)
    def model(params):
        return replace(candidate,coefficients=(1.,float(params[0])/scale,float(params[1])/scale**2 if degrees==2 else 0.))
    def cost(params):
        residual=batch_residuals(correct_points(sampled,model(params))).ravel()/np.sqrt(sampled.shape[1])
        return np.r_[residual, params[1]*.001] if degrees==2 else residual
    result=least_squares(cost,start,bounds=(-bound,bound),loss='soft_l1',max_nfev=25,ftol=1e-6,xtol=1e-6)
    return model(result.x)


def robust_fit(lines,candidate,seed=0,*,settings=None,degrees=2,check_deadline=lambda:None):
    settings=settings or {}
    count=len(lines)
    if count<2:return RobustFit(candidate,np.zeros(count,dtype=bool),0.)
    sampled=sample_contours(lines)
    spans=np.linalg.norm(np.ptp(sampled,axis=1),axis=1)
    weights=np.clip(spans/np.hypot(*candidate.size),.02,1.)
    threshold=settings.get('ransac_residual_px',1.2)
    maximum=settings.get('ransac_max_iterations',60)
    deadline=time.monotonic()+settings.get('ransac_budget_seconds',1.5)
    rng=np.random.default_rng(seed)
    best=candidate;mask=np.zeros(count,dtype=bool);best_score=(-1.,-np.inf)
    identity=replace(candidate,coefficients=(1.,0.,0.))
    candidates=[identity,candidate]
    try:candidates.append(fit_model(lines,candidate,degrees))
    except (ValueError,np.linalg.LinAlgError):pass
    iterations=0;timed_out=False
    while candidates or iterations<maximum:
        check_deadline()
        if time.monotonic()>deadline:
            timed_out=True;break
        if candidates:
            model=candidates.pop(0)
        else:
            iterations+=1
            indices=rng.choice(count,size=2,replace=False,p=weights/weights.sum())
            try:model=fit_model([lines[i] for i in indices],identity,degrees)
            except (ValueError,np.linalg.LinAlgError):continue
        if not valid_model(model):continue
        errors=np.sqrt(np.mean(batch_residuals(correct_points(sampled,model))**2,axis=1))
        support=errors<threshold
        score=(float(weights[support].sum()),-float(np.sum(np.minimum(errors,threshold)*weights)))
        if score>best_score:
            best_score=score;best=model;mask=support
        if support.all() and iterations>=8:break
    if mask.sum()>=2:
        try:
            refined=fit_model([p for p,keep in zip(lines,mask) if keep],best,degrees)
            if valid_model(refined):
                errors=np.sqrt(np.mean(batch_residuals(correct_points(sampled,refined))**2,axis=1))
                updated=errors<threshold
                if weights[updated].sum()>=weights[mask].sum()*.98:
                    best=refined;mask=updated
        except (ValueError,np.linalg.LinAlgError):pass
    # Sampling accelerates proposal search; final evidence uses every point.
    full_errors=np.array([np.sqrt(np.mean(batch_residuals(correct_points(points,best))**2)) for points in lines])
    mask=full_errors<threshold
    return RobustFit(best,mask,float(np.mean(mask)),iterations,timed_out)
