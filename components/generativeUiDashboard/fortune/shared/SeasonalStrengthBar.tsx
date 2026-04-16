import React from 'react';
import { motion } from 'framer-motion';
import { GLASS } from '../designTokens';
import { fadeInUp, pickVariants } from '../animations';

interface SeasonalStrengthBarProps {
  strength: 'strong' | 'moderate' | 'weak';
  score: number;
  season?: string;
  accentColor?: string;
  isReplay?: boolean;
}

const STRENGTH_MAP = {
  strong: { width: '85%', color: '#4ade80', label: 'Strong' },
  moderate: { width: '55%', color: '#eab308', label: 'Moderate' },
  weak: { width: '25%', color: '#f87171', label: 'Weak' },
} as const;

export const SeasonalStrengthBar: React.FC<SeasonalStrengthBarProps> = ({
  strength,
  score,
  season,
  accentColor,
  isReplay = false,
}) => {
  const s = STRENGTH_MAP[strength] || STRENGTH_MAP.moderate;
  const barColor = accentColor || s.color;

  return (
    <motion.div
      variants={pickVariants(isReplay, fadeInUp)}
      className={`${GLASS} p-3`}
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-slate-400">
          Seasonal Strength{season ? ` · ${season}` : ''}
        </span>
        <span className="text-xs font-semibold" style={{ color: s.color }}>
          {s.label} ({Math.round(score)})
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-700/50 overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: barColor }}
          initial={isReplay ? { width: s.width } : { width: '0%' }}
          animate={{ width: s.width }}
          transition={isReplay ? { duration: 0 } : { duration: 1, ease: [0.25, 0.46, 0.45, 0.94] }}
        />
      </div>
    </motion.div>
  );
};
