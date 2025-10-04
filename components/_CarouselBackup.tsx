import React from 'react';
import type { Project } from '../types';
import { ChevronLeftIcon } from './icons/ChevronLeftIcon';
import { ChevronRightIcon } from './icons/ChevronRightIcon';

interface CarouselBackupProps {
  projects: Project[];
  currentIndex: number;
  currentProject?: Project;
  onPrev: () => void;
  onNext: () => void;
  onGoTo: (index: number) => void;
}

// Backup of the landing hero carousel previously rendered inline in LandingPage.tsx.
// Not used by default. You can re‑use it by importing and wiring the props.
export default function CarouselBackup({
  projects,
  currentIndex,
  currentProject,
  onPrev,
  onNext,
  onGoTo,
}: CarouselBackupProps) {
  return (
    <div className="w-full bg-gray-900">
      {/* --- Carousel Section - responsive height --- */}
      <div className="h-[60vh] sm:h-[70vh] md:h-[70vh] min-h-[400px] sm:min-h-[500px] w-full relative group">
        <div className="w-full h-full">
          {projects.map((project, index) => (
            <div
              key={project.id}
              className={`absolute inset-0 w-full h-full transition-opacity duration-1000 ease-in-out ${index === currentIndex ? 'opacity-100' : 'opacity-0'}`}
              style={{
                backgroundImage: `url(${project.coverUrl ?? project.imageUrl})`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
              }}
            >
              <div className="absolute inset-0 bg-black/80" />
            </div>
          ))}
        </div>

        {/* Main content - responsive layout and typography */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-4 sm:p-6 md:p-8 text-white z-10">
          <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl xl:text-7xl font-black uppercase tracking-wider animate-fade-in-up leading-tight px-2">
            {currentProject?.title}
          </h1>
          <div className="mt-4 sm:mt-6 flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 max-w-xs sm:max-w-md md:max-w-2xl animate-fade-in-up animation-delay-200">
            {currentProject?.technologies.map((tech) => (
              <span key={tech} className="bg-white/10 text-white text-xs sm:text-sm font-medium px-2 sm:px-3 py-1 sm:py-1.5 rounded-full">
                {tech}
              </span>
            ))}
          </div>
          <button
            onClick={() => currentProject && onGoTo(currentIndex)}
            className="mt-6 sm:mt-8 bg-white text-black font-bold py-2 sm:py-3 px-6 sm:px-8 rounded-full text-sm sm:text-base md:text-lg uppercase tracking-widest hover:bg-gray-200 transform hover:scale-105 transition-all duration-300 animate-fade-in-up animation-delay-400"
          >
            Explore Project
          </button>
        </div>

        {/* Navigation Arrows - responsive sizing and positioning */}
        <button
          onClick={onPrev}
          className="absolute top-1/2 left-2 sm:left-4 -translate-y-1/2 z-20 p-2 sm:p-3 bg-white/10 rounded-full hover:bg-white/30 transition-all opacity-0 group-hover:opacity-100 text-white"
        >
          <ChevronLeftIcon />
        </button>
        <button
          onClick={onNext}
          className="absolute top-1/2 right-2 sm:right-4 -translate-y-1/2 z-20 p-2 sm:p-3 bg-white/10 rounded-full hover:bg-white/30 transition-all opacity-0 group-hover:opacity-100 text-white"
        >
          <ChevronRightIcon />
        </button>

        {/* Pagination Dots - responsive positioning */}
        <div className="absolute bottom-4 sm:bottom-8 left-1/2 -translate-x-1/2 z-20 flex space-x-2">
          {projects.map((_, slideIndex) => (
            <button
              key={slideIndex}
              onClick={() => onGoTo(slideIndex)}
              className={`w-2 h-2 sm:w-3 sm:h-3 rounded-full transition-all duration-300 ${currentIndex === slideIndex ? 'bg-white scale-125' : 'bg-white/50 hover:bg-white'}`}
              aria-label={`Go to slide ${slideIndex + 1}`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

