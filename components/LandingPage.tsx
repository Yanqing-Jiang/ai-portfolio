
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import type { Project, ProjectYear } from '../types';
import { ChevronLeftIcon } from './icons/ChevronLeftIcon';
import { ChevronRightIcon } from './icons/ChevronRightIcon';
import { motion } from 'framer-motion';
import Style2MorphWords from './hero/Style2MorphWords';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import {
  DEFAULT_OG_IMAGE,
  DEFAULT_THEME_COLOR,
  DEFAULT_TWITTER_HANDLE,
  LANDING_SEO,
  SITE_NAME,
} from '../constants/seo';
import { buildLandingSchemas, toNavigationFromProjects } from '../constants/structuredData';

const contactLinks = [
  {
    label: 'LinkedIn',
    href: 'https://www.linkedin.com/in/jiangyanqing/',
    icon: (
      <svg viewBox="0 0 34 34" className="w-8 h-8 sm:w-10 sm:h-10" xmlns="http://www.w3.org/2000/svg">
        <rect width="34" height="34" rx="4" fill="#0A66C2"/>
        <path d="M8 12.5h4v13H8v-13zm2-6.5C8.9 6 8 6.9 8 8s.9 2 2 2 2-.9 2-2-.9-2-2-2zm6 6.5h3.8v1.8h.1c.5-1 1.9-2 3.9-2 4.1 0 4.9 2.7 4.9 6.1V25.5h-4v-6.4c0-1.5 0-3.5-2.1-3.5-2.1 0-2.4 1.6-2.4 3.4v6.5h-4v-13z" fill="#fff"/>
      </svg>
    ),
  },
  {
    label: 'Medium',
    href: 'https://medium.com/@yanqing_j',
    icon: (
      <img src="https://yanqinghot.blob.core.windows.net/public-access/Medium_logo_Monogram.svg.png" alt="Medium" className="w-8 h-8 sm:w-10 sm:h-10" />
    ),
  },
  {
    label: 'Email',
    href: 'mailto:jiangyanqing90@gmail.com',
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8 sm:w-10 sm:h-10">
        <path d="M20 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V6a2 2 0 00-2-2zm0 2l-8 5-8-5h16zm0 12H4V8l8 5 8-5v10z" />
      </svg>
    ),
  },
] as const;

const capabilities = [
  {
    title: 'Data Automation & AI Workflow',
    description: 'Saved thousands of labor hours and reducing reliance on manual workflows. From Gen AI-powered web apps to smart bidding platforms, drive efficiency and intelligence into the analytics lifecycle by automating the boring stuff.',
  },
  {
    title: 'Data Science Solutions',
    description: 'Architect machine learning pipelines, experimentation frameworks, and predictive models that have delivered $150M+ incremental revenue.',
  },
  {
    title: 'Reporting & Insight Platforms',
    description: 'Lead end-to-end design of enterprise analytics tooling that drives measurable impact across digital commerce and retail media, and build BI ecosystems that surface the right metrics to executive stakeholders when they need them.',
  },
  {
    title: 'Enterprise Data Infrastructure & Governance',
    description: 'Hands-on with MS SQL Server from advanced queries to views and stored procedures powering terabyte-scale systems.',
  },
] as const;

type TechCategory = 'ai' | 'data' | 'frontend' | 'infra' | 'ml' | 'default';

const TECH_CATEGORY_CLASSES: Record<TechCategory, string> = {
  ai: 'border bg-emerald-600/20 text-emerald-300 border-emerald-500/30 hover:bg-emerald-600/30',
  data: 'border bg-emerald-500/20 text-emerald-200 border-emerald-500/30 hover:bg-emerald-500/30',
  frontend: 'border bg-purple-500/20 text-purple-200 border-purple-500/30 hover:bg-purple-500/30',
  infra: 'border bg-orange-500/20 text-orange-200 border-orange-500/30 hover:bg-orange-500/30',
  ml: 'border bg-pink-500/20 text-pink-200 border-pink-500/30 hover:bg-pink-500/30',
  default: 'border bg-sky-500/15 text-sky-200 border-sky-500/30 hover:bg-sky-500/25',
};

const TECH_EXACT_CATEGORIES: Record<string, TechCategory> = {
  'single agent workflow': 'ai',
  'multi-agent workflow': 'ai',
  'human-in-the-loop': 'frontend',
  'human-in-loop': 'frontend',
  'rag': 'ml',
  'long-term memory': 'ml',
  'long term memory': 'ml',
  'langgraph': 'ai',
  'agent orchestration': 'ai',
  'agentic framework': 'ai',
  'agentic workflow': 'ai',
  'agent': 'ai',
  'agents': 'ai',
  'workflow automation': 'ai',
  'automation': 'ai',
  'ask my resume': 'ai',
  'vector search': 'data',
  'faiss': 'data',
  'function calling': 'ai',
  'zero-shot prompting': 'ai',
  'json structured output': 'ai',
  'smart sql': 'data',
  'state management': 'ml',
  'analytics automation': 'ai',
  'decision intelligence': 'ai',
  'talent ai': 'ai',
  'agentic trading': 'ai',
  'risk management': 'ai',
  'power platform': 'infra',
  'power apps': 'infra',
  'power automate': 'infra',
  'workflow platform': 'infra',
  'procurement automation': 'infra',
  'capital planning': 'infra',
  'workflow orchestration': 'infra',
  'platform': 'infra',
  'cloud': 'infra',
  'azure': 'infra',
  'ibkr api': 'infra',
  'api': 'infra',
  'apis': 'infra',
  'docker': 'infra',
  'data automation': 'data',
  'data governance': 'data',
  'data science': 'ml',
  'data infrastructure & governance': 'data',
  'enterprise data infrastructure & governance': 'data',
  'supabase': 'data',
  'postgresql': 'data',
  'fastapi': 'data',
  'database': 'data',
  'sql': 'data',
  'ms sql server': 'data',
  'javascript': 'frontend',
  'tailwindcss': 'frontend',
  'react': 'frontend',
  'typescript': 'frontend',
  'vite': 'frontend',
  'echarts': 'frontend',
  'power bi': 'data',
  'bi automation': 'data',
  'reporting & insight platforms': 'data',
  'supply chain analytics': 'data',
  'analytics': 'ml',
  'insight automation': 'ai',
  'enterprise data platform': 'data',
  'long-term memory agent': 'ai',
  'enterprise automation': 'ai',
};

const TECH_CATEGORY_KEYWORDS: Array<{ category: TechCategory; keywords: string[] }> = [
  { category: 'ai', keywords: ['agent', 'workflow', 'rag', 'memory', 'orchestration', 'automation', 'copilot', 'langgraph', 'vector', 'prompt', 'resume'] },
  { category: 'data', keywords: ['sql', 'database', 'supabase', 'postgres', 'fastapi', 'data', 'governance', 'pipeline', 'warehouse', 'bi', 'analytics'] },
  { category: 'frontend', keywords: ['react', 'typescript', 'tailwind', 'echarts', 'ui', 'frontend', 'javascript', 'css', 'ux'] },
  { category: 'infra', keywords: ['azure', 'docker', 'api', 'cloud', 'platform', 'apps', 'automate', 'ops', 'infrastructure', 'procurement'] },
  { category: 'ml', keywords: ['model', 'forecast', 'ml', 'machine learning', 'experiment', 'causal', 'science'] },
];

const getTechBadgeClass = (tech: string) => {
  const normalized = tech.trim().toLowerCase();
  if (TECH_EXACT_CATEGORIES[normalized]) {
    return TECH_CATEGORY_CLASSES[TECH_EXACT_CATEGORIES[normalized]];
  }
  for (const { category, keywords } of TECH_CATEGORY_KEYWORDS) {
    if (keywords.some(keyword => normalized.includes(keyword))) {
      return TECH_CATEGORY_CLASSES[category];
    }
  }
  return TECH_CATEGORY_CLASSES.default;
};

interface LandingPageProps {
  projectData: ProjectYear[];
  onSelectProject: (project: Project) => void;
}

const LandingPage: React.FC<LandingPageProps> = ({ projectData, onSelectProject }) => {
  const preAiProjects = useMemo(
    () => projectData.find(group => group.label === 'Pre-AI Projects')?.projects ?? [],
    [projectData]
  );
  const allProjects = useMemo(
    () => projectData.filter(group => !group.hiddenOnLanding).flatMap(year => year.projects),
    [projectData]
  );
  const navigationLinks = useMemo(() => toNavigationFromProjects(allProjects), [allProjects]);
  const landingSchemas = useMemo(
    () => buildLandingSchemas(allProjects, navigationLinks),
    [allProjects, navigationLinks]
  );
  const landingKeywords = useMemo(() => LANDING_SEO.keywords.join(', '), []);
  
  const [currentIndex, setCurrentIndex] = useState(0);
  const heroRef = useRef<HTMLElement | null>(null);
  const [heroMouse, setHeroMouse] = useState<{ x: number; y: number } | null>(null);
  const pageRef = useRef<HTMLDivElement | null>(null);
  const [pageMouse, setPageMouse] = useState<{ x: number; y: number } | null>(null);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const update = () => setIsMobile(window.innerWidth < 768);
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  const onHeroMouseMove = useCallback((e: React.MouseEvent<HTMLElement>) => {
    if (!heroRef.current) return;
    const rect = heroRef.current.getBoundingClientRect();
    setHeroMouse({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }, []);

  const goToPrevious = () => {
    const isFirstSlide = currentIndex === 0;
    const newIndex = isFirstSlide ? allProjects.length - 1 : currentIndex - 1;
    setCurrentIndex(newIndex);
  };

  const goToNext = useCallback(() => {
    const isLastSlide = currentIndex === allProjects.length - 1;
    const newIndex = isLastSlide ? 0 : currentIndex + 1;
    setCurrentIndex(newIndex);
  }, [currentIndex, allProjects.length]);

  const goToSlide = (slideIndex: number) => {
    setCurrentIndex(slideIndex);
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      goToNext();
    }, 5000);
    return () => clearTimeout(timer);
  }, [currentIndex, goToNext]);
  
  const currentProject = allProjects[currentIndex];

  return (
    <>
    <Helmet>
      <title>{LANDING_SEO.title}</title>
      <meta name="description" content={LANDING_SEO.description} />
      <meta name="keywords" content={landingKeywords} />
      <meta name="author" content={LANDING_SEO.author} />
      <meta name="subject" content={LANDING_SEO.subject} />
      <meta name="category" content={LANDING_SEO.category} />
      <meta name="robots" content="index, follow" />
      <link rel="canonical" href={LANDING_SEO.canonical} />
      <link rel="alternate" hrefLang="en-us" href={LANDING_SEO.canonical} />
      {LANDING_SEO.sameAs?.map((profile) => (
        <link key={profile} rel="me" href={profile} />
      ))}

      {/* Open Graph tags */}
      <meta property="og:type" content="website" />
      <meta property="og:title" content={LANDING_SEO.title} />
      <meta property="og:description" content={LANDING_SEO.description} />
      <meta property="og:url" content={LANDING_SEO.canonical} />
      <meta property="og:site_name" content={SITE_NAME} />
      <meta property="og:locale" content={LANDING_SEO.locale} />
      <meta property="og:updated_time" content={LANDING_SEO.updatedTime} />
      <meta property="og:image" content={DEFAULT_OG_IMAGE} />
      <meta property="og:image:secure_url" content={DEFAULT_OG_IMAGE} />
      <meta property="og:image:type" content="image/png" />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:image:alt" content="AI systems and analytics automation portfolio by Yanqing Jiang" />

      {/* Twitter Card tags */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content={DEFAULT_TWITTER_HANDLE} />
      <meta name="twitter:creator" content={DEFAULT_TWITTER_HANDLE} />
      <meta name="twitter:title" content={LANDING_SEO.title} />
      <meta name="twitter:description" content={LANDING_SEO.description} />
      <meta name="twitter:image" content={DEFAULT_OG_IMAGE} />
      <meta name="twitter:image:alt" content="Yanqing Jiang AI systems and analytics automation showcase" />

      {/* Additional SEO tags */}
      <meta name="theme-color" content={DEFAULT_THEME_COLOR} />
      <meta name="msapplication-TileColor" content={DEFAULT_THEME_COLOR} />

      {/* Structured Data (JSON-LD) */}
      {landingSchemas.map((schema, index) => (
        <script key={`landing-schema-${index}`} type="application/ld+json">
          {JSON.stringify(schema)}
        </script>
      ))}
    </Helmet>
    <div
      ref={pageRef}
      onMouseMove={(e) => setPageMouse({ x: e.clientX, y: e.clientY })}
      className="relative min-h-screen bg-slate-950 text-gray-300"
    >
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-10"
        style={{
          background: pageMouse
            ? `radial-gradient(360px 360px at ${pageMouse.x}px ${pageMouse.y}px, rgba(56,189,248,0.20), transparent 70%)`
            : 'radial-gradient(360px 360px at 50% 10%, rgba(56,189,248,0.20), transparent 70%)',
          transition: 'background 200ms ease-out',
        }}
      />
      <div className="relative z-20">
        <section ref={heroRef as any} onMouseMove={onHeroMouseMove} className="relative overflow-hidden border-b border-white/5">
          <div className="relative mx-auto grid max-w-7xl grid-cols-1 gap-10 px-4 sm:px-6 lg:px-8 py-12 sm:py-16 md:py-20 lg:grid-cols-[3fr_2fr] lg:items-center">
            <div className="flex flex-col">
              <h1
                className="text-balance font-extrabold text-white tracking-[-0.01em] leading-[1.1]"
                style={{ fontSize: 'clamp(44px, 4.5vw, 56px)' }}
              >
                Yanqing Jiang
              </h1>
              <div
                className="mt-4 font-bold text-sky-200"
                style={{ fontSize: 'clamp(17px, 2vw, 22px)' }}
              >
                Advanced Analytics @ P&amp;G
              </div>
              <div className="mt-5 flex flex-wrap items-center gap-5 text-gray-400">
                {contactLinks.map((item) => (
                  <motion.a
                    key={item.label}
                    href={item.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex flex-col items-center hover:text-white transition-colors"
                    initial="rest"
                    whileHover="hover"
                    animate="rest"
                  >
                    <motion.div
                      variants={{ rest: { scale: 1 }, hover: { scale: 1.1 } }}
                      className="flex items-center justify-center rounded-full border border-white/15 bg-white/10 p-3 backdrop-blur-sm"
                    >
                      {item.icon}
                    </motion.div>
                    <motion.span
                      variants={{ rest: { opacity: 0.8, y: 0 }, hover: { opacity: 1, y: -2 } }}
                      className="mt-2 text-xs uppercase tracking-wide"
                    >
                      {item.label}
                    </motion.span>
                  </motion.a>
                ))}
              </div>
            </div>
            <div className="relative flex justify-center lg:justify-end">
              <div className="relative z-10 w-full max-w-xl text-left">
                <Style2MorphWords
                  variant="inline"
                  size="xl"
                  gradient={false}
                  intervalMs={2900}
                  words={['AI Agent Systems', 'Insight Automation', 'Enterprise Data Platform', 'Long-term Memory Agent']}
                />
              </div>
            </div>
          </div>
        </section>
        {/* Animation Showcase removed per request */}

        {/* --- Projects List Section - responsive layout --- */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 md:py-20">
          <h2
            className="font-black text-left text-balance bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500"
            style={{ fontSize: 'clamp(44px, 4.5vw, 56px)', textShadow: '0 0 40px rgba(56, 189, 248, 0.3)' }}
          >
            AI Project Preview
          </h2>
          <div className="space-y-12 sm:space-y-16">
          {projectData.filter(group => !group.hiddenOnLanding).map(({ year, subtitle, projects, label }) => (
            <div key={year}>
              <div className="flex flex-col sm:flex-row sm:items-baseline mb-6 sm:mb-8">
                <h3 className="text-lg sm:text-xl md:text-2xl lg:text-3xl font-extrabold text-sky-100">{label ?? year}</h3>
                {subtitle && <p className="mt-1 sm:mt-0 sm:ml-3 text-sm sm:text-base md:text-lg text-gray-400">{subtitle}</p>}
              </div>
              <div className="grid grid-cols-1 gap-8 sm:gap-12">
                {projects.map((project, projectIndex) => {
                  const useContainLayout = project.id === 'next-gen-analytics-memory' || project.id === 'next-gen-analytics-sql';
                  const previewDescription = project.cardDescription ?? project.description;
                  const truncatedDescription =
                    previewDescription.length > 200 ? `${previewDescription.substring(0, 200)}...` : previewDescription;

                  return (
                    <div
                      key={project.id}
                      onClick={() => onSelectProject(project)}
                      className={`rounded-lg overflow-hidden transform hover:-translate-y-1 
                             transition-transform duration-300 shadow-lg hover:shadow-blue-500/20 cursor-pointer 
                             group border border-gray-700/50 bg-gray-800/50 flex flex-col md:flex-row items-stretch 
                             ${projectIndex % 2 !== 0 ? 'md:flex-row-reverse' : ''}`}
                    >
                      <div
                        className={`w-full md:w-2/5 xl:w-1/3 shrink-0${useContainLayout ? ' bg-gray-950/70 flex items-center justify-center' : ''}`}
                      >
                        <img
                          src={project.coverUrl ?? project.imageUrl}
                          alt={project.title}
                          loading="lazy"
                          className={`${useContainLayout
                          ? 'w-full h-auto max-h-64 sm:max-h-72 md:max-h-[22rem] min-h-[12rem] object-contain transition-transform duration-300 group-hover:scale-105'
                          : 'w-full h-48 sm:h-64 md:h-full object-cover transition-transform duration-300 group-hover:scale-105'
                          }`}
                        />
                      </div>
                      <div className="flex-1 p-4 sm:p-6 lg:p-8 flex flex-col justify-center">
                        <h4 className="text-base sm:text-lg md:text-xl lg:text-2xl font-bold text-white mb-2 sm:mb-3">{project.title}</h4>
                        <p className="text-gray-300 text-pretty text-xs sm:text-sm md:text-base lg:text-lg leading-[1.7] mb-4 max-w-prose">
                          {truncatedDescription}
                        </p>
                        <div className="flex flex-wrap gap-1.5 sm:gap-2 mt-auto">
                          {project.technologies.slice(0, 5).map(tech => (
                            <span
                              key={tech}
                              className={`text-xs sm:text-sm font-medium px-2 sm:px-2.5 py-1 rounded-md transition-colors duration-200 ${getTechBadgeClass(tech)}`}
                            >
                              {tech}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {preAiProjects.length > 0 && (
        <section className="bg-gray-900 border-t border-white/5">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
            <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-center text-sky-100 mb-8 sm:mb-12">
              Pre-AI Projects
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8 sm:gap-10">
              {preAiProjects.map((project) => {
                const previewDescription = project.cardDescription ?? project.description;
                const truncatedDescription =
                  previewDescription.length > 200 ? `${previewDescription.substring(0, 200)}...` : previewDescription;
                return (
                <div
                  key={project.id}
                  className="bg-gray-800/50 rounded-lg overflow-hidden transform hover:-translate-y-1 transition-transform duration-300 shadow-lg hover:shadow-blue-500/20 border border-gray-700/50 flex flex-col"
                >
                  <div className="w-full h-52 bg-gray-900 overflow-hidden">
                    <img
                      src={project.coverUrl ?? project.imageUrl}
                      alt={project.title}
                      className="w-full h-full object-cover transition-transform duration-300 hover:scale-105"
                      loading="lazy"
                    />
                  </div>
                  <div className="flex-1 p-4 sm:p-6 flex flex-col">
                    <h3 className="text-lg sm:text-xl font-bold text-white mb-3">{project.title}</h3>
                    <p className="text-gray-300 text-sm sm:text-base leading-[1.7] mb-6">
                      {truncatedDescription}
                    </p>
                    <div className="mt-auto">
                      <button
                        type="button"
                        onClick={() => onSelectProject(project)}
                        className="inline-flex items-center gap-2 text-sm font-medium text-sky-300 hover:text-sky-100 transition-colors"
                      >
                        Visit case study
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L6.75 17.25" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h9v9" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              )})}
            </div>
          </div>
        </section>
      )}



      <style>{`
        @keyframes fade-in-up {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes fade-in-down {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in-up { animation: fade-in-up 0.8s ease-out forwards; }
        .animate-fade-in-down { animation: fade-in-down 1s ease-out forwards; }
        .animation-delay-200 { animation-delay: 0.2s; }
        .animation-delay-400 { animation-delay: 0.4s; }
       `}</style>
      </div>
    </div>
    </>
  );
};

export default LandingPage;

