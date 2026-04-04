
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
import Sidebar from './components/SidebarV2';
import ProjectView from './components/ProjectView';
import LandingPageFlow from './components/LandingPageFlow';
import { GenerativeUIPage } from './components/generativeUiDashboard';
import { ConsultingPage } from './components/consulting/ConsultingPage';

import { PROJECT_DATA } from './constants';
import type { Project } from './types';
import { ChevronLeftIcon } from './components/icons/ChevronLeftIcon';
import { ChevronRightIcon } from './components/icons/ChevronRightIcon';
import { supabase } from './services/auth';
// @ts-ignore
import { HelmetProvider } from 'react-helmet-async';


// Function: findProject - called from ProjectRoute and Layout to resolve a Project by id; forwards the Project into ProjectView for rendering and into SidebarV2 for active highlighting; exists to centralize project lookup for routing.
const ALL_PROJECTS = PROJECT_DATA.flatMap((y) => y.projects);
const findProject = (id: string) => ALL_PROJECTS.find((p) => p.id === id);

// Function: ProjectRoute - mounted by the /project/:id route; looks up the requested project and renders ProjectView or redirects home if missing; exists to keep route elements thin.
const ProjectRoute: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const project = useMemo(() => (projectId ? findProject(projectId) : undefined), [projectId]);
  if (!project) return <Navigate to="/" replace />;
  return <ProjectView project={project} />;
};

// AuthCallback — lightweight route for OAuth popup flow. Supabase SDK parses the auth
// tokens from the URL hash, then notifies the opener window via postMessage and closes.
const AuthCallback: React.FC = () => {
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (window.opener) {
        window.opener.postMessage(
          { type: 'supabase-auth-complete', session: !!session },
          window.location.origin
        );
        window.close();
      } else {
        // Direct navigation (mobile redirect fallback) — go home
        window.location.href = '/';
      }
    });
  }, []);

  return (
    <div className="flex items-center justify-center h-screen bg-[#0B1120] text-white">
      <p className="text-sm text-slate-400">Completing sign-in...</p>
    </div>
  );
};

// Function: Layout - shell used by AppRoutes to hold the sidebar, routing, and shared UI chrome; called from AppRoutes; invokes goHome/goProject for navigation; exists to keep router wiring in one place.
const Layout: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false); // Always default closed
  const [isMobile, setIsMobile] = useState(false);
  const [showSidebarHint, setShowSidebarHint] = useState(false);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
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

  useEffect(() => {
    const match = location.pathname.match(/^\/project\/([^/]+)/);
    if (match?.[1]) {
      setActiveProject(findProject(match[1]) ?? null);
    } else {
      setActiveProject(null);
    }
  }, [location.pathname]);

  // navigation helpers
  // Function: goHome - triggered by sidebar brand/backdrop to return to landing; called from SidebarV2 on logo/backdrop click; clears active project state, closes sidebar on mobile; exists to reset layout from a project view.
  const goHome = () => {
    navigate('/');
    setActiveProject(null);
    if (isMobile) setIsSidebarOpen(false); // Close sidebar on mobile after navigation
  };

  // Function: goProject - used by SidebarV2 and LandingPageFlow; navigates to the requested project, treats repeat clicks as a full refresh, and collapses the sidebar on mobile; exists to centralize project navigation semantics.
  const goProject = (p: Project) => {
    const targetPath = `/project/${p.id}`;
    const isCurrent = location.pathname === targetPath;
    setActiveProject(findProject(p.id) ?? p);
    if (isMobile) setIsSidebarOpen(false); // Close sidebar on mobile after navigation

    if (isCurrent) {
      navigate(0); // force refresh when clicking the current project
      return;
    }

    navigate(targetPath);
  };

  return (
    <div className="flex h-[100dvh] bg-[#010208] text-white font-sans overflow-hidden">
      <Sidebar
        isSidebarOpen={isSidebarOpen}
        projectData={PROJECT_DATA}
        selectedProject={activeProject}
        onSelectProject={goProject}
        onGoHome={goHome}
      />

      <div className="relative flex-1 flex flex-col min-w-0 transition-all duration-500 ease-in-out">
        {/* Sidebar toggle button - hidden on /consult page */}
        {location.pathname !== '/consult' && (
        <button
          onClick={() => {
            setIsSidebarOpen(!isSidebarOpen);
            if (showSidebarHint) {
              setShowSidebarHint(false);
              localStorage.setItem('sidebarHintSeen', 'true');
            }
          }}
          className={`fixed top-6 z-[60] flex items-center justify-center w-8 h-8 md:w-10 md:h-10
                     bg-slate-900/80 backdrop-blur-xl border border-sky-500/30 rounded-full
                     text-sky-400 transition-all duration-500 shadow-[0_0_20px_rgba(14,165,233,0.2)] 
                     hover:bg-sky-500/20 hover:text-white hover:border-sky-400
                     ${isSidebarOpen ? 'left-[19rem] sm:left-[23rem] md:left-[19rem]' : 'left-6'}`}
        >
          {isSidebarOpen ? <ChevronLeftIcon /> : <ChevronRightIcon />}
        </button>)
}

        {/* Sidebar hint tooltip with premium animated arrow - shows once */}
        {showSidebarHint && !isSidebarOpen && location.pathname !== '/consult' && (
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
            {/* 2026 Agent to UI - Custom full-page experience */}
            <Route path="/project/agent-to-ui" element={<GenerativeUIPage />} />



            <Route path="/project/:projectId" element={<ProjectRoute />} />
            <Route path="/consult" element={<ConsultingPage />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>

        </main>
      </div>
    </div>
  );
};

// Function: AppRoutes - exported for tests/demos; renders the shared Layout inside the router context; exists to keep routing tree modular.
export const AppRoutes: React.FC = () => <Layout />;

// Function: App - application root used by Vite entry; wraps the router with HelmetProvider; exists to set up providers once.
const App: React.FC = () => (
  <HelmetProvider>
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  </HelmetProvider>
);

export default App;

