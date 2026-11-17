import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({baseURL:'http://127.0.0.1:8765',viewport:{width:1440,height:1100}});
const errors=[];page.on('pageerror',error=>errors.push(error.message));
try{
  await page.goto('/');await page.waitForLoadState('networkidle');
  const posted=page.waitForResponse(r=>r.url().endsWith('/api/jobs')&&r.request().method()==='POST');
  await page.getByLabel('选择待校正图片').setInputFiles(path.resolve('../evaluation/generated/grid_barrel.png'));
  const parentId=(await (await posted).json()).id;
  const uncut=page.getByRole('link',{name:'下载矫正图·未裁切',exact:true});
  await uncut.waitFor({timeout:60000});
  const url=await uncut.getAttribute('href');
  const data=await page.evaluate(async url=>{
    const bitmap=await createImageBitmap(await (await fetch(url)).blob());
    const canvas=document.createElement('canvas');canvas.width=bitmap.width;canvas.height=bitmap.height;
    const c=canvas.getContext('2d');c.drawImage(bitmap,0,0);
    c.strokeStyle='#ff3030';c.lineWidth=8;c.beginPath();c.moveTo(100,200);c.lineTo(canvas.width-100,canvas.height-200);c.stroke();
    c.strokeStyle='#ffcc00';c.lineWidth=6;c.strokeRect(150,150,350,220);
    return canvas.toDataURL('image/png').split(',')[1];
  },url);
  await mkdir('../evaluation/reverse-results',{recursive:true});
  const input=Buffer.from(data,'base64');await writeFile('../evaluation/reverse-results/browser-upload.png',input);
  const reversed=page.waitForResponse(r=>r.url().endsWith('/reverse')&&r.request().method()==='POST');
  await page.getByLabel('上传待反算图片').setInputFiles({name:'external-edited.png',mimeType:'image/png',buffer:input});
  const childId=(await (await reversed).json()).id;
  const download=page.getByRole('link',{name:'下载反算结果',exact:true});await download.waitFor({timeout:60000});
  await page.waitForFunction(()=>{const image=document.querySelector('[aria-label="反向映射"] img[alt="反算结果"]');return image&&image.complete&&image.naturalWidth>0;});
  const record=await (await page.request.get(`/api/jobs/${childId}`)).json();
  await writeFile('../evaluation/reverse-results/browser-result.png',await (await page.request.get(record.download_url)).body());
  await mkdir('../docs/screenshots',{recursive:true});
  await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:'../docs/screenshots/reverse-upper.png',fullPage:false});
  const panel=page.getByRole('region',{name:'反向映射',exact:true});
  await panel.evaluate(element=>window.scrollTo(0,element.getBoundingClientRect().top+window.scrollY-20));
  await page.screenshot({path:'../docs/screenshots/reverse-result.png',fullPage:false});
  for(const width of [768,390]){
    await page.setViewportSize({width,height:900});
    const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth);
    if(!fits)throw new Error(`overflow at ${width}`);
  }
  await panel.evaluate(element=>window.scrollTo(0,element.getBoundingClientRect().top+window.scrollY-20));
  await page.screenshot({path:'../docs/screenshots/reverse-mobile.png',fullPage:false});
  if(errors.length)throw new Error(errors.join('\n'));
  const report={parent_id:parentId,reverse_id:childId,reference_basis:record.reference_basis,output_size:[record.output_width,record.output_height],elapsed_seconds:record.elapsed_seconds,covered_fraction:record.covered_fraction,console_errors:errors};
  await writeFile('../evaluation/reverse-web-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser.close();}
