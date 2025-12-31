import React, { useRef, useMemo, useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import type { Project, ProjectYear } from '../types';
import { motion } from 'framer-motion';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import Lenis from 'lenis';
import { AdvancedNeuralField, HolographicTerminal } from './demos/StreamingInsightDemo';
import {
    DEFAULT_OG_IMAGE,
    DEFAULT_THEME_COLOR,
    DEFAULT_TWITTER_HANDLE,
    LANDING_FAQ,
    LANDING_SEO,
    SITE_NAME,
} from '../constants/seo';
import { buildLandingSchemas, toNavigationFromProjects } from '../constants/structuredData';

// Register GSAP plugins
gsap.registerPlugin(ScrollTrigger);

// Tech badge styling
type TechCategory = 'ai' | 'data' | 'frontend' | 'infra' | 'ml' | 'default';

const TECH_CATEGORY_CLASSES: Record<TechCategory, string> = {
    ai: 'border bg-emerald-600/20 text-emerald-300 border-emerald-500/30 hover:bg-emerald-600/30',
    data: 'border bg-emerald-500/20 text-emerald-200 border-emerald-500/30 hover:bg-emerald-500/30',
    frontend: 'border bg-purple-500/20 text-purple-200 border-purple-500/30 hover:bg-purple-500/30',
    infra: 'border bg-orange-500/20 text-orange-200 border-orange-500/30 hover:bg-orange-500/30',
    ml: 'border bg-pink-500/20 text-pink-200 border-pink-500/30 hover:bg-pink-500/30',
    default: 'border bg-sky-500/15 text-sky-200 border-sky-500/30 hover:bg-sky-500/25',
};

const TECH_EXACT_CATEGORIES: Record<string, TechCategory> = {
    'single agent workflow': 'ai',
    'multi-agent workflow': 'ai',
    'human-in-the-loop': 'frontend',
    'rag': 'ml',
    'langgraph': 'ai',
    'agent orchestration': 'ai',
    'agentic workflow': 'ai',
    'vector search': 'data',
    'faiss': 'data',
    'function calling': 'ai',
    'supabase': 'data',
    'postgresql': 'data',
    'fastapi': 'data',
    'react': 'frontend',
    'typescript': 'frontend',
    'power bi': 'data',
    'azure': 'infra',
    'docker': 'infra',
};

const TECH_CATEGORY_KEYWORDS: Array<{ category: TechCategory; keywords: string[] }> = [
    { category: 'ai', keywords: ['agent', 'workflow', 'rag', 'memory', 'orchestration', 'automation', 'copilot'] },
    { category: 'data', keywords: ['sql', 'database', 'supabase', 'postgres', 'fastapi', 'data', 'bi', 'analytics'] },
    { category: 'frontend', keywords: ['react', 'typescript', 'tailwind', 'echarts', 'ui', 'frontend', 'javascript'] },
    { category: 'infra', keywords: ['azure', 'docker', 'api', 'cloud', 'platform'] },
    { category: 'ml', keywords: ['model', 'forecast', 'ml', 'machine learning', 'science'] },
];

// Year-specific visual themes for Project Evolution section
// Year-specific visual themes for Project Evolution section
interface YearTheme {
    gradient: string;
    bgGradient: string; // Global atmosphere
    accent: string;
    headingGradient: string;
    nodeGradient: string;
    glowColor: string;
    cardBorderHover: string;
    cardShadowHover: string;
}

const YEAR_THEMES: Record<number | string, YearTheme> = {
    2026: {
        gradient: 'from-orange-400 to-rose-500',
        bgGradient: 'radial-gradient(circle at 50% 50%, rgba(251, 146, 60, 0.15), rgba(225, 29, 72, 0.05) 50%, transparent 100%)',
        accent: '#fb923c',
        headingGradient: 'from-orange-300 via-rose-400 to-pink-400',
        nodeGradient: 'from-orange-400 to-rose-500',
        glowColor: 'rgba(244, 63, 94, 0.4)',
        cardBorderHover: 'hover:border-rose-500/50',
        cardShadowHover: 'hover:shadow-rose-500/20',
    },
    2025: {
        gradient: 'from-cyan-400 to-blue-600',
        bgGradient: 'radial-gradient(circle at 50% 50%, rgba(34, 211, 238, 0.15), rgba(37, 99, 235, 0.05) 50%, transparent 100%)',
        accent: '#22d3ee',
        headingGradient: 'from-cyan-300 via-sky-400 to-blue-500',
        nodeGradient: 'from-cyan-400 to-blue-600',
        glowColor: 'rgba(34, 211, 238, 0.4)',
        cardBorderHover: 'hover:border-cyan-500/50',
        cardShadowHover: 'hover:shadow-cyan-500/20',
    },
    2024: {
        gradient: 'from-emerald-400 to-teal-600',
        bgGradient: 'radial-gradient(circle at 50% 50%, rgba(52, 211, 153, 0.15), rgba(13, 148, 136, 0.05) 50%, transparent 100%)',
        accent: '#34d399',
        headingGradient: 'from-emerald-300 via-teal-400 to-green-500',
        nodeGradient: 'from-emerald-400 to-teal-600',
        glowColor: 'rgba(52, 211, 153, 0.4)',
        cardBorderHover: 'hover:border-emerald-500/50',
        cardShadowHover: 'hover:shadow-emerald-500/20',
    },
    default: {
        gradient: 'from-purple-400 to-indigo-600',
        bgGradient: 'radial-gradient(circle at 50% 50%, rgba(168, 85, 247, 0.15), rgba(79, 70, 229, 0.05) 50%, transparent 100%)',
        accent: '#a855f7',
        headingGradient: 'from-purple-300 via-indigo-400 to-purple-500',
        nodeGradient: 'from-purple-400 to-indigo-600',
        glowColor: 'rgba(56, 189, 248, 0.4)',
        cardBorderHover: 'hover:border-purple-500/50',
        cardShadowHover: 'hover:shadow-purple-500/20',
    },
};

const getYearTheme = (year: number | string): YearTheme => {
    return YEAR_THEMES[year] ?? YEAR_THEMES.default;
};


const getTechBadgeClass = (tech: string) => {
    const normalized = tech.trim().toLowerCase();
    if (TECH_EXACT_CATEGORIES[normalized]) {
        return TECH_CATEGORY_CLASSES[TECH_EXACT_CATEGORIES[normalized]];
    }
    for (const { category, keywords } of TECH_CATEGORY_KEYWORDS) {
        if (keywords.some(keyword => normalized.includes(keyword))) {
            return TECH_CATEGORY_CLASSES[category];
        }
    }
    return TECH_CATEGORY_CLASSES.default;
};

interface LandingPageFlowProps {
    projectData: ProjectYear[];
    onSelectProject: (project: Project) => void;
}

const LandingPageFlow: React.FC<LandingPageFlowProps> = ({ projectData, onSelectProject }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const mainScrollerRef = useRef<HTMLElement | null>(null);
    const heroRef = useRef<HTMLElement>(null);
    const horizontalSectionRef = useRef<HTMLDivElement>(null);
    const trackRef = useRef<HTMLDivElement>(null);
    const preAiSectionRef = useRef<HTMLDivElement>(null);

    const [pageMouse, setPageMouse] = useState<{ x: number; y: number } | null>(null);
    const lenisRef = useRef<Lenis | null>(null);

    // Separate AI projects from Pre-AI projects
    const displayYears = useMemo(
        () => projectData.filter(group => !group.hiddenOnLanding),
        [projectData]
    );

    const preAiProjects = useMemo(
        () => projectData.find(group =>
            group.label?.toLowerCase().includes('pre-ai') ||
            group.year === 2021
        )?.projects ?? [],
        [projectData]
    );

    const allProjects = useMemo(
        () => displayYears.flatMap(year => year.projects),
        [displayYears]
    );

    const navigationLinks = useMemo(() => toNavigationFromProjects(allProjects), [allProjects]);
    const landingSchemas = useMemo(
        () => buildLandingSchemas(allProjects, navigationLinks, LANDING_FAQ),
        [allProjects, navigationLinks]
    );
    const landingKeywords = useMemo(() => LANDING_SEO.keywords.join(', '), []);

    // Initialize Lenis Smooth Scroll
    useEffect(() => {
        const mainEl = document.querySelector('main');
        if (!mainEl) return;

        // Ensure main scroller ref is set for GSAP
        mainScrollerRef.current = mainEl;

        const lenis = new Lenis({
            wrapper: mainEl,
            content: mainEl,
            duration: 1.2,
            easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
            touchMultiplier: 1.5,
            infinite: false,
        });

        lenisRef.current = lenis;

        // Sync GSAP with Lenis via Ticker (High Performance)
        const updateLenis = (time: number) => {
            lenis.raf(time * 1000);
        };

        gsap.ticker.add(updateLenis);
        gsap.ticker.lagSmoothing(0);

        // Sync ScrollTrigger updates
        lenis.on('scroll', ScrollTrigger.update);

        return () => {
            gsap.ticker.remove(updateLenis);
            lenis.destroy();
            lenisRef.current = null;
        };
    }, []);

    // GSAP Animations with ScrollTrigger
    useGSAP(() => {
        // Wait for scroller to be available
        const scroller = mainScrollerRef.current || window;

        const ctx = gsap.context(() => {
            ScrollTrigger.defaults({
                scroller: scroller,
            });

            // 1. Hero Animations (Cinematic Reveal)
            const heroTl = gsap.timeline({ defaults: { ease: 'power4.out', duration: 1.5 } });
            heroTl
                .from('.hero-name span', { y: 100, opacity: 0, skewX: -20, stagger: 0.1, filter: 'blur(20px)', delay: 0.5 })
                .from('.hero-line', { scaleX: 0, transformOrigin: 'left' }, '-=1')
                .from('.hero-title', { opacity: 0, y: 20, duration: 0.8 }, '-=0.8')
                .from('.terminal-entrance', { scale: 0.9, opacity: 0, y: 40, duration: 2 }, '-=1.2');

            // Scroll-triggered tilt for the hero dashboard
            gsap.to('.terminal-entrance', {
                rotateX: -10,
                y: -30,
                scrollTrigger: {
                    trigger: '.terminal-entrance',
                    start: 'top bottom',
                    end: 'bottom top',
                    scrub: true
                }
            });

            // 2. Horizontal Scroll Section "The Neural Stream"
            // Use matchMedia to optimize for mobile vs desktop
            if (horizontalSectionRef.current && trackRef.current) {
                const track = trackRef.current;
                const section = horizontalSectionRef.current;
                const mainScroller = document.querySelector('main');

                // Calculate scroll amount
                const getScrollAmount = () => -(track.scrollWidth - window.innerWidth);

                // ============================================
                // RESPONSIVE SCROLL SETUP with matchMedia
                // ============================================
                const mm = gsap.matchMedia();

                // ============================================
                // DESKTOP: Timeline "Wow" Factor logic
                // ============================================

                mm.add("(min-width: 768px)", () => {
                    const tween = gsap.to(track, {
                        x: getScrollAmount,
                        ease: 'none',
                        scrollTrigger: {
                            trigger: section,
                            scroller: mainScroller,
                            start: 'top top',
                            end: () => `+=${track.scrollWidth - window.innerWidth}`,
                            pin: true,
                            scrub: 1,
                            invalidateOnRefresh: true,
                            onToggle: (self) => {
                                // Performance: Hide hero background canvas when timeline is active
                                gsap.set("#neural-field-canvas", {
                                    display: self.isActive ? "none" : "block"
                                });
                            }
                        },
                    });

                    // 1. Parallax Images
                    gsap.utils.toArray<HTMLElement>('.parallax-img').forEach(img => {
                        gsap.to(img, {
                            x: 100,
                            ease: 'none',
                            scrollTrigger: {
                                trigger: img.closest('.stream-card'),
                                scroller: mainScroller,
                                containerAnimation: tween,
                                start: 'left right',
                                end: 'right left',
                                scrub: true,
                            }
                        });
                    });

                    // 2. Atmosphere Shift (Background Gradients)
                    displayYears.forEach((yearData) => {
                        const yearSection = document.getElementById(`year-section-${yearData.year}`);
                        const bgLayer = document.getElementById(`bg-layer-${yearData.year}`);
                        if (yearSection && bgLayer) {
                            gsap.to(bgLayer, {
                                opacity: 1,
                                duration: 1,
                                scrollTrigger: {
                                    trigger: yearSection,
                                    scroller: mainScroller,
                                    containerAnimation: tween,
                                    start: 'left center',
                                    end: 'right center',
                                    toggleActions: 'play reverse play reverse',
                                    scrub: 0.5,
                                }
                            });
                        }
                    });

                    // 3. Living Timeline Pulse
                    const pulsePoint = document.querySelector('.timeline-pulse');
                    if (pulsePoint) {
                        gsap.to(pulsePoint, {
                            x: track.scrollWidth,
                            ease: 'none',
                            scrollTrigger: {
                                trigger: section,
                                scroller: mainScroller,
                                start: 'top top',
                                end: () => `+=${track.scrollWidth - window.innerWidth}`,
                                scrub: 0.1,
                            }
                        });
                    }

                    return () => { tween.kill(); };
                });


                // Mobile (<768px): NO horizontal scroll - it's hidden
                // Instead, we animate the vertical stacked cards
                mm.add("(max-width: 767px)", () => {
                    const mobileCards = gsap.utils.toArray('.mobile-project-card') as HTMLElement[];

                    mobileCards.forEach((card) => {
                        gsap.fromTo(card,
                            { y: 60, opacity: 0 },
                            {
                                y: 0, opacity: 1,
                                duration: 0.8,
                                ease: 'power2.out',
                                scrollTrigger: {
                                    trigger: card,
                                    scroller: mainScroller,
                                    start: 'top bottom-=100',
                                    toggleActions: 'play none none none',
                                }
                            }
                        );
                    });

                    return () => { };
                });
            }

            // 3. Pre-AI Section (Vertical) - CRT/TERMINAL REVEAL
            if (preAiSectionRef.current) {
                const header = preAiSectionRef.current.querySelector('.pre-ai-header');
                const cards = preAiSectionRef.current.querySelectorAll('.pre-ai-card');

                // Get the main scroller for nested layouts
                const mainScroller = document.querySelector('main');

                // Standard reveal for the whole container - more relaxed trigger to ensure it shows
                gsap.from(header, {
                    y: 40,
                    opacity: 0,
                    filter: 'blur(5px)',
                    duration: 1,
                    scrollTrigger: {
                        trigger: header,
                        scroller: mainScroller, // EXPLICIT scroller for nested layouts
                        start: 'top bottom', // Start as soon as it enters viewport
                        toggleActions: 'play none none none',
                    }
                });

                // Simple stagger for cards to ensure they are visible
                gsap.fromTo(cards,
                    { y: 50, opacity: 0 },
                    {
                        y: 0,
                        opacity: 1,
                        stagger: 0.1,
                        duration: 0.8,
                        ease: 'power2.out',
                        scrollTrigger: {
                            trigger: preAiSectionRef.current,
                            scroller: mainScroller, // EXPLICIT scroller for nested layouts
                            start: 'top bottom-=50',
                        }
                    }
                );

                // Scanline animation
                cards.forEach(card => {
                    const scanline = card.querySelector('.scanline');
                    if (scanline) {
                        gsap.to(scanline, {
                            y: 500,
                            duration: 3,
                            repeat: -1,
                            ease: 'none',
                        });
                    }
                });
            }

        }, containerRef);

        // CRITICAL: Refresh ScrollTrigger after a short delay to ensure DOM is fully rendered
        // This fixes issues in production where elements may not be measured correctly on first load
        const refreshTimeout = setTimeout(() => {
            ScrollTrigger.refresh(true);
        }, 100);

        return () => {
            clearTimeout(refreshTimeout);
            ctx.revert();
        };
    }, { scope: containerRef, dependencies: [displayYears, preAiProjects] });

    return (
        <>
            <Helmet>
                <title>{LANDING_SEO.title}</title>
                <meta name="description" content={LANDING_SEO.description} />
                <meta name="keywords" content={landingKeywords} />
                <meta name="author" content={LANDING_SEO.author} />
                <meta name="robots" content="index, follow" />
                <link rel="canonical" href={LANDING_SEO.canonical} />
                <meta property="og:type" content="website" />
                <meta property="og:title" content={LANDING_SEO.title} />
                <meta property="og:description" content={LANDING_SEO.description} />
                <meta property="og:url" content={LANDING_SEO.canonical} />
                <meta property="og:site_name" content={SITE_NAME} />
                <meta property="og:image" content={DEFAULT_OG_IMAGE} />
                <meta name="twitter:card" content="summary_large_image" />
                <meta name="twitter:site" content={DEFAULT_TWITTER_HANDLE} />
                <meta name="twitter:title" content={LANDING_SEO.title} />
                <meta name="twitter:description" content={LANDING_SEO.description} />
                <meta name="twitter:image" content={DEFAULT_OG_IMAGE} />
                <meta name="theme-color" content={DEFAULT_THEME_COLOR} />
                {landingSchemas.map((schema, index) => (
                    <script key={`landing-schema-${index}`} type="application/ld+json">
                        {JSON.stringify(schema)}
                    </script>
                ))}
            </Helmet>

            <div
                ref={containerRef}
                onMouseMove={(e) => setPageMouse({ x: e.clientX, y: e.clientY })}
                className="relative min-h-screen bg-slate-950 text-gray-300"
            >
                {/* Mouse follower glow with parallax */}
                <div
                    aria-hidden
                    className="pointer-events-none fixed inset-0 z-10 transition-opacity duration-300"
                    style={{
                        background: pageMouse
                            ? `radial-gradient(500px 500px at ${pageMouse.x}px ${pageMouse.y}px, rgba(56,189,248,0.12), transparent 60%)`
                            : 'radial-gradient(500px 500px at 50% 10%, rgba(56,189,248,0.12), transparent 60%)',
                    }}
                />

                <div className="relative z-20">
                    {/* Hero Section with 3D Holographic Dashboard */}
                    <section ref={heroRef} className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden py-12 px-4 sm:px-6 lg:px-8 border-b border-white/5 bg-slate-950">
                        {/* Noise Texture (Consistent with Sidebar & Rest of Page) */}
                        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none" />

                        <AdvancedNeuralField />

                        {/* Ambient Nebula Glows */}
                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full pointer-events-none">
                            <div className="absolute top-1/4 -left-1/4 w-[800px] h-[800px] bg-sky-600/10 rounded-full blur-[200px]" />
                            <div className="absolute bottom-1/4 -right-1/4 w-[800px] h-[800px] bg-purple-600/10 rounded-full blur-[200px]" />
                        </div>

                        <div className="relative z-20 max-w-7xl w-full grid grid-cols-1 lg:grid-cols-[1fr_1.5fr] gap-8 lg:gap-16 items-center lg:min-h-[80vh]">
                            {/* Information Section */}
                            <div className="space-y-10 lg:pr-12">
                                <div className="space-y-6">
                                    <div className="hero-line h-px w-24 bg-sky-500" />

                                    <h1 className="hero-name text-[clamp(2.5rem,8vw,8rem)] font-black italic tracking-tighter leading-[0.85] flex flex-col uppercase text-white">
                                        <span className="inline-block">Yanqing</span>
                                        <span className="inline-block">Jiang</span>
                                    </h1>

                                    <div className="hero-title space-y-2">
                                        <p className="text-sky-500 font-mono text-sm md:text-base tracking-[0.4em] uppercase">Advanced Analytics @ P&G</p>
                                    </div>
                                </div>

                            </div>

                            {/* VISUAL SECTION: WIDE 3D DASHBOARD */}
                            <div className="terminal-entrance relative flex items-center justify-center perspective-2000">
                                <motion.div
                                    className="relative z-20 w-full max-w-[750px] aspect-[1.6/1]"
                                >
                                    <div className="absolute inset-0 bg-sky-500/10 blur-[150px] rounded-full opacity-30 pointer-events-none" />
                                    <HolographicTerminal />
                                </motion.div>
                            </div>
                        </div>
                    </section>

                    {/* HORIZONTAL SCROLL "NEURAL STREAM" SECTION - DESKTOP ONLY */}
                    <div ref={horizontalSectionRef} className="hidden md:block relative h-screen w-screen bg-slate-950 z-30 overflow-hidden">
                        {/* GLOBAL ATMOSPHERE LAYERS (Fixed behind track) */}
                        <div className="absolute inset-0 w-full h-full pointer-events-none z-0">
                            {displayYears.map(y => (
                                <div
                                    key={`bg-${y.year}`}
                                    id={`bg-layer-${y.year}`}
                                    className="absolute inset-0 w-full h-full opacity-0 will-change-[opacity]"
                                    style={{
                                        background: getYearTheme(y.year).bgGradient,
                                        filter: 'blur(60px)'
                                    }}
                                />
                            ))}
                            {/* NOISE OVERLAY */}
                            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20" />
                        </div>

                        <div className="h-full w-full relative z-10 overflow-visible">
                            {/* The Track - full width without constraints */}
                            <div ref={trackRef} className="flex h-full items-center gap-0 w-max relative pl-20 will-change-transform shrink-0">
                                {/* THE LIVING TIMELINE LINE */}
                                <div className="absolute top-1/2 left-0 right-0 h-px bg-slate-800 w-full pointer-events-none">
                                    <div className="timeline-pulse absolute top-1/2 left-0 -translate-y-1/2 w-32 h-1 bg-gradient-to-r from-transparent via-white to-transparent blur-[2px]" />
                                </div>

                                {/* Introduction / Start Node */}
                                <div className="w-[30vw] shrink-0 px-10">
                                    <h2 className="text-6xl font-black mb-4">The Work</h2>
                                    <p className="text-slate-400">A journey through generative UI, agents, and data.</p>
                                </div>

                                {/* Years Loop */}
                                {displayYears.map((yearGroup) => {
                                    const theme = getYearTheme(yearGroup.year);
                                    return (
                                        <div
                                            key={yearGroup.year}
                                            id={`year-section-${yearGroup.year}`}
                                            className="flex items-center gap-20 px-10 relative"
                                        >
                                            {/* YEAR MARKER */}
                                            <div className="relative shrink-0 flex flex-col items-center gap-6">
                                                <div className="text-[12rem] font-bold leading-none text-transparent bg-clip-text bg-gradient-to-b from-white/10 to-transparent select-none absolute -top-40 left-1/2 -translate-x-1/2 blur-sm">
                                                    {yearGroup.year}
                                                </div>

                                                {/* Timeline Node */}
                                                <div
                                                    className="w-4 h-4 rounded-full relative z-10"
                                                    style={{ background: theme.accent, boxShadow: `0 0 20px ${theme.accent}` }}
                                                />
                                                <div className="h-24 w-px bg-gradient-to-b from-slate-700 to-transparent" />
                                                <h3 className="text-xl font-mono tracking-widest uppercase" style={{ color: theme.accent }}>
                                                    {yearGroup.subtitle?.replace(/[()]/g, '') || 'Era'}
                                                </h3>
                                            </div>

                                            {/* Projects */}
                                            {yearGroup.projects.map((project) => (
                                                <div
                                                    key={project.id}
                                                    className="stream-card relative w-[600px] h-[450px] shrink-0 group perspective-1000"
                                                >
                                                    <div className="relative w-full h-full bg-slate-900/40 backdrop-blur-md border border-white/10 rounded-3xl overflow-hidden hover:border-white/30 transition-all duration-500 hover:shadow-2xl hover:shadow-cyan-500/10 group-hover:-translate-y-2">
                                                        {/* PARALLAX IMAGE CONTAINER */}
                                                        <div className="absolute inset-0 overflow-hidden pointer-events-none">
                                                            <div className="absolute inset-0 grayscale group-hover:grayscale-0 opacity-60 group-hover:opacity-80 transition-opacity duration-700">
                                                                <img
                                                                    src={project.coverUrl ?? project.imageUrl}
                                                                    alt={project.title}
                                                                    className="parallax-img w-[120%] h-full object-cover grayscale group-hover:grayscale-0"
                                                                    style={{ transform: 'translateX(-50px)' }}
                                                                />
                                                            </div>
                                                            <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent" />
                                                        </div>

                                                        {/* CONTENT */}
                                                        <div className="absolute bottom-0 left-0 w-full p-8 z-20 translate-y-4 group-hover:translate-y-0 transition-transform duration-500">
                                                            <div className="flex gap-2 mb-3">
                                                                {project.technologies.slice(0, 3).map(tech => (
                                                                    <span key={tech} className="text-[10px] uppercase font-bold px-2 py-1 rounded bg-white/5 border border-white/10 text-slate-300">
                                                                        {tech}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                            <h4 className="text-3xl font-bold leading-tight mb-2 group-hover:text-white transition-colors">
                                                                {project.title}
                                                            </h4>
                                                            <p className="text-slate-400 text-sm line-clamp-2 mb-6 group-hover:text-slate-300 transition-colors">
                                                                {project.cardDescription ?? project.description}
                                                            </p>
                                                            <div className="flex items-center gap-2 text-sm font-bold tracking-widest uppercase text-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity duration-500 delay-100">
                                                                <Link
                                                                    to={`/project/${project.id}`}
                                                                    onClick={() => onSelectProject(project)}
                                                                >
                                                                    <span>View Project</span>
                                                                </Link>
                                                                <span className="text-lg">→</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    );
                                })}

                                {/* END SPACER */}
                                <div className="w-[50vw]" />
                            </div>
                        </div>
                    </div>


                    {/* MOBILE VERTICAL STACKED CARDS - Shown only on mobile */}
                    {/* This replaces the horizontal timeline experience with natural vertical scroll */}
                    <section className="md:hidden relative bg-slate-950 py-12 px-4">
                        {/* Section Header */}
                        <div className="text-center mb-10">
                            <h2 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white to-slate-600 mb-4">
                                AI Projects
                            </h2>
                            <div className="h-1 w-16 mx-auto bg-gradient-to-r from-blue-500 to-purple-500 rounded-full" />
                            <p className="mt-4 text-slate-400 text-sm max-w-xs mx-auto">
                                Scroll to explore Yanqing's work
                            </p>
                        </div>

                        {/* Vertically Stacked Project Cards */}
                        <div className="space-y-8 max-w-md mx-auto">
                            {displayYears.flatMap(({ year, projects }) =>
                                projects.map((project) => {
                                    const previewDescription = project.cardDescription ?? project.description;
                                    const shortDesc = previewDescription.length > 100
                                        ? previewDescription.substring(0, 100) + '...'
                                        : previewDescription;

                                    return (
                                        <div
                                            key={project.id}
                                            className="mobile-project-card group relative rounded-2xl overflow-hidden bg-slate-900/80 border border-slate-800 shadow-xl"
                                        >
                                            {/* Project Image */}
                                            <div className="relative h-48 overflow-hidden">
                                                <img
                                                    src={project.coverUrl ?? project.imageUrl}
                                                    alt={project.title}
                                                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                                                    loading="lazy"
                                                />
                                                <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-slate-900/40 to-transparent" />

                                                {/* Year Badge */}
                                                <div className="absolute top-3 right-3 bg-blue-600/80 backdrop-blur-sm px-3 py-1 rounded-full text-xs font-bold text-white">
                                                    {year}
                                                </div>
                                            </div>

                                            {/* Project Content */}
                                            <div className="p-5">
                                                <h3 className="text-lg font-bold text-white mb-2 leading-tight">
                                                    {project.title}
                                                </h3>
                                                <p className="text-slate-400 text-sm mb-4 leading-relaxed">
                                                    {shortDesc}
                                                </p>

                                                {/* Tech Tags */}
                                                <div className="flex flex-wrap gap-2 mb-4">
                                                    {project.technologies.slice(0, 3).map((tech) => (
                                                        <span
                                                            key={tech}
                                                            className="text-[10px] font-medium px-2 py-0.5 rounded-full border border-blue-500/30 bg-blue-500/10 text-blue-300"
                                                        >
                                                            {tech}
                                                        </span>
                                                    ))}
                                                </div>

                                                {/* CTA Button */}
                                                <Link
                                                    to={`/project/${project.id}`}
                                                    onClick={() => onSelectProject(project)}
                                                    className="inline-flex items-center gap-2 text-sm font-semibold text-blue-400 hover:text-blue-300 transition-colors"
                                                >
                                                    View Details
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                                                    </svg>
                                                </Link>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    </section>

                    {/* Pre-AI Projects Section - Distinct "Nostalgic" Style */}
                    {preAiProjects.length > 0 && (
                        <section ref={preAiSectionRef} className="relative bg-gradient-to-b from-slate-950 via-amber-950/10 to-slate-950 border-t border-amber-900/30">
                            {/* Vintage overlay texture */}
                            <div className="absolute inset-0 opacity-5 pointer-events-none"
                                style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noise\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.65\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noise)\'/%3E%3C/svg%3E")' }}
                            />

                            <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
                                <div className="pre-ai-header text-center mb-16">
                                    <h2
                                        className="font-black text-balance bg-clip-text text-transparent bg-gradient-to-r from-amber-400 via-orange-400 to-yellow-500 mb-4"
                                        style={{ fontSize: 'clamp(32px, 3.5vw, 48px)', textShadow: '0 0 40px rgba(251, 191, 36, 0.2)' }}
                                    >
                                        Pre-AI Projects
                                    </h2>
                                    <p className="text-lg text-amber-200/60 max-w-2xl mx-auto">
                                        Foundation work in analytics automation, BI platforms, and enterprise workflows before the AI revolution
                                    </p>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
                                    {preAiProjects.map((project) => {
                                        const previewDescription = project.cardDescription ?? project.description;
                                        const truncatedDescription =
                                            previewDescription.length > 150
                                                ? `${previewDescription.substring(0, 150)}...`
                                                : previewDescription;

                                        return (
                                            <div
                                                key={project.id}
                                                className="pre-ai-card group relative rounded-lg overflow-hidden border border-amber-800/20 bg-slate-950/40 backdrop-blur-sm hover:border-amber-600/40 transition-all duration-700 shadow-xl"
                                            >
                                                {/* CRT Scanline Effect */}
                                                <div className="scanline absolute top-0 left-0 w-full h-[2px] bg-amber-500/20 z-10 pointer-events-none -translate-y-full" />

                                                {/* Retro Overlay Effect */}
                                                <div className="absolute inset-0 pointer-events-none z-10 opacity-0 group-hover:opacity-10 bg-amber-500/5 mix-blend-overlay transition-opacity" />

                                                <div className="relative w-full h-56 overflow-hidden">
                                                    <img
                                                        src={project.coverUrl ?? project.imageUrl}
                                                        alt={project.title}
                                                        className="w-full h-full object-cover transition-all duration-1000 group-hover:scale-105 filter grayscale sepia-[0.3] group-hover:sepia-0 group-hover:grayscale-0"
                                                        loading="lazy"
                                                    />
                                                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/60 to-transparent" />

                                                    {/* Year Badge */}
                                                    <div className="absolute top-4 right-4 bg-amber-900/40 backdrop-blur-md px-3 py-1 rounded-full border border-amber-500/30 text-[10px] font-mono text-amber-200 tracking-tighter uppercase">
                                                        Pre-AI
                                                    </div>
                                                </div>

                                                <div className="p-6 sm:p-8">
                                                    <div className="mb-2 text-[10px] font-mono text-amber-500/60 flex items-center gap-2">
                                                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                                                        Pre-AI Era
                                                    </div>

                                                    <h3 className="text-xl sm:text-2xl font-bold text-white mb-4 group-hover:text-amber-300 transition-colors">
                                                        {project.title}
                                                    </h3>
                                                    <p className="text-gray-400 text-sm leading-relaxed mb-4">
                                                        {truncatedDescription}
                                                    </p>
                                                    <div className="flex flex-wrap gap-2 mb-4">
                                                        {project.technologies.slice(0, 3).map(tech => (
                                                            <span
                                                                key={tech}
                                                                className="text-xs font-medium px-2 py-0.5 rounded border border-amber-700/40 bg-amber-900/20 text-amber-300/80"
                                                            >
                                                                {tech}
                                                            </span>
                                                        ))}
                                                    </div>
                                                    <Link
                                                        to={`/project/${project.id}`}
                                                        onClick={() => onSelectProject(project)}
                                                        className="inline-flex items-center gap-2 text-sm font-medium text-amber-400 hover:text-amber-300 transition-colors"
                                                    >
                                                        Explore project
                                                        <svg className="h-4 w-4 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                                                        </svg>
                                                    </Link>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </section>
                    )}
                </div>

                {/* Gradient animation styles */}
                <style>{`
                    @keyframes gradient-x {
                        0%, 100% { background-position: 0% 50%; }
                        50% { background-position: 100% 50%; }
                    }
                    .animate-gradient-x {
                        background-size: 200% 200%;
                        animation: gradient-x 4s ease infinite;
                    }
                `}</style>
            </div>

        </>
    );
};

export default LandingPageFlow;
