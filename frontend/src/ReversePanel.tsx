import {useEffect,useRef,useState} from 'react';
import type {ChangeEvent} from 'react';
import {ApiError,getJob,uploadReverse} from './api';
import type {Job,Basis} from './api';
import './reverse.css';

export default function ReversePanel({parent}:{parent:Job}){
  const [file,setFile]=useState<File>();
  const [localUrl,setLocalUrl]=useState('');
  const [job,setJob]=useState<Job>();
  const [stage,setStage]=useState('');
  const [error,setError]=useState('');
  const [ambiguous,setAmbiguous]=useState(false);
  const [choice,setChoice]=useState<''|'cropped'|'uncropped'>('');
  const [zoom,setZoom]=useState(false);
  const [view,setView]=useState<'original'|'result'|'split'>('split');
  const [comparison,setComparison]=useState<'original'|'upload'>('original');
  const input=useRef<HTMLInputElement>(null);
  const controller=useRef<AbortController|null>(null);
  const generation=useRef(0);
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const done=job?.status==='succeeded';
  const busy=['uploading','queued','preparing','reverse_mapping','finishing'].includes(stage);
  useEffect(()=>()=>{generation.current++;controller.current?.abort();if(timer.current)clearTimeout(timer.current);},[]);
  useEffect(()=>()=>{if(localUrl)URL.revokeObjectURL(localUrl);},[localUrl]);
  async function start(next:File,basis:Basis='auto'){
    if(next.size>20*1024*1024){setError('图片超过 20 MiB，请选择较小的图片。');return;}
    if(next.type&&!['image/jpeg','image/png','image/webp'].includes(next.type)){setError('请选择 JPG、PNG 或 WebP 静态图片。');return;}
    const seq=++generation.current;
    controller.current?.abort();if(timer.current)clearTimeout(timer.current);
    const abort=new AbortController();controller.current=abort;
    setFile(next);setLocalUrl(URL.createObjectURL(next));setJob(undefined);setError('');setAmbiguous(false);setStage('uploading');setView('split');setComparison('upload');
    try{
      const accepted=await uploadReverse(parent.id,next,basis,abort.signal);
      if(seq!==generation.current)return;
      setStage('queued');
      async function poll(){
        try{
          const record=await getJob(accepted.id,abort.signal);
          if(seq!==generation.current)return;
          setJob(record);setStage(record.stage);
          if(record.status==='succeeded')return;
          if(record.status==='failed'){setError(record.message);return;}
          timer.current=setTimeout(poll,500);
        }catch(e){if(seq===generation.current&&!abort.signal.aborted){setError(e instanceof Error?e.message:'无法读取反算结果。');setStage('failed');}}
      }
      await poll();
    }catch(e){
      if(seq!==generation.current||abort.signal.aborted)return;
      setStage('failed');setError(e instanceof Error?e.message:'反算上传失败。');
      if(e instanceof ApiError&&e.code==='basis_ambiguous'){setAmbiguous(true);setChoice('');}
    }
  }
  function select(event:ChangeEvent<HTMLInputElement>){const files=event.target.files;if(files?.length===1)void start(files[0]);event.target.value='';}
  const stageNames:Record<string,string>={uploading:'正在上传图片',queued:'等待反算',preparing:'正在准备反算',reverse_mapping:'正在按原始坐标反算',finishing:'正在生成结果'};
  const original=(zoom?job?.original_image_url:job?.original_preview_url)||(zoom?parent.original_image_url:parent.original_preview_url)||'';
  const result=(zoom?job?.result_image_url:job?.result_preview_url)||'';
  const uploaded=(zoom?job?.upload_image_url:job?.upload_preview_url)||localUrl;
  const left=comparison==='upload'?uploaded:original;
  const leftLabel=comparison==='upload'?'上传图片':'原图';
  const leftAlt=comparison==='upload'?'上传图片（反算对比）':'原图（反算对比）';
  function pane(src:string,caption:string,alt=caption){return <figure className={`image-pane ${zoom?'actual':''}`}><figcaption>{caption}</figcaption><div className="image-scroll">{src?<img src={src} alt={alt} draggable={false}/>:<p className="reverse-placeholder">{busy?stageNames[stage]||'正在反算':'上传图片后显示反算结果'}</p>}</div></figure>;}
  return <section className="reverse-panel" aria-label="反向映射">
    <input type="file" ref={input} accept="image/jpeg,image/png,image/webp" onChange={select} className="file-input" aria-label="上传待反算图片"/>
    <div className="reverse-heading"><div><h2>反向映射</h2><p>上传整张图片，按当前任务参数还原到原始坐标。</p></div><button onClick={()=>input.current?.click()} disabled={!parent.can_reverse}>{file?'更换反算图片':'上传待反算图片'}</button></div>
    {!parent.can_reverse?<p className="reverse-unavailable">校正记录不完整，请重新处理原图后再反算。</p>:<div className="workspace-layout">
      <section className="workspace" aria-label={`${leftLabel}与反算结果对比`}>
        <div className="reverse-comparison-source" role="group" aria-label="反算对比对象"><span>对比来源</span><button aria-pressed={comparison==='original'} onClick={()=>{setComparison('original');setView('split');}}>原图对比</button><button disabled={!file} aria-pressed={comparison==='upload'} onClick={()=>{setComparison('upload');setView('split');}}>上传图片对比</button></div>
        <div className="workspace-toolbar"><div className="tabs" aria-label="反算对比方式">{(['original','result','split'] as const).map((mode,i)=><button key={mode} aria-pressed={view===mode} disabled={mode!=='original'&&!done} onClick={()=>setView(mode)}>{[leftLabel,'反算结果','并排对比'][i]}</button>)}</div><button className="zoom" onClick={()=>setZoom(!zoom)} aria-pressed={zoom}>{zoom?'适应窗口':'100% 查看'}</button></div>
        <div className={`image-area ${view==='split'?'split':''}`}>
          {view==='split'?<>{pane(left,leftLabel,leftAlt)}{pane(done?result:'','反算结果')}</>:pane(view==='original'?left:done?result:'',view==='original'?leftLabel:'反算结果',view==='original'?leftAlt:'反算结果')}
        </div>
        <div className="workspace-footer"><span className="filename" title={file?.name}>{file?.name||'等待上传整张图片'}</span><span>{done?'原图坐标 · 完整尺寸':'不需要识别涂鸦'}</span></div>
      </section>
      <aside className="details reverse-details" aria-label="反算信息">
        <div className="section-heading"><h2>整图反算</h2><span className="outcome">{done?'反算完成':busy?'处理中':'等待上传'}</span></div>
        <p className="reverse-message" role="status" aria-live="polite">{done?job.message:busy?stageNames[stage]||'正在处理':'支持修改后的矫正图、未修改的图或其他正常图片。整张图都会参与反算。'}</p>
        {error&&<div role="alert" className="error reverse-error">{error}</div>}
        {busy&&<div className="processing-indicator" aria-hidden="true"><span/></div>}
        {file&&localUrl&&<figure className="reverse-upload-preview"><img src={job?.upload_preview_url||localUrl} alt="待反算上传图"/><figcaption>{file.name}</figcaption></figure>}
        <p className="reverse-sizes">裁切：{parent.output_width} × {parent.output_height}<br/>未裁切：{parent.uncropped_width} × {parent.uncropped_height}</p>
        {ambiguous&&<fieldset className="basis-choice"><legend>选择参考版本</legend><label><input type="radio" name={`basis-${parent.id}`} checked={choice==='cropped'} onChange={()=>setChoice('cropped')}/>基于裁切图</label><label><input type="radio" name={`basis-${parent.id}`} checked={choice==='uncropped'} onChange={()=>setChoice('uncropped')}/>基于未裁切图</label><button disabled={!choice||!file} onClick={()=>{if(file&&choice)void start(file,choice);}}>按所选版本反算</button></fieldset>}
        {job?.reference_basis&&<p className="resolved-basis">参考版本：{job.reference_basis==='cropped'?'裁切版':'未裁切版'}</p>}
        {done&&<dl className="image-meta"><div><dt>输出尺寸</dt><dd>{job.output_width} × {job.output_height}</dd></div><div><dt>处理耗时</dt><dd>{typeof job.elapsed_seconds==='number'?`${job.elapsed_seconds.toFixed(1)} 秒`:'—'}</dd></div></dl>}
        {done&&job.download_url?<a className="download primary" href={job.download_url}>下载反算结果</a>:<button className="download" disabled>反算完成后可下载</button>}
        <p className="reverse-note">保留正常透视。未覆盖部分及边缘少量像素保留原图，避免黑边混入；裁切缺失区域不补画。</p>
      </aside>
    </div>}
  </section>;
}
