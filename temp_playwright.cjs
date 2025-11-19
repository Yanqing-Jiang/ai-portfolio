const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 10000 });
    await page.screenshot({ path: 'frontend.png', fullPage: true });
    console.log('Saved screenshot to frontend.png');
  } catch (err) {
    console.error('PAGE ERROR', err);
  } finally {
    await browser.close();
  }
})();
