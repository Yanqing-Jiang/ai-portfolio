import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
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

const LinkCTA: React.FC<{ to: string; children: React.ReactNode; onClick?: () => void }> = ({ to, children, onClick }) => (
    <Link
        to={to}
        onClick={onClick}
        className="group inline-flex min-h-[48px] items-center gap-2 py-2 text-[15px] font-semibold text-[#F1EADF] transition-colors hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#F04A32]"
    >
        {children}
        <span className="text-[#F04A32] transition-transform duration-200 group-hover:translate-x-1">→</span>
    </Link>
);

const Eyebrow: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <p className="text-[12px] font-semibold uppercase tracking-[0.22em] text-[#A8A096]">{children}</p>
);

interface LandingPageFlowProps {
    projectData: ProjectYear[];
    onSelectProject: (project: Project) => void;
}

const LandingPageFlow: React.FC<LandingPageFlowProps> = ({ projectData, onSelectProject }) => {
    const [menuOpen, setMenuOpen] = useState(false);
    const allProjects = useMemo(
        () => projectData.filter((g) => !g.hiddenOnLanding).flatMap((y) => y.projects),
        [projectData]
    );
    // SiteNavigation schema mirrors the visible commercial nav, not the legacy
    // project chronology (which stays in WebSite.hasPart via buildWebsiteSchema).
    const landingSchemas = useMemo(
        () => buildLandingSchemas(allProjects, LANDING_NAV),
        [allProjects]
    );
    const personSchema = useMemo(() => buildPersonSchema(), []);
    const landingKeywords = useMemo(() => LANDING_SEO.keywords.join(', '), []);

    // Resolve real project routes for the "selected systems" section.
    const findProject = (id: string) => allProjects.find((p) => p.id === id);
    const homer = findProject('homer');
    const agentToUi = findProject('agent-to-ui');
    const analytics = findProject('next-gen-analytics-agent');

    const goTo = (id: string) => {
        const p = findProject(id);
        if (p) onSelectProject(p);
    };

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
                    .hero-h1 .hero-line { overflow: hidden; padding-top: 0.12em; margin-top: -0.12em; }
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
            `}</style>

            {/* ── Section 0 — Nav ─────────────────────────────────────── */}
            <header className="sticky top-0 z-50 border-b border-[#37332E] bg-[#12110F]/90 backdrop-blur-md">
                <nav className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-6 lg:px-10">
                    <a href="#top" className="text-[15px] font-bold tracking-tight text-[#F1EADF]">
                        Yanqing Jiang
                    </a>
                    <div className="hidden items-center gap-8 md:flex">
                        <a href="#build" className="text-[14px] text-[#A8A096] transition-colors hover:text-[#F1EADF]">What I build</a>
                        <a href="#proof" className="text-[14px] text-[#A8A096] transition-colors hover:text-[#F1EADF]">Proof</a>
                        <a href="#process" className="text-[14px] text-[#A8A096] transition-colors hover:text-[#F1EADF]">Process</a>
                        <Link to="/blog" className="text-[14px] text-[#A8A096] transition-colors hover:text-[#F1EADF]">Writing</Link>
                    </div>
                    <div className="flex items-center gap-3">
                        <Link
                            to="/consult"
                            className="rounded-[4px] bg-[#F04A32] px-4 py-2 text-[13px] font-semibold text-[#12110F] transition-colors hover:bg-[#D63B27]"
                        >
                            Start a project
                        </Link>
                        <button
                            type="button"
                            onClick={() => setMenuOpen(true)}
                            aria-label="Open menu"
                            aria-expanded={menuOpen}
                            className="flex min-h-[44px] min-w-[44px] items-center justify-center text-[14px] font-semibold text-[#F1EADF] md:hidden"
                        >
                            Menu
                        </button>
                    </div>
                </nav>
            </header>

            {/* Mobile menu sheet */}
            <AnimatePresence>
                {menuOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[60] bg-[#12110F] px-6 py-6 md:hidden"
                    >
                        <div className="flex h-16 items-center justify-between">
                            <span className="text-[15px] font-bold text-[#F1EADF]">Yanqing Jiang</span>
                            <button
                                type="button"
                                onClick={() => setMenuOpen(false)}
                                aria-label="Close menu"
                                className="flex min-h-[44px] min-w-[44px] items-center justify-center text-[14px] font-semibold text-[#F1EADF]"
                            >
                                Close
                            </button>
                        </div>
                        <div className="mt-8 flex flex-col gap-6">
                            <a href="#build" onClick={() => setMenuOpen(false)} className="text-[22px] font-semibold text-[#F1EADF]">What I build</a>
                            <a href="#proof" onClick={() => setMenuOpen(false)} className="text-[22px] font-semibold text-[#F1EADF]">Proof</a>
                            <a href="#process" onClick={() => setMenuOpen(false)} className="text-[22px] font-semibold text-[#F1EADF]">Process</a>
                            <Link to="/blog" onClick={() => setMenuOpen(false)} className="text-[22px] font-semibold text-[#F1EADF]">Writing</Link>
                            <Link
                                to="/consult"
                                onClick={() => setMenuOpen(false)}
                                className="mt-4 inline-flex min-h-[48px] items-center justify-center rounded-[4px] bg-[#F04A32] px-6 text-[16px] font-semibold text-[#12110F]"
                            >
                                Start a project
                            </Link>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            <main id="top">
                {/* ── Section 1 — Hero + proof rail ───────────────────── */}
                <section className="mx-auto max-w-[1280px] px-6 pt-20 pb-24 sm:pt-28 lg:px-10 lg:pt-32 lg:pb-32">
                    <Eyebrow>Yanqing Jiang · Advanced Analytics at P&amp;G</Eyebrow>
                    <h1 className="hero-h1 mt-8 font-black leading-[0.86] tracking-[-0.06em] text-[#F1EADF]" style={{ fontSize: 'clamp(52px, 12vw, 190px)' }}>
                        <span className="hero-line"><span className="hero-line-inner">AI agent</span></span>
                        <span className="hero-line"><span className="hero-line-inner">system builder<span className="hero-period text-[#F04A32]">.</span></span></span>
                    </h1>
                    <div className="mt-10 grid gap-10 lg:grid-cols-[1.4fr_1fr] lg:items-end">
                        <p className="max-w-[46ch] text-[18px] leading-[1.5] text-[#A8A096] sm:text-[20px]">
                            I design and ship enterprise pipelines that remove repetitive work, and personal AI
                            systems that remember how you work. Once the plan is agreed, a five-person team is
                            ready to deliver.
                        </p>
                        <div className="flex flex-col gap-4 sm:flex-row sm:items-center lg:justify-end">
                            <PrimaryCTA to="/consult?path=enterprise">Build for my business</PrimaryCTA>
                            <LinkCTA to="/consult?path=individual">Build for me</LinkCTA>
                        </div>
                    </div>

                    {/* Proof rail */}
                    <div className="mt-16 border-t border-[#37332E] pt-8">
                        <dl className="grid grid-cols-2 gap-8 sm:grid-cols-3" style={{ fontVariantNumeric: 'tabular-nums' }}>
                            {[
                                { n: '4,000+', l: 'hours automated' },
                                { n: '$150M', l: 'in decisions influenced' },
                                { n: '5 people', l: 'ready to deliver' },
                            ].map((m) => (
                                <div key={m.l}>
                                    <dt className="text-[40px] font-black tracking-[-0.03em] text-[#F1EADF] sm:text-[48px]">{m.n}</dt>
                                    <dd className="mt-1 text-[15px] text-[#A8A096]">{m.l}</dd>
                                </div>
                            ))}
                        </dl>
                        <p className="mt-6 text-[13px] text-[#A8A096]">Numbers from production systems, not demos.</p>
                    </div>
                </section>

                {/* ── Section 2 — Offers, two buyer paths ─────────────── */}
                <section id="build" className="border-t border-[#37332E]">
                    <div className="mx-auto max-w-[1280px] px-6 py-24 lg:px-10 lg:py-32">
                        <Reveal>
                            <h2 className="font-black tracking-[-0.04em] text-[#F1EADF]" style={{ fontSize: 'clamp(36px, 6vw, 72px)' }}>
                                What should work better?
                            </h2>
                            <p className="mt-4 text-[18px] text-[#A8A096]">Choose the outcome. The technology follows.</p>
                        </Reveal>

                        <div className="mt-16 grid gap-12 lg:grid-cols-2 lg:gap-0">
                            {/* FOR BUSINESSES */}
                            <div className="lg:pr-14">
                                <Eyebrow>For businesses</Eyebrow>
                                <p className="mt-3 max-w-[42ch] text-[16px] text-[#A8A096]">
                                    Remove expensive work from an operating process, then give the system a metric it has to move.
                                </p>
                                <div className="mt-10 space-y-10">
                                    <OfferRow
                                        title="Enterprise agentic pipelines"
                                        tagline="Pipelines with a number attached."
                                        body="Automate document-heavy, analytical, or multi-system work. Every build starts with a baseline — hours, cost, cycle time, error rate — and ships with telemetry around the result."
                                        proof="1,000 analyst hours saved · 90% fewer late payments"
                                        cta="Scope an enterprise pipeline"
                                        to="/consult?path=enterprise&offer=pipeline"
                                    />
                                    <OfferRow
                                        title="Embedded AI delivery team"
                                        tagline="A five-person team that ships."
                                        body="Need execution, not another recommendation deck? Yanqing leads a five-person team across AI, data, product, and interface delivery once the plan, milestones, owners, and success criteria are agreed."
                                        cta="Bring in the delivery team"
                                        to="/consult?path=enterprise&offer=delivery-team"
                                    />
                                </div>
                            </div>

                            {/* FOR INDIVIDUALS */}
                            <div className="border-t border-[#37332E] pt-12 lg:border-l lg:border-t-0 lg:pl-14 lg:pt-0">
                                <Eyebrow>For individuals</Eyebrow>
                                <p className="mt-3 max-w-[42ch] text-[16px] text-[#A8A096]">
                                    Build a system around the way you think, work, publish, and remember.
                                </p>
                                <div className="mt-10 space-y-10">
                                    <OfferRow
                                        title="Personal agent OS"
                                        tagline="An assistant that remembers you."
                                        body="Short-term context, long-term memory, scheduled work, and controlled access to your tools — running on infrastructure you own. Not another chat window: a system that compounds context over months."
                                        proof="I run one myself. It's called Homer, and it runs my life."
                                        cta="Design my personal agent"
                                        to="/consult?path=individual&offer=personal-agent"
                                    />
                                    <OfferRow
                                        title="Zero-maintenance personal website"
                                        tagline="A site you never touch."
                                        body="Designed, built, hosted, maintained. Publishing, metadata, deployment, and monitoring are automated, while the site and content remain yours."
                                        proof="This site is one."
                                        cta="Build my personal site"
                                        to="/consult?path=individual&offer=website"
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="mt-16 border-t border-[#37332E] pt-8">
                            <p className="text-[16px] text-[#A8A096]">
                                Not sure which path fits? Start with the problem and we'll route it.{' '}
                                <Link to="/consult" className="font-semibold text-[#F1EADF] underline decoration-[#F04A32] decoration-2 underline-offset-4 hover:text-white">
                                    Describe the problem →
                                </Link>
                            </p>
                        </div>
                    </div>
                </section>

                {/* ── Section 3 — Flagship enterprise case ────────────── */}
                <section id="proof" className="border-t border-[#37332E] bg-[#191816]">
                    <div className="mx-auto max-w-[1280px] px-6 py-24 lg:px-10 lg:py-32">
                        <Reveal>
                            <Eyebrow>Enterprise case study · Invoice reconciliation</Eyebrow>
                            <h2 className="mt-6 font-black leading-[0.92] tracking-[-0.045em] text-[#F1EADF]" style={{ fontSize: 'clamp(34px, 6vw, 84px)' }}>
                                1,000 analyst hours back.<br />
                                <span className="text-[#F04A32]">90% fewer late payments.</span>
                            </h2>
                        </Reveal>
                        <div className="mt-14 grid gap-12 lg:grid-cols-[5fr_7fr]">
                            <div>
                                <p className="text-[18px] leading-[1.5] text-[#A8A096]">
                                    An LLM invoice processor turned a fragmented reconciliation process into a
                                    production workflow for P&amp;G Walgreens teams.
                                </p>
                                <p className="mt-6 text-[15px] leading-[1.6] text-[#A8A096]">
                                    Mixed PDFs, XLSX, and XLSB in — structured extraction — one-to-many
                                    reconciliation — an actionable discrepancy report out.
                                </p>
                                <p className="mt-8 font-mono text-[12px] leading-[1.7] text-[#A8A096]">
                                    Function calling · Python · Flask · pandas · PDF/XLSB processing · Azure
                                </p>
                                <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center">
                                    {findProject('llm-invoice-processor') ? (
                                        <LinkCTA to="/project/llm-invoice-processor" onClick={() => goTo('llm-invoice-processor')}>
                                            Read the invoice case study
                                        </LinkCTA>
                                    ) : null}
                                    <LinkCTA to="/consult?path=enterprise&offer=pipeline&context=invoice-reconciliation">
                                        Discuss a similar workflow
                                    </LinkCTA>
                                </div>
                            </div>
                            <ol className="space-y-6">
                                {[
                                    ['01', 'Ingest', 'Mixed-format invoices and statements (PDF, XLSX, XLSB) land in one intake.'],
                                    ['02', 'Extract', 'Function-calling turns unstructured documents into structured, validated line items.'],
                                    ['03', 'Reconcile', 'One-to-many matching against expected records surfaces every discrepancy.'],
                                    ['04', 'Report', 'An actionable discrepancy report ships to the AP team with the exceptions ranked.'],
                                ].map(([n, t, d]) => (
                                    <li key={n} className="flex gap-5 border-t border-[#37332E] pt-6">
                                        <span className="font-mono text-[13px] text-[#F04A32]">{n}</span>
                                        <div>
                                            <p className="text-[17px] font-semibold text-[#F1EADF]">{t}</p>
                                            <p className="mt-1 text-[15px] text-[#A8A096]">{d}</p>
                                        </div>
                                    </li>
                                ))}
                            </ol>
                        </div>
                    </div>
                </section>

                {/* ── Section 4 — Selected working systems ────────────── */}
                <section className="border-t border-[#37332E]">
                    <div className="mx-auto max-w-[1280px] px-6 py-24 lg:px-10 lg:py-32">
                        <Reveal>
                            <h2 className="max-w-[20ch] font-black tracking-[-0.04em] text-[#F1EADF]" style={{ fontSize: 'clamp(30px, 5vw, 60px)' }}>
                                Systems you can inspect, not claims you have to take on faith.
                            </h2>
                        </Reveal>
                        <div className="mt-14 divide-y divide-[#37332E] border-y border-[#37332E]">
                            <SystemRow
                                kicker="Personal AI OS"
                                title="Homer remembers, schedules, and acts."
                                body="Runs 24/7 on a Mac Mini: SQLite-backed hybrid memory, five CLI executors, MCP tools, scheduled jobs. The working reference behind the personal-agent offer."
                                proof="Live for 6+ months · five executors · ~12,000 memory claims"
                                cta="Open the Homer console"
                                to={homer?.link ?? '/homer'}
                                onClick={() => goTo('homer')}
                            />
                            <SystemRow
                                kicker="Generative interfaces"
                                title="The agent assembles the interface."
                                body="Ask a finance question and Agent to UI streams the relevant charts, KPIs, tables, and news — no static dashboard required."
                                cta="Try Agent to UI"
                                to={agentToUi?.link ?? '/project/agent-to-ui'}
                                onClick={() => goTo('agent-to-ui')}
                            />
                            <SystemRow
                                kicker="Agentic analytics"
                                title="Answers without another static dashboard."
                                body="Clarify the question, query the data, generate charts, and expose a traceable task graph you can follow end to end."
                                cta="See the analytics architecture"
                                to={analytics?.link ?? '/project/next-gen-analytics-agent'}
                                onClick={() => goTo('next-gen-analytics-agent')}
                            />
                        </div>
                        <div className="mt-10">
                            <a
                                href="https://www.jiangyanqing.com"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="group inline-flex items-center gap-2 text-[15px] font-semibold text-[#F1EADF] hover:text-white"
                            >
                                Full archive
                                <span className="text-[#F04A32] transition-transform duration-200 group-hover:translate-x-1">→</span>
                            </a>
                        </div>
                    </div>
                </section>

                {/* ── Section 5 — Engagement process ──────────────────── */}
                <section id="process" className="border-t border-[#37332E] bg-[#191816]">
                    <div className="mx-auto max-w-[1280px] px-6 py-24 lg:px-10 lg:py-32">
                        <Reveal>
                            <h2 className="font-black tracking-[-0.04em] text-[#F1EADF]" style={{ fontSize: 'clamp(36px, 6vw, 72px)' }}>
                                Agree on the plan. Then we ship.
                            </h2>
                        </Reveal>
                        <div className="mt-14 grid gap-8 md:grid-cols-2">
                            {[
                                ['01 · Diagnose', 'We map the current workflow, the people doing it, the systems involved, and the cost of leaving it unchanged.'],
                                ['02 · Design the plan', 'You get proposed scope, architecture, milestones, owners, a success metric, and a fixed commercial proposal.'],
                                ['03 · Deliver', 'Once approved, Yanqing leads a five-person team to build, instrument, launch, and hand over the system.'],
                                ['04 · Prove the result', 'We compare the shipped workflow with the baseline and decide what to improve, expand, or stop.'],
                            ].map(([t, d]) => (
                                <div key={t} className="border-t border-[#37332E] pt-6">
                                    <p className="font-mono text-[13px] tracking-wide text-[#F04A32]">{t}</p>
                                    <p className="mt-3 text-[16px] leading-[1.55] text-[#A8A096]">{d}</p>
                                </div>
                            ))}
                        </div>
                        <div className="mt-12">
                            <PrimaryCTA to="/consult">Start a project</PrimaryCTA>
                        </div>
                    </div>
                </section>

                {/* ── Section 6 — Builder-led trust ───────────────────── */}
                <section className="border-t border-[#37332E]">
                    <div className="mx-auto max-w-[1280px] px-6 py-24 lg:px-10 lg:py-32">
                        <div className="grid gap-12 lg:grid-cols-[1fr_1.2fr]">
                            <Reveal>
                                <h2 className="font-black tracking-[-0.04em] text-[#F1EADF]" style={{ fontSize: 'clamp(32px, 5vw, 64px)' }}>
                                    Builder-led.<br />Team-delivered.
                                </h2>
                            </Reveal>
                            <div>
                                <p className="text-[18px] leading-[1.55] text-[#A8A096]">
                                    Yanqing Jiang works where AI models meet operating reality: data, memory, tools,
                                    interfaces, guardrails, and ownership. His enterprise perspective comes from
                                    Advanced Analytics at P&amp;G; his proof comes from systems that run and outcomes
                                    that can be measured.
                                </p>
                                <div className="mt-10 grid gap-6 sm:grid-cols-3">
                                    {[
                                        'Measure before modeling.',
                                        'Integrate before replacing.',
                                        'Leave ownership behind.',
                                    ].map((p) => (
                                        <p key={p} className="border-t border-[#37332E] pt-4 text-[16px] font-semibold text-[#F1EADF]">{p}</p>
                                    ))}
                                </div>
                                <p className="mt-8 text-[14px] text-[#A8A096]">
                                    Ship with observability, docs, and a handoff path — no permanent consulting dependency.
                                </p>
                                <div className="mt-10">
                                    <LinkCTA to="/blog">Read Yanqing's writing</LinkCTA>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

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
                            <a href="#process" className="text-[15px] font-semibold text-[#A8A096] transition-colors hover:text-[#F1EADF]">
                                See how the process works
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
                                <a href="#build" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">Enterprise agentic pipelines</a>
                                <a href="#build" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">Embedded AI delivery team</a>
                                <a href="#build" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">Personal agent OS</a>
                                <a href="#build" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">Zero-maintenance website</a>
                            </div>
                            <div className="space-y-3">
                                <p className="text-[12px] uppercase tracking-[0.2em] text-[#A8A096]">More</p>
                                <a href="https://www.jiangyanqing.com" target="_blank" rel="noopener noreferrer" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">Work</a>
                                <Link to="/blog" className="block text-[15px] text-[#A8A096] hover:text-[#F1EADF]">Writing</Link>
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

// --- Offer row (two-path offers) ------------------------------------------
const OfferRow: React.FC<{
    title: string;
    tagline: string;
    body: string;
    proof?: string;
    cta: string;
    to: string;
}> = ({ title, tagline, body, proof, cta, to }) => (
    <Reveal>
        <div>
            <h3 className="text-[24px] font-bold tracking-[-0.02em] text-[#F1EADF] sm:text-[28px]">{title}</h3>
            <p className="mt-1 text-[16px] italic text-[#A8A096]">{tagline}</p>
            <p className="mt-4 max-w-[46ch] text-[16px] leading-[1.55] text-[#A8A096]">{body}</p>
            {proof ? <p className="mt-4 text-[15px] font-semibold text-[#F04A32]">{proof}</p> : null}
            <div className="mt-5">
                <LinkCTA to={to}>{cta}</LinkCTA>
            </div>
        </div>
    </Reveal>
);

// --- System row (selected working systems) --------------------------------
const SystemRow: React.FC<{
    kicker: string;
    title: string;
    body: string;
    proof?: string;
    cta: string;
    to: string;
    onClick?: () => void;
}> = ({ kicker, title, body, proof, cta, to, onClick }) => (
    <Reveal>
        <div className="grid gap-6 py-10 lg:grid-cols-[1fr_1.4fr] lg:gap-16">
            <div>
                <p className="text-[12px] uppercase tracking-[0.2em] text-[#A8A096]">{kicker}</p>
                <h3 className="mt-3 text-[26px] font-bold leading-[1.05] tracking-[-0.02em] text-[#F1EADF] sm:text-[32px]">{title}</h3>
            </div>
            <div>
                <p className="text-[16px] leading-[1.6] text-[#A8A096]">{body}</p>
                {proof ? <p className="mt-4 font-mono text-[13px] text-[#A8A096]">{proof}</p> : null}
                <div className="mt-5">
                    <LinkCTA to={to} onClick={onClick}>{cta}</LinkCTA>
                </div>
            </div>
        </div>
    </Reveal>
);

export default LandingPageFlow;
