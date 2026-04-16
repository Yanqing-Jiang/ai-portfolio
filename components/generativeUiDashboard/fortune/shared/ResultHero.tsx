import React from 'react';
import { motion } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import { ScoreGauge } from './ScoreGauge';
import { fadeInUp, pickVariants } from '../animations';
import { GLASS } from '../designTokens';

interface ResultHeroProps {
  title: string;
  subtitle?: string;
  score?: number;
  scoreLabel?: string;
  accentColor?: string;
  loading?: boolean;
  isReplay?: boolean;
}

export const ResultHero: React.FC<ResultHeroProps> = ({
  title,
  subtitle,
  score,
  scoreLabel,
  accentColor = '#14b8a6',
  loading = false,
  isReplay = false,
}) => {
  return (
    <motion.div
      variants={pickVariants(isReplay, fadeInUp)}
      initial="hidden"
      animate="visible"
      className={`${GLASS} p-5 text-center`}
    >
      {loading ? (
        <div className="flex flex-col items-center gap-3 py-4">
          <Loader2 className="w-8 h-8 animate-spin" style={{ color: accentColor }} />
          <div className="text-xs text-slate-400">Reading the pillars...</div>
        </div>
      ) : (
        <>
          {score !== undefined && (
            <div className="flex justify-center mb-3">
              <ScoreGauge
                score={score}
                label={scoreLabel}
                accentColor={accentColor}
                isReplay={isReplay}
              />
            </div>
          )}
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          {subtitle && (
            <p className="mt-1.5 text-xs leading-relaxed text-slate-400">{subtitle}</p>
          )}
        </>
      )}
    </motion.div>
  );
};
