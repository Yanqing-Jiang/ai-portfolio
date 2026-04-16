import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';
import type { AnnualPillar } from '../../lib/fortuneTypes';
import { ELEMENT_COLORS, scoreColor } from '../designTokens';
import { staggerItem, slideDown, pickVariants } from '../animations';

interface YearCardProps {
  item: AnnualPillar;
  isExpanded?: boolean;
  onToggle?: () => void;
  isReplay?: boolean;
}

export const YearCard: React.FC<YearCardProps> = ({
  item,
  isExpanded = false,
  onToggle,
  isReplay = false,
}) => {
  const element = item.element || 'Wood';
  const ec = ELEMENT_COLORS[element];
  const score = item.score ?? 50;

  return (
    <motion.div
      variants={pickVariants(isReplay, staggerItem)}
      className={`rounded-xl border border-white/5 bg-white/[0.03] overflow-hidden ${
        item.isCurrent ? 'ring-1 ring-indigo-500/40 bg-indigo-500/[0.04]' : ''
      }`}
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-3 text-left"
      >
        <div className="text-sm font-bold text-white min-w-[40px]">{item.year}</div>
        <div className={`text-[10px] ${ec.text} ${ec.bg} ${ec.border} border rounded-full px-2 py-0.5`}>
          {element}
        </div>
        <div className={`text-xs font-semibold ml-auto ${scoreColor(score)}`}>
          {Math.round(score)}
        </div>
        <ChevronDown
          className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
        />
      </button>

      <AnimatePresence>
        {isExpanded && item.prediction && (
          <motion.div
            variants={slideDown}
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="overflow-hidden"
          >
            <div className="px-3 pb-3">
              <p className="text-xs leading-relaxed text-slate-400">{item.prediction}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
