import React from 'react';
import { motion } from 'framer-motion';
import { GLASS, ELEMENT_COLORS } from '../designTokens';
import { fadeInUp, pickVariants } from '../animations';
import type { ElementType } from '../../lib/fortuneTypes';

interface DynamicCardProps {
  title: string;
  description: string;
  effect?: string;
  elements?: ElementType[];
  accentColor?: string;
  isReplay?: boolean;
}

export const DynamicCard: React.FC<DynamicCardProps> = ({
  title,
  description,
  effect,
  elements = [],
  accentColor = '#f43f5e',
  isReplay = false,
}) => {
  return (
    <motion.div
      variants={pickVariants(isReplay, fadeInUp)}
      className={`${GLASS} p-4`}
    >
      <div className="flex items-start gap-3">
        <div
          className="h-1 w-1 rounded-full mt-2 flex-none"
          style={{ background: accentColor }}
        />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">{description}</p>
          {effect && (
            <p className="mt-1.5 text-[11px] text-slate-300 italic">{effect}</p>
          )}
          {elements.length > 0 && (
            <div className="mt-2 flex gap-1.5">
              {elements.map((el) => {
                const key = typeof el === 'string'
                  ? (el.charAt(0).toUpperCase() + el.slice(1).toLowerCase()) as ElementType
                  : el;
                const ec = ELEMENT_COLORS[key] ?? {
                  bg: 'bg-slate-500/10',
                  text: 'text-slate-300',
                  border: 'border-slate-500/30',
                };
                return (
                  <span
                    key={String(el)}
                    className={`${ec.bg} ${ec.text} ${ec.border} border rounded-full px-2 py-0.5 text-[10px]`}
                  >
                    {String(el)}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};
