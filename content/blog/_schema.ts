// content/blog/_schema.ts
// Frontmatter schema for blog posts. Each MDX post exports a `frontmatter` const
// matching this shape. We keep validation lightweight (compile-time types) since
// posts are checked-in and authored manually — we control the input.

export type BlogTag =
  // Original technical lanes
  | 'agents'
  | 'llm-eng'
  | 'a2ui'
  | 'claude'
  | 'rag'
  | 'evals'
  | 'finance'
  | 'infra'
  | 'devops'
  // Editorial lanes added for Medium imports (Apr 2026):
  // map to Yanqing's three published angles + lifestyle/philosophy/career.
  | 'analytics'      // BI, dashboards, agentic analytics
  | 'skills'         // SKILL.md, anthropic-claude, skills-as-SaaS
  | 'personal-ai'    // Homer / Clawdbot / personal AI assistants
  | 'philosophy'     // consciousness, dao, panpsychism, mind
  | 'career'         // career notes, productivity, systems-thinking
  | 'vibe-coding';   // weekend-build / vibe-coded / "monster" reflections

export interface BlogFrontmatter {
  /** Display title. */
  title: string;
  /** URL slug, must match filename. */
  slug: string;
  /** 1–2 sentence summary used in OG description, RSS, list cards. */
  description: string;
  /** ISO date — YYYY-MM-DD. */
  publishedAt: string;
  /** Optional last-edited date. */
  updatedAt?: string;
  /** Topic tags. Drive /blog/tag/[tag] pages and related posts. */
  tags: BlogTag[];
  /** External canonical URL. Set ONLY when another URL should be the SEO
   *  canonical (e.g. Medium) — leave undefined to self-canonicalize, which
   *  is the default and preferred for posts authored/owned on yanqing.app. */
  canonical?: string;
  /** Original Medium URL when this post was mirrored from Medium. Used by the
   *  post page to show an "Originally on Medium" link without affecting SEO
   *  (does NOT become the canonical — that's `canonical` above). */
  mediumUrl?: string;
  /** Real word count, computed at import time. When present, the MDX loader
   *  uses this for Article schema + reading time instead of the synthetic
   *  estimate from description.repeat(20). */
  wordCount?: number;
  /** Real reading time in minutes (rounded up). Same provenance as wordCount. */
  readingMinutes?: number;
  /** Override per-post OG image. Otherwise auto-generated at build (Phase 1.5). */
  ogImage?: string;
  /** Draft posts are excluded from index, sitemap, RSS. */
  draft?: boolean;
  /** Optional series grouping. */
  series?: { name: string; order: number };
  /** Author identifier — only one author for now. */
  author: 'yanqing-jiang';
  /** Hero image (Azure Blob URL preferred). */
  hero?: { src: string; alt?: string; caption?: string };
  // Phase C — selective FAQPage schema (post-March-2026 core update safe).
  // Set `emitFaqSchema: true` AND provide `faqItems` (≥3) for BlogHelmet to
  // emit FAQPage JSON-LD. Pure FAQ format hurts AI citation per
  // geo-citation-lab; this is opt-in for posts that are genuinely Q&A-shaped.
  /** Canonical entities mentioned in the post (for schema.org Article.mentions). */
  mentions?: string[];
  /** Q&A pairs for FAQPage schema. Only emitted when emitFaqSchema=true and len ≥ 3. */
  faqItems?: Array<{ question: string; answer: string }>;
  /** Explicit opt-in for FAQPage schema emission. */
  emitFaqSchema?: boolean;
}

/** Cheap runtime guard for posts loaded from import.meta.glob. */
export function isValidFrontmatter(fm: unknown): fm is BlogFrontmatter {
  if (!fm || typeof fm !== 'object') return false;
  const f = fm as Record<string, unknown>;
  return (
    typeof f.title === 'string' &&
    typeof f.slug === 'string' &&
    typeof f.description === 'string' &&
    typeof f.publishedAt === 'string' &&
    Array.isArray(f.tags) &&
    f.author === 'yanqing-jiang'
  );
}
