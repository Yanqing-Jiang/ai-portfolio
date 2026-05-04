import React, { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
// @ts-ignore — react-helmet-async types not bundled cleanly with ESM
import { Helmet } from 'react-helmet-async';
import {
  allPosts,
  formatPostDate,
  formatPostDateShort,
  getYearAccent,
} from '../../lib/blog/mdx';
import type { BlogPost } from '../../lib/blog/mdx';
import type { BlogTag } from '../../content/blog/_schema';

/**
 * BlogIndexPage — editorial-v2 design.
 *
 * Layout:
 *   [HERO]    Latest piece. Split column (text left, 4:5 portrait right).
 *             Meta row sits ABOVE the title — date-first to stay consistent
 *             with the rest of the site (sidebar, post page).
 *   [ARCHIVE] Rich list. Each row: 80x80 thumbnail · meta-above-title ·
 *             2-line excerpt. Smaller than the old magazine cards but with
 *             enough context to justify the click.
 *
 * Replaces the previous "quiet-1" zig-zag list, which duplicated the sidebar
 * and pushed meta below the title (clashed with the date-first pattern).
 *
 * Mounted at:
 *   /blog                  — all posts (newest is the hero)
 *   /blog/tag/:tag         — filtered. The first match becomes the hero.
 */
const BlogIndexPage: React.FC = () => {
  const { tag } = useParams<{ tag?: BlogTag }>();
  const filtered = useMemo<BlogPost[]>(
    () => (tag ? allPosts.filter((p) => p.frontmatter.tags.includes(tag)) : allPosts),
    [tag]
  );

  const pageTitle = tag
    ? `Writing — ${tag} — Yanqing Jiang`
    : 'Writing — Yanqing Jiang';
  const pageDescription = tag
    ? `Posts tagged ${tag} on yanqing.app — field notes on shipping AI in production.`
    : 'Field notes from the neural stream — research, technical deep-dives, and lessons from shipping AI in production.';

  const hero = filtered[0];
  const rest = filtered.slice(1);

  return (
    <div className="relative min-h-screen bg-slate-950 text-gray-300 selection:bg-sky-500/30">
      <Helmet>
        <title>{pageTitle}</title>
        <meta name="description" content={pageDescription} />
        <link rel="canonical" href={`https://yanqing.app/blog${tag ? `/tag/${tag}` : ''}`} />
        <link rel="alternate" type="application/rss+xml" title="Yanqing Jiang — Field Notes" href="https://yanqing.app/rss.xml" />
        <meta property="og:type" content="website" />
        <meta property="og:title" content={pageTitle} />
        <meta property="og:description" content={pageDescription} />
        <meta property="og:url" content={`https://yanqing.app/blog${tag ? `/tag/${tag}` : ''}`} />
        <meta property="og:site_name" content="Yanqing Jiang" />
        <meta property="og:image" content="https://yanqing.app/og-default.png" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:site" content="@yanqing_j" />
        <meta name="twitter:title" content={pageTitle} />
        <meta name="twitter:description" content={pageDescription} />
        <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1" />
        {/* Blog (CollectionPage) JSON-LD: declares this URL as the index for
            field notes, and lists each post with title, url, and date so
            crawlers don't have to re-fetch every post to index the set. */}
        <script type="application/ld+json">{JSON.stringify({
          '@context': 'https://schema.org',
          '@type': 'Blog',
          '@id': `https://yanqing.app/blog${tag ? `/tag/${tag}` : ''}`,
          name: 'Field Notes',
          description: 'Field notes from Yanqing Jiang on shipping AI in production.',
          url: `https://yanqing.app/blog${tag ? `/tag/${tag}` : ''}`,
          inLanguage: 'en',
          author: {
            '@type': 'Person',
            name: 'Yanqing Jiang',
            url: 'https://yanqing.app',
          },
          blogPost: filtered.slice(0, 25).map((p) => ({
            '@type': 'BlogPosting',
            headline: p.frontmatter.title,
            url: `https://yanqing.app/blog/${p.slug}`,
            datePublished: new Date(p.frontmatter.publishedAt).toISOString(),
            description: p.frontmatter.description,
            keywords: p.frontmatter.tags.join(', '),
          })),
        })}</script>
      </Helmet>

      {/* Subtle noise overlay — matches landing aesthetic without competing with the prose */}
      <div className="fixed inset-0 z-0 pointer-events-none opacity-20 bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />

      <main className="relative z-10 max-w-[860px] mx-auto px-6 pt-24 pb-32">
        {/* Tag-filter notice (only when filtering). Replaces the old "FIELD
            NOTES" page header — under the editorial design the hero IS the
            page header. */}
        {tag && (
          <header className="mb-12">
            <p className="text-xs font-mono tracking-widest uppercase text-slate-500">
              Filtering by <span className="text-sky-400">#{tag}</span> ·{' '}
              <Link to="/blog" className="hover:text-white transition">Clear filter</Link>
            </p>
          </header>
        )}

        {filtered.length === 0 || !hero ? (
          <p className="py-20 text-center font-mono text-xs uppercase tracking-widest text-slate-600">
            No posts in this stream yet.
          </p>
        ) : (
          <>
            <HeroEntry post={hero} isFiltered={Boolean(tag)} />

            {rest.length > 0 && (
              <>
                <div className="flex items-center gap-4 mb-8">
                  <span className="font-mono text-[10px] tracking-[0.3em] uppercase text-slate-500">
                    Earlier
                  </span>
                  <div className="flex-1 h-px bg-white/5" />
                  <span className="font-mono text-[10px] tracking-[0.3em] uppercase text-slate-700">
                    {rest.length}
                  </span>
                </div>
                <ul>
                  {rest.map((p) => (
                    <ArchiveRow key={p.slug} post={p} />
                  ))}
                </ul>
              </>
            )}
          </>
        )}

        <footer className="mt-32 pt-12">
          <div className="font-mono tracking-[0.3em] uppercase text-[10px] text-slate-700">
            yanqing.app
          </div>
        </footer>
      </main>
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/*  HERO ENTRY — latest piece (or first match in tag view)                    */
/* -------------------------------------------------------------------------- */

interface HeroProps {
  post: BlogPost;
  isFiltered: boolean;
}

const HeroEntry: React.FC<HeroProps> = ({ post, isFiltered }) => {
  const { frontmatter, slug, readingMinutes } = post;
  const year = new Date(frontmatter.publishedAt).getFullYear();
  const accent = getYearAccent(year);
  const heroSrc = frontmatter.hero?.src ??
    `https://picsum.photos/seed/${encodeURIComponent(slug)}/1200/800`;

  return (
    <Link to={`/blog/${slug}`} className="group block mb-24">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-8 md:gap-10 items-start">
        <div className="md:col-span-7 order-2 md:order-1">
          {/* Meta ABOVE title — year · date · min · tag, mono uppercase, sky
              accent for the tag. Reads context-first. */}
          <div className="font-mono text-[10px] tracking-[0.3em] uppercase text-slate-500 mb-5 flex items-center gap-3 flex-wrap">
            <span style={{ color: accent.hex }}>
              ● {isFiltered ? year : 'latest'}
            </span>
            <span className="opacity-40">·</span>
            <span>{formatPostDate(frontmatter.publishedAt)}</span>
            <span className="opacity-40">·</span>
            <span>{readingMinutes} min</span>
            {frontmatter.tags[0] && (
              <>
                <span className="opacity-40">·</span>
                <span className="text-sky-400/80">{frontmatter.tags[0]}</span>
              </>
            )}
          </div>
          <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold tracking-tight text-white leading-[1.05] mb-5 group-hover:text-sky-300 transition-colors">
            {frontmatter.title}
          </h1>
          <p className="text-base md:text-lg leading-relaxed text-slate-400 mb-7">
            {frontmatter.description}
          </p>
          <span className="inline-flex items-center gap-2 font-mono text-[11px] tracking-[0.3em] uppercase text-sky-400 group-hover:text-sky-300 transition-colors">
            Read piece <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
          </span>
        </div>
        <div className="md:col-span-5 order-1 md:order-2">
          <div className="aspect-[4/5] rounded-xl overflow-hidden border border-white/10 bg-slate-900 group-hover:border-sky-400/30 transition-colors">
            <img
              src={heroSrc}
              alt={frontmatter.hero?.alt ?? ''}
              className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-700"
            />
          </div>
        </div>
      </div>
    </Link>
  );
};

/* -------------------------------------------------------------------------- */
/*  ARCHIVE ROW — rich list under the hero                                    */
/* -------------------------------------------------------------------------- */

interface RowProps {
  post: BlogPost;
}

/**
 * 80x80 thumbnail (left) · meta-above-title · 2-line excerpt. Hairline divider
 * underneath. Spec from Gemini 3.1 Pro consult.
 */
const ArchiveRow: React.FC<RowProps> = ({ post }) => {
  const { frontmatter, slug, readingMinutes } = post;
  const year = new Date(frontmatter.publishedAt).getFullYear();
  const accent = getYearAccent(year);
  const thumbSrc = frontmatter.hero?.src ??
    `https://picsum.photos/seed/${encodeURIComponent(slug)}/200/200`;

  return (
    <li className="group">
      <Link
        to={`/blog/${slug}`}
        className="flex gap-5 py-6 border-b border-white/5 hover:border-sky-400/30 transition-colors"
      >
        {/* 80x80 thumbnail — hover scale inside an overflow-hidden wrapper so
            the image grows but the row stays put. */}
        <div className="w-20 h-20 shrink-0 overflow-hidden rounded-md border border-white/10 group-hover:border-white/20 transition-colors bg-slate-900">
          <img
            src={thumbSrc}
            alt={frontmatter.hero?.alt ?? ''}
            loading="lazy"
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          />
        </div>

        <div className="flex-1 min-w-0 flex flex-col gap-1.5">
          {/* Meta row ABOVE the title — date-first, consistent with hero. */}
          <div className="font-mono text-[10px] tracking-[0.25em] uppercase text-slate-500 flex items-center gap-2.5 flex-wrap">
            <span style={{ color: accent.hex }}>{year}</span>
            <span className="opacity-40">·</span>
            <span>{formatPostDateShort(frontmatter.publishedAt)}</span>
            <span className="opacity-40">·</span>
            <span>{readingMinutes} min</span>
            {frontmatter.tags[0] && (
              <>
                <span className="opacity-40">·</span>
                <span className="text-sky-400/80">{frontmatter.tags[0]}</span>
              </>
            )}
          </div>

          {/* Title — 18px semibold, slate-200 → sky-400 on hover. 2-line clamp
              so a long title doesn't blow the row out vertically. */}
          <h3 className="text-[18px] leading-snug font-semibold text-slate-200 group-hover:text-sky-400 transition-colors line-clamp-2">
            {frontmatter.title}
          </h3>

          {/* 2-line excerpt — enough context to justify a click without
              resurrecting the magazine card bulk. */}
          <p className="text-sm leading-relaxed text-slate-400 line-clamp-2">
            {frontmatter.description}
          </p>
        </div>
      </Link>
    </li>
  );
};

export default BlogIndexPage;
