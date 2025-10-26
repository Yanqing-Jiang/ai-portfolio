const { chromium } = require("playwright");
const executablePath = "C:\\Users\\Y_J\\AppData\\Local\\ms-playwright\\chromium-1194\\chrome-win\\chrome.exe";
(async () => {
  const browser = await chromium.launch({ executablePath, headless: false });
  const page = await browser.newPage();
  page.on("console", msg => console.log("BROWSER LOG:", msg.type(), msg.text()));
  page.on("pageerror", err => console.log("PAGE ERROR:", err));
  await page.goto("http://localhost:5173/project/next-gen-analytics-agent", { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  await page.click("text=AMD vs NVIDIA revenue comparison in the past 5 years?");
  await page.waitForTimeout(500);
  await page.click("text=Analyze");
  await page.waitForTimeout(5000);
  try {
    await page.waitForSelector("text=Show Process", { timeout: 20000 });
    await page.click("text=Show Process");
    await page.waitForTimeout(2000);
  } catch (err) {
    console.log("Show Process button not available:", err.message);
  }
  await page.screenshot({ path: "playwright_snapshot_after.png", fullPage: true });
  await browser.close();
})();
