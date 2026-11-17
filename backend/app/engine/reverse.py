"""Whole-image pull sampling back onto the original image's coordinate canvas."""
from dataclasses import dataclass
from pathlib import Path
import time
import json
import cv2
import numpy as np
from PIL import Image
from .transforms import TransformSpec,original_to_canvas
from ..images import normalize_image,ImageError,make_preview


class ReverseError(ValueError):
    def __init__(self,code,detail,status=422,reference_sizes=None):
        super().__init__(detail);self.code=code;self.status=status;self.reference_sizes=reference_sizes


@dataclass(frozen=True)
class BasisMatch:
    name: str
    reference_size: tuple[int,int]
    upload_size: tuple[int,int]


@dataclass
class ReverseResult:
    size: tuple[int,int]
    covered_fraction: float
    basis: str


def resolve_basis(upload_size,spec,requested_basis='auto'):
    x0,y0,x1,y1=spec.crop
    sizes={'cropped':(x1-x0,y1-y0),'uncropped':spec.canvas_size}
    if requested_basis not in ('auto','cropped','uncropped'):
        raise ReverseError('invalid_basis','参考版本无效')
    if len(upload_size)!=2 or min(upload_size)<=0:raise ReverseError('invalid_image','图片尺寸无效')
    matches=[key for key,size in sizes.items() if tuple(upload_size)==size]
    if requested_basis!='auto':
        size=sizes[requested_basis]
        ratio_error=abs((upload_size[0]/upload_size[1])/(size[0]/size[1])-1)
        if ratio_error>.001:raise ReverseError('aspect_ratio_mismatch','图片比例与参考版本不一致，请按原画布比例导出',reference_sizes=sizes)
        return BasisMatch(requested_basis,size,tuple(upload_size))
    if not matches:
        matches=[key for key,size in sizes.items() if abs((upload_size[0]/upload_size[1])/(size[0]/size[1])-1)<=.001]
    if not matches:raise ReverseError('aspect_ratio_mismatch','图片尺寸不匹配，请使用裁切版或未裁切版的原画布比例',reference_sizes=sizes)
    if len(matches)>1 and sizes['cropped']!=sizes['uncropped']:
        raise ReverseError('basis_ambiguous','无法唯一识别参考版本，请选择基于裁切图或未裁切图',reference_sizes=sizes)
    name=matches[0]
    return BasisMatch(name,sizes[name],tuple(upload_size))


def prepare_reverse_upload(source,work_dir):
    try:info=normalize_image(source,work_dir)
    except ImageError as exc:
        code={413:'upload_too_large',415:'unsupported_image'}.get(exc.status,'invalid_image')
        raise ReverseError(code,str(exc),exc.status) from exc
    if info.transparent:raise ReverseError('transparent_input','请上传不透明的整张图片',415)
    return info


def render_reverse(upload_path,original_path,spec,basis,output_path,check_deadline=lambda:None,*,mask_path=None):
    check_deadline()
    with Image.open(upload_path) as image:upload=np.array(image.convert('RGB'))
    with Image.open(original_path) as image:original=np.array(image.convert('RGB'))
    if (original.shape[1],original.shape[0])!=spec.original_size:raise ReverseError('invalid_transform','原图尺寸与几何记录不一致',409)
    upload_size=(upload.shape[1],upload.shape[0])
    match=resolve_basis(upload_size,spec,basis.name if isinstance(basis,BasisMatch) else basis)
    rw,rh=match.reference_size
    if mask_path is not None:
        with Image.open(mask_path) as image:
            if image.size!=spec.canvas_size:raise ReverseError('invalid_transform','覆盖掩码尺寸不一致',409)
            mask=np.array(image.convert('L'),dtype=np.float32)/255
        if match.name=='cropped':
            x0,y0,x1,y1=spec.crop;mask=mask[y0:y1,x0:x1]
        shrinking=upload_size[0]<rw or upload_size[1]<rh
        # Averaging avoids sampling past a thin invalid border when shrinking.
        weights=cv2.resize(mask,upload_size,interpolation=cv2.INTER_AREA if shrinking else cv2.INTER_LINEAR)
    else:weights=np.ones(upload.shape[:2],dtype=np.float32)
    # Coverage is binary on purpose: a resampled fractional weight blends the
    # uploader's black padding into valid original pixels around a thin invalid
    # border. Partial coverage is never needed, because uploads are opaque.
    weights=np.where(weights>=.999,1.,0.).astype(np.uint8)
    if weights.size and not weights.all():
        # Bilinear sampling of the upload reaches one pixel past a boundary, so
        # erode the valid area rather than letting padding bleed inwards.
        weights=cv2.erode(weights,np.ones((3,3),np.uint8))
    weights=weights.astype(np.float32)
    premultiplied=upload.astype(np.float32)
    premultiplied*=weights[...,None]
    result=np.empty_like(original)
    w,h=spec.original_size;covered=0.
    for y0 in range(0,h,128):
        check_deadline();y1=min(h,y0+128)
        yy,xx=np.mgrid[y0:y1,0:w]
        points=np.stack((xx,yy),axis=-1)
        coords=original_to_canvas(points,spec)
        if match.name=='cropped':coords=coords-np.array(spec.crop[:2])
        valid=np.isfinite(coords).all(axis=-1)&(coords[...,0]>=-1e-6)&(coords[...,0]<=rw-1+1e-6)&(coords[...,1]>=-1e-6)&(coords[...,1]<=rh-1+1e-6)
        mx=np.clip((coords[...,0]+.5)*upload_size[0]/rw-.5,0,upload_size[0]-1).astype(np.float32)
        my=np.clip((coords[...,1]+.5)*upload_size[1]/rh-.5,0,upload_size[1]-1).astype(np.float32)
        mx=np.nan_to_num(mx);my=np.nan_to_num(my)
        alpha=cv2.remap(weights,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)*valid
        sampled=cv2.remap(premultiplied,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
        composed=sampled*valid[...,None]+original[y0:y1]*(1-alpha[...,None])
        result[y0:y1]=np.clip(np.rint(composed),0,255).astype(np.uint8)
        covered+=float(alpha.sum())
    check_deadline();Image.fromarray(result).save(output_path)
    return ReverseResult((w,h),covered/(w*h),match.name)


def process_reverse_job(directory,stage,cancel_event=None):
    from .ipol import EngineError
    started=time.monotonic()
    def check():
        if cancel_event is not None and cancel_event.is_set():raise EngineError('任务已取消')
        if time.monotonic()-started>180:raise EngineError('反算任务超过计算时限')
    stage('preparing')
    spec=TransformSpec.from_dict(json.loads((directory/'transform.json').read_text()))
    request=json.loads((directory/'reverse-request.json').read_text())
    stage('reverse_mapping')
    result=render_reverse(directory/'upload.png',directory/'normalized.png',spec,request['basis'],directory/'result.png',check,mask_path=directory/'valid-mask.png')
    stage('finishing');make_preview(directory/'result.png',directory/'result.jpg')
    return {'outcome':'reversed','reason_code':'reverse_mapped','message':'已按当前校正参数完成整图反算，未覆盖区域保留原图。',
            'output_width':result.size[0],'output_height':result.size[1],'reference_basis':result.basis,
            'covered_fraction':result.covered_fraction,'elapsed_seconds':round(time.monotonic()-started,2)}
