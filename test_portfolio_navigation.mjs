import { BrowserManager } from 'agent-browser/dist/browser.js';
import { chromium } from 'playwright';

const BASE_URL = 'http://localhost:5173';

async function waitForServer() {
  console.log('Waiting for server...');
  for (let i = 0; i < 30; i++) {
    try {
      // Using fetch with a short timeout via AbortController if supported, 
      // or just standard fetch. Node 18+ has fetch.
      const response = await fetch(BASE_URL);
      if (response.ok || response.status < 500) {
        console.log('Server is up!');
        return;
      }
    } catch (e) {
        // ignore connection refused
    }
    await new Promise(r => setTimeout(r, 1000));
  }
  throw new Error('Server not ready after 30 seconds');
}

async function runAgentBrowserTest() {
  console.log('\n--- Running Agent-Browser Test (Headless) ---');
  const startTotal = performance.now();
  
  const browser = new BrowserManager();
  await browser.launch({ headless: true });
  const page = browser.pages[browser.activePageIndex];
  
  try {
    const startHome = performance.now();
    console.log(`Navigating to ${BASE_URL}...`);
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    const timeHome = performance.now() - startHome;
    console.log(`Home Title: ${await page.title()} (${timeHome.toFixed(2)}ms)`);
    
    const startP1 = performance.now();
    console.log('Navigating to Project: Agent to UI');
    await page.goto(`${BASE_URL}/project/agent-to-ui`, { waitUntil: 'networkidle' });
    const timeP1 = performance.now() - startP1;
    console.log(`Project 1 Title: ${await page.title()} (${timeP1.toFixed(2)}ms)`);
    
    const startP2 = performance.now();
    console.log('Navigating to Project: LinkedIn Photo');
    await page.goto(`${BASE_URL}/project/linkedin-photo`, { waitUntil: 'networkidle' });
    const timeP2 = performance.now() - startP2;
    console.log(`Project 2 Title: ${await page.title()} (${timeP2.toFixed(2)}ms)`);
    
    console.log(`Agent-Browser Total Time: ${(performance.now() - startTotal).toFixed(2)}ms`);
  } finally {
    await browser.close();
  }
}

async function runPlaywrightHeadedTest() {
  console.log('\n--- Running Playwright Test (Headed) ---');
  const startTotal = performance.now();

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  try {
    const startHome = performance.now();
    console.log(`Navigating to ${BASE_URL}...`);
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    const timeHome = performance.now() - startHome;
    console.log(`Home Title: ${await page.title()} (${timeHome.toFixed(2)}ms)`);
    
    // Visual pause
    await page.waitForTimeout(1000);

    const startP1 = performance.now();
    console.log('Navigating to Project: Agent to UI');
    await page.goto(`${BASE_URL}/project/agent-to-ui`, { waitUntil: 'networkidle' });
    const timeP1 = performance.now() - startP1;
    console.log(`Project 1 Title: ${await page.title()} (${timeP1.toFixed(2)}ms)`);
    await page.waitForTimeout(1000);
    
    const startP2 = performance.now();
    console.log('Navigating to Project: LinkedIn Photo');
    await page.goto(`${BASE_URL}/project/linkedin-photo`, { waitUntil: 'networkidle' });
    const timeP2 = performance.now() - startP2;
    console.log(`Project 2 Title: ${await page.title()} (${timeP2.toFixed(2)}ms)`);
    await page.waitForTimeout(1000);
    
    console.log(`Playwright Headed Total Time (incl. pauses): ${(performance.now() - startTotal).toFixed(2)}ms`);
  } finally {
    await browser.close();
  }
}

(async () => {
  try {
    await waitForServer();
    await runAgentBrowserTest();
    await runPlaywrightHeadedTest();
    console.log('\nAll tests passed successfully!');
    process.exit(0);
  } catch (e) {
    console.error('Test failed:', e);
    process.exit(1);
  }
})();
