/**
 * The high-impact #1 pick card for the Lucky Day function.
 */
import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Copy, Check, Calendar, Clock } from 'lucide-react';
import { FLOW_ACCENTS } from '../designTokens';
import { fadeInUp, pickVariants } from '../animations';
import { ScoreGauge } from './ScoreGauge';
import type { OccasionPick } from '../../lib/fortuneTypes';

interface HeroPickCardProps {
  pick: OccasionPick;
  isComputing?: boolean;
  isReplay?: boolean;
}

export const HeroPickCard: React.FC<HeroPickCardProps> = ({ pick, isComputing, isReplay = false }) => {
  const [copied, setCopied] = useState(false);
  const accent = FLOW_ACCENTS['lucky-day'];

  const handleCopy = () => {
    const text = `Lucky Day #1: ${pick.date} (Score: ${pick.score}/100) - ${pick.oneLineReason}`;
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text).catch(() => { /* ignore */ });
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const dateObj = new Date(`${pick.date}T12:00:00`);
  const isValidDate = Number.isFinite(dateObj.getTime());
  const formattedDate = isValidDate
    ? dateObj.toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', weekday: 'short',
      })
    : 'Date pending';

  // Simple countdown logic
  const daysDiff = isValidDate
    ? Math.ceil((dateObj.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;

  return (
    <motion.div
      variants={pickVariants(isReplay, fadeInUp)}
      initial="hidden"
      animate="visible"
      className={`relative overflow-hidden rounded-3xl p-5 border-2 ${
        isComputing ? 'border-amber-500/50 animate-pulse' : 'border-amber-500/20'
      } bg-gradient-to-br from-amber-500/10 to-transparent backdrop-blur-md`}
    >
      <div className="flex flex-col gap-6">
        {/* Header: Date & Score (badge sits inline with date so it never
             collides with the score gauge in the top-right). */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col">
            <div className="mb-1 flex items-center gap-2 flex-wrap">
              <span className="text-[11px] font-bold text-amber-500 uppercase tracking-widest">
                {formattedDate}
              </span>
              <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[9px] font-bold uppercase tracking-tighter text-amber-300 border border-amber-500/30">
                Best Pick
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-serif text-white leading-none">
                {pick.dayPillar?.stem || '--'}
                <span className="text-amber-500/80">{pick.dayPillar?.branch || '--'}</span>
              </span>
              <span className="text-xs text-white/40 font-light">Day Pillar</span>
            </div>
          </div>

          <div className="w-16 h-16 flex-none">
            <ScoreGauge score={pick.score} size={64} accentColor={accent.primary} isReplay={isReplay} />
          </div>
        </div>

        {/* Reason */}
        <div className="bg-white/5 rounded-xl p-3 border border-white/10">
          <p className="text-sm text-amber-50/90 italic leading-relaxed">
            &ldquo;{pick.oneLineReason}&rdquo;
          </p>
        </div>

        {/* Actionable Chips */}
        {pick.bestHours && pick.bestHours.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {pick.bestHours.map((hour, idx) => (
              <div key={idx} className="flex items-center gap-1.5 px-2.5 py-1.5 bg-white/5 rounded-lg border border-white/5 text-[10px] text-white/70">
                <Clock className="w-3 h-3 text-amber-500/70" />
                {hour}
              </div>
            ))}
          </div>
        )}

        {/* Footer Actions */}
        <div className="flex items-center justify-between pt-2 border-t border-white/10">
          <div className="flex items-center gap-2 text-[11px] text-white/40">
            <Calendar className="w-3.5 h-3.5" />
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
            className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500/10 hover:bg-amber-500/20 rounded-full transition-colors group"
          >
            {copied ? (
              <Check className="w-3.5 h-3.5 text-green-400" />
            ) : (
              <Copy className="w-3.5 h-3.5 text-amber-500 group-active:scale-90 transition-transform" />
            )}
            <span className="text-[11px] font-medium text-amber-200">
              {copied ? 'Copied' : 'Copy Date'}
            </span>
          </button>
        </div>
      </div>
    </motion.div>
  );
};
