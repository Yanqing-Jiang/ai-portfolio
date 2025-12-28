import React, { useRef, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import type { Project, ProjectYear } from '../types';
import { motion } from 'framer-motion';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
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
    const heroRef = useRef<HTMLElement>(null);
    const timelineLineRef = useRef<SVGLineElement>(null);
    const yearSectionsRef = useRef<(HTMLDivElement | null)[]>([]);

    const [pageMouse, setPageMouse] = useState<{ x: number; y: number } | null>(null);

    // Filter and organize projects
    const displayYears = useMemo(
        () => projectData.filter(group => !group.hiddenOnLanding),
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



    // GSAP Animations
    useGSAP(() => {
        const ctx = gsap.context(() => {
            // Hero staggered animation
            const heroTl = gsap.timeline({ defaults: { ease: 'power3.out' } });

            heroTl
                .from('.hero-name', {
                    opacity: 0,
                    y: 60,
                    duration: 1,
                    delay: 0.2
                })
                .from('.hero-title', {
                    opacity: 0,
                    y: 40,
                    duration: 0.8
                }, '-=0.5')
                .from('.hero-social', {
                    opacity: 0,
                    y: 30,
                    stagger: 0.1,
                    duration: 0.6
                }, '-=0.4')
                .from('.hero-morph', {
                    opacity: 0,
                    scale: 0.9,
                    duration: 0.8
                }, '-=0.3');

            // Timeline line draw animation
            if (timelineLineRef.current) {
                gsap.fromTo(
                    timelineLineRef.current,
                    { attr: { y2: '0%' } },
                    {
                        attr: { y2: '100%' },
                        ease: 'none',
                        scrollTrigger: {
                            trigger: '.timeline-container',
                            start: 'top 80%',
                            end: 'bottom 20%',
                            scrub: 1,
                        },
                    }
                );
            }

            // Year sections - sticky labels and card animations
            yearSectionsRef.current.forEach((section) => {
                if (!section) return;

                const yearLabel = section.querySelector('.year-label');
                const cards = section.querySelectorAll('.project-card');

                // Sticky year label
                if (yearLabel) {
                    ScrollTrigger.create({
                        trigger: section,
                        start: 'top 100px',
                        end: 'bottom 200px',
                        pin: yearLabel,
                        pinSpacing: false,
                    });
                }

                // Staggered card reveals
                gsap.from(cards, {
                    opacity: 0,
                    y: 80,
                    stagger: 0.15,
                    duration: 0.8,
                    ease: 'power2.out',
                    scrollTrigger: {
                        trigger: section,
                        start: 'top 70%',
                        toggleActions: 'play none none reverse',
                    },
                });

                // Year node pulse animation
                const yearNode = section.querySelector('.year-node');
                if (yearNode) {
                    gsap.from(yearNode, {
                        scale: 0,
                        duration: 0.5,
                        ease: 'back.out(1.7)',
                        scrollTrigger: {
                            trigger: section,
                            start: 'top 80%',
                            toggleActions: 'play none none reverse',
                        },
                    });
                }
            });

        }, containerRef);

        return () => ctx.revert();
    }, { scope: containerRef, dependencies: [displayYears] });

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
                {/* Mouse follower glow */}
                <div
                    aria-hidden
                    className="pointer-events-none fixed inset-0 z-10"
                    style={{
                        background: pageMouse
                            ? `radial-gradient(400px 400px at ${pageMouse.x}px ${pageMouse.y}px, rgba(56,189,248,0.15), transparent 70%)`
                            : 'radial-gradient(400px 400px at 50% 10%, rgba(56,189,248,0.15), transparent 70%)',
                        transition: 'background 200ms ease-out',
                    }}
                />

                <div className="relative z-20">
                    {/* Hero Section */}
                    <section ref={heroRef} className="relative overflow-hidden border-b border-white/5">
                        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 sm:py-20 md:py-28">
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:items-center">
                                {/* Left: Name and info */}
                                <div className="flex flex-col">
                                    <h1
                                        className="hero-name text-balance font-extrabold text-white tracking-[-0.02em] leading-[1.1]"
                                        style={{ fontSize: 'clamp(48px, 5vw, 64px)' }}
                                    >
                                        Yanqing Jiang
                                    </h1>
                                    <div
                                        className="hero-title mt-4 font-semibold text-sky-300"
                                        style={{ fontSize: 'clamp(18px, 2.2vw, 24px)' }}
                                    >
                                        Advanced Analytics @ P&amp;G
                                    </div>
                                    <div className="mt-8 flex flex-wrap items-center gap-6 text-gray-400">
                                        {contactLinks.map((item) => (
                                            <motion.a
                                                key={item.label}
                                                href={item.href}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="hero-social group flex flex-col items-center hover:text-white transition-colors"
                                                whileHover={{ scale: 1.05 }}
                                                whileTap={{ scale: 0.95 }}
                                            >
                                                <div className="flex items-center justify-center rounded-full border border-white/20 bg-white/5 p-3 backdrop-blur-sm group-hover:border-sky-400/50 group-hover:bg-sky-500/10 transition-all">
                                                    {item.icon}
                                                </div>
                                                <span className="mt-2 text-xs uppercase tracking-wider opacity-70 group-hover:opacity-100 transition-opacity">
                                                    {item.label}
                                                </span>
                                            </motion.a>
                                        ))}
                                    </div>
                                </div>

                                {/* Right: Animated keywords */}
                                <div className="hero-morph relative flex justify-center lg:justify-end">
                                    <div className="relative z-10 w-full max-w-xl text-left lg:text-right">
                                        <div className="text-2xl sm:text-3xl md:text-4xl font-bold bg-gradient-to-r from-sky-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                                            AI Agent Systems
                                        </div>
                                        <div className="mt-2 text-lg sm:text-xl text-gray-400">
                                            Insight Automation • Enterprise Data Platform
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Timeline Section */}
                    <div className="timeline-container max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
                        <h2
                            className="font-black text-left text-balance bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-purple-500 to-pink-500 mb-16"
                            style={{ fontSize: 'clamp(36px, 4vw, 52px)', textShadow: '0 0 60px rgba(56, 189, 248, 0.2)' }}
                        >
                            Project Evolution
                        </h2>

                        <div className="relative">
                            {/* Timeline line (SVG) */}
                            <div className="absolute left-8 md:left-16 top-0 bottom-0 w-px">
                                <svg className="w-full h-full" preserveAspectRatio="none">
                                    <defs>
                                        <linearGradient id="timeline-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                                            <stop offset="0%" stopColor="#38bdf8" stopOpacity="1" />
                                            <stop offset="50%" stopColor="#a855f7" stopOpacity="1" />
                                            <stop offset="100%" stopColor="#ec4899" stopOpacity="1" />
                                        </linearGradient>
                                    </defs>
                                    <line
                                        ref={timelineLineRef}
                                        x1="50%"
                                        y1="0%"
                                        x2="50%"
                                        y2="0%"
                                        stroke="url(#timeline-gradient)"
                                        strokeWidth="2"
                                    />
                                    {/* Background line */}
                                    <line
                                        x1="50%"
                                        y1="0%"
                                        x2="50%"
                                        y2="100%"
                                        stroke="rgba(255,255,255,0.1)"
                                        strokeWidth="1"
                                    />
                                </svg>
                            </div>

                            {/* Year sections */}
                            <div className="space-y-20">
                                {displayYears.map(({ year, subtitle, projects, label }, yearIndex) => (
                                    <div
                                        key={year}
                                        ref={(el) => { yearSectionsRef.current[yearIndex] = el; }}
                                        className="relative pl-20 md:pl-32"
                                    >
                                        {/* Year node on timeline */}
                                        <div className="year-node absolute left-6 md:left-14 top-0 w-4 h-4 rounded-full bg-gradient-to-br from-sky-400 to-purple-500 shadow-lg shadow-sky-500/30 ring-4 ring-slate-950" />

                                        {/* Sticky year label */}
                                        <div className="year-label mb-8">
                                            <h3 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-white">
                                                {label ?? year}
                                            </h3>
                                            {subtitle && (
                                                <p className="mt-2 text-base sm:text-lg text-gray-400">{subtitle}</p>
                                            )}
                                        </div>

                                        {/* Project cards */}
                                        <div className="space-y-8">
                                            {projects.map((project) => {
                                                const previewDescription = project.cardDescription ?? project.description;
                                                const truncatedDescription =
                                                    previewDescription.length > 180
                                                        ? `${previewDescription.substring(0, 180)}...`
                                                        : previewDescription;

                                                return (
                                                    <Link
                                                        key={project.id}
                                                        to={`/project/${project.id}`}
                                                        onClick={() => onSelectProject(project)}
                                                        className="project-card block group rounded-xl overflow-hidden border border-gray-700/50 bg-gray-800/40 backdrop-blur-sm hover:bg-gray-800/60 hover:border-sky-500/30 transition-all duration-300 shadow-lg hover:shadow-sky-500/10"
                                                    >
                                                        <div className="flex flex-col md:flex-row">
                                                            {/* Image */}
                                                            <div className="w-full md:w-2/5 shrink-0 overflow-hidden bg-gray-900/50">
                                                                <img
                                                                    src={project.coverUrl ?? project.imageUrl}
                                                                    alt={project.title}
                                                                    loading="lazy"
                                                                    className="w-full h-48 sm:h-56 md:h-full object-cover transition-transform duration-500 group-hover:scale-105"
                                                                />
                                                            </div>

                                                            {/* Content */}
                                                            <div className="flex-1 p-5 sm:p-6 lg:p-8 flex flex-col justify-center">
                                                                <h4 className="text-lg sm:text-xl md:text-2xl font-bold text-white mb-3 group-hover:text-sky-300 transition-colors">
                                                                    {project.title}
                                                                </h4>
                                                                <p className="text-gray-300 text-sm sm:text-base leading-relaxed mb-4">
                                                                    {truncatedDescription}
                                                                </p>
                                                                <div className="flex flex-wrap gap-2 mt-auto">
                                                                    {project.technologies.slice(0, 5).map(tech => (
                                                                        <span
                                                                            key={tech}
                                                                            className={`text-xs sm:text-sm font-medium px-2.5 py-1 rounded-md transition-colors duration-200 ${getTechBadgeClass(tech)}`}
                                                                        >
                                                                            {tech}
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </Link>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
};

export default LandingPageFlow;
