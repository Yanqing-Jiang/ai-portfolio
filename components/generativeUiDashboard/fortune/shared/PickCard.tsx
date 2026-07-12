/**
 * Secondary pick card — Observatory mock A `.pick.minor` quiet variant.
 */
import React from 'react';
import { motion } from 'framer-motion';
import type { OccasionPick } from '../../lib/fortuneTypes';
import { OBS_QUIET_CARD, OBSERVATORY_SERIF } from '../designTokens';
import { staggerItem, pickVariants } from '../animations';

interface PickCardProps {
  pick: OccasionPick;
  rank: number;
  accentColor?: string;
  onSelect?: () => void;
  isReplay?: boolean;
}

export const PickCard: React.FC<PickCardProps> = ({
  pick,
  rank: _rank,
  accentColor: _accentColor = '#f59e0b',
  onSelect,
  isReplay = false,
}) => {
  const dateObj = new Date(`${pick.date}T12:00:00`);
  const formattedDate = Number.isFinite(dateObj.getTime())
    ? dateObj.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
    : 'Date pending';
  const pillar = `${pick.dayPillar?.stem || '—'}${pick.dayPillar?.branch ? pick.dayPillar.branch : ''}`;

  return (
    <motion.button
      type="button"
      variants={pickVariants(isReplay, staggerItem)}
      onClick={onSelect}
      className={`w-full text-left ${OBS_QUIET_CARD} transition-transform hover:scale-[1.01]`}
    >
      <div
        className="min-w-[56px] flex-none text-center text-[26px] font-bold leading-none text-[#c9cdd4]"
        style={{ fontFamily: OBSERVATORY_SERIF }}
      >
        {pick.score}
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="text-[14px] font-semibold text-[#e8e6e1]">
          {formattedDate}
          <span className="text-[#8a8f98]"> · {pillar}</span>
        </h3>
        <p className="mt-1 text-[12px] leading-relaxed text-[#9aa0a8]">{pick.oneLineReason}</p>
        {pick.bestHours && pick.bestHours.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {pick.bestHours.map((h) => (
              <span
                key={h}
                className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-slate-400"
              >
                {h}
              </span>
            ))}
          </div>
        )}
      </div>
    </motion.button>
  );
};
