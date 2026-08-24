const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  await page.goto('http://localhost:3000/login');
  await page.fill('input[type="text"]', 'support_user');
  await page.fill('input[type="password"]', 'password123');
  await page.click('button[type="submit"]');
  
  await page.waitForTimeout(2000);
  
  const url = page.url();
  console.log("Current URL after login:", url);
  
  const localStorage = await page.evaluate(() => JSON.stringify(window.localStorage));
  console.log("LocalStorage:", localStorage);
  
  const content = await page.content();
  if (content.includes("Authentication failed")) {
      console.log("Found auth failed message");
  }
  
  await browser.close();
})();
