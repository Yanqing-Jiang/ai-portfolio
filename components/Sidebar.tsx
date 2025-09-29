
import React, { useState, useEffect } from 'react';
import type { Project, ProjectYear } from '../types';
import { ChevronDownIcon } from './icons/ChevronDownIcon';
import { ChevronRightIcon } from './icons/ChevronRightIcon';
import { SignInIcon } from './icons/SignInIcon';
import { authService, type AuthState } from '../services/auth';
import { AuthModal } from './AuthModal';

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
        fixed md:relative inset-y-0 left-0 z-30 md:z-auto
        h-full bg-gray-800/95 md:bg-gray-800/50 backdrop-blur-sm md:backdrop-blur-none
        border-r border-gray-700/50 flex flex-col shrink-0 
        transition-all duration-300 ease-in-out
        ${isSidebarOpen 
          ? 'w-80 sm:w-96 md:w-80 p-4 sm:p-6 md:p-4' 
          : 'w-0 p-0 overflow-hidden'
        }
      `}
    >
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Header with logo and title - responsive sizing */}
        <button 
          onClick={onGoHome} 
          className="flex items-center gap-2 mb-6 sm:mb-8 px-2 flex-shrink-0 hover:bg-gray-700/30 rounded-lg transition-colors duration-200"
        >
          <img 
            src="https://yanqinghot.blob.core.windows.net/public-access/Profile%20Logo%20black.png" 
            alt="Profile Logo" 
            className="w-16 h-17 sm:w-20 sm:h-21 md:w-20 md:h-21 shrink-0" 
          />
          <div className="min-w-0">
            <h1 className="text-2xl sm:text-3xl font-bold text-white">
              Yanqing{' '}
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
                AI Portfolio
              </span>
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
                  className="w-full flex justify-between items-center py-2 sm:py-3 px-2 sm:px-3 text-left 
                           text-sm sm:text-base font-semibold text-gray-400 hover:bg-gray-700/50 
                           rounded-md transition-colors duration-200"
                >
                  <div className="flex items-baseline min-w-0 flex-1">
                    <span className="text-base sm:text-lg md:text-lg font-bold text-gray-300 shrink-0">
                      {label ?? year}
                    </span>
                    {subtitle && (
                      <span className="text-xs sm:text-sm text-gray-500 font-normal ml-2 truncate">
                        {subtitle}
                      </span>
                    )}
                  </div>
                  <span className="shrink-0 ml-2">
                    {openYears.has(year) ? <ChevronDownIcon /> : <ChevronRightIcon />}
                  </span>
                </button>
                
                {openYears.has(year) && (
                  <ul className="pl-3 sm:pl-4 mt-2 border-l border-gray-700 space-y-1">
                    {projects.map(project => (
                      <li key={project.id}>
                        <button
                          onClick={() => onSelectProject(project)}
                          className={`w-full text-left py-2 sm:py-2.5 px-3 sm:px-4 text-sm sm:text-base 
                                   rounded-md transition-all duration-200 
                                   ${selectedProject?.id === project.id
                                     ? 'bg-blue-600/30 text-white font-medium shadow-sm'
                                     : 'text-gray-300 hover:bg-gray-700/50 hover:text-white'
                                   }`}
                        >
                          <span className="block truncate">{project.title}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </nav>

        {/* Footer with auth and external link */}
        <div className="flex-shrink-0 mt-auto pt-4 border-t border-gray-700/50 space-y-2">
          {/* Sign In/Out Button */}
          <button 
            onClick={handleAuthAction}
            className="flex items-center gap-3 w-full text-left py-2 sm:py-3 px-2 sm:px-3 
                     text-sm sm:text-base rounded-md transition-all duration-200 
                     text-gray-400 hover:bg-gray-700/50 hover:text-white group"
          >
            <SignInIcon />
            <span className="truncate">
              {authState.user ? `Sign Out (${authState.user.email})` : 'Sign In / Sign Up'}
            </span>
          </button>

          {/* External website link */}
          <a 
            href="https://www.jiangyanqing.com" 
            target="_blank" 
            rel="noopener noreferrer" 
            className="flex items-center gap-3 w-full text-left py-2 sm:py-3 px-2 sm:px-3 
                     text-sm sm:text-base rounded-md transition-all duration-200 
                     text-gray-400 hover:bg-gray-700/50 hover:text-white group"
          >
            <img 
              src="https://yanqinghot.blob.core.windows.net/public-access/Profile%20Logo.png" 
              alt="Website Logo" 
              className="w-4 h-4 sm:w-5 sm:h-5 shrink-0 group-hover:scale-110 transition-transform duration-200" 
            />
            <span className="truncate">Visit Yanqing Pre-AI Page</span>
          </a>
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
