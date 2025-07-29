
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import type { Project, ProjectYear } from '../types';
import { ChevronLeftIcon } from './icons/ChevronLeftIcon';
import { ChevronRightIcon } from './icons/ChevronRightIcon';
import { motion } from 'framer-motion';
// @ts-ignore
import { Helmet } from 'react-helmet-async';

interface LandingPageProps {
  projectData: ProjectYear[];
  onSelectProject: (project: Project) => void;
}

const LandingPage: React.FC<LandingPageProps> = ({ projectData, onSelectProject }) => {
  const allProjects = useMemo(() => projectData.flatMap(year => year.projects), [projectData]);
  
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
                        AI & ML Portfolio
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

      {/* --- Social Icons Section - responsive layout --- */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-2 sm:gap-4 py-4 sm:py-6 px-4" data-testid="social-icons">
        <h3 className="text-xl sm:text-2xl md:text-3xl font-bold mb-2 sm:mb-0 sm:mr-2 text-center">Find me at:</h3>
        <div className="flex items-center gap-4 sm:gap-6 md:gap-8">
        {[
          {
            href: 'https://www.linkedin.com/in/jiangyanqing/',
            label: 'LinkedIn',
            svg: (
              <svg viewBox="0 0 34 34" className="w-8 h-8 sm:w-10 sm:h-10" xmlns="http://www.w3.org/2000/svg">
                <rect width="34" height="34" rx="4" fill="#0A66C2"/>
                <path d="M8 12.5h4v13H8v-13zm2-6.5C8.9 6 8 6.9 8 8s.9 2 2 2 2-.9 2-2-.9-2-2-2zm6 6.5h3.8v1.8h.1c.5-1 1.9-2 3.9-2 4.1 0 4.9 2.7 4.9 6.1V25.5h-4v-6.4c0-1.5 0-3.5-2.1-3.5-2.1 0-2.4 1.6-2.4 3.4v6.5h-4v-13z" fill="#fff"/>
              </svg>
            ),
          },
          {
            href: 'https://medium.com/@yanqing_j',
            label: 'Medium',
            svg: (
              <img src="https://yanqinghot.blob.core.windows.net/public-access/Medium_logo_Monogram.svg.png" alt="Medium" className="w-8 h-8 sm:w-10 sm:h-10" />
            ),
          },
          {
            href: 'mailto:jiangyanqing90@gmail.com',
            label: 'Email',
            svg: (
              <svg viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8 sm:w-10 sm:h-10">
                <path d="M20 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V6a2 2 0 00-2-2zm0 2l-8 5-8-5h16zm0 12H4V8l8 5 8-5v10z" />
              </svg>
            ),
          },
        ].map((item, idx) => (
          <motion.a
            key={idx}
            href={item.href}
            target="_blank"
            rel="noopener noreferrer"
            className="relative group text-gray-400 hover:text-white"
            initial="rest"
            whileHover="hover"
            animate="rest"
          >
            <motion.div variants={{ rest: { scale: 1 }, hover: { scale: 1.15 } }} className="flex items-center justify-center">
              {item.svg}
            </motion.div>
            {/* Tooltip - responsive positioning */}
            <motion.div
              variants={{ rest: { opacity: 0, y: 10, pointerEvents: 'none' }, hover: { opacity: 1, y: 0 } }}
              transition={{ duration: 0.3 }}
              className="absolute bottom-10 sm:bottom-12 left-1/2 -translate-x-1/2 bg-gray-800 px-2 sm:px-3 py-1 text-xs sm:text-sm rounded-md text-white whitespace-nowrap"
            >
              {item.label}
            </motion.div>
          </motion.a>
        ))}
        </div>
      </div>

      {/* --- Projects List Section - responsive layout --- */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 md:py-20">
        <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-center mb-8 sm:mb-12">
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
            Project Preview
          </span>
        </h2>
        <div className="space-y-12 sm:space-y-16">
          {projectData.map(({ year, subtitle, projects }) => (
            <div key={year}>
              <div className="flex flex-col sm:flex-row sm:items-baseline mb-6 sm:mb-8">
                <h3 className="text-lg sm:text-xl md:text-2xl lg:text-3xl font-bold text-gray-200">{year}</h3>
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
