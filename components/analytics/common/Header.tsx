import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { HeaderProps } from '../types';

export const Header: React.FC<HeaderProps> = ({
  title,
  description,
  technologies,
  imageUrl,
  showProcessPanel,
  onToggleProcess,
  isCollapsed = false,
  onToggleCollapse
}) => {
  if (isCollapsed) {
    return (
      <motion.div 
        initial={{ height: 'auto' }}
        animate={{ height: 50 }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        className="bg-gray-800 border-b border-gray-700"
      >
        <div className="w-full max-w-5xl mx-auto flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-white truncate">{title}</h1>
            <div className="hidden sm:flex gap-2">
              {technologies.slice(0, 3).map((tag) => (
                <span key={tag} className="px-2 py-0.5 rounded-full bg-gray-700 text-gray-200 text-xs border border-gray-600">
                  {tag}
                </span>
              ))}
              {technologies.length > 3 && (
                <span className="px-2 py-0.5 rounded-full bg-gray-700 text-gray-200 text-xs border border-gray-600">
                  +{technologies.length - 3}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {showProcessPanel !== undefined && onToggleProcess && (
              <button
                onClick={onToggleProcess}
                className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors"
              >
                {showProcessPanel ? 'Hide' : 'Show'} Process
              </button>
            )}
            {onToggleCollapse && (
              <button
                onClick={onToggleCollapse}
                className="p-2 hover:bg-gray-700 rounded-lg transition-colors text-gray-400 hover:text-white"
                title="Expand header"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div 
      initial={{ height: 50 }}
      animate={{ height: 'auto' }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
      className="bg-gray-800 border-b border-gray-700"
    >
      <div className="w-full max-w-5xl mx-auto p-3 sm:p-4 md:p-6 lg:p-8">
        {/* Collapse button */}
        {onToggleCollapse && (
          <div className="flex justify-end mb-2">
            <button
              onClick={onToggleCollapse}
              className="p-2 hover:bg-gray-700 rounded-lg transition-colors text-gray-400 hover:text-white"
              title="Collapse header"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
            </button>
          </div>
        )}
        
        <div className="flex flex-col md:flex-row items-center gap-3 sm:gap-4 md:gap-6">
          <div className="flex-1 text-center md:text-left">
            <h1 className="text-xl sm:text-2xl md:text-3xl lg:text-4xl font-bold text-white">{title}</h1>
            <AnimatePresence>
              <motion.div 
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
                className="mt-2 sm:mt-3 md:mt-4 text-gray-300 text-xs sm:text-sm md:text-base space-y-0.5 sm:space-y-1 md:space-y-1.5"
              >
                {description.split('•').filter(line => line.trim()).map((line, index) => (
                  <div key={index}>• {line.trim()}</div>
                ))}
              </motion.div>
            </AnimatePresence>
            <AnimatePresence>
              <motion.div 
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3, delay: 0.1 }}
                className="mt-2 sm:mt-3 md:mt-4 flex flex-wrap gap-1.5 sm:gap-2 md:gap-2.5 justify-center md:justify-start"
              >
                {technologies.map((tag) => (
                  <span key={tag} className="px-2 sm:px-3 py-0.5 sm:py-1 md:py-1.5 rounded-full bg-gray-700 text-gray-200 text-[10px] sm:text-xs md:text-sm border border-gray-600 shadow-inner">
                    {tag}
                  </span>
                ))}
              </motion.div>
            </AnimatePresence>
          </div>
          {imageUrl && (
            <AnimatePresence>
              <motion.div 
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                transition={{ duration: 0.3, delay: 0.2 }}
                className="hidden md:block w-full md:w-1/3"
              >
                <img src={imageUrl} alt={title} className="w-full h-40 sm:h-48 object-cover rounded-lg border border-gray-700 shadow" />
              </motion.div>
            </AnimatePresence>
          )}
        </div>
      </div>
    </motion.div>
  );
};