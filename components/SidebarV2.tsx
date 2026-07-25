
import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link, useLocation } from 'react-router-dom';
import type { Project, ProjectYear } from '../types';
import { SignInIcon } from './icons/SignInIcon';
import { ChevronDown } from 'lucide-react';
import { authService, type AuthState } from '../services/auth';
import { AuthModal } from './AuthModal';
import { allPosts, formatPostDateShort } from '../lib/blog/mdx';
import type { BlogPost } from '../lib/blog/mdx';

interface SidebarV2Props {
    projectData: ProjectYear[];
    selectedProject: Project | null;
    onSelectProject: (project: Project) => void;
    onGoHome: () => void;
}

/**
 * Function: SidebarV2 - called from Layout in App.tsx to render the site-wide
 * top header ("Yanqing Jiang" returns to the landing page; "Menu" opens the
 * navigation drawer) plus the drawer itself: a Projects | Blog tab switch over
 * the year-grouped trees, auth entry at the bottom, hover preview on desktop.
 *
 * Themed to match the landing page: bg #12110F, hairline #37332E, bone #F1EADF,
 * muted #A8A096, single vermilion accent #F04A32. Flat editorial surfaces —
 * hairline rules, mono uppercase labels, 4px corners; no glows or scan-lines.
 */

const SidebarV2: React.FC<SidebarV2Props> = ({
    projectData,
    selectedProject,
    onSelectProject,
    onGoHome
}) => {
    const location = useLocation();
    const [open, setOpen] = useState(false);
    // Tab is local drawer state (switching tabs must not navigate); it seeds
    // from the URL each time the drawer opens so it lands on the relevant tree.
    const [tab, setTab] = useState<'projects' | 'blog'>('projects');

    // Group blog posts by year for the Blog-tab tree.
    const postsByYear = useMemo(() => {
        const grouped: Record<number, BlogPost[]> = {};
        for (const post of allPosts) {
            const year = new Date(post.frontmatter.publishedAt).getFullYear();
            if (!grouped[year]) grouped[year] = [];
            grouped[year].push(post);
        }
        return grouped;
    }, []);

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

    // Function: handleProjectClick - called from drawer project links; clears the hover preview and closes the drawer, then forwards the project to the parent onSelectProject so navigation/refresh logic can run.
    const handleProjectClick = (project: Project) => {
        setHoveredProject(null);
        setOpen(false);
        onSelectProject(project);
    };

    // Close the drawer on any route change (blog links, back button, deep nav).
    useEffect(() => {
        setOpen(false);
        setHoveredProject(null);
    }, [location.pathname]);

    // Seed the tab from the URL whenever the drawer opens.
    useEffect(() => {
        if (open) setTab(location.pathname.startsWith('/blog') ? 'blog' : 'projects');
    }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

    // Escape closes the drawer.
    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [open]);

    useEffect(() => {
        const unsubscribe = authService.subscribe(setAuthState);
        return unsubscribe;
    }, []);

    const handleAuthAction = () => {
        if (authState.user) {
            authService.signOut();
        } else {
            setShowAuthModal(true);
        }
    };

    return (
        <>
            {/* 1. TOP HEADER — a single wordmark. First click opens the drawer;
                the drawer repeats the wordmark at the same spot, and clicking it
                there (menu expanded) returns to the landing page. */}
            <header className="z-50 shrink-0 border-b border-[#37332E] bg-[#12110F]" style={{ colorScheme: 'dark' }}>
                <nav className="mx-auto flex h-16 max-w-[1280px] items-center justify-start px-6 lg:px-10">
                    <button
                        type="button"
                        onClick={() => setOpen(true)}
                        aria-label="Open menu"
                        aria-expanded={open}
                        className="group flex min-h-[44px] items-center text-[16px] font-black tracking-[-0.03em] text-[#F1EADF] transition-colors hover:text-white"
                    >
                        Yanqing Jiang<span className="text-[#F04A32] transition-transform duration-200 group-hover:scale-125">.</span>
                    </button>
                </nav>
            </header>

            {/* 2. NAVIGATION DRAWER (left slide-over, all screen sizes) */}
            <AnimatePresence>
                {open && (
                    <>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setOpen(false)}
                            className="fixed inset-0 z-[60] bg-[#12110F]/70 backdrop-blur-sm"
                        />
                        <motion.aside
                            initial={{ x: '-100%' }}
                            animate={{ x: 0 }}
                            exit={{ x: '-100%' }}
                            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                            className="fixed inset-y-0 left-0 z-[70] flex w-[85vw] flex-col border-r border-[#37332E] bg-[#12110F] px-7 pb-4 sm:w-80"
                            style={{ colorScheme: 'dark' }}
                        >
                            {/* 2a. WORDMARK ROW — same "Yanqing Jiang." as the header;
                                with the menu expanded, clicking it returns to landing. */}
                            <div className="-mx-7 mb-5 border-b border-[#37332E] px-7">
                                <div className="flex h-16 items-center justify-between">
                                    <button
                                        type="button"
                                        onClick={() => { setOpen(false); onGoHome(); }}
                                        aria-label="Back to home"
                                        className="group flex min-h-[44px] items-center text-[16px] font-black tracking-[-0.03em] text-[#F1EADF] transition-colors hover:text-white"
                                    >
                                        Yanqing Jiang<span className="text-[#F04A32] transition-transform duration-200 group-hover:scale-125">.</span>
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setOpen(false)}
                                        aria-label="Close menu"
                                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[4px] text-[#A8A096] transition-colors hover:text-[#F1EADF]"
                                    >
                                        ✕
                                    </button>
                                </div>
                            </div>

                            {/* 2b. PROJECTS / BLOG TAB SWITCH */}
                            <div className="mb-6 flex gap-1 rounded-[4px] border border-[#37332E] p-1">
                                <button
                                    onClick={() => setTab('projects')}
                                    className={`flex-1 py-2 rounded-[3px] font-mono text-[11px] tracking-[0.18em] uppercase transition-colors ${tab === 'projects' ? 'bg-[#F04A32] text-[#12110F]' : 'text-[#A8A096] hover:text-[#F1EADF]'}`}
                                >Projects</button>
                                <button
                                    onClick={() => setTab('blog')}
                                    className={`flex-1 py-2 rounded-[3px] font-mono text-[11px] tracking-[0.18em] uppercase transition-colors ${tab === 'blog' ? 'bg-[#F04A32] text-[#12110F]' : 'text-[#A8A096] hover:text-[#F1EADF]'}`}
                                >Blog</button>
                            </div>

                            {/* 2c. NAV TREE — branches on tab */}
                            <nav className="sidebar-scrollbar relative -mr-6 flex-1 overflow-y-auto overflow-x-hidden pr-6">

                                {/* BLOG TAB — year-grouped post list */}
                                {tab === 'blog' && (
                                    <div className="space-y-8 py-1">
                                        {Object.entries(postsByYear)
                                            .sort(([a], [b]) => Number(b) - Number(a))
                                            .map(([year, posts]) => (
                                                <div key={year}>
                                                    <div className="flex items-center gap-3 mb-4">
                                                        <span className="w-1.5 h-1.5 shrink-0 bg-[#F04A32]" />
                                                        <span className="font-mono text-[11px] tracking-[0.22em] uppercase shrink-0 text-[#A8A096]">{year}</span>
                                                        <div className="flex-1 h-px bg-[#37332E]" />
                                                    </div>
                                                    <div className="space-y-4 pl-1">
                                                        {posts.map((post) => {
                                                            const isActive = location.pathname === `/blog/${post.slug}`;
                                                            return (
                                                                <Link
                                                                    key={post.slug}
                                                                    to={`/blog/${post.slug}`}
                                                                    onClick={() => setOpen(false)}
                                                                    className="group/link block"
                                                                >
                                                                    {/* line-clamp-2 keeps long titles from bloating the rail;
                                                                        full title stays in the native title tooltip. */}
                                                                    <h3 className={`text-[15px] leading-snug font-medium transition-colors line-clamp-2 ${isActive ? 'text-[#F04A32]' : 'text-[#F1EADF] group-hover/link:text-[#F04A32]'}`} title={post.frontmatter.title}>
                                                                        {post.frontmatter.title}
                                                                    </h3>
                                                                    <p className="font-mono text-[10px] text-[#A8A096] mt-1 tracking-[0.12em] uppercase">
                                                                        {formatPostDateShort(post.frontmatter.publishedAt)} · {post.readingMinutes} min
                                                                    </p>
                                                                </Link>
                                                            );
                                                        })}
                                                    </div>
                                                </div>
                                            ))}
                                    </div>
                                )}

                                {/* PROJECTS TAB — year-grouped project tree.
                                    Homer lives inside the 2026 group via PROJECT_DATA, with a
                                    `link: '/homer'` override that the project Link below honors. */}
                                {tab === 'projects' && (
                                <div className="flex flex-col gap-4 py-1">
                                    {projectData.map(({ year, projects, label }) => {
                                        const isCollapsed = collapsedYears[year];
                                        return (
                                            <div key={year} className="mb-1">
                                                {/* Year header with toggle */}
                                                <div
                                                    onClick={() => toggleYear(year)}
                                                    className="flex items-center justify-between mb-3 group/header cursor-pointer"
                                                >
                                                    <div className="flex items-baseline gap-2">
                                                        <h3 className={`font-black tracking-[-0.03em] text-[#F1EADF] ${year === 2021 ? 'text-[15px]' : 'text-xl'}`}>{year === 2021 ? 'Pre-AI Projects' : year}</h3>
                                                        {year !== 2021 && label && (
                                                            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[#A8A096] truncate max-w-[150px]">
                                                                {label}
                                                            </span>
                                                        )}
                                                    </div>
                                                    <ChevronDown
                                                        className={`w-4 h-4 text-[#A8A096] transition-transform duration-300 group-hover/header:text-[#F1EADF] ${isCollapsed ? '-rotate-90' : 'rotate-0'}`}
                                                    />
                                                </div>

                                                {/* Collapsible tree with hairline spine */}
                                                <AnimatePresence>
                                                    {!isCollapsed && (
                                                        <motion.ul
                                                            initial={{ height: 0, opacity: 0 }}
                                                            animate={{ height: 'auto', opacity: 1 }}
                                                            exit={{ height: 0, opacity: 0 }}
                                                            transition={{ duration: 0.3, ease: "easeInOut" }}
                                                            className="relative space-y-0.5 border-l border-[#37332E] ml-1 pl-4 overflow-hidden"
                                                        >
                                                            {projects.map((project, idx) => {
                                                                const isActive = selectedProject?.id === project.id;
                                                                return (
                                                                    <motion.li
                                                                        key={project.id}
                                                                        initial={{ opacity: 0, x: -8 }}
                                                                        animate={{ opacity: 1, x: 0 }}
                                                                        transition={{ delay: idx * 0.03 }}
                                                                    >
                                                                        <Link
                                                                            to={project.link ?? `/project/${project.id}`}
                                                                            onClick={() => handleProjectClick(project)}
                                                                            onMouseEnter={() => setHoveredProject(project)}
                                                                            onMouseLeave={() => setHoveredProject(null)}
                                                                            className={`
                                                                            group/link relative block py-1.5 px-3 -ml-px rounded-[4px] transition-colors duration-200
                                                                            ${isActive
                                                                                    ? 'bg-[#191816]'
                                                                                    : 'hover:bg-[#191816]'}
                                                                        `}
                                                                        >
                                                                            {/* Active indicator — accent left bar */}
                                                                            {isActive && (
                                                                                <motion.div
                                                                                    layoutId="active-pill"
                                                                                    className="absolute left-[-1px] top-1 bottom-1 w-0.5 bg-[#F04A32]"
                                                                                    transition={{ type: 'spring', damping: 20, stiffness: 260 }}
                                                                                />
                                                                            )}
                                                                            <span className={`text-[14px] font-medium tracking-tight transition-colors duration-200 block
                                                                                ${isActive
                                                                                    ? 'text-[#F1EADF]'
                                                                                    : 'text-[#A8A096] group-hover/link:text-[#F1EADF]'}`}>
                                                                                {project.title}
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
                                )}
                            </nav>

                            <div className="mt-auto pt-4 border-t border-[#37332E]">
                                <button
                                    onClick={handleAuthAction}
                                    className="flex items-center gap-4 w-full group py-3 px-4 border border-[#37332E] hover:border-[#F04A32] bg-transparent hover:bg-[#191816] rounded-[4px] transition-colors duration-200"
                                >
                                    <div className="w-9 h-9 rounded-[4px] border border-[#37332E] flex items-center justify-center text-[#A8A096] group-hover:text-[#F04A32] group-hover:border-[#F04A32] transition-colors duration-200">
                                        <SignInIcon />
                                    </div>
                                    <div className="flex flex-col text-left min-w-0">
                                        <span className="font-mono text-[10px] text-[#A8A096] uppercase tracking-[0.2em] leading-none mb-1">
                                            {authState.user ? 'Access Terminal' : 'Sign In / Sign Up'}
                                        </span>
                                        <span className="text-[12px] font-semibold text-[#F1EADF] truncate">
                                            {authState.user ? authState.user.email : 'to unlock more usage'}
                                        </span>
                                    </div>
                                </button>
                            </div>

                            <style dangerouslySetInnerHTML={{
                                __html: `
                .sidebar-scrollbar::-webkit-scrollbar {
                  width: 0px;
                }
              `}} />
                        </motion.aside>
                    </>
                )}
            </AnimatePresence>

            {/* Auth Modal - rendered outside the drawer to avoid overflow clipping */}
            <AuthModal
                isOpen={showAuthModal}
                onClose={() => setShowAuthModal(false)}
                onSuccess={() => setShowAuthModal(false)}
            />

            {/* 3. HOVER PREVIEW (flat editorial card; outside the drawer to avoid clipping) */}
            <AnimatePresence>
                {open && hoveredProject && hoveredProject.id !== selectedProject?.id && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.96, x: -12 }}
                        animate={{ opacity: 1, scale: 1, x: 0 }}
                        exit={{ opacity: 0, scale: 0.96, x: -12 }}
                        transition={{ type: 'spring', damping: 22, stiffness: 220 }}
                        className="fixed left-[350px] md:left-[380px] pointer-events-none z-[100] hidden md:block"
                        style={{ top: '25vh' }}
                    >
                        <div className="relative w-[320px] aspect-square overflow-hidden rounded-[4px] border border-[#37332E] bg-[#191816]">
                            <img
                                src={hoveredProject.posterUrl || hoveredProject.coverUrl || hoveredProject.imageUrl}
                                alt={hoveredProject.title}
                                className="w-full h-full object-cover"
                            />
                            <div className="absolute inset-0 bg-gradient-to-t from-[#12110F] via-[#12110F]/30 to-transparent" />

                            <div className="absolute bottom-5 left-5 right-5">
                                <div className="flex flex-wrap gap-2 mb-3">
                                    {hoveredProject.technologies.slice(0, 3).map((tech) => (
                                        <span
                                            key={tech}
                                            className="font-mono text-[10px] px-2 py-1 rounded-[3px] border border-[#37332E] bg-[#12110F]/60 uppercase tracking-[0.12em] text-[#A8A096]"
                                        >
                                            {tech}
                                        </span>
                                    ))}
                                </div>
                                <h4 className="text-xl font-black tracking-[-0.03em] text-[#F1EADF] leading-tight">
                                    {hoveredProject.title}
                                </h4>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
};

export default SidebarV2;
