import React, { useRef, useEffect } from 'react';
import { motion, useSpring, useMotionValue, useTransform, AnimatePresence } from 'framer-motion';
import { Linkedin, Mail } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

// Custom Colored Medium Icon (Vector Path)
const MediumIcon = ({ color = "white" }: { color?: string }) => (
    <svg viewBox="0 0 24 24" className="w-4 h-4" style={{ fill: color }}>
        <path d="M13.54 12a6.8 6.8 0 01-6.77 6.82A6.8 6.8 0 010 12a6.8 6.8 0 016.77-6.82A6.8 6.8 0 0113.54 12zM20.96 12c0 3.54-1.51 6.42-3.38 6.42-1.87 0-3.39-2.88-3.39-6.42s1.52-6.42 3.39-6.42 3.38 2.88 3.38 6.42zM24 12c0 3.17-.53 5.75-1.19 5.75-.66 0-1.19-2.58-1.19-5.75s.53-5.75 1.19-5.75C23.47 6.25 24 8.83 24 12z" />
    </svg>
);

// --- ABSTRACT DATA BACKGROUNDS ---
const ChartBackgrounds: React.FC<{ index: number }> = ({ index }) => {
    switch (index) {
        case 0: // Bar Charts
            return (
                <div className="absolute inset-0 flex items-end justify-around px-20 opacity-20 transition-opacity duration-1000">
                    {[...Array(12)].map((_, i) => (
                        <motion.div
                            key={i}
                            className="w-4 bg-sky-500 rounded-t-sm"
                            initial={{ height: 0 }}
                            animate={{ height: `${Math.random() * 60 + 20}%` }}
                            transition={{ duration: 1, delay: i * 0.05 }}
                        />
                    ))}
                </div>
            );
        case 1: // Line Chart
            return (
                <div className="absolute inset-0 px-20 flex items-center opacity-20 transition-opacity duration-1000">
                    <svg className="w-full h-1/2 overflow-visible">
                        <motion.path
                            d="M0,50 Q50,20 100,50 T200,80 T300,40 T400,60 T500,20 T600,50"
                            fill="none"
                            stroke="#8b5cf6"
                            strokeWidth="4"
                            initial={{ pathLength: 0 }}
                            animate={{ pathLength: 1 }}
                            transition={{ duration: 2 }}
                        />
                    </svg>
                </div>
            );
        case 2: // Area / Wave
            return (
                <div className="absolute inset-0 opacity-15 transition-opacity duration-1000">
                    <svg className="w-full h-full" preserveAspectRatio="none">
                        <motion.path
                            d="M0,100 C200,30 400,120 600,60 L600,150 L0,150 Z"
                            fill="url(#grad1)"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                        />
                        <defs>
                            <linearGradient id="grad1" x1="0%" y1="0%" x2="0%" y2="100%">
                                <stop offset="0%" style={{ stopColor: '#14b8a6', stopOpacity: 1 }} />
                                <stop offset="100%" style={{ stopColor: '#14b8a6', stopOpacity: 0 }} />
                            </linearGradient>
                        </defs>
                    </svg>
                </div>
            );
        default: // Network / Dots
            return (
                <div className="absolute inset-0 opacity-20 transition-opacity duration-1000">
                    {[...Array(20)].map((_, i) => (
                        <motion.div
                            key={i}
                            className="absolute w-2 h-2 bg-rose-500 rounded-full"
                            style={{
                                left: `${Math.random() * 80 + 10}%`,
                                top: `${Math.random() * 80 + 10}%`
                            }}
                            animate={{ scale: [1, 1.5, 1], opacity: [0.5, 1, 0.5] }}
                            transition={{ duration: 2, repeat: Infinity, delay: i * 0.1 }}
                        />
                    ))}
                </div>
            );
    }
};

// --- ADVANCED PHYSICS BACKGROUND: LIQUID NEURAL FIELD ---
export const AdvancedNeuralField: React.FC = () => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const mouse = useRef({ x: -1000, y: -1000, targetX: -1000, targetY: -1000 });

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d', { alpha: false });
        if (!ctx) return;

        let animationFrameId: number;
        let particles: any[] = [];
        const particleCount = 200;

        class Particle {
            x: number; y: number; originX: number; originY: number;
            vx: number; vy: number; friction: number; ease: number;
            size: number; color: string;

            constructor() {
                this.x = Math.random() * canvas!.width;
                this.y = Math.random() * canvas!.height;
                this.originX = this.x;
                this.originY = this.y;
                this.vx = 0;
                this.vy = 0;
                this.friction = 0.95;
                this.ease = 0.08;
                this.size = Math.random() * 2 + 0.5;
                this.color = Math.random() > 0.5 ? '#0ea5e9' : '#6366f1';
            }

            update() {
                const dx = mouse.current.x - this.x;
                const dy = mouse.current.y - this.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                const force = (250 - distance) / 250;

                if (distance < 250) {
                    const angle = Math.atan2(dy, dx);
                    this.vx -= Math.cos(angle) * force * 6;
                    this.vy -= Math.sin(angle) * force * 6;
                }

                this.vx *= this.friction;
                this.vy *= this.friction;
                this.x += this.vx + (this.originX - this.x) * this.ease;
                this.y += this.vy + (this.originY - this.y) * this.ease;
            }

            draw() {
                ctx!.fillStyle = this.color;
                ctx!.beginPath();
                ctx!.arc(this.x, this.y, this.size, 0, Math.PI * 2);
                ctx!.fill();
            }
        }

        const init = () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            particles = Array.from({ length: particleCount }, () => new Particle());
        };

        const render = () => {
            mouse.current.x += (mouse.current.targetX - mouse.current.x) * 0.12;
            mouse.current.y += (mouse.current.targetY - mouse.current.y) * 0.12;

            ctx.fillStyle = '#010208';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.strokeStyle = 'rgba(56, 189, 248, 0.03)';
            ctx.lineWidth = 1;
            const step = 60;
            for (let x = 0; x < canvas.width; x += step) {
                ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
            }
            for (let y = 0; y < canvas.height; y += step) {
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
            }

            ctx.lineWidth = 0.6;
            for (let i = 0; i < particles.length; i++) {
                for (let j = i + 1; j < particles.length; j++) {
                    const dx = particles[i].x - particles[j].x;
                    const dy = particles[i].y - particles[j].y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < 130) {
                        ctx.strokeStyle = `rgba(14, 165, 233, ${0.18 * (1 - dist / 130)})`;
                        ctx.beginPath();
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        ctx.stroke();
                    }
                }
            }

            particles.forEach(p => {
                p.update();
                p.draw();
            });

            animationFrameId = requestAnimationFrame(render);
        };

        const handleMouseMove = (e: MouseEvent) => {
            mouse.current.targetX = e.clientX;
            mouse.current.targetY = e.clientY;
        };

        window.addEventListener('resize', init);
        window.addEventListener('mousemove', handleMouseMove);
        init();
        render();

        return () => {
            window.removeEventListener('resize', init);
            window.removeEventListener('mousemove', handleMouseMove);
            cancelAnimationFrame(animationFrameId);
        };
    }, []);

    return <canvas ref={canvasRef} className="fixed inset-0 z-0 select-none bg-[#010208]" />;
};

// --- HOLOGRAPHIC DASHBOARD WIDGET ---
export const HolographicTerminal: React.FC = () => {
    const [lineIndex, setLineIndex] = React.useState(0);
    const lines = [
        { text: "Insight Automation", color: "rgba(14, 165, 233, 1)" },
        { text: "Enterprise Data Platform", color: "rgba(139, 92, 246, 1)" },
        { text: "Long-term Memory Agent", color: "rgba(20, 184, 166, 1)" },
        { text: "AI Agent system", color: "rgba(244, 63, 94, 1)" },
    ];

    const cycleDuration = 3000;

    useEffect(() => {
        const interval = setInterval(() => {
            setLineIndex((i) => (i + 1) % lines.length);
        }, cycleDuration);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="relative w-full h-full bg-[#050b1a]/90 border border-sky-500/30 rounded-[2.5rem] overflow-hidden flex flex-col shadow-[0_0_100px_rgba(14,165,233,0.1)] backdrop-blur-3xl">
            {/* Syncing Charts in Background */}
            <ChartBackgrounds index={lineIndex} />

            {/* Inner Glowing Rim */}
            <motion.div
                className="absolute inset-0 border border-white/5 rounded-[2.5rem] pointer-events-none transition-colors duration-1000"
                style={{ borderColor: lines[lineIndex].color.replace('1)', '0.3)') }}
            />

            {/* Minimal Header dots */}
            <div className="px-10 py-6">
                <div className="flex gap-2.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-red-500/30" />
                    <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/30" />
                    <div className="w-2.5 h-2.5 rounded-full bg-green-500/30" />
                </div>
            </div>

            {/* Main Flip Card Area (DOMINANT 85%) */}
            <div className="flex-1 p-10 flex flex-col justify-center overflow-hidden relative">
                <AnimatePresence mode="wait">
                    <motion.div
                        key={lineIndex}
                        initial={{ opacity: 0, y: 40, filter: 'blur(10px)' }}
                        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                        exit={{ opacity: 0, y: -40, filter: 'blur(10px)' }}
                        transition={{ duration: 0.8, ease: "circOut" }}
                        className="relative"
                    >
                        <span className="relative z-10 text-white text-[clamp(2rem,10vw,4.5rem)] font-black uppercase tracking-tighter leading-[1] block">
                            {lines[lineIndex].text}
                        </span>
                    </motion.div>
                </AnimatePresence>
            </div>

            {/* Social Logos Section (Colored & Smaller) */}
            <div className="flex-none h-20 flex justify-end items-center px-10 gap-4 border-t border-white/5">
                {[
                    {
                        icon: <Linkedin className="w-4 h-4" />,
                        href: 'https://www.linkedin.com/in/jiangyanqing/',
                        color: '#0A66C2',
                        label: 'LinkedIn'
                    },
                    {
                        icon: <MediumIcon color="#ffffff" />,
                        href: 'https://medium.com/@yanqing_j',
                        color: '#000000',
                        label: 'Medium'
                    },
                    {
                        icon: <Mail className="w-4 h-4" />,
                        href: 'mailto:jiangyanqing90@gmail.com',
                        color: '#94a3b8',
                        label: 'Email'
                    }
                ].map((item, idx) => (
                    <motion.a
                        key={idx}
                        href={item.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        whileHover={{ scale: 1.15, y: -3 }}
                        className="flex items-center justify-center w-8 h-8 rounded-full border border-white/10 transition-all hover:bg-white/10 group relative"
                        style={{ backgroundColor: `${item.color}20`, borderColor: `${item.color}40`, color: item.color }}
                    >
                        <div className="group-hover:brightness-125 transition-all">
                            {item.icon}
                        </div>
                        {/* Hover Tooltip */}
                        <div className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-slate-900 border border-white/10 text-white text-[7px] rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none uppercase font-mono tracking-widest whitespace-nowrap">
                            {item.label}
                        </div>
                    </motion.a>
                ))}
            </div>

            {/* SYNCED SCANLINE OVERLAY */}
            <motion.div
                key={`scan-${lineIndex}`}
                className="absolute inset-0 pointer-events-none bg-gradient-to-b from-transparent via-sky-400/20 to-transparent h-px shadow-[0_0_20px_#0ea5e9]"
                initial={{ top: '0%' }}
                animate={{ top: '100%' }}
                transition={{ duration: cycleDuration / 1000, ease: 'linear' }}
            />
        </div>
    );
};

const StreamingInsightDemo: React.FC = () => {
    const containerRef = useRef<HTMLDivElement>(null);
    const mouseX = useMotionValue(0);
    const mouseY = useMotionValue(0);

    const springConfig = { stiffness: 100, damping: 30 };
    const rotateX = useSpring(useTransform(mouseY, [-0.5, 0.5], [10, -10]), springConfig);
    const rotateY = useSpring(useTransform(mouseX, [-0.5, 0.5], [-10, 10]), springConfig);

    const handleMouseMove = (e: React.MouseEvent) => {
        const x = (e.clientX - window.innerWidth / 2) / (window.innerWidth / 2);
        const y = (e.clientY - window.innerHeight / 2) / (window.innerHeight / 2);
        mouseX.set(x);
        mouseY.set(y);
    };

    useGSAP(() => {
        const tl = gsap.timeline({ defaults: { ease: 'power4.out', duration: 1.5 } });

        // Staggered Entrance
        tl.from('.title-word', {
            y: 100,
            opacity: 0,
            skewX: -20,
            stagger: 0.1,
            filter: 'blur(20px)',
            delay: 0.5
        });

        tl.from('.header-line', { scaleX: 0, transformOrigin: 'left' }, '-=1');

        tl.from('.terminal-entrance', {
            scale: 0.9,
            opacity: 0,
            y: 40,
            duration: 2
        }, '-=1.2');

        // Scroll-triggered tilt for mobile/desktop scroll
        gsap.to('.terminal-entrance', {
            rotateX: -5,
            y: -20,
            scrollTrigger: {
                trigger: '.terminal-entrance',
                start: 'top bottom',
                end: 'bottom top',
                scrub: true
            }
        });
    }, { scope: containerRef });

    return (
        <div
            ref={containerRef}
            className="relative min-h-screen text-white overflow-x-hidden overflow-y-auto flex flex-col items-center py-20 px-6 md:p-8 bg-[#010208]"
            onMouseMove={handleMouseMove}
        >
            <AdvancedNeuralField />

            {/* Ambient Nebula Glows */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full pointer-events-none">
                <div className="absolute top-1/4 -left-1/4 w-[800px] h-[800px] bg-sky-600/10 rounded-full blur-[200px]" />
                <div className="absolute bottom-1/4 -right-1/4 w-[800px] h-[800px] bg-purple-600/10 rounded-full blur-[200px]" />
            </div>

            <div className="relative z-10 max-w-7xl w-full grid grid-cols-1 lg:grid-cols-[1fr_1.5fr] gap-12 lg:gap-12 items-center lg:min-h-[80vh]">

                {/* Information Section */}
                <div className="space-y-10 lg:pr-12">
                    <div className="space-y-6">
                        <div className="header-line h-px w-24 bg-sky-500" />

                        <h1 className="text-[clamp(3.5rem,8vw,8rem)] font-black italic tracking-tighter leading-[0.85] flex flex-col uppercase text-white">
                            <span className="title-word inline-block">Yanqing</span>
                            <span className="title-word inline-block">Jiang</span>
                        </h1>

                        <div className="name-reveal space-y-2">
                            <p className="text-sky-500 font-mono text-sm md:text-base tracking-[0.4em] uppercase">Advanced Analytics @ P&G</p>
                        </div>
                    </div>

                </div>

                {/* VISUAL SECTION: WIDE 3D DASHBOARD */}
                <div className="terminal-entrance relative flex items-center justify-center perspective-2000">
                    <motion.div
                        style={{ rotateX, rotateY }}
                        className="relative z-20 w-full max-w-[750px] aspect-[1.6/1]"
                    >
                        <div className="absolute inset-0 bg-sky-500/10 blur-[150px] rounded-full opacity-30 pointer-events-none" />
                        <HolographicTerminal />
                    </motion.div>
                </div>
            </div>

            <style>{`
                .perspective-2000 { perspective: 2000px; }
            `}</style>
        </div>
    );
};

export default StreamingInsightDemo;
