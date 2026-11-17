import {test,expect,Page} from '@playwright/test';
import path from 'node:path';
const root=path.resolve('..');
const tiny=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jJCkAAAAASUVORK5CYII=','base64');

async function mockCorrection(page:Page){
  let count=0;
  await page.route('**/api/**',async route=>{
    const url=new URL(route.request().url());
    if(url.pathname==='/api/health')return route.fulfill({json:{algorithm_ready:true}});
    if(url.pathname==='/api/jobs'&&route.request().method()==='POST')return route.fulfill({status:202,json:{id:String(++count),status:'queued'}});
    if(url.pathname.endsWith('/preview/original')||url.pathname.endsWith('/preview/result'))return route.fulfill({body:tiny,contentType:'image/png'});
    if(/^\/api\/jobs\/\d+$/.test(url.pathname)){
      const id=url.pathname.split('/').pop();
      return route.fulfill({json:{id,status:'succeeded',stage:'complete',stages:['preparing','estimating','checking','rendering','complete'],outcome:'corrected',message:'已完成校正',width:800,height:600,output_width:780,output_height:580,can_reverse:true,download_url:`/api/jobs/${id}/download`,uncropped_download_url:`/api/jobs/${id}/download?variant=uncropped`,uncropped_width:800,uncropped_height:600,original_preview_url:`/api/jobs/${id}/preview/original`,result_preview_url:`/api/jobs/${id}/preview/result`}});
    }
    return route.fulfill({status:404,json:{detail:'not mocked'}});
  });
  await page.goto('/');
  await page.getByLabel('选择待校正图片').setInputFiles({name:'source.png',mimeType:'image/png',buffer:tiny});
  await expect(page.getByText('已校正',{exact:true})).toBeVisible();
}

test('裁切及未裁切下载后可上传整图反算，包括无修改图片',async({page})=>{
  test.setTimeout(120000);
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await page.getByLabel('选择待校正图片').setInputFiles(path.join(root,'evaluation/generated/grid_barrel.png'));
  const cropped=page.getByRole('link',{name:'下载矫正图·裁切',exact:true});
  await expect(cropped).toBeVisible({timeout:45000});
  const uncut=page.getByRole('link',{name:'下载矫正图·未裁切',exact:true});
  await expect(uncut).toBeVisible();
  for(const button of [cropped,uncut]){
    const download=page.waitForEvent('download');await button.click();expect((await download).suggestedFilename()).toMatch(/\.png$/);
  }
  const edited=await page.evaluate(async url=>{
    const image=await createImageBitmap(await (await fetch(url!)).blob());
    const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
    const c=canvas.getContext('2d')!;c.drawImage(image,0,0);c.strokeStyle='#ff3030';c.lineWidth=5;c.beginPath();c.moveTo(25,25);c.lineTo(canvas.width-25,canvas.height-25);c.stroke();
    return canvas.toDataURL('image/png').split(',')[1];
  },await cropped.getAttribute('href'));
  await page.getByLabel('上传待反算图片').setInputFiles({name:'edited.png',mimeType:'image/png',buffer:Buffer.from(edited,'base64')});
  await expect(page.getByRole('link',{name:'下载反算结果',exact:true})).toBeVisible({timeout:30000});
  await expect(page.getByRole('img',{name:'反算结果',exact:true})).toBeVisible();
  const reverse=page.getByRole('region',{name:'反向映射',exact:true});
  await expect(reverse.getByRole('button',{name:'上传图片对比',exact:true})).toHaveAttribute('aria-pressed','true');
  const uploadedCompare=reverse.getByRole('img',{name:'上传图片（反算对比）',exact:true});
  await expect(uploadedCompare).toBeVisible();
  await reverse.getByRole('button',{name:'100% 查看',exact:true}).click();
  await expect(uploadedCompare).toHaveAttribute('src',/\/image\/upload$/);
  await reverse.getByRole('button',{name:'原图对比',exact:true}).click();
  await expect(reverse.getByRole('img',{name:'原图（反算对比）',exact:true})).toBeVisible();
  await reverse.getByRole('button',{name:'上传图片对比',exact:true}).click();
  expect(await page.locator('.image-pane img').count()).toBe(4);
  const download=page.waitForEvent('download');await page.getByRole('link',{name:'下载反算结果'}).click();
  expect((await download).suggestedFilename()).toContain('reversed');
  const body=await (await page.request.get((await uncut.getAttribute('href'))!)).body();
  await page.getByLabel('上传待反算图片').setInputFiles({name:'unchanged.png',mimeType:'image/png',buffer:body});
  await expect(page.getByRole('link',{name:'下载反算结果'})).toBeVisible({timeout:30000});
  await expect(page.getByText('参考版本：未裁切版',{exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await expect(page.getByRole('link',{name:'下载反算结果',exact:true})).toBeVisible();
  expect(errors).toEqual([]);
});

test('反算比例错误保留第一组结果',async({page})=>{
  await mockCorrection(page);
  await page.route('**/api/jobs/1/reverse',route=>route.fulfill({status:422,json:{code:'aspect_ratio_mismatch',detail:'图片比例与参考版本不一致'}}));
  await expect(page.getByLabel('上传待反算图片')).toBeAttached();
  await page.getByLabel('上传待反算图片').setInputFiles({name:'wrong.png',mimeType:'image/png',buffer:tiny});
  await expect(page.getByRole('region',{name:'反向映射'}).getByRole('alert')).toContainText('比例');
  await expect(page.getByRole('link',{name:'下载矫正图·裁切',exact:true})).toBeVisible();
});

test('参考歧义只要求选择版本后重试',async({page})=>{
  await mockCorrection(page);
  await page.route('**/api/jobs/1/reverse',route=>route.request().postData()?.includes('uncropped')?
    route.fulfill({status:202,json:{id:'reverse-child',status:'queued'}}):
    route.fulfill({status:422,json:{code:'basis_ambiguous',detail:'请选择参考版本'}}));
  await page.route('**/api/jobs/reverse-child',route=>route.fulfill({json:{id:'reverse-child',kind:'reverse',status:'succeeded',stage:'complete',stages:[],outcome:'reversed',message:'反算完成',reference_basis:'uncropped',output_width:800,output_height:600,download_url:'/api/jobs/reverse-child/download',result_preview_url:'/api/jobs/1/preview/result'}}));
  await page.getByLabel('上传待反算图片').setInputFiles({name:'other.png',mimeType:'image/png',buffer:tiny});
  await page.getByRole('radio',{name:'基于未裁切图',exact:true}).check();
  await page.getByRole('button',{name:'按所选版本反算',exact:true}).click();
  await expect(page.getByRole('link',{name:'下载反算结果',exact:true})).toBeVisible();
});

test('第二组原图使用反算任务自己的快照地址',async({page})=>{
  await mockCorrection(page);
  await page.route('**/api/jobs/1/reverse',route=>route.fulfill({status:202,json:{id:'reverse-owned',status:'queued'}}));
  await page.route('**/api/jobs/reverse-owned',route=>route.fulfill({json:{id:'reverse-owned',kind:'reverse',status:'succeeded',stage:'complete',stages:[],outcome:'reversed',message:'反算完成',download_url:'/api/jobs/reverse-owned/download',original_preview_url:'/api/jobs/reverse-owned/preview/original',result_preview_url:'/api/jobs/1/preview/result'}}));
  await page.getByLabel('上传待反算图片').setInputFiles({name:'snapshot.png',mimeType:'image/png',buffer:tiny});
  await expect(page.getByRole('link',{name:'下载反算结果',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'原图对比',exact:true}).click();
  await expect(page.getByRole('img',{name:'原图（反算对比）',exact:true})).toHaveAttribute('src','/api/jobs/reverse-owned/preview/original');
});

test('更换原任务会清除旧反算界面',async({page})=>{
  await mockCorrection(page);
  await page.route('**/api/jobs/1/reverse',route=>route.fulfill({status:202,json:{id:'reverse-old',status:'queued'}}));
  await page.route('**/api/jobs/reverse-old',async route=>{
    await new Promise(resolve=>setTimeout(resolve,500));
    await route.fulfill({json:{id:'reverse-old',status:'succeeded',stage:'complete',stages:[],outcome:'reversed',message:'旧结果',download_url:'/old-download'}}).catch(()=>{});
  });
  await page.getByLabel('上传待反算图片').setInputFiles({name:'old.png',mimeType:'image/png',buffer:tiny});
  await page.getByLabel('选择待校正图片').setInputFiles({name:'new.png',mimeType:'image/png',buffer:tiny});
  await expect(page.getByRole('link',{name:'下载矫正图·裁切',exact:true})).toHaveAttribute('href','/api/jobs/2/download');
  await expect(page.getByRole('link',{name:'下载反算结果'})).toHaveCount(0);
});
