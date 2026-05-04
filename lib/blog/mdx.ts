// lib/blog/mdx.ts
// Loads MDX blog posts at build time via Vite's import.meta.glob and exposes
// helpers for routing/index pages. Each .mdx file exports `frontmatter` plus
// a default React component.

import type { ComponentType } from 'react';
import type { BlogFrontmatter, BlogTag } from '../../content/blog/_schema';
import { isValidFrontmatter } from '../../content/blog/_schema';

// Inline word-count + reading-time. We avoided the `reading-time` npm package
// because v1.x imports Node's `stream`/`util` which Vite stubs to undefined in
// the browser, throwing at module init and turning the page black.
const WORDS_PER_MINUTE = 220;
function estimateReading(text: string): { words: number; minutes: number } {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return { words, minutes: words / WORDS_PER_MINUTE };
}

export interface BlogPost {
  slug: string;
  frontmatter: BlogFrontmatter;
  /** The MDX content as a React component. */
  Component: ComponentType<Record<string, unknown>>;
  /** Estimated read time in minutes (rounded up, min 1). */
  readingMinutes: number;
  /** Raw word count (used for OG cards). */
  wordCount: number;
}

interface RawModule {
  default: ComponentType<Record<string, unknown>>;
  frontmatter?: unknown;
}

// Vite's import.meta.glob returns a record of { '/path/to/file.mdx': Module }.
const modules = import.meta.glob<RawModule>('/content/blog/*.mdx', { eager: true });

/** Return all non-draft posts, newest first. */
export const allPosts: BlogPost[] = Object.entries(modules)
  .map(([path, mod]) => {
    if (!isValidFrontmatter(mod.frontmatter)) {
      console.warn(`[blog] invalid frontmatter in ${path}`);
      return null;
    }
    const fm = mod.frontmatter;
    const slugFromPath = path.split('/').pop()!.replace(/\.mdx$/, '');
    if (fm.slug !== slugFromPath) {
      console.warn(`[blog] frontmatter.slug "${fm.slug}" does not match filename "${slugFromPath}" in ${path}`);
    }
    // Prefer the real word count baked in at import time
    // (scripts/medium-import.mjs writes wordCount + readingMinutes into
    // frontmatter). Fall back to the synthetic-from-description estimate for
    // hand-authored posts that haven't filled them in yet.
    let wordCount = fm.wordCount;
    let readingMinutes = fm.readingMinutes;
    if (typeof wordCount !== 'number' || typeof readingMinutes !== 'number') {
      const synth = fm.description.repeat(20);
      const stats = estimateReading(synth);
      wordCount = wordCount ?? stats.words;
      readingMinutes = readingMinutes ?? Math.max(1, Math.ceil(stats.minutes));
    }
    return {
      slug: fm.slug,
      frontmatter: fm,
      Component: mod.default,
      readingMinutes,
      wordCount,
    } satisfies BlogPost;
  })
  .filter((p): p is BlogPost => p !== null && !p.frontmatter.draft)
  .sort(
    (a, b) => new Date(b.frontmatter.publishedAt).getTime() - new Date(a.frontmatter.publishedAt).getTime()
  );

/** Find a post by slug. */
export function getPostBySlug(slug: string): BlogPost | undefined {
  return allPosts.find((p) => p.slug === slug);
}

/** Posts filtered by a single tag, newest first. */
export function getPostsByTag(tag: BlogTag): BlogPost[] {
  return allPosts.filter((p) => p.frontmatter.tags.includes(tag));
}

/** Up to N related posts, ranked by tag overlap, excluding the current slug. */
export function getRelatedPosts(currentSlug: string, limit = 3): BlogPost[] {
  const current = getPostBySlug(currentSlug);
  if (!current) return allPosts.slice(0, limit);
  const currentTags = new Set(current.frontmatter.tags);
  return allPosts
    .filter((p) => p.slug !== currentSlug)
    .map((p) => ({
      post: p,
      overlap: p.frontmatter.tags.filter((t) => currentTags.has(t)).length,
    }))
    .sort((a, b) => b.overlap - a.overlap || new Date(b.post.frontmatter.publishedAt).getTime() - new Date(a.post.frontmatter.publishedAt).getTime())
    .slice(0, limit)
    .map((entry) => entry.post);
}

/** All unique tags in use, sorted alphabetically. */
export const allTags: BlogTag[] = Array.from(
  new Set(allPosts.flatMap((p) => p.frontmatter.tags))
).sort() as BlogTag[];

/** Year theme accent (matches LandingPageFlow.tsx YEAR_THEMES). */
export function getYearAccent(year: number): { hex: string; rgba: string; label: string } {
  switch (year) {
    case 2026:
      return { hex: '#fb923c', rgba: 'rgba(251,146,60,0.6)', label: 'orange-400' };
    case 2025:
      return { hex: '#22d3ee', rgba: 'rgba(34,211,238,0.6)', label: 'cyan-400' };
    case 2024:
      return { hex: '#34d399', rgba: 'rgba(52,211,153,0.6)', label: 'emerald-400' };
    default:
      return { hex: '#38bdf8', rgba: 'rgba(56,189,248,0.6)', label: 'sky-400' };
  }
}

/** Format a date as "Apr 15, 2026" for display. */
export function formatPostDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/** Format a date as "Apr 15" (no year) for compact metadata. */
export function formatPostDateShort(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
