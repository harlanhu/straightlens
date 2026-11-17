"""Small one-parameter proposals with whole-contour validation and an identity baseline."""
from dataclasses import replace
import time
import numpy as np
from .fitting import batch_residuals,sample_contours,fit_model
from .remap import correct_points,valid_model


class _WeakBudgetExceeded(Exception):
    pass


def evaluate_weak(candidate,check_deadline=lambda:None):
    from .policy import POLICY
    deadline=time.monotonic()+POLICY['weak_budget_seconds']
    def ensure_budget():
        check_deadline()
        if time.monotonic()>deadline:raise _WeakBudgetExceeded()
    try:
        return _evaluate_weak(candidate,ensure_budget)
    except _WeakBudgetExceeded:
        return None


def _evaluate_weak(candidate,check_deadline):
    from .policy import POLICY,preprocess_lines,robust_fit,rms
    if candidate.strategy=='weak' and candidate.validation is not None:
        return dict(candidate.validation,candidate=candidate)
    raw_lines=[line for line in candidate.lines if len(line)>=30 and np.isfinite(line).all()]
    if len(raw_lines)<4:return None
    # Skip zero-evidence inputs before the pairwise preprocessing cost.
    raw_errors=np.array([rms(line) for line in raw_lines])
    if np.sum(raw_errors>.45)<2:return None
    check_deadline()
    # Bound the quadratic pair scans before consensus. Original straight edges
    # remain guards even when they are outside this bounded proposal subset.
    ranked=sorted(raw_lines,key=lambda p:-np.linalg.norm(np.ptp(p,axis=0)))
    selected=ranked[:POLICY['weak_max_contours']]
    base=replace(candidate,lines=selected,center=(candidate.size[0]/2,candidate.size[1]/2),coefficients=(1.,0.,0.),strategy='weak',validation=None)
    lines=preprocess_lines(base,check_deadline)
    if len(lines)<4:return None
    fit=robust_fit(lines,base,seed=17,degrees=1,check_deadline=check_deadline)
    if fit.timed_out:return None
    model=fit.model
    if not valid_model(model):return None
    # Inlier proposal discovery sees the image, but coefficient refits below never
    # include the held-out trace. This is a consistency check, not ground truth.
    keep=fit.inlier_mask
    inliers=[p for p,ok in zip(lines,keep) if ok]
    if len(inliers)<4:return None
    w,h=model.size;diagonal=float(np.hypot(w,h))
    spread=np.ptp(np.concatenate(inliers),axis=0)/[w,h]
    if spread[0]<.45 or spread[1]<.4:return None
    x,y=np.meshgrid(np.linspace(0,w-1,9),np.linspace(0,h-1,7))
    samples=np.column_stack((x.ravel(),y.ravel()))
    shift=np.linalg.norm(correct_points(samples,model)-samples,axis=1)
    if shift.max()<1.5 or shift.max()>POLICY['weak_max_shift_ratio']*diagonal:return None
    raw=np.array([rms(p) for p in lines])
    corrected=np.array([rms(correct_points(p,model)) for p in lines])
    # All originally straight long contours are guards, even if RANSAC omitted them.
    if np.any((raw<.5)&(corrected>np.maximum(.9,raw+.5))):return None
    for trace,error in zip(raw_lines,raw_errors):
        check_deadline()
        if error<.5 and np.linalg.norm(np.ptp(trace,axis=0))>=.12*diagonal:
            if rms(correct_points(trace,model))>max(.9,float(error)+.5):return None
    eligible=keep&(raw>.45)
    if eligible.sum()<2:return None
    before=float(np.median(raw[eligible]));after=float(np.median(corrected[eligible]))
    if after>POLICY['weak_max_corrected_rms'] or after/before>POLICY['weak_max_residual_ratio']:return None
    improvement=float(np.mean(corrected[eligible]<raw[eligible]*.85))
    if improvement<POLICY['weak_min_improving_fraction']:return None
    if before-after<.2:return None
    heldout=[]
    # Leave out a whole inlier contour, bounded to eight representative folds.
    indices=np.linspace(0,len(inliers)-1,min(8,len(inliers)),dtype=int)
    for index in indices:
        check_deadline()
        trained=fit_model([p for i,p in enumerate(inliers) if i!=index],base,degrees=1)
        if not valid_model(trained):return None
        disagreement=np.max(np.linalg.norm(correct_points(samples,trained)-correct_points(samples,model),axis=1))
        if disagreement>diagonal*.008:return None
        p=inliers[index];r=rms(p);c=rms(correct_points(p,trained))
        if r>.45:heldout.append((r,c))
        if r<.5 and c>max(.9,r+.5):return None
    if len(heldout)<2:return None
    ratios=np.array([c/r for r,c in heldout])
    if np.median(ratios)>POLICY['weak_max_residual_ratio'] or np.mean(ratios<.85)<POLICY['weak_min_improving_fraction']:return None
    metrics={'strategy':'weak','usable_lines':len(lines),'inlier_lines':len(inliers),'inlier_fraction':fit.inlier_fraction,
             'coverage':spread.tolist(),'raw_rms':before,'corrected_rms':after,'heldout_median_ratio':float(np.median(ratios)),
             'max_shift_px':float(shift.max()),'score':max(after/before,float(np.median(ratios)))}
    model=replace(model,validation=metrics)
    return dict(metrics,candidate=model)
