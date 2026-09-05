import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import type { OccasionDay, Mechanism, Citation } from '../../lib/fortuneTypes';
import { GLASS, scoreBg, scoreColor } from '../designTokens';
import { MechanismCard } from './MechanismCard';
import { formatDateOnly } from './dateOnly';

interface DayDetailSheetProps {
  day: OccasionDay | null;
  mechanisms?: Mechanism[];
  citations?: Citation[];
  accentColor?: string;
  onClose: () => void;
}

export const DayDetailSheet: React.FC<DayDetailSheetProps> = ({
  day,
  mechanisms = [],
  citations = [],
  accentColor = '#f59e0b',
  onClose,
}) => {
  return (
    <AnimatePresence>
      {day && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/60"
            onClick={onClose}
          />
          {/* Sheet */}
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', bounce: 0.15, duration: 0.5 }}
            className={`fixed bottom-0 left-0 right-0 z-50 max-h-[70vh] overflow-y-auto rounded-t-2xl ${GLASS} p-5`}
            style={{ background: 'rgba(15,23,42,0.95)', backdropFilter: 'blur(20px)' }}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-sm font-semibold text-white">
                  {formatDateOnly(day.date, { weekday: 'long', month: 'short', day: 'numeric' })}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  {day.pillar && (
                    <span className="text-xs text-slate-400">
                      {day.pillar.stem}{day.pillar.branch}
                    </span>
                  )}
                  {day.officer && (
                    <span className="text-[10px] text-slate-500 bg-white/5 rounded-full px-2 py-0.5">
                      {day.officer}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className={`text-lg font-bold ${scoreColor(day.score)}`}>
                  {day.score}
                </div>
                <button
                  type="button"
                  aria-label="Close day details"
                  onClick={onClose}
                  className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Score bar */}
            <div className={`h-1.5 rounded-full mb-4 ${scoreBg(day.score)}`} />

            {/* Clash warning */}
            {day.isClash && (
              <div className="mb-4 rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-400">
                This day has a branch clash with your chart — proceed with extra caution.
              </div>
            )}

            {/* Mechanisms */}
            {mechanisms.length > 0 && (
              <div className="space-y-2">
                {mechanisms.map((m, i) => (
                  <MechanismCard
                    key={m.id || i}
                    mechanism={m}
                    citations={citations}
                    accentColor={accentColor}
                    isExpanded
                    isReplay
                  />
                ))}
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
