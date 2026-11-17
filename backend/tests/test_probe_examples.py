from pathlib import Path
import pytest
from PIL import Image
from app.engine.probe import load_job_estimate


def test_load_job_estimate_reads_existing_job(tmp_path):
    job='a'*32
    directory=tmp_path/job;directory.mkdir()
    Image.new('RGB',(900,603),'white').save(directory/'estimate.png')
    for name in ('pol-0.8','pol-0.9','div-0.8','center-div'):
        candidate=directory/name;candidate.mkdir()
        (candidate/'primitives.txt').write_text('DISTORTION MODEL\ndistortion center = (450 301.5)\nNumber of distortion parameters = 3\nvalue of distortion parameter 0 = 1\nvalue of distortion parameter 1 = 0\nvalue of distortion parameter 2 = 0\nNUMBER OF LINES = 0\n')
    bundle=load_job_estimate(job,jobs_root=tmp_path)
    assert bundle.size==(900,603)
    assert len(bundle.candidates)==4
    assert all(p.exists() for p in bundle.primitive_paths)


def test_missing_job_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_job_estimate('0'*32,jobs_root=tmp_path)
