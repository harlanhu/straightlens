import {useState} from 'react';
import type {DistortionReport as Report} from './api';
import DistortionGrid from './DistortionGrid';

export default function DistortionReport({report}:{report?:Report}) {
  const [details,setDetails]=useState(false);
  const [grid,setGrid]=useState(false);
  if(!report?.available) return <section className="distortion-report muted-report"><div className="report-heading"><h2>镜头畸变报告</h2><span>无可用模型</span></div><p>{report?.reason_label||'本次没有足够可靠的直线结构，未生成可展示的畸变模型。'}</p></section>;
  const center=report.center!; const model=report.model!; const crop=report.crop!;
  return <section className="distortion-report"><div className="report-heading"><div><h2>镜头畸变报告</h2><p>根据当前图片估计</p></div><span className="report-profile">{report.profile_label}</span></div>
    <div className="report-strength"><strong>{report.strength_label}</strong><span>校正强度</span></div>
    <dl className="report-meta"><div><dt>估计畸变中心</dt><dd>{center.x_percent.toFixed(1)}% × {center.y_percent.toFixed(1)}%</dd></div><div><dt>边缘最大修正</dt><dd>{report.edge_correction_percent?.toFixed(1)}%</dd></div><div><dt>画面保留</dt><dd>{(crop.retained_area*100).toFixed(1)}%</dd></div></dl>
    <div className="report-actions"><button className="report-toggle" onClick={()=>setGrid(!grid)} aria-expanded={grid}>{grid?'隐藏畸变网格':'显示畸变网格'}</button><button className="report-toggle" onClick={()=>setDetails(!details)} aria-expanded={details}>{details?'收起技术参数':'查看技术参数'}</button></div>
    {grid&&<DistortionGrid report={report}/>} {details&&<dl className="technical-meta"><div><dt>模型类型</dt><dd>{model.label}</dd></div><div><dt>系数</dt><dd className="technical-value">{model.coefficients.map((value,index)=><span key={index}>k{index+1} = {value}</span>)}</dd></div><div><dt>中心像素</dt><dd>{center.x.toFixed(1)} × {center.y.toFixed(1)}</dd></div><div><dt>估计画布</dt><dd>{model.estimation_size.width} × {model.estimation_size.height}</dd></div><div><dt>渲染缩放</dt><dd>{model.render_scale}</dd></div><div><dt>自动裁切</dt><dd>左 {crop.left} · 上 {crop.top} · 右 {crop.right} · 下 {crop.bottom}</dd></div><div><dt>模型版本</dt><dd>v{model.version}</dd></div></dl>}
  </section>;
}
