import {useEffect, useRef, useState} from 'react';
import type {ChangeEvent, DragEvent} from 'react';
import {getJob, uploadImage} from './api';
import type {Job} from './api';
import ReversePanel from './ReversePanel';

type View = 'original'|'result'|'split';
const phases=[{key:'preparing',label:'准备图片'},{key:'estimating',label:'估计镜头畸变'},{key:'checking',label:'检查校正效果'},{key:'rendering',label:'生成完整图片'}];
const stageLabel: Record<string,string>={uploading:'正在上传图片',queued:'等待处理',preparing:'正在准备图片',estimating:'正在估计镜头畸变',checking:'正在检查校正效果',rendering:'正在生成完整图片',finishing:'正在完成导出',complete:'处理完成',failed:'处理失败'};
function Arrow({down=false}:{down?:boolean}) {return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d={down?'M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4':'M12 20V4m-6 6 6-6 6 6'} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>}

export default function App(){
  const [file,setFile]=useState<File>();
  const [localUrl,setLocalUrl]=useState('');
  const [job,setJob]=useState<Job>();
  const [stage,setStage]=useState('');
  const [error,setError]=useState('');
  const [view,setView]=useState<View>('original');
  const [zoom,setZoom]=useState(false);
  const [drag,setDrag]=useState(false);
  const [serviceReady,setServiceReady]=useState<boolean|null>(null);
  const input=useRef<HTMLInputElement>(null);
  const controller=useRef<AbortController|null>(null);
  const generation=useRef(0);
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const busy=['uploading','queued','preparing','estimating','checking','rendering','finishing'].includes(stage);
  const complete=job?.status==='succeeded';
  useEffect(()=>{
    fetch('/api/health').then(r=>r.json()).then(data=>setServiceReady(data.algorithm_ready)).catch(()=>setServiceReady(false));
    return ()=>{controller.current?.abort();if(timer.current)clearTimeout(timer.current);};
  },[]);
  useEffect(()=>()=>{if(localUrl)URL.revokeObjectURL(localUrl);},[localUrl]);
  async function begin(next:File){
    if(next.size>20*1024*1024){setError('图片超过 20 MiB，请选择较小的图片。');return;}
    if(!['image/jpeg','image/png','image/webp'].includes(next.type)) {setError('请选择 JPG、PNG 或 WebP 静态图片。');return;}
    const seq=++generation.current;
    controller.current?.abort();if(timer.current)clearTimeout(timer.current);
    const abort=new AbortController();controller.current=abort;
    setFile(next);setLocalUrl(URL.createObjectURL(next));setJob(undefined);setError('');setView('original');setZoom(false);setStage('uploading');
    try{
      const accepted=await uploadImage(next,abort.signal);
      if(seq!==generation.current)return;
      setStage('queued');
      async function poll(){
        try{
          const record=await getJob(accepted.id,abort.signal);
          if(seq!==generation.current)return;
          setJob(record);setStage(record.stage);
          if(record.status==='succeeded'){setView('split');return;}
          if(record.status==='failed'){setError(record.message);return;}
          timer.current=setTimeout(poll,700);
        }catch(e){if(seq===generation.current&&!abort.signal.aborted){setError(e instanceof Error?e.message:'无法读取处理状态，请重新上传。');setStage('failed');}}
      }
      await poll();
    }catch(e){if(seq===generation.current&&!abort.signal.aborted){setError(e instanceof Error?e.message:'上传失败，请重新尝试。');setStage('failed');}}
  }
  function selection(event:ChangeEvent<HTMLInputElement>){
    const files=event.target.files;
    if(files?.length===1)void begin(files[0]);
    else if(files&&files.length>1)setError('每次请选择一张图片。');
    event.target.value='';
  }
  function drop(event:DragEvent){
    event.preventDefault();setDrag(false);
    if(event.dataTransfer.files.length!==1){setError('每次请拖入一张图片。');return;}
    void begin(event.dataTransfer.files[0]);
  }
  const original=(zoom?job?.original_image_url:job?.original_preview_url)||localUrl;
  const result=(zoom?job?.result_image_url:job?.result_preview_url)||original;
  const outcome=job?.outcome==='corrected'?'已校正':job?.outcome==='unchanged'?'已保留原图':error?'未完成':busy?'处理中':'等待图片';
  const phaseIndex=stage==='finishing'||stage==='complete'?4:phases.findIndex(p=>p.key===stage);
  function pane(src:string,label:string){return <figure className={`image-pane ${zoom?'actual':''}`}><figcaption>{label}</figcaption><div className="image-scroll"><img src={src} alt={label} draggable={false}/></div></figure>}
  return <div className={`app-shell ${complete&&job?.outcome==='corrected'?'has-correction':''}`}>
    <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" onChange={selection} className="file-input" aria-label="选择待校正图片"/>
    <header className="app-header"><a className="brand" href="/" aria-label="StraightLens 首页"><svg width="30" height="26" viewBox="0 0 30 26" fill="none" aria-hidden="true"><path d="M3 4Q12 13 3 22M15 4v18M27 4v18" stroke="currentColor" strokeWidth="2"/><path d="m20 11 3 2-3 2" stroke="currentColor" strokeWidth="1.5"/></svg><span>StraightLens</span></a><span className="header-scope">镜头校正工作台</span><span className="local-note"><span className="status-dot"/>仅在本机处理</span></header>
    <main>
      <div className="page-heading"><div><h1>镜头校正</h1><p>导入一张图片，自动还原画面中的直线。</p></div><button className="primary" onClick={()=>input.current?.click()} disabled={serviceReady===false}><Arrow/>{file?'更换图片':'导入图片'}</button></div>
      {serviceReady===false&&<div role="alert" className="error">校正服务暂不可用，请检查后台和算法是否已启动。</div>}
      {error&&<div role="alert" className="error">{error}<button onClick={()=>input.current?.click()}>重新选择</button></div>}
      <div className="workspace-layout">
        <section className={`workspace ${drag?'dragging':''}`} aria-label="图像工作区" onDragOver={e=>{e.preventDefault();setDrag(true);}} onDragLeave={e=>{if(!e.currentTarget.contains(e.relatedTarget as Node))setDrag(false);}} onDrop={drop}>
          <div className="workspace-toolbar"><div className="tabs" aria-label="对比方式">{(['original','result','split'] as View[]).map((value,i)=><button key={value} aria-pressed={view===value} disabled={!file||(value!=='original'&&!complete)} onClick={()=>setView(value)}>{['原图','结果','并排对比'][i]}</button>)}</div><button className="zoom" aria-pressed={zoom} onClick={()=>setZoom(!zoom)} disabled={!file}>{zoom?'适应窗口':'100% 查看'}</button></div>
          {!file?<div className="empty-canvas"><div className="empty-mark" aria-hidden="true"><svg width="112" height="72" viewBox="0 0 112 72" fill="none"><path d="M16 12Q48 36 16 60" stroke="#949494" strokeWidth="1.5"/><path d="M85 12v48" stroke="#e8e8e8" strokeWidth="1.5"/><path d="M45 36h20m-5-5 5 5-5 5" stroke="#949494" strokeWidth="1.5"/></svg></div><h2>把图片拖到这里</h2><p>或使用上方「导入图片」开始</p><span className="format-hint">JPG、PNG、WebP · 最大 20 MiB / 2000 万像素</span></div>:<div className={`image-area ${view==='split'?'split':''}`}>{view==='split'?<>{pane(original,'原图')}{pane(result,job?.outcome==='corrected'?'校正结果':'原图 · 未应用校正')}</>:pane(view==='original'?original:result,view==='original'?'原图':'处理结果')}</div>}
          <div className="workspace-footer"><span className="filename" title={file?.name}>{file?.name||'尚未导入图片'}</span><span>{file?`${(file.size/1024/1024).toFixed(2)} MiB`:'图片不会发送至第三方'}</span></div>
        </section>
        <aside className="details" aria-label="处理信息">
          <section className="result-summary"><div className="section-heading"><h2>处理结果</h2><span className={`outcome ${job?.outcome==='corrected'?'success':''}`}>{outcome}</span></div><p className="result-message" role="status" aria-live="polite">{error?'请重新尝试或选择另一张图片。':complete?job.message:busy?stageLabel[stage]||'正在处理':'系统会自动估计畸变，无需选线或调整参数。'}</p>
            {busy&&<div className="processing-indicator" aria-hidden="true"><span/></div>}
            <dl className="image-meta"><div><dt>输入尺寸</dt><dd>{job?.width?`${job.width} × ${job.height}`:'—'}</dd></div><div><dt>输出尺寸</dt><dd>{job?.output_width?`${job.output_width} × ${job.output_height}`:'—'}</dd></div><div><dt>处理耗时</dt><dd>{typeof job?.elapsed_seconds==='number'?`${job.elapsed_seconds.toFixed(1)} 秒`:'—'}</dd></div></dl>
            {complete&&job.download_url?<div className="correction-downloads"><a className="download primary" href={job.download_url}><Arrow down/>{job.outcome==='corrected'?'下载矫正图·裁切':'下载原图'}</a>{job.outcome==='corrected'&&job.uncropped_download_url&&<a className="download secondary" href={job.uncropped_download_url}>下载矫正图·未裁切</a>}{job.outcome==='corrected'&&<p className="download-note">页面展示裁切版。未裁切版保留自动裁边前的完整画布，可能带黑边。</p>}</div>:<button className="download" disabled>处理完成后可下载</button>}
          </section>
          <details className="flow" open={!complete}><summary>自动处理流程</summary><ol>{phases.map((phase,i)=><li key={phase.key} className={`${(complete?job.stages?.includes(phase.key):phaseIndex>i)?'done':''} ${busy&&phaseIndex===i?'current':''}`}><span className="phase-dot"/>{phase.label}<span className="phase-state">{(complete?job.stages?.includes(phase.key):phaseIndex>i)?'完成':complete?'跳过':busy&&phaseIndex===i?'进行中':''}</span></li>)}</ol></details>
          <details className="note" open={!complete}><summary>只在有依据时校正</summary><p>直线结构不足，或未发现可靠改善时，自动保留原图。镜头校正会保留正常拍摄透视。</p></details>
        </aside>
      </div>
      {complete&&job.outcome==='corrected'&&<ReversePanel key={job.id} parent={job}/>}
      {complete&&job.outcome!=='corrected'&&<p className="reverse-unavailable">本次未应用校正，没有可复用的校正模型，因此不提供反向映射。可以重新导入一张有足够直线结构的图片。</p>}
      <footer className="page-footer"><span>StraightLens · 单图自动校正</span><span>本地处理 · 临时文件保留 24 小时</span></footer>
    </main>
  </div>;
}
