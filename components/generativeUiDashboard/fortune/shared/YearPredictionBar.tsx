import React from 'react';
import { motion } from 'framer-motion';
import type { Retrodiction } from '../../lib/fortuneTypes';
import { staggerItem, pickVariants } from '../animations';
import { supportBand } from './outlook';

interface YearPredictionBarProps {
  item: Retrodiction;
  accentColor?: string;
  isReplay?: boolean;
}

export const YearPredictionBar: React.FC<YearPredictionBarProps> = ({
  item,
  accentColor = '#14b8a6',
  isReplay = false,
}) => {
  const band = supportBand(item.confidence);
  const pct = band.percent;

  return (
    <motion.div
      variants={pickVariants(isReplay, staggerItem)}
      className="rounded-xl border border-white/5 bg-white/[0.03] p-3"
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-semibold text-slate-200">{item.year}</span>
        <span className="text-[10px] uppercase tracking-wide text-slate-500">
          {band.label}
        </span>
      </div>
      <p className="text-[11px] leading-relaxed text-slate-400 mb-2">{item.prediction}</p>
      <div className="h-1 rounded-full bg-slate-700/50 overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: accentColor }}
          initial={isReplay ? { width: `${pct}%` } : { width: '0%' }}
          animate={{ width: `${pct}%` }}
          transition={isReplay ? { duration: 0 } : { duration: 0.8, ease: [0.25, 0.46, 0.45, 0.94] }}
        />
      </div>
      {item.correction && (
        <div className="mt-2 text-[10px] text-amber-500/80 italic">
          Corrected: {item.correction.user_note}
        </div>
      )}
    </motion.div>
  );
};
