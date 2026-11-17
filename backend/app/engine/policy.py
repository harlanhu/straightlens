"""Conservative geometry heuristics; no calibrated probability is claimed."""
from dataclasses import dataclass,field,replace
import json
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from .ipol import CandidateResult
from .remap import correct_points, valid_model
from .fitting import robust_fit as _robust_fit,RobustFit

POLICY=json.loads(Path(__file__).with_name('policy.json').read_text())

@dataclass
class Decision:
    outcome: str
    reason_code: str
    candidate: CandidateResult | None = None
    diagnostics: dict = field(default_factory=dict)


def residuals(points):
    centered=points-points.mean(axis=0)
    _,_,vectors=np.linalg.svd(centered,full_matrices=False)
    return centered@vectors[-1]


def rms(points):
    return float(np.sqrt(np.mean(residuals(points)**2)))


def _fragment_direction(points):
    centered=points-points.mean(axis=0)
    if np.linalg.norm(centered)<1e-9:return None
    _,_,vectors=np.linalg.svd(centered,full_matrices=False)
    direction=vectors[0]
    if direction[0]<-1e-8 or (abs(direction[0])<=1e-8 and direction[1]<0):
        direction=-direction
    return direction


def _join_fragments(lines, max_gap_px, max_angle_deg, check_deadline=lambda:None):
    """Merge nearby end-to-end traces, never disjoint parallel evidence."""
    remaining=[_radial_order(line,None) for line in lines]
    while len(remaining)>1:
        merged=False
        for i,a in enumerate(remaining):
            check_deadline()
            da=_fragment_direction(a)
            if da is None:continue
            normal=np.array([-da[1],da[0]])
            for j in range(i+1,len(remaining)):
                b=remaining[j];db=_fragment_direction(b)
                if db is None or abs(np.dot(da,db))<np.cos(np.deg2rad(max_angle_deg)):continue
                overlap=min(np.max(a@da),np.max(b@da))-max(np.min(a@da),np.min(b@da))
                if overlap>3:continue
                gaps=[np.linalg.norm(a[-1]-b[0]),np.linalg.norm(b[-1]-a[0])]
                pair=(a[-1],b[0]) if gaps[0]<=gaps[1] else (b[-1],a[0])
                if min(gaps)>max_gap_px or abs(np.dot(pair[1]-pair[0],normal))>3:continue
                remaining[i]=_radial_order(np.vstack((a,b)),None)
                remaining.pop(j);merged=True;break
            if merged:break
        if not merged:break
    return remaining


def _dedupe_parallel(lines, max_normal_px, check_deadline=lambda:None):
    """Drop spatially overlapping double edges; disjoint traces are independent."""
    from scipy.spatial import cKDTree
    order=sorted(range(len(lines)),key=lambda k:(-np.linalg.norm(np.ptp(lines[k],axis=0)),-len(lines[k])))
    kept=[]
    for index in order:
        check_deadline()
        current=lines[index];direction=_fragment_direction(current)
        if direction is None:continue
        duplicate=False
        for other in kept:
            other_dir=_fragment_direction(other)
            if other_dir is None or abs(np.dot(direction,other_dir))<np.cos(np.deg2rad(8)):continue
            lo=max(np.min(current@direction),np.min(other@direction))
            hi=min(np.max(current@direction),np.max(other@direction))
            if hi-lo<.65*min(np.ptp(current@direction),np.ptp(other@direction)):continue
            local=current[(current@direction>=lo)&(current@direction<=hi)]
            # Interpolate long sparse traces before measuring edge-to-edge distance.
            ordered=other[np.argsort(other@direction)]
            projection=ordered@direction
            xs=np.linspace(lo,hi,160)
            reference=np.column_stack([np.interp(xs,projection,ordered[:,axis]) for axis in (0,1)])
            if len(local) and np.quantile(cKDTree(reference).query(local)[0],.9)<max_normal_px:
                duplicate=True;break
        if not duplicate:kept.append(current)
    return kept


def _radial_order(points, center):
    # A radial radius is not monotone along a trace crossing the center.
    direction=_fragment_direction(points)
    if direction is None:return points
    return points[np.argsort(points@direction,kind='stable')]


def preprocess_lines(candidate: CandidateResult,check_deadline=lambda:None) -> list[np.ndarray]:
    """Merge fragments and double edges, with cancellable pairwise scans."""
    check_deadline()
    diagonal=np.hypot(*candidate.size)
    minimum=POLICY['min_line_span_ratio']*diagonal
    raw=[line for line in candidate.lines if len(line)>=8 and np.linalg.norm(np.ptp(line,axis=0))>=minimum*.6]
    joined=_join_fragments(raw, .02*diagonal, 8.,check_deadline)
    deduped=_dedupe_parallel(joined, 3.,check_deadline)
    center=np.array(candidate.center)
    return [_radial_order(line[::max(1,len(line)//160)], center)
            for line in deduped
            if len(line)>=30 and np.linalg.norm(np.ptp(line,axis=0))>=minimum]


def useful_lines(candidate,check_deadline=lambda:None):
    return preprocess_lines(candidate,check_deadline)


def robust_fit(lines,candidate,seed=0,**kwargs):
    return _robust_fit(lines,candidate,seed,settings=POLICY,**kwargs)


def refit(candidate, train):
    """Refit coefficients using training curves only; whole curves are held out.

    Line discovery/center still originate from the native whole-image detector,
    so this is a consistency check, not independent ground-truth validation.
    """
    scale=np.hypot(*candidate.size)**2
    coefficients=candidate.coefficients
    start=[coefficients[1]*scale,(coefficients[2] if len(coefficients)>2 else 0)*scale**2]
    def model(x):
        return replace(candidate,coefficients=(1.,x[0]/scale,x[1]/scale**2))
    def cost(x):
        return np.concatenate([residuals(correct_points(p,model(x))) for p in train])
    fit=least_squares(cost,start,bounds=([-10,-10],[10,10]),loss='soft_l1',max_nfev=45)
    return model(fit.x)


def evaluate(candidate,check_deadline=lambda:None):
    check_deadline()
    if not valid_model(candidate):
        return None
    lines=useful_lines(candidate,check_deadline)
    if len(lines)<POLICY['min_lines']:
        return None
    w,h=candidate.size
    spread=np.ptp(np.concatenate(lines),axis=0)/[w,h]
    if spread[0]<POLICY['min_width_coverage'] or spread[1]<POLICY['min_height_coverage']:
        return None
    # Spatially interleave groups, never split one curve's points across folds.
    lines=sorted(lines,key=lambda p: float(p.mean(axis=0)[1]+p.mean(axis=0)[0]*.37))
    folds=[]
    try:
        for parity in (0,1):
            check_deadline()
            train=lines[parity::2]
            validation=lines[1-parity::2]
            fitted=refit(candidate,train)
            if not valid_model(fitted):
                return None
            raw=np.array([rms(p) for p in validation])
            corrected=np.array([rms(correct_points(p,fitted)) for p in validation])
            # Tiny already-straight segments provide little distortion evidence.
            mask=raw>=POLICY['min_raw_rms']
            if mask.sum()<2:
                return None
            r=float(np.median(raw[mask])); c=float(np.median(corrected[mask]))
            improve=float(np.mean(corrected[mask]<raw[mask]*.85))
            if c>POLICY['max_corrected_rms'] or c/r>POLICY['max_residual_ratio'] or improve<POLICY['min_improving_fraction']:
                return None
            # Validate the actual model that will be rendered, not just fold refits.
            final=np.array([rms(correct_points(p,candidate)) for p in validation])
            final_rms=float(np.median(final[mask]))
            final_improve=float(np.mean(final[mask]<raw[mask]*.85))
            if final_rms>POLICY['max_corrected_rms'] or final_rms/r>POLICY['max_residual_ratio'] or final_improve<POLICY['min_improving_fraction']:
                return None
            # Don't improve curved evidence by badly damaging originally straight edges.
            if np.any((raw<.5)&((corrected>1.5)|(final>1.5))):
                return None
            folds.append({'raw_rms':r,'corrected_rms':max(c,final_rms),'improving_fraction':min(improve,final_improve)})
    except (ValueError,np.linalg.LinAlgError,FloatingPointError):
        return None
    return {'usable_lines':len(lines),'coverage':spread.tolist(),'folds':folds,
            'score':float(np.mean([f['corrected_rms']/f['raw_rms'] for f in folds]))}


def shape_disagreement(a,b):
    # Output zoom/translation are arbitrary; compare nonrigid shape only.
    ac=a-a.mean(axis=0); bc=b-b.mean(axis=0)
    denominator=float(np.sum(bc*bc))
    if denominator<1e-10:return float('inf')
    scale=float(np.sum(ac*bc)/denominator)
    if scale<=0:return float('inf')
    return float(np.quantile(np.linalg.norm(ac-bc*scale,axis=1),.9))


def evaluate_weak(candidate,**kwargs):
    from .weak import evaluate_weak as evaluate_candidate
    return evaluate_candidate(candidate,**kwargs)


def assess_candidates(candidates: list[CandidateResult],evidence=None,*,check_deadline=lambda:None) -> Decision:
    native=_assess_native_candidates([c for c in candidates if c.strategy!='weak'],check_deadline)
    if native.outcome=='corrected':return native
    weak=[]
    for candidate in candidates:
        if candidate.strategy!='weak' or not valid_model(candidate):continue
        check_deadline()
        metrics=evaluate_weak(candidate,check_deadline=check_deadline)
        if metrics is not None:weak.append((metrics['score'],metrics['candidate'],metrics))
    weak.sort(key=lambda entry:entry[0])
    if len(weak)>=2:
        _,best,metrics=weak[0]
        w,h=best.size
        x,y=np.meshgrid(np.linspace(0,w-1,9),np.linspace(0,h-1,7))
        samples=np.column_stack((x.ravel(),y.ravel()))
        for _,other,_ in weak[1:]:
            if shape_disagreement(correct_points(samples,best),correct_points(samples,other))<.008*np.hypot(w,h):
                diagnostic={key:value for key,value in metrics.items() if key!='candidate'}
                diagnostic['weak_candidate_count']=len(weak)
                return Decision('corrected','geometry_improved',best,diagnostic)
    if weak:
        return Decision('unchanged','unstable_estimate',diagnostics={'weak_candidate_count':len(weak)})
    return native


def _assess_native_candidates(candidates: list[CandidateResult],check_deadline=lambda:None) -> Decision:
    evaluations=[]
    for candidate in candidates:
        check_deadline()
        result=evaluate(candidate,check_deadline)
        if result is not None:
            evaluations.append((result['score'],candidate,result))
    if not evaluations:
        has_lines=any(len(useful_lines(c,check_deadline))>=POLICY['min_lines'] for c in candidates)
        return Decision('unchanged','no_reliable_improvement' if has_lines else 'insufficient_evidence')
    evaluations.sort(key=lambda entry:entry[0])
    _,best,diagnostic=evaluations[0]
    if len(evaluations)<2:
        return Decision('unchanged','unstable_estimate',diagnostics=diagnostic)
    w,h=best.size
    x,y=np.meshgrid(np.linspace(0,w-1,9),np.linspace(0,h-1,7))
    samples=np.column_stack((x.ravel(),y.ravel()))
    displacement=correct_points(samples,best)-samples
    consistent=[]
    for _,other,_ in evaluations[1:]:
        disagreement=shape_disagreement(correct_points(samples,best),correct_points(samples,other))
        if disagreement<POLICY['max_candidate_disagreement_ratio']*np.hypot(w,h):
            consistent.append(other)
    if not consistent:
        return Decision('unchanged','unstable_estimate',diagnostics=diagnostic)
    if float(np.max(np.linalg.norm(displacement,axis=1)))<1.5:
        return Decision('unchanged','no_reliable_improvement',diagnostics=diagnostic)
    return Decision('corrected','geometry_improved',best,diagnostic)
