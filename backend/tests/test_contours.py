from pathlib import Path
import numpy as np
from app.engine.ipol import CandidateConfig, CandidateResult
from app.engine.policy import preprocess_lines


def line(start,end,n=64):
    return np.linspace(start,end,n)


def candidate(*lines):
    return CandidateResult(CandidateConfig('pol',.8),(1.,0.,0.),(320.,240.),(640,480),list(lines),Path('.'))


def test_merge_colinear_fragments():
    a=line([10,100],[200,100]); b=line([205,100],[400,100])
    merged=preprocess_lines(candidate(a,b))
    assert len(merged)==1
    assert len(merged[0])==128
    assert np.ptp(merged[0][:,1])==0
    assert np.isclose(np.ptp(merged[0][:,0]),390)


def test_gap_too_large_keeps_separate():
    a=line([10,100],[130,100]);b=line([300,100],[430,100])
    assert len(preprocess_lines(candidate(a,b)))==2


def test_parallel_duplicate_removed():
    longer=line([0,100],[639,100],180);shorter=line([100,102],[300,102],64)
    kept=preprocess_lines(candidate(longer,shorter))
    assert len(kept)==1
    assert np.allclose(kept[0][:,1],100)


def test_parallel_far_apart_both_kept():
    assert len(preprocess_lines(candidate(line([0,100],[639,100]),line([0,300],[639,300]))))==2


def test_negative_slope_preserved_and_shuffled_trace_ordered():
    points=line([0,400],[639,0],80)
    shuffled=points[np.random.default_rng(2).permutation(80)]
    out=preprocess_lines(candidate(shuffled))[0]
    np.testing.assert_allclose(out,points,atol=1e-8)


def test_crossing_edges_not_merged():
    a=line([0,80],[630,400]); b=line([0,400],[630,80])
    assert len(preprocess_lines(candidate(a,b)))==2


def test_radial_order_does_not_join_opposite_sides_of_center():
    points=line([0,240],[639,240],160)
    shuffled=points[np.random.default_rng(3).permutation(160)]
    ordered=preprocess_lines(candidate(shuffled))[0]
    assert np.all(np.diff(ordered[:,0])>0)
    np.testing.assert_allclose(ordered[:,1],240)
