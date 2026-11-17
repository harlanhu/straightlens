import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},baseURL:'http://127.0.0.1:8765'});
const errors=[];page.on('pageerror',error=>errors.push(error.message));
const report=[];
try{
  await page.goto('http://127.0.0.1:8765');
  await page.waitForLoadState('networkidle');
  await mkdir('../docs/screenshots',{recursive:true});
  for(const name of ['grid_barrel.png','grid_pincushion.png']){
    const posted=page.waitForResponse(response=>response.url().endsWith('/api/jobs')&&response.request().method()==='POST');
    await page.getByLabel('选择待校正图片').setInputFiles(path.resolve('../evaluation/generated',name));
    const accepted=await posted;
    if(accepted.status()!==202)throw new Error(`${name}: upload ${accepted.status()}`);
    const {id}=await accepted.json();
    await page.getByText('已校正',{exact:true}).waitFor({timeout:60000});
    const response=await page.request.get(`/api/jobs/${id}`);
    const job=await response.json();
    if(job.status!=='succeeded'||job.outcome!=='corrected')throw new Error(`${name}: ${JSON.stringify(job)}`);
    await page.waitForFunction(()=>Array.from(document.querySelectorAll('[aria-label="图像工作区"] .image-pane img')).length===2&&Array.from(document.querySelectorAll('[aria-label="图像工作区"] .image-pane img')).every(image=>image.complete&&image.naturalWidth>0));
    const result=await page.request.get(job.download_url);
    const bytes=await result.body();
    if(!result.ok()||bytes.subarray(0,8).toString('hex')!=='89504e470d0a1a0a')throw new Error(`${name}: invalid PNG download`);
    const record={filename:name,id,outcome:job.outcome,elapsed_seconds:job.elapsed_seconds,output_size:[job.output_width,job.output_height],stages:job.stages,download_bytes:bytes.length};
    report.push(record);console.log(JSON.stringify(record));
    await page.screenshot({path:`../docs/screenshots/${name.replace('.png','')}.png`,fullPage:false});
  }
  if(errors.length)throw new Error(errors.join('\n'));
  await writeFile('../evaluation/weak-web-report.json',JSON.stringify(report,null,2));
}finally{await browser.close();}
