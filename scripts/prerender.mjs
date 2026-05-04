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
await writeFile(path.join(rootDir, 'public', 'sitemap.xml'), sitemapXml, 'utf-8');
await writeFile(path.join(distDir, 'sitemap.xml'), sitemapXml, 'utf-8');

console.log('Generated single flat sitemap.xml in public/ and dist/');

// ---- RSS feed (uses the same SSR bundle so post bodies render to HTML once) ----
try {
  const rssEntries = getRssEntries();
  await writeRssFeed(rssEntries, distDir, rootDir);
} catch (err) {
  console.warn('RSS generation failed (continuing build):', err);
}

if (process.env.PING_SITEMAPS === '1') {
  const siteOrigin = pages[0] ? `${new URL(pages[0].loc).origin}/` : 'https://yanqing.app/';
  const sitemapUrl = new URL('sitemap.xml', siteOrigin).toString();
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
