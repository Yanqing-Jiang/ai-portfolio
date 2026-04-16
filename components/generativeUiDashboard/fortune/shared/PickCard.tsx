import React from 'react';
import { motion } from 'framer-motion';
import { Trophy } from 'lucide-react';
import type { OccasionPick } from '../../lib/fortuneTypes';
import { GLASS, scoreColor } from '../designTokens';
import { staggerItem, pickVariants } from '../animations';

interface PickCardProps {
  pick: OccasionPick;
  rank: number;
  accentColor?: string;
  onSelect?: () => void;
  isReplay?: boolean;
}

const MEDAL_STYLES = {
  1: 'from-amber-500/15 border-2 border-amber-500/40 shadow-[0_0_20px_rgba(245,158,11,0.15)]',
  2: 'from-slate-400/10 border border-slate-400/30',
  3: 'from-amber-700/10 border border-amber-700/20',
} as const;

const MEDAL_COLORS = { 1: '#f59e0b', 2: '#94a3b8', 3: '#b45309' } as const;

export const PickCard: React.FC<PickCardProps> = ({
  pick,
  rank,
  accentColor: _accentColor = '#f59e0b',
  onSelect,
  isReplay = false,
}) => {
  const medalClass = MEDAL_STYLES[rank as 1 | 2 | 3] || 'border border-white/10';
  const medalColor = MEDAL_COLORS[rank as 1 | 2 | 3] || '#64748b';

  return (
    <motion.button
      type="button"
      variants={pickVariants(isReplay, staggerItem)}
      onClick={onSelect}
      className={`w-full text-left rounded-2xl bg-gradient-to-b ${medalClass} ${GLASS} p-4 transition-transform hover:scale-[1.02]`}
    >
      <div className="flex items-start gap-3">
        {/* Medal */}
        <div className="flex h-10 w-10 flex-none items-center justify-center rounded-xl" style={{ background: `${medalColor}1A` }}>
          <Trophy className="w-5 h-5" style={{ color: medalColor }} />
        </div>

        <div className="min-w-0 flex-1">
          {/* Date */}
          <div className="text-sm font-semibold text-white">
            {new Date(pick.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
          </div>

          {/* Pillar */}
          <div className="text-[10px] text-slate-400 mt-0.5">
            {pick.dayPillar.stem} {pick.dayPillar.branch}
          </div>

          {/* Reason */}
          <p className="mt-1.5 text-xs leading-relaxed text-slate-300">{pick.oneLineReason}</p>

          {/* Best hours */}
          {pick.bestHours && pick.bestHours.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {pick.bestHours.map((h) => (
                <span key={h} className="text-[10px] bg-white/5 border border-white/10 rounded-full px-2 py-0.5 text-slate-400">
                  {h}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Score */}
        <div className={`text-lg font-bold ${scoreColor(pick.score)}`}>
          {pick.score}
        </div>
      </div>
    </motion.button>
  );
};
