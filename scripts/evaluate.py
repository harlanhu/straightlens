#!/usr/bin/env python3
"""Local evaluation: known synthetic geometry and unlabeled real samples."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import cv2
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.engine.pipeline import process_image
from app.engine.ipol import CandidateResult,CandidateConfig
from app.engine.remap import correct_points


def generate(out):
    out.mkdir(parents=True,exist_ok=True)
    w,h=800,600
    grid=Image.new('RGB',(w,h),'#d7d0c5');draw=ImageDraw.Draw(grid)
    for x in range(35,w,65):draw.line((x,0,x,h),fill='#282c30',width=3)
    for y in range(30,h,60):draw.line((0,y,w,y),fill='#282c30',width=3)
    grid.save(out/'grid_identity.png')
    for name,coefficient,center in [('barrel',.35,(400,300)),('pincushion',-.2,(400,300)),('offcenter',.3,(350,270))]:
        c=CandidateResult(CandidateConfig('pol',.8),(1.,coefficient/(500**2),0.),center,(w,h),[],out)
        yy,xx=np.mgrid[:h,:w]
        corrected=correct_points(np.stack((xx,yy),axis=-1),c).astype('float32')
        distorted=cv2.remap(np.asarray(grid),corrected,None,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
        Image.fromarray(distorted).save(out/f'grid_{name}.png')
    Image.new('RGB',(800,600),'#627b68').save(out/'blank.png')
    natural=Image.new('RGB',(800,600),'#e4e2dc');d=ImageDraw.Draw(natural)
    for r in range(60,500,45): d.ellipse((400-r,300-r,400+r,300+r),outline='#384c43',width=3)
    natural.save(out/'curves.png')
    overlay=grid.copy();d=ImageDraw.Draw(overlay);d.rectangle((30,20,300,85),fill='white');d.text((45,40),'SCORE 0 - 0',fill='black')
    overlay.save(out/'overlay_identity.png')


def geometry_metrics(name,directory):
    truth={'grid_barrel':(.35,(400,300)),'grid_pincushion':(-.2,(400,300)),'grid_offcenter':(.3,(350,270))}
    if name not in truth:return {}
    value,center=truth[name]
    known=CandidateResult(CandidateConfig('pol',.8),(1.,value/500**2,0.),center,(800,600),[],directory)
    x,y=np.meshgrid(np.linspace(80,720,14),np.linspace(60,540,12))
    points=np.column_stack((x.ravel(),y.ravel()))
    target=correct_points(points,known)
    predicted=points
    model_path=directory/'model.json'
    current=json.loads((directory/'result.json').read_text()) if (directory/'result.json').exists() else {}
    if current.get('outcome')=='corrected' and model_path.exists():
        model=json.loads(model_path.read_text())
        fitted=CandidateResult(CandidateConfig(model['model'],.8),tuple(model['coefficients']),tuple(model['center']),tuple(model['estimation_size']),[],directory)
        predicted=correct_points(points,fitted)
    def error(values):
        a=target-target.mean(0);b=values-values.mean(0)
        scale=np.sum(a*b)/np.sum(b*b)
        return float(np.sqrt(np.mean(np.sum((a-b*scale)**2,axis=1))))
    return {'geometry_rms_before_px':round(error(points),3),'geometry_rms_after_px':round(error(predicted),3)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['feasibility','policy'],default='policy');parser.add_argument('--only')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'evaluation/results')
    parser.add_argument('--verify-controls',action='store_true')
    args=parser.parse_args()
    generated=ROOT/'evaluation/generated';generate(generated)
    examples=sorted(p for p in (ROOT/'examples').glob('*') if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'})
    files=[ROOT/'third_party/ipol/example/building.png',*examples,*sorted(generated.glob('*.png'))]
    if args.only: files=[p for p in files if args.only in p.name]
    report=[]
    for i,path in enumerate(files):
        directory=args.output_dir/path.stem
        directory.mkdir(parents=True,exist_ok=True)
        try:
            result=process_image(path,directory)
        except Exception as exc:
            result={'outcome':'failed','error':str(exc)}
        row={'file':str(path.relative_to(ROOT)),**result,**geometry_metrics(path.stem,directory)}
        report.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/f'{args.phase}-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if args.verify_controls:
        unchanged={'grid_identity','curves','blank','overlay_identity'}
        corrected={'building','1','2','grid_barrel','grid_pincushion','grid_offcenter'}
        failures=[row['file'] for row in report if row.get('outcome')=='failed' or
                  (Path(row['file']).stem in unchanged and row.get('outcome')!='unchanged') or
                  (Path(row['file']).stem in corrected and row.get('outcome')!='corrected')]
        if failures:raise SystemExit('Control regression: '+', '.join(failures))

if __name__=='__main__':main()
