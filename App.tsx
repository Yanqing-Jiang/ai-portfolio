
import React, { useState, useMemo, useEffect } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useParams,
} from 'react-router-dom';
import Sidebar from './components/Sidebar';
import ProjectView from './components/ProjectView';
import LandingPage from './components/LandingPage';
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
  const [isSidebarOpen, setIsSidebarOpen] = useState(false); // Default closed for mobile-first
  const [isMobile, setIsMobile] = useState(false);
  const navigate = useNavigate();

  // Check if screen is mobile size
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768); // md breakpoint
      // Auto-open sidebar on desktop, keep closed on mobile
      if (window.innerWidth >= 768) {
        setIsSidebarOpen(true);
      } else {
        setIsSidebarOpen(false);
      }
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

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
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className={`fixed top-4 z-40 flex items-center justify-center w-10 h-10 md:w-8 md:h-8
                     bg-gray-800 hover:bg-gray-700 border border-gray-700/50 rounded-full
                     transition-all duration-300 shadow-lg hover:shadow-xl
                     ${isSidebarOpen && !isMobile ? 'left-[18rem]' : 'left-4'}
                     md:absolute md:top-6 md:left-auto md:-ml-4`}
        >
          {isSidebarOpen ? <ChevronLeftIcon /> : <ChevronRightIcon />}
        </button>

        {/* Main content area with fluid dimensions */}
        <main className="flex-1 overflow-y-auto pt-16 md:pt-0">
          <Routes>
            <Route
              path="/"
              element={
                <LandingPage
                  projectData={PROJECT_DATA}
                  onSelectProject={goProject}
                />
              }
            />
            <Route path="/project/:projectId" element={<ProjectRoute />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
};

// Root component -------------------------------------------------
const App: React.FC = () => (
  <HelmetProvider>
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  </HelmetProvider>
);

export default App;
