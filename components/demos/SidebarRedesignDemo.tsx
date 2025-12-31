
import React from 'react';
import { motion } from 'framer-motion';

/**
 * SidebarRedesignDemo Component
 * A showcase page for the SidebarV2 component.
 * Now that SidebarV2 is the main sidebar, this page serves as a documentation of its features.
 */
const SidebarRedesignDemo: React.FC = () => {
    return (
        <div className="relative min-h-full">
            <main className="flex-1 overflow-y-auto p-12 lg:p-24 relative">

                {/* Background Decoration */}
                <div className="absolute inset-0 z-0 pointer-events-none">
                    <div className="absolute top-[20%] left-[30%] w-[600px] h-[600px] bg-sky-500/5 blur-[150px] rounded-full" />
                </div>

                <div className="relative z-10 max-w-4xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.8 }}
                    >
                        <h2 className="text-sky-500 font-mono text-sm tracking-[0.4em] uppercase mb-4">Design Review</h2>
                        <h1 className="text-5xl md:text-7xl font-black italic tracking-tighter uppercase mb-8">
                            Sidebar<br />
                            <span className="text-transparent bg-clip-text bg-gradient-to-r from-white to-sky-400">Redesign V2</span>
                        </h1>

                        <div className="max-w-2xl space-y-8 text-slate-400 text-lg leading-relaxed">
                            <p>
                                This redesigned sidebar brings the high-energy, premium aesthetic of the landing page hero section into the primary navigation. It uses deep glassmorphism and subtle animations to feel integrated and alive.
                            </p>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-12">
                                <div className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:border-sky-500/30 transition-colors group">
                                    <h3 className="text-white font-bold mb-2 flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-sky-500 shadow-[0_0_8px_#0ea5e9]" />
                                        Hero Aesthetics
                                    </h3>
                                    <p className="text-sm">The brand identity now uses the same italic, extra-bold typography as the landing page, creating a cohesive visual thread throughout the site.</p>
                                </div>

                                <div className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:border-sky-500/30 transition-colors group">
                                    <h3 className="text-white font-bold mb-2 flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-purple-500 shadow-[0_0_8px_#a855f7]" />
                                        Dynamic Feedback
                                    </h3>
                                    <p className="text-sm">Interactive hover states and multi-colored tech tags provide a tactile feel to the navigation experience.</p>
                                </div>

                                <div className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:border-sky-500/30 transition-colors group">
                                    <h3 className="text-white font-bold mb-2 flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_#10b981]" />
                                        Terminal Access
                                    </h3>
                                    <p className="text-sm">The footer has been re-engineered as a "System Terminal" module with glassmorphic backgrounds and status indicators.</p>
                                </div>

                                <div className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:border-sky-500/30 transition-colors group">
                                    <h3 className="text-white font-bold mb-2 flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-amber-500 shadow-[0_0_8px_#f59e0b]" />
                                        Deep Immersion
                                    </h3>
                                    <p className="text-sm">Utilizing <code>backdrop-blur-3xl</code> and custom transitions to ensure the UI feels like a physical layer on top of a digital world.</p>
                                </div>
                            </div>

                            <div className="mt-16 pt-16 border-t border-white/5 text-slate-500 font-mono text-xs uppercase tracking-widest flex flex-col items-center">
                                <p>This redesign is now active as the primary navigation.</p>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </main>
        </div>
    );
};

export default SidebarRedesignDemo;
