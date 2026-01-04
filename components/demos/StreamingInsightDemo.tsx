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
        case 0: // Bar Charts (Insight Automation)
            return (
                <div className="absolute inset-0 flex items-end justify-around px-20 pb-10 opacity-30 transition-opacity duration-1000">
                    {[...Array(16)].map((_, i) => (
                        <motion.div
                            key={i}
                            className="w-3 bg-sky-500/60 rounded-t-lg shadow-[0_0_15px_rgba(14,165,233,0.3)]"
                            initial={{ height: 0 }}
                            animate={{ height: [`${20 + Math.random() * 40}%`, `${30 + Math.random() * 50}%`, `${20 + Math.random() * 40}%`] }}
                            transition={{
                                duration: 2 + Math.random() * 2,
                                repeat: Infinity,
                                repeatType: 'reverse',
                                delay: i * 0.1
                            }}
                        />
                    ))}
                </div>
            );
        case 1: // Data Platform (Enterprise Data Platform) - Data Grid/Circuits
            return (
                <div className="absolute inset-0 px-20 flex items-center justify-center opacity-25 transition-opacity duration-1000">
                    <div className="relative w-full h-full">
                        {/* Grid lines */}
                        <div className="absolute inset-0 grid grid-cols-8 grid-rows-6">
                            {[...Array(48)].map((_, i) => (
                                <div key={i} className="border-[0.5px] border-purple-500/10 h-full w-full" />
                            ))}
                        </div>
                        {/* Moving Data Packets */}
                        {[...Array(8)].map((_, i) => (
                            <motion.div
                                key={i}
                                className="absolute w-12 h-1 bg-gradient-to-r from-transparent via-purple-500 to-transparent blur-[1px]"
                                style={{
                                    top: `${(i % 6) * 16.6}%`,
                                    left: '-50px'
                                }}
                                animate={{ left: ['0%', '100%'] }}
                                transition={{
                                    duration: 3 + Math.random() * 4,
                                    repeat: Infinity,
                                    ease: 'linear',
                                    delay: i * 0.5
                                }}
                            />
                        ))}
                        {[...Array(8)].map((_, i) => (
                            <motion.div
                                key={`v-${i}`}
                                className="absolute w-1 h-12 bg-gradient-to-b from-transparent via-violet-400 to-transparent blur-[1px]"
                                style={{
                                    left: `${(i % 8) * 12.5}%`,
                                    top: '-50px'
                                }}
                                animate={{ top: ['0%', '100%'] }}
                                transition={{
                                    duration: 4 + Math.random() * 3,
                                    repeat: Infinity,
                                    ease: 'linear',
                                    delay: i * 0.7
                                }}
                            />
                        ))}
                    </div>
                </div>
            );
        case 2: // Memory Agent (Long-term Memory Agent) - Sophisticated Neural Orb
            return (
                <div className="absolute inset-0 flex items-center justify-center opacity-30 transition-opacity duration-1000">
                    <div className="relative w-80 h-80 flex items-center justify-center">
                        {/* Concentric HUD Rings */}
                        <motion.div
                            className="absolute inset-0 border-[0.5px] border-teal-500/20 rounded-full"
                            animate={{ rotate: 360 }}
                            transition={{ duration: 40, repeat: Infinity, ease: 'linear' }}
                        />
                        <motion.div
                            className="absolute inset-12 border-[0.5px] border-teal-500/20 rounded-full border-dashed"
                            animate={{ rotate: -360 }}
                            transition={{ duration: 30, repeat: Infinity, ease: 'linear' }}
                        />
                        <motion.div
                            className="absolute inset-24 border-[0.5px] border-teal-500/10 rounded-full"
                            animate={{ scale: [1, 1.1, 1], opacity: [0.1, 0.3, 0.1] }}
                            transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
                        />

                        {/* Floating Memory Nodes */}
                        {[...Array(16)].map((_, i) => {
                            const angle = (i / 16) * Math.PI * 2;
                            return (
                                <motion.div
                                    key={i}
                                    className="absolute w-1.5 h-1.5 bg-teal-500 rounded-full shadow-[0_0_12px_rgba(20,184,166,0.8)]"
                                    animate={{
                                        x: [Math.cos(angle) * 70, Math.cos(angle) * 130, Math.cos(angle) * 70],
                                        y: [Math.sin(angle) * 70, Math.sin(angle) * 130, Math.sin(angle) * 70],
                                        opacity: [0.2, 0.9, 0.2],
                                        scale: [1, 1.4, 1]
                                    }}
                                    transition={{
                                        duration: 4 + Math.random() * 2,
                                        repeat: Infinity,
                                        ease: "easeInOut",
                                        delay: i * 0.15
                                    }}
                                />
                            );
                        })}

                        {/* Synaptic Pulses */}
                        <svg className="absolute inset-0 w-full h-full overflow-visible pointer-events-none opacity-20">
                            {[...Array(8)].map((_, i) => {
                                const angle = (i / 8) * Math.PI * 2;
                                return (
                                    <motion.line
                                        key={i}
                                        x1="50%" y1="50%"
                                        x2={`${50 + Math.cos(angle) * 35}%`}
                                        y2={`${50 + Math.sin(angle) * 35}%`}
                                        stroke="#14b8a6"
                                        strokeWidth="0.5"
                                        animate={{ opacity: [0, 0.6, 0] }}
                                        transition={{ duration: 2, repeat: Infinity, delay: i * 0.25 }}
                                    />
                                );
                            })}
                        </svg>

                        {/* Central Data Core */}
                        <motion.div
                            className="w-4 h-4 bg-white rounded-full shadow-[0_0_20px_#14b8a6]"
                            animate={{ scale: [0.8, 1.2, 0.8], opacity: [0.4, 1, 0.4] }}
                            transition={{ duration: 3, repeat: Infinity }}
                        />
                    </div>
                </div>
            );
        case 3: // AI Swarm (AI Agent system) - Orbiting Agents
            return (
                <div className="absolute inset-0 flex items-center justify-center opacity-20 transition-opacity duration-1000">
                    <div className="relative w-full h-full flex items-center justify-center">
                        {[...Array(5)].map((_, i) => (
                            <motion.div
                                key={i}
                                className="absolute border border-rose-500/20 rounded-full"
                                style={{
                                    width: `${200 + i * 80}px`,
                                    height: `${200 + i * 80}px`
                                }}
                                animate={{ rotate: i % 2 === 0 ? 360 : -360 }}
                                transition={{ duration: 15 + i * 5, repeat: Infinity, ease: 'linear' }}
                            >
                                <motion.div
                                    className="absolute top-0 left-1/2 -translate-x-1/2 w-4 h-4 bg-rose-500 rounded-full shadow-[0_0_15px_rgba(244,63,94,0.5)]"
                                    animate={{ scale: [1, 1.2, 1] }}
                                    transition={{ duration: 2, repeat: Infinity }}
                                />
                                <div className="absolute top-1/2 left-0 -translate-y-1/2 w-1.5 h-1.5 bg-rose-400/40 rounded-full" />
                            </motion.div>
                        ))}
                        {/* Core Targeting System */}
                        <div className="w-32 h-32 border-2 border-dashed border-rose-500/10 rounded-full flex items-center justify-center">
                            <motion.div
                                className="w-16 h-16 border border-rose-500/30 rounded-full"
                                animate={{ scale: [0.8, 1.1, 0.8], opacity: [0.1, 0.4, 0.1] }}
                                transition={{ duration: 4, repeat: Infinity }}
                            />
                        </div>
                    </div>
                </div>
            );
        default:
            return null;
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
            driftX: number; driftY: number; driftSpeed: number;

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
                this.driftX = Math.random() * 2000;
                this.driftY = Math.random() * 2000;
                this.driftSpeed = 0.001 + Math.random() * 0.002;
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

                // Add autonomous drift
                const driftAmount = 0.5;
                const dx_drift = Math.cos(this.driftX) * driftAmount;
                const dy_drift = Math.sin(this.driftY) * driftAmount;
                this.driftX += this.driftSpeed;
                this.driftY += this.driftSpeed;

                this.x += this.vx + dx_drift + (this.originX - this.x) * this.ease;
                this.y += this.vy + dy_drift + (this.originY - this.y) * this.ease;
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

    return <canvas id="neural-field-canvas" ref={canvasRef} className="fixed inset-0 z-0 select-none bg-[#010208]" />;
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
                        <div className="absolute -top-12 left-1/2 -translate-x-1/2 px-4 py-1.5 bg-slate-900 border border-white/30 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none uppercase font-mono tracking-[0.2em] whitespace-nowrap shadow-[0_0_20px_rgba(0,0,0,0.5)]">
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
