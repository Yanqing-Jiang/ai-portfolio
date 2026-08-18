
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
import ProjectHelmet from './components/ProjectHelmet';
import ProjectView from './components/ProjectView';
import LandingPageFlow from './components/LandingPageFlow';
import { GenerativeUIPage } from './components/generativeUiDashboard';
import { MingEnginePage } from './components/generativeUiDashboard/MingEnginePage';
import { FortuneAgentIntro } from './components/generativeUiDashboard/FortuneAgentIntro';
import { FortuneAgentHub } from './components/generativeUiDashboard/FortuneAgentHub';
import { FortuneAgentCompatibility } from './components/generativeUiDashboard/FortuneAgentCompatibility';
import { FortuneAgentLuckyDay } from './components/generativeUiDashboard/FortuneAgentLuckyDay';
import { FortuneAgentLuckDraw } from './components/generativeUiDashboard/FortuneAgentLuckDraw';
import { FortuneAgentCustomWish } from './components/generativeUiDashboard/FortuneAgentCustomWish';
import { FortuneResultShell } from './components/generativeUiDashboard/FortuneResultShell';
import { AskDemoPage } from './components/generativeUiDashboard/fortune/AskDemoPage';
import { ConsultingPage } from './components/consulting/ConsultingPage';
import { MeetPage } from './components/consulting/MeetPage';
import BlogIndexPage from './components/blog/BlogIndexPage';
import BlogPostPage from './components/blog/BlogPostPage';
import HomerLitePage from './components/homer-lite/HomerLitePage';

import { PROJECT_DATA } from './constants';
import type { Project } from './types';
import { supabase } from './services/auth';
import { fortuneIntakeRoute, fortuneResultRoute } from './lib/fortuneRoutes';
// @ts-ignore
import { HelmetProvider } from 'react-helmet-async';


// Function: findProject - called from ProjectRoute and Layout to resolve a Project by id; forwards the Project into ProjectView for rendering and into SidebarV2 for active highlighting; exists to centralize project lookup for routing.
const ALL_PROJECTS = PROJECT_DATA.flatMap((y) => y.projects);
const findProject = (id: string) => ALL_PROJECTS.find((p) => p.id === id);

const FortuneAgentIntroRoute: React.FC = () => {
  const navigate = useNavigate();
  const goExplore = () => navigate('/project/fortune-agent/explore');
  const fortuneProject = findProject('fortune-agent');
  return (
    <>
      {fortuneProject && <ProjectHelmet project={fortuneProject} />}
      <FortuneAgentIntro onFinish={goExplore} onSkip={goExplore} />
    </>
  );
};

const FortuneAgentHubRoute: React.FC = () => {
  const navigate = useNavigate();
  return (
    <FortuneAgentHub
      onSelect={(id) => navigate(`/project/fortune-agent/${id}`)}
    />
  );
};

const FortuneAgentCompatibilityRoute: React.FC = () => {
  const navigate = useNavigate();
  return (
    <FortuneAgentCompatibility
      onBack={() => navigate('/project/fortune-agent/explore')}
      onComplete={(payload) => navigate(fortuneResultRoute('compatibility'), { state: payload })}
    />
  );
};

const FortuneAgentLuckyDayRoute: React.FC = () => {
  const navigate = useNavigate();
  return (
    <FortuneAgentLuckyDay
      onBack={() => navigate('/project/fortune-agent/explore')}
      onComplete={(payload) => navigate(fortuneResultRoute('occasion'), { state: payload })}
    />
  );
};

const FortuneAgentLuckDrawRoute: React.FC = () => {
  const navigate = useNavigate();
  return (
    <FortuneAgentLuckDraw
      onBack={() => navigate('/project/fortune-agent/explore')}
      onComplete={(payload) => navigate(fortuneResultRoute('cycle'), { state: payload })}
    />
  );
};

const FortuneAgentCustomWishRoute: React.FC = () => {
  const navigate = useNavigate();
  return (
    <FortuneAgentCustomWish
      onBack={() => navigate('/project/fortune-agent/explore')}
      onComplete={(payload) => navigate(fortuneResultRoute('wish'), { state: payload })}
    />
  );
};

const FortuneAgentCompatibilityResultRoute: React.FC = () => {
  const navigate = useNavigate();
  const { state } = useLocation();
  const { fortuneId } = useParams<{ fortuneId?: string }>();
  if (!state && !fortuneId) return <Navigate to={fortuneIntakeRoute('compatibility')} replace />;
  return <FortuneResultShell functionId="compatibility" onBack={() => navigate(fortuneIntakeRoute('compatibility'))} />;
};

const FortuneAgentOccasionResultRoute: React.FC = () => {
  const navigate = useNavigate();
  const { state } = useLocation();
  const { fortuneId } = useParams<{ fortuneId?: string }>();
  if (!state && !fortuneId) return <Navigate to={fortuneIntakeRoute('occasion')} replace />;
  return <FortuneResultShell functionId="occasion" onBack={() => navigate(fortuneIntakeRoute('occasion'))} />;
};

const FortuneAgentCycleResultRoute: React.FC = () => {
  const navigate = useNavigate();
  const { state } = useLocation();
  const { fortuneId } = useParams<{ fortuneId?: string }>();
  if (!state && !fortuneId) return <Navigate to={fortuneIntakeRoute('cycle')} replace />;
  return <FortuneResultShell functionId="cycle" onBack={() => navigate(fortuneIntakeRoute('cycle'))} />;
};

const FortuneAgentCustomWishResultRoute: React.FC = () => {
  const navigate = useNavigate();
  const { state } = useLocation();
  const { fortuneId } = useParams<{ fortuneId?: string }>();
  if (!state && !fortuneId) return <Navigate to={fortuneIntakeRoute('wish')} replace />;
  return <FortuneResultShell functionId="wish" onBack={() => navigate(fortuneIntakeRoute('wish'))} />;
};

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
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const mainContentRef = useRef<HTMLElement>(null);

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
  // Function: goHome - triggered by the header brand button to return to landing; called from SidebarV2; clears active project state; exists to reset layout from a project view.
  const goHome = () => {
    navigate('/');
    setActiveProject(null);
  };

  // Function: goProject - used by SidebarV2 and LandingPageFlow; navigates to the requested project and treats repeat clicks as a full refresh; exists to centralize project navigation semantics.
  // Honors `project.link` override so a project (e.g. Homer) can route to a custom path like `/homer`.
  const goProject = (p: Project) => {
    const targetPath = p.link ?? `/project/${p.id}`;
    const isCurrent = location.pathname === targetPath;
    setActiveProject(findProject(p.id) ?? p);

    if (isCurrent) {
      navigate(0); // force refresh when clicking the current project
      return;
    }

    navigate(targetPath);
  };

  // /consult and /meet carry their own top nav — hide the shared header there.
  const hideShellChrome = location.pathname === '/consult' || location.pathname === '/meet';

  return (
    <div className="flex h-[100dvh] flex-col bg-[#010208] text-white font-sans overflow-hidden">
      {!hideShellChrome && (
        <Sidebar
          projectData={PROJECT_DATA}
          selectedProject={activeProject}
          onSelectProject={goProject}
          onGoHome={goHome}
        />
      )}

      <div className="relative flex-1 flex flex-col min-w-0 min-h-0">
        {/* Main content area with fluid dimensions */}
        <main
          ref={mainContentRef}
          id="site-main"
          className="flex-1 min-h-0 overflow-y-auto"
          aria-label="Primary content"
          tabIndex={-1}
        >
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
            {/* 2026 Ming Engine - BaZi Fortune Reading */}
            <Route path="/project/ming-engine" element={<MingEnginePage />} />

            {/* 2026 Fortune Agent — redesign experiments (local test routes) */}
            <Route path="/project/fortune-agent" element={<FortuneAgentIntroRoute />} />
            <Route path="/project/fortune-agent/explore" element={<FortuneAgentHubRoute />} />
            <Route path={fortuneIntakeRoute('compatibility')} element={<FortuneAgentCompatibilityRoute />} />
            <Route path={fortuneIntakeRoute('occasion')} element={<FortuneAgentLuckyDayRoute />} />
            <Route path={fortuneIntakeRoute('cycle')} element={<FortuneAgentLuckDrawRoute />} />
            <Route path={fortuneIntakeRoute('wish')} element={<FortuneAgentCustomWishRoute />} />

            {/* Result pages — /:fortuneId routes for live backend + replay */}
            <Route path={fortuneResultRoute('wish', ':fortuneId')} element={<FortuneAgentCustomWishResultRoute />} />
            <Route path={fortuneResultRoute('cycle', ':fortuneId')} element={<FortuneAgentCycleResultRoute />} />
            <Route path={fortuneResultRoute('compatibility', ':fortuneId')} element={<FortuneAgentCompatibilityResultRoute />} />
            <Route path={fortuneResultRoute('occasion', ':fortuneId')} element={<FortuneAgentOccasionResultRoute />} />

            {/* State-backed result routes used by the current input flows */}
            <Route path={fortuneResultRoute('compatibility')} element={<FortuneAgentCompatibilityResultRoute />} />
            <Route path={fortuneResultRoute('occasion')} element={<FortuneAgentOccasionResultRoute />} />
            <Route path={fortuneResultRoute('cycle')} element={<FortuneAgentCycleResultRoute />} />
            <Route path={fortuneResultRoute('wish')} element={<FortuneAgentCustomWishResultRoute />} />

            {/* Ask-tab redesign experiments — three concepts side-by-side */}
            <Route path="/project/fortune-agent/ask-demo" element={<AskDemoPage />} />
            <Route path="/project/fortune-agent/ask-demo/:variant" element={<AskDemoPage />} />

            <Route path="/project/:projectId" element={<ProjectRoute />} />
            <Route path="/consult" element={<ConsultingPage />} />
            {/* Unlisted direct-scheduling page (share by link; noindex, not in
                the sitemap or prerender list — served by the SPA fallback). */}
            <Route path="/meet" element={<MeetPage />} />

            {/* Blog (Phase 1) */}
            <Route path="/blog" element={<BlogIndexPage />} />
            <Route path="/blog/tag/:tag" element={<BlogIndexPage />} />
            <Route path="/blog/:slug" element={<BlogPostPage />} />

            {/* Homer Lite case study (target: 2026-05-16) */}
            <Route path="/homer" element={<HomerLitePage />} />

            <Route path="/auth/callback" element={<AuthCallback />} />
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
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AppRoutes />
    </BrowserRouter>
  </HelmetProvider>
);

export default App;
