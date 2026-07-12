/**
 * Shared hero verdict card — Observatory accent wash + large serif score.
 */
import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import { fadeInUp, pickVariants } from '../animations';
import { OBSERVATORY_SERIF, OBSERVATORY_MONO, observatoryAccent } from '../designTokens';

interface ResultHeroProps {
  title: string;
  subtitle?: string;
  score?: number;
  scoreLabel?: string;
  accentColor?: string;
  loading?: boolean;
  isReplay?: boolean;
  /** When true, render quiet (secondary) surface instead of accent hero. */
  quiet?: boolean;
}

export const ResultHero: React.FC<ResultHeroProps> = ({
  title,
  subtitle,
  score,
  scoreLabel,
  accentColor = '#14b8a6',
  loading = false,
  isReplay = false,
  quiet = false,
}) => {
  const reduceMotion = useReducedMotion();
  const obs = observatoryAccent(accentColor);

  return (
    <motion.div
      variants={pickVariants(isReplay, fadeInUp)}
      initial="hidden"
      animate="visible"
      className="relative flex items-center gap-5 overflow-hidden rounded-2xl border p-[22px]"
      style={
        quiet
          ? {
              borderColor: 'rgba(255,255,255,0.08)',
              background: 'rgba(255,255,255,0.02)',
            }
          : {
              borderColor: obs.heroBorder,
              background: obs.heroWash,
            }
      }
    >
      {loading ? (
        <div className="flex w-full flex-col items-center gap-3 py-4">
          <Loader2 className="h-8 w-8 animate-spin" style={{ color: accentColor }} />
          <div className="text-xs text-slate-400">Reading the pillars...</div>
        </div>
      ) : (
        <>
          {score !== undefined && (
            <div
              className={`flex-none text-center ${quiet ? 'min-w-[56px]' : 'min-w-[76px]'}`}
              style={{
                fontFamily: OBSERVATORY_SERIF,
                color: quiet ? '#c9cdd4' : obs.score,
              }}
            >
              <div className={`font-bold leading-none ${quiet ? 'text-[26px]' : 'text-[40px]'}`}>
                {Math.round(score)}
              </div>
              {scoreLabel && (
                <small
                  className="mt-1 block text-[8px] font-semibold uppercase tracking-[0.25em] text-[#8a8f98]"
                  style={{ fontFamily: OBSERVATORY_MONO }}
                >
                  {scoreLabel}
                </small>
              )}
            </div>
          )}
          <div className="min-w-0 flex-1 text-left">
            <h2
              className="text-[16px] font-semibold leading-snug text-[#f4e9c8]"
              style={{ fontFamily: OBSERVATORY_SERIF }}
            >
              {title}
            </h2>
            {subtitle && (
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-[#9aa0a8]">{subtitle}</p>
            )}
          </div>
        </>
      )}

      {!quiet && !loading && !reduceMotion && score !== undefined && (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute -right-8 -top-10 h-32 w-32 rounded-full opacity-30 blur-3xl"
          style={{ background: accentColor }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.25 }}
          transition={{ duration: 0.8 }}
        />
      )}
    </motion.div>
  );
};
