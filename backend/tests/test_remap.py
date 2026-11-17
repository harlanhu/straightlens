from pathlib import Path
import numpy as np
from PIL import Image
from app.engine.ipol import CandidateConfig,CandidateResult
from app.engine.remap import map_block,correct_points,render_full_resolution
from app.images import normalize_image


def model(size=(160,100),coeff=(1.,0.,0.),kind='pol',center=None):
    return CandidateResult(CandidateConfig(kind,.8),coeff,center or (size[0]/2,size[1]/2),size,[],Path('.'))


def test_identity_maps_pixels():
    mx,my,valid=map_block(model(),(160,100),0,100)
    y,x=np.mgrid[:100,:160]
    np.testing.assert_allclose(mx,x,atol=1e-4)
    np.testing.assert_allclose(my,y,atol=1e-4)
    assert valid.all()


def test_scaled_model_same_normalized_mapping():
    c=model(coeff=(1.,2e-5,0.))
    ax,ay,_=map_block(c,(160,100),0,100)
    bx,by,_=map_block(c,(320,200),0,200)
    np.testing.assert_allclose(bx[::2,::2]/2,ax,atol=1e-4)
    np.testing.assert_allclose(by[::2,::2]/2,ay,atol=1e-4)


def test_render_identity_full_resolution(tmp_path):
    path=tmp_path/'input.png'
    array=np.random.default_rng(1).integers(0,256,(100,160,4),dtype=np.uint8)
    Image.fromarray(array).save(path)
    info=normalize_image(path,tmp_path/'work')
    output=tmp_path/'result.png'
    result=render_full_resolution(info,model(),output)
    assert result.size==(160,100)
    np.testing.assert_array_equal(np.array(Image.open(output)),array)
