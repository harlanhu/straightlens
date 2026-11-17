import threading
import time
from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient
from app.main import create_app
from app.jobs import JobManager
from test_jobs_api import fake_pipeline,image_bytes


def test_one_running_two_queued_and_busy_response(tmp_path):
    entered=threading.Event();release=threading.Event()
    def blocked(source,directory,stage):
        entered.set()
        assert release.wait(timeout=5)
        return fake_pipeline(source,directory,stage)
    with TestClient(create_app(tmp_path,processor=blocked)) as client:
        try:
            assert client.post('/api/jobs',files={'image':('a.png',image_bytes(),'image/png')}).status_code==202
            assert entered.wait(timeout=2)
            for _ in range(2):
                assert client.post('/api/jobs',files={'image':('a.png',image_bytes(),'image/png')}).status_code==202
            assert client.post('/api/jobs',files={'image':('a.png',image_bytes(),'image/png')}).status_code==429
        finally:release.set()


def test_file_size_limit(tmp_path,monkeypatch):
    import app.main as module
    monkeypatch.setattr(module,'MAX_BYTES',8)
    with TestClient(create_app(tmp_path,processor=fake_pipeline)) as client:
        response=client.post('/api/jobs',files={'image':('a.png',image_bytes(),'image/png')})
        assert response.status_code==413
        assert list(tmp_path.iterdir())==[]


def test_unsupported_content_415(tmp_path):
    buffer=BytesIO();Image.new('RGB',(20,20)).save(buffer,'TIFF')
    with TestClient(create_app(tmp_path,processor=fake_pipeline)) as client:
        assert client.post('/api/jobs',files={'image':('pretend.png',buffer.getvalue(),'image/png')}).status_code==415


def test_expired_result_removed_but_active_kept(tmp_path):
    manager=JobManager(tmp_path,processor=fake_pipeline)
    done='b'*32;active='c'*32
    for key,status in ((done,'succeeded'),(active,'running')):
        (tmp_path/key).mkdir()
        manager.records[key]={'id':key,'status':status,'created_at':0}
    manager.cleanup(now=90000)
    assert not (tmp_path/done).exists()
    assert done in manager.expired
    assert (tmp_path/active).exists()


def test_restart_marks_interrupted_task_failed(tmp_path):
    import json
    key='d'*32;directory=tmp_path/key;directory.mkdir()
    (directory/'job.json').write_text(json.dumps({'id':key,'status':'running','created_at':time.time()}))
    manager=JobManager(tmp_path,processor=fake_pipeline)
    assert manager.get(key)['reason_code']=='interrupted'
