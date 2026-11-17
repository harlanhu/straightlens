from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from app.engine.ipol import CandidateConfig,CandidateResult
from app.engine.transforms import TransformSpec
from app.engine.reverse import render_reverse


def make(tmp_path):
    """Identity geometry with a two-pixel invalid border on a 640×480 canvas."""
    width,height=640,480
    original=np.empty((height,width,3),dtype=np.uint8)
    original[...,0]=np.arange(width,dtype=np.uint8)[None,:]
    original[...,1]=np.arange(height,dtype=np.uint8)[:,None]
    original[...,2]=90
    source=tmp_path/'original.png';Image.fromarray(original).save(source)
    c=CandidateResult(CandidateConfig('pol',.8),(1.,0.,0.),(width/2,height/2),(width,height),[],tmp_path)
    spec=TransformSpec.from_candidate(c,(width,height),(8,6,width-8,height-6))
    mask=np.full((height,width),255,dtype=np.uint8)
    mask[:2,:]=mask[-2:,:]=mask[:,:2]=mask[:,-2:]=0
    mask_path=tmp_path/'valid-mask.png';Image.fromarray(mask).save(mask_path)
    padding=original.copy();padding[mask==0]=0
    uncropped=tmp_path/'uncropped.png';Image.fromarray(padding).save(uncropped)
    cropped=tmp_path/'cropped.png';Image.fromarray(padding[6:height-6,8:width-8]).save(cropped)
    return source,original,spec,mask_path,uncropped,cropped


@pytest.mark.parametrize('factor',[1.0,0.5,0.1])
def test_scaled_uncropped_upload_never_blackens_invalid_original_pixels(tmp_path,factor):
    source,original,spec,mask_path,uncropped,cropped=make(tmp_path)
    with Image.open(uncropped) as full:
        target=(max(1,int(full.width*factor)),max(1,int(full.height*factor)))
        upload=tmp_path/f'scaled-{factor}.png'
        full.resize(target,Image.LANCZOS).save(upload)
    output=tmp_path/f'result-{factor}.png'
    render_reverse(upload,source,spec,'uncropped',output,mask_path=mask_path)
    result=np.array(Image.open(output))
    with Image.open(mask_path) as mask_image:invalid=np.array(mask_image)==0
    # The whole guarantee: pixels without valid upload coverage stay the original.
    np.testing.assert_array_equal(result[invalid],original[invalid])
    darker=np.mean((original.astype(int)-result.astype(int))[~invalid].max(axis=1)>10)
    # Remaining variation is ringing baked into the resized upload, not our blend.
    assert darker<.08,darker


def test_scaled_cropped_upload_preserves_outside(tmp_path):
    source,original,spec,mask_path,uncropped,cropped=make(tmp_path)
    with Image.open(cropped) as image:
        upload=tmp_path/'half.png'
        image.resize((image.width//2,image.height//2),Image.LANCZOS).save(upload)
    output=tmp_path/'out.png'
    render_reverse(upload,source,spec,'cropped',output,mask_path=mask_path)
    result=np.array(Image.open(output))
    assert np.array_equal(result[:, :4],original[:, :4])
