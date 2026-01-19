const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('Navigating to http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'domcontentloaded', timeout: 60000 });

    console.log('Page loaded. Waiting for content...');
    await page.waitForTimeout(3000);

    // Take screenshot of the page
    await page.screenshot({ path: '/mnt/c/Users/Y_J/Desktop/ai-portfolio-main/docs/testing/screenshots/full-page.png', fullPage: true });
    console.log('Full page screenshot saved.');

    // Get all text content from the page
    const bodyText = await page.textContent('body');
    console.log('\n=== Checking for "2026" in page content ===');

    if (bodyText.includes('2026')) {
      console.log('✅ FOUND: "2026" is present in the page content.');

      // Use page.evaluate to find elements more efficiently
      const elements2026 = await page.evaluate(() => {
        const results = [];
        const walker = document.createTreeWalker(
          document.body,
          NodeFilter.SHOW_TEXT,
          null,
          false
        );

        let node;
        while (node = walker.nextNode()) {
          if (node.textContent.includes('2026')) {
            const element = node.parentElement;
            const rect = element.getBoundingClientRect();
            results.push({
              tagName: element.tagName,
              className: element.className,
              id: element.id,
              text: node.textContent.trim().substring(0, 200),
              x: rect.x,
              y: rect.y,
              width: rect.width,
              height: rect.height,
              isLeftSide: rect.x < 400
            });
          }
        }
        return results;
      });

      console.log(`\nFound ${elements2026.length} elements containing "2026":\n`);

      let foundInLeftMenu = false;
      elements2026.forEach((el, idx) => {
        console.log(`${idx + 1}. <${el.tagName}> ${el.id ? `id="${el.id}"` : ''} ${el.className ? `class="${el.className}"` : ''}`);
        console.log(`   Text: "${el.text}"`);
        console.log(`   Position: x=${Math.round(el.x)}, y=${Math.round(el.y)} ${el.isLeftSide ? '← LEFT SIDE' : ''}`);
        if (el.isLeftSide) {
          foundInLeftMenu = true;
        }
        console.log('');
      });

      if (foundInLeftMenu) {
        console.log('✅ "2026" IS in the LEFT MENU BAR (x < 400px)!');
      } else {
        console.log('❌ "2026" is NOT in the left menu bar area.');
      }

    } else {
      console.log('❌ NOT FOUND: "2026" does not appear in the page content.');
    }

    // Try to find the left menu/sidebar
    const sidebarSelectors = [
      'nav',
      '[class*="sidebar"]',
      '[class*="menu"]',
      '[class*="nav"]',
      'aside',
      '[role="navigation"]'
    ];

    let sidebarFound = false;
    let sidebarSelector = null;

    for (const selector of sidebarSelectors) {
      const elements = await page.$$(selector);
      if (elements.length > 0) {
        console.log(`\nFound ${elements.length} element(s) with selector: ${selector}`);
        sidebarSelector = selector;
        sidebarFound = true;
        break;
      }
    }

    // Get left sidebar specific content
    if (sidebarFound) {
      const sidebarText = await page.textContent(sidebarSelector);
      console.log('\n=== Left Menu/Sidebar Content ===');
      console.log(sidebarText);

      if (sidebarText.includes('2026')) {
        console.log('\n✅ "2026" IS in the left menu/sidebar element!');
      } else {
        console.log('\n❌ "2026" is NOT in the left menu/sidebar element.');
      }
    }

    // Take screenshot of just the left portion
    await page.screenshot({
      path: '/mnt/c/Users/Y_J/Desktop/ai-portfolio-main/docs/testing/screenshots/left-menu.png',
      clip: { x: 0, y: 0, width: 400, height: 800 }
    });
    console.log('\nLeft menu screenshot saved to: docs/testing/screenshots/left-menu.png');

  } catch (error) {
    console.error('Error during test:', error.message);
  } finally {
    await browser.close();
  }
})();
