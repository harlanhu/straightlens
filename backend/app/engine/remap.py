"""IPOL pixel-radius pol/div conventions, independent of OpenCV camera k1/k2."""
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from .ipol import CandidateResult


def radial(radius, candidate: CandidateResult):
    r2 = np.asarray(radius, dtype=float)**2
    a = candidate.coefficients
    factor = a[0] + a[1]*r2 + (a[2]*r2*r2 if len(a)>2 else 0)
    with np.errstate(divide='ignore',invalid='ignore'):
        return np.asarray(radius)*factor if candidate.config.model=='pol' else np.asarray(radius)/factor


def correct_points(points, candidate):
    points = np.asarray(points,dtype=float)
    delta = points - candidate.center
    r = np.linalg.norm(delta,axis=-1)
    factor = np.divide(radial(r,candidate),r,out=np.ones_like(r),where=r>0)
    return candidate.center + delta*factor[...,None]


def valid_model(candidate):
    w,h = candidate.size
    cx,cy = candidate.center
    if not (.2*w <= cx <= .8*w and .2*h <= cy <= .8*h):
        return False
    max_r = max(np.hypot(x-cx,y-cy) for x,y in ((0,0),(w,0),(0,h),(w,h)))
    radii = np.linspace(0,max_r,4096)
    values = radial(radii,candidate)
    slopes = np.diff(values)/np.diff(radii)
    return bool(np.isfinite(values).all() and np.all(slopes>.08) and np.all(slopes<10))


def image_scale(candidate):
    w,_ = candidate.size
    cx,_ = candidate.center
    # Mirrors upstream FIT_WIDTH: denominator is cx for both sides.
    return min(float(radial(w-cx,candidate))/cx, float(radial(cx,candidate))/cx)


def map_block(candidate, full_size, y0, y1):
    w,h = full_size
    sw,sh = candidate.size
    sx,sy = w/sw,h/sh
    cx,cy = candidate.center
    yy,xx = np.mgrid[y0:y1,0:w]
    scale = image_scale(candidate)
    dx = (xx/sx-cx)*scale
    dy = (yy/sy-cy)*scale
    ru = np.hypot(dx,dy)
    max_r = max(np.hypot(x-cx,y-cy) for x,y in ((0,0),(sw,0),(0,sh),(sw,sh)))
    rd = np.linspace(0,max_r,16384)
    mapped = radial(rd,candidate)
    inv = np.interp(ru,mapped,rd,left=0,right=np.nan)
    factor = np.divide(inv,ru,out=np.ones_like(inv),where=ru>0)
    mx = ((cx+dx*factor)*sx).astype('float32')
    my = ((cy+dy*factor)*sy).astype('float32')
    valid = np.isfinite(mx)&np.isfinite(my)&(mx>=0)&(my>=0)&(mx<=w-1)&(my<=h-1)
    return np.nan_to_num(mx,nan=-1),np.nan_to_num(my,nan=-1),valid


def valid_crop(mask):
    """Deterministic large centered all-valid rectangle, no inpainting."""
    h,w = mask.shape
    best = None
    for trim in np.linspace(0,int(h*.4),60,dtype=int):
        rows = mask[trim:h-trim or h]
        usable = rows.all(axis=0)
        indices = np.flatnonzero(usable)
        if not len(indices):
            continue
        breaks = np.where(np.diff(indices)>1)[0]+1
        for run in np.split(indices,breaks):
            area = len(run)*len(rows)
            if best is None or area>best[0]:
                best=(area,int(run[0]),int(trim),int(run[-1])+1,h-int(trim))
    if best is None:
        raise ValueError('没有有效的校正区域')
    return best[1:]

@dataclass
class RenderResult:
    size: tuple[int,int]
    crop: tuple[int,int,int,int]
    retained_area: float
    uncropped_path: Path | None = None
    mask_path: Path | None = None
    canvas_size: tuple[int,int] | None = None


def render_full_resolution(image, candidate, output_path: Path, check_deadline=lambda:None, *, crop_override=None) -> RenderResult:
    if not valid_model(candidate):
        raise ValueError('无效的几何映射')
    with Image.open(image.normalized_path) as source:
        source_array=np.array(source)
    h,w=source_array.shape[:2]
    result=np.empty_like(source_array)
    valid=np.empty((h,w),dtype=bool)
    for y in range(0,h,128):
        check_deadline()
        end=min(y+128,h)
        mx,my,mask=map_block(candidate,(w,h),y,end)
        result[y:end]=cv2.remap(source_array,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        valid[y:end]=mask
    check_deadline()
    # An opaque RGBA input must download as an opaque whole canvas, including
    # black padding, so users can upload that canvas to the opaque reverse API.
    if source_array.ndim==3 and source_array.shape[2]==4 and np.all(source_array[...,3]==255):
        result[...,3]=255
    crop=valid_crop(valid) if crop_override is None else tuple(crop_override)
    x0,y0,x1,y1=crop
    if not (0<=x0<x1<=w and 0<=y0<y1<=h):raise ValueError('裁切框越界')
    uncropped_path=output_path.parent/'uncropped.png'
    mask_path=output_path.parent/'valid-mask.png'
    Image.fromarray(result).save(uncropped_path)
    Image.fromarray(valid.astype('uint8')*255).save(mask_path)
    Image.fromarray(result[y0:y1,x0:x1]).save(output_path)
    return RenderResult((x1-x0,y1-y0),crop,(x1-x0)*(y1-y0)/(w*h),uncropped_path,mask_path,(w,h))
