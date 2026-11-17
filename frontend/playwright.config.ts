import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./tests', timeout:60000, workers:1,
  use:{baseURL:'http://127.0.0.1:8765',browserName:'chromium',channel:'chrome',headless:true},
  reporter:[['list']],
});
