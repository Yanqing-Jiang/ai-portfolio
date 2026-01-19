const { chromium } = require('playwright');

(async () => {
  // Launching in headed mode as requested
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('Navigating to Google...');
    await page.goto('https://www.google.com');
    console.log('Title:', await page.title());

    console.log('Searching for "Playwright MCP"...');
    await page.fill('textarea[name="q"]', 'Playwright MCP');
    await page.press('textarea[name="q"]', 'Enter');
    
    await page.waitForNavigation();
    console.log('Search results page reached.');
    
    // Stay open for a few seconds to let the user see the "headed" mode
    await page.waitForTimeout(5000);
    
  } catch (error) {
    console.error('Error during navigation:', error);
  } finally {
    await browser.close();
  }
})();
