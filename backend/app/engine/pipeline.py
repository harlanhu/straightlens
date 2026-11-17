from pathlib import Path
import json
import time
from dataclasses import asdict
from PIL import Image
import cv2
import numpy as np
from ..images import normalize_image,make_preview
from .ipol import CandidateConfig,run_ipol,EngineError
from .policy import POLICY,assess_candidates,useful_lines,evaluate_weak
from .remap import render_full_resolution

MESSAGES={
    'geometry_improved':'已完成镜头畸变校正，并自动裁去无效边缘。',
    'insufficient_evidence':'没有找到足够的可靠直线结构，已保留原图。',
    'no_reliable_improvement':'未检测到可靠的校正收益，已保留原图。',
    'unstable_estimate':'不同估计结果不够一致，已保留原图。',
    'too_much_crop':'校正会损失过多画面，已保留原图。',
    'transparent_input':'图片含透明区域，边界可能干扰估计，已保留原图。',
}


def process_image(source: Path, work_dir: Path, stage=lambda value:None, cancel_event=None):
    started=time.monotonic()
    def check_deadline():
        if cancel_event is not None and cancel_event.is_set():raise EngineError('任务已取消')
        if time.monotonic()-started>180:raise EngineError('任务超过计算时限')
    def notify(value):
        check_deadline()
        stage(value)
    notify('preparing')
    info=normalize_image(source,work_dir)
    result={'width':info.width,'height':info.height,'output_width':info.width,'output_height':info.height}
    if info.transparent:
        # Safer than pretending composited transparency boundaries are real lines.
        decision={'outcome':'unchanged','reason_code':'transparent_input'}
    elif np.count_nonzero(cv2.Canny(np.array(Image.open(info.estimate_path).convert('L')),60,160))<80:
        decision={'outcome':'unchanged','reason_code':'insufficient_evidence'}
    else:
        notify('estimating')
        candidates=[]; errors=[]
        for model in POLICY['models']:
            for threshold in POLICY['thresholds']:
                remaining=120-(time.monotonic()-started)
                if remaining<1:
                    break
                config=CandidateConfig(model,threshold)
                try:
                    candidate=run_ipol(info.estimate_path,config,work_dir/f'{model}-{threshold}',min(25,remaining),cancel_event=cancel_event)
                    candidates.append(candidate)
                except EngineError as exc:
                    errors.append(str(exc))
        if not candidates:
            raise EngineError(errors[-1] if errors else '算法未能完成估计')
        # Fixed-center failure is not evidence against off-center distortion.
        # Gate exploration on line count/coverage; final acceptance still uses all
        # held-out, native-model and cross-candidate consistency checks.
        fixed_candidates=list(candidates)
        for model in POLICY['models']:
            viable=[]
            for candidate in fixed_candidates:
                if candidate.config.model!=model:continue
                lines=useful_lines(candidate,check_deadline)
                if len(lines)<POLICY['min_lines']:continue
                coverage=np.ptp(np.concatenate(lines),axis=0)/candidate.size
                if coverage[0]<POLICY['min_width_coverage'] or coverage[1]<POLICY['min_height_coverage']:continue
                viable.append((len(lines),candidate))
            remaining=120-(time.monotonic()-started)
            if not viable or remaining<=5:continue
            config=max(viable,key=lambda item:item[0])[1].config
            try:
                optimized=run_ipol(info.estimate_path,CandidateConfig(config.model,config.threshold,True),work_dir/f'center-{model}',min(20,remaining),cancel_event=cancel_event)
                candidates.append(optimized)
            except EngineError as exc:
                errors.append(str(exc))
        notify('checking')
        assessment=assess_candidates(candidates,check_deadline=check_deadline)
        weak_attempted=0
        if assessment.outcome!='corrected':
            def check_weak_budget():
                check_deadline()
                if time.monotonic()-started>120:raise TimeoutError('weak estimation budget exhausted')
            for original in list(candidates):
                try:
                    check_weak_budget()
                    weak_attempted+=1
                    proposal=evaluate_weak(original,check_deadline=check_weak_budget)
                    if proposal is not None:candidates.append(proposal['candidate'])
                except TimeoutError:
                    break
                except (ValueError,np.linalg.LinAlgError):
                    # A degenerate proposal is not a failure of all native estimates.
                    continue
            assessment=assess_candidates(candidates,check_deadline=check_deadline)
        decision={'outcome':assessment.outcome,'reason_code':assessment.reason_code}
        diagnostics={'decision':assessment.diagnostics,'candidate_count':len(candidates),'weak_attempted':weak_attempted,'engine_errors':errors}
        (work_dir/'diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2))
        if assessment.candidate is not None:
            notify('rendering')
            rendered=render_full_resolution(info,assessment.candidate,work_dir/'result.png',check_deadline=check_deadline)
            if rendered.retained_area<POLICY['min_retained_area']:
                decision={'outcome':'unchanged','reason_code':'too_much_crop'}
            else:
                result.update(output_width=rendered.size[0],output_height=rendered.size[1])
                model_record={'model':assessment.candidate.config.model,'strategy':assessment.candidate.strategy,'coefficients':assessment.candidate.coefficients,
                              'center':assessment.candidate.center,'estimation_size':assessment.candidate.size,
                              'crop':rendered.crop,'retained_area':rendered.retained_area}
                (work_dir/'model.json').write_text(json.dumps(model_record,indent=2))
                from .transforms import TransformSpec
                spec=TransformSpec.from_candidate(assessment.candidate,(info.width,info.height),rendered.crop)
                spec.save(work_dir/'transform.json')
                result.update(uncropped_width=info.width,uncropped_height=info.height,can_reverse=True,transform_version=spec.version)
    if time.monotonic()-started>180:
        raise EngineError('任务超过计算时限')
    stage('finishing')
    preview_source=work_dir/'result.png' if decision['outcome']=='corrected' else info.normalized_path
    make_preview(preview_source,work_dir/'result.jpg')
    result.update(decision)
    result['message']=MESSAGES[result['reason_code']]
    result['elapsed_seconds']=round(time.monotonic()-started,2)
    (work_dir/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result
