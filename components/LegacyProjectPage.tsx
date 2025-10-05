import React from 'react';
import type { Project } from '../types';

interface LegacyProjectPageProps {
  project: Project;
}

const LegacyProjectPage: React.FC<LegacyProjectPageProps> = ({ project }) => {
  return (
    <div className="flex flex-col min-h-full bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <header className="relative overflow-hidden">
        {project.coverUrl && (
          <div className="absolute inset-0">
            <img
              src={project.coverUrl}
              alt={project.title}
              className="w-full h-full object-cover opacity-30"
            />
          </div>
        )}
        <div className="relative mx-auto max-w-5xl px-4 py-16 sm:py-20">
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-sky-300">Pre-AI Project</p>
          <h1 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-bold text-white">{project.title}</h1>
          <p className="mt-6 max-w-3xl text-base sm:text-lg text-slate-200 leading-relaxed">
            {project.description}
          </p>
        </div>
      </header>

      <main className="flex-1">
              <style>{`
        .legacy-content-wrapper :where(h1,h2,h3,h4) {
          color: inherit;
        }
        .legacy-content img {
          max-width: 100%;
          border-radius: 0.75rem;
          margin: 1.5rem auto;
        }
        .legacy-content ul {
          list-style: disc;
          margin-left: 1.5rem;
          color: #cbd5f5;
        }
        .legacy-content li {
          margin-bottom: 0.5rem;
        }
        .legacy-hero {
          max-width: 100%;
          border-radius: 1rem;
          margin: 1.5rem auto;
          display: block;
        }
        .legacy-content .legacy-gallery {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
          gap: 1rem;
          margin: 1.5rem 0;
        }
        .legacy-content .inventory-content {
          display: flex;
          flex-direction: column;
          gap: 2rem;
        }
        .legacy-content .inventory-main {
          display: block;
          width: 100%;
          margin: 0;
        }
        .legacy-content .inventory-row {
          display: flex;
          flex-direction: row;
          align-items: flex-start;
          gap: 2rem;
        }
        .legacy-content .inventory-sidebar {
          flex: 0 0 auto;
          width: min(280px, 100%);
          margin: 0;
        }
        .legacy-content .inventory-text {
          flex: 1 1 0%;
          color: inherit;
        }
        @media (min-width: 1024px) {
          .legacy-content .inventory-content {
            gap: 2.5rem;
          }
          .legacy-content .inventory-row {
            gap: 2.5rem;
          }
          .legacy-content .inventory-sidebar {
            flex-basis: 300px;
          }
          .legacy-content .inventory-text {
            padding-left: 0.5rem;
          }
        }
      `}</style>

        <div className="legacy-content-wrapper mx-auto max-w-4xl px-4 py-10 sm:py-14 prose prose-invert prose-img:rounded-xl prose-headings:text-white">
          {project.contentHtml ? (
            <div className="legacy-content" dangerouslySetInnerHTML={{ __html: project.contentHtml }} />
          ) : (
            <p className="text-slate-300">Detailed content coming soon.</p>
          )}
        </div>
      </main>
    </div>
  );
};

export default LegacyProjectPage;

