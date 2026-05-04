#!/usr/bin/env node
/**
 * scripts/medium-import.mjs
 * --------------------------------------------------------------------------
 * Pull every Medium post from an author's RSS feed and mirror it into the
 * local blog system as MDX:
 *   - Article body → content/blog/<slug>.mdx (Turndown-converted Markdown)
 *   - Images       → public/blog/<slug>/img-N.<ext>  (served at /blog/<slug>/img-N.<ext>)
 *   - Frontmatter  → matches content/blog/_schema.ts (BlogFrontmatter)
 *
 * SEO opinions baked in:
 *   - Self-canonical by default (the local mirror is canonical, not Medium).
 *     Medium-side canonical can be configured to point back to yanqing.app via
 *     Story Settings → Customize canonical link. This tells Google "yanqing.app
 *     is the source"; Medium then gets credit as a syndication mirror, not the
 *     primary. Override per-post via `canonical:` frontmatter if you ever want
 *     Medium to be canonical.
 *   - Top-level Medium <h3> → MDX `##` (H2). Medium uses H3 because Medium
 *     itself owns the H1; on our pages the post title is H1, so the body's
 *     section breaks must be H2 to keep semantic hierarchy + drive the TOC.
 *   - First body image is emitted as raw <img loading="eager"
 *     fetchpriority="high" width=W height=H .../> so it's the LCP candidate
 *     with explicit dimensions (eliminates layout shift).
 *   - Subsequent images get explicit width/height too (CLS prevention).
 *   - Real wordCount + readingMinutes baked into frontmatter (not estimated
 *     from the description like the legacy mdx loader did).
 *   - Description capped at 160 chars on a word boundary (Google snippet ≈ 155).
 *
 * Why RSS instead of scraping the HTML?
 *   medium.com returns 403 to plain curl — they aggressively gate non-browser
 *   clients. The author's RSS feed (medium.com/feed/@handle) returns full
 *   <content:encoded> for every public post and is rate-limit friendly.
 *
 * Image strategy: "land on local first" — every <img> referenced in the
 * Medium HTML is downloaded into public/blog/<slug>/ so the post is
 * fully self-hosted. A future sync step (scripts/blog-sync-blob.mjs, TBD)
 * can re-upload that whole folder to Azure Blob and rewrite the URLs.
 *
 * Usage:
 *   node scripts/medium-import.mjs                # use default handle
 *   node scripts/medium-import.mjs --handle yanqing_j
 *   node scripts/medium-import.mjs --feed ./local-rss.xml
 *   node scripts/medium-import.mjs --slug some-slug   # only re-import one
 *   node scripts/medium-import.mjs --force            # overwrite existing MDX
 *   node scripts/medium-import.mjs --dry              # parse only, write nothing
 *
 * Re-running without --force is safe: existing MDX files are skipped, but any
 * referenced images that aren't on disk yet are still downloaded.
 */

import { writeFile, mkdir, readFile } from 'node:fs/promises';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';
import TurndownService from 'turndown';
import { imageSize } from 'image-size';

// --------------------------------------------------------------------------
// Paths + config
// --------------------------------------------------------------------------
const __filename = fileURLToPath(import.meta.url);
const ROOT = path.resolve(path.dirname(__filename), '..');
const CONTENT_DIR = path.join(ROOT, 'content', 'blog');
const PUBLIC_DIR = path.join(ROOT, 'public', 'blog');

const DEFAULT_HANDLE = 'yanqing_j';
const UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
const WORDS_PER_MINUTE = 220;
const DESC_MAX = 160; // Google snippet sweet spot ≈ 155 chars

// Map Medium categories → our BlogTag union (content/blog/_schema.ts).
// Anything not listed is dropped silently to keep tag pages clean.
const TAG_MAP = {
  // technical lanes
  'ai-agent': 'agents',
  'agentic-ai': 'agents',
  'ai-agents': 'agents',
  llm: 'llm-eng',
  'large-language-models': 'llm-eng',
  'software-engineering': 'llm-eng',
  'software-development': 'llm-eng',
  'anthropic-claude': 'claude',
  claude: 'claude',
  rag: 'rag',
  evals: 'evals',
  finance: 'finance',
  // editorial lanes
  analytics: 'analytics',
  dashboard: 'analytics',
  bi: 'analytics',
  'business-intelligence': 'analytics',
  genai: 'llm-eng',
  skills: 'skills',
  'mac-mini': 'personal-ai',
  clawdbot: 'personal-ai',
  openclaw: 'personal-ai',
  'personal-ai': 'personal-ai',
  'personal-development': 'personal-ai',
  'personal-assistant': 'personal-ai',
  productivity: 'career',
  careers: 'career',
  career: 'career',
  future: 'career',
  'systems-thinking': 'career',
  technology: 'career',
  consciousness: 'philosophy',
  'human-mind': 'philosophy',
  panpsychism: 'philosophy',
  dao: 'philosophy',
  'vibe-coding': 'vibe-coding',
  ui: 'a2ui',
  a2ui: 'a2ui',
};

// --------------------------------------------------------------------------
// CLI args
// --------------------------------------------------------------------------
const args = parseArgs(process.argv.slice(2));

function parseArgs(argv) {
  const out = { handle: DEFAULT_HANDLE, feed: null, slug: null, force: false, dry: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--handle') out.handle = argv[++i];
    else if (a === '--feed') out.feed = argv[++i];
    else if (a === '--slug') out.slug = argv[++i];
    else if (a === '--force') out.force = true;
    else if (a === '--dry') out.dry = true;
    else if (a === '--help' || a === '-h') {
      console.log(
        'Usage: node scripts/medium-import.mjs [--handle X] [--feed file] [--slug s] [--force] [--dry]'
      );
      process.exit(0);
    }
  }
  return out;
}

// --------------------------------------------------------------------------
// Fetchers
// --------------------------------------------------------------------------
async function loadFeed() {
  if (args.feed) {
    log('feed', `reading local file ${args.feed}`);
    return readFile(args.feed, 'utf8');
  }
  const url = `https://medium.com/feed/@${args.handle}`;
  log('feed', `GET ${url}`);
  const res = await fetch(url, { headers: { 'User-Agent': UA, accept: 'application/rss+xml' } });
  if (!res.ok) throw new Error(`Feed fetch failed: ${res.status} ${res.statusText}`);
  return res.text();
}

/** Build candidate URLs to try when fetching a Medium image.
 *  - cdn-images-1.medium.com/max/<n>/<file>  → 403 without a session cookie
 *  - miro.medium.com/v2/resize:fit:<n>/<file>  is the public mirror that works
 *  - miro.medium.com/v2/<file>                 strips the resize directive
 */
function imageCandidateUrls(originalUrl) {
  const urls = [originalUrl];
  const m = originalUrl.match(
    /^https?:\/\/cdn-images-1\.medium\.com\/max\/(\d+)\/(.+)$/i
  );
  if (m) {
    const [, size, file] = m;
    urls.push(`https://miro.medium.com/v2/resize:fit:${size}/${file}`);
    urls.push(`https://miro.medium.com/v2/${file}`);
  }
  return urls;
}

async function downloadImage(url, destPath) {
  if (existsSync(destPath)) return false; // already on disk
  const candidates = imageCandidateUrls(url);
  // Medium's CDN sometimes 403s without a referer. Try plain, then with referer.
  const headerVariants = [
    { 'User-Agent': UA },
    { 'User-Agent': UA, Referer: 'https://medium.com/' },
  ];
  let lastStatus = 0;
  for (const candidate of candidates) {
    for (const headers of headerVariants) {
      const res = await fetch(candidate, { headers, redirect: 'follow' });
      if (res.ok) {
        const buf = Buffer.from(await res.arrayBuffer());
        await mkdir(path.dirname(destPath), { recursive: true });
        await writeFile(destPath, buf);
        return true;
      }
      lastStatus = res.status;
    }
  }
  throw new Error(`Image fetch ${url} → ${lastStatus}`);
}

/** Strip Medium's analytics beacons that masquerade as <img>. */
function isTrackingPixel(url) {
  return /medium\.com\/_\/stat/.test(url);
}

/** Probe a downloaded image for natural dimensions; returns {w, h} or null. */
function probeDims(absPath) {
  try {
    const buf = readFileSync(absPath);
    const dim = imageSize(buf);
    if (dim?.width && dim?.height) return { w: dim.width, h: dim.height };
  } catch (err) {
    warn(`dims probe failed for ${absPath}: ${err.message}`);
  }
  return null;
}

// --------------------------------------------------------------------------
// RSS parsing — jsdom in XML mode handles <content:encoded> CDATA cleanly
// --------------------------------------------------------------------------
function parseFeed(xml) {
  const dom = new JSDOM(xml, { contentType: 'text/xml' });
  const doc = dom.window.document;
  const items = [...doc.querySelectorAll('item')];
  return items.map((item) => {
    const get = (sel) => item.querySelector(sel)?.textContent?.trim() ?? '';
    // namespaced tags need getElementsByTagName-style lookup
    const ns = (tag) => item.getElementsByTagName(tag)[0]?.textContent?.trim() ?? '';
    return {
      title: get('title'),
      link: get('link'),
      pubDate: get('pubDate'),
      creator: ns('dc:creator'),
      categories: [...item.querySelectorAll('category')].map((c) => c.textContent.trim()),
      content: ns('content:encoded'),
    };
  });
}

// --------------------------------------------------------------------------
// Slug + helpers
// --------------------------------------------------------------------------
/** Medium URLs end with `<slug>-<hash12>` — strip the trailing hash. */
function slugFromLink(link, fallbackTitle) {
  try {
    const u = new URL(link);
    const last = u.pathname.split('/').filter(Boolean).pop() ?? '';
    // strip Medium's 12-char hex story hash if present
    const cleaned = last.replace(/-[0-9a-f]{8,16}$/i, '');
    if (cleaned) return cleaned;
  } catch {}
  return slugify(fallbackTitle);
}

function slugify(s) {
  return s
    .toLowerCase()
    .replace(/[''']/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}

function isoDate(rfc2822) {
  const d = new Date(rfc2822);
  if (Number.isNaN(d.getTime())) return new Date().toISOString().slice(0, 10);
  return d.toISOString().slice(0, 10);
}

function mapTags(categories) {
  const mapped = new Set();
  for (const raw of categories) {
    const key = raw.toLowerCase();
    if (TAG_MAP[key]) mapped.add(TAG_MAP[key]);
  }
  // ensure at least one tag so the schema validator is happy
  if (mapped.size === 0) mapped.add('llm-eng');
  return [...mapped];
}

function escapeForJsLiteral(s) {
  // Single-quoted JS string. Escape backslash + apostrophe.
  return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function escapeHtmlAttr(s) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

function imageExtFromUrl(url) {
  try {
    const u = new URL(url);
    const m = u.pathname.match(/\.(png|jpg|jpeg|gif|webp|svg)$/i);
    if (m) return m[1].toLowerCase().replace('jpeg', 'jpg');
  } catch {}
  return 'jpg';
}

// --------------------------------------------------------------------------
// Body transform: download images, rewrite to local /blog/<slug>/img-N.ext,
// strip Medium chrome (figcaption "Photo by..." etc), normalize headings,
// then Turndown → md (with raw <img> for the LCP candidate)
// --------------------------------------------------------------------------
async function transformBody(html, slug) {
  const dom = new JSDOM(`<!doctype html><body>${html}</body>`);
  const doc = dom.window.document;

  // ---- 1. Heading hierarchy: Medium uses H3 (because their template owns H1)
  //         and H4 for sub-sections. On our page the post title is H1, so the
  //         body should start at H2 / H3 to be semantically valid + power the
  //         right-rail TOC (which queries h2[id], h3[id]).
  doc.querySelectorAll('h4').forEach((h) => renameElement(h, 'h3'));
  doc.querySelectorAll('h3').forEach((h) => renameElement(h, 'h2'));
  // (any pre-existing h2 stays h2)

  // ---- 2. Images: download, dimension-probe, rewrite, hero-pick
  const imgEls = [...doc.querySelectorAll('img')];
  let firstImg = null;
  let counter = 0;
  // Track per-image metadata so we can later upgrade the FIRST image to raw
  // HTML (with eager + fetchpriority=high) post-Turndown.
  const imageMeta = []; // { localUrl, alt, w?, h? }

  for (const img of imgEls) {
    const src = img.getAttribute('src');
    if (!src || !/^https?:/.test(src)) continue;
    if (isTrackingPixel(src)) {
      img.remove();
      continue;
    }
    counter += 1;
    const ext = imageExtFromUrl(src);
    const filename = `img-${String(counter).padStart(2, '0')}.${ext}`;
    const dest = path.join(PUBLIC_DIR, slug, filename);
    const localUrl = `/blog/${slug}/${filename}`;
    let dims = null;
    if (!args.dry) {
      try {
        const wrote = await downloadImage(src, dest);
        log('img', `${slug} ${filename} ${wrote ? 'downloaded' : 'cached'}`);
        dims = probeDims(dest);
      } catch (err) {
        warn(`image download failed for ${src}: ${err.message}`);
        continue;
      }
    }
    img.setAttribute('src', localUrl);
    img.removeAttribute('srcset');
    img.removeAttribute('sizes');
    if (dims) {
      img.setAttribute('width', String(dims.w));
      img.setAttribute('height', String(dims.h));
    }
    if (counter === 1) {
      // Mark the first image so Turndown can be told to skip it (we'll inject
      // a raw <img> instead via a placeholder).
      img.setAttribute('data-lcp', 'true');
    }
    imageMeta.push({
      localUrl,
      alt: img.getAttribute('alt') ?? '',
      w: dims?.w,
      h: dims?.h,
      isLcp: counter === 1,
    });
    if (!firstImg) firstImg = { src: localUrl, alt: img.getAttribute('alt') ?? '' };
  }

  // ---- 3. Drop empty <figure> and Medium's signature "Photo by ..." captions.
  doc.querySelectorAll('figcaption').forEach((fc) => {
    if (!fc.textContent || !fc.textContent.trim()) fc.remove();
  });

  // ---- 4. Convert to Markdown.
  const td = new TurndownService({
    headingStyle: 'atx',
    codeBlockStyle: 'fenced',
    bulletListMarker: '-',
    emDelimiter: '_',
  });
  // Medium often wraps code in <pre><span>...</span></pre> — keep raw
  td.addRule('preserveCodeBlocks', {
    filter: ['pre'],
    replacement(_, node) {
      const code = node.textContent ?? '';
      return `\n\n\`\`\`\n${code.trim()}\n\`\`\`\n\n`;
    },
  });
  // Custom rule: emit explicit width/height for non-LCP images via raw HTML
  // (markdown image syntax can't carry dimensions). LCP image gets a sentinel
  // we replace post-conversion so we can also add fetchpriority.
  td.addRule('imgWithDims', {
    filter: 'img',
    replacement(_, node) {
      const src = node.getAttribute('src') ?? '';
      const alt = node.getAttribute('alt') ?? '';
      const w = node.getAttribute('width');
      const h = node.getAttribute('height');
      const lcp = node.getAttribute('data-lcp') === 'true';
      if (lcp) {
        // Sentinel — final raw <img> built below so it can carry fetchpriority
        return `\n\n<!--LCP_IMG:${src}-->\n\n`;
      }
      const attrs = [
        `src="${escapeHtmlAttr(src)}"`,
        `alt="${escapeHtmlAttr(alt)}"`,
        w ? `width="${w}"` : '',
        h ? `height="${h}"` : '',
        'loading="lazy"',
        'decoding="async"',
      ]
        .filter(Boolean)
        .join(' ');
      return `\n\n<img ${attrs} />\n\n`;
    },
  });

  let md = td.turndown(doc.body.innerHTML);

  // Replace the LCP sentinel with a raw <img> carrying fetchPriority=high.
  // NOTE: MDX parses inline HTML as JSX, so attribute names must be JSX-cased
  // (`fetchPriority`, not `fetchpriority`). React then serializes the HTML
  // attribute correctly when prerendering.
  md = md.replace(/<!--LCP_IMG:([^>]+?)-->/g, (_m, src) => {
    const meta = imageMeta.find((i) => i.isLcp && i.localUrl === src) ?? imageMeta[0];
    if (!meta) return '';
    const attrs = [
      `src="${escapeHtmlAttr(src)}"`,
      `alt="${escapeHtmlAttr(meta.alt ?? '')}"`,
      meta.w ? `width="${meta.w}"` : '',
      meta.h ? `height="${meta.h}"` : '',
      'loading="eager"',
      'fetchPriority="high"',
      'decoding="async"',
    ]
      .filter(Boolean)
      .join(' ');
    return `<img ${attrs} />`;
  });

  // Tidy: collapse 3+ blank lines.
  md = md.replace(/\n{3,}/g, '\n\n').trim();
  return { markdown: md, hero: firstImg };
}

/** jsdom helper: rename a DOM element while preserving children + attrs. */
function renameElement(node, newTag) {
  const doc = node.ownerDocument;
  const replacement = doc.createElement(newTag);
  while (node.firstChild) replacement.appendChild(node.firstChild);
  for (const attr of [...node.attributes]) replacement.setAttribute(attr.name, attr.value);
  node.parentNode.replaceChild(replacement, node);
  return replacement;
}

// --------------------------------------------------------------------------
// Description + word count
// --------------------------------------------------------------------------
function deriveDescription(markdown) {
  // First substantive non-heading paragraph, trimmed to DESC_MAX on a word boundary.
  for (const block of markdown.split(/\n\n+/)) {
    const t = block.trim();
    if (
      !t ||
      t.startsWith('#') ||
      t.startsWith('!') ||
      t.startsWith('<') ||
      t.startsWith('>') ||
      t.startsWith('```')
    )
      continue;
    const flat = t
      .replace(/\s+/g, ' ')
      .replace(/[*_`]/g, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // strip [text](url) → text
      .trim();
    if (flat.length < 50) continue;
    if (flat.length <= DESC_MAX) return flat;
    return flat.slice(0, DESC_MAX - 1).replace(/\s+\S*$/, '') + '…';
  }
  return 'Mirrored from Medium.';
}

function countWords(markdown) {
  // Strip code blocks, raw HTML tags, and markdown punctuation before counting.
  const stripped = markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/[#>*_`~\[\]\(\)!|]/g, ' ');
  return stripped.trim().split(/\s+/).filter(Boolean).length;
}

// --------------------------------------------------------------------------
// MDX emission
// --------------------------------------------------------------------------
function buildMdx({ frontmatter, markdown }) {
  const fm = frontmatter;
  const lines = [];
  lines.push('export const frontmatter = {');
  lines.push(`  title: '${escapeForJsLiteral(fm.title)}',`);
  lines.push(`  slug: '${fm.slug}',`);
  lines.push(`  description:`);
  lines.push(`    '${escapeForJsLiteral(fm.description)}',`);
  lines.push(`  publishedAt: '${fm.publishedAt}',`);
  lines.push(`  tags: [${fm.tags.map((t) => `'${t}'`).join(', ')}],`);
  if (fm.canonical) lines.push(`  canonical: '${fm.canonical}',`);
  if (fm.mediumUrl) lines.push(`  mediumUrl: '${fm.mediumUrl}',`);
  lines.push(`  author: 'yanqing-jiang',`);
  if (typeof fm.wordCount === 'number') lines.push(`  wordCount: ${fm.wordCount},`);
  if (typeof fm.readingMinutes === 'number')
    lines.push(`  readingMinutes: ${fm.readingMinutes},`);
  if (fm.hero) {
    lines.push(`  hero: {`);
    lines.push(`    src: '${fm.hero.src}',`);
    lines.push(`    alt: '${escapeForJsLiteral(fm.hero.alt ?? '')}',`);
    lines.push(`  },`);
  }
  lines.push('};');
  lines.push('');
  lines.push(markdown);
  lines.push('');
  return lines.join('\n');
}

// --------------------------------------------------------------------------
// Driver
// --------------------------------------------------------------------------
async function run() {
  const xml = await loadFeed();
  const items = parseFeed(xml);
  log('feed', `parsed ${items.length} items`);

  await mkdir(CONTENT_DIR, { recursive: true });
  await mkdir(PUBLIC_DIR, { recursive: true });

  let written = 0;
  let skipped = 0;
  for (const item of items) {
    const slug = slugFromLink(item.link, item.title);
    if (args.slug && slug !== args.slug) continue;
    const mdxPath = path.join(CONTENT_DIR, `${slug}.mdx`);

    if (existsSync(mdxPath) && !args.force) {
      log('skip', `${slug} (exists; pass --force to overwrite)`);
      skipped++;
      continue;
    }

    log('post', `processing ${slug}`);
    const { markdown, hero } = await transformBody(item.content, slug);
    const description = deriveDescription(markdown);
    const tags = mapTags(item.categories);
    const words = countWords(markdown);
    const fm = {
      title: item.title,
      slug,
      description,
      publishedAt: isoDate(item.pubDate),
      tags,
      // canonical defaults to self (yanqing.app/blog/<slug>) — see BlogHelmet.
      // We still record the Medium URL separately so the post page can show a
      // "Originally on Medium" link without leaking SEO juice.
      mediumUrl: item.link.split('?')[0],
      wordCount: words,
      readingMinutes: Math.max(1, Math.ceil(words / WORDS_PER_MINUTE)),
      hero: hero ?? undefined,
    };
    const mdx = buildMdx({ frontmatter: fm, markdown });
    if (args.dry) {
      log(
        'dry',
        `would write ${mdxPath} (${mdx.length}b, ${tags.join('+')}, ${words}w)`
      );
    } else {
      await writeFile(mdxPath, mdx, 'utf8');
      log('write', `${mdxPath} (${words}w, ~${fm.readingMinutes}min)`);
      written++;
    }
  }

  log(
    'done',
    `${written} written, ${skipped} skipped${args.dry ? ' (dry run, nothing changed)' : ''}`
  );
}

function log(tag, msg) {
  console.log(`[medium-import:${tag}] ${msg}`);
}
function warn(msg) {
  console.warn(`[medium-import:warn] ${msg}`);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
