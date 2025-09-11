import React from 'react';
import { HeaderProps } from '../types';

export const Header: React.FC<HeaderProps> = ({
  title,
  description,
  technologies,
  imageUrl,
  showProcessPanel,
  onToggleProcess
}) => {
  return (
    <div className="bg-gray-800 border-b border-gray-700">
      <div className="w-full max-w-5xl mx-auto flex flex-col md:flex-row items-center gap-3 sm:gap-4 md:gap-6 p-3 sm:p-4 md:p-6 lg:p-8">
        <div className="flex-1 text-center md:text-left">
          <h1 className="text-xl sm:text-2xl md:text-3xl lg:text-4xl font-bold text-white">{title}</h1>
          <div className="mt-2 sm:mt-3 md:mt-4 text-gray-300 text-xs sm:text-sm md:text-base space-y-0.5 sm:space-y-1 md:space-y-1.5">
            {description.split('•').filter(line => line.trim()).map((line, index) => (
              <div key={index}>• {line.trim()}</div>
            ))}
          </div>
          <div className="mt-2 sm:mt-3 md:mt-4 flex flex-wrap gap-1.5 sm:gap-2 md:gap-2.5 justify-center md:justify-start">
            {technologies.map((tag) => (
              <span key={tag} className="px-2 sm:px-3 py-0.5 sm:py-1 md:py-1.5 rounded-full bg-gray-700 text-gray-200 text-[10px] sm:text-xs md:text-sm border border-gray-600 shadow-inner">
                {tag}
              </span>
            ))}
          </div>
        </div>
        {imageUrl && (
          <div className="hidden md:block w-full md:w-1/3">
            <img src={imageUrl} alt={title} className="w-full h-40 sm:h-48 object-cover rounded-lg border border-gray-700 shadow" />
          </div>
        )}
      </div>
    </div>
  );
};