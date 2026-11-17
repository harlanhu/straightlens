from pathlib import Path
from contextlib import asynccontextmanager
import os
import tempfile
from fastapi import FastAPI,File,UploadFile,Request
from typing import Literal
from .engine.reverse import ReverseError
from .reverse_api import router as reverse_router,describe_correction,materialize_correction_assets
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from .jobs import JobManager,BusyError,JOB_ID
from .images import normalize_image,ImageError,MAX_BYTES
from .engine.ipol import BINARY
from .schemas import JobAccepted,JobView


def create_app(data_root: Path|None=None, processor=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.manager.start()
        try:
            yield
        finally:
            app.state.manager.close()
    app=FastAPI(title='StraightLens',docs_url=None,redoc_url=None,lifespan=lifespan)
    root=Path(data_root or os.environ.get('STRAIGHTLENS_DATA', os.environ.get('LENSLINE_DATA', Path(tempfile.gettempdir())/'straightlens')))
    app.state.manager=JobManager(root,processor=processor) if processor else JobManager(root)

    @app.exception_handler(ImageError)
    async def image_error(_request,exc):return JSONResponse({'detail':str(exc)},status_code=exc.status)

    @app.exception_handler(ReverseError)
    async def reverse_error(_request,exc):
        body={'code':exc.code,'detail':str(exc)}
        if exc.reference_sizes is not None:body['reference_sizes']=exc.reference_sizes
        return JSONResponse(body,status_code=exc.status)

    app.include_router(reverse_router)

    @app.exception_handler(BusyError)
    async def busy(_request,_exc):return JSONResponse({'detail':'当前排队任务已满，请稍后再试。'},status_code=429)

    @app.get('/api/health')
    def health():
        return {'ok':BINARY.is_file(),'algorithm_ready':BINARY.is_file()}

    @app.post('/api/jobs',response_model=JobAccepted,status_code=202)
    def create_job(request: Request,image: UploadFile=File(...)):
        manager: JobManager=request.app.state.manager
        identifier,directory=manager.allocate()
        try:
            with (directory/'source').open('wb') as target:
                size=0
                while chunk:=image.file.read(1024*1024):
                    size+=len(chunk)
                    if size>MAX_BYTES:raise ImageError('图片超过 20 MiB，请选择较小的图片',413)
                    target.write(chunk)
            info=normalize_image(directory/'source',directory)
            manager.submit(identifier,image.filename or 'image',info)
        except BaseException:
            manager.discard(directory)
            raise
        return {'id':identifier,'status':'queued'}

    @app.get('/api/jobs/{identifier}',response_model=JobView)
    def read_job(identifier: str,request: Request):
        if not JOB_ID.fullmatch(identifier):return JSONResponse({'detail':'任务不存在'},status_code=404)
        record=request.app.state.manager.get(identifier)
        if not record:
            status=410 if identifier in request.app.state.manager.expired else 404
            return JSONResponse({'detail':'任务已过期' if status==410 else '任务不存在'},status_code=status)
        view={key:record.get(key) for key in JobView.model_fields if key in record}
        view.update(describe_correction(request.app.state.manager.root/identifier,record))
        if record['status']=='succeeded':
            view['original_preview_url']=f'/api/jobs/{identifier}/preview/original'
            view['result_preview_url']=f'/api/jobs/{identifier}/preview/result'
            view['download_url']=f'/api/jobs/{identifier}/download'
            view['original_image_url']=f'/api/jobs/{identifier}/image/original'
            view['result_image_url']=f'/api/jobs/{identifier}/image/result'
            if record.get('kind')=='reverse':
                view['upload_preview_url']=f'/api/jobs/{identifier}/preview/upload'
                view['upload_image_url']=f'/api/jobs/{identifier}/image/upload'
        return view

    def completed(identifier):
        if not JOB_ID.fullmatch(identifier):return None,JSONResponse({'detail':'任务不存在'},status_code=404)
        record=app.state.manager.get(identifier)
        if not record:return None,JSONResponse({'detail':'任务不存在'},status_code=404)
        if record['status']!='succeeded':return None,JSONResponse({'detail':'任务尚未完成'},status_code=409)
        return record,None

    @app.get('/api/jobs/{identifier}/preview/{kind}')
    def preview(identifier: str,kind: str,request: Request):
        record,error=completed(identifier)
        if error:return error
        if kind not in ('original','result','upload') or (kind=='upload' and record.get('kind')!='reverse'):return JSONResponse({'detail':'预览不存在'},status_code=404)
        path=request.app.state.manager.root/identifier/({'original':'original.jpg','result':'result.jpg','upload':'upload.jpg'}[kind])
        if not path.is_file():return JSONResponse({'detail':'预览尚未生成'},status_code=404)
        return FileResponse(path,media_type='image/jpeg')

    @app.get('/api/jobs/{identifier}/image/{kind}')
    def full_image(identifier: str,kind: str,request: Request):
        record,error=completed(identifier)
        if error:return error
        if kind not in ('original','result','upload') or (kind=='upload' and record.get('kind')!='reverse'):return JSONResponse({'detail':'图片不存在'},status_code=404)
        corrected=kind=='result' and record.get('outcome') in ('corrected','reversed')
        filename='upload.png' if kind=='upload' else 'result.png' if corrected else 'normalized.png'
        path=request.app.state.manager.root/identifier/filename
        if not path.is_file():return JSONResponse({'detail':'图片尚未生成'},status_code=404)
        return FileResponse(path,media_type='image/png')

    @app.get('/api/jobs/{identifier}/download')
    def download(identifier: str,request: Request,variant:Literal['cropped','uncropped']='cropped'):
        record,error=completed(identifier)
        if error:return error
        manager=request.app.state.manager
        directory=manager.root/identifier
        if record.get('kind')=='reverse':
            if variant!='cropped':raise ReverseError('invalid_variant','反算结果没有额外裁切版本',409)
            name=Path(record.get('filename') or 'image').stem[:80]
            return FileResponse(directory/'result.png',media_type='image/png',filename=f'{name}-reversed.png')
        if variant=='uncropped':
            try:
                with manager.pin(identifier) as (folder,parent):
                    materialize_correction_assets(folder,parent)
                    name=Path(parent.get('filename') or 'image').stem[:80]
                    return FileResponse(folder/'uncropped.png',media_type='image/png',filename=f'{name}-uncropped.png')
            except FileNotFoundError as exc:raise ReverseError('parent_expired','原任务已过期',410) from exc
        corrected=record.get('outcome')=='corrected'
        path=directory/('result.png' if corrected else 'source')
        if not path.is_file():return JSONResponse({'detail':'文件尚未生成'},status_code=404)
        original_name=record.get('filename') or 'image'
        name=Path(original_name).stem[:80]
        media='image/png' if corrected else 'application/octet-stream'
        return FileResponse(path,media_type=media,filename=f'{name}-corrected.png' if corrected else original_name)

    frontend=Path(__file__).resolve().parents[2]/'frontend/dist'
    if frontend.is_dir():app.mount('/',StaticFiles(directory=frontend,html=True),name='frontend')
    return app

app=create_app()
