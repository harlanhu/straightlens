import {test,expect} from '@playwright/test';
import path from 'node:path';
const root=path.resolve('..');

test('real upload, correction, compare, download, then unchanged',async({page})=>{
  const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'镜头校正',exact:true})).toBeVisible();
  await page.getByLabel('选择待校正图片').setInputFiles(path.join(root,'evaluation/generated/grid_barrel.png'));
  await expect(page.getByText('已校正',{exact:true})).toBeVisible({timeout:45000});
  await expect(page.getByRole('img',{name:'校正结果',exact:true})).toBeVisible();
  const workspace=page.getByRole('region',{name:'图像工作区',exact:true});
  await workspace.getByRole('button',{name:'100% 查看'}).click();
  await expect(workspace.getByRole('button',{name:'适应窗口'})).toBeVisible();
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('link',{name:'下载矫正图·裁切',exact:true}).click();
  const download=await downloadPromise;expect(download.suggestedFilename()).toMatch(/corrected\.png$/);
  await workspace.getByRole('button',{name:'原图',exact:true}).click();
  await expect(page.getByRole('img',{name:'原图',exact:true})).toBeVisible();
  await page.getByLabel('选择待校正图片').setInputFiles(path.join(root,'evaluation/generated/blank.png'));
  await expect(page.getByText('已保留原图',{exact:true})).toBeVisible({timeout:10000});
  await expect(page.getByRole('link',{name:'下载原图',exact:true})).toBeVisible();
  expect(errors).toEqual([]);
});

test('invalid upload explains failure without indefinite processing',async({page})=>{
  await page.goto('/');
  await page.getByLabel('选择待校正图片').setInputFiles({name:'broken.png',mimeType:'image/png',buffer:Buffer.from('broken')});
  await expect(page.getByRole('alert')).toContainText('损坏');
  await expect(page.getByText('正在上传图片',{exact:true})).not.toBeVisible();
});

test('mobile layout stays within viewport',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await expect(page.getByRole('button',{name:'导入图片',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});
