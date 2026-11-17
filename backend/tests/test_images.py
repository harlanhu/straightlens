from pathlib import Path
import pytest
from PIL import Image
from app.images import normalize_image, ImageError


def test_exif_orientation(tmp_path):
    path=tmp_path/'source.jpg'
    exif=Image.Exif(); exif[274]=6
    Image.new('RGB',(80,40)).save(path,exif=exif)
    result=normalize_image(path,tmp_path/'out')
    assert (result.width,result.height)==(40,80)


def test_corrupt_rejected(tmp_path):
    path=tmp_path/'bad.png'; path.write_bytes(b'not an image')
    with pytest.raises(ImageError) as exc:
        normalize_image(path,tmp_path/'out')
    assert exc.value.status==422


def test_animation_rejected(tmp_path):
    path=tmp_path/'animated.png'
    Image.new('RGB',(20,20),'red').save(path,save_all=True,append_images=[Image.new('RGB',(20,20),'blue')])
    with pytest.raises(ImageError): normalize_image(path,tmp_path/'out')


def test_transparency_retained(tmp_path):
    path=tmp_path/'alpha.png'; Image.new('RGBA',(80,80),(255,0,0,100)).save(path)
    result=normalize_image(path,tmp_path/'out')
    assert Image.open(result.normalized_path).mode=='RGBA'


def test_pixel_limit(tmp_path,monkeypatch):
    import app.images as module
    monkeypatch.setattr(module,'MAX_PIXELS',100)
    path=tmp_path/'big.png';Image.new('RGB',(20,20)).save(path)
    with pytest.raises(ImageError) as exc: normalize_image(path,tmp_path/'out')
    assert exc.value.status==413
