import React, { useEffect, useRef, useState } from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import { Share2, X as XIcon, Link2, Calendar } from 'lucide-react';
import {
  formatPostDate,
  formatPostDateShort,
  getPostBySlug,
  getRelatedPosts,
  getYearAccent,
} from '../../lib/blog/mdx';
import type { BlogPost } from '../../lib/blog/mdx';
import BlogHelmet from './BlogHelmet';

// Inline LinkedIn SVG (lucide's `Linkedin` brand icon is deprecated)
const LinkedinIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
    <path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.94v5.67H9.37V9h3.41v1.56h.05c.47-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29zM5.34 7.43a2.06 2.06 0 110-4.13 2.06 2.06 0 010 4.13zM3.56 20.45h3.55V9H3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.45C23.2 24 24 23.23 24 22.28V1.72C24 .77 23.2 0 22.22 0z" />
  </svg>
);

/**
 * BlogPostPage — hero-2-medium-classic-faithful design.
 *
 * Layout:
 *   [progress bar]
 *   [title + description]
 *   [author chip + meta + Share button — single row]
 *   [LARGE 16:9 hero image with caption]
 *   [drop-cap body with TOC right-rail + share-the-quote popover]
 *   [tags]
 *   [consulting CTA]
 *   [Read Next trio]
 *
 * No top nav (left sidebar handles all navigation).
 * No heart/comment/bookmark — share is the only engagement action.
 * No author bio block, no "Write a response" textarea (deferred to Phase 2 if ever).
 */
const BlogPostPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const post = slug ? getPostBySlug(slug) : undefined;
  if (!post) {
    return <Navigate to="/blog" replace />;
  }
  return <ArticleShell post={post} />;
};

interface ShellProps {
  post: BlogPost;
}

const ArticleShell: React.FC<ShellProps> = ({ post }) => {
  const { frontmatter, Component, readingMinutes } = post;
  const articleRef = useRef<HTMLElement>(null);
  const related = getRelatedPosts(post.slug, 3);
  const publishedYear = new Date(frontmatter.publishedAt).getFullYear();
  const yearAccent = getYearAccent(publishedYear);
  const url = `https://yanqing.app/blog/${post.slug}`;

  // ------- Reading-progress bar -------
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    const onScroll = () => {
      const h = document.documentElement;
      const st = h.scrollTop || document.body.scrollTop;
      const sh = h.scrollHeight - h.clientHeight;
      setProgress(sh > 0 ? Math.min(1, st / sh) : 0);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // ------- Auto-derived TOC + scrollspy -------
  const [toc, setToc] = useState<Array<{ id: string; level: 2 | 3; text: string }>>([]);
  const [activeHeadingId, setActiveHeadingId] = useState<string>('');
  useEffect(() => {
    if (!articleRef.current) return;
    const headings = Array.from(
      articleRef.current.querySelectorAll('h2[id], h3[id]')
    ) as HTMLHeadingElement[];
    setToc(
      headings.map((h) => ({
        id: h.id,
        level: (h.tagName === 'H3' ? 3 : 2) as 2 | 3,
        text: h.textContent ?? '',
      }))
    );
    if (headings.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length > 0) setActiveHeadingId(visible[0].target.id);
      },
      { rootMargin: '0px 0px -70% 0px', threshold: [0, 1] }
    );
    headings.forEach((h) => observer.observe(h));
    return () => observer.disconnect();
  }, [post.slug]);

  // ------- Share-the-quote popover -------
  const [highlight, setHighlight] = useState<{ text: string; x: number; y: number } | null>(null);
  useEffect(() => {
    const onSelect = () => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed) {
        setHighlight(null);
        return;
      }
      const text = sel.toString().trim();
      if (text.length < 12 || text.length > 280) {
        setHighlight(null);
        return;
      }
      if (!articleRef.current?.contains(sel.anchorNode)) {
        setHighlight(null);
        return;
      }
      const range = sel.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      setHighlight({
        text,
        x: rect.left + rect.width / 2 + window.scrollX,
        y: rect.top + window.scrollY - 12,
      });
    };
    document.addEventListener('selectionchange', onSelect);
    return () => document.removeEventListener('selectionchange', onSelect);
  }, []);

  const buildShareUrl = (network: 'x' | 'linkedin', text: string): string => {
    if (network === 'x') {
      return `https://twitter.com/intent/tweet?text=${encodeURIComponent(`"${text}" — `)}&url=${encodeURIComponent(url)}&via=yanqing_j`;
    }
    return `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`;
  };

  const onShare = () => {
    if (typeof navigator === 'undefined') return;
    const nav = navigator as Navigator & {
      share?: (data: { title?: string; text?: string; url?: string }) => Promise<void>;
    };
    if (nav.share) {
      nav.share({ title: frontmatter.title, text: frontmatter.description, url })
        .catch(() => { /* user dismissed */ });
    } else if (nav.clipboard) {
      nav.clipboard.writeText(url);
    }
  };

  return (
    <div className="relative min-h-screen bg-slate-950 text-gray-300 selection:bg-sky-500/30">
      <BlogHelmet post={post} />

      {/* Reading-progress bar (top) */}
      <div className="fixed top-0 left-0 right-0 h-0.5 bg-white/5 z-[110]">
        <div
          className="h-full bg-gradient-to-r from-sky-400 to-sky-500 origin-left transition-transform duration-75"
          style={{ transform: `scaleX(${progress})` }}
        />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-12 pt-20 pb-12">
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,720px)_minmax(0,1fr)] gap-16">
          <article ref={articleRef} className="max-w-[68ch] mx-auto lg:mx-0 w-full">
            {/* === Title block (Medium-classic: title FIRST, then hero) === */}
            <header className="mb-8">
              <div className="h-px w-24 bg-sky-500 mb-6" />
              <p className="text-sky-500 font-mono text-xs tracking-[0.4em] uppercase mb-5">
                {frontmatter.tags[0] ? `Field Notes · ${frontmatter.tags[0]}` : 'Field Notes'}
              </p>
              <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-white leading-[1.1] mb-6">
                {frontmatter.title}
              </h1>
              <p className="text-xl text-slate-400 leading-relaxed">{frontmatter.description}</p>
            </header>

            {/* === Author + Share row (Share inlined; no heart/comment/bookmark) === */}
            <div className="flex flex-wrap items-center gap-4 mb-12 pb-8 border-b border-white/5">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-sky-400 to-purple-600 flex items-center justify-center text-white font-bold shadow-lg flex-shrink-0">
                YJ
              </div>
              <div className="flex flex-col flex-grow min-w-0">
                <div className="text-white font-medium text-sm">Yanqing Jiang</div>
                <div className="flex items-center text-slate-400 text-sm mt-1 gap-2 flex-wrap">
                  <span>{readingMinutes} min read</span>
                  <span className="w-1 h-1 rounded-full bg-slate-600" />
                  <span>{formatPostDate(frontmatter.publishedAt)}</span>
                  <span className="w-1 h-1 rounded-full bg-slate-600" />
                  <div className="flex gap-2">
                    {frontmatter.tags.slice(0, 3).map((tag) => (
                      <Link
                        key={tag}
                        to={`/blog/tag/${tag}`}
                        className="px-2 py-0.5 bg-white/5 rounded text-xs font-mono hover:bg-sky-500/20 hover:text-sky-300 transition-colors"
                      >
                        {tag}
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={onShare}
                className="flex items-center gap-2 px-3 py-2 rounded-full hover:bg-white/5 text-slate-400 hover:text-white transition-colors flex-shrink-0"
                title="Share"
              >
                <Share2 className="w-5 h-5" />
                <span className="text-xs font-mono uppercase tracking-wider">Share</span>
              </button>
            </div>

            {/*
              Hero image is intentionally NOT rendered here.
              For mirrored Medium posts, the article body's first <img> already
              serves as the lede image — rendering frontmatter.hero would
              duplicate it. The hero still drives the /blog index thumbnail,
              the OG/Twitter card, and the JSON-LD Article.image.
            */}

            {/* === Body (drop cap on first paragraph) === */}
            <div
              className="prose prose-invert prose-lg max-w-none
                prose-headings:tracking-tight prose-headings:text-white
                prose-h2:text-2xl prose-h2:font-bold prose-h2:mt-12 prose-h2:mb-5
                prose-h3:text-xl prose-h3:font-semibold prose-h3:mt-8 prose-h3:mb-4
                prose-p:text-gray-300 prose-p:leading-[1.8]
                prose-strong:text-white
                prose-a:text-sky-400 prose-a:no-underline hover:prose-a:text-sky-300 hover:prose-a:underline
                prose-blockquote:border-l-2 prose-blockquote:border-sky-500 prose-blockquote:bg-sky-500/5
                prose-blockquote:rounded-r-xl prose-blockquote:px-6 prose-blockquote:py-1
                prose-blockquote:text-white prose-blockquote:font-medium prose-blockquote:not-italic
                prose-pre:bg-slate-900/60 prose-pre:backdrop-blur prose-pre:border prose-pre:border-white/5 prose-pre:rounded-xl
                prose-code:before:content-none prose-code:after:content-none
                prose-code:bg-slate-900/60 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-sky-300 prose-code:font-normal
                prose-img:rounded-2xl prose-img:border prose-img:border-white/5
                first-of-type:prose-p:first-letter:font-serif first-of-type:prose-p:first-letter:text-7xl
                first-of-type:prose-p:first-letter:font-black first-of-type:prose-p:first-letter:float-left
                first-of-type:prose-p:first-letter:mr-3 first-of-type:prose-p:first-letter:leading-[0.85]
                first-of-type:prose-p:first-letter:text-white"
            >
              <Component />
            </div>

            {/* === Tags (clickable; route to filtered index) === */}
            <footer className="mt-16 pt-8 border-t border-white/5 space-y-6">
              <div className="flex gap-2 flex-wrap">
                {frontmatter.tags.map((tag) => (
                  <Link
                    key={tag}
                    to={`/blog/tag/${tag}`}
                    className="bg-slate-800/60 text-gray-300 hover:bg-sky-500/20 hover:text-sky-300 transition rounded-full px-3 py-1 text-xs font-medium"
                  >
                    {tag}
                  </Link>
                ))}
              </div>

              {/* Originally on Medium — UX courtesy for readers who prefer
                  Medium's reader. Does NOT change SEO: canonical stays local,
                  and the link uses default rel (no nofollow) since this is a
                  syndication relationship we want crawlers to understand. */}
              {frontmatter.mediumUrl && (
                <p className="text-xs font-mono uppercase tracking-widest text-slate-500">
                  Originally published on{' '}
                  <a
                    href={frontmatter.mediumUrl}
                    target="_blank"
                    rel="noopener"
                    className="text-sky-400 hover:text-sky-300 underline-offset-4 hover:underline"
                  >
                    Medium
                  </a>
                  . This copy is canonical.
                </p>
              )}
            </footer>

            {/* === Consulting CTA (booking-glow keyframe defined in globals.css) === */}
            <div className="mt-16 p-8 bg-sky-500/10 backdrop-blur-xl border border-sky-500/40 rounded-2xl animate-booking-glow text-center">
              <h3 className="text-xl font-bold text-white mb-3">Scaling agentic workflows in production?</h3>
              <p className="text-slate-300 mb-6 max-w-md mx-auto">
                I help enterprise teams design and deploy multi-agent systems that actually work in production.
              </p>
              <Link
                to="/consult"
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-sky-500/20 border border-sky-400 rounded-full text-white font-semibold hover:bg-sky-500/40 transition"
              >
                <Calendar className="w-4 h-4" />
                Book a Consulting Session
              </Link>
            </div>
          </article>

          {/* === Sticky right-rail TOC === */}
          <aside className="hidden lg:block">
            <div className="sticky top-24 space-y-8">
              {toc.length > 0 && (
                <div>
                  <h4 className="text-xs font-mono tracking-[0.4em] uppercase text-sky-500 mb-6">Contents</h4>
                  <ul className="space-y-3 text-sm font-medium text-slate-400">
                    {toc.map((entry) => (
                      <li key={entry.id} className={entry.level === 3 ? 'pl-4' : ''}>
                        <a
                          href={`#${entry.id}`}
                          className={`transition pl-4 border-l-2 ${
                            activeHeadingId === entry.id
                              ? 'text-sky-300 border-sky-500'
                              : 'border-transparent hover:text-white'
                          }`}
                        >
                          {entry.text}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Year accent footer (single subtle marker — no share rail since Share is inline above) */}
              <div className="pt-8 border-t border-white/5 flex items-center gap-3 text-xs font-mono uppercase tracking-widest text-slate-600">
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ backgroundColor: yearAccent.hex, boxShadow: `0 0 8px ${yearAccent.rgba}` }}
                />
                <span style={{ color: yearAccent.hex }}>{publishedYear}</span>
              </div>
            </div>
          </aside>
        </div>
      </div>

      {/* === Read Next trio === */}
      {related.length > 0 && (
        <section className="relative z-10 max-w-7xl mx-auto px-6 lg:px-12 pb-32 border-t border-white/5 pt-20">
          <header className="mb-12 max-w-[68ch] mx-auto lg:mx-0">
            <div className="h-px w-24 bg-sky-500 mb-5" />
            <p className="text-sky-500 font-mono text-xs tracking-[0.4em] uppercase">Read Next</p>
          </header>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {related.map((p) => {
              const accent = getYearAccent(new Date(p.frontmatter.publishedAt).getFullYear());
              return (
                <Link
                  key={p.slug}
                  to={`/blog/${p.slug}`}
                  className="group block bg-slate-900/10 backdrop-blur-2xl border border-white/5 rounded-2xl p-6 transition duration-500 hover:border-white/20 hover:shadow-[0_0_30px_rgba(56,189,248,0.1)] hover:-translate-y-1"
                >
                  <div className="flex items-center gap-2 mb-5">
                    <div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{
                        backgroundColor: accent.hex,
                        boxShadow: `0 0 12px ${accent.rgba}`,
                      }}
                    />
                    <span
                      className="text-[10px] font-mono tracking-[0.3em] uppercase"
                      style={{ color: accent.hex }}
                    >
                      {new Date(p.frontmatter.publishedAt).getFullYear()}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-white leading-snug mb-3 group-hover:text-sky-300 transition">
                    {p.frontmatter.title}
                  </h3>
                  <p className="text-sm text-slate-400 leading-relaxed line-clamp-2 mb-6">
                    {p.frontmatter.description}
                  </p>
                  <div className="flex items-center gap-3 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                    <span>{formatPostDateShort(p.frontmatter.publishedAt)}</span>
                    <span className="opacity-40">·</span>
                    <span>{p.readingMinutes} min</span>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>
      )}

      {/* === Share-the-quote popover === */}
      {highlight && (
        <div
          role="dialog"
          aria-label="Share quote"
          style={{
            position: 'absolute',
            top: highlight.y,
            left: highlight.x,
            transform: 'translate(-50%, -100%)',
          }}
          className="z-[200] flex items-center gap-4 px-4 py-2 bg-slate-900/95 backdrop-blur border border-white/10 rounded-lg shadow-[0_0_30px_rgba(14,165,233,0.2)] text-xs font-mono uppercase tracking-wider"
        >
          <span className="text-sky-400 font-bold">Share Quote</span>
          <a
            href={buildShareUrl('x', highlight.text)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-300 hover:text-white"
            aria-label="Share on X"
          >
            <XIcon className="w-3.5 h-3.5" />
          </a>
          <a
            href={buildShareUrl('linkedin', highlight.text)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-300 hover:text-white"
            aria-label="Share on LinkedIn"
          >
            <LinkedinIcon className="w-3.5 h-3.5" />
          </a>
          <button
            type="button"
            onClick={() => navigator.clipboard.writeText(`"${highlight.text}" — ${url}`)}
            className="text-slate-300 hover:text-white"
            aria-label="Copy quote"
          >
            <Link2 className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};

export default BlogPostPage;
