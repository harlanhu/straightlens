import {useMemo} from 'react';
import type {DistortionReport} from './api';

export default function DistortionGrid({report}:{report:DistortionReport}) {
  const lines=useMemo(()=>Array.from({length:9},(_,index)=>index*12.5),[]);
  if(!report.available||!report.center) return null;
  const curve=report.profile==='barrel'?-4:report.profile==='pincushion'?4:report.profile==='mustache'?2:0;
  function vertical(value:number){const distance=Math.abs(value-50)/50;const bend=curve*distance;return `M ${value} 0 Q ${value+bend} 50 ${value} 100`;}
  function horizontal(value:number){const distance=Math.abs(value-50)/50;const bend=curve*distance;return `M 0 ${value} Q 50 ${value+bend} 100 ${value}`;}
  return <div className="distortion-grid" aria-label="镜头畸变网格示意图">
    <div className="grid-visual" role="img" aria-label={`${report.profile_label||'估计畸变'}的网格示意`}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {lines.map(value=><path key={`v-${value}`} d={vertical(value)} />)}
        {lines.map(value=><path key={`h-${value}`} d={horizontal(value)} />)}
        <circle cx={report.center.x_percent} cy={report.center.y_percent} r="2.2" />
      </svg>
    </div>
    <p>网格中心表示估计的畸变中心，曲线方向表示校正趋势。</p>
  </div>;
}
