import { BrowserManager } from 'agent-browser/dist/browser.js';

(async () => {
  try {
    console.log('=== Agent-Browser Portfolio Exploration ===\n');
    const browser = new BrowserManager();
    await browser.launch({ headless: true });
    
    const page = browser.pages[browser.activePageIndex];
    
    // 1. Home page
    console.log('1. Opening portfolio home...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    console.log('   Title:', await page.title());
    await page.screenshot({ path: 'explore-1-home.png', fullPage: true });
    console.log('   Screenshot: explore-1-home.png\n');
    
    // 2. Show interactive elements
    console.log('2. Interactive elements found:');
    const snapshot = await browser.getSnapshot({ interactive: true });
    console.log(snapshot.tree);
    console.log('');
    
    // 3. Scroll to middle
    console.log('3. Scrolling to middle of page...');
    await page.evaluate(() => window.scrollTo({ top: window.innerHeight, behavior: 'smooth' }));
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'explore-2-scrolled.png' });
    console.log('   Screenshot: explore-2-scrolled.png\n');
    
    // 4. Scroll to bottom
    console.log('4. Scrolling to bottom...');
    await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'explore-3-bottom.png' });
    console.log('   Screenshot: explore-3-bottom.png\n');
    
    // 5. Click a "View Project" link using JavaScript
    console.log('5. Clicking first "View Project" link...');
    await page.evaluate(() => {
      const link = document.querySelector('a[href*="agent-to-ui"], a[href*="project"]');
      if (link) link.click();
    });
    await page.waitForTimeout(2000);
    console.log('   URL after click:', page.url());
    await page.screenshot({ path: 'explore-4-project.png', fullPage: true });
    console.log('   Screenshot: explore-4-project.png\n');
    
    // 6. Go back and try the sidebar nav
    console.log('6. Going back home...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    
    // 7. Click "The Headshot Studio" via JS
    console.log('7. Clicking "The Headshot Studio"...');
    await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('a'));
      const link = links.find(a => a.textContent?.includes('Headshot'));
      if (link) link.click();
    });
    await page.waitForTimeout(2000);
    console.log('   URL:', page.url());
    await page.screenshot({ path: 'explore-5-headshot.png', fullPage: true });
    console.log('   Screenshot: explore-5-headshot.png\n');
    
    // 8. Go back and click the Terminal button
    console.log('8. Going back and clicking Terminal...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('button')).find(b => 
        b.textContent?.includes('Terminal') || b.textContent?.includes('Sign')
      );
      if (btn) btn.click();
    });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'explore-6-terminal.png' });
    console.log('   Screenshot: explore-6-terminal.png\n');
    
    // 9. Final snapshot
    console.log('9. Final page state:');
    const finalSnapshot = await browser.getSnapshot({ interactive: true, compact: true });
    console.log(finalSnapshot.tree?.slice(0, 500) || 'No tree');
    
    console.log('\n=== Exploration Complete! ===');
    console.log('Screenshots saved:');
    console.log('  - explore-1-home.png (full page)');
    console.log('  - explore-2-scrolled.png');
    console.log('  - explore-3-bottom.png');
    console.log('  - explore-4-project.png');
    console.log('  - explore-5-headshot.png');
    console.log('  - explore-6-terminal.png');
    
    await browser.close();
  } catch (e) {
    console.error('Error:', e.message);
    process.exit(1);
  }
})();
