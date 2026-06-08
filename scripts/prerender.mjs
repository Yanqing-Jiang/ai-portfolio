/**
 * File: prerender.mjs
 * Called from: npm run build (via npm run prerender)
 * Purpose: Pre-renders all static routes from the SSR bundle, generates sitemap.xml,
 *          and optionally pings search engines. Enables SEO crawling for SPA pages.
 */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const distDir = path.resolve(__dirname, '../dist');
const ssrEntryPath = path.resolve(__dirname, '../dist-ssr/entry-server.js');

const template = await readFile(path.join(distDir, 'index.html'), 'utf-8');

const { render, getRoutes, getSitemapEntries, getRssEntries } = await import(pathToFileURL(ssrEntryPath).href);
const { writeRssFeed } = await import(pathToFileURL(path.resolve(__dirname, 'generate-rss.mjs')).href);

const routes = getRoutes();

// SEO dedupe: every prerendered page should have exactly one <title> and
// one <meta name="description">. Two ways they multiply:
//   1. The template ships generic defaults (so the page is meaningful before
//      React hydrates) — Helmet adds the route-specific ones during render.
//   2. Some pages (e.g. /blog) may also pick up sibling <Helmet> tags from
//      other mounted components in the same SSR pass.
// Crawlers (Google in particular) often take the FIRST <title> they see,
// which would mean serving the GENERIC site-wide title for every route —
// a real ranking hit. We strip template defaults, then post-dedupe to keep
// only the LAST (most-specific) tag of each kind.
const stripTemplateSeoDefaults = (tpl) =>
  tpl
    .replace(/\n?\s*<title>[\s\S]*?<\/title>/, '')
    .replace(/\n?\s*<meta\s+name="description"[\s\S]*?\/>/i, '');

/** Keep only the last occurrence of each tag pattern (post-Helmet injection). */
function dedupeHeadTags(html) {
  return html
    .replace(/(<title[^>]*>[\s\S]*?<\/title>)/gi, (m, _tag, offset, full) => {
      // If a later <title> exists, drop this one.
      const remainder = full.slice(offset + m.length);
      return /<title[^>]*>/i.test(remainder) ? '' : m;
    })
    .replace(/(<meta[^>]*name=["']description["'][^>]*\/?>)/gi, (m, _tag, offset, full) => {
      const remainder = full.slice(offset + m.length);
      return /<meta[^>]*name=["']description["'][^>]*\/?>/i.test(remainder) ? '' : m;
    })
    .replace(/(<link[^>]*rel=["']canonical["'][^>]*\/?>)/gi, (m, _tag, offset, full) => {
      const remainder = full.slice(offset + m.length);
      return /<link[^>]*rel=["']canonical["'][^>]*\/?>/i.test(remainder) ? '' : m;
    });
}

// Vite's build emits dist/index.html with <div id="root"> already populated by
// some upstream pre-bake step (likely a vite plugin) — it contains the entire
// landing-page HTML, NOT an empty placeholder. The previous prerender regex
// `<div id="root"><\/div>` therefore never matched, so every prerendered
// route file ended up serving landing-page content in its body. Result:
// crawlers indexed each blog/project URL with the wrong body content.
//
// Fix: replace EVERYTHING between `<div id="root">` and the last `</div>`
// before `</body>` with the route's freshly-rendered SSR output. This is
// robust to whatever the upstream plugin pre-baked.
function replaceRootDivContents(tpl, newInner) {
  const startMarker = '<div id="root">';
  const startIdx = tpl.indexOf(startMarker);
  if (startIdx === -1) {
    // Fallback: try the empty-placeholder pattern in case the upstream
    // behavior changes back to the standard Vite default.
    return tpl.replace(/<div id="root"><\/div>/, `<div id="root">${newInner}</div>`);
  }
  const bodyCloseIdx = tpl.indexOf('</body>', startIdx);
  if (bodyCloseIdx === -1) return tpl;
  // Find the last </div> between root start and </body>; whatever sits between
  // that </div> and </body> (typically just whitespace) is preserved.
  const between = tpl.slice(startIdx, bodyCloseIdx);
  const lastDivCloseRel = between.lastIndexOf('</div>');
  const trailer =
    lastDivCloseRel === -1 ? '' : between.slice(lastDivCloseRel + '</div>'.length);
  return (
    tpl.slice(0, startIdx) +
    `<div id="root">${newInner}</div>` +
    trailer +
    tpl.slice(bodyCloseIdx)
  );
}

for (const route of routes) {
  const { html, headTags } = render(route);

  // Cleaned template per-route (cheap; pure string ops on a ~100-line file).
  const cleanTemplate = headTags ? stripTemplateSeoDefaults(template) : template;

  const withHead = cleanTemplate.replace('</head>', `${headTags}\n</head>`);
  const deduped = dedupeHeadTags(withHead);
  const withAppHtml = replaceRootDivContents(deduped, html);

  const outputRelative =
    route === '/' ? 'index.html' : path.join(route.replace(/^\//, ''), 'index.html');
  const outputPath = path.join(distDir, outputRelative);

  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, withAppHtml, 'utf-8');

  console.log(`Prerendered ${route} -> ${outputRelative}`);
}

const { pages, projects } = getSitemapEntries();
const allEntries = [...pages, ...projects];
const today = new Date().toISOString().split('T')[0];

const formatDate = (value) => {
  if (!value) return today;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return today;
  return date.toISOString().split('T')[0];
};

const buildUrlEntry = ({ loc, lastModified, changefreq, priority }) => {
  const pieces = [
    `  <url>`,
    `    <loc>${loc}</loc>`,
    `    <lastmod>${formatDate(lastModified)}</lastmod>`,
  ];

  if (changefreq) {
    pieces.push(`    <changefreq>${changefreq}</changefreq>`);
  }
  if (typeof priority === 'number') {
    pieces.push(`    <priority>${priority.toFixed(2)}</priority>`);
  }

  pieces.push('  </url>');
  return pieces.join('\n');
};

const buildUrlSet = (entries) => [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ...entries.map(buildUrlEntry),
  '</urlset>',
].join('\n');

const sitemapXml = buildUrlSet(allEntries);

const rootDir = path.resolve(__dirname, '..');
// Phase A — write only to dist/ (the deploy target). Previously this also wrote to
// public/sitemap.xml, but Vite copies public/* into dist/* before prerender runs,
// which meant the public/ copy was overwritten by us on every build and kept showing
// up as a git diff — the actual drift vector. Source of truth: getSitemapEntries()
// in ssr/entry-server.tsx. Build output: dist/sitemap.xml only.
await writeFile(path.join(distDir, 'sitemap.xml'), sitemapXml, 'utf-8');

console.log(`Generated dist/sitemap.xml with ${allEntries.length} URLs`);

// ---- RSS feed (uses the same SSR bundle so post bodies render to HTML once) ----
try {
  const rssEntries = getRssEntries();
  await writeRssFeed(rssEntries, distDir, rootDir);
} catch (err) {
  console.warn('RSS generation failed (continuing build):', err);
}

// ---- llms.txt + llms-full.txt (Phase B) ----
// Build-time generation from PROJECT_DATA + allPosts via getLlmsCorpus().
// Replaces the static public/llms.txt + public/llms-full.txt — those drifted
// every time a new project or post landed. Failure is non-fatal so a body-
// render bug doesn't block the deploy.
try {
  const { writeLlmsArtifacts } = await import(
    pathToFileURL(path.resolve(__dirname, 'generate-llms.mjs')).href
  );
  const { getLlmsCorpus } = await import(pathToFileURL(ssrEntryPath).href);
  const preludePath = path.resolve(__dirname, '..', 'data', 'llms-prelude.md');
  const preludeMd = await readFile(preludePath, 'utf-8');
  const corpus = getLlmsCorpus();
  const sizes = await writeLlmsArtifacts(corpus, preludeMd, distDir);
  console.log(
    `Generated dist/llms.txt (${sizes.shortBytes}b) + dist/llms-full.txt (${sizes.fullBytes}b)`
  );
} catch (err) {
  console.warn('llms.txt generation failed (continuing build):', err);
}

const siteOrigin = pages[0] ? `${new URL(pages[0].loc).origin}/` : 'https://yanqing.app/';
const sitemapUrl = new URL('sitemap.xml', siteOrigin).toString();

if (process.env.PING_SITEMAPS === '1') {
  const endpoints = [
    `https://www.google.com/ping?sitemap=${encodeURIComponent(sitemapUrl)}`,
    `https://www.bing.com/ping?sitemap=${encodeURIComponent(sitemapUrl)}`,
  ];

  await Promise.all(
    endpoints.map(async (endpoint) => {
      try {
        const response = await fetch(endpoint, { method: 'GET' });
        if (!response.ok) {
          console.warn(`Sitemap ping failed for ${endpoint}: ${response.status}`);
        } else {
          console.log(`Sitemap ping succeeded for ${endpoint}`);
        }
      } catch (error) {
        console.warn(`Sitemap ping threw for ${endpoint}`, error);
      }
    })
  );
}

// ---- IndexNow ping (Bing / Copilot / Perplexity / Yandex) ----
// Per Tw93 GEO playbook (2026-05-03): IndexNow lets Bing pick up new pages
// in minutes instead of waiting for crawlers. Bing's index powers Copilot,
// DuckDuckGo, Yahoo, and feeds many AI search systems.
//
// Set INDEXNOW_KEY in CI/env. The matching key file MUST exist at
// public/<INDEXNOW_KEY>.txt with the key as its content. Generate a key at
// https://www.bing.com/indexnow.
//
// Skipped silently if INDEXNOW_KEY is unset (e.g. local dev builds).
if (process.env.INDEXNOW_KEY) {
  const indexNowKey = process.env.INDEXNOW_KEY;
  const host = new URL(siteOrigin).host;
  const keyLocation = `${siteOrigin}${indexNowKey}.txt`;

  // Send all sitemap URLs. IndexNow accepts up to 10,000 URLs per request.
  const urlList = allEntries.map((entry) => entry.loc);

  try {
    const response = await fetch('https://api.indexnow.org/indexnow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({
        host,
        key: indexNowKey,
        keyLocation,
        urlList,
      }),
    });
    // IndexNow returns 200 (accepted) or 202 (queued) on success.
    if (response.ok || response.status === 202) {
      console.log(`IndexNow ping succeeded: ${urlList.length} URLs submitted (status ${response.status})`);
    } else {
      console.warn(`IndexNow ping returned ${response.status}: ${await response.text()}`);
    }
  } catch (error) {
    console.warn('IndexNow ping threw:', error);
  }
} else {
  console.log('IndexNow ping skipped (INDEXNOW_KEY not set).');
}
