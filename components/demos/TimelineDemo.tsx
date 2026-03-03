import React, { useRef, useEffect } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import Lenis from 'lenis';
import { PROJECT_DATA } from '../../constants';
import { Link } from 'react-router-dom';

// Register GSAP plugins
gsap.registerPlugin(ScrollTrigger);

// --- Enhanced Themes for "Atmosphere Shift" ---
const YEAR_THEMES: Record<number | string, {
    gradient: string;
    bgGradient: string; // New: Global background atmosphere
    accent: string;
}> = {
    2026: {
        gradient: 'from-orange-400 to-rose-500',
        bgGradient: 'radial-gradient(circle at 50% 50%, rgba(251, 146, 60, 0.15), rgba(225, 29, 72, 0.05) 50%, transparent 100%)',
        accent: '#fb923c'
    },
    2025: {
        gradient: 'from-cyan-400 to-blue-600',
        bgGradient: 'radial-gradient(circle at 50% 50%, rgba(34, 211, 238, 0.15), rgba(37, 99, 235, 0.05) 50%, transparent 100%)',
        accent: '#22d3ee'
    },
    2024: {
        gradient: 'from-emerald-400 to-teal-600',
        bgGradient: 'radial-gradient(circle at 50% 50%, rgba(52, 211, 153, 0.15), rgba(13, 148, 136, 0.05) 50%, transparent 100%)',
        accent: '#34d399'
    },
    default: {
        gradient: 'from-purple-400 to-indigo-600',
        bgGradient: 'radial-gradient(circle at 50% 50%, rgba(168, 85, 247, 0.15), rgba(79, 70, 229, 0.05) 50%, transparent 100%)',
        accent: '#a855f7'
    }
};

const getTheme = (year: number) => YEAR_THEMES[year] || YEAR_THEMES.default;

const TimelineDemo: React.FC = () => {
    const containerRef = useRef<HTMLDivElement>(null);
    const trackRef = useRef<HTMLDivElement>(null);
    const sectionRef = useRef<HTMLDivElement>(null);
    const lenisRef = useRef<Lenis | null>(null);

    // Filter only relevant years for the demo
    const displayYears = PROJECT_DATA.filter(y => !y.hiddenOnLanding);

    // Initialize Lenis
    useEffect(() => {
        const scrollContainer = document.querySelector('main');
        if (!scrollContainer) return;

        const lenis = new Lenis({
            wrapper: scrollContainer,
            content: scrollContainer,
            duration: 1.2,
            easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
            orientation: 'vertical',
            smoothWheel: true,
        });
        lenisRef.current = lenis;

        function raf(time: number) {
            lenis.raf(time * 1000);
        }
        gsap.ticker.add(raf);

        lenis.on('scroll', ScrollTrigger.update);

        return () => {
            gsap.ticker.remove(raf);
            lenis.destroy();
        };
    }, []);

    useGSAP(() => {
        if (!trackRef.current || !sectionRef.current) return;

        const scrollContainer = document.querySelector('main');
        const track = trackRef.current;
        const section = sectionRef.current;

        // Calculate scroll amount: Total width of track minus viewport width
        const getScrollAmount = () => -(track.scrollWidth - window.innerWidth);
        const totalScroll = track.scrollWidth - window.innerWidth;

        // 1. Horizontal Scroll & pinning
        const mainTween = gsap.to(track, {
            x: getScrollAmount,
            ease: 'none',
            scrollTrigger: {
                trigger: section,
                scroller: scrollContainer,
                start: 'top top',
                end: `+=${totalScroll}`,
                pin: true,
                scrub: 1,
                invalidateOnRefresh: true,
            }
        });

        // 2. Parallax Cards (Window Effect)
        // Images move slightly inside their container against the scroll direction
        gsap.utils.toArray<HTMLElement>('.parallax-img').forEach(img => {
            gsap.to(img, {
                x: 100, // Move image 100px right while container moves left
                ease: 'none',
                scrollTrigger: {
                    trigger: img.closest('.stream-card'),
                    scroller: scrollContainer,
                    containerAnimation: mainTween,
                    start: 'left right',
                    end: 'right left',
                    scrub: true,
                }
            });
        });

        // 3. Atmosphere Shift (Background Gradients)
        // We trigger background changes based on which year section is in view
        displayYears.forEach((yearData, index) => {
            const yearSection = document.getElementById(`year-section-${yearData.year}`);
            const bgLayer = document.getElementById(`bg-layer-${yearData.year}`);
            if (yearSection && bgLayer) {
                gsap.to(bgLayer, {
                    opacity: 1,
                    duration: 1,
                    scrollTrigger: {
                        trigger: yearSection,
                        scroller: scrollContainer,
                        containerAnimation: mainTween, // Sync with horizontal scroll
                        start: 'left center', // When year section hits center
                        end: 'right center',
                        toggleActions: 'play reverse play reverse',
                        scrub: 0.5,
                    }
                });
            }
        });

        // 4. "Living Timeline" Pulse (The Data Packet)
        // A glowing dot that travels the entire length of the line
        gsap.to('.timeline-pulse', {
            x: track.scrollWidth,
            ease: 'none',
            scrollTrigger: {
                trigger: section,
                scroller: scrollContainer,
                start: 'top top',
                end: `+=${totalScroll}`,
                scrub: 0.1, // Fast reaction
            }
        });

    }, { scope: containerRef });

    return (
        <div ref={containerRef} className="bg-slate-950 text-white min-h-screen font-sans selection:bg-cyan-500/30">
            {/* INSTRUCTION HEADER */}
            <div className="fixed top-0 left-0 w-full z-50 p-6 flex justify-between items-start pointer-events-none mix-blend-difference">
                <div>
                    <h1 className="text-2xl font-bold tracking-tighter">Timeline "Wow" Factor Demo</h1>
                    <p className="text-sm opacity-70 max-w-md mt-2">
                        Scroll down. New features:
                        <br />1. <b>Atmospheric Backgrounds</b> (Colors shift per era)
                        <br />2. <b>Parallax Cards</b> (Images have depth)
                        <br />3. <b>Living Timeline</b> (Pulse travels the line)
                    </p>
                </div>
                <Link to="/" className="pointer-events-auto px-4 py-2 bg-white/10 hover:bg-white/20 backdrop-blur rounded-full text-sm font-medium transition-colors">
                    Back to Main
                </Link>
            </div>

            {/* SPACER TO FORCE SCROLL */}
            <div className="h-[50vh] flex items-center justify-center border-b border-white/5">
                <p className="animate-bounce font-mono text-slate-500">↓ SCROLL TO BEGIN TIMELINE ↓</p>
            </div>

            {/* MAIN HORIZONTAL SECTION */}
            <div ref={sectionRef} className="relative h-screen overflow-hidden">

                {/* GLOBAL ATMOSPHERE LAYERS (Fixed behind track) */}
                <div className="absolute inset-0 w-full h-full pointer-events-none z-0">
                    {displayYears.map(y => (
                        <div
                            key={`bg-${y.year}`}
                            id={`bg-layer-${y.year}`}
                            className="absolute inset-0 w-full h-full transition-opacity duration-1000 opacity-0"
                            style={{
                                background: getTheme(y.year).bgGradient,
                                filter: 'blur(60px)'
                            }}
                        />
                    ))}
                    {/* STARS / PARTICLES OVERLAY */}
                    <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20" />
                </div>

                {/* HORIZONTAL TRACK */}
                <div ref={trackRef} className="flex h-full items-center pl-20 relative z-10 w-max">

                    {/* THE LIVING TIMELINE LINE */}
                    <div className="absolute top-1/2 left-0 right-0 h-px bg-slate-800 w-full pointer-events-none">
                        <div className="timeline-pulse absolute top-1/2 left-0 -translate-y-1/2 w-32 h-1 bg-gradient-to-r from-transparent via-white to-transparent blur-[2px]" />
                    </div>

                    {/* INTRO TEXT */}
                    <div className="w-[30vw] shrink-0 px-10">
                        <h2 className="text-6xl font-black mb-4">The Work</h2>
                        <p className="text-slate-400">A journey through generative UI, agents, and data.</p>
                    </div>

                    {/* YEARS LOOP */}
                    {displayYears.map((yearGroup) => {
                        const theme = getTheme(yearGroup.year);

                        return (
                            <div
                                key={yearGroup.year}
                                id={`year-section-${yearGroup.year}`}
                                className="flex items-center gap-20 px-10 relative" // Each year is a section
                            >
                                {/* YEAR MARKER (New Style) */}
                                <div className="relative shrink-0 flex flex-col items-center gap-6">
                                    <div className="text-[12rem] font-bold leading-none text-transparent bg-clip-text bg-gradient-to-b from-white/10 to-transparent select-none absolute -top-40 left-1/2 -translate-x-1/2 blur-sm">
                                        {yearGroup.year}
                                    </div>

                                    {/* Timeline Node */}
                                    <div className="w-4 h-4 rounded-full relative z-10" style={{ background: theme.accent, boxShadow: `0 0 20px ${theme.accent}` }} />
                                    <div className="h-24 w-px bg-gradient-to-b from-slate-700 to-transparent" />
                                    <h3 className="text-xl font-mono tracking-widest uppercase" style={{ color: theme.accent }}>
                                        {yearGroup.subtitle?.replace(/[()]/g, '') || 'Era'}
                                    </h3>
                                </div>

                                {/* PROJECTS */}
                                {yearGroup.projects.map((project) => (
                                    <div
                                        key={project.id}
                                        className="stream-card relative w-[600px] h-[450px] shrink-0 group perspective-1000"
                                    >
                                        <div className="relative w-full h-full bg-slate-900/40 backdrop-blur-md border border-white/10 rounded-3xl overflow-hidden hover:border-white/30 transition-all duration-500 hover:shadow-2xl hover:shadow-cyan-500/10 group-hover:-translate-y-2">

                                            {/* PARALLAX IMAGE CONTAINER */}
                                            <div className="absolute inset-0 overflow-hidden">
                                                <img
                                                    src={project.posterUrl || project.coverUrl || project.imageUrl}
                                                    alt={project.title}
                                                    className="parallax-img w-[120%] h-full object-cover opacity-60 group-hover:opacity-80 transition-opacity duration-700 grayscale group-hover:grayscale-0"
                                                    style={{ transform: 'translateX(-50px)' }} // Initial offset for parallax
                                                />
                                                <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent" />
                                            </div>

                                            {/* CONTENT */}
                                            <div className="absolute bottom-0 left-0 w-full p-8 z-20 translate-y-4 group-hover:translate-y-0 transition-transform duration-500">
                                                <div className="flex gap-2 mb-3">
                                                    {project.technologies.slice(0, 3).map(t => (
                                                        <span key={t} className="text-[10px] uppercase font-bold px-2 py-1 rounded bg-white/5 border border-white/10 text-slate-300">
                                                            {t}
                                                        </span>
                                                    ))}
                                                </div>
                                                <h4 className="text-3xl font-bold leading-tight mb-2 group-hover:text-white transition-colors">
                                                    {project.title}
                                                </h4>
                                                <p className="text-slate-400 text-sm line-clamp-2 mb-6 group-hover:text-slate-300">
                                                    {project.cardDescription || project.description}
                                                </p>
                                                <div className="flex items-center gap-2 text-sm font-bold tracking-widest uppercase text-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity duration-500 delay-100">
                                                    <span>View Project</span>
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

            <div className="h-[50vh] flex items-center justify-center text-slate-600">
                End of Timeline
            </div>
        </div>
    );
};

export default TimelineDemo;
