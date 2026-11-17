"""Reverse upload admission and immutable snapshots of correction geometry."""
from pathlib import Path
from types import SimpleNamespace
import json
import shutil
from fastapi import APIRouter,UploadFile,File,Form,Request
from .engine.reverse import ReverseError,prepare_reverse_upload,resolve_basis
from .engine.transforms import load_transform
from .engine.remap import render_full_resolution
from .images import MAX_BYTES
from .jobs import JOB_ID

router=APIRouter()


def require_parent(record):
    if record.get('status')!='succeeded':raise ReverseError('parent_not_ready','原任务尚未完成',409)
    if record.get('kind','correction')!='correction' or record.get('outcome')!='corrected':
        raise ReverseError('model_unavailable','本次未应用校正，无可复用的校正模型',409)


def materialize_correction_assets(directory,record,check_deadline=lambda:None):
    require_parent(record)
    try:
        spec=load_transform(directory)
        uncropped=directory/'uncropped.png';mask=directory/'valid-mask.png'
        if not uncropped.is_file() or not mask.is_file():
            # The saved ROI is authoritative. Never re-estimate or overwrite result.png.
            scratch=directory/'backfill-cropped.png'
            render_full_resolution(SimpleNamespace(normalized_path=directory/'normalized.png'),spec.as_candidate(),scratch,check_deadline,crop_override=spec.crop)
            if scratch.parent.resolve()!=directory.resolve():raise ValueError('invalid artifact path')
            scratch.unlink(missing_ok=True)
        from PIL import Image
        import numpy as np
        for path in (uncropped,mask):
            with Image.open(path) as image:
                if image.size!=spec.canvas_size:raise ValueError('不一致的参考画布尺寸')
        # Older canvases of fully opaque sources may still carry alpha holes that
        # the reverse uploader (correctly) rejects. Repair only that exact case.
        with Image.open(directory/'normalized.png') as source_image:
            source_is_opaque=source_image.mode!='RGBA' or np.all(np.array(source_image.getchannel('A'))==255)
        if source_is_opaque:
            with Image.open(uncropped) as canvas:
                if canvas.mode=='RGBA' and np.any(np.array(canvas.getchannel('A'))<255):
                    repaired=canvas.copy();repaired.putalpha(255)
                    temp=uncropped.with_suffix('.tmp');repaired.save(temp,format='PNG');temp.replace(uncropped)
        spec.save(directory/'transform.json')
        return spec
    except (ValueError,OSError) as exc:
        raise ReverseError('model_unavailable','校正记录缺失或不一致，请重新处理原图',409) from exc


def describe_correction(directory,record):
    if record.get('status')!='succeeded' or record.get('outcome')!='corrected' or record.get('kind','correction')!='correction':return {'can_reverse':False}
    try:
        spec=load_transform(directory)
        return {'can_reverse':True,'transform_version':spec.version,'uncropped_width':spec.canvas_size[0],'uncropped_height':spec.canvas_size[1],
                'uncropped_download_url':f"/api/jobs/{record['id']}/download?variant=uncropped"}
    except (ValueError,OSError):return {'can_reverse':False}


@router.post('/api/jobs/{parent_id}/reverse',status_code=202)
def upload_reverse(parent_id:str,request:Request,image:UploadFile=File(...),basis:str=Form('auto')):
    manager=request.app.state.manager
    if not JOB_ID.fullmatch(parent_id):raise ReverseError('parent_not_found','原任务不存在',404)
    if manager.get(parent_id) is None:
        status=410 if parent_id in manager.expired else 404
        raise ReverseError('parent_expired' if status==410 else 'parent_not_found','原任务已过期' if status==410 else '原任务不存在',status)
    identifier,directory=manager.allocate()
    admitted=False
    try:
        with manager.pin(parent_id) as (parent,record):
            require_parent(record)
            with (directory/'source').open('wb') as target:
                size=0
                while chunk:=image.file.read(1024*1024):
                    size+=len(chunk)
                    if size>MAX_BYTES:raise ReverseError('upload_too_large','图片超过 20 MiB',413)
                    target.write(chunk)
            info=prepare_reverse_upload(directory/'source',directory/'upload')
            spec=materialize_correction_assets(parent,record)
            match=resolve_basis((info.width,info.height),spec,basis)
            shutil.copyfile(parent/'normalized.png',directory/'normalized.png')
            shutil.copyfile(parent/'original.jpg',directory/'original.jpg')
            shutil.copyfile(parent/'valid-mask.png',directory/'valid-mask.png')
            shutil.copyfile(info.normalized_path,directory/'upload.png')
            shutil.copyfile(info.preview_path,directory/'upload.jpg')
            spec.save(directory/'transform.json')
            (directory/'reverse-request.json').write_text(json.dumps({'basis':match.name,'transform_fingerprint':spec.fingerprint},indent=2))
            manager.submit(identifier,image.filename or 'image',info,kind='reverse',parent_id=parent_id,reference_basis=match.name)
            admitted=True
        return {'id':identifier,'status':'queued'}
    except FileNotFoundError as exc:
        raise ReverseError('parent_expired','原任务已过期，请重新处理原图',410) from exc
    finally:
        image.file.close()
        if not admitted:manager.discard(directory)
