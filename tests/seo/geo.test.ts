/**
 * @vitest-environment node
 */
// GEO regression suite — Phase G of the ai-portfolio refactor.
// These tests lock in the structural guarantees that drive AI citation:
//   (1) every prerenderable route shows up in the sitemap entries
//   (2) ProjectHelmet + BlogHelmet each emit exactly one canonical head shape
//   (3) the JSON-LD blocks parse and carry the expected schema.org shapes
//   (4) (post-build) dist/llms-full.txt sits in the 30-60KB sweet spot and
//       contains every project + non-draft post slug
//
// Env is `node` (not jsdom) so react-helmet-async stays in SSR mode and
// FilledContext is populated — under jsdom Helmet detects a DOM and emits
// to document.head instead. Tests (1)-(3) are pure SSR imports; test (4)
// opportunistically reads dist/ if it exists (post `npm run build`) and
// skips otherwise so `npm run test` works pre-build in CI.

import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import { describe, it, expect } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import { HelmetProvider, type HelmetServerState } from 'react-helmet-async';

import { PROJECT_DATA } from '../../constants';
import { allPosts, allTags } from '../../lib/blog/mdx';
import { SITE_BASE_URL } from '../../constants/seo';
import {
  getRoutes,
  getSitemapEntries,
  getLlmsCorpus,
} from '../../ssr/entry-server';
import { ProjectHelmet } from '../../components/ProjectHelmet';
import BlogHelmet from '../../components/blog/BlogHelmet';

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const DIST_LLMS_FULL = path.join(REPO_ROOT, 'dist', 'llms-full.txt');

// --------------------------------------------------------------------------
// 1. Sitemap completeness
// --------------------------------------------------------------------------
describe('sitemap completeness', () => {
  it('contains every prerenderable route except tag pages', () => {
    const { pages, projects } = getSitemapEntries();
    const sitemapLocs = new Set([...pages, ...projects].map((entry) => entry.loc));

    // /blog/tag/* are intentionally excluded from the sitemap (low-value
    // facet pages); every other route in getRoutes() must show up.
    const prerenderable = getRoutes().filter((r) => !r.startsWith('/blog/tag/'));

    for (const route of prerenderable) {
      const fullUrl = route === '/' ? `${SITE_BASE_URL}/` : `${SITE_BASE_URL}${route}`;
      expect(sitemapLocs, `route missing from sitemap: ${route}`).toContain(fullUrl);
    }
  });

  it('does not include /blog/tag/* facet pages in sitemap', () => {
    const { pages, projects } = getSitemapEntries();
    const locs = [...pages, ...projects].map((e) => e.loc);
    const tagged = locs.filter((l) => l.includes('/blog/tag/'));
    expect(tagged).toEqual([]);
  });

  it('emits one sitemap entry per project (no canonicalId collisions accidentally splitting)', () => {
    const { projects } = getSitemapEntries();
    expect(projects.length).toBe(PROJECT_DATA.flatMap((y) => y.projects).length);
  });
});

// --------------------------------------------------------------------------
// 2. Helmet injection per page type
// --------------------------------------------------------------------------
function renderHelmet(node: React.ReactNode) {
  const helmetContext: { helmet?: HelmetServerState } = {};
  renderToString(
    React.createElement(HelmetProvider, { context: helmetContext }, node)
  );
  return helmetContext.helmet;
}

describe('Helmet injection — project pages', () => {
  const sampleProject = PROJECT_DATA[0].projects[0];

  it('renders exactly one title and one description', () => {
    const helmet = renderHelmet(React.createElement(ProjectHelmet, { project: sampleProject }));
    const titleHtml = helmet?.title?.toString() ?? '';
    const metaHtml = helmet?.meta?.toString() ?? '';
    expect(titleHtml.match(/<title/g)?.length ?? 0).toBe(1);
    // description appears once as name= meta tag
    const descMatches = metaHtml.match(/name="description"/g) ?? [];
    expect(descMatches.length).toBe(1);
  });

  it('emits a canonical link pointing at the project URL', () => {
    const helmet = renderHelmet(React.createElement(ProjectHelmet, { project: sampleProject }));
    const linkHtml = helmet?.link?.toString() ?? '';
    const slug = sampleProject.canonicalId ?? sampleProject.id;
    expect(linkHtml).toContain(`rel="canonical"`);
    expect(linkHtml).toContain(`${SITE_BASE_URL}/project/${slug}`);
  });

  it('emits at least 3 JSON-LD blocks (Article + Software + Breadcrumb)', () => {
    const helmet = renderHelmet(React.createElement(ProjectHelmet, { project: sampleProject }));
    const scriptHtml = helmet?.script?.toString() ?? '';
    const ldBlocks = scriptHtml.match(/application\/ld\+json/g) ?? [];
    expect(ldBlocks.length).toBeGreaterThanOrEqual(3);
  });
});

describe('Helmet injection — blog pages', () => {
  const samplePost = allPosts[0];

  it('renders exactly one title and one canonical', () => {
    const helmet = renderHelmet(React.createElement(BlogHelmet, { post: samplePost }));
    const titleHtml = helmet?.title?.toString() ?? '';
    const linkHtml = helmet?.link?.toString() ?? '';
    expect(titleHtml.match(/<title/g)?.length ?? 0).toBe(1);
    expect((linkHtml.match(/rel="canonical"/g) ?? []).length).toBe(1);
  });

  it('emits at least 2 JSON-LD blocks (Article + Breadcrumb)', () => {
    const helmet = renderHelmet(React.createElement(BlogHelmet, { post: samplePost }));
    const scriptHtml = helmet?.script?.toString() ?? '';
    const ldBlocks = scriptHtml.match(/application\/ld\+json/g) ?? [];
    expect(ldBlocks.length).toBeGreaterThanOrEqual(2);
  });
});

// --------------------------------------------------------------------------
// 3. JSON-LD shape validity
// --------------------------------------------------------------------------
function extractJsonLdBlocks(html: string): unknown[] {
  // Helmet emits <script data-rh="true" type="application/ld+json">...</script>.
  const re = /<script[^>]*ld\+json[^>]*>([\s\S]*?)<\/script>/g;
  const blocks: unknown[] = [];
  let match: RegExpExecArray | null;
  while ((match = re.exec(html)) !== null) {
    blocks.push(JSON.parse(match[1]));
  }
  return blocks;
}

describe('JSON-LD shape validity', () => {
  const allowedTypes = new Set([
    'Article',
    'SoftwareApplication',
    'SoftwareSourceCode',
    'BreadcrumbList',
    'FAQPage',
    'Person',
  ]);

  it('every project page LD block parses + uses schema.org with an allowed @type', () => {
    const sampleProject = PROJECT_DATA[0].projects[0];
    const helmet = renderHelmet(React.createElement(ProjectHelmet, { project: sampleProject }));
    const scriptHtml = helmet?.script?.toString() ?? '';
    const blocks = extractJsonLdBlocks(scriptHtml) as Array<Record<string, unknown>>;
    expect(blocks.length).toBeGreaterThanOrEqual(3);
    for (const b of blocks) {
      expect(b['@context']).toBe('https://schema.org');
      expect(allowedTypes.has(String(b['@type']))).toBe(true);
    }
  });

  it('Article schema uses ImageObject array for multi-modal lift (Phase C)', () => {
    const sampleProject = PROJECT_DATA[0].projects[0];
    const helmet = renderHelmet(React.createElement(ProjectHelmet, { project: sampleProject }));
    const blocks = extractJsonLdBlocks(helmet?.script?.toString() ?? '') as Array<Record<string, any>>;
    const article = blocks.find((b) => b['@type'] === 'Article');
    expect(article).toBeTruthy();
    expect(Array.isArray(article!.image)).toBe(true);
    expect(article!.image[0]['@type']).toBe('ImageObject');
    expect(article!.image[0].width).toBe(1200);
    expect(article!.image[0].height).toBe(630);
  });

  it('Article.about uses Thing-typed nodes (entity-graph density)', () => {
    // Find a project that has serviceTags (which we fall back to for about)
    const projectWithTags = PROJECT_DATA.flatMap((y) => y.projects).find(
      (p) => (p.serviceTags?.length ?? 0) > 0
    );
    if (!projectWithTags) return;
    const helmet = renderHelmet(React.createElement(ProjectHelmet, { project: projectWithTags }));
    const blocks = extractJsonLdBlocks(helmet?.script?.toString() ?? '') as Array<Record<string, any>>;
    const article = blocks.find((b) => b['@type'] === 'Article');
    expect(Array.isArray(article!.about)).toBe(true);
    expect(article!.about[0]['@type']).toBe('Thing');
    expect(typeof article!.about[0].name).toBe('string');
  });

  it('blog post schema includes Article with required fields', () => {
    const samplePost = allPosts[0];
    const helmet = renderHelmet(React.createElement(BlogHelmet, { post: samplePost }));
    const blocks = extractJsonLdBlocks(helmet?.script?.toString() ?? '') as Array<Record<string, any>>;
    const article = blocks.find((b) => b['@type'] === 'Article');
    expect(article).toBeTruthy();
    expect(article!.headline).toBe(samplePost.frontmatter.title);
    expect(article!.url).toContain(`/blog/${samplePost.slug}`);
  });
});

// --------------------------------------------------------------------------
// 4. llms-full.txt completeness (Phase B) — only when dist/ exists
// --------------------------------------------------------------------------
describe('llms-full.txt build artifact', () => {
  const skipIfNoDist = existsSync(DIST_LLMS_FULL) ? it : it.skip;

  skipIfNoDist('sits in the 30-60KB sweet spot', () => {
    const stats = readFileSync(DIST_LLMS_FULL, 'utf-8');
    const bytes = Buffer.byteLength(stats);
    // Mintlify-derived target. Allow a 25-80KB tolerance band so the test
    // is informative without being brittle when posts grow modestly.
    expect(bytes).toBeGreaterThan(25_000);
    expect(bytes).toBeLessThan(80_000);
  });

  skipIfNoDist('mentions every project (by canonical URL)', () => {
    const body = readFileSync(DIST_LLMS_FULL, 'utf-8');
    const corpus = getLlmsCorpus();
    for (const p of corpus.projects) {
      expect(body, `project missing in llms-full.txt: ${p.id}`).toContain(p.url);
    }
  });

  skipIfNoDist('mentions every non-draft blog post (by URL)', () => {
    const body = readFileSync(DIST_LLMS_FULL, 'utf-8');
    const corpus = getLlmsCorpus();
    for (const post of corpus.posts) {
      expect(body, `post missing in llms-full.txt: ${post.slug}`).toContain(post.url);
    }
  });
});

// Force a no-op import so allTags participates in the type graph (silences
// "imported but never used" linters if they get enabled later).
void allTags;
