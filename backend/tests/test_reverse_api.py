from io import BytesIO
from pathlib import Path
import json
import time
import threading
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import create_app


def png(size=(80,60),color='white'):
    buffer=BytesIO();Image.new('RGB',size,color).save(buffer,'PNG');return buffer.getvalue()


def parent_processor(source,directory,stage):
    from app.images import normalize_image,make_preview
    from app.engine.ipol import CandidateConfig,CandidateResult
    from app.engine.remap import render_full_resolution
    from app.engine.transforms import TransformSpec
    info=normalize_image(source,directory)
    c=CandidateResult(CandidateConfig('pol',.8),(1.,0.,0.),(40.,30.),(80,60),[],directory)
    result=render_full_resolution(info,c,directory/'result.png',crop_override=(5,3,75,57))
    TransformSpec.from_candidate(c,(80,60),result.crop).save(directory/'transform.json')
    make_preview(directory/'result.png',directory/'result.jpg')
    return {'outcome':'corrected','reason_code':'geometry_improved','message':'已校正','width':80,'height':60,'output_width':70,'output_height':54}


def wait_job(client,identifier):
    for _ in range(200):
        value=client.get('/api/jobs/'+identifier).json()
        if value['status'] in ('succeeded','failed'):return value
        time.sleep(.01)
    raise AssertionError('job did not finish')


def create_parent(client):
    response=client.post('/api/jobs',files={'image':('source.png',png(),'image/png')})
    assert response.status_code==202
    parent=wait_job(client,response.json()['id'])
    assert parent['status']=='succeeded'
    return parent


def test_dual_download_and_reverse_whole_image(tmp_path):
    with TestClient(create_app(tmp_path,processor=parent_processor)) as client:
        parent=create_parent(client);identifier=parent['id']
        assert parent['can_reverse']
        cropped=client.get(parent['download_url']);full=client.get(parent['uncropped_download_url'])
        assert Image.open(BytesIO(cropped.content)).size==(70,54)
        assert Image.open(BytesIO(full.content)).size==(80,60)
        response=client.post(f'/api/jobs/{identifier}/reverse',data={'basis':'auto'},files={'image':('paint.png',png((70,54),'red'),'image/png')})
        assert response.status_code==202
        child=wait_job(client,response.json()['id'])
        assert child['status']=='succeeded',child
        assert child['kind']=='reverse' and child['parent_id']==identifier
        assert child['reference_basis']=='cropped'
        assert child['outcome']=='reversed'
        uploaded=client.get(child['upload_image_url'])
        assert uploaded.status_code==200
        with Image.open(BytesIO(uploaded.content)) as image:
            assert image.size==(70,54)
            assert image.convert('RGB').getpixel((0,0))==(255,0,0)
        result=np.array(Image.open(BytesIO(client.get(child['download_url']).content)))
        assert result[20,20].tolist()==[255,0,0]
        assert result[0,0].tolist()==[255,255,255]
        assert client.get(parent['download_url']).content==cropped.content


def test_reverse_same_image_and_unrelated_full_image(tmp_path):
    with TestClient(create_app(tmp_path,processor=parent_processor)) as client:
        parent=create_parent(client);url=f"/api/jobs/{parent['id']}/reverse"
        image=client.get(parent['uncropped_download_url']).content
        first=client.post(url,data={'basis':'uncropped'},files={'image':('same.png',image,'image/png')})
        second=client.post(url,data={'basis':'uncropped'},files={'image':('other.png',png(color='blue'),'image/png')})
        assert first.status_code==second.status_code==202
        a=wait_job(client,first.json()['id']);b=wait_job(client,second.json()['id'])
        assert a['id']!=b['id']
        assert a['status']==b['status']=='succeeded'
        arr=np.array(Image.open(BytesIO(client.get(b['download_url']).content)))
        assert arr[20,20].tolist()==[0,0,255]


def test_reverse_validation_errors(tmp_path):
    with TestClient(create_app(tmp_path,processor=parent_processor)) as client:
        parent=create_parent(client);url=f"/api/jobs/{parent['id']}/reverse"
        response=client.post(url,files={'image':('square.png',png((100,100)),'image/png')})
        assert response.status_code==422 and response.json()['code']=='aspect_ratio_mismatch'
        response=client.post(url,files={'image':('broken.png',b'broken','image/png')})
        assert response.status_code==422 and response.json()['code']=='invalid_image'
        assert client.post('/api/jobs/'+'0'*32+'/reverse',files={'image':('a.png',png(),'image/png')}).status_code==404
        assert client.post('/api/jobs/not-a-valid-id/reverse',files={'image':('a.png',png(),'image/png')}).status_code==404


def square_processor(source,directory,stage):
    from app.images import normalize_image,make_preview
    from app.engine.ipol import CandidateConfig,CandidateResult
    from app.engine.remap import render_full_resolution
    from app.engine.transforms import TransformSpec
    info=normalize_image(source,directory)
    c=CandidateResult(CandidateConfig('pol',.8),(1.,0.,0.),(50.,50.),(100,100),[],directory)
    result=render_full_resolution(info,c,directory/'result.png',crop_override=(10,10,90,90))
    TransformSpec.from_candidate(c,(100,100),result.crop).save(directory/'transform.json')
    make_preview(directory/'result.png',directory/'result.jpg')
    return {'outcome':'corrected','reason_code':'geometry_improved','message':'已校正','width':100,'height':100,'output_width':80,'output_height':80}


def test_ambiguous_reference_produces_no_child(tmp_path):
    with TestClient(create_app(tmp_path,processor=square_processor)) as client:
        created=client.post('/api/jobs',files={'image':('square.png',png((100,100)),'image/png')})
        parent=wait_job(client,created.json()['id'])
        assert parent['status']=='succeeded'
        before=sorted(p.name for p in tmp_path.iterdir())
        response=client.post(f"/api/jobs/{parent['id']}/reverse",files={'image':('scaled.png',png((40,40)),'image/png')})
        assert response.status_code==422
        assert response.json()['code']=='basis_ambiguous'
        assert sorted(p.name for p in tmp_path.iterdir())==before


def test_reverse_child_restart_is_recovered_as_failed(tmp_path):
    import json as jsonlib
    from app.jobs import JobManager
    key='c'*32;directory=tmp_path/key;directory.mkdir()
    (directory/'job.json').write_text(jsonlib.dumps({'id':key,'kind':'reverse','parent_id':'a'*32,'status':'running','created_at':time.time()}))
    manager=JobManager(tmp_path,processor=parent_processor)
    record=manager.get(key)
    assert record['status']=='failed' and record['kind']=='reverse'


def test_legacy_backfill_preserves_crop_and_does_not_reestimate(tmp_path,monkeypatch):
    import app.engine.pipeline as pipeline
    def forbidden(*args,**kwargs):raise AssertionError('must reuse saved geometry')
    with TestClient(create_app(tmp_path,processor=parent_processor)) as client:
        parent=create_parent(client);directory=tmp_path/parent['id']
        before=client.get(parent['download_url']).content
        data=json.loads((directory/'transform.json').read_text())
        (directory/'model.json').write_text(json.dumps({key:data[key] for key in ('model','coefficients','center','estimation_size','crop')}))
        for name in ('transform.json','uncropped.png','valid-mask.png'):(directory/name).unlink()
        monkeypatch.setattr(pipeline,'run_ipol',forbidden)
        response=client.get(f"/api/jobs/{parent['id']}/download?variant=uncropped")
        assert response.status_code==200
        assert Image.open(BytesIO(response.content)).size==(80,60)
        assert client.get(parent['download_url']).content==before
        assert (directory/'transform.json').exists()


def test_old_uncropped_rgba_padding_is_opaque_on_download(tmp_path):
    with TestClient(create_app(tmp_path,processor=parent_processor)) as client:
        parent=create_parent(client);directory=tmp_path/parent['id']
        with Image.open(directory/'uncropped.png') as image:old=image.convert('RGBA')
        alpha=Image.new('L',old.size,255)
        for x in range(old.width):alpha.putpixel((x,0),0)
        old.putalpha(alpha);old.save(directory/'uncropped.png')
        before=client.get(parent['download_url']).content
        downloaded=client.get(parent['uncropped_download_url'])
        with Image.open(BytesIO(downloaded.content)) as image:
            assert np.min(np.array(image.convert('RGBA'))[...,3])==255
        assert client.get(parent['download_url']).content==before


def test_unchanged_parent_has_no_reverse_model(tmp_path):
    from test_jobs_api import fake_pipeline
    with TestClient(create_app(tmp_path,processor=fake_pipeline)) as client:
        created=client.post('/api/jobs',files={'image':('original.png',png(),'image/png')})
        parent=wait_job(client,created.json()['id'])
        response=client.post(f"/api/jobs/{parent['id']}/reverse",files={'image':('a.png',png(),'image/png')})
        assert response.status_code==409 and response.json()['code']=='model_unavailable'
        assert len(list(tmp_path.iterdir()))==1


def test_reverse_byte_limit_and_invalid_transform(tmp_path,monkeypatch):
    import app.reverse_api as module
    with TestClient(create_app(tmp_path,processor=parent_processor)) as client:
        parent=create_parent(client);url=f"/api/jobs/{parent['id']}/reverse"
        monkeypatch.setattr(module,'MAX_BYTES',8)
        response=client.post(url,files={'image':('a.png',png(),'image/png')})
        assert response.status_code==413 and response.json()['code']=='upload_too_large'
        monkeypatch.setattr(module,'MAX_BYTES',20*1024*1024)
        path=tmp_path/parent['id']/'transform.json';data=json.loads(path.read_text());data['version']=99;path.write_text(json.dumps(data))
        response=client.post(url,files={'image':('a.png',png(),'image/png')})
        assert response.status_code==409 and response.json()['code']=='model_unavailable'


def test_reverse_queue_uses_same_capacity(tmp_path,monkeypatch):
    import app.jobs as module
    from app.engine.reverse import process_reverse_job
    entered=threading.Event();release=threading.Event()
    def blocked(*args,**kwargs):
        entered.set();assert release.wait(3)
        return process_reverse_job(*args,**kwargs)
    monkeypatch.setattr(module,'process_reverse_job',blocked)
    with TestClient(create_app(tmp_path,processor=parent_processor)) as client:
        parent=create_parent(client);url=f"/api/jobs/{parent['id']}/reverse"
        try:
            assert client.post(url,files={'image':('a.png',png(),'image/png')}).status_code==202
            assert entered.wait(1)
            for _ in range(2):assert client.post(url,files={'image':('a.png',png(),'image/png')}).status_code==202
            assert client.post(url,files={'image':('a.png',png(),'image/png')}).status_code==429
        finally:release.set()


def test_parent_pin_blocks_cleanup_during_snapshot(tmp_path):
    app=create_app(tmp_path,processor=parent_processor)
    with TestClient(app) as client:
        parent=create_parent(client);manager=app.state.manager
        manager.records[parent['id']]['created_at']=0
        with manager.pin(parent['id']):
            manager.cleanup();assert (tmp_path/parent['id']).exists()
        manager.cleanup();assert not (tmp_path/parent['id']).exists()


def test_parent_expiry_does_not_break_admitted_reverse(tmp_path,monkeypatch):
    import app.jobs as module
    from app.engine.reverse import process_reverse_job
    entered=threading.Event();release=threading.Event()
    def blocked(*args,**kwargs):
        entered.set();assert release.wait(3)
        return process_reverse_job(*args,**kwargs)
    monkeypatch.setattr(module,'process_reverse_job',blocked)
    app=create_app(tmp_path,processor=parent_processor)
    with TestClient(app) as client:
        parent=create_parent(client)
        response=client.post(f"/api/jobs/{parent['id']}/reverse",files={'image':('a.png',png((70,54),'red'),'image/png')})
        assert response.status_code==202
        try:
            assert entered.wait(1)
            app.state.manager.records[parent['id']]['created_at']=0
            app.state.manager.cleanup()
            assert not (tmp_path/parent['id']).exists()
        finally:release.set()
        child=wait_job(client,response.json()['id'])
        assert child['status']=='succeeded',child
        assert client.get(child['download_url']).status_code==200
