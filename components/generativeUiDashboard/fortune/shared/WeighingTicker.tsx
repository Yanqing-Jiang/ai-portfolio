import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface WeighingTickerProps {
  currentMechanism?: string;
  count: number;
  total: number;
  isComplete: boolean;
  accentColor: string;
  onTabChange?: (id: string) => void;
}

export const WeighingTicker: React.FC<WeighingTickerProps> = ({
  currentMechanism,
  count,
  total,
  isComplete,
  accentColor,
  onTabChange,
}) => {
  return (
    <div className="flex flex-col items-center justify-center py-2 h-10">
      <AnimatePresence mode="wait">
        {!isComplete ? (
          <motion.div
            key="weighing"
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="flex items-center gap-2"
          >
            <span className="flex h-1.5 w-1.5 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ backgroundColor: accentColor }}></span>
              <span className="relative inline-flex rounded-full h-1.5 w-1.5" style={{ backgroundColor: accentColor }}></span>
            </span>
            <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-slate-400">
              Weighing factor {count}/{total}:
            </span>
            <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-white truncate max-w-[120px]">
              {currentMechanism || '...'}
            </span>
          </motion.div>
        ) : (
          <motion.div
            key="finalized"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-2"
          >
            <span className="flex h-1.5 w-1.5 rounded-full" style={{ backgroundColor: accentColor }} />
            {onTabChange ? (
              <button
                type="button"
                onClick={() => onTabChange('Why')}
                className="text-[11px] font-medium text-slate-400 underline decoration-slate-600 underline-offset-4 hover:text-slate-200"
              >
                {count > 0
                  ? `Weighed from ${count} factor${count === 1 ? '' : 's'} · see Why`
                  : 'Weighed from the chart · see Why'}
              </button>
            ) : (
              <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-slate-400">
                Reading complete
              </span>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
