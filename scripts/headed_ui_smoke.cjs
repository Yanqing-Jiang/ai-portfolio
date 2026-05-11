/**
 * Headed-Chromium UI smoke for the post-PR5 fortune engine.
 *
 * Run after the backend (port 8000 or 8100) and frontend (port 5173 or
 * 3000) are both up. Drives the wish flow as the cheapest-to-input
 * smoke (no birth-time picker churn), screenshots every panel, and
 * captures SSE timing from the browser's EventSource via window
 * instrumentation.
 *
 *   npm install -D playwright
 *   node scripts/headed_ui_smoke.cjs
 *
 * Outputs to ~/homer/output/claude/headed-ui-smoke-<timestamp>/
 *   - 01-explore.png       hub
 *   - 02-input.png         input form filled
 *   - 03-thinking.png      ThinkingPanel mid-stream (heartbeat visible)
 *   - 04-narrative-rendered.png  reading after narrative_complete
 *   - 05-banner.png        "Verifying Safety" banner during guardrail tail
 *   - 06-final.png         after complete
 *   - sse-timeline.json    array of {ts, kind, path}
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const os = require('os');

const TS = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 16);
const OUT = path.join(os.homedir(), 'homer/output/claude', `headed-ui-smoke-${TS}`);
fs.mkdirSync(OUT, { recursive: true });

const FRONTEND = process.env.FRONTEND_URL || 'http://localhost:5173';

(async () => {
    const browser = await chromium.launch({ headless: false, slowMo: 100 });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();

    // Instrument EventSource so we can record SSE timing from the browser's
    // perspective (matches what the user would see).
    await page.addInitScript(() => {
        window.__sse = [];
        const Original = window.EventSource;
        window.EventSource = function (...args) {
            const es = new Original(...args);
            es.addEventListener('message', (ev) => {
                try {
                    const env = JSON.parse(ev.data);
                    const body = env.payload || env;
                    let kind = 'unknown', path = null, contents = {};
                    if (body && body.dataModelUpdate) {
                        kind = 'dataModelUpdate';
                        path = body.dataModelUpdate.path;
                        for (const c of body.dataModelUpdate.contents || []) {
                            const v = c.valueBoolean ?? c.valueString ?? c.valueNumber;
                            if (v !== undefined) contents[c.key] = v;
                        }
                    } else if (body && body.surfaceUpdate) kind = 'surfaceUpdate';
                    else if (body && body.beginRendering) kind = 'beginRendering';
                    else if (body && body.audit) kind = 'audit';
                    else if (body && body.done === true) kind = 'done';
                    window.__sse.push({ ts: performance.now(), kind, path, contents, seq: env.seq });
                } catch (e) { /* ignore parse errors */ }
            });
            return es;
        };
    });

    console.log(`[smoke] FRONTEND=${FRONTEND} OUT=${OUT}`);

    // 1. Explore hub
    await page.goto(`${FRONTEND}/project/fortune-agent/explore`);
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(OUT, '01-explore.png'), fullPage: true });

    // 2. Pick wish (custom-wish has the simplest input — just a textarea)
    await page.goto(`${FRONTEND}/project/fortune-agent/custom-wish`);
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(OUT, '02-input.png'), fullPage: true });
    console.log('[smoke] Loaded custom-wish form. The input UI varies — please fill birth + question manually if not auto-filled, then click Submit. Script will continue once SSE traffic begins.');

    // Wait for the user to submit + first SSE event
    const t0 = Date.now();
    while (Date.now() - t0 < 120000) {
        const count = await page.evaluate(() => (window.__sse || []).length);
        if (count > 0) break;
        await page.waitForTimeout(500);
    }
    if (await page.evaluate(() => (window.__sse || []).length) === 0) {
        console.error('[smoke] No SSE events seen in 120s — was Submit clicked?');
        await browser.close();
        return;
    }

    // 3. Mid-stream — capture ThinkingPanel with heartbeat
    await page.waitForTimeout(10000);   // ~10s in, heartbeat should have fired
    await page.screenshot({ path: path.join(OUT, '03-thinking.png'), fullPage: true });

    // 4. Wait for narrative_complete then screenshot
    await page.waitForFunction(() => {
        return (window.__sse || []).some(
            (e) => e.path === '/data/narrative' && e.contents.isComplete === true,
        );
    }, { timeout: 90000 });
    await page.waitForTimeout(500);  // let React commit
    await page.screenshot({ path: path.join(OUT, '04-narrative-rendered.png'), fullPage: true });

    // 5. Banner during guardrail tail
    await page.waitForTimeout(1500);  // banner should be visible during the 3-4s tail
    await page.screenshot({ path: path.join(OUT, '05-banner.png'), fullPage: true });

    // 6. Wait for terminal complete
    await page.waitForFunction(() => {
        return (window.__sse || []).some(
            (e) => e.path === '/data/meta' && e.contents.status === 'complete',
        ) || (window.__sse || []).some((e) => e.kind === 'done');
    }, { timeout: 30000 });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT, '06-final.png'), fullPage: true });

    // Dump SSE timeline
    const timeline = await page.evaluate(() => window.__sse || []);
    fs.writeFileSync(path.join(OUT, 'sse-timeline.json'), JSON.stringify(timeline, null, 2));

    // Compute key derived metrics
    const t = (e) => e.ts;
    const first = timeline[0];
    const narrComplete = timeline.find(
        (e) => e.path === '/data/narrative' && e.contents.isComplete === true,
    );
    const guardrail = timeline.find((e) => e.path === '/data/guardrail');
    const terminal = timeline.find((e) => e.path === '/data/meta' && e.contents.status === 'complete');
    const heartbeats = timeline.filter(
        (e) => e.path === '/data/meta/progress' && (e.contents.message || '').includes('Still reasoning'),
    );

    const metrics = {
        first_event_ts: first ? first.ts : null,
        narrative_complete_offset_s: narrComplete ? (narrComplete.ts - first.ts) / 1000 : null,
        guardrail_offset_s: guardrail ? (guardrail.ts - first.ts) / 1000 : null,
        complete_offset_s: terminal ? (terminal.ts - first.ts) / 1000 : null,
        heartbeat_count: heartbeats.length,
        heartbeat_intervals_s: heartbeats.slice(1).map((h, i) => (h.ts - heartbeats[i].ts) / 1000),
    };
    fs.writeFileSync(path.join(OUT, 'metrics.json'), JSON.stringify(metrics, null, 2));
    console.log(JSON.stringify(metrics, null, 2));

    console.log(`[smoke] Done. Screenshots + JSON in ${OUT}`);
    await browser.close();
})();
