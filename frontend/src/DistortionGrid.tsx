import {useMemo} from 'react';
import type {DistortionReport} from './api';

export default function DistortionGrid({report}:{report:DistortionReport}) {
  const lines=useMemo(()=>Array.from({length:9},(_,index)=>index*12.5),[]);
  if(!report.available||!report.center) return null;
  return <div className="distortion-grid" aria-label="镜头畸变网格示意图">
    <div className="grid-visual" role="img" aria-label={`${report.profile_label||'估计畸变'}的网格示意`}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {lines.map(value=><line key={`v-${value}`} x1={value} y1="0" x2={value} y2="100" />)}
        {lines.map(value=><line key={`h-${value}`} x1="0" y1={value} x2="100" y2={value} />)}
        <circle cx={report.center.x_percent} cy={report.center.y_percent} r="2.2" />
      </svg>
    </div>
    <p>网格中心表示估计的畸变中心，线条弯曲方向表示校正趋势。</p>
  </div>;
}
