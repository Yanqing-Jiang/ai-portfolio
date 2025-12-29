import React, { useRef, useMemo, useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import type { Project, ProjectYear } from '../types';
import { motion } from 'framer-motion';
import Style2MorphWords from './hero/Style2MorphWords';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import Lenis from 'lenis';
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

// Contact links data
const contactLinks = [
    {
        label: 'LinkedIn',
        href: 'https://www.linkedin.com/in/jiangyanqing/',
        icon: (
            <svg viewBox="0 0 34 34" className="w-8 h-8 sm:w-10 sm:h-10" xmlns="http://www.w3.org/2000/svg">
                <rect width="34" height="34" rx="4" fill="#0A66C2" />
                <path d="M8 12.5h4v13H8v-13zm2-6.5C8.9 6 8 6.9 8 8s.9 2 2 2 2-.9 2-2-.9-2-2-2zm6 6.5h3.8v1.8h.1c.5-1 1.9-2 3.9-2 4.1 0 4.9 2.7 4.9 6.1V25.5h-4v-6.4c0-1.5 0-3.5-2.1-3.5-2.1 0-2.4 1.6-2.4 3.4v6.5h-4v-13z" fill="#fff" />
            </svg>
        ),
    },
    {
        label: 'Medium',
        href: 'https://medium.com/@yanqing_j',
        icon: (
            <img src="https://yanqinghot.blob.core.windows.net/public-access/Medium_logo_Monogram.svg.png" alt="Medium" className="w-8 h-8 sm:w-10 sm:h-10" />
        ),
    },
    {
        label: 'Email',
        href: 'mailto:jiangyanqing90@gmail.com',
        icon: (
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8 sm:w-10 sm:h-10">
                <path d="M20 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V6a2 2 0 00-2-2zm0 2l-8 5-8-5h16zm0 12H4V8l8 5 8-5v10z" />
            </svg>
        ),
    },
] as const;

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
interface YearTheme {
    gradient: string;
    headingGradient: string;
    nodeGradient: string;
    glowColor: string;
    cardBorderHover: string;
    cardShadowHover: string;
}

const YEAR_THEMES: Record<number | string, YearTheme> = {
    2025: {
        gradient: 'from-cyan-400 to-purple-500',
        headingGradient: 'from-cyan-300 via-sky-400 to-purple-400',
        nodeGradient: 'from-cyan-400 to-purple-500',
        glowColor: 'rgba(34, 211, 238, 0.4)',
        cardBorderHover: 'hover:border-cyan-500/50',
        cardShadowHover: 'hover:shadow-cyan-500/20',
    },
    2024: {
        gradient: 'from-blue-400 to-teal-500',
        headingGradient: 'from-blue-300 via-blue-400 to-teal-400',
        nodeGradient: 'from-blue-400 to-teal-500',
        glowColor: 'rgba(59, 130, 246, 0.4)',
        cardBorderHover: 'hover:border-blue-500/50',
        cardShadowHover: 'hover:shadow-blue-500/20',
    },
    2023: {
        gradient: 'from-purple-400 to-pink-500',
        headingGradient: 'from-purple-300 via-fuchsia-400 to-pink-400',
        nodeGradient: 'from-purple-400 to-pink-500',
        glowColor: 'rgba(168, 85, 247, 0.4)',
        cardBorderHover: 'hover:border-purple-500/50',
        cardShadowHover: 'hover:shadow-purple-500/20',
    },
    2022: {
        gradient: 'from-green-400 to-emerald-500',
        headingGradient: 'from-green-300 via-emerald-400 to-teal-400',
        nodeGradient: 'from-green-400 to-emerald-500',
        glowColor: 'rgba(52, 211, 153, 0.4)',
        cardBorderHover: 'hover:border-emerald-500/50',
        cardShadowHover: 'hover:shadow-emerald-500/20',
    },
    default: {
        gradient: 'from-sky-400 to-purple-500',
        headingGradient: 'from-sky-300 via-blue-400 to-purple-400',
        nodeGradient: 'from-sky-400 to-purple-500',
        glowColor: 'rgba(56, 189, 248, 0.4)',
        cardBorderHover: 'hover:border-sky-500/50',
        cardShadowHover: 'hover:shadow-sky-500/20',
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

            // 1. Hero Animations (Immediate)
            const heroTl = gsap.timeline({ defaults: { ease: 'power3.out' } });
            heroTl
                .from('.hero-name', { opacity: 0, y: 60, duration: 1, delay: 0.2 })
                .from('.hero-title', { opacity: 0, y: 40, duration: 0.8 }, '-=0.5')
                .from('.hero-social', { opacity: 0, y: 30, stagger: 0.1, duration: 0.6 }, '-=0.4')
                .from('.hero-morph', { opacity: 0, scale: 0.9, duration: 0.8 }, '-=0.3');

            // 2. Horizontal Scroll Section "The Neural Stream"
            // Use matchMedia to optimize for mobile vs desktop
            if (horizontalSectionRef.current && trackRef.current) {
                const track = trackRef.current;
                const section = horizontalSectionRef.current;
                const mainScroller = document.querySelector('main');

                // Calculate scroll amount
                const getScrollAmount = () => -(track.scrollWidth - window.innerWidth);

                // ============================================
                // DESKTOP: Full cinematic card assembly
                // ============================================
                const createDesktopCardAnimations = (tween: gsap.core.Tween) => {
                    const cards = gsap.utils.toArray('.stream-card') as HTMLElement[];
                    cards.forEach((card) => {
                        const background = card.querySelector('.assembler-bg');
                        const image = card.querySelector('.assembler-image');
                        const content = card.querySelector('.assembler-content');
                        const header = card.querySelector('.assembler-header');

                        // Background glass flies in with 3D depth
                        gsap.from(background, {
                            z: -600, opacity: 0, scale: 0.8, rotateX: -25,
                            scrollTrigger: {
                                trigger: card, containerAnimation: tween,
                                start: 'left center+=500', end: 'left center', scrub: true,
                            }
                        });

                        // Image slides in with blur reveal
                        gsap.from(image, {
                            x: 150, opacity: 0, scale: 1.2, filter: 'blur(20px)',
                            scrollTrigger: {
                                trigger: card, containerAnimation: tween,
                                start: 'left center+=600', end: 'left center', scrub: true,
                            }
                        });

                        // Content floats up magnetically
                        gsap.from(content, {
                            y: 120, opacity: 0, rotate: 5,
                            scrollTrigger: {
                                trigger: card, containerAnimation: tween,
                                start: 'left center+=400', end: 'left center', scrub: true,
                            }
                        });

                        // Header slides in with power
                        gsap.from(header, {
                            x: -80, scale: 0.9, opacity: 0,
                            scrollTrigger: {
                                trigger: card, containerAnimation: tween,
                                start: 'left center+=450', end: 'left center', scrub: true,
                            }
                        });

                        // Focus highlight effect
                        gsap.to(card, {
                            scale: 1.05, filter: 'brightness(1.1) saturate(1.1)', zIndex: 50, duration: 0.5,
                            scrollTrigger: {
                                trigger: card, containerAnimation: tween,
                                start: 'left center+=200', end: 'right center-=200',
                                toggleActions: 'play reverse play reverse',
                                onEnter: () => card.classList.add('is-focused'),
                                onLeave: () => card.classList.remove('is-focused'),
                                onEnterBack: () => card.classList.add('is-focused'),
                                onLeaveBack: () => card.classList.remove('is-focused'),
                            }
                        });
                    });

                    // Year markers parallax
                    const years = gsap.utils.toArray('.year-marker-bg') as HTMLElement[];
                    years.forEach((year) => {
                        gsap.to(year, {
                            x: 500, opacity: 0, scale: 1.5, ease: 'none',
                            scrollTrigger: {
                                trigger: year, containerAnimation: tween,
                                start: 'left right', end: 'right left', scrub: true,
                            }
                        });
                    });
                };

                // ============================================
                // RESPONSIVE SCROLL SETUP with matchMedia
                // ============================================
                const mm = gsap.matchMedia();

                // Desktop (768px+): Full horizontal scroll cinematic experience
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
                            scrub: 1.2,
                            invalidateOnRefresh: true,
                            anticipatePin: 1,
                        },
                    });
                    createDesktopCardAnimations(tween);

                    // Neural Pulse Progress Tracker (desktop only)
                    const pulsePoint = document.querySelector('.neural-pulse-point');
                    if (pulsePoint) {
                        gsap.to(pulsePoint, {
                            x: () => {
                                const bar = pulsePoint.parentElement;
                                return bar ? (bar.clientWidth - 8) : 0;
                            },
                            ease: 'none',
                            scrollTrigger: {
                                trigger: section,
                                scroller: mainScroller,
                                start: 'top top',
                                end: () => `+=${track.scrollWidth - window.innerWidth}`,
                                scrub: true,
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
                    {/* Hero Section with Parallax Background */}
                    <section ref={heroRef} className="relative overflow-hidden border-b border-white/5">
                        {/* Parallax background elements */}
                        <div className="absolute inset-0 overflow-hidden pointer-events-none">
                            <div className="parallax-bg absolute -top-20 -right-20 w-96 h-96 bg-gradient-to-br from-sky-500/10 to-purple-500/10 rounded-full blur-3xl" />
                            <div className="parallax-bg absolute -bottom-32 -left-32 w-80 h-80 bg-gradient-to-tr from-pink-500/10 to-sky-500/10 rounded-full blur-3xl" />
                        </div>

                        {/* Match legacy LandingPage.tsx hero exactly */}
                        <div className="relative mx-auto grid max-w-7xl grid-cols-1 gap-10 px-4 sm:px-6 lg:px-8 pt-4 pb-12 sm:pt-6 sm:pb-16 md:pt-8 md:pb-20 lg:grid-cols-[3fr_2fr] lg:items-center">
                            {/* Left: Name and info */}
                            <div className="flex flex-col">
                                <h1
                                    className="hero-name text-balance font-extrabold text-white tracking-[-0.01em] leading-[1.1]"
                                    style={{ fontSize: 'clamp(36px, 8vw, 56px)' }}
                                >
                                    Yanqing Jiang
                                </h1>
                                <div
                                    className="hero-title mt-4 font-bold text-sky-200"
                                    style={{ fontSize: 'clamp(15px, 2.5vw, 22px)' }}
                                >
                                    Advanced Analytics @ P&amp;G
                                </div>
                                <div className="mt-8 flex flex-wrap items-center gap-4 sm:gap-6 text-gray-400">
                                    {contactLinks.map((item) => (
                                        <motion.a
                                            key={item.label}
                                            href={item.href}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="hero-social group flex flex-col items-center hover:text-white transition-colors"
                                            initial="rest"
                                            whileHover="hover"
                                            animate="rest"
                                        >
                                            <motion.div
                                                variants={{ rest: { scale: 1 }, hover: { scale: 1.1 } }}
                                                className="flex items-center justify-center rounded-full border border-white/10 bg-white/5 p-2.5 sm:p-3 backdrop-blur-sm"
                                            >
                                                {/* Scale icon for mobile */}
                                                <div className="scale-75 sm:scale-100">
                                                    {item.icon}
                                                </div>
                                            </motion.div>
                                            <motion.span
                                                variants={{ rest: { opacity: 0.8, y: 0 }, hover: { opacity: 1, y: -2 } }}
                                                className="mt-2 text-[10px] sm:text-xs uppercase tracking-widest"
                                            >
                                                {item.label}
                                            </motion.span>
                                        </motion.a>
                                    ))}
                                </div>
                            </div>

                            {/* Right: Morphing keywords (matching legacy Style2MorphWords) */}
                            <div className="hero-morph relative flex justify-center lg:justify-end">
                                <div className="relative z-10 w-full max-w-xl text-left">
                                    <Style2MorphWords
                                        variant="inline"
                                        size="xl"
                                        gradient={false}
                                        intervalMs={2900}
                                        words={['AI Agent Systems', 'Insight Automation', 'Enterprise Data Platform', 'Long-term Memory Agent']}
                                    />
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* HORIZONTAL SCROLL "NEURAL STREAM" SECTION - DESKTOP ONLY */}
                    {/* Mobile shows vertical stacked cards instead (see below) */}
                    <div ref={horizontalSectionRef} className="hidden md:block relative h-screen w-screen bg-slate-950 z-30 overflow-hidden">
                        <div className="h-full w-full flex items-center">
                            {/* The Track - full width without constraints */}
                            <div ref={trackRef} className="flex h-full items-center gap-0 w-max relative">
                                {/* The Neural Pulse Progress Tracker */}
                                <div className="fixed bottom-12 left-12 right-12 h-px bg-slate-800 z-50 pointer-events-none hidden md:block">
                                    <div className="neural-pulse-point absolute top-1/2 left-0 -translate-y-1/2 w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_15px_theme('colors.blue.400')]" />
                                </div>

                                {/* Connecting Data Line (Background) */}
                                <div className="absolute top-1/2 left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500/10 to-transparent w-full pointer-events-none" />

                                <div className="flex gap-20 md:gap-40 items-center pl-8 md:pl-20 pr-[50vw]">
                                    {/* Introduction / Start Node */}
                                    <div className="flex flex-col justify-center min-w-[80vw] md:min-w-[30vw] px-4 sm:px-10">
                                        <h2 className="text-3xl md:text-6xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white to-slate-600 mb-6">
                                            Project<br />Preview
                                        </h2>
                                        <div className="h-1 w-20 sm:w-24 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full" />
                                        <p className="mt-6 text-slate-400 text-base sm:text-lg max-w-sm">
                                            Scroll to view timeline of Yanqing's AI projects
                                        </p>
                                    </div>

                                    {/* Years Loop */}
                                    {displayYears.map(({ year, projects, label }) => {
                                        const theme = getYearTheme(year);
                                        return (
                                            <div key={year} className="flex gap-12 md:gap-20 items-center relative">
                                                {/* Giant Background Year Marker */}
                                                <div
                                                    className="year-marker-bg absolute -top-20 md:-top-40 -left-10 md:-left-20 text-[8rem] md:text-[18rem] font-bold text-slate-900/40 select-none z-0 pointer-events-none"
                                                    style={{ fontFamily: 'Inter, sans-serif' }}
                                                >
                                                    {year}
                                                </div>

                                                {/* Visual Separator / Node */}
                                                <div className="relative z-10 flex flex-col items-center gap-4">
                                                    <div
                                                        className={`w-4 h-4 rounded-full bg-gradient-to-r ${theme.nodeGradient} shadow-[0_0_20px_theme('colors.blue.400')]`}
                                                    />
                                                    <div className="h-32 w-px bg-slate-800" />
                                                    <h3 className={`text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-br ${theme.headingGradient} rotate-[-90deg] whitespace-nowrap origin-center select-none`}>
                                                        {label ?? year}
                                                    </h3>
                                                </div>

                                                {/* Projects Stream */}
                                                {projects.map((project) => {
                                                    const previewDescription = project.cardDescription ?? project.description;
                                                    const shortDesc = previewDescription.length > 120 ? previewDescription.substring(0, 120) + '...' : previewDescription;

                                                    return (
                                                        <div
                                                            key={project.id}
                                                            className="stream-card relative group flex-shrink-0 w-[90vw] md:w-[700px] h-[60vh] md:h-[550px] perspective-2000 z-10 will-change-transform"
                                                        >
                                                            {/* Card Container - DECONSTRUCTED ASSEMBLER */}
                                                            <div className="relative w-full h-full flex flex-col justify-end p-6 md:p-14 group-hover:shadow-[0_0_60px_rgba(59,130,246,0.25)] transition-shadow duration-500 rounded-3xl">

                                                                {/* Layer 1: Background Glass Frame (Assembler Piece) */}
                                                                <div className="assembler-bg absolute inset-0 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-white/5 group-hover:border-white/20 transition-colors duration-700 shadow-2xl will-change-transform" />

                                                                {/* Layer 2: Image Fragment (Assembler Piece) */}
                                                                <div className="assembler-image absolute top-4 right-4 bottom-1/2 md:bottom-4 left-4 md:left-1/3 rounded-2xl overflow-hidden pointer-events-none z-0">
                                                                    <div className="absolute inset-0 grayscale contrast-125 opacity-40 group-hover:grayscale-0 group-hover:opacity-80 transition-all duration-1000">
                                                                        <img
                                                                            src={project.coverUrl ?? project.imageUrl}
                                                                            alt={project.title}
                                                                            className="w-full h-full object-cover scale-110 group-hover:scale-100 transition-transform duration-1000"
                                                                        />
                                                                    </div>
                                                                    <div className="absolute inset-0 bg-gradient-to-t md:bg-gradient-to-l from-slate-950/80 via-transparent to-transparent" />
                                                                </div>

                                                                {/* Layer 3: Floating Meta (Assembler Piece) */}
                                                                <div className="assembler-header absolute top-10 md:top-12 left-8 md:left-10 z-30">
                                                                    <div className="flex flex-wrap gap-2 mb-4 md:mb-6">
                                                                        {project.technologies.slice(0, 3).map(tech => (
                                                                            <span key={tech} className={`text-[9px] md:text-[10px] uppercase tracking-widest font-bold px-2 py-0.5 rounded-full ${getTechBadgeClass(tech)}`}>
                                                                                {tech}
                                                                            </span>
                                                                        ))}
                                                                    </div>
                                                                    <h4 className={`text-3xl md:text-6xl font-black text-white leading-none tracking-tighter transition-all duration-500 group-hover:text-blue-400`}>
                                                                        {project.title.split(' ').map((word, i) => (
                                                                            <span key={i} className="block">{word}</span>
                                                                        ))}
                                                                    </h4>
                                                                </div>

                                                                {/* Layer 4: Description (Assembler Piece) */}
                                                                <div className="assembler-content relative z-30 max-w-sm">
                                                                    <p className="text-slate-400 text-sm md:text-lg mb-6 md:mb-8 leading-relaxed font-medium">
                                                                        {shortDesc}
                                                                    </p>

                                                                    <Link
                                                                        to={`/project/${project.id}`}
                                                                        onClick={() => onSelectProject(project)}
                                                                        className="group/btn relative inline-flex items-center justify-center px-8 py-3 overflow-hidden font-bold text-white transition-all duration-300 bg-white/5 rounded-full hover:bg-white/10"
                                                                    >
                                                                        <span className="relative flex items-center gap-2 text-xs tracking-widest uppercase">
                                                                            Explore Project
                                                                            <svg className="w-4 h-4 transition-transform group-hover/btn:translate-x-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
                                                                        </span>
                                                                    </Link>
                                                                </div>

                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        );
                                    })}

                                    {/* Visual End of Stream */}
                                    <div className="min-w-[20vw] flex items-center justify-center text-slate-500 text-sm font-mono tracking-widest uppercase rotate-90">
                                    </div>
                                </div>
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
