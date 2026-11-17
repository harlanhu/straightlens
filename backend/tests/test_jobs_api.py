from io import BytesIO
import time
from PIL import Image
from fastapi.testclient import TestClient
from app.main import create_app


def image_bytes():
    f=BytesIO();Image.new('RGB',(80,60),'white').save(f,'PNG');return f.getvalue()


def fake_pipeline(source,work_dir,stage):
    from app.images import normalize_image,make_preview
    info=normalize_image(source,work_dir);stage('checking')
    make_preview(info.normalized_path,work_dir/'result.jpg')
    return {'outcome':'unchanged','reason_code':'insufficient_evidence','message':'已保留原图。','width':80,'height':60,'output_width':80,'output_height':60,'elapsed_seconds':.01}


def test_upload_poll_download(tmp_path):
    with TestClient(create_app(tmp_path,processor=fake_pipeline)) as client:
        result=client.post('/api/jobs',files={'image':('图片.png',image_bytes(),'image/png')})
        assert result.status_code==202
        job=result.json()['id']
        for _ in range(100):
            response=client.get('/api/jobs/'+job)
            if response.json()['status'] in ('succeeded','failed'):break
            time.sleep(.01)
        data=response.json()
        assert data['status']=='succeeded'
        assert data['outcome']=='unchanged'
        assert client.get(data['download_url']).content==image_bytes()
        assert client.get(data['original_preview_url']).status_code==200
        assert client.get(data['result_preview_url']).status_code==200
        original_full=client.get(data['original_image_url'])
        assert original_full.status_code==200
        assert Image.open(BytesIO(original_full.content)).size==(80,60)
        assert client.get(data['result_image_url']).status_code==200


def test_corrupt_and_unknown(tmp_path):
    with TestClient(create_app(tmp_path,processor=fake_pipeline)) as client:
        assert client.post('/api/jobs',files={'image':('x.png',b'bad','image/png')}).status_code==422
        assert client.get('/api/jobs/not-a-job').status_code==404
        assert client.get('/api/jobs/abc/download').status_code==404


def test_worker_recovers_after_failure(tmp_path):
    count=0
    def processor(*args):
        nonlocal count
        count+=1
        if count==1:raise RuntimeError('internal path should not leak')
        return fake_pipeline(*args)
    with TestClient(create_app(tmp_path,processor=processor)) as client:
        ids=[]
        for _ in range(2):
            ids.append(client.post('/api/jobs',files={'image':('x.png',image_bytes(),'image/png')}).json()['id'])
        for _ in range(100):
            second=client.get('/api/jobs/'+ids[1]).json()
            if second['status']=='succeeded':break
            time.sleep(.01)
        first=client.get('/api/jobs/'+ids[0]).json()
        assert first['status']=='failed'
        assert 'internal path' not in first['message']
        assert second['status']=='succeeded'


def test_cleanup_skips_active(tmp_path):
    from app.jobs import JobManager
    manager=JobManager(tmp_path,processor=fake_pipeline)
    directory=tmp_path/('a'*32)
    directory.mkdir()
    manager.records['a'*32]={'id':'a'*32,'status':'running','created_at':0}
    manager.cleanup(now=100000)
    assert directory.exists()
