import React, { useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import type { LuckPillar } from '../../lib/fortuneTypes';
import { ELEMENT_COLORS } from '../designTokens';
import { barGrow, staggerContainer, pickVariants } from '../animations';

interface TimelineBarProps {
  decades: LuckPillar[];
  currentDecadeIndex?: number;
  accentColor?: string;
  showChinese?: boolean;
  onDecadeSelect?: (index: number) => void;
  isReplay?: boolean;
}

export const TimelineBar: React.FC<TimelineBarProps> = ({
  decades,
  currentDecadeIndex = -1,
  accentColor = '#6366f1',
  showChinese = false,
  onDecadeSelect,
  isReplay = false,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const maxScore = Math.max(...decades.map((d) => d.score ?? 50), 1);

  // Auto-scroll to current decade on mount
  useEffect(() => {
    if (currentDecadeIndex >= 0 && scrollRef.current) {
      const child = scrollRef.current.children[currentDecadeIndex] as HTMLElement;
      child?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    }
  }, [currentDecadeIndex]);

  return (
    <motion.div
      ref={scrollRef}
      variants={pickVariants(isReplay, staggerContainer(0.08))}
      initial="hidden"
      animate="visible"
      className="flex overflow-x-auto snap-x snap-mandatory gap-2 pb-2 scrollbar-hide"
    >
      {decades.map((d, i) => {
        const isCurrent = i === currentDecadeIndex;
        const isPast = i < currentDecadeIndex;
        const barHeight = ((d.score ?? 50) / maxScore) * 60 + 20; // min 20px
        const element = d.element || 'Wood';
        const ec = ELEMENT_COLORS[element];

        return (
          <motion.button
            key={i}
            type="button"
            variants={pickVariants(isReplay, barGrow)}
            onClick={() => onDecadeSelect?.(i)}
            className={`snap-center flex flex-col items-center gap-1.5 rounded-xl border px-3 py-2 min-w-[60px] transition-all ${
              isCurrent
                ? 'scale-105 border-indigo-500/60 bg-indigo-500/10 shadow-[0_0_30px_rgba(99,102,241,0.15)]'
                : isPast
                ? 'opacity-40 bg-slate-800/30 border-white/5'
                : 'opacity-60 bg-slate-800/30 border-white/5'
            }`}
            style={{ transformOrigin: 'bottom' }}
          >
            {/* Bar */}
            <div className="w-3 rounded-full" style={{
              height: barHeight,
              background: isCurrent ? accentColor : ec.hex,
              opacity: isCurrent ? 1 : 0.5,
            }} />
            {/* Stem-Branch label */}
            <div className="text-[10px] text-slate-300">
              {showChinese && d.stemChinese ? `${d.stemChinese}${d.branchChinese}` : `${d.stem}${d.branch}`}
            </div>
            {/* Age range */}
            <div className="text-[9px] text-slate-500">
              {d.startAge}-{d.endAge}
            </div>
          </motion.button>
        );
      })}
    </motion.div>
  );
};
