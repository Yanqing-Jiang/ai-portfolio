
import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence, useSpring } from 'framer-motion';
import { Link } from 'react-router-dom';
import type { Project, ProjectYear } from '../types';
import { SignInIcon } from './icons/SignInIcon';
import { ChevronDown } from 'lucide-react';
import { authService, type AuthState } from '../services/auth';
import { AuthModal } from './AuthModal';

interface SidebarV2Props {
    projectData: ProjectYear[];
    selectedProject: Project | null;
    onSelectProject: (project: Project) => void;
    isSidebarOpen: boolean;
    onGoHome: () => void;
}

/**
 * Function: SidebarV2 - called from Layout in App.tsx to render the project navigation shell; renders project list, interactive hologram preview, and auth entry; forwards selection to onSelectProject and active state via selectedProject; exists to provide the "Neural Portal" sidebar UX.
 *
 * FEATURES:
 * - Pure Visuals: No year headers or bullets. The year exists solely as a 3D watermark.
 * - Interactive Portal: Hovering project titles creates a "Holographic Preview Portal".
 * - Clean Typography: Zero subtitles or descriptive text clutter.
 * - Motion-Reactive: Deep parallax and mouse-following lighting.
 */

const YEAR_COLORS: Record<number | string, { accent: string, glow: string }> = {
    2026: { accent: '#fb923c', glow: 'rgba(251, 146, 60, 0.5)' }, // Orange-Rose (Future Era)
    2025: { accent: '#22d3ee', glow: 'rgba(34, 211, 238, 0.5)' }, // Cyan-Blue (Current Era)
    2024: { accent: '#34d399', glow: 'rgba(52, 211, 153, 0.5)' }, // Emerald-Teal (Agentic Era)
    2023: { accent: '#a855f7', glow: 'rgba(168, 85, 247, 0.5)' }, // Purple-Indigo (Foundation Era)
    2022: { accent: '#f43f5e', glow: 'rgba(244, 63, 94, 0.5)' },  // Rose (Genesis)
    2021: { accent: '#f59e0b', glow: 'rgba(245, 158, 11, 0.5)' }, // Amber (Pre-AI/Legacy)
    default: { accent: '#0ea5e9', glow: 'rgba(14, 165, 233, 0.5)' }
};

const SidebarV2: React.FC<SidebarV2Props> = ({
    projectData,
    selectedProject,
    onSelectProject,
    isSidebarOpen,
    onGoHome
}) => {
    const [authState, setAuthState] = useState<AuthState>({ user: null, loading: true, error: null });
    const [showAuthModal, setShowAuthModal] = useState(false);
    const [hoveredProject, setHoveredProject] = useState<Project | null>(null);
    const [collapsedYears, setCollapsedYears] = useState<Record<number, boolean>>(() => {
        // Default 2021 to collapsed
        return { 2021: true };
    });

    const toggleYear = (year: number) => {
        setCollapsedYears(prev => ({
            ...prev,
            [year]: !prev[year]
        }));
    };

    // Mouse position for lighting and portal positioning
    const mouseX = useSpring(0, { stiffness: 50, damping: 20 });
    const mouseY = useSpring(0, { stiffness: 50, damping: 20 });

    const sidebarRef = useRef<HTMLDivElement>(null);

    // Function: handleProjectClick - called from sidebar project links; clears the hologram preview then forwards the project to the parent onSelectProject so navigation/refresh logic can run; exists to hide the preview when a project is chosen.
    const handleProjectClick = (project: Project) => {
        setHoveredProject(null); // hide hologram preview on click/refresh
        onSelectProject(project);
    };

    useEffect(() => {
        const unsubscribe = authService.subscribe(setAuthState);
        return unsubscribe;
    }, []);

    const handleMouseMove = (e: React.MouseEvent) => {
        if (!sidebarRef.current) return;
        const rect = sidebarRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        mouseX.set(x);
        mouseY.set(y);
    };

    const handleAuthAction = () => {
        if (authState.user) {
            authService.signOut();
        } else {
            setShowAuthModal(true);
        }
    };

    return (
        <>
            {/* 0. MOBILE BACKDROP */}
            <AnimatePresence>
                {isSidebarOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onGoHome} // Use goHome or a specific close handler if available
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden"
                    />
                )}
            </AnimatePresence>

            <aside
                ref={sidebarRef}
                onMouseMove={handleMouseMove}
                className={`
          fixed inset-y-0 left-0 z-50
          h-full bg-slate-950 border-r border-white/5 flex flex-col shrink-0 
          transition-all duration-700 ease-[cubic-bezier(0.16,1,0.3,1)]
          overflow-x-hidden
          ${isSidebarOpen
                        ? 'w-[85vw] sm:w-80 opacity-100 translate-x-0 shadow-[20px_0_100px_rgba(0,0,0,0.8)]'
                        : 'w-0 p-0 overflow-hidden border-none opacity-0 -translate-x-full'
                    }
          md:translate-x-0 md:relative
        `}
            >
                {/* 1. ATMOSPHERIC BACKGROUND LAYER */}
                <div className="absolute inset-0 overflow-hidden pointer-events-none">
                    {/* Noise Texture (Aligned with Landing Page) */}
                    <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20" />

                    {/* Reactive Spotlight */}
                    <motion.div
                        className="absolute w-[600px] h-[600px] bg-sky-500/5 blur-[120px] rounded-full"
                        style={{ x: mouseX, y: mouseY, translateX: '-50%', translateY: '-50%' }}
                    />

                    {/* Moving Mesh Gradient */}
                    <div className="absolute inset-0 opacity-[0.02]"
                        style={{
                            backgroundImage: 'radial-gradient(circle at 2px 2px, #0ea5e9 1px, transparent 0)',
                            backgroundSize: '40px 40px'
                        }} />
                </div>

                <div className="flex flex-col flex-1 h-full relative z-10 px-8 pt-6 pb-4 overflow-hidden">

                    {/* 2. BRAND IDENTITY */}
                    <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mb-4"
                    >
                        <button onClick={onGoHome} className="flex items-center gap-5 group transition-all">
                            <div className="relative w-14 h-14">
                                {/* 1. HUD Orbitals (Creative Fix) */}
                                <motion.div
                                    className="absolute inset-[-4px] border border-sky-400/20 rounded-full z-0"
                                    animate={{ rotate: 360 }}
                                    transition={{ duration: 15, repeat: Infinity, ease: 'linear' }}
                                >
                                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1.5 h-1.5 bg-sky-400 rounded-full shadow-[0_0_10px_#38bdf8]" />
                                </motion.div>

                                {/* 2. Main Portal Container */}
                                <div className="relative w-full h-full rounded-full overflow-hidden border border-white/10 bg-slate-900/40 backdrop-blur-sm z-10 shadow-[inner_0_0_20px_rgba(14,165,233,0.2)]">
                                    {/* Atmospheric Glow */}
                                    <div className="absolute inset-0 bg-sky-500/10 blur-md" />

                                    {/* THE FIX: mix-blend-screen makes the black background of the image transparent */}
                                    <img
                                        src="https://yanqinghot.blob.core.windows.net/public-access/Profile%20Logo%20black.png"
                                        alt="Logo"
                                        className="w-full h-full object-contain relative z-20 mix-blend-screen scale-110 brightness-110 contrast-125"
                                    />

                                    {/* 4. Glass Reflection Overlay */}
                                    <div className="absolute inset-0 z-40 bg-gradient-to-tr from-transparent via-white/5 to-white/10 pointer-events-none" />
                                </div>

                                {/* 5. Exterior Glow */}
                                <div className="absolute inset-0 bg-sky-500/20 blur-2xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
                            </div>
                            <div className="flex flex-col">
                                <h1 className="text-2xl font-black italic tracking-tighter uppercase text-white leading-[0.8]">
                                    Yanqing<br />
                                    <span className="text-sky-500 text-xl">AI Portfolio</span>
                                </h1>
                            </div>
                        </button>
                    </motion.div>

                    {/* 3. PURE TIMELINE NAVIGATION */}
                    <nav className="flex-1 overflow-y-auto overflow-x-hidden pr-6 -mr-6 sidebar-scrollbar custom-scrollbar relative">
                        <div className="flex flex-col gap-4 py-1">
                            {projectData.map(({ year, projects, label }) => {
                                const isCollapsed = collapsedYears[year];
                                return (
                                    <div key={year} className="mb-2">
                                        {/* RESTORED: Standard Year Header with working Toggle */}
                                        <div
                                            onClick={() => toggleYear(year)}
                                            className="flex items-center justify-between mb-2 group/header cursor-pointer"
                                        >
                                            <div className="flex items-center gap-2">
                                                <h3 className={`font-black text-white tracking-tighter ${year === 2021 ? 'text-lg' : 'text-2xl uppercase'}`}>{year === 2021 ? 'Pre-AI Projects' : year}</h3>
                                                {year !== 2021 && label && (
                                                    <span className="text-[10px] font-black text-slate-500/50 uppercase tracking-tight truncate max-w-[150px] mt-1">
                                                        ({label})
                                                    </span>
                                                )}
                                            </div>
                                            <ChevronDown
                                                className={`w-4 h-4 text-sky-500 transition-transform duration-300 ${isCollapsed ? '-rotate-90' : 'rotate-0'}`}
                                            />
                                        </div>

                                        {/* RESTORED: Tree Layout with Left Border - Collapsible */}
                                        <AnimatePresence>
                                            {!isCollapsed && (
                                                <motion.ul
                                                    initial={{ height: 0, opacity: 0 }}
                                                    animate={{ height: 'auto', opacity: 1 }}
                                                    exit={{ height: 0, opacity: 0 }}
                                                    transition={{ duration: 0.3, ease: "easeInOut" }}
                                                    className="relative space-y-1 border-l border-white/10 ml-2 pl-6 overflow-hidden"
                                                >
                                                    {projects.map((project, idx) => {
                                                        const isActive = selectedProject?.id === project.id;
                                                        const theme = YEAR_COLORS[year] || YEAR_COLORS.default;

                                                        return (
                                                            <motion.li
                                                                key={project.id}
                                                                initial={{ opacity: 0, x: -10 }}
                                                                animate={{ opacity: 1, x: 0 }}
                                                                transition={{ delay: idx * 0.03 }}
                                                            >
                                                                <Link
                                                                    to={`/project/${project.id}`}
                                                                    onClick={() => handleProjectClick(project)}
                                                                    onMouseEnter={() => setHoveredProject(project)}
                                                                    onMouseLeave={() => setHoveredProject(null)}
                                                                    className={`
                                                                    group/link relative block py-1 px-4 -mx-2 rounded-xl transition-all duration-500 border border-transparent
                                                                    ${isActive
                                                                            ? 'bg-white/[0.03] border-white/10 shadow-[inner_0_0_20px_rgba(255,255,255,0.02)] overflow-hidden'
                                                                            : 'opacity-70 hover:opacity-100 hover:bg-white/5'}
                                                                `}
                                                                >
                                                                    {/* 1. SOPHISTICATED INDICATOR NODE */}
                                                                    {isActive && (
                                                                        <>
                                                                            {/* Left Vertical Bar */}
                                                                            <motion.div
                                                                                layoutId="active-pill"
                                                                                className="absolute left-0 top-[20%] bottom-[20%] w-1 rounded-r-full z-20"
                                                                                style={{
                                                                                    background: theme.accent,
                                                                                    boxShadow: `0 0 15px ${theme.accent}, 0 0 30px ${theme.accent}40`
                                                                                }}
                                                                                initial={{ opacity: 0, scaleY: 0 }}
                                                                                animate={{ opacity: 1, scaleY: 1 }}
                                                                                transition={{ type: 'spring', damping: 15, stiffness: 200 }}
                                                                            />
                                                                            {/* Subtle Gradient Wash */}
                                                                            <div
                                                                                className="absolute inset-0 pointer-events-none opacity-20"
                                                                                style={{
                                                                                    background: `linear-gradient(90deg, ${theme.accent}40 0%, transparent 60%)`
                                                                                }}
                                                                            />
                                                                            {/* Moving Pulse Scanline */}
                                                                            <motion.div
                                                                                className="absolute inset-x-0 h-px bg-white/20 z-10 pointer-events-none"
                                                                                animate={{ top: ['0%', '100%'], opacity: [0, 0.5, 0] }}
                                                                                transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
                                                                            />
                                                                        </>
                                                                    )}

                                                                    <span className={`text-[14px] font-bold tracking-tight transition-all duration-500 relative z-10 block
                                                                        ${isActive
                                                                            ? 'text-white translate-x-1'
                                                                            : 'text-slate-400 group-hover/link:text-white group-hover/link:translate-x-1'}`}>
                                                                        {project.title}
                                                                        {isActive && (
                                                                            <motion.span
                                                                                layoutId="active-dot"
                                                                                className="inline-block ml-2 w-1 h-1 rounded-full mb-0.5"
                                                                                style={{ background: theme.accent, boxShadow: `0 0 8px ${theme.accent}` }}
                                                                                animate={{ opacity: [0.4, 1, 0.4] }}
                                                                                transition={{ duration: 2, repeat: Infinity }}
                                                                            />
                                                                        )}
                                                                    </span>
                                                                </Link>
                                                            </motion.li>
                                                        );
                                                    })}

                                                </motion.ul>
                                            )}
                                        </AnimatePresence>
                                    </div>
                                );
                            })}
                        </div>
                    </nav>



                    <div className="mt-auto pt-4 border-t border-white/5">
                        <motion.button
                            onClick={handleAuthAction}
                            whileHover={{ x: 5 }}
                            className="flex items-center gap-4 w-full group py-4 px-4 bg-sky-500/5 border border-sky-500/10 hover:bg-sky-500/10 hover:border-sky-500/30 rounded-2xl transition-all duration-500"
                        >
                            <div className="w-10 h-10 rounded-full border border-sky-500/20 flex items-center justify-center text-sky-500 group-hover:scale-110 transition-all duration-500">
                                <SignInIcon />
                            </div>
                            <div className="flex flex-col text-left">
                                <span className="text-[10px] font-black text-sky-500/70 uppercase tracking-[0.2em] leading-none mb-1">
                                    {authState.user ? 'Access Terminal' : 'Sign In / Sign Up'}
                                </span>
                                <span className="text-[11px] font-bold text-white/80 group-hover:text-white transition-colors">
                                    {authState.user ? authState.user.email : 'to unlock more usage'}
                                </span>
                            </div>
                        </motion.button>
                    </div>
                </div>

                <style dangerouslySetInnerHTML={{
                    __html: `
        @keyframes scan-y {
          0% { transform: translateY(0%); }
          100% { transform: translateY(200%); }
        }
        .animate-scan-y {
          animation: scan-y 3s linear infinite;
        }
        .animate-pulse-subtle {
          animation: pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 0.1; }
        }
        .sidebar-scrollbar::-webkit-scrollbar {
          width: 0px;
        }
        .perspective-1000 {
            perspective: 1000px;
        }
      `}} />
            </aside>

            {/* Auth Modal - rendered outside aside to avoid overflow clipping */}
            <AuthModal
                isOpen={showAuthModal}
                onClose={() => setShowAuthModal(false)}
                onSuccess={() => setShowAuthModal(false)}
            />

            {/* 4. HOLOGRAPHIC PORTAL PREVIEW (Moved outside sidebar container to avoid clipping) */}
            <AnimatePresence>
                {hoveredProject && hoveredProject.id !== selectedProject?.id && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.5, rotateY: -30, x: -50 }}
                        animate={{ opacity: 1, scale: 1, rotateY: 0, x: 0 }}
                        exit={{ opacity: 0, scale: 0.5, rotateY: 30, x: 50 }}
                        transition={{ type: 'spring', damping: 20, stiffness: 100 }}
                        className="fixed left-[350px] md:left-[380px] pointer-events-none z-[100] perspective-1000 hidden md:block"
                        style={{ top: '25vh' }}
                    >
                        <div className="relative w-[340px] aspect-square rounded-[2rem] overflow-hidden border border-white/10 p-1 bg-white/5 backdrop-blur-2xl shadow-[0_0_50px_rgba(14,165,233,0.3)]">
                            {/* Inner Glow Rim */}
                            <div className="absolute inset-0 border-2 border-sky-500/20 rounded-[2rem] animate-pulse-subtle" />

                            {/* Content Container */}
                            <div className="relative w-full h-full rounded-[1.8rem] overflow-hidden">
                                <img
                                    src={hoveredProject.posterUrl || hoveredProject.coverUrl || hoveredProject.imageUrl}
                                    alt={hoveredProject.title}
                                    className="w-full h-full object-cover opacity-80"
                                />
                                <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent" />

                                {/* Floating Scan-line */}
                                <div className="absolute inset-x-0 h-[100%] bg-gradient-to-b from-transparent via-sky-500/20 to-transparent top-[-100%] animate-scan-y pointer-events-none" />

                                {/* Minimal Branding */}
                                <div className="absolute bottom-6 left-6 right-6">
                                    {/* Top 3 Tags */}
                                    <div className="flex flex-wrap gap-2 mb-3">
                                        {hoveredProject.technologies.slice(0, 3).map((tech, i) => (
                                            <span
                                                key={tech}
                                                className={`text-xs font-bold px-2.5 py-1 rounded-full border uppercase tracking-wider
                                                        ${i === 0 ? 'bg-sky-500/20 border-sky-500/40 text-sky-300' :
                                                        i === 1 ? 'bg-purple-500/20 border-purple-500/40 text-purple-300' :
                                                            'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'}
                                                    `}
                                            >
                                                {tech}
                                            </span>
                                        ))}
                                    </div>
                                    <h4 className="text-2xl font-black italic text-white leading-tight tracking-tighter">
                                        {hoveredProject.title}
                                    </h4>
                                </div>
                            </div>

                            {/* Outer Portal Orbs */}
                            <div className="absolute -top-4 -right-4 w-12 h-12 bg-sky-500/20 blur-xl rounded-full" />
                            <div className="absolute -bottom-4 -left-4 w-16 h-16 bg-purple-500/10 blur-xl rounded-full" />
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
};

export default SidebarV2;
