import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import ProjectMedia from './ProjectMedia';
import type { Project, ProjectYear } from '../types';
import {
    DEFAULT_OG_IMAGE,
    DEFAULT_THEME_COLOR,
    DEFAULT_TWITTER_HANDLE,
    LANDING_NAV,
    LANDING_SEO,
    SITE_NAME,
} from '../constants/seo';
import { buildLandingSchemas, buildPersonSchema } from '../constants/structuredData';

/*
 * Landing refactor Phase 1 — the commercial front door.
 * Locked visual system: near-black charcoal, bone off-white grotesk type,
 * a single vermilion accent, generous whitespace, no stock imagery, no photo.
 * Extends hero-bold-typographic.html; responsive translation of the fixed mock.
 */

// Design tokens live inline as Tailwind arbitrary values so the whole route
// reads as one system: bg #12110F · surface #191816 · bone #F1EADF ·
// muted #A8A096 · hairline #37332E · vermilion #F04A32 (hover #D63B27).

// --- Motion primitive ------------------------------------------------------
// Fade-up entrance, once, that respects prefers-reduced-motion by rendering
// the final layout immediately (and stays crawlable/visible without JS).
const Reveal: React.FC<{ children: React.ReactNode; className?: string; delay?: number }> = ({
    children,
    className,
    delay = 0,
}) => {
    const reduce = useReducedMotion();
    if (reduce) return <div className={className}>{children}</div>;
    return (
        <motion.div
            className={className}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1], delay }}
        >
            {children}
        </motion.div>
    );
};

// Fires once when the element scrolls into view. Reduced-motion (or no
// IntersectionObserver) resolves to `true` immediately so the lit/final state
// is shown without waiting for a scroll.
const useInViewOnce = <T extends HTMLElement>(threshold = 0.35): [React.RefObject<T | null>, boolean] => {
    const ref = useRef<T>(null);
    const reduce = useReducedMotion();
    const [inView, setInView] = useState(false);
    useEffect(() => {
        if (reduce || typeof IntersectionObserver === 'undefined') {
            setInView(true);
            return;
        }
        const el = ref.current;
        if (!el) return;
        const obs = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setInView(true);
                    obs.disconnect();
                }
            },
            { threshold }
        );
        obs.observe(el);
        return () => obs.disconnect();
    }, [reduce, threshold]);
    return [ref, inView];
};

// --- Small building blocks -------------------------------------------------
const PrimaryCTA: React.FC<{ to: string; children: React.ReactNode; onClick?: () => void }> = ({ to, children, onClick }) => (
    <Link
        to={to}
        onClick={onClick}
        className="group inline-flex items-center gap-2 rounded-[4px] bg-[#F04A32] px-6 py-3.5 text-[15px] font-semibold text-[#12110F] transition-colors duration-200 hover:bg-[#D63B27] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#F04A32]"
    >
        {children}
        <span className="transition-transform duration-200 group-hover:translate-x-1">→</span>
    </Link>
);

// --- Animated proof-rail stat ----------------------------------------------
// Prerenders the final figure (crawlable, no-JS visible); on the client the
// number counts up from 0 the first time it scrolls into view, staggered per
// column. The non-numeric unit (+, M) pops in vermilion once the count lands,
// echoing the hero period. Clicking replays the count. Reduced motion: static.
const easeOutExpo = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

const AnimatedStat: React.FC<{ n: string; l: string; index: number }> = ({ n, l, index }) => {
    const reduce = useReducedMotion();
    const [ref, inView] = useInViewOnce<HTMLDivElement>(0.5);
    // '4,000+' → ['', '4,000', '+'] · '$150M' → ['$', '150', 'M']
    const [, prefix = '', digits = '0', suffix = ''] = n.match(/^([^\d]*)([\d,]+)([^\d]*)$/) ?? [];
    const target = parseInt(digits.replace(/,/g, ''), 10);
    const [value, setValue] = useState(target);
    const [done, setDone] = useState(true);
    const rafRef = useRef(0);

    const play = React.useCallback(
        (delay: number) => {
            cancelAnimationFrame(rafRef.current);
            setValue(0);
            setDone(false);
            const start = performance.now() + delay;
            const duration = 1400;
            const tick = (now: number) => {
                const t = Math.min(Math.max((now - start) / duration, 0), 1);
                setValue(Math.round(target * easeOutExpo(t)));
                if (t < 1) {
                    rafRef.current = requestAnimationFrame(tick);
                } else {
                    setDone(true);
                }
            };
            rafRef.current = requestAnimationFrame(tick);
        },
        [target]
    );

    // First play, staggered per column; SSR/no-JS keeps the static figure.
    useEffect(() => {
        if (reduce || !inView) return;
        play(index * 150);
        return () => cancelAnimationFrame(rafRef.current);
    }, [reduce, inView, index, play]);

    return (
        <div ref={ref} onClick={() => !reduce && play(0)} className={reduce ? undefined : 'cursor-pointer select-none'}>
            <dt className="text-[40px] font-black tracking-[-0.03em] text-[#F1EADF] sm:text-[48px]">
                {prefix}
                {value.toLocaleString('en-US')}
                {suffix && (
                    <span
                        className="inline-block text-[#F04A32] transition-[opacity,transform] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]"
                        style={done ? undefined : { opacity: 0, transform: 'translateY(0.15em) scale(0.6)' }}
                    >
                        {suffix}
                    </span>
                )}
            </dt>
            <dd className="mt-1 text-[15px] text-[#A8A096]">{l}</dd>
        </div>
    );
};

interface LandingPageFlowProps {
    projectData: ProjectYear[];
    onSelectProject: (project: Project) => void;
}

const LandingPageFlow: React.FC<LandingPageFlowProps> = ({ projectData, onSelectProject }) => {
    // Pre-AI heading lights up (muted → bone) the first time it scrolls in.
    const [preAiRef, preAiLit] = useInViewOnce<HTMLHeadingElement>(0.5);
    // "The Work" carousel: every visible year group, in chronology order.
    const displayYears = useMemo(
        () => projectData.filter((g) => !g.hiddenOnLanding),
        [projectData]
    );
    const allProjects = useMemo(() => displayYears.flatMap((y) => y.projects), [displayYears]);
    // Pre-AI era pulled out by label/year (mirrors the legacy landing memo).
    const preAiGroup = useMemo(
        () =>
            projectData.find(
                (g) => g.label?.toLowerCase().includes('pre-ai') || g.year === 2021
            ),
        [projectData]
    );
    const preAiProjects = preAiGroup?.projects ?? [];
    // SiteNavigation schema mirrors the visible commercial nav, not the legacy
    // project chronology (which stays in WebSite.hasPart via buildWebsiteSchema).
    const landingSchemas = useMemo(
        () => buildLandingSchemas(allProjects, LANDING_NAV),
        [allProjects]
    );
    const personSchema = useMemo(() => buildPersonSchema(), []);
    const landingKeywords = useMemo(() => LANDING_SEO.keywords.join(', '), []);

    return (
        <div className="min-h-screen bg-[#12110F] text-[#F1EADF] antialiased" style={{ colorScheme: 'dark' }}>
            <Helmet>
                <title>{LANDING_SEO.title}</title>
                <meta name="description" content={LANDING_SEO.description} />
                <meta name="keywords" content={landingKeywords} />
                <meta name="author" content={LANDING_SEO.author} />
                <meta name="robots" content="index, follow" />
                <link rel="canonical" href={LANDING_SEO.canonical} />
                <meta property="og:type" content="website" />
                <meta property="og:title" content={LANDING_SEO.ogTitle} />
                <meta property="og:description" content={LANDING_SEO.ogDescription} />
                <meta property="og:url" content={LANDING_SEO.canonical} />
                <meta property="og:site_name" content={SITE_NAME} />
                <meta property="og:image" content={DEFAULT_OG_IMAGE} />
                <meta property="og:image:width" content="1200" />
                <meta property="og:image:height" content="630" />
                <meta property="og:image:alt" content="AI agent system builder." />
                <meta name="twitter:card" content="summary_large_image" />
                <meta name="twitter:site" content={DEFAULT_TWITTER_HANDLE} />
                <meta name="twitter:title" content={LANDING_SEO.ogTitle} />
                <meta name="twitter:description" content={LANDING_SEO.ogDescription} />
                <meta name="twitter:image" content={DEFAULT_OG_IMAGE} />
                <meta name="theme-color" content={DEFAULT_THEME_COLOR} />
                <script type="application/ld+json">{JSON.stringify(personSchema)}</script>
                {landingSchemas.map((schema, index) => (
                    <script key={`landing-schema-${index}`} type="application/ld+json">
                        {JSON.stringify(schema)}
                    </script>
                ))}
            </Helmet>

            {/* Hero clip-reveal — text is always in the DOM (crawlable, no-JS
                visible); the animation only runs when motion is allowed. */}
            <style>{`
                .hero-h1 .hero-line { display: block; }
                @media (prefers-reduced-motion: no-preference) {
                    /* Clip box needs vertical breathing room: the reveal wants overflow
                       hidden, but line-height 0.86 crops ascenders (top) and descenders
                       (g/y, bottom). Pad both edges and cancel the padding with negative
                       margins so leading stays identically tight. */
                    .hero-h1 .hero-line { overflow: hidden; padding-top: 0.15em; padding-bottom: 0.22em; margin-top: -0.15em; margin-bottom: -0.22em; }
                    .hero-h1 .hero-line-inner {
                        display: inline-block;
                        animation: heroClipReveal 800ms cubic-bezier(0.22, 1, 0.36, 1) both;
                    }
                    .hero-h1 .hero-line:nth-child(2) .hero-line-inner { animation-delay: 120ms; }
                    .hero-h1 .hero-period {
                        display: inline-block;
                        animation: heroPeriodIn 320ms ease both;
                        animation-delay: 820ms;
                    }
                    @keyframes heroClipReveal { from { transform: translateY(105%); } to { transform: translateY(0); } }
                    @keyframes heroPeriodIn { from { opacity: 0; } to { opacity: 1; } }
                }
                .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
                .hide-scrollbar::-webkit-scrollbar { display: none; }
                @media (prefers-reduced-motion: no-preference) {
                    .cta-pulse .cta-arrow { animation: ctaArrowNudge 3.4s ease-in-out infinite; }
                    @keyframes ctaArrowNudge {
                        0%, 86%, 100% { transform: translateX(0); }
                        90% { transform: translateX(3px); }
                        94% { transform: translateX(0); }
                    }
                }
            `}</style>

            {/* Nav lives in the shared top header (SidebarV2 in App.tsx Layout):
                "Yanqing Jiang" returns home, "Menu" opens the Projects/Blog drawer. */}
            <main id="top">
                {/* ── Section 1 — Hero + proof rail ───────────────────── */}
                <section className="mx-auto max-w-[1280px] px-6 pt-16 pb-24 sm:pt-20 lg:px-10 lg:pt-24 lg:pb-32">
                    <h1 className="hero-h1 font-black leading-[0.86] tracking-[-0.06em] text-[#F1EADF]" style={{ fontSize: 'clamp(52px, 12vw, 190px)' }}>
                        <span className="hero-line"><span className="hero-line-inner">AI agent</span></span>
                        <span className="hero-line"><span className="hero-line-inner">system builder<span className="hero-period text-[#F04A32]">.</span></span></span>
                    </h1>
                    <div className="mt-10">
                        <div className="grid gap-4 sm:grid-cols-3">
                            {[
                                { t: 'Enterprise workflow', d: 'Cut 90% of the work time with an AI agent workflow — from the database to the delivered PowerPoint or dashboard.' },
                                { t: 'Personal Agent OS', d: 'A personal agent that remembers how you work, or an agent-managed personal website.' },
                                { t: 'Hands on training', d: 'Learn the agentic stack on your own toolset — GitHub Copilot, Claude Code, Codex, Pi, OpenClaw, Hermes.' },
                            ].map((o) => (
                                <div key={o.t} className="rounded-[6px] border border-[#37332E] bg-[#191816]/40 p-5">
                                    <h2 className="text-[17px] font-bold leading-snug text-[#F1EADF]">{o.t}</h2>
                                    <p className="mt-2 text-[14px] leading-[1.5] text-[#A8A096]">{o.d}</p>
                                </div>
                            ))}
                        </div>
                        <div className="mt-7">
                            <PrimaryCTA to="/consult">Start a booking</PrimaryCTA>
                        </div>
                    </div>

                    {/* Proof rail — numbers count up on first scroll-in; the unit
                        marks (+, M) pop in vermilion after the count, echoing the
                        hero period. Click a number to replay its count. */}
                    <div className="mt-16 border-t border-[#37332E] pt-8">
                        <dl className="grid grid-cols-2 gap-8 sm:grid-cols-3" style={{ fontVariantNumeric: 'tabular-nums' }}>
                            {[
                                { n: '4,000+', l: 'hours automated' },
                                { n: '$150M', l: 'in decisions influenced' },
                                { n: '4', l: 'full-time AI engineers' },
                            ].map((m, i) => (
                                <AnimatedStat key={m.l} n={m.n} l={m.l} index={i} />
                            ))}
                        </dl>
                    </div>
                </section>

                {/* ── Section 2 — The Work (vertical staggered rows) ──── */}
                <WorkCarousel displayYears={displayYears} onSelect={onSelectProject} />

                {/* ── Section 2b — Pre-AI projects ────────────────────── */}
                {preAiProjects.length > 0 && (
                    <section id="pre-ai" className="border-t border-[#37332E]">
                        <div className="mx-auto max-w-[1280px] px-6 py-24 lg:px-10 lg:py-32">
                            <h2
                                ref={preAiRef}
                                data-lit={preAiLit}
                                className={`font-bold tracking-[-0.03em] transition-colors duration-[600ms] ease-out ${preAiLit ? 'text-[#F1EADF]' : 'text-[#A8A096]/60'}`}
                                style={{ fontSize: 'clamp(28px, 4vw, 44px)' }}
                            >
                                Pre-AI projects<span className={`transition-colors duration-[600ms] ease-out ${preAiLit ? 'text-[#F04A32]' : 'text-transparent'}`}>.</span>
                            </h2>
                            <div className="mt-12">
                                <CarouselTrack>
                                    {preAiProjects.map((project) => (
                                        <ProjectCard
                                            key={project.id}
                                            project={project}
                                            year={preAiGroup?.year}
                                            onSelect={onSelectProject}
                                            variant="pre"
                                        />
                                    ))}
                                </CarouselTrack>
                            </div>
                        </div>
                    </section>
                )}

                {/* ── Section 7 — Final CTA ───────────────────────────── */}
                <section className="border-t border-[#37332E] bg-[#191816]">
                    <div className="mx-auto max-w-[1280px] px-6 py-28 text-center lg:px-10 lg:py-36">
                        <Reveal>
                            <h2 className="mx-auto max-w-[16ch] font-black tracking-[-0.045em] text-[#F1EADF]" style={{ fontSize: 'clamp(40px, 7vw, 96px)' }}>
                                Start with the problem<span className="text-[#F04A32]">.</span>
                            </h2>
                        </Reveal>
                        <p className="mx-auto mt-8 max-w-[52ch] text-[18px] leading-[1.5] text-[#A8A096]">
                            Tell me what is slow, manual, fragmented, or impossible today. Add the context up front
                            and the first conversation starts with your problem — not introductions.
                        </p>
                        <div className="mt-12 flex flex-col items-center justify-center gap-5 sm:flex-row">
                            <PrimaryCTA to="/consult">Start a project</PrimaryCTA>
                            <a href="#work" className="text-[15px] font-semibold text-[#A8A096] transition-colors hover:text-[#F1EADF]">
                                See the work
                            </a>
                        </div>
                        <p className="mx-auto mt-10 text-[13px] text-[#A8A096]">
                            No sign-in. Prices and availability are visible.
                        </p>
                    </div>
                </section>

                {/* ── Section 8 — Footer ──────────────────────────────── */}
                <footer className="border-t border-[#37332E]">
                    <div className="mx-auto max-w-[1280px] px-6 py-16 lg:px-10">
                        <div className="grid gap-10 md:grid-cols-[1.5fr_1fr_1fr]">
                            <div>
                                <p className="text-[18px] font-bold text-[#F1EADF]">
                                    Yanqing Jiang — AI agent system builder<span className="text-[#F04A32]">.</span>
                                </p>
                            </div>
                            <div className="space-y-3">
                                <p className="text-[12px] uppercase tracking-[0.2em] text-[#A8A096]">Offers</p>
                                <Link to="/consult?path=enterprise" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">Enterprise workflow</Link>
                                <Link to="/consult?path=individual" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">Personal Agent OS</Link>
                                <Link to="/consult?path=training" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">Hands on training</Link>
                            </div>
                            <div className="space-y-3">
                                <p className="text-[12px] uppercase tracking-[0.2em] text-[#A8A096]">More</p>
                                <a href="#work" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">The Work</a>
                                <Link to="/consult" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">Start a project</Link>
                                <a href="https://www.linkedin.com/in/jiangyanqing/" target="_blank" rel="noopener noreferrer" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">LinkedIn</a>
                                <a href="https://github.com/Yanqing-Jiang" target="_blank" rel="noopener noreferrer" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">GitHub</a>
                            </div>
                        </div>
                        <div className="mt-14 border-t border-[#37332E] pt-8">
                            <p className="text-[13px] text-[#A8A096]">© 2026 Yanqing Jiang. Systems should earn their keep.</p>
                        </div>
                    </div>
                </footer>
            </main>
        </div>
    );
};

// --- Cover media with CSS-drawn fallback ----------------------------------
// Renders the project cover; when no source exists, draws a flat placeholder
// (surface bg + hairline + mono label) rather than a broken image.
const CoverMedia: React.FC<{ src?: string; alt: string; className: string }> = ({ src, alt, className }) => {
    if (!src) {
        return (
            <div className={`${className} flex items-center justify-center bg-[#191816]`}>
                <span className="px-4 text-center font-mono text-[11px] uppercase tracking-[0.14em] text-[#A8A096]">{alt}</span>
            </div>
        );
    }
    return <ProjectMedia src={src} alt={alt} className={className} loading="lazy" />;
};

// --- Horizontal scroll track (dependency-light; snap + hidden scrollbar) ---
const CarouselTrack: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const ref = useRef<HTMLDivElement>(null);
    const scrollBy = (dir: number) => ref.current?.scrollBy({ left: dir * 560, behavior: 'smooth' });
    return (
        <div>
            <div className="mb-6 hidden justify-end gap-2 md:flex">
                <button
                    type="button"
                    aria-label="Scroll back"
                    onClick={() => scrollBy(-1)}
                    className="flex h-10 w-10 items-center justify-center border border-[#37332E] font-mono text-[15px] text-[#A8A096] transition-colors hover:border-[#A8A096] hover:text-[#F1EADF]"
                >
                    ←
                </button>
                <button
                    type="button"
                    aria-label="Scroll forward"
                    onClick={() => scrollBy(1)}
                    className="flex h-10 w-10 items-center justify-center border border-[#37332E] font-mono text-[15px] text-[#A8A096] transition-colors hover:border-[#A8A096] hover:text-[#F1EADF]"
                >
                    →
                </button>
            </div>
            <div
                ref={ref}
                className="hide-scrollbar flex flex-col gap-12 md:flex-row md:items-stretch md:gap-10 md:overflow-x-auto md:snap-x md:snap-mandatory md:pb-2"
            >
                {children}
            </div>
        </div>
    );
};

// --- Tag chips -------------------------------------------------------------
// Year as a leading accent chip, then each technology as its own small mono
// chip (1px hairline, surface fill) — old-card style recolored to new tokens.
const TagChips: React.FC<{ year?: number; techs: string[]; align?: 'left' | 'right' }> = ({
    year,
    techs,
    align = 'left',
}) => (
    <div className={`flex flex-wrap gap-1.5 ${align === 'right' ? 'lg:justify-end' : ''}`}>
        {year != null && (
            <span className="rounded-[3px] border border-[#F04A32]/40 bg-[#F04A32]/10 px-2 py-1 font-mono text-[10px] uppercase leading-none tracking-[0.14em] text-[#F04A32]">
                {year}
            </span>
        )}
        {techs.map((t) => (
            <span
                key={t}
                className="rounded-[3px] border border-[#37332E] bg-[#191816] px-2 py-1 font-mono text-[10px] uppercase leading-none tracking-[0.14em] text-[#A8A096]"
            >
                {t}
            </span>
        ))}
    </div>
);

// --- Project card (picture-first; flat + typographic) ----------------------
const ProjectCard: React.FC<{
    project: Project;
    year?: number;
    onSelect: (project: Project) => void;
    variant?: 'work' | 'pre';
}> = ({ project, year, onSelect, variant = 'work' }) => {
    const isPre = variant === 'pre';
    const to = project.link ?? `/project/${project.id}`;
    const techs = project.technologies.slice(0, isPre ? 2 : 3);
    return (
        <article className={`group flex w-full max-w-[600px] shrink-0 flex-col md:max-w-none md:snap-start ${isPre ? 'md:w-[320px]' : 'md:w-[420px]'}`}>
            <Link
                to={to}
                onClick={() => onSelect(project)}
                aria-label={`View ${project.title}`}
                className="block overflow-hidden rounded-[6px] border border-[#37332E] transition-[transform,border-color,box-shadow] duration-300 ease-out group-hover:-translate-y-1 group-hover:border-[#F04A32]/60 group-hover:shadow-[0_16px_40px_rgba(0,0,0,0.35)]"
            >
                <CoverMedia
                    src={project.coverUrl ?? project.imageUrl}
                    alt={project.title}
                    className="aspect-[16/10] w-full object-cover grayscale transition-[filter] duration-500 group-hover:grayscale-0"
                />
            </Link>
            <div className="mt-4">
                <TagChips year={year} techs={techs} />
                <h3 className={`mt-3 font-black leading-[1.05] tracking-[-0.03em] text-[#F1EADF] ${isPre ? 'text-[18px]' : 'text-[20px]'}`}>
                    {project.title}
                </h3>
                <p className="mt-2 line-clamp-1 text-[14px] text-[#A8A096]">
                    {project.cardDescription ?? project.description}
                </p>
                <Link
                    to={to}
                    onClick={() => onSelect(project)}
                    className="mt-3 inline-flex items-center gap-2 text-[13px] font-semibold text-[#A8A096] transition-colors group-hover:text-[#F1EADF]"
                >
                    {project.linkText ?? 'View project'}
                    <span className="text-[#F04A32] transition-transform duration-200 group-hover:translate-x-1">→</span>
                </Link>
            </div>
        </article>
    );
};

// --- Year marker (vertical flow) -------------------------------------------
// Opens each year group in the vertical timeline. Keeps the old carousel
// marker's four ingredients: giant ghost numeral, glowing vermilion node,
// faded vertical hairline, mono era label — restacked for downward reading.
const YearMarker: React.FC<{ year: number; subtitle?: string }> = ({ year, subtitle }) => (
    <div className="relative flex flex-col gap-2.5 pt-1">
        {/* Ghost oversized numeral, bleeding behind the group (scaled down) */}
        <span
            aria-hidden
            className="pointer-events-none absolute -top-6 left-0 select-none bg-gradient-to-b from-[#F1EADF]/[0.07] to-transparent bg-clip-text font-black leading-none text-transparent blur-[1px]"
            style={{ fontSize: 'clamp(4rem, 9vw, 7rem)' }}
        >
            {year}
        </span>
        {/* Glowing accent node */}
        <div className="relative z-10 h-3 w-3 rounded-full bg-[#F04A32]" style={{ boxShadow: '0 0 16px #F04A32' }} />
        {/* Vertical hairline dropping into the group */}
        <div className="relative z-10 h-9 w-px bg-gradient-to-b from-[#37332E] to-transparent" />
        {/* Mono era subtitle (prefixed with the readable year) */}
        <h3 className="relative z-10 font-mono text-[12px] uppercase tracking-[0.2em] text-[#F04A32]">
            {year} · {subtitle?.replace(/[()]/g, '') || 'Era'}
        </h3>
    </div>
);

// --- The Work row (editorial, stagger-aligned) -----------------------------
// Picture-first row: media + content in a 2-col grid on desktop, alternating
// which side the media sits on (align). Scroll-revealed via <Reveal>. Mobile
// (<lg): single column, media on top, everything left-aligned (no stagger).
const WorkRow: React.FC<{
    project: Project;
    year: number;
    align: 'left' | 'right';
    onSelect: (project: Project) => void;
}> = ({ project, year, align, onSelect }) => {
    const to = project.link ?? `/project/${project.id}`;
    const techs = project.technologies.slice(0, 3);
    const right = align === 'right';
    return (
        <Reveal>
            <div
                className={`group flex flex-col gap-4 lg:flex-row lg:items-center lg:gap-10 ${
                    right ? 'lg:flex-row-reverse' : ''
                }`}
            >
                {/* Media — small (aspect 2/1, ~44% wide on desktop), lifts + colors on hover.
                    Stacked (<lg) it caps at 600px so its absolute size stays close to the
                    desktop 44% column — no gigantic full-bleed covers at tablet widths. */}
                <Link
                    to={to}
                    onClick={() => onSelect(project)}
                    aria-label={`View ${project.title}`}
                    className="block w-full max-w-[600px] shrink-0 overflow-hidden rounded-[6px] border border-[#37332E] transition-[transform,border-color,box-shadow] duration-300 ease-out group-hover:-translate-y-1 group-hover:border-[#F04A32]/60 group-hover:shadow-[0_16px_40px_rgba(0,0,0,0.35)] lg:w-[44%] lg:max-w-none"
                >
                    <CoverMedia
                        src={project.coverUrl ?? project.imageUrl}
                        alt={project.title}
                        className="aspect-[2/1] w-full object-cover grayscale transition-[filter] duration-500 group-hover:grayscale-0"
                    />
                </Link>
                {/* Content */}
                <div className={`lg:flex-1 ${right ? 'lg:text-right' : ''}`}>
                    <TagChips year={year} techs={techs} align={right ? 'right' : 'left'} />
                    <h3 className="mt-3 font-black leading-[1.05] tracking-[-0.03em] text-[#F1EADF] text-[22px] lg:text-[26px]">
                        {project.title}
                    </h3>
                    <p className={`mt-2 max-w-[46ch] text-[15px] leading-[1.5] text-[#A8A096] ${right ? 'lg:ml-auto' : ''}`}>
                        {project.cardDescription ?? project.description}
                    </p>
                    <Link
                        to={to}
                        onClick={() => onSelect(project)}
                        className={`mt-3 inline-flex items-center gap-2 text-[13px] font-semibold text-[#A8A096] transition-colors group-hover:text-[#F1EADF] ${
                            right ? 'lg:flex-row-reverse' : ''
                        }`}
                    >
                        {project.linkText ?? 'View project'}
                        <span className="text-[#F04A32] transition-transform duration-200 group-hover:translate-x-1">→</span>
                    </Link>
                </div>
            </div>
        </Reveal>
    );
};

// --- The Work section ------------------------------------------------------
// Normal vertical scroll. Each year group opens with a <YearMarker>, then its
// projects render as stagger-aligned editorial rows (alternating left/right on
// desktop, single column on mobile). Scroll reveals respect reduced motion.
const WorkCarousel: React.FC<{
    displayYears: ProjectYear[];
    onSelect: (project: Project) => void;
}> = ({ displayYears, onSelect }) => {
    // Flatten to markers + project rows, tagging each project row's alignment so
    // the stagger alternates across the whole section (not per-year).
    const rows = useMemo(() => {
        const out: Array<
            | { kind: 'marker'; key: string; year: number; subtitle?: string }
            | { kind: 'project'; key: string; project: Project; year: number; align: 'left' | 'right' }
        > = [];
        let i = 0;
        for (const group of displayYears) {
            out.push({ kind: 'marker', key: `year-${group.year}`, year: group.year, subtitle: group.subtitle });
            for (const project of group.projects) {
                out.push({
                    kind: 'project',
                    key: project.id,
                    project,
                    year: group.year,
                    align: i % 2 === 0 ? 'left' : 'right',
                });
                i += 1;
            }
        }
        return out;
    }, [displayYears]);

    return (
        <section id="work" className="border-t border-[#37332E] bg-[#191816]">
            <div className="mx-auto max-w-[1280px] px-6 py-24 lg:px-10 lg:py-32">
                <Reveal>
                    <h2 className="font-black tracking-[-0.04em] text-[#F1EADF]" style={{ fontSize: 'clamp(40px, 7vw, 88px)' }}>
                        The Work<span className="text-[#F04A32]">.</span>
                    </h2>
                </Reveal>
                <div className="mt-12 flex flex-col gap-10 lg:mt-14 lg:gap-14">
                    {rows.map((row) =>
                        row.kind === 'marker' ? (
                            <YearMarker key={row.key} year={row.year} subtitle={row.subtitle} />
                        ) : (
                            <WorkRow key={row.key} project={row.project} year={row.year} align={row.align} onSelect={onSelect} />
                        )
                    )}
                </div>
            </div>
        </section>
    );
};

export default LandingPageFlow;
