import React from 'react';
import { renderToString, renderToStaticMarkup } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { HelmetProvider, type FilledContext } from 'react-helmet-async';
import { AppRoutes } from '../App';
import { PROJECT_DATA } from '../constants';
import { LANDING_SEO, SITE_BASE_URL } from '../constants/seo';
import { allPosts, allTags } from '../lib/blog/mdx';

export interface RenderResult {
  html: string;
  headTags: string;
}

export const getRoutes = (): string[] => [
  '/',
  '/consult',
  ...PROJECT_DATA.flatMap((year) => year.projects.map((project) => `/project/${project.id}`)),
  '/blog',
  ...allPosts.map((post) => `/blog/${post.slug}`),
  ...allTags.map((tag) => `/blog/tag/${tag}`),
];

interface SitemapUrl {
  loc: string;
  lastModified?: string;
  changefreq?: string;
  priority?: number;
}

const toIsoDate = (value?: string) => {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  return date.toISOString();
};

export const getSitemapEntries = (): { pages: SitemapUrl[]; projects: SitemapUrl[] } => {
  const projects: SitemapUrl[] = PROJECT_DATA.flatMap((year) =>
    year.projects.map((project) => ({
      loc: `${SITE_BASE_URL}/project/${project.id}`,
      lastModified: toIsoDate(project.dateModified ?? project.datePublished ?? LANDING_SEO.updatedTime),
      changefreq: 'monthly',
      priority: 0.85,
    }))
  );

  const pages: SitemapUrl[] = [
    {
      loc: `${SITE_BASE_URL}/`,
      lastModified: toIsoDate(LANDING_SEO.updatedTime),
      changefreq: 'weekly',
      priority: 1.0,
    },
    {
      loc: `${SITE_BASE_URL}/consult`,
      changefreq: 'monthly',
      priority: 0.9,
    },
    {
      loc: `${SITE_BASE_URL}/blog`,
      changefreq: 'weekly',
      priority: 0.95,
    },
  ];

  // Each post — only include posts whose canonical is the site itself.
  // Mirrored posts (canonical → Medium) get crawled but with rel=canonical handed off,
  // so we still include them in our sitemap to surface internal links.
  const blogPosts: SitemapUrl[] = allPosts.map((post) => ({
    loc: `${SITE_BASE_URL}/blog/${post.slug}`,
    lastModified: toIsoDate(post.frontmatter.updatedAt ?? post.frontmatter.publishedAt),
    changefreq: 'monthly',
    priority: 0.8,
  }));

  return { pages: [...pages, ...blogPosts], projects };
};

/**
 * RSS feed payload — one entry per non-draft post, newest first, with the
 * full body rendered to static HTML so feed readers (including Google Reader
 * archives, FreshRSS, NetNewsWire, Feedly) get the complete article without
 * needing to follow the link.
 *
 * Image src in rendered HTML stays as `/blog/<slug>/...` (root-relative);
 * scripts/generate-rss.mjs absolutizes them to https://yanqing.app/blog/...
 * during XML emit so feed readers can resolve them.
 */
export interface RssEntry {
  slug: string;
  title: string;
  description: string;
  url: string;
  publishedAt: string;
  updatedAt?: string;
  tags: string[];
  heroUrl?: string;
  contentHtml: string;
}

export const getRssEntries = (): RssEntry[] => {
  return allPosts.map((post) => {
    const { Component, frontmatter } = post;
    let contentHtml = '';
    try {
      contentHtml = renderToStaticMarkup(<Component />);
    } catch (err) {
      // Don't poison the whole feed if one MDX component throws.
      contentHtml = `<p><em>Body unavailable in feed — read the full post on the site.</em></p>`;
      console.warn(`[rss] body render failed for ${post.slug}: ${(err as Error).message}`);
    }
    return {
      slug: post.slug,
      title: frontmatter.title,
      description: frontmatter.description,
      url: `${SITE_BASE_URL}/blog/${post.slug}`,
      publishedAt: frontmatter.publishedAt,
      updatedAt: frontmatter.updatedAt,
      tags: frontmatter.tags,
      heroUrl: frontmatter.hero?.src,
      contentHtml,
    };
  });
};

/**
 * LLM corpus payload — single source of truth for the build-time
 * `llms.txt` + `llms-full.txt` generator (scripts/generate-llms.mjs).
 * Mirrors getRssEntries but optimized for plain-text consumption: bodies are
 * rendered via renderToStaticMarkup then stripped of HTML so the output file
 * is RAG-friendly without inflating byte size with tag noise.
 *
 * Why route this through the SSR bundle (vs. reading PROJECT_DATA + MDX
 * directly in the script): the MDX components are React modules — only the
 * SSR bundle can render them in Node. Same constraint that drives the RSS
 * path.
 */
export interface LlmsCorpusProject {
  id: string;
  canonicalId?: string;
  title: string;
  description: string;
  url: string;
  technologies: string[];
  serviceTags: string[];
  statHighlights: string[];
  primaryMetric?: { label?: string; value: number; unitText?: string };
  datePublished?: string;
  dateModified?: string;
}
export interface LlmsCorpusPost {
  slug: string;
  title: string;
  description: string;
  url: string;
  publishedAt: string;
  updatedAt?: string;
  tags: string[];
  /** Plain-text body, HTML stripped. Used for the llms-full.txt long form. */
  plainTextBody: string;
}
export interface LlmsCorpus {
  projects: LlmsCorpusProject[];
  posts: LlmsCorpusPost[];
}

/** Strip HTML tags and decode the few entities we emit. Keep it tiny — these
 *  go into a plain-text file, not back into HTML. */
const stripHtmlToText = (html: string): string =>
  html
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<\/(p|div|li|h\d|br|tr|blockquote)>/gi, '\n')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]+\n/g, '\n')
    .trim();

export const getLlmsCorpus = (): LlmsCorpus => {
  const projects: LlmsCorpusProject[] = PROJECT_DATA.flatMap((year) =>
    year.projects.map((project) => ({
      id: project.id,
      canonicalId: project.canonicalId,
      title: project.seoTitle ?? project.title,
      description: project.seoDescription ?? project.description,
      url: `${SITE_BASE_URL}/project/${project.canonicalId ?? project.id}`,
      technologies: project.technologies ?? [],
      serviceTags: project.serviceTags ?? [],
      statHighlights: project.statHighlights ?? [],
      primaryMetric: project.primaryMetricValue,
      datePublished: project.datePublished,
      dateModified: project.dateModified,
    }))
  );

  const posts: LlmsCorpusPost[] = allPosts.map((post) => {
    const { Component, frontmatter } = post;
    let bodyHtml = '';
    try {
      bodyHtml = renderToStaticMarkup(<Component />);
    } catch (err) {
      bodyHtml = `<p>Body unavailable — read the full post at ${SITE_BASE_URL}/blog/${post.slug}.</p>`;
      console.warn(`[llms] body render failed for ${post.slug}: ${(err as Error).message}`);
    }
    return {
      slug: post.slug,
      title: frontmatter.title,
      description: frontmatter.description,
      url: `${SITE_BASE_URL}/blog/${post.slug}`,
      publishedAt: frontmatter.publishedAt,
      updatedAt: frontmatter.updatedAt,
      tags: frontmatter.tags,
      plainTextBody: stripHtmlToText(bodyHtml),
    };
  });

  return { projects, posts };
};

export const render = (url: string): RenderResult => {
  const helmetContext: FilledContext = {};

  const app = (
    <HelmetProvider context={helmetContext}>
      <StaticRouter location={url}>
        <AppRoutes />
      </StaticRouter>
    </HelmetProvider>
  );

  const html = renderToString(app);
  const helmet = helmetContext.helmet;

  const headTags = [
    helmet?.title?.toString() ?? '',
    helmet?.meta?.toString() ?? '',
    helmet?.link?.toString() ?? '',
    helmet?.script?.toString() ?? '',
    helmet?.noscript?.toString() ?? '',
  ].join('');

  return { html, headTags };
};
