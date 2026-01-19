const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('Navigating to http://localhost:5173...');

    // Just wait for the page to start loading, don't wait for all network
    const response = await page.goto('http://localhost:5173', {
      waitUntil: 'commit',
      timeout: 10000
    });

    console.log(`Response status: ${response.status()}`);

    // Wait a bit for React to render
    await page.waitForTimeout(5000);

    // Take screenshot
    await page.screenshot({
      path: '/mnt/c/Users/Y_J/Desktop/ai-portfolio-main/docs/testing/screenshots/page.png',
      fullPage: false
    });
    console.log('Screenshot saved.');

    // Get all text
    const allText = await page.evaluate(() => document.body.innerText);

    console.log('\n=== Page Text Content (first 500 chars) ===');
    console.log(allText.substring(0, 500));
    console.log('\n=== Checking for "2026" ===');

    if (allText.includes('2026')) {
      console.log('✅ FOUND "2026" in page!');

      // Find where it is positioned
      const info = await page.evaluate(() => {
        const results = [];
        const elements = document.querySelectorAll('*');

        for (const el of elements) {
          if (el.textContent.includes('2026') && !el.querySelector('*:not(script):not(style)')) {
            const rect = el.getBoundingClientRect();
            results.push({
              tag: el.tagName,
              class: el.className,
              text: el.textContent.trim().substring(0, 100),
              x: Math.round(rect.x),
              y: Math.round(rect.y),
              isLeft: rect.x < 400
            });
          }
        }
        return results.slice(0, 10); // Just first 10
      });

      console.log(`\nFound ${info.length} elements with "2026":`);
      info.forEach((el, i) => {
        console.log(`\n${i+1}. <${el.tag}> class="${el.class}"`);
        console.log(`   Text: ${el.text}`);
        console.log(`   Position: (${el.x}, ${el.y}) ${el.isLeft ? '← LEFT MENU' : ''}`);
      });

      const inLeftMenu = info.some(el => el.isLeft);
      console.log(`\n${inLeftMenu ? '✅' : '❌'} ${inLeftMenu ? 'YES' : 'NO'} - "2026" is ${inLeftMenu ? '' : 'NOT '}in left menu area (x < 400px)`);

    } else {
      console.log('❌ NOT FOUND - "2026" not in page');
    }

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
})();
