#!/usr/bin/env python3
"""Generate reproducible opaque editing fixtures and validate real-image reversals."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.engine.transforms import load_transform,original_to_canvas
from app.engine.reverse import render_reverse
from app.engine.remap import map_block


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--corrections-dir',type=Path,default=ROOT/'evaluation/results')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'evaluation/reverse-results')
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    report=[]
    directories=sorted(path.parent for path in args.corrections_dir.glob('*/transform.json'))
    if not directories:
        parser.error('No correction transforms found; run scripts/evaluate.py first.')
    for directory in directories:
        name=directory.name;spec=load_transform(directory)
        with Image.open(directory/'normalized.png') as image:original=np.array(image.convert('RGB'))
        for basis in ('cropped','uncropped'):
            reference=directory/('result.png' if basis=='cropped' else 'uncropped.png')
            with Image.open(reference) as image:reference_image=image.convert('RGB')
            width,height=reference_image.size
            for mode in ('edited','unchanged','other'):
                image=reference_image.copy()
                cx,cy=width//2,height//2
                if mode=='edited':
                    draw=ImageDraw.Draw(image)
                    draw.line((30,height//3,width-30,height*2//3),fill=(255,40,25),width=6)
                    draw.rectangle((cx-8,cy-8,cx+8,cy+8),fill=(255,0,255))
                    draw.text((40,40),'REVERSE TEST',fill=(255,255,0))
                elif mode=='other':image=Image.new('RGB',image.size,(30,90,220))
                upload=args.output_dir/f'{name}-{basis}-{mode}-upload.png'
                output=args.output_dir/f'{name}-{basis}-{mode}-result.png'
                image.save(upload)
                result=render_reverse(upload,directory/'normalized.png',spec,basis,output,mask_path=directory/'valid-mask.png')
                with Image.open(output) as decoded:array=np.array(decoded)
                assert decoded.size==spec.original_size
                y,x=np.mgrid[:spec.original_size[1],:spec.original_size[0]]
                coordinates=original_to_canvas(np.stack((x,y),axis=-1),spec)
                if basis=='cropped':coordinates-=np.array(spec.crop[:2])
                outside=(coordinates[...,0]<-1e-6)|(coordinates[...,1]<-1e-6)|(coordinates[...,0]>width-1+1e-6)|(coordinates[...,1]>height-1+1e-6)
                assert np.array_equal(array[outside],original[outside])
                record={'example':name,'basis':basis,'input':mode,'output':str(output.relative_to(ROOT)),
                        'output_size':list(result.size),'covered_fraction':result.covered_fraction,'outside_pixels_unchanged':int(outside.sum())}
                if mode=='edited':
                    u=cx+(spec.crop[0] if basis=='cropped' else 0)
                    v=cy+(spec.crop[1] if basis=='cropped' else 0)
                    mx,my,valid=map_block(spec.as_candidate(),spec.original_size,v,v+1)
                    px,py=int(round(float(mx[0,u]))),int(round(float(my[0,u])))
                    assert valid[0,u]
                    error=np.max(np.abs(array[py,px].astype(int)-[255,0,255]))
                    assert error<=5
                    record.update(marker_max_color_error=int(error),marker_original_position=[px,py])
                elif mode=='unchanged':record['roundtrip_mean_rgb_error']=round(float(np.mean(np.abs(array.astype(float)-original))),4)
                report.append(record);print(json.dumps(record,ensure_ascii=False),flush=True)
    (args.output_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
