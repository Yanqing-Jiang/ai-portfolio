
import React, { useState, useMemo, useEffect, useRef } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useLocation,
  useParams,
} from 'react-router-dom';
import Sidebar from './components/Sidebar';
import ProjectView from './components/ProjectView';
import LandingPageFlow from './components/LandingPageFlow';
import { GenerativeUIPage } from './components/generativeUiDashboard';
import { PROJECT_DATA } from './constants';
import type { Project } from './types';
import { ChevronLeftIcon } from './components/icons/ChevronLeftIcon';
import { ChevronRightIcon } from './components/icons/ChevronRightIcon';
// @ts-ignore
import { HelmetProvider } from 'react-helmet-async';


// --- helper to look up a project by id ---
const ALL_PROJECTS = PROJECT_DATA.flatMap((y) => y.projects);
const findProject = (id: string) => ALL_PROJECTS.find((p) => p.id === id);

// --- <ProjectRoute/> wrapper for the /project/:id path ---
const ProjectRoute: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const project = useMemo(() => (projectId ? findProject(projectId) : undefined), [projectId]);
  if (!project) return <Navigate to="/" replace />;
  return <ProjectView project={project} />;
};

// --- main layout that stays the same on every page ---
const Layout: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false); // Always default closed
  const [isMobile, setIsMobile] = useState(false);
  const [showSidebarHint, setShowSidebarHint] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const mainContentRef = useRef<HTMLDivElement>(null);

  // Check if screen is mobile size - but keep sidebar closed by default
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768); // md breakpoint
      // Keep sidebar closed by default on all sizes
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Show hint once on first visit (check localStorage)
  useEffect(() => {
    const hasSeenHint = localStorage.getItem('sidebarHintSeen');
    if (!hasSeenHint) {
      // Show immediately on first visit
      setShowSidebarHint(true);

      // Auto-hide after 3 seconds
      const timer = setTimeout(() => {
        setShowSidebarHint(false);
        localStorage.setItem('sidebarHintSeen', 'true');
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, []);

  // Also dismiss hint on scroll (backup)
  useEffect(() => {
    const mainEl = mainContentRef.current;
    if (!mainEl || !showSidebarHint) return;

    const handleScroll = () => {
      if (showSidebarHint) {
        setShowSidebarHint(false);
        localStorage.setItem('sidebarHintSeen', 'true');
      }
    };

    mainEl.addEventListener('scroll', handleScroll, { passive: true });
    return () => mainEl.removeEventListener('scroll', handleScroll);
  }, [showSidebarHint]);

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      if (mainContentRef.current) {
        mainContentRef.current.scrollTo({ top: 0, behavior: 'auto' });
      } else {
        window.scrollTo({ top: 0, behavior: 'auto' });
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [location.pathname]);

  // navigation helpers
  const goHome = () => {
    navigate('/');
    if (isMobile) setIsSidebarOpen(false); // Close sidebar on mobile after navigation
  };

  const goProject = (p: Project) => {
    navigate(`/project/${p.id}`);
    if (isMobile) setIsSidebarOpen(false); // Close sidebar on mobile after navigation
  };

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100 font-sans overflow-hidden">
      <Sidebar
        isSidebarOpen={isSidebarOpen}
        projectData={PROJECT_DATA}
        selectedProject={null}
        onSelectProject={goProject}
        onGoHome={goHome}
      />

      {/* Mobile overlay when sidebar is open */}
      {isSidebarOpen && isMobile && (
        <div
          onClick={() => setIsSidebarOpen(false)}
          className="fixed inset-0 bg-black/50 z-20 md:hidden backdrop-blur-sm"
        />
      )}

      <div className="relative flex-1 flex flex-col min-w-0">
        {/* Sidebar toggle button - responsive positioning */}
        <button
          onClick={() => {
            setIsSidebarOpen(!isSidebarOpen);
            if (showSidebarHint) {
              setShowSidebarHint(false);
              localStorage.setItem('sidebarHintSeen', 'true');
            }
          }}
          className={`fixed top-4 z-40 flex items-center justify-center w-10 h-10 md:w-8 md:h-8
                     bg-gray-800 hover:bg-gray-700 border border-gray-700/50 rounded-full
                     transition-all duration-300 shadow-lg hover:shadow-xl
                     ${isSidebarOpen && !isMobile ? 'left-[18rem]' : 'left-4'}
                     md:absolute md:top-6 md:left-auto md:-ml-4`}
        >
          {isSidebarOpen ? <ChevronLeftIcon /> : <ChevronRightIcon />}
        </button>

        {/* Sidebar hint tooltip with premium animated arrow - shows once */}
        {showSidebarHint && !isSidebarOpen && (
          <div className="fixed top-4 left-[64px] z-50 flex items-center gap-4 animate-fade-in pointer-events-none">
            {/* Premium Stylish Arrow */}
            <div className="relative flex items-center animate-bounce-horizontal">
              <svg
                className="w-12 h-12 text-sky-400 filter drop-shadow-[0_0_8px_rgba(56,189,248,0.6)]"
                viewBox="0 0 64 64"
                fill="none"
              >
                <path
                  d="M56 32H12M12 32L24 20M12 32L24 44"
                  stroke="currentColor"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <circle cx="56" cy="32" r="3" fill="currentColor" className="animate-pulse" />
              </svg>
            </div>

            {/* Refined Tooltip Bubble */}
            <div className="relative group">
              <div className="absolute inset-0 bg-sky-500/20 blur-xl rounded-full" />
              <div className="relative bg-slate-900/80 backdrop-blur-md border border-sky-500/30 text-sky-100 text-sm font-semibold tracking-wide px-6 py-2.5 rounded-full shadow-2xl">
                Explore Yanqing's Projects
              </div>
            </div>
          </div>
        )}

        {/* Main content area with fluid dimensions */}
        <main ref={mainContentRef} className="flex-1 overflow-y-auto pt-16 md:pt-0">
          <Routes>
            <Route
              path="/"
              element={
                <LandingPageFlow
                  projectData={PROJECT_DATA}
                  onSelectProject={goProject}
                />
              }
            />
            {/* 2026 Generative UI - Custom full-page experience */}
            <Route path="/project/generative-ui-a2ui" element={<GenerativeUIPage />} />
            <Route path="/project/:projectId" element={<ProjectRoute />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>

        </main>
      </div>
    </div>
  );
};

// Root component -------------------------------------------------
export const AppRoutes: React.FC = () => <Layout />;

const App: React.FC = () => (
  <HelmetProvider>
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  </HelmetProvider>
);

export default App;

