/**
 * Headed-Chromium 4-function audit (parallel browser contexts).
 *
 * Drives the SSE stream directly against the backend, rendering a live
 * status panel in each tab. We skip the React frontend because the local
 * Vite (:5173) is bound to a stuck IPv6 socket that won't accept new
 * connections (separate issue, not related to the refactor). The route
 * we exercise — POST /api/fortune/create + GET /api/fortune/{id}/stream
 * — is the same one the React app subscribes to via useFortuneStream,
 * so timing is faithful to production.
 *
 *   1. POST /api/fortune/create directly per flow.
 *   2. Open a tab to about:blank, inject a minimal HTML status panel.
 *   3. Open EventSource to /api/fortune/{id}/stream from the page.
 *   4. Stream events update the panel in-place (visible to the operator).
 *   5. Screenshot at: mid-stream (10 s), narrative_complete, terminal complete.
 *   6. Compute latencies + heartbeat counts.
 *
 * Run:
 *   node scripts/headed_4_function_audit.cjs
 *
 * Outputs to:
 *   ~/homer/output/claude/headed-4fn-audit-<timestamp>/
 *     summary.json
 *     summary.md
 *     <flow>/01-mid.png, 02-narrative.png, 03-final.png, sse.json
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');

const TS = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 16);
const OUT = path.join(os.homedir(), 'homer/output/claude', `headed-4fn-audit-${TS}`);
fs.mkdirSync(OUT, { recursive: true });

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8000';

const BIRTH_A = '1990-06-15T08:30:00';
const BIRTH_B = '1992-03-21T14:00:00';
const TIMEZONE = 'Asia/Shanghai';

const FLOWS = [
    {
        key: 'luck_cycle', target_s: 30,
        body: { birth_iso: BIRTH_A, timezone: TIMEZONE, focus: 'luck_cycle:career:1y',
            tone: 'reflective', gender: 'male' },
    },
    {
        key: 'wish', target_s: 35,
        body: { birth_iso: BIRTH_A, timezone: TIMEZONE,
            question: 'Will my next career move pay off?',
            tone: 'reflective', gender: 'male' },
    },
    {
        key: 'occasion', target_s: 35,
        body: { birth_iso: BIRTH_A, timezone: TIMEZONE,
            focus: 'occasion:wedding:2026-06-08:2026-06-14',
            tone: 'reflective', gender: 'male' },
    },
    {
        key: 'compatibility', target_s: 50,
        body: { birth_iso: BIRTH_A, timezone: TIMEZONE, focus: 'compatibility:romance',
            tone: 'reflective', gender: 'male',
            person_b: { birth_iso: BIRTH_B, timezone: TIMEZONE, gender: 'female' } },
    },
];

function buildPanelHtml(flow, fortuneId) {
    return `<!doctype html>
<html><head><meta charset="utf-8"><title>${flow} · audit</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; background:#0c0c12; color:#e6e6f0; margin:0; padding:24px; }
  h1 { margin:0 0 8px; font-size:22px; }
  .row { display:flex; gap:24px; margin:8px 0; font-size:14px; }
  .row b { color:#8ad7ff; }
  .grid { display:grid; grid-template-columns: 200px 1fr; gap:6px 16px; font-family: ui-monospace, monospace; font-size:13px; margin-top:16px; }
  .grid .k { color:#888; }
  .grid .v { color:#cfeacf; }
  .events { margin-top:18px; padding:12px; background:#15151c; border-radius:8px; max-height:55vh; overflow:auto; font-family:ui-monospace,monospace; font-size:12px; line-height:1.5; }
  .ev { padding:2px 0; border-bottom:1px solid #20202a; }
  .ev .t { color:#666; }
  .ev .p { color:#7af09a; }
  .ev .k { color:#ffb46b; }
  .gate { padding:14px; margin-top:12px; border-radius:8px; font-weight:600; }
  .gate.pending { background:#3a2a00; color:#ffd25a; }
  .gate.ok { background:#0e3a1a; color:#7af09a; }
  .gate.miss { background:#3a0e0e; color:#ff8585; }
</style></head>
<body>
<h1>${flow} · headed audit</h1>
<div class="row">fortune_id <b>${fortuneId}</b></div>
<div class="row">target ≤<b>${FLOWS.find((f) => f.key === flow).target_s} s</b></div>
<div class="grid">
  <div class="k">elapsed</div><div class="v" id="elapsed">0.00 s</div>
  <div class="k">events seen</div><div class="v" id="count">0</div>
  <div class="k">narrative_complete</div><div class="v" id="narr">—</div>
  <div class="k">guardrail tail</div><div class="v" id="tail">—</div>
  <div class="k">terminal complete</div><div class="v" id="cmp">—</div>
  <div class="k">heartbeats</div><div class="v" id="hb">0</div>
</div>
<div class="gate pending" id="gate">streaming…</div>
<div class="events" id="events"></div>
<script>
window.__sse = [];
window.__t0 = performance.now();
const $ = (id) => document.getElementById(id);
const elap = setInterval(() => {
  $('elapsed').textContent = ((performance.now() - window.__t0) / 1000).toFixed(2) + ' s';
}, 100);
const url = ${JSON.stringify(BACKEND + '/api/fortune/' + fortuneId + '/stream')};
const es = new EventSource(url);
es.addEventListener('message', (ev) => {
  let env, body, kind = 'unknown', p = null, contents = {};
  try { env = JSON.parse(ev.data); } catch { return; }
  body = env.payload || env;
  if (body.dataModelUpdate) {
    kind = 'dataModelUpdate'; p = body.dataModelUpdate.path;
    for (const c of body.dataModelUpdate.contents || []) {
      const v = c.valueBoolean ?? c.valueString ?? c.valueNumber;
      if (v !== undefined) contents[c.key] = v;
    }
  } else if (body.surfaceUpdate) kind = 'surfaceUpdate';
  else if (body.beginRendering) kind = 'beginRendering';
  else if (body.audit) kind = 'audit';
  else if (body.done === true) kind = 'done';
  const t = (performance.now() - window.__t0) / 1000;
  window.__sse.push({ ts: t * 1000, kind, path: p, contents, seq: env.seq });
  $('count').textContent = window.__sse.length;
  const evDiv = document.createElement('div');
  evDiv.className = 'ev';
  evDiv.innerHTML = '<span class="t">' + t.toFixed(2) + 's</span> ' +
    '<span class="k">' + kind + '</span> ' +
    '<span class="p">' + (p || '') + '</span> ' +
    (Object.keys(contents).length ? '<span style="color:#888">' + Object.entries(contents).map(([k,v])=>k+'='+JSON.stringify(v).slice(0,40)).join(' ') + '</span>' : '');
  $('events').prepend(evDiv);

  if (p === '/data/narrative' && contents.isComplete === true && !window.__narrTs) {
    window.__narrTs = t;
    $('narr').textContent = t.toFixed(2) + ' s';
  }
  if (p === '/data/guardrail' && !window.__guardTs) {
    window.__guardTs = t;
  }
  if ((p === '/data/meta' && contents.status === 'complete') || kind === 'done') {
    if (!window.__cmpTs) {
      window.__cmpTs = t;
      $('cmp').textContent = t.toFixed(2) + ' s';
      if (window.__narrTs) {
        $('tail').textContent = (t - window.__narrTs).toFixed(2) + ' s';
      }
      const hit = t <= ${FLOWS.find((f) => f.key === flow).target_s};
      $('gate').className = 'gate ' + (hit ? 'ok' : 'miss');
      $('gate').textContent = (hit ? 'HIT' : 'MISS') + ' · complete in ' + t.toFixed(2) + ' s · target ${FLOWS.find((f) => f.key === flow).target_s} s';
      es.close();
      clearInterval(elap);
    }
  }
  if (p === '/data/meta/progress' &&
      ((contents.message || '') + '').toLowerCase().includes('still reasoning')) {
    window.__hb = (window.__hb || 0) + 1;
    $('hb').textContent = window.__hb;
  }
});
es.addEventListener('error', (e) => {
  $('gate').className = 'gate miss';
  $('gate').textContent = 'EventSource error — readyState=' + es.readyState;
});
</script>
</body></html>`;
}

async function createFortune(flow) {
    const r = await fetch(`${BACKEND}/api/fortune/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(flow.body),
    });
    if (!r.ok) throw new Error(`create ${flow.key}: ${r.status} ${await r.text()}`);
    return r.json();
}

async function driveOne(browser, flow) {
    const flowDir = path.join(OUT, flow.key);
    fs.mkdirSync(flowDir, { recursive: true });
    const log = (msg) => console.log(`[${flow.key}] ${msg}`);

    const t0 = Date.now();
    log('POST /api/fortune/create');
    const created = await createFortune(flow);
    const fortuneId = created.fortune_id;
    log(`fortune_id=${fortuneId}`);

    const ctx = await browser.newContext({ viewport: { width: 1080, height: 720 } });
    const page = await ctx.newPage();

    page.on('pageerror', (err) => log(`pageerror: ${err.message}`));
    page.on('console', (msg) => {
        const t = msg.type();
        if (t === 'error' || t === 'warning') log(`console.${t}: ${msg.text().slice(0, 200)}`);
    });

    // Stash the panel HTML keyed by fortune_id so the local server can
    // serve it at http://127.0.0.1:<port>/panel?id=<fortuneId>. The
    // real-origin URL is required because the backend's CORS allowlist
    // accepts ``http://127.0.0.1:<port>`` but rejects "null" (which is
    // what setContent / data: URLs produce).
    PANELS.set(fortuneId, buildPanelHtml(flow.key, fortuneId));
    await page.goto(`${PANEL_BASE}/panel?id=${fortuneId}`, { waitUntil: 'load' });
    log('panel loaded; SSE opening');

    // Mid-stream screenshot
    await page.waitForTimeout(10_000);
    await page.screenshot({ path: path.join(flowDir, '01-mid.png'), fullPage: true });

    let narrSeen = false;
    try {
        await page.waitForFunction(() => !!window.__narrTs, { timeout: 180_000 });
        narrSeen = true;
    } catch (e) { log('narrative_complete not seen in 180 s'); }
    if (narrSeen) {
        await page.waitForTimeout(800);
        await page.screenshot({ path: path.join(flowDir, '02-narrative.png'), fullPage: true });
    }

    let cmpSeen = false;
    try {
        await page.waitForFunction(() => !!window.__cmpTs, { timeout: 30_000 });
        cmpSeen = true;
    } catch (e) { log('terminal complete not seen in 30 s after narrative'); }
    if (cmpSeen) {
        await page.waitForTimeout(500);
        await page.screenshot({ path: path.join(flowDir, '03-final.png'), fullPage: true });
    }

    const timeline = await page.evaluate(() => window.__sse || []);
    fs.writeFileSync(path.join(flowDir, 'sse.json'), JSON.stringify(timeline, null, 2));

    const first = timeline[0];
    const narr = timeline.find((e) => e.path === '/data/narrative' && e.contents.isComplete === true);
    const term = timeline.find((e) => e.path === '/data/meta' && e.contents.status === 'complete');
    const heartbeats = timeline.filter(
        (e) => e.path === '/data/meta/progress'
            && ((e.contents.message || '') + '').toLowerCase().includes('still reasoning'),
    );

    const result = {
        flow: flow.key,
        fortune_id: fortuneId,
        target_s: flow.target_s,
        narrative_complete_s: narr ? +(narr.ts / 1000).toFixed(2) : null,
        guardrail_tail_s: (narr && term) ? +((term.ts - narr.ts) / 1000).toFixed(2) : null,
        complete_s: term ? +(term.ts / 1000).toFixed(2) : null,
        heartbeat_count: heartbeats.length,
        heartbeat_intervals_s: heartbeats.slice(1).map(
            (h, i) => +((h.ts - heartbeats[i].ts) / 1000).toFixed(2),
        ),
        event_count: timeline.length,
        first_event_kind: first ? `${first.kind}${first.path ? ':' + first.path : ''}` : null,
        wall_time_s: +((Date.now() - t0) / 1000).toFixed(2),
        verdict: (() => {
            if (!narr || !term) return 'STREAM_INCOMPLETE';
            return (term.ts / 1000) <= flow.target_s ? 'HIT' : 'MISS';
        })(),
    };

    await ctx.close();
    log(`verdict=${result.verdict} narr=${result.narrative_complete_s}s complete=${result.complete_s}s hb=${result.heartbeat_count}`);
    return result;
}

// Local panel-serving HTTP server so each tab loads from a real
// http://127.0.0.1:<port> origin (matches backend CORS allowlist regex).
const PANELS = new Map(); // fortune_id -> HTML
let PANEL_BASE = '';

function startPanelServer() {
    return new Promise((resolve) => {
        const server = http.createServer((req, res) => {
            const m = req.url.match(/^\/panel\?id=([\w-]+)/);
            if (m && PANELS.has(m[1])) {
                res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
                res.end(PANELS.get(m[1]));
                return;
            }
            res.writeHead(404); res.end('not found');
        });
        // Bind to a fixed port (5173) on localhost — both the port AND
        // the hostname must match an entry in CORS_ORIGINS exactly. The
        // allowlist has ``http://localhost:5173`` (NOT 127.0.0.1), and
        // CORS checks the Origin header verbatim. Override via
        // PANEL_PORT env if 5173 is occupied.
        const port = parseInt(process.env.PANEL_PORT || '5173', 10);
        server.listen(port, 'localhost', () => {
            PANEL_BASE = `http://localhost:${port}`;
            console.log(`[audit] panel server: ${PANEL_BASE}`);
            resolve(server);
        });
    });
}

(async () => {
    console.log(`[audit] BACKEND=${BACKEND}  OUT=${OUT}`);
    const panelServer = await startPanelServer();
    const browser = await chromium.launch({ headless: false, slowMo: 0 });

    // ONLY=<flow> filter — useful for cycling through one flow per
    // fresh browser process to dodge chromium's connection-pool bug
    // that drops 2/4 SSE streams when contexts share a process.
    const onlyFilter = process.env.ONLY;
    if (onlyFilter) {
        const before = FLOWS.length;
        FLOWS.splice(0, FLOWS.length, ...FLOWS.filter((f) => f.key === onlyFilter));
        console.log(`[audit] ONLY=${onlyFilter}: filtered ${before} flows → ${FLOWS.length}`);
    }

    // Three execution modes:
    //
    //  - PARALLEL (default): all 4 flows simultaneously, one browser
    //    context each. Fastest but hits chromium's per-origin HTTP/1.1
    //    connection cap (6) when EventSource holds connections open.
    //  - SEQUENTIAL=1: one context at a time, same browser process.
    //    More reliable than parallel but still observed an alternating
    //    failure pattern (1st/3rd HIT, 2nd/4th miss) — chromium appears
    //    to leak connection state across contexts even after ctx.close.
    //  - FRESH_BROWSER=1: spin up a fresh chromium per flow. Slowest
    //    (~5s startup tax × 4) but the most isolated. Use this when
    //    SEQUENTIAL hits the alternating-stream-incomplete pattern.
    const sequential = process.env.SEQUENTIAL === '1' || process.env.FRESH_BROWSER === '1';
    const freshBrowser = process.env.FRESH_BROWSER === '1';
    let results;
    if (sequential) {
        results = [];
        for (const f of FLOWS) {
            let runBrowser = browser;
            if (freshBrowser && results.length > 0) {
                // Close the prior browser entirely and launch a new one
                // to guarantee zero connection-pool / socket reuse.
                try { await runBrowser.close(); } catch {}
                runBrowser = await chromium.launch({ headless: false, slowMo: 0 });
            }
            try {
                results.push(await driveOne(runBrowser, f));
            } catch (err) {
                results.push({ flow: f.key, error: String(err), verdict: 'ERROR' });
            }
            // Re-export for the outer browser.close() below.
            // Last iteration's browser becomes the one we close at the end.
            // eslint-disable-next-line no-global-assign
            globalThis.__lastBrowser = runBrowser;
        }
    } else {
        results = await Promise.all(FLOWS.map((f) => driveOne(browser, f).catch((err) => ({
            flow: f.key, error: String(err), verdict: 'ERROR',
        }))));
    }

    fs.writeFileSync(path.join(OUT, 'summary.json'), JSON.stringify(results, null, 2));

    const fmt = (n) => (n == null || isNaN(n) ? '—' : (typeof n === 'number' ? n.toFixed(2) + ' s' : String(n)));
    const rows = results.map((r) =>
        `| ${r.flow} | ${fmt(r.narrative_complete_s)} | ${fmt(r.guardrail_tail_s)} | ${fmt(r.complete_s)} | ${r.heartbeat_count ?? '—'} | ${r.target_s} s | **${r.verdict}** |`
    );
    const md = [
        `# Headed-Chromium 4-function audit — ${TS}`,
        '',
        `Backend: ${BACKEND}`,
        '',
        '| Flow | narrative_complete | guardrail tail | complete | heartbeats | target | verdict |',
        '|---|---:|---:|---:|---:|---:|---|',
        ...rows,
        '',
        '## Per-flow JSON',
        '',
        ...results.map((r) => `### ${r.flow}\n\n\`\`\`json\n${JSON.stringify(r, null, 2)}\n\`\`\`\n`),
    ].join('\n');
    fs.writeFileSync(path.join(OUT, 'summary.md'), md);

    console.log('\n[audit] DONE');
    console.log(`[audit] ${OUT}/summary.md`);
    await browser.close();
    panelServer.close();
})();
