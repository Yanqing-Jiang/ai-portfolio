const { chromium } = require('playwright');

(async () => {
  console.log('Launching browser...');
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    console.log('Navigating to page...');
    // Set viewport to a standard desktop size
    await page.setViewportSize({ width: 1280, height: 800 });
    
    // Go to the URL
    await page.goto('http://localhost:5173/project/generative-ui-a2ui', { 
      waitUntil: 'networkidle',
      timeout: 10000 // 10s timeout to fail fast if server is down
    });
    
    // Wait a bit extra for any animations or client-side hydration
    await page.waitForTimeout(2000);
    
    console.log('Taking screenshot...');
    await page.screenshot({ path: 'screenshot.png', fullPage: true });
    console.log('Screenshot saved to screenshot.png');
    
  } catch (error) {
    console.error('Failed to take screenshot:', error.message);
    if (error.message.includes('ERR_CONNECTION_REFUSED')) {
      console.log('Server appears to be down.');
    }
  } finally {
    await browser.close();
  }
})();
