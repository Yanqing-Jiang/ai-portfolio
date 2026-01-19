const { BrowserManager } = require('agent-browser');

(async () => {
  try {
    console.log('Starting browser...');
    const browser = new BrowserManager();
    await browser.launch({ headless: false });
    
    console.log('Navigating to portfolio...');
    await browser.navigate('http://localhost:5173');
    
    console.log('Waiting for page load...');
    await browser.waitForTimeout(2000);
    
    console.log('Taking snapshot...');
    const snapshot = await browser.snapshot();
    console.log('Snapshot:', snapshot.slice(0, 1000));
    
    console.log('Taking screenshot...');
    await browser.screenshot('portfolio-test.png');
    
    console.log('Done!');
    await browser.close();
  } catch (e) {
    console.error('Error:', e.message);
    process.exit(1);
  }
})();
