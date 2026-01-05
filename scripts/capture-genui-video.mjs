import { chromium } from 'playwright';
import { mkdirSync, renameSync } from 'fs';
import { join } from 'path';

const OUT_DIR = 'docs';
const OUT_NAME = 'agent-to-ui-hero.webm';
const URL = 'http://localhost:5173/project/agent-to-ui';

/**
 * Function: main — invoked via `node scripts/capture-genui-video.mjs`; records the Generative UI hero animation as a 420x250 WebM clip focused tightly on the card.
 * Called by: no internal callers; run manually or from scripts to refresh the asset.
 * Calls: Playwright chromium launch/newContext/newPage, page.goto/scrollIntoViewIfNeeded/waitForTimeout/video, fs.renameSync.
 * Purpose: capture the left-to-right hero animation for use as a landscape hero media asset in docs.
 */
async function main() {
  mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 420, height: 250 },
    recordVideo: { dir: OUT_DIR, size: { width: 420, height: 250 } },
  });

  const page = await context.newPage();
  await page.goto(URL, { waitUntil: 'networkidle' });

  const label = page.getByText('Generative UI').first();
  await label.scrollIntoViewIfNeeded();
  const box = await label.boundingBox();
  if (box) {
    const x = Math.max(0, box.x - 80);
    const y = Math.max(0, box.y - 120);
    await page.evaluate(
      ([sx, sy]) => window.scrollTo(sx, sy),
      [x, y],
    );
  }
  await page.waitForTimeout(2800);

  const video = page.video();
  await page.close();
  await browser.close();

  const original = await video.path();
  const target = join(OUT_DIR, OUT_NAME);
  renameSync(original, target);
  console.log(`Saved: ${target}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
