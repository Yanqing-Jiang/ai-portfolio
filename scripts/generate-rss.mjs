/**
 * scripts/generate-rss.mjs
 * --------------------------------------------------------------------------
 * Build an RSS 2.0 feed for /blog from the SSR bundle's getRssEntries(),
 * write it to public/rss.xml + dist/rss.xml.
 *
 * Called as a side-effect from scripts/prerender.mjs (after the SSR bundle
 * is built). Can also be run standalone after `npm run build:ssr` for testing.
 *
 * Why RSS 2.0 and not Atom?
 *   RSS 2.0 has the broadest reader support (Feedly, NetNewsWire, FreshRSS,
 *   The Old Reader, Inoreader). Atom is technically nicer but loses ~5%
 *   compatibility for no real benefit. We declare content:encoded for full
 *   article HTML, dc:creator for the author, atom:link for self-discovery,
 *   and one <category> per tag.
 */

import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const SITE = 'https://yanqing.app';
const SITE_NAME = 'Yanqing Jiang';
const FEED_TITLE = 'Yanqing Jiang — Field Notes';
const FEED_DESC =
  'Field notes from the neural stream — research, technical deep-dives, and lessons from shipping AI in production.';
const FEED_URL = `${SITE}/rss.xml`;
const AUTHOR_EMAIL = 'jiangyanqing91@gmail.com';

/** Escape an XML text node. */
function xmlEscape(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/** Wrap a string in CDATA, escaping any inner ]]> sequences. */
function cdata(s) {
  return `<![CDATA[${String(s ?? '').replace(/\]\]>/g, ']]]]><![CDATA[>')}]]>`;
}

/** Convert "YYYY-MM-DD" or ISO to RFC 822 (RSS spec date format). */
function rfc822(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return new Date().toUTCString();
  return d.toUTCString();
}

/** Make all root-relative URLs in HTML absolute against SITE. */
function absolutizeHtml(html) {
  return html
    .replace(/(\s(?:src|href)=)"\/(?!\/)/g, `$1"${SITE}/`)
    // also catch single-quoted attrs (rare but safe)
    .replace(/(\s(?:src|href)=)'\/(?!\/)/g, `$1'${SITE}/`);
}

/**
 * @param entries Array<RssEntry> from entry-server.getRssEntries()
 * @param distDir absolute path to /dist (where build output lives)
 * @param rootDir absolute path to repo root (so we can also write public/rss.xml)
 */
export async function writeRssFeed(entries, distDir, rootDir) {
  // Newest first; cap at 50 to keep the feed payload reasonable.
  const sorted = [...entries]
    .sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt))
    .slice(0, 50);

  const lastBuild = sorted[0]?.updatedAt ?? sorted[0]?.publishedAt ?? new Date().toISOString();

  const items = sorted
    .map((entry) => {
      const html = absolutizeHtml(entry.contentHtml ?? '');
      const heroAbs = entry.heroUrl
        ? entry.heroUrl.startsWith('http')
          ? entry.heroUrl
          : `${SITE}${entry.heroUrl}`
        : null;
      const enclosure = heroAbs
        ? `      <enclosure url="${xmlEscape(heroAbs)}" type="${guessMime(heroAbs)}" length="0" />`
        : '';
      return [
        '    <item>',
        `      <title>${cdata(entry.title)}</title>`,
        `      <link>${xmlEscape(entry.url)}</link>`,
        `      <guid isPermaLink="true">${xmlEscape(entry.url)}</guid>`,
        `      <pubDate>${rfc822(entry.publishedAt)}</pubDate>`,
        `      <dc:creator>${cdata(SITE_NAME)}</dc:creator>`,
        `      <description>${cdata(entry.description)}</description>`,
        ...entry.tags.map((t) => `      <category>${xmlEscape(t)}</category>`),
        enclosure,
        `      <content:encoded>${cdata(html)}</content:encoded>`,
        '    </item>',
      ]
        .filter(Boolean)
        .join('\n');
    })
    .join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${xmlEscape(FEED_TITLE)}</title>
    <link>${xmlEscape(`${SITE}/blog`)}</link>
    <description>${xmlEscape(FEED_DESC)}</description>
    <language>en-us</language>
    <copyright>© ${new Date().getFullYear()} ${xmlEscape(SITE_NAME)}</copyright>
    <managingEditor>${xmlEscape(AUTHOR_EMAIL)} (${xmlEscape(SITE_NAME)})</managingEditor>
    <webMaster>${xmlEscape(AUTHOR_EMAIL)} (${xmlEscape(SITE_NAME)})</webMaster>
    <lastBuildDate>${rfc822(lastBuild)}</lastBuildDate>
    <generator>scripts/generate-rss.mjs</generator>
    <atom:link href="${xmlEscape(FEED_URL)}" rel="self" type="application/rss+xml" />
${items}
  </channel>
</rss>
`;

  const distPath = path.join(distDir, 'rss.xml');
  const publicPath = path.join(rootDir, 'public', 'rss.xml');
  await writeFile(distPath, xml, 'utf-8');
  await writeFile(publicPath, xml, 'utf-8');
  console.log(`Generated rss.xml (${sorted.length} items, ${xml.length}b) → ${distPath} + ${publicPath}`);
  return xml;
}

function guessMime(url) {
  const m = url.toLowerCase().match(/\.(png|jpg|jpeg|gif|webp|svg)(?:$|\?)/);
  if (!m) return 'image/jpeg';
  switch (m[1]) {
    case 'png':
      return 'image/png';
    case 'gif':
      return 'image/gif';
    case 'webp':
      return 'image/webp';
    case 'svg':
      return 'image/svg+xml';
    default:
      return 'image/jpeg';
  }
}

// Standalone CLI mode: `node scripts/generate-rss.mjs` after a build.
if (import.meta.url === `file://${process.argv[1]}`) {
  const { fileURLToPath } = await import('node:url');
  const { pathToFileURL } = await import('node:url');
  const here = path.dirname(fileURLToPath(import.meta.url));
  const root = path.resolve(here, '..');
  const distDir = path.join(root, 'dist');
  const ssrEntry = path.join(root, 'dist-ssr', 'entry-server.js');
  // Lazy import the SSR bundle.
  await readFile(ssrEntry); // throws if not built
  const mod = await import(pathToFileURL(ssrEntry).href);
  const entries = mod.getRssEntries();
  await writeRssFeed(entries, distDir, root);
}
