from pathlib import Path
import sys
import threading
import time
import numpy as np
import pytest
from PIL import Image
from app.engine import ipol
from app.engine.ipol import CandidateConfig,run_ipol,EngineError
from app.images import normalize_image
from app.engine.remap import render_full_resolution,valid_model


def fake_binary(tmp_path,monkeypatch,body):
    script=tmp_path/'fake_engine'
    script.write_text(f'#!{sys.executable}\n'+body)
    script.chmod(0o755)
    monkeypatch.setattr(ipol,'BINARY',script)
    image=tmp_path/'input.png';Image.new('RGB',(80,60),'white').save(image)
    return image


def test_timeout_terminates_process(tmp_path,monkeypatch):
    image=fake_binary(tmp_path,monkeypatch,'import time\ntime.sleep(60)\n')
    start=time.monotonic()
    with pytest.raises(EngineError,match='超时'):
        run_ipol(image,CandidateConfig('div',.8),tmp_path/'work',.1)
    assert time.monotonic()-start<2


def test_cancel_terminates_process(tmp_path,monkeypatch):
    image=fake_binary(tmp_path,monkeypatch,'import time\ntime.sleep(60)\n')
    cancel=threading.Event();cancel.set()
    with pytest.raises(EngineError,match='取消'):
        run_ipol(image,CandidateConfig('div',.8),tmp_path/'work',20,cancel_event=cancel)


def test_zero_exit_without_output_is_error(tmp_path,monkeypatch):
    image=fake_binary(tmp_path,monkeypatch,'pass\n')
    with pytest.raises(EngineError,match='未产生有效输出'):
        run_ipol(image,CandidateConfig('div',.8),tmp_path/'work',2)


@pytest.mark.skipif(not ipol.BINARY.exists(),reason='build IPOL first')
def test_offcenter_can_reach_center_refinement(tmp_path):
    from scripts.evaluate import generate,geometry_metrics
    from app.engine.pipeline import process_image
    generate(tmp_path/'samples')
    work=tmp_path/'work'
    result=process_image(tmp_path/'samples/grid_offcenter.png',work)
    assert result['outcome']=='corrected'
    metrics=geometry_metrics('grid_offcenter',work)
    assert metrics['geometry_rms_after_px']<metrics['geometry_rms_before_px']*.8


@pytest.mark.skipif(not ipol.BINARY.exists(),reason='build IPOL first')
@pytest.mark.parametrize('model',['pol','div'])
def test_mapping_matches_native_render(tmp_path,model):
    source=ipol.ROOT/'third_party/ipol/example/building.png'
    info=normalize_image(source,tmp_path/'images')
    candidate=run_ipol(info.estimate_path,CandidateConfig(model,.8),tmp_path/'native',25)
    # Match source dimensions exactly to native estimate, then compare after our crop.
    info.normalized_path=info.estimate_path
    output=tmp_path/'mapped.png'
    if not valid_model(candidate):
        pytest.skip('native candidate is non-invertible on this platform')
    rendered=render_full_resolution(info,candidate,output)
    native=np.array(Image.open(tmp_path/'native/corrected.png')).astype(float)
    x0,y0,x1,y1=rendered.crop
    ours=np.array(Image.open(output)).astype(float)
    difference=np.abs(native[y0:y1,x0:x1]-ours)
    assert float(difference.mean())<2.5
