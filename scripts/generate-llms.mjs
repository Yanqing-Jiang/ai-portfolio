/**
 * File: generate-llms.mjs
 * Called from: scripts/prerender.mjs (after sitemap, before IndexNow)
 * Purpose: Build-time generation of dist/llms.txt + dist/llms-full.txt from
 *          the single source of truth (PROJECT_DATA + allPosts via the SSR
 *          bundle export getLlmsCorpus). Replaces the previously hand-
 *          maintained public/llms.txt + public/llms-full.txt — those drifted
 *          every time a new project or post was added.
 *
 * Why a separate script (not inlined in prerender.mjs): keeps prerender focused
 * on HTML output; mirrors generate-rss.mjs as the precedent for SSR-driven
 * artifact generation. Also lets `node scripts/generate-llms.mjs` run as a
 * standalone smoke test.
 *
 * Note on adoption: research (aeo.press, codersera; May 2026) shows major AI
 * bots rarely fetch llms.txt today. This script is drift-prevention + future-
 * proofing — Cursor / Claude Code / Continue do fetch it, and the cost of
 * maintenance drops to zero.
 */

import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const SITE = 'https://yanqing.app';

function formatProjectSection(p, full) {
  const lines = [];
  lines.push(`## ${p.title}`);
  lines.push(`- URL: ${p.url}`);
  if (p.datePublished) lines.push(`- Published: ${p.datePublished}`);
  if (p.dateModified && p.dateModified !== p.datePublished) {
    lines.push(`- Updated: ${p.dateModified}`);
  }
  lines.push('');
  lines.push(p.description);
  if (!full) return lines.join('\n');

  if (p.technologies?.length) {
    lines.push('');
    lines.push(`**Technologies:** ${p.technologies.join(', ')}`);
  }
  if (p.serviceTags?.length) {
    lines.push(`**Service tags:** ${p.serviceTags.join(', ')}`);
  }
  if (p.statHighlights?.length) {
    lines.push('');
    lines.push('**Outcomes:**');
    for (const stat of p.statHighlights) {
      lines.push(`- ${stat}`);
    }
  }
  if (p.primaryMetric) {
    const { label, value, unitText } = p.primaryMetric;
    lines.push('');
    lines.push(
      `**Primary metric:** ${value}${unitText ? ` ${unitText}` : ''}${label ? ` (${label})` : ''}`
    );
  }
  return lines.join('\n');
}

// Cap per-post body to keep llms-full.txt in the 30-60KB sweet spot
// (Mintlify CDN analysis). At ~10 posts × 3KB body each plus a 22KB
// prelude+projects header, the file lands around 50KB. Truncated posts
// end with a link to the canonical URL so deeper content is one fetch away.
const POST_BODY_MAX_CHARS = 3000;

function truncateBody(body, url) {
  if (body.length <= POST_BODY_MAX_CHARS) return body;
  const slice = body.slice(0, POST_BODY_MAX_CHARS);
  // Cut at the last paragraph break we can find to avoid mid-sentence stops.
  const lastBreak = slice.lastIndexOf('\n\n');
  const trimmed = lastBreak > POST_BODY_MAX_CHARS * 0.6 ? slice.slice(0, lastBreak) : slice;
  return `${trimmed}\n\n... (full post: ${url})`;
}

function formatPostSection(post, full) {
  const lines = [];
  lines.push(`## ${post.title}`);
  lines.push(`- URL: ${post.url}`);
  lines.push(`- Published: ${post.publishedAt}`);
  if (post.updatedAt && post.updatedAt !== post.publishedAt) {
    lines.push(`- Updated: ${post.updatedAt}`);
  }
  if (post.tags?.length) {
    lines.push(`- Tags: ${post.tags.join(', ')}`);
  }
  lines.push('');
  lines.push(post.description);
  if (full && post.plainTextBody) {
    lines.push('');
    lines.push(truncateBody(post.plainTextBody, post.url));
  }
  return lines.join('\n');
}

/**
 * Write dist/llms.txt (summary) + dist/llms-full.txt (long form).
 *
 * @param {object} corpus    From entry-server.tsx getLlmsCorpus()
 * @param {string} preludeMd Static identity prelude (from data/llms-prelude.md)
 * @param {string} distDir   Path to dist/
 * @returns {Promise<{ shortBytes: number; fullBytes: number }>}
 */
export async function writeLlmsArtifacts(corpus, preludeMd, distDir) {
  const today = new Date().toISOString().split('T')[0];
  const footer = `\n\nUpdated: ${today}\n`;

  // ---- llms.txt (summary) ----
  const shortParts = [preludeMd.trim(), '\n', '## Projects', ''];
  for (const p of corpus.projects) {
    shortParts.push(`- [${p.title}](${p.url}) — ${p.description}`);
  }
  shortParts.push('', '## Blog Posts', '');
  for (const post of corpus.posts) {
    shortParts.push(`- [${post.title}](${post.url}) — ${post.description}`);
  }
  const shortDoc = shortParts.join('\n') + footer;
  await writeFile(path.join(distDir, 'llms.txt'), shortDoc, 'utf-8');

  // ---- llms-full.txt (long form, target 30-60KB) ----
  const fullParts = [preludeMd.trim(), '\n', '## Project Catalog', ''];
  for (const p of corpus.projects) {
    fullParts.push(formatProjectSection(p, true));
    fullParts.push('');
  }
  fullParts.push('## Blog Articles', '');
  for (const post of corpus.posts) {
    fullParts.push(formatPostSection(post, true));
    fullParts.push('');
    fullParts.push('---');
    fullParts.push('');
  }
  const fullDoc = fullParts.join('\n') + footer;
  await writeFile(path.join(distDir, 'llms-full.txt'), fullDoc, 'utf-8');

  return { shortBytes: Buffer.byteLength(shortDoc), fullBytes: Buffer.byteLength(fullDoc) };
}

// CLI mode: read prelude + load SSR corpus + write to ./dist
if (import.meta.url === `file://${process.argv[1]}`) {
  const { pathToFileURL } = await import('node:url');
  const rootDir = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
  const preludePath = path.join(rootDir, 'data', 'llms-prelude.md');
  const ssrEntry = path.join(rootDir, 'dist-ssr', 'entry-server.js');
  const distDir = path.join(rootDir, 'dist');

  const preludeMd = await readFile(preludePath, 'utf-8');
  const mod = await import(pathToFileURL(ssrEntry).href);
  const corpus = mod.getLlmsCorpus();
  const { shortBytes, fullBytes } = await writeLlmsArtifacts(corpus, preludeMd, distDir);
  console.log(`Generated llms.txt (${shortBytes}b) + llms-full.txt (${fullBytes}b)`);
}
