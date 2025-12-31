
import React, { useState, useEffect } from 'react';
import type { Project, ProjectYear } from '../types';
import { ChevronRightIcon } from './icons/ChevronRightIcon';
import { SignInIcon } from './icons/SignInIcon';
import { authService, type AuthState } from '../services/auth';
import { AuthModal } from './AuthModal';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';


interface SidebarProps {
  projectData: ProjectYear[];
  selectedProject: Project | null;
  onSelectProject: (project: Project) => void;
  isSidebarOpen: boolean;
  onGoHome: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ projectData, selectedProject, onSelectProject, isSidebarOpen, onGoHome }) => {
  const [openYears, setOpenYears] = useState<Set<number>>(() => {
    const initiallyOpenYears = projectData
      .filter(group => group.label !== 'Pre-AI Projects')
      .map(group => group.year);
    return new Set(initiallyOpenYears);
  });
  const [authState, setAuthState] = useState<AuthState>({ user: null, loading: true, error: null });
  const [showAuthModal, setShowAuthModal] = useState(false);

  // Subscribe to auth state changes
  useEffect(() => {
    const unsubscribe = authService.subscribe(setAuthState);
    return unsubscribe;
  }, []);

  const toggleYear = (year: number) => {
    setOpenYears(prev => {
      const newSet = new Set(prev);
      if (newSet.has(year)) {
        newSet.delete(year);
      } else {
        newSet.add(year);
      }
      return newSet;
    });
  };

  const handleAuthAction = () => {
    if (authState.user) {
      authService.signOut();
    } else {
      setShowAuthModal(true);
    }
  };

  return (
    <aside
      className={`
        fixed md:relative inset-y-0 left-0 z-50
        h-full bg-[#010208] border-r border-sky-500/10 flex flex-col shrink-0 
        transition-all duration-300 ease-in-out shadow-2xl
        ${isSidebarOpen
          ? 'w-80 sm:w-96 md:w-80 p-6 opacity-100'
          : 'w-0 p-0 overflow-hidden border-none opacity-0'
        }
      `}
    >
      {/* Glow Effect */}
      <div className="absolute top-0 right-0 w-32 h-64 bg-sky-600/5 blur-[100px] pointer-events-none" />

      <div className="flex flex-col flex-1 h-full relative z-10">
        {/* Header - Brand Identity */}
        <button
          onClick={onGoHome}
          className="flex items-center gap-3 mb-12 hover:opacity-80 transition-opacity text-left group shrink-0"
        >
          <div className="relative w-12 h-12 flex-shrink-0">
            <div className="absolute inset-0 bg-sky-500/20 blur-lg rounded-full animate-pulse" />
            <img
              src="https://yanqinghot.blob.core.windows.net/public-access/Profile%20Logo%20black.png"
              alt="Logo"
              className="w-full h-full object-contain relative z-10"
            />
          </div>
          <div className="min-w-0">
            <h1 className="text-xl font-black tracking-tighter uppercase text-white leading-[0.9]">
              Yanqing<br />
              <span className="text-white">Jiang</span>
            </h1>
          </div>
        </button>

        {/* Navigation with responsive typography */}
        <nav className="flex-1 overflow-y-auto pr-1 sidebar-scrollbar">
          <ul className="space-y-3 sm:space-y-4">
            {projectData.map(({ year, subtitle, projects, label }) => (
              <li key={year}>
                <button
                  onClick={() => toggleYear(year)}
                  className="w-full flex justify-between items-center group mb-4"
                >
                  <div className="flex items-baseline gap-3">
                    <span className={`font-black text-white uppercase tracking-widest ${label === 'Pre-AI Projects' ? 'text-sm' : 'text-lg'}`}>
                      {label ?? year}
                    </span>
                    {subtitle && (
                      <span className="text-[10px] font-mono text-slate-500 uppercase tracking-tighter truncate max-w-[120px]">
                        {subtitle}
                      </span>
                    )}
                  </div>
                  <span className={`transition-transform duration-300 ${openYears.has(year) ? 'rotate-90' : ''} text-sky-500/50`}>
                    <ChevronRightIcon />
                  </span>
                </button>

                {openYears.has(year) && (
                  <ul className="pl-4 border-l border-sky-500/10 space-y-2 mb-8">
                    {projects.map(project => (
                      <li key={project.id}>
                        <Link
                          to={`/project/${project.id}`}
                          onClick={() => onSelectProject(project)}
                          className={`group relative block py-2 px-3 text-sm transition-all duration-300 rounded-lg
                            ${selectedProject?.id === project.id
                              ? 'bg-sky-500/20 text-white font-bold'
                              : 'text-slate-400 hover:text-white hover:bg-white/5'
                            }`}
                        >
                          <span className="truncate block pr-4">{project.title}</span>
                          {selectedProject?.id === project.id && (
                            <motion.div
                              layoutId="active-nav"
                              className="absolute left-[-1.5px] top-1.5 bottom-1.5 w-0.5 bg-sky-500 rounded-full shadow-[0_0_8px_#0ea5e9]"
                            />
                          )}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </nav>

        {/* Terminal Footer */}
        <div className="mt-auto pt-6 border-t border-sky-500/10">
          <button
            onClick={handleAuthAction}
            className="flex items-center gap-3 w-full py-4 px-4 rounded-2xl bg-sky-500/5 border border-sky-500/10 hover:border-sky-500/30 transition-all group"
          >
            <div className="text-sky-500 group-hover:scale-110 transition-transform">
              <SignInIcon />
            </div>
            <div className="text-left min-w-0">
              <p className="text-[10px] font-black text-sky-500/70 uppercase tracking-[0.2em] leading-none mb-1">Access.Terminal</p>
              <p className="text-[11px] text-white truncate font-mono">
                {authState.user ? authState.user.email : 'Sign In / Sign Up'}
              </p>
            </div>
          </button>
        </div>
      </div>

      {/* Authentication Modal */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSuccess={() => {
          setShowAuthModal(false);
        }}
      />
    </aside>
  );
};

export default Sidebar;
