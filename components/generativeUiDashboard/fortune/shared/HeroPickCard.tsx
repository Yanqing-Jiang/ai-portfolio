/**
 * Hero #1 pick card — Observatory mock A `.pick` treatment.
 */
import React, { useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Copy, Check, Calendar } from 'lucide-react';
import {
  FLOW_ACCENTS,
  OBSERVATORY_SERIF,
  OBSERVATORY_MONO,
  accentAlpha,
  observatoryAccent,
} from '../designTokens';
import { fadeInUp, pickVariants } from '../animations';
import type { OccasionPick } from '../../lib/fortuneTypes';
import { calendarDayDistance, formatDateOnly } from './dateOnly';

interface HeroPickCardProps {
  pick: OccasionPick;
  isComputing?: boolean;
  isReplay?: boolean;
}

export const HeroPickCard: React.FC<HeroPickCardProps> = ({ pick, isComputing, isReplay = false }) => {
  const [copied, setCopied] = useState(false);
  const reduceMotion = useReducedMotion();
  const accent = FLOW_ACCENTS['lucky-day'];
  const obs = observatoryAccent(accent.primary);

  const handleCopy = () => {
    const text = `Lucky Day #1: ${pick.date} (Score: ${pick.score}/100) - ${pick.oneLineReason}`;
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text).catch(() => { /* ignore */ });
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formattedDate = formatDateOnly(pick.date, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

  const daysDiff = calendarDayDistance(pick.date);

  const pillar = `${pick.dayPillar?.stem || '—'}${pick.dayPillar?.branch || ''}`;

  return (
    <motion.div
      variants={pickVariants(isReplay, fadeInUp)}
      initial="hidden"
      animate="visible"
      className="relative flex items-center gap-5 overflow-hidden rounded-2xl border p-[22px]"
      style={{
        borderColor: isComputing ? accent.primary : obs.heroBorder,
        background: obs.heroWash,
      }}
    >
      <div
        className="min-w-[76px] flex-none text-center"
        style={{ fontFamily: OBSERVATORY_SERIF, color: obs.score }}
      >
        <div className="text-[40px] font-bold leading-none">{pick.score}</div>
        <small
          className="mt-1 block text-[8px] font-semibold uppercase tracking-[0.25em] text-[#8a8f98]"
          style={{ fontFamily: OBSERVATORY_MONO }}
        >
          Score
        </small>
      </div>

      <div className="min-w-0 flex-1">
        <h3 className="text-[16px] font-semibold text-[#f4e9c8]">
          {formattedDate}
          <span className="text-[#8a8f98]"> · {pillar}</span>
        </h3>
        <p className="mt-1 text-[12.5px] leading-relaxed text-[#9aa0a8]">
          {pick.oneLineReason}
        </p>

        {pick.bestHours && pick.bestHours.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {pick.bestHours.map((hour, idx) => (
              <span
                key={idx}
                className="rounded-md border border-white/5 bg-white/[0.03] px-2 py-1 font-mono text-[10px] text-white/70"
              >
                {hour}
              </span>
            ))}
          </div>
        )}

        <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-2">
          <div className="flex items-center gap-2 text-[11px] text-white/40">
            <Calendar className="h-3.5 w-3.5" />
            <span>
              {daysDiff === null
                ? 'Timing pending'
                : daysDiff >= 0
                  ? `In ${daysDiff} days`
                  : `${Math.abs(daysDiff)} days ago`}
            </span>
          </div>

          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-full px-3 py-1.5 transition-colors"
            style={{ background: accentAlpha(accent.primary, 0.1), color: accent.light }}
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-green-400" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
            <span className="text-[11px] font-medium">{copied ? 'Copied' : 'Copy Date'}</span>
          </button>
        </div>
      </div>

      {isComputing && !reduceMotion && (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-2xl"
          style={{ boxShadow: `inset 0 0 0 1px ${accent.primary}` }}
          animate={{ opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 1.6, repeat: Infinity }}
        />
      )}
    </motion.div>
  );
};
