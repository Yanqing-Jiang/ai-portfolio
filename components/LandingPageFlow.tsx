import React, { useRef, useMemo, useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import type { Project, ProjectYear } from '../types';
import { motion, useMotionValue, useSpring, useTransform, AnimatePresence } from 'framer-motion';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import Lenis from 'lenis';
import ProjectMedia from './ProjectMedia';
import { AdvancedNeuralField, HolographicTerminal } from './demos/StreamingInsightDemo';
import {
    DEFAULT_OG_IMAGE,
    DEFAULT_THEME_COLOR,
    DEFAULT_TWITTER_HANDLE,
    LANDING_SEO,
    SITE_NAME,
} from '../constants/seo';
import { buildLandingSchemas, buildPersonSchema, toNavigationFromProjects } from '../constants/structuredData';
import { Calendar as CalendarIcon } from 'lucide-react';

// Register GSAP plugins
gsap.registerPlugin(ScrollTrigger);



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
    'hero': {
        gradient: 'from-sky-400 to-purple-600',
        bgGradient: 'radial-gradient(circle at 50% 50%, rgba(14, 165, 233, 0.15), rgba(147, 51, 234, 0.05) 50%, transparent 100%)',
        accent: '#38bdf8',
        headingGradient: 'from-sky-300 via-sky-400 to-purple-500',
        nodeGradient: 'from-sky-400 to-purple-600',
        glowColor: 'rgba(56, 189, 248, 0.4)',
        cardBorderHover: 'hover:border-sky-500/50',
        cardShadowHover: 'hover:shadow-sky-500/20',
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


// AI Summary Footer - Provider configuration
// Function: AI_PROVIDERS — used by footer to open AI chat with recruiter prompt
interface AIProvider {
    name: string;
    icon: React.ReactNode;
    buildUrl: (prompt: string) => string;
    supportsUrlPrompt: boolean;
    color: string;
}

const RECRUITER_PROMPT = `As a recruiter or hiring manager reviewing Yanqing Jiang's AI portfolio (https://yanqing.app), I'd like a concise summary of his technical capabilities.

Please analyze these 5 highlighted projects:

1. **Agent to UI (2026)**: Streams custom financial dashboards from natural language using A2UI protocol, Claude Agent SDK, React Renderer, SSE Streaming.
   - Key achievement: Real-time widget generation from conversational queries

2. **Next Gen Analytics (2025)**: Multi-agent system with three workflow modes (Direct, Single-Agent, Multi-Agent) plus human-in-the-loop clarifications.
   - Key achievement: Explainable AI with task graph visualization

3. **Agentic Trading Bot (2025)**: LangGraph multi-agent system that achieved 200% realized gain on options before risk-triggered shutdown.
   - Key achievement: Demonstrates disciplined risk management in production

4. **LLM Invoice Processor (2024)**: Automates invoice reconciliation saving 1,000+ analyst hours annually with 90% reduction in late payments.
   - Key achievement: Measurable enterprise ROI with OpenAI function calling

5. **Ask My Resume RAG (2023)**: Career copilot achieving 95% question coverage via retrieval-augmented generation.
   - Key achievement: Evidence-backed responses with source citations`;

// SVG Icons for AI providers
const ChatGPTIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full">
        <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.8956zm16.0993 3.8558L12.6 8.3829l2.02-1.1638a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z" />
    </svg>
);

const ClaudeIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full">
        <path d="M4.709 15.955l4.72-2.647.08-.079-.08-.08-2.086-1.2a.383.383 0 0 0-.392.007l-2.399 1.39a.39.39 0 0 0-.132.536l.29.073zm8.493-4.044l.937-.526-.94-.542-4.91-2.829a.383.383 0 0 0-.392.007L5.62 9.597l7.582 2.314zm2.02-.598l2.379-1.334-2.1-1.218-1.216.684 1.064 1.787-.127.081zm4.069-2.283l-1.748 1.005-1.636-.947 1.178-.662-.007-.088-2.156-1.245-.078.044-1.66.931 1.064 1.787-.08.08.08.08 5.043 2.919v-2.57a.39.39 0 0 0-.195-.337l.195-.997zm-6.168.399l-1.064-1.787.08-.08-.08-.08L7.017 4.73a.383.383 0 0 0-.392.007L4.63 5.92l7.349 4.239 1.144-.73zm7.168 4.12L18.16 12.6l-2.1 1.178v2.436l4.231-2.386v-.83a.39.39 0 0 0-.195-.337l.195-.012zm-2.231 4.4l-2.1-1.218v2.389l2.1 1.218v-2.389zm-4.231 2.379l2.1-1.178v-2.436l-2.1 1.178v2.436zm-2.1-4.853v2.436l2.1 1.218v-2.389l-2.1-1.265zm-2.1 1.218l2.1-1.178v-2.436l-2.1 1.178v2.436zm6.231-3.654l2.1-1.218-2.1-1.178-2.1 1.178 2.1 1.218zm-4.131-2.396l-2.1-1.178v2.389l2.1 1.218v-2.429zm8.231 5.823v-2.389l-2.1 1.178v2.436l2.1-1.225z" />
    </svg>
);

const GeminiIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full">
        <path d="M12 24A14.304 14.304 0 0 0 0 12 14.304 14.304 0 0 0 12 0a14.305 14.305 0 0 0 12 12 14.305 14.305 0 0 0-12 12" />
    </svg>
);

const PerplexityIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full">
        <path d="M12.051.24a.72.72 0 0 0-.722.72v6.328L6.006 2.86a.72.72 0 0 0-.963 1.071l5.81 5.22H4.679a.72.72 0 0 0 0 1.44h6.172l-5.808 5.218a.72.72 0 1 0 .963 1.072l5.323-4.782v6.662a.72.72 0 1 0 1.44 0V11.93l5.177 4.65a.72.72 0 1 0 .963-1.071l-5.66-5.085h6.072a.72.72 0 1 0 0-1.44h-6.072l5.66-5.085a.72.72 0 1 0-.963-1.071l-5.177 4.65V.96a.72.72 0 0 0-.718-.72z" />
    </svg>
);

const AI_PROVIDERS: AIProvider[] = [
    {
        name: 'ChatGPT',
        icon: <ChatGPTIcon />,
        buildUrl: (prompt: string) => `https://chat.openai.com/?q=${encodeURIComponent(prompt)}`,
        supportsUrlPrompt: true,
        color: '#10a37f',
    },
    {
        name: 'Claude',
        icon: <ClaudeIcon />,
        buildUrl: () => 'https://claude.ai/new',
        supportsUrlPrompt: false,
        color: '#d97757',
    },
    {
        name: 'Gemini',
        icon: <GeminiIcon />,
        buildUrl: (prompt: string) => `https://gemini.google.com/app?q=${encodeURIComponent(prompt)}`,
        supportsUrlPrompt: true,
        color: '#4285f4',
    },
    {
        name: 'Perplexity',
        icon: <PerplexityIcon />,
        buildUrl: (prompt: string) => `https://www.perplexity.ai/?q=${encodeURIComponent(prompt)}`,
        supportsUrlPrompt: true,
        color: '#20b8cd',
    },
];


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
    const [showToast, setShowToast] = useState(false);
    const lenisRef = useRef<Lenis | null>(null);

    // Tilt Effect Logic for Hero Dashboard
    const heroMouseX = useMotionValue(0);
    const heroMouseY = useMotionValue(0);
    const mouseSpringConfig = { stiffness: 150, damping: 20 };
    const heroRotateX = useSpring(useTransform(heroMouseY, [-0.5, 0.5], [10, -10]), mouseSpringConfig);
    const heroRotateY = useSpring(useTransform(heroMouseX, [-0.5, 0.5], [-10, 10]), mouseSpringConfig);

    const handleHeroMouseMove = (e: React.MouseEvent) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        heroMouseX.set((e.clientX - centerX) / (rect.width / 2));
        heroMouseY.set((e.clientY - centerY) / (rect.height / 2));
    };

    const handleHeroMouseLeave = () => {
        heroMouseX.set(0);
        heroMouseY.set(0);
    };

    // Handler for AI provider click - copies prompt if needed, opens provider URL
    // Function: handleProviderClick — triggered by footer AI icons; opens AI chat with recruiter prompt
    const handleProviderClick = async (provider: AIProvider) => {
        if (!provider.supportsUrlPrompt) {
            try {
                await navigator.clipboard.writeText(RECRUITER_PROMPT);
                setShowToast(true);
                setTimeout(() => setShowToast(false), 3000);
            } catch {
                // Fallback: prompt user to copy manually
                console.warn('Clipboard API not available');
            }
        }
        window.open(provider.buildUrl(RECRUITER_PROMPT), '_blank', 'noopener,noreferrer');
    };

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
    // LANDING_FAQ is no longer passed into landing-page JSON-LD per GEO audit
    // 2026-05-03 (FAQPage schema removed; Princeton/IIT Delhi research shows
    // pure FAQ format hurts AI citations). LANDING_FAQ remains exported for
    // reuse as RAG context in the Ask-My-Resume agent.
    const landingSchemas = useMemo(
        () => buildLandingSchemas(allProjects, navigationLinks),
        [allProjects, navigationLinks]
    );
    const personSchema = useMemo(() => buildPersonSchema(), []);
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
            duration: 0.7,
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

        // Hoisted for cleanup access outside gsap.context()
        let aberrationRafId = 0;
        const cardListeners: Array<{ el: HTMLElement; type: string; fn: EventListener }> = [];

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
                            scrub: 0.3,
                            invalidateOnRefresh: true,
                            onToggle: (self) => {
                                // Performance: Lower neural field visibility instead of hiding it
                                gsap.to("#neural-field-canvas", {
                                    opacity: self.isActive ? 0.3 : 1,
                                    scale: self.isActive ? 0.9 : 1,
                                    duration: 1,
                                    overwrite: true
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
                    const yearsWithHero = [{ year: 'hero' }, ...displayYears];
                    yearsWithHero.forEach((yearData) => {
                        const yearSection = document.getElementById(`year-section-${yearData.year}`);
                        const bgLayer = document.getElementById(`bg-layer-${yearData.year}`);
                        if (yearSection && bgLayer) {
                            gsap.to(bgLayer, {
                                opacity: yearData.year === 'hero' ? 0 : 1, // Hero fades out, others fade in
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

            // 4. Projects: 3D Tilt & Inner Glow
            const cards = gsap.utils.toArray<HTMLElement>('.stream-card');
            cards.forEach(card => {
                const inner = card.querySelector('div') as HTMLElement;

                // Throttled mousemove (~60fps cap)
                let lastMoveTime = 0;
                const onMouseMove = ((e: MouseEvent) => {
                    const now = performance.now();
                    if (now - lastMoveTime < 16) return;
                    lastMoveTime = now;

                    const rect = card.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;

                    // Update Inner Glow
                    const xPct = (x / rect.width) * 100;
                    const yPct = (y / rect.height) * 100;
                    inner.style.setProperty('--mouse-x', `${xPct}%`);
                    inner.style.setProperty('--mouse-y', `${yPct}%`);

                    // GSAP Tilt
                    const centerX = rect.width / 2;
                    const centerY = rect.height / 2;
                    const rotateX = ((y - centerY) / centerY) * -10;
                    const rotateY = ((x - centerX) / centerX) * 10;

                    gsap.to(inner, {
                        rotateX: rotateX,
                        rotateY: rotateY,
                        duration: 0.1,
                        ease: 'power1.out',
                        overwrite: true
                    });
                }) as EventListener;

                const onMouseLeave = (() => {
                    gsap.to(inner, {
                        rotateX: 0,
                        rotateY: 0,
                        duration: 1,
                        ease: 'elastic.out(1, 0.3)',
                        overwrite: true
                    });
                }) as EventListener;

                card.addEventListener('mousemove', onMouseMove);
                card.addEventListener('mouseleave', onMouseLeave);
                cardListeners.push({ el: card, type: 'mousemove', fn: onMouseMove });
                cardListeners.push({ el: card, type: 'mouseleave', fn: onMouseLeave });
            });

            // 5. Chromatic Aberration based on Scroll Velocity
            // Uses opacity instead of drop-shadow for GPU-accelerated compositing
            const mainScrollerEl = document.querySelector('main');
            if (mainScrollerEl) {
                let lastScroll = 0;
                const updateAberration = () => {
                    const currentScroll = lenisRef.current?.scroll || 0;
                    const velocity = Math.abs(currentScroll - lastScroll);
                    lastScroll = currentScroll;

                    // Reset opacity when not scrolling, then skip further work
                    if (velocity < 1) {
                        gsap.set('.stream-card img', { opacity: 1 });
                        aberrationRafId = requestAnimationFrame(updateAberration);
                        return;
                    }

                    const opacity = velocity > 5 ? Math.max(0.7, 1 - velocity * 0.005) : 1;
                    gsap.set('.stream-card img', { opacity });

                    aberrationRafId = requestAnimationFrame(updateAberration);
                };
                aberrationRafId = requestAnimationFrame(updateAberration);
            }

        }, containerRef);

        // CRITICAL: Refresh ScrollTrigger after a short delay to ensure DOM is fully rendered
        // This fixes issues in production where elements may not be measured correctly on first load
        const refreshTimeout = setTimeout(() => {
            ScrollTrigger.refresh(true);
        }, 100);

        return () => {
            clearTimeout(refreshTimeout);
            // Cancel rAF loop to prevent it surviving unmount
            cancelAnimationFrame(aberrationRafId);
            // Remove card DOM event listeners (ctx.revert only cleans GSAP tweens)
            cardListeners.forEach(({ el, type, fn }) => el.removeEventListener(type, fn));
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
                <script type="application/ld+json">{JSON.stringify(personSchema)}</script>
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
                {/* Global Neural Field (Background) */}
                <div className="fixed inset-0 z-0 pointer-events-none">
                    <AdvancedNeuralField />
                </div>
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
                    <section ref={heroRef} className="relative min-h-0 md:min-h-screen flex flex-col items-center justify-start md:justify-center overflow-hidden pt-4 pb-6 md:pb-12 md:py-12 px-4 sm:px-6 lg:px-8 border-b border-white/5">
                        {/* Noise Texture (Consistent with Sidebar & Rest of Page) */}
                        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none" />

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
                                    onMouseMove={handleHeroMouseMove}
                                    onMouseLeave={handleHeroMouseLeave}
                                    style={{ rotateX: heroRotateX, rotateY: heroRotateY }}
                                    className="relative z-20 w-full max-w-[750px] aspect-[1.6/1]"
                                >
                                    <div className="absolute inset-0 bg-sky-500/10 blur-[150px] rounded-full opacity-30 pointer-events-none" />
                                    <HolographicTerminal />
                                </motion.div>
                            </div>

                            {/* Book a Consulting Session CTA */}
                            <div className="col-span-1 lg:col-span-2 flex justify-center mt-6 md:mt-10">
                                <Link
                                    to="/consult"
                                    className="group relative inline-flex items-center gap-2.5 px-6 py-3 md:px-8 md:py-3.5
                                               bg-sky-500/10 backdrop-blur-xl border border-sky-500/40 rounded-full
                                               text-sky-300 text-sm md:text-base font-semibold tracking-wide
                                               transition-all duration-300
                                               hover:bg-sky-500/20 hover:border-sky-400 hover:text-white hover:shadow-[0_0_30px_rgba(14,165,233,0.3)]
                                               active:scale-95"
                                >
                                    <CalendarIcon className="w-4 h-4 md:w-5 md:h-5" />
                                    Book a Consulting Session
                                    <svg className="w-4 h-4 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                                    </svg>
                                </Link>
                            </div>
                        </div>
                    </section>

                    {/* HORIZONTAL SCROLL "NEURAL STREAM" SECTION - DESKTOP ONLY */}
                    <div ref={horizontalSectionRef} className="hidden md:block relative h-screen w-screen z-30 overflow-hidden left-0 right-0" style={{ marginLeft: 'calc(-50vw + 50%)', width: '100vw' }}>
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
                            <div
                                id="bg-layer-hero"
                                className="absolute inset-0 w-full h-full opacity-1 will-change-[opacity]"
                                style={{
                                    background: getYearTheme('hero').bgGradient,
                                    filter: 'blur(60px)'
                                }}
                            />
                            {/* NOISE OVERLAY */}
                            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20" />
                        </div>

                        <div className="h-full w-full relative z-10 overflow-visible">
                            {/* The Track - full width without constraints */}
                            <div ref={trackRef} className="flex h-full items-center gap-0 w-max relative pl-20 will-change-transform shrink-0">
                                {/* THE LIVING TIMELINE LINE */}
                                <div className="absolute top-1/2 left-0 right-0 h-px bg-slate-800/50 w-full pointer-events-none">
                                    <div className="timeline-pulse absolute top-1/2 left-0 -translate-y-1/2 w-32 h-1 bg-gradient-to-r from-transparent via-sky-400 to-transparent blur-[2px]" />
                                </div>

                                {/* Introduction / Start Node */}
                                <div id="year-section-hero" className="w-[40vw] shrink-0 px-20">
                                    <h2 className="text-8xl font-black mb-6 tracking-tighter text-white/90">The <span className="text-sky-500">Work</span></h2>
                                    <p className="text-slate-400 text-xl font-mono">Exploring the evolution of Yanqing's AI Projects.</p>
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
                                                    className="stream-card relative w-[600px] h-[450px] shrink-0 group perspective-1000 transform-style-3d"
                                                >
                                                    <div className="relative w-full h-full bg-slate-900/10 backdrop-blur-2xl border border-white/5 rounded-3xl overflow-hidden hover:border-white/20 transition-shadow duration-700 hover:shadow-[0_0_50px_rgba(56,189,248,0.15)] group-hover:-translate-y-4 will-change-transform">
                                                        {/* GLOW FOLLOWER (Inner Card) */}
                                                        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none z-10"
                                                            style={{
                                                                background: `radial-gradient(circle at var(--mouse-x) var(--mouse-y), rgba(255,255,255,0.12), transparent 40%)`,
                                                                // @ts-ignore
                                                                '--mouse-x': '50%',
                                                                '--mouse-y': '50%'
                                                            }}
                                                        />
                                                        {/* PARALLAX IMAGE CONTAINER */}
                                                        <div className="absolute inset-0 overflow-hidden pointer-events-none">
                                                            <div className="absolute -inset-4 grayscale group-hover:grayscale-0 opacity-60 group-hover:opacity-80 transition-opacity duration-700">
                                                                <ProjectMedia
                                                                    src={project.coverUrl ?? project.imageUrl ?? ''}
                                                                    videoUrl={project.videoUrl}
                                                                    posterUrl={project.posterUrl}
                                                                    alt={project.title}
                                                                    className="parallax-img w-full h-full object-cover grayscale group-hover:grayscale-0"
                                                                    style={{ transform: 'scale(1.15)' }}
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
                                                                    to={project.link ?? `/project/${project.id}`}
                                                                    onClick={() => onSelectProject(project)}
                                                                >
                                                                    <span>{project.linkText ?? project.title}</span>
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
                    <section className="md:hidden relative bg-slate-950 pt-6 pb-12 px-4">
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
                                            {/* Project Image (clickable) */}
                                            <Link
                                                to={project.link ?? `/project/${project.id}`}
                                                onClick={() => onSelectProject(project)}
                                                aria-label={`View ${project.title}`}
                                                className="block relative h-48 overflow-hidden cursor-pointer"
                                            >
                                                <ProjectMedia
                                                    src={project.coverUrl ?? project.imageUrl ?? ''}
                                                    videoUrl={project.videoUrl}
                                                    posterUrl={project.posterUrl}
                                                    alt={project.title}
                                                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                                                    loading="lazy"
                                                />
                                                <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-slate-900/40 to-transparent" />

                                                {/* Year Badge */}
                                                <div className="absolute top-3 right-3 bg-blue-600/80 backdrop-blur-sm px-3 py-1 rounded-full text-xs font-bold text-white">
                                                    {year}
                                                </div>
                                            </Link>

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
                                                    to={project.link ?? `/project/${project.id}`}
                                                    onClick={() => onSelectProject(project)}
                                                    className="inline-flex items-center gap-2 text-sm font-semibold text-blue-400 hover:text-blue-300 transition-colors"
                                                >
                                                    {project.linkText ?? project.title}
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
                        <section ref={preAiSectionRef} className="relative bg-gradient-to-b from-transparent via-amber-950/10 to-transparent border-t border-amber-900/30">
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
                                                    <ProjectMedia
                                                        src={project.coverUrl ?? project.imageUrl ?? ''}
                                                        videoUrl={project.videoUrl}
                                                        posterUrl={project.posterUrl}
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
                                                        to={project.link ?? `/project/${project.id}`}
                                                        onClick={() => onSelectProject(project)}
                                                        className="inline-flex items-center gap-2 text-sm font-medium text-amber-400 hover:text-amber-300 transition-colors"
                                                    >
                                                        {project.linkText ?? project.title}
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

                    {/* AI Summary Footer */}
                    {/* Function: AI Footer — renders AI provider icons for recruiters to get portfolio summary */}
                    <footer className="relative py-16 px-4 sm:px-6 lg:px-8 border-t border-white/5 mt-24">
                        <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/95 to-transparent pointer-events-none" />

                        <div className="relative max-w-4xl mx-auto text-center space-y-8">
                            {/* Heading */}
                            <div className="space-y-3">
                                <h3 className="text-xl sm:text-2xl font-bold text-white">
                                    Analyze this portfolio with AI
                                </h3>
                                <p className="text-sm text-gray-400 max-w-xl mx-auto">
                                    Let your preferred AI summarize my technical capabilities and project highlights
                                </p>
                            </div>

                            {/* AI Provider Icons */}
                            <div className="flex flex-col items-center gap-4">
                                <div className="flex items-center justify-center gap-6 sm:gap-8">
                                {AI_PROVIDERS.map((provider) => (
                                    <motion.button
                                        key={provider.name}
                                        onClick={() => handleProviderClick(provider)}
                                        className="group relative flex flex-col items-center gap-2"
                                        whileHover={{ scale: 1.1 }}
                                        whileTap={{ scale: 0.95 }}
                                    >
                                        {/* Icon container */}
                                        <div
                                            className="relative w-14 h-14 sm:w-16 sm:h-16 rounded-xl bg-slate-900/80 border border-white/10 flex items-center justify-center backdrop-blur-sm transition-all duration-300 group-hover:border-white/30"
                                        >
                                            {/* SVG Icon */}
                                            <div className="w-8 h-8 text-gray-400 group-hover:text-white transition-colors">
                                                {provider.icon}
                                            </div>
                                            {/* Hover glow */}
                                            <div
                                                className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-20 transition-opacity"
                                                style={{ backgroundColor: provider.color }}
                                            />
                                        </div>

                                        {/* Label */}
                                        <span className="text-xs text-gray-500 group-hover:text-gray-300 transition-colors">
                                            {provider.name}
                                        </span>

                                        {/* Clipboard indicator for Claude */}
                                        {!provider.supportsUrlPrompt && (
                                            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-sky-500/80 flex items-center justify-center" title="Copies prompt to clipboard">
                                                <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                                                </svg>
                                            </span>
                                        )}
                                    </motion.button>
                                ))}
                                </div>
                                <p className="text-xs text-gray-500">
                                    Perplexity auto-answers • Others pre-fill prompt
                                </p>
                            </div>

                            {/* Copyright */}
                            <div className="pt-8 border-t border-white/5">
                                <p className="text-xs text-gray-600">
                                    &copy; {new Date().getFullYear()} Yanqing Jiang
                                </p>
                            </div>
                        </div>

                        {/* Toast notification for clipboard */}
                        <AnimatePresence>
                            {showToast && (
                                <motion.div
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: 20 }}
                                    className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 bg-sky-600 text-white text-sm rounded-lg shadow-xl z-50"
                                >
                                    Prompt copied! Paste it in Claude.
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </footer>
                </div>

                {/* Gradient animation styles */}
                <style>{`
                    .perspective-2000 { perspective: 2000px; }
                    .transform-style-3d { transform-style: preserve-3d; }
                    .will-change-transform { will-change: transform; }
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
