from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from app.engine.ipol import CandidateConfig,CandidateResult
from app.engine.transforms import TransformSpec
from app.engine.reverse import render_reverse,resolve_basis,ReverseError


def spec(size=(200,140),crop=None):
    c=CandidateResult(CandidateConfig('pol',.8),(1.,0.,0.),(50.,35.),(100,70),[],Path('.'))
    return TransformSpec.from_candidate(c,size,crop or (0,0,*size))


def files(tmp_path,upload_size=(200,140)):
    original=tmp_path/'original.png';upload=tmp_path/'upload.png'
    Image.new('RGB',(200,140),(17,31,47)).save(original)
    Image.new('RGB',upload_size,(210,30,70)).save(upload)
    return original,upload


def test_identity_reverse_exact(tmp_path):
    original,upload=files(tmp_path)
    output=tmp_path/'result.png'
    result=render_reverse(upload,original,spec(),'auto',output)
    np.testing.assert_array_equal(np.array(Image.open(output)),np.array(Image.open(upload)))
    assert result.size==(200,140)


def test_crop_offset_preserves_outside_original(tmp_path):
    original,upload=files(tmp_path,(160,120))
    image=Image.open(upload);image.putpixel((20,30),(0,255,0));image.save(upload)
    output=tmp_path/'result.png'
    render_reverse(upload,original,spec(crop=(20,10,180,130)),'cropped',output)
    array=np.array(Image.open(output))
    np.testing.assert_array_equal(array[40,40],[0,255,0])
    np.testing.assert_array_equal(array[:10],np.array(Image.open(original))[:10])
    np.testing.assert_array_equal(array[:,180:],np.array(Image.open(original))[:,180:])


def test_uncropped_invalid_border_does_not_blacken_original(tmp_path):
    original,upload=files(tmp_path)
    mask=np.full((140,200),255,dtype=np.uint8);mask[:,:30]=0
    Image.fromarray(mask).save(tmp_path/'mask.png')
    output=tmp_path/'result.png'
    render_reverse(upload,original,spec(),'uncropped',output,mask_path=tmp_path/'mask.png')
    out=np.array(Image.open(output))
    np.testing.assert_array_equal(out[:,:30],np.array(Image.open(original))[:,:30])
    np.testing.assert_array_equal(out[:,31:],np.array(Image.open(upload))[:,31:])


def test_opaque_unrelated_image_is_mapped_without_diff(tmp_path):
    original,upload=files(tmp_path)
    output=tmp_path/'result.png';render_reverse(upload,original,spec(),'auto',output)
    assert np.array(Image.open(output))[50,50].tolist()==[210,30,70]
    render_reverse(original,original,spec(),'auto',output)
    np.testing.assert_array_equal(np.array(Image.open(output)),np.array(Image.open(original)))


def test_resize_pixel_center_alignment(tmp_path):
    original,upload=files(tmp_path,(400,280))
    render_reverse(upload,original,spec(),'auto',tmp_path/'result.png')
    assert Image.open(tmp_path/'result.png').size==(200,140)
    assert np.array(Image.open(tmp_path/'result.png'))[0,0].tolist()==[210,30,70]


def test_upscaled_upload_uses_pixel_center_coordinates(tmp_path):
    original,upload=files(tmp_path,(400,280))
    yy,xx=np.mgrid[:280,:400]
    pattern=np.stack((np.clip(100+2*xx,0,255),np.clip(3*yy,0,255),np.full_like(xx,40)),axis=-1).astype(np.uint8)
    Image.fromarray(pattern).save(upload)
    output=tmp_path/'centers.png'
    render_reverse(upload,original,spec(),'uncropped',output)
    # Original (11,13) samples upload (22.5,26.5), not (22,26).
    assert np.array(Image.open(output))[13,11].tolist()==[145,80,40]


def test_basis_exact_and_scaled():
    s=spec(crop=(20,10,180,130))
    assert resolve_basis((160,120),s,'auto').name=='cropped'
    assert resolve_basis((200,140),s,'auto').name=='uncropped'
    assert resolve_basis((80,60),s,'auto').name=='cropped'
    assert resolve_basis((200,140),spec(),'auto').name=='cropped'


def test_ambiguous_basis_is_not_guessed():
    s=spec(size=(1000,700),crop=(0,0,999,700))
    with pytest.raises(ReverseError) as error:resolve_basis((2000,1401),s,'auto')
    assert error.value.code=='basis_ambiguous'
    assert resolve_basis((2000,1401),s,'uncropped').name=='uncropped'


@pytest.mark.parametrize('kind',['pol','div'])
def test_gradient_forward_reverse_roundtrip(tmp_path,kind):
    from types import SimpleNamespace
    from app.engine.remap import render_full_resolution
    yy,xx=np.mgrid[:200,:320]
    original=np.stack((xx*.5,yy,xx*.2+yy*.3),axis=-1).astype(np.uint8)
    source=tmp_path/'original.png';Image.fromarray(original).save(source)
    c=CandidateResult(CandidateConfig(kind,.8),(1.,1e-5,0.),(75.,47.),(160,100),[],tmp_path)
    rendered=render_full_resolution(SimpleNamespace(normalized_path=source),c,tmp_path/'corrected.png')
    s=TransformSpec.from_candidate(c,(320,200),rendered.crop)
    render_reverse(tmp_path/'corrected.png',source,s,'cropped',tmp_path/'reversed.png',mask_path=rendered.mask_path)
    actual=np.array(Image.open(tmp_path/'reversed.png')).astype(float)
    assert np.mean(np.abs(actual[2:-2,2:-2]-original[2:-2,2:-2]))<2


def test_reverse_upload_orientation_and_transparency(tmp_path):
    from app.engine.reverse import prepare_reverse_upload
    source=tmp_path/'oriented.jpg';exif=Image.Exif();exif[274]=6
    Image.new('RGB',(120,160),'red').save(source,exif=exif)
    info=prepare_reverse_upload(source,tmp_path/'oriented')
    assert (info.width,info.height)==(160,120)
    source=tmp_path/'transparent.png';Image.new('RGBA',(80,60),(10,20,30,100)).save(source)
    with pytest.raises(ReverseError) as error:prepare_reverse_upload(source,tmp_path/'alpha')
    assert error.value.status==415


def test_ratio_mismatch_rejected():
    with pytest.raises(ReverseError) as error:resolve_basis((200,200),spec(),'cropped')
    assert error.value.code=='aspect_ratio_mismatch'
