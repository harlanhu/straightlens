from pathlib import Path
import json
import logging
import queue
import re
import shutil
import threading
import time
import uuid
from copy import deepcopy
from contextlib import contextmanager
from .engine.reverse import process_reverse_job
from .engine.pipeline import process_image
from .engine.ipol import EngineError

LOG=logging.getLogger(__name__)
JOB_ID=re.compile(r'^[a-f0-9]{32}$')

class BusyError(RuntimeError):pass

class JobManager:
    def __init__(self,root:Path,processor=process_image):
        self.root=root.resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.processor=processor
        self.records={};self.expired=set();self.lock=threading.RLock()
        self.pins={};self.artifact_locks={}
        self.queue=queue.Queue(maxsize=2)
        self.stop_event=threading.Event();self.worker=None
        self._recover()

    def _recover(self):
        for directory in self.root.iterdir():
            if not directory.is_dir() or not JOB_ID.fullmatch(directory.name):continue
            try:
                data=json.loads((directory/'job.json').read_text())
                if data.get('id')!=directory.name:continue
                if data.get('status') in ('queued','running'):
                    data.update(status='failed',stage='failed',outcome='failed',reason_code='interrupted',message='服务重启中断了处理，请重新上传。')
                self.records[directory.name]=data
            except (OSError,ValueError):
                # An interrupted upload has no job.json; cleanup only once old.
                continue
        self.cleanup()

    def start(self):
        self.worker=threading.Thread(target=self._run,name='straightlens-worker',daemon=True)
        self.worker.start()

    def close(self):
        self.stop_event.set()
        if self.worker:self.worker.join(timeout=2)

    def allocate(self):
        identifier=uuid.uuid4().hex
        path=self.root/identifier;path.mkdir()
        return identifier,path

    def discard(self,directory):
        resolved=directory.resolve()
        if resolved.parent!=self.root or not JOB_ID.fullmatch(resolved.name):
            raise ValueError('invalid task path')
        if resolved.exists():shutil.rmtree(resolved)

    def _save(self,identifier):
        path=self.root/identifier/'job.json'
        temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.records[identifier],ensure_ascii=False,indent=2))
        temp.replace(path)

    @contextmanager
    def pin(self,identifier):
        with self.lock:
            if not JOB_ID.fullmatch(identifier) or identifier not in self.records:raise FileNotFoundError(identifier)
            self.pins[identifier]=self.pins.get(identifier,0)+1
            record=deepcopy(self.records[identifier])
            asset_lock=self.artifact_locks.setdefault(identifier,threading.Lock())
        try:
            with asset_lock:yield self.root/identifier,record
        finally:
            with self.lock:
                self.pins[identifier]-=1
                if self.pins[identifier]==0:del self.pins[identifier]

    def submit(self,identifier,filename,info,*,kind='correction',parent_id=None,reference_basis=None):
        with self.lock:
            # Queue admission and record insertion are atomic relative to worker state.
            if self.queue.full():raise BusyError()
            data={'id':identifier,'filename':Path(filename.replace('\\','/')).name[:120],
                  'created_at':time.time(),'status':'queued','stage':'queued','stages':['queued'],'outcome':None,
                  'message':'等待处理','width':info.width,'height':info.height,
                  'kind':kind,'parent_id':parent_id,'reference_basis':reference_basis}
            self.records[identifier]=data;self._save(identifier)
            self.queue.put_nowait(identifier)
        return identifier

    def get(self,identifier):
        with self.lock:
            value=self.records.get(identifier)
            return deepcopy(value) if value else None

    def update(self,identifier,**changes):
        with self.lock:
            record=self.records[identifier]
            if 'stage' in changes:
                stages=record.setdefault('stages',[])
                if changes['stage'] not in stages:stages.append(changes['stage'])
            record.update(changes);self._save(identifier)

    def _run(self):
        while not self.stop_event.is_set():
            try:identifier=self.queue.get(timeout=1)
            except queue.Empty:
                self.cleanup();continue
            try:
                self.update(identifier,status='running',stage='preparing',message='正在准备图片')
                directory=self.root/identifier
                callback=lambda stage:self.update(identifier,stage=stage)
                if self.records[identifier].get('kind')=='reverse':
                    result=process_reverse_job(directory,callback,cancel_event=self.stop_event)
                elif self.processor is process_image:
                    result=self.processor(directory/'source',directory,callback,cancel_event=self.stop_event)
                else:
                    result=self.processor(directory/'source',directory,callback)
                self.update(identifier,**result,status='succeeded',stage='complete')
            except Exception as exc:
                LOG.exception('Job %s failed',identifier)
                message=str(exc) if isinstance(exc,EngineError) else '处理失败，请重新上传或尝试另一张图片。'
                self.update(identifier,status='failed',stage='failed',outcome='failed',reason_code='processing_failed',message=message)
            finally:
                self.queue.task_done()
                self.cleanup()

    def cleanup(self,now=None):
        now=time.time() if now is None else now
        with self.lock:
            for identifier,data in list(self.records.items()):
                if data.get('status') in ('queued','running') or self.pins.get(identifier,0):continue
                if now-data['created_at']>86400:
                    self.discard(self.root/identifier)
                    del self.records[identifier];self.expired.add(identifier)
                    self.artifact_locks.pop(identifier,None)
            if len(self.expired)>1000:self.expired=set(list(self.expired)[-1000:])
            for directory in self.root.iterdir():
                if directory.is_dir() and JOB_ID.fullmatch(directory.name) and directory.name not in self.records:
                    if now-directory.stat().st_mtime>86400:self.discard(directory)
