import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import type { Project } from '../types';
import Chat from './Chat';
import { Page as AnalyticsSqlPage } from './analytics/sql';
import { Page as AnalyticsMemoryPage } from './analytics/memory';
import LegacyProjectPage from './LegacyProjectPage';
import ProjectHelmet from './ProjectHelmet';

interface ProjectViewProps {
  project: Project;
}

const ProjectView: React.FC<ProjectViewProps> = ({ project }) => {
  const [hasStartedChat, setHasStartedChat] = useState(false);
  const [isHeaderCollapsed, setIsHeaderCollapsed] = useState(false);

  useEffect(() => {
    setHasStartedChat(false);
    setIsHeaderCollapsed(false);
  }, [project.id]);

  const handleFirstMessage = () => {
    if (!hasStartedChat) {
      setHasStartedChat(true);
      setIsHeaderCollapsed(true);
    }
  };

  if (project.id === 'next-gen-analytics-sql') {
    return (
      <>
        <ProjectHelmet project={project} />
        <AnalyticsSqlPage />
      </>
    );
  }

  if (project.id === 'next-gen-analytics-memory') {
    return (
      <>
        <ProjectHelmet project={project} />
        <AnalyticsMemoryPage />
      </>
    );
  }

  if (project.contentHtml) {
    return <LegacyProjectPage project={project} />;
  }

  return (
    <>
      <ProjectHelmet project={project} />
      <div className="flex flex-col h-full overflow-hidden">
        <motion.div
          initial={false}
          animate={isHeaderCollapsed ? { height: 60 } : { height: 'auto' }}
          transition={{ duration: 0.3, ease: 'easeInOut' }}
          className="flex-shrink-0 border-b border-gray-800 bg-gray-900 overflow-hidden"
        >
        {isHeaderCollapsed ? (
          <div className="h-full flex items-center justify-between px-4 md:px-6 lg:px-8">
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <h2 className="text-lg md:text-xl font-bold text-white truncate">{project.title}</h2>
              <div className="hidden sm:flex gap-2">
                {project.technologies.slice(0, 3).map(tech => (
                  <span
                    key={tech}
                    className="px-2 py-0.5 rounded-full bg-gray-700 text-gray-200 text-xs border border-gray-600"
                  >
                    {tech}
                  </span>
                ))}
                {project.technologies.length > 3 && (
                  <span className="px-2 py-0.5 rounded-full bg-gray-700 text-gray-200 text-xs border border-gray-600">
                    +{project.technologies.length - 3}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={() => setIsHeaderCollapsed(!isHeaderCollapsed)}
              className="p-2 hover:bg-gray-700 rounded-lg transition-colors text-gray-400 hover:text-white shrink-0"
              title="Expand header"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
        ) : (
          <div className="p-3 sm:p-4 md:p-6 lg:p-8 relative">
            <div className="flex flex-col md:flex-row gap-4 sm:gap-6 md:gap-8">
              <div className="flex-1 flex flex-col justify-center min-w-0">
                <h2 className="text-xl sm:text-2xl md:text-3xl lg:text-4xl xl:text-5xl font-bold text-white mb-2 sm:mb-3 md:mb-4 leading-tight">
                  {project.title}
                </h2>
                <div className="text-gray-400 text-sm sm:text-base md:text-base lg:text-lg max-w-none md:max-w-3xl mb-3 sm:mb-4 md:mb-6 space-y-2 sm:space-y-3 overflow-y-auto flex-1 md:flex-none">
                  {project.description.split('\n').map((line, idx) => {
                    const trimmed = line.trim();
                    if (trimmed.startsWith('http')) {
                      if (trimmed.includes('medium.com')) {
                        return (
                          <p key={idx} className="flex items-center gap-2">
                            <a
                              href={trimmed}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-2 text-gray-300 hover:text-white transition-colors group"
                            >
                              <img
                                src="https://yanqinghot.blob.core.windows.net/public-access/Medium_logo_Monogram.svg.png"
                                alt="Medium"
                                className="w-5 h-5 sm:w-6 sm:h-6 group-hover:scale-110 transition-transform"
                              />
                              <span className="text-sm sm:text-base">Read the full story on Medium</span>
                            </a>
                          </p>
                        );
                      }
                      return (
                        <p key={idx}>
                          <a
                            href={trimmed}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:underline break-all"
                          >
                            {trimmed}
                          </a>
                        </p>
                      );
                    }
                    return <p key={idx} className="leading-relaxed">{line}</p>;
                  })}
                </div>
                <div className="flex gap-1.5 sm:gap-2 flex-wrap mt-auto">
                  {project.technologies.map(tech => (
                    <span
                      key={tech}
                      className="bg-gray-700 text-gray-300 text-xs sm:text-sm font-medium px-2 sm:px-3 py-1 sm:py-1.5 rounded-full whitespace-nowrap"
                    >
                      {tech}
                    </span>
                  ))}
                </div>
              </div>
              {(project.gifUrl || project.imageUrl) && (
                <div className="hidden md:block md:w-1/3 lg:w-2/5 rounded-xl overflow-hidden shadow-2xl">
                  <img
                    src={project.gifUrl ?? project.imageUrl}
                    alt={project.title}
                    className="w-full h-full object-cover hover:scale-105 transition-transform duration-300"
                  />
                </div>
              )}
            </div>
            <button
              onClick={() => setIsHeaderCollapsed(!isHeaderCollapsed)}
              className="absolute bottom-2 right-2 p-2 hover:bg-gray-700 rounded-lg transition-colors text-gray-400 hover:text-white"
              title="Collapse header"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
            </button>
          </div>
        )}
      </motion.div>
      <div className="flex-1 min-h-0 bg-gray-900">
        <Chat project={project} onFirstMessage={handleFirstMessage} />
      </div>
    </div>
    </>
  );
};

export default ProjectView;
