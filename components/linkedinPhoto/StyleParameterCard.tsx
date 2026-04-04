/**
 * StyleParameterCard - Reusable card component for Custom Style builder preset options
 *
 * Renders a clickable card with icon, title, and description
 * Provides visual feedback for selected state
 */

import React from 'react';
import { Check } from 'lucide-react';

interface StyleParameterCardProps {
  icon: string | React.ReactNode;
  title: string;
  description: string;
  selected: boolean;
  onClick: () => void;
}

export const StyleParameterCard: React.FC<StyleParameterCardProps> = ({
  icon,
  title,
  description,
  selected,
  onClick,
}) => {
  return (
    <button
      onClick={onClick}
      className={`
        relative flex flex-col items-center p-4 rounded-xl border-2 transition-all
        hover:shadow-md hover:scale-[1.02] active:scale-[0.98]
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
        ${
          selected
            ? 'border-blue-500 bg-blue-50 dark:bg-blue-950 shadow-sm'
            : 'border-border bg-card hover:border-muted-foreground/30'
        }
      `}
      type="button"
      aria-pressed={selected}
    >
      {/* Selected checkmark badge */}
      {selected && (
        <div className="absolute top-2 right-2 bg-blue-500 rounded-full p-1">
          <Check className="w-3 h-3 text-white" />
        </div>
      )}

      {/* Icon */}
      <div className="text-3xl mb-2">
        {typeof icon === 'string' ? icon : icon}
      </div>

      {/* Title */}
      <div className={`font-semibold text-sm mb-1 text-center ${
        selected ? 'text-blue-700 dark:text-blue-300' : 'text-foreground'
      }`}>
        {title}
      </div>

      {/* Description */}
      <div className={`text-xs text-center ${
        selected ? 'text-blue-600 dark:text-blue-400' : 'text-muted-foreground'
      }`}>
        {description}
      </div>
    </button>
  );
};
