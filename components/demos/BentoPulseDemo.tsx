import React, { useRef, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

// --- Grid Pulse Background ---
const BentoGridPulse: React.FC = () => {
    const [pulses, setPulses] = useState<{ id: number; x: number; y: number; direction: 'h' | 'v' }[]>([]);

    useEffect(() => {
        const interval = setInterval(() => {
            const id = Date.now();
            const direction = Math.random() > 0.5 ? 'h' : 'v';
            const pos = Math.floor(Math.random() * 20) * 5;
            setPulses(prev => [...prev.slice(-12), { id, x: direction === 'v' ? pos : -10, y: direction === 'h' ? pos : -10, direction }]);
        }, 1200);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="fixed inset-0 z-0 bg-slate-950">
            <div className="absolute inset-0 opacity-[0.04]"
                style={{
                    backgroundImage: 'linear-gradient(#38bdf8 1px, transparent 1px), linear-gradient(90deg, #38bdf8 1px, transparent 1px)',
                    backgroundSize: '4% 4%'
                }}
            />
            {pulses.map(pulse => (
                <motion.div
                    key={pulse.id}
                    className={`absolute ${pulse.direction === 'h' ? 'h-px w-32' : 'w-px h-32'} bg-gradient-to-r from-transparent via-cyan-400 to-transparent`}
                    initial={{ left: `${pulse.x}%`, top: `${pulse.y}%`, opacity: 0 }}
                    animate={{
                        left: pulse.direction === 'h' ? ['0%', '100%'] : `${pulse.x}%`,
                        top: pulse.direction === 'v' ? ['0%', '100%'] : `${pulse.y}%`,
                        opacity: [0, 1, 0]
                    }}
                    transition={{ duration: 3.5, ease: 'linear' }}
                />
            ))}
        </div>
    );
};

const BentoPulseDemo: React.FC = () => {
    const containerRef = useRef<HTMLDivElement>(null);

    useGSAP(() => {
        const tl = gsap.timeline({ defaults: { duration: 0.8, ease: 'back.out(1.2)' } });

        tl.from('.bento-cell', {
            scale: 0.95,
            opacity: 0,
            y: 20,
            stagger: 0.1,
            delay: 0.3
        });

        tl.from('.pulse-line', {
            scaleX: 0,
            duration: 1.5,
            ease: 'expo.inOut'
        }, '-=0.5');
    }, { scope: containerRef });

    return (
        <div ref={containerRef} className="relative min-h-screen text-white flex items-center justify-center p-6 bg-[#020617] font-sans">
            <BentoGridPulse />

            <div className="relative z-10 grid grid-cols-1 md:grid-cols-4 grid-rows-auto gap-4 max-w-6xl w-full h-auto">

                {/* 1. Primary Identity Cell (Double Width) */}
                <div className="bento-cell md:col-span-3 md:row-span-2 bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-[40px] p-12 flex flex-col justify-end relative overflow-hidden group">
                    <div className="pulse-line absolute top-0 left-0 h-1 bg-cyan-400 w-full" />
                    <div className="space-y-6">
                        <div className="flex items-center gap-3">
                            <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.8)]" />
                            <span className="text-xs font-mono text-slate-500 tracking-widest uppercase">System Protocol Active</span>
                        </div>
                        <h1 className="text-6xl md:text-8xl font-black tracking-tighter uppercase leading-[0.85]">
                            Intelligence<br /><span className="text-slate-600">Architect</span>
                        </h1>
                        <p className="text-slate-400 text-xl max-w-xl leading-relaxed">
                            Pioneering <span className="text-white">Generative Financial UX</span> and autonomous trade execution swarms for the next era of professional analysis.
                        </p>
                    </div>
                    {/* Abstract design element */}
                    <div className="absolute top-10 right-10 w-32 h-32 border border-white/5 rounded-full flex items-center justify-center">
                        <div className="w-16 h-16 border-2 border-cyan-500/20 rounded-full animate-pulse" />
                        <div className="absolute w-full h-[1px] bg-white/5 rotate-45" />
                        <div className="absolute w-full h-[1px] bg-white/5 -rotate-45" />
                    </div>
                </div>

                {/* 2. Key Metric Cell (Single Width) */}
                <div className="bento-cell bg-gradient-to-br from-cyan-500/10 to-transparent border border-cyan-500/20 backdrop-blur-md rounded-[40px] p-8 flex flex-col justify-between group hover:border-cyan-500/50 transition-colors">
                    <div className="text-[10px] font-mono text-cyan-400 tracking-widest uppercase">Max_Realized_Gain</div>
                    <div className="text-6xl font-black tracking-tighter text-white group-hover:scale-110 transition-transform">200%</div>
                    <div className="text-xs text-slate-500 font-mono tracking-tighter">SOUN / PUT_OPTIONS / 2025</div>
                </div>

                {/* 3. Tech Stack Orbit Cell (Single Width) */}
                <div className="bento-cell bg-slate-950 border border-white/5 rounded-[40px] p-8 flex flex-col justify-between overflow-hidden relative group">
                    <div className="absolute inset-0 bg-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                    <div className="space-y-4">
                        <div className="text-[10px] font-mono text-slate-500 tracking-widest uppercase">Stack_Control</div>
                        <div className="flex flex-wrap gap-2">
                            {['A2UI', 'LANGGRAPH', 'CLAUDE', 'GEMINI'].map(tech => (
                                <span key={tech} className="px-3 py-1 rounded-full border border-white/10 bg-white/5 text-[9px] font-mono hover:border-cyan-500 transition-colors">{tech}</span>
                            ))}
                        </div>
                    </div>
                    <div className="relative h-12 flex items-center justify-center gap-1 opacity-20">
                        {Array.from({ length: 12 }).map((_, i) => (
                            <motion.div
                                key={i}
                                className="w-1 bg-cyan-400 h-2"
                                animate={{ height: [8, 24, 8] }}
                                transition={{ duration: 1, repeat: Infinity, delay: i * 0.1 }}
                            />
                        ))}
                    </div>
                </div>

                {/* 4. Contact/Action Cell (Double Width Bottom Left) */}
                <div className="bento-cell md:col-span-2 bg-[#0a0a0a] border border-white/10 rounded-[40px] p-10 flex items-center justify-between group cursor-pointer overflow-hidden relative">
                    <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/0 to-cyan-500/5 translate-x-[-100%] group-hover:translate-x-[0%] transition-transform duration-700" />
                    <div className="space-y-1 relative z-10">
                        <div className="text-3xl font-black tracking-tight group-hover:translate-x-2 transition-transform">EXPLORE_PROFILES.exe</div>
                        <div className="text-[10px] text-slate-500 font-mono tracking-widest uppercase">LinkedIn / Medium / Email</div>
                    </div>
                    <div className="w-14 h-14 rounded-full bg-white text-slate-950 flex items-center justify-center group-hover:scale-110 transition-transform shadow-[0_0_20px_rgba(255,255,255,0.2)]">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
                    </div>
                </div>

                {/* 5. Career Pulse Cell (Double Width Bottom Right) */}
                <div className="bento-cell md:col-span-2 bg-slate-900/40 backdrop-blur-md border border-white/5 rounded-[40px] p-10 flex flex-col justify-center relative group">
                    <div className="flex justify-between items-center">
                        <div className="space-y-4">
                            <div className="text-xs font-mono text-cyan-400 tracking-widest uppercase">Active Evolution</div>
                            <div className="flex gap-4 items-center">
                                <div className="text-lg font-bold">2021 — 2026</div>
                                <div className="h-px w-20 bg-slate-800" />
                                <div className="text-lg font-bold text-slate-500">P&G SR. ANALYST</div>
                            </div>
                        </div>
                        <motion.div
                            className="w-12 h-12 rounded-xl border border-cyan-500/30 flex items-center justify-center"
                            animate={{ rotate: 360 }}
                            transition={{ duration: 10, repeat: Infinity, ease: 'linear' }}
                        >
                            <div className="w-2 h-2 bg-cyan-400 rounded-sm" />
                        </motion.div>
                    </div>
                </div>

            </div>

            <style>{`
                @font-face {
                    font-family: 'Geist';
                    src: url('https://cdn.jsdelivr.net/font-geist/1.0.0/Geist-Black.woff2') format('woff2');
                }
            `}</style>
        </div>
    );
};

export default BentoPulseDemo;
