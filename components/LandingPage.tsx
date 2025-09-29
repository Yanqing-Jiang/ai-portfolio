
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import type { Project, ProjectYear } from '../types';
import { ChevronLeftIcon } from './icons/ChevronLeftIcon';
import { ChevronRightIcon } from './icons/ChevronRightIcon';
import { motion } from 'framer-motion';
// @ts-ignore
import { Helmet } from 'react-helmet-async';

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

interface LandingPageProps {
  projectData: ProjectYear[];
  onSelectProject: (project: Project) => void;
}

const LandingPage: React.FC<LandingPageProps> = ({ projectData, onSelectProject }) => {
  const preAiProjects = useMemo(() => projectData.find(group => group.label === 'Pre-AI Projects')?.projects ?? [], [projectData]);
  const allProjects = useMemo(() => projectData.filter(group => !group.hiddenOnLanding).flatMap(year => year.projects), [projectData]);
  
  const [currentIndex, setCurrentIndex] = useState(0);

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
      <title>Yanqing Jiang | AI ML Portfolio & Data Projects</title>
      <meta name="description" content="Explore AI & ML projects, data analytics, and LLM applications by Yanqing Jiang, including live demos and code." />
      <meta name="keywords" content="AI, ML, machine learning, data analytics, portfolio, langchain, React, FastAPI" />
      <meta name="author" content="Yanqing Jiang" />
      <meta name="robots" content="index, follow" />
      <link rel="canonical" href="https://ai.jiangyanqing.com/" />
      
      {/* Open Graph tags */}
      <meta property="og:title" content="Yanqing Jiang | AI ML Portfolio & Data Projects" />
      <meta property="og:description" content="Explore AI & ML projects, data analytics, and LLM applications by Yanqing Jiang, including live demos and code." />
      <meta property="og:type" content="website" />
      <meta property="og:url" content="https://ai.jiangyanqing.com/" />
      <meta property="og:site_name" content="Yanqing Jiang AI & ML Portfolio" />
      <meta name="image" property="og:image" content="https://yanqinghot.blob.core.windows.net/public-access/OG-Page.png" />
      <meta property="og:image:secure_url" content="https://yanqinghot.blob.core.windows.net/public-access/OG-Page.png" />
      <meta property="og:image:type" content="image/png" />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:image:alt" content="Yanqing Jiang AI & ML Portfolio - Showcasing AI, machine learning, data analytics projects" />
      
      {/* Twitter Card tags */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content="@yanqing_j" />
      <meta name="twitter:creator" content="@yanqing_j" />
      <meta name="twitter:title" content="Yanqing Jiang | AI ML Portfolio & Data Projects" />
      <meta name="twitter:description" content="Explore AI & ML projects, data analytics, and LLM applications by Yanqing Jiang, including live demos and code." />
      <meta name="twitter:image" content="https://yanqinghot.blob.core.windows.net/public-access/OG-Page.png" />
      <meta name="twitter:image:alt" content="Yanqing Jiang AI & ML Portfolio - Showcasing AI, machine learning, data analytics projects" />
      
      {/* Additional SEO tags */}
      <meta name="theme-color" content="#111827" />
      <meta name="msapplication-TileColor" content="#111827" />
      
      {/* Structured Data (JSON-LD) */}
      <script type="application/ld+json">
        {JSON.stringify({
          "@context": "https://schema.org",
          "@type": "Portfolio",
          "name": "Yanqing Jiang AI & ML Portfolio",
          "description": "AI, machine learning, data analytics projects by Yanqing Jiang",
          "url": "https://ai.jiangyanqing.com",
          "author": {
            "@type": "Person",
            "name": "Yanqing Jiang",
            "jobTitle": "Machine Learning Engineer",
            "description": "AI and ML professional specializing in machine learning, LangChain, and data-driven solutions",
            "sameAs": [
              "https://www.linkedin.com/in/jiangyanqing/",
              "https://medium.com/@yanqing_j"
            ]
          },
          "mainEntity": {
            "@type": "ItemList",
            "name": "AI and ML Projects",
            "itemListElement": allProjects.map((project, index) => ({
              "@type": "CreativeWork",
              "position": index + 1,
              "name": project.title,
              "description": project.description,
              "url": `https://ai.jiangyanqing.com/project/${project.id}`,
              "image": project.coverUrl || project.imageUrl,
              "keywords": project.technologies.join(', '),
              "author": {
                "@type": "Person",
                "name": "Yanqing Jiang"
              }
            }))
          }
        })}
      </script>
    </Helmet>
    <div className="w-full bg-gray-900">
      {/* --- Carousel Section - responsive height --- */}
      <div className="h-[60vh] sm:h-[70vh] md:h-[70vh] min-h-[400px] sm:min-h-[500px] w-full relative group">
        <div className="w-full h-full">
          {allProjects.map((project, index) => (
              <div
                  key={project.id}
                  className={`absolute inset-0 w-full h-full transition-opacity duration-1000 ease-in-out ${index === currentIndex ? 'opacity-100' : 'opacity-0'}`}
                  style={{
                      backgroundImage: `url(${project.coverUrl ?? project.imageUrl})`,
                      backgroundSize: 'cover',
                      backgroundPosition: 'center',
                  }}
              >
                  <div className="absolute inset-0 bg-black/80"></div>
              </div>
          ))}
        </div>
        
        {/* Animated Portfolio Title - responsive positioning and sizing */}
        <div className="absolute top-4 sm:top-6 md:top-10 w-full flex justify-center z-20 pointer-events-none">
            <div className="text-center animate-fade-in-down px-4">
                <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold tracking-tight text-white">
                    <span className="font-light">Yanqing</span>{' '}
                    <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
                        AI Portfolio
                    </span>
                </h2>
            </div>
        </div>
        
        {/* Main content - responsive layout and typography */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-4 sm:p-6 md:p-8 text-white z-10">
          <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl xl:text-7xl font-black uppercase tracking-wider animate-fade-in-up leading-tight px-2">
              {currentProject?.title}
          </h1>
          <div className="mt-4 sm:mt-6 flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 max-w-xs sm:max-w-md md:max-w-2xl animate-fade-in-up animation-delay-200">
              {currentProject?.technologies.map(tech => (
                  <span key={tech} className="bg-white/10 text-white text-xs sm:text-sm font-medium px-2 sm:px-3 py-1 sm:py-1.5 rounded-full">
                      {tech}
                  </span>
              ))}
          </div>
          <button
              onClick={() => currentProject && onSelectProject(currentProject)}
              className="mt-6 sm:mt-8 bg-white text-black font-bold py-2 sm:py-3 px-6 sm:px-8 
                       rounded-full text-sm sm:text-base md:text-lg uppercase tracking-widest 
                       hover:bg-gray-200 transform hover:scale-105 transition-all duration-300 
                       animate-fade-in-up animation-delay-400"
          >
              Explore Project
          </button>
        </div>

        {/* Navigation Arrows - responsive sizing and positioning */}
        <button 
          onClick={goToPrevious} 
          className="absolute top-1/2 left-2 sm:left-4 -translate-y-1/2 z-20 p-2 sm:p-3 
                   bg-white/10 rounded-full hover:bg-white/30 transition-all 
                   opacity-0 group-hover:opacity-100 text-white"
        >
          <ChevronLeftIcon />
        </button>
        <button 
          onClick={goToNext} 
          className="absolute top-1/2 right-2 sm:right-4 -translate-y-1/2 z-20 p-2 sm:p-3 
                   bg-white/10 rounded-full hover:bg-white/30 transition-all 
                   opacity-0 group-hover:opacity-100 text-white"
        >
          <ChevronRightIcon />
        </button>

        {/* Pagination Dots - responsive positioning */}
        <div className="absolute bottom-4 sm:bottom-8 left-1/2 -translate-x-1/2 z-20 flex space-x-2">
          {allProjects.map((_, slideIndex) => (
            <button
              key={slideIndex}
              onClick={() => goToSlide(slideIndex)}
              className={`w-2 h-2 sm:w-3 sm:h-3 rounded-full transition-all duration-300 ${currentIndex === slideIndex ? 'bg-white scale-125' : 'bg-white/50 hover:bg-white'}`}
              aria-label={`Go to slide ${slideIndex + 1}`}
            ></button>
          ))}
        </div>
      </div>


      <section className="relative overflow-hidden border-b border-white/5 bg-slate-950 text-slate-100">
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage: "url('https://www.jiangyanqing.com/wp-content/uploads/2021/05/bg-02-free-img.png')",
            backgroundPosition: 'top right',
            backgroundRepeat: 'no-repeat',
            backgroundSize: '65%',
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 opacity-90" />
        <div className="relative mx-auto grid max-w-6xl gap-12 px-4 py-16 sm:py-20 md:grid-cols-[minmax(0,1fr)_minmax(0,320px)] md:py-24">
          <div className="space-y-6">
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-sky-300">Hello, my name is</p>
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold leading-tight text-white">Yanqing Jiang</h1>
            <h2 className="text-xl sm:text-2xl font-semibold text-sky-200">Advance Analytics Senior Manager</h2>
            <p className="max-w-2xl text-base sm:text-lg text-slate-300">
              I unite analytics, automation, and modern AI agents to solve the hardest decision-support problems in commerce and media. From experimentation platforms to agentic workflows, I build systems that push insights directly into the hands of operators.
            </p>
            <div className="flex flex-wrap items-center gap-4 sm:gap-5">
              {contactLinks.map((item) => (
                <motion.a
                  key={item.label}
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex flex-col items-center text-slate-300 hover:text-white transition-colors"
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
          <div className="relative flex justify-center md:justify-end">
            <div className="absolute -top-6 -right-6 h-48 w-48 rounded-full bg-sky-500/50 blur-3xl" aria-hidden="true" />
            <img
              src="https://www.jiangyanqing.com/wp-content/uploads/2025/07/LinkedIn-Profile-4-e1753424574256.webp"
              alt="Portrait of Yanqing Jiang"
              className="relative z-10 w-64 rounded-3xl border border-white/10 bg-white/5 object-cover shadow-[0_25px_60px_rgba(15,118,230,0.35)]"
              loading="lazy"
            />
          </div>
        </div>
      </section>

      <section className="py-16 sm:py-20 border-b border-white/5 bg-slate-900/40">
        <div className="mx-auto flex max-w-5xl flex-col gap-8 px-4 md:flex-row md:items-start">
          <div className="md:w-1/3">
            <h2 className="text-3xl font-semibold text-white md:text-4xl">What I do</h2>
            <p className="mt-4 text-base text-slate-300">
              I move from discovery to deployment with the same hands-on ownership. Strategy is only useful when the build is production-ready.
            </p>
          </div>
          <div className="grid flex-1 gap-6 sm:grid-cols-2">
            {capabilities.map((capability) => (
              <div key={capability.title} className="rounded-2xl border border-white/10 bg-slate-900/60 p-6 shadow-[0_18px_36px_rgba(12,74,110,0.2)]">
                <h3 className="text-lg font-semibold text-white">{capability.title}</h3>
                <p className="mt-3 text-sm text-slate-300">{capability.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* --- Projects List Section - responsive layout --- */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 md:py-20">
        <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-center mb-8 sm:mb-12">
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
            AI Project Preview
          </span>
        </h2>
        <div className="space-y-12 sm:space-y-16">
          {projectData.filter(group => !group.hiddenOnLanding).map(({ year, subtitle, projects, label }) => (
            <div key={year}>
              <div className="flex flex-col sm:flex-row sm:items-baseline mb-6 sm:mb-8">
                <h3 className="text-lg sm:text-xl md:text-2xl lg:text-3xl font-bold text-gray-200">{label ?? year}</h3>
                {subtitle && <p className="mt-1 sm:mt-0 sm:ml-3 text-xs sm:text-sm md:text-base text-gray-500">{subtitle}</p>}
              </div>
              <div className="grid grid-cols-1 gap-8 sm:gap-12">
                {projects.map((project, projectIndex) => (
                  <div
                    key={project.id}
                    onClick={() => onSelectProject(project)}
                    className={`bg-gray-800/50 rounded-lg overflow-hidden transform hover:-translate-y-1 
                             transition-transform duration-300 shadow-lg hover:shadow-blue-500/20 cursor-pointer 
                             group border border-gray-700/50 flex flex-col md:flex-row items-stretch 
                             ${projectIndex % 2 !== 0 ? 'md:flex-row-reverse' : ''}`}
                  >
                    <div className="w-full md:w-2/5 xl:w-1/3 shrink-0">
                      <img 
                        src={project.coverUrl ?? project.imageUrl} 
                        alt={project.title} 
                        className="w-full h-48 sm:h-64 md:h-full object-cover group-hover:scale-105 transition-transform duration-300" 
                      />
                    </div>
                    <div className="flex-1 p-4 sm:p-6 lg:p-8 flex flex-col justify-center">
                      <h4 className="text-base sm:text-lg md:text-xl lg:text-2xl font-bold text-white mb-2 sm:mb-3">{project.title}</h4>
                      <p className="text-gray-400 text-xs sm:text-sm md:text-base lg:text-lg mb-4 
                                  leading-relaxed">
                        {project.description.length > 150 ? `${project.description.substring(0, 150)}...` : project.description}
                      </p>
                      <div className="flex flex-wrap gap-1.5 sm:gap-2 mt-auto">
                        {project.technologies.slice(0, 5).map(tech => (
                          <span 
                            key={tech} 
                            className="bg-gray-700 text-gray-300 text-xs sm:text-sm font-medium 
                                     px-2 sm:px-2.5 py-1 rounded-md"
                          >
                            {tech}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {preAiProjects.length > 0 && (
        <section className="bg-slate-900/60 border-t border-white/5">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
            <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-center mb-8 sm:mb-12">
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
                Pre-AI Projects
              </span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8 sm:gap-10">
              {preAiProjects.map((project) => (
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
                    <p className="text-gray-400 text-sm sm:text-base leading-relaxed mb-6">
                      {project.description.length > 150 ? `${project.description.substring(0, 150)}...` : project.description}
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
              ))}
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
    </>
  );
};

export default LandingPage;
