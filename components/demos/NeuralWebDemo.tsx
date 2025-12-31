import React, { useRef, useEffect } from 'react';
import { motion, useSpring, useMotionValue, useTransform } from 'framer-motion';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

// --- ADVANCED PHYSICS BACKGROUND: LIQUID NEURAL FIELD ---
const AdvancedNeuralField: React.FC = () => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const mouse = useRef({ x: -1000, y: -1000, targetX: -1000, targetY: -1000 });

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d', { alpha: false });
        if (!ctx) return;

        let animationFrameId: number;
        let particles: any[] = [];
        const particleCount = 180;

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
                this.ease = 0.1;
                this.size = Math.random() * 2 + 0.5;
                this.color = Math.random() > 0.5 ? '#38bdf8' : '#818cf8';
            }

            update() {
                const dx = mouse.current.x - this.x;
                const dy = mouse.current.y - this.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                const force = (200 - distance) / 200;

                if (distance < 200) {
                    const angle = Math.atan2(dy, dx);
                    this.vx -= Math.cos(angle) * force * 5;
                    this.vy -= Math.sin(angle) * force * 5;
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
            // Smooth mouse move
            mouse.current.x += (mouse.current.targetX - mouse.current.x) * 0.1;
            mouse.current.y += (mouse.current.targetY - mouse.current.y) * 0.1;

            ctx.fillStyle = '#020617';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            // Connect nearby particles with glow
            ctx.lineWidth = 0.5;
            for (let i = 0; i < particles.length; i++) {
                for (let j = i + 1; j < particles.length; j++) {
                    const dx = particles[i].x - particles[j].x;
                    const dy = particles[i].y - particles[j].y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < 120) {
                        ctx.strokeStyle = `rgba(56, 189, 248, ${0.15 * (1 - dist / 120)})`;
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

    return <canvas ref={canvasRef} className="fixed inset-0 z-0 select-none bg-slate-950" />;
};

// --- CUSTOM HUD ELEMENT: THE AGENT CORE ---
const AgentCoreHUD: React.FC = () => {
    return (
        <div className="relative w-64 h-64 md:w-96 md:h-96 flex items-center justify-center">
            {/* Pulsing Outer Rings */}
            {[0, 1, 2].map(i => (
                <motion.div
                    key={i}
                    className="absolute inset-0 border border-sky-500/10 rounded-full"
                    animate={{ scale: [1, 1.4], opacity: [0.5, 0], rotate: i * 120 }}
                    transition={{ duration: 4, repeat: Infinity, delay: i * 1.3, ease: 'linear' }}
                />
            ))}

            {/* Core Geometry */}
            <div className="relative w-32 h-32 md:w-48 md:h-48 group">
                <div className="absolute inset-0 bg-sky-500/20 blur-[60px] rounded-full animate-pulse" />

                {/* Rotating Polygon (Hexagon style) */}
                <motion.div
                    className="absolute inset-0 border-2 border-sky-400 group-hover:border-white transition-colors duration-700 rounded-[30%] rotate-45 flex items-center justify-center"
                    animate={{ rotate: 405 }}
                    transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
                >
                    <div className="w-1/2 h-1/2 border border-sky-400 rounded-lg animate-ping opacity-20" />
                </motion.div>

                {/* Inner Data Spinner */}
                <motion.div
                    className="absolute inset-4 border border-dashed border-sky-400/40 rounded-full"
                    animate={{ rotate: -360 }}
                    transition={{ duration: 10, repeat: Infinity, ease: 'linear' }}
                />

                {/* Central Focus */}
                <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-4 h-4 bg-white rounded-sm shadow-[0_0_20px_white] animate-pulse" />
                </div>
            </div>

            {/* Orbiting Labels */}
            <div className="absolute inset-0 animate-spin-slow">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-8 text-[8px] font-mono tracking-widest text-sky-400 bg-slate-950 px-2 py-0.5 border border-sky-500/30 rounded">SYS_ACTIVE</div>
            </div>
        </div>
    );
};

const NeuralWebDemo: React.FC = () => {
    const containerRef = useRef<HTMLDivElement>(null);
    const mouseX = useMotionValue(0);
    const mouseY = useMotionValue(0);

    const springConfig = { stiffness: 100, damping: 30 };
    const rotateX = useSpring(useTransform(mouseY, [-0.5, 0.5], [15, -15]), springConfig);
    const rotateY = useSpring(useTransform(mouseX, [-0.5, 0.5], [-15, 15]), springConfig);

    const handleMouseMove = (e: React.MouseEvent) => {
        const x = (e.clientX - window.innerWidth / 2) / (window.innerWidth / 2);
        const y = (e.clientY - window.innerHeight / 2) / (window.innerHeight / 2);
        mouseX.set(x);
        mouseY.set(y);
    };

    useGSAP(() => {
        const tl = gsap.timeline({ defaults: { ease: 'expo.out', duration: 1.4 } });

        tl.from('.hero-main-title span', {
            y: 150,
            skewY: 10,
            opacity: 0,
            stagger: 0.1,
            rotate: 5
        });

        tl.from('.hero-sub-meta', {
            x: -40,
            opacity: 0,
            stagger: 0.1
        }, '-=1');

        tl.from('.hud-entrance', {
            scale: 0.5,
            opacity: 0,
            filter: 'blur(20px)',
            duration: 2
        }, '-=1.2');
    }, { scope: containerRef });

    return (
        <div
            ref={containerRef}
            className="relative min-h-screen text-white overflow-hidden flex items-center justify-center bg-slate-950 p-6 md:p-12"
            onMouseMove={handleMouseMove}
        >
            <AdvancedNeuralField />

            {/* Corner Decorative Elements */}
            <div className="fixed top-10 left-10 pointer-events-none z-20">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-1 bg-sky-500" />
                    <span className="text-[10px] font-mono tracking-[0.6em] text-slate-500 uppercase">A2UI_v0.8.0</span>
                </div>
            </div>

            <div className="relative z-10 max-w-7xl w-full grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr] gap-20 items-center">

                {/* Content Unit */}
                <div className="space-y-16">
                    <div className="space-y-6">
                        <div className="flex items-center gap-4 text-sky-400 font-mono text-[10px] tracking-[0.4em]">
                            <span className="px-2 py-0.5 border border-sky-400/30 rounded">PROD_ENV</span>
                            <span className="animate-pulse">● SIGNAL CAPTURED</span>
                        </div>

                        <h1 className="hero-main-title text-[clamp(4rem,10vw,8rem)] font-black leading-[0.85] tracking-tighter uppercase whitespace-pre-line">
                            <span className="inline-block">NEURAL</span><br />
                            <span className="inline-block text-transparent italic" style={{ WebkitTextStroke: '2px rgba(255,255,255,0.8)' }}>SWARMS.</span>
                        </h1>

                        <p className="hero-sub-meta text-slate-400 text-lg md:text-2xl max-w-xl font-medium leading-relaxed">
                            I engineer <span className="text-white">autonomous decision swarms</span> that harmonize complex market flows into deterministic alpha.
                        </p>
                    </div>

                    <div className="flex flex-wrap gap-8 items-center pt-8 border-t border-white/5">
                        {[
                            { label: 'SOUN_PILOT', val: '200%', tech: 'LANGGRAPH' },
                            { label: 'SYS_LATENCY', val: '5ms', tech: 'CLAUDE_SDK' },
                            { label: 'MATCH_RATE', val: '99%', tech: 'IBKR_API' }
                        ].map(m => (
                            <div key={m.label} className="hero-sub-meta space-y-2 group cursor-pointer">
                                <div className="text-[10px] font-mono text-slate-500 tracking-widest">{m.label}</div>
                                <div className="text-4xl font-black group-hover:text-sky-400 transition-colors">{m.val}</div>
                                <div className="text-[8px] font-mono text-sky-500/50 group-hover:text-sky-400">{m.tech}</div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* VISUAL UNIT: HUD & HUD-LIKE 3D TRANSFORM */}
                <div className="hud-entrance relative flex items-center justify-center perspective-2000">
                    <motion.div
                        style={{ rotateX, rotateY }}
                        className="relative z-20 flex flex-col items-center"
                    >
                        <AgentCoreHUD />

                        {/* Floating Action Button (Glass) */}
                        <div className="mt-8 relative group">
                            <div className="absolute inset-0 bg-sky-500/20 blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
                            <button className="relative px-12 py-4 bg-slate-900/40 backdrop-blur-xl border border-sky-500/30 rounded-full font-bold uppercase tracking-[0.3em] text-[10px] hover:bg-sky-500/10 hover:border-sky-400 transition-all flex items-center gap-4">
                                <span>Initialize Stream</span>
                                <div className="w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
                            </button>
                        </div>
                    </motion.div>

                    {/* Background Light Beam */}
                    <div className="absolute inset-0 bg-gradient-to-t from-sky-500/5 via-transparent to-transparent h-[150%] -top-[25%] pointer-events-none" />
                </div>
            </div>

            {/* Scroll Indicator */}
            <div className="absolute bottom-12 right-12 hidden md:block">
                <div className="flex flex-col items-center gap-4 font-mono text-[8px] tracking-[0.5em] text-slate-600 vertical-text">
                    SCROLL_TO_DESCEND
                    <div className="w-[1px] h-12 bg-slate-800 relative overflow-hidden">
                        <motion.div
                            className="absolute top-0 left-0 w-full h-1/2 bg-sky-500"
                            animate={{ y: [0, 48, 0] }}
                            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                        />
                    </div>
                </div>
            </div>

            <style>{`
                .perspective-2000 { perspective: 2000px; }
                .vertical-text { writing-mode: vertical-rl; }
                .animate-spin-slow { animation: spin 40s linear infinite; }
                @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
            `}</style>
        </div>
    );
};

export default NeuralWebDemo;
