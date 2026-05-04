import React, { useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import type { LuckPillar } from '../../lib/fortuneTypes';
import { ELEMENT_COLORS } from '../designTokens';
import { staggerContainer, pickVariants } from '../animations';

interface LuckFilmStripProps {
  decades: LuckPillar[];
  currentDecadeIndex?: number;
  selectedIndex?: number;
  onDecadeSelect?: (index: number) => void;
  showChinese?: boolean;
  compact?: boolean;
  isReplay?: boolean;
  isStreaming?: boolean;
}

export const LuckFilmStrip: React.FC<LuckFilmStripProps> = ({
  decades,
  currentDecadeIndex = -1,
  selectedIndex,
  onDecadeSelect,
  showChinese = false,
  compact = false,
  isReplay = false,
  isStreaming = false,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeIdx = selectedIndex !== undefined ? selectedIndex : currentDecadeIndex;

  useEffect(() => {
    if (activeIdx >= 0 && scrollRef.current) {
      const child = scrollRef.current.children[activeIdx] as HTMLElement | undefined;
      child?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    }
  }, [activeIdx]);

  return (
    <div className="relative group">
      {/* Visual Film Strip Track */}
      <div className="absolute inset-x-0 top-0 bottom-0 pointer-events-none border-y border-white/5 opacity-20" />

      <motion.div
        ref={scrollRef}
        variants={pickVariants(isReplay, staggerContainer(0.08))}
        initial="hidden"
        animate="visible"
        className="flex overflow-x-auto snap-x snap-mandatory gap-3 py-4 px-1 scrollbar-hide no-scrollbar"
      >
        {decades.map((d, i) => {
          const isActive = i === activeIdx;
          const isCurrent = i === currentDecadeIndex;
          const element = d.element || 'Wood';
          const ec = ELEMENT_COLORS[element];

          return (
            <motion.button
              key={`${d.startAge}-${i}`}
              type="button"
              variants={pickVariants(isReplay, {
                hidden: { opacity: 0, scale: 0.9, x: 20 },
                visible: { opacity: 1, scale: 1, x: 0, transition: { duration: 0.4 } },
              })}
              onClick={() => onDecadeSelect?.(i)}
              className={`snap-center relative flex flex-col items-center flex-none rounded-xl border transition-all duration-300 ${
                compact ? 'w-24 py-3' : 'w-32 py-5'
              } ${
                isActive
                  ? 'bg-indigo-600/20 border-indigo-500/60 shadow-[0_0_25px_rgba(99,102,241,0.25)] ring-1 ring-indigo-500/30'
                  : 'bg-slate-900/60 border-white/5 hover:border-white/20'
              }`}
            >
              {/* Film Perforations (Top) */}
              <div className="absolute top-1.5 inset-x-0 flex justify-around px-2">
                {[...Array(4)].map((_, idx) => (
                  <div key={idx} className="w-1.5 h-1.5 rounded-sm bg-slate-700/40" />
                ))}
              </div>

              {/* Age Range Label */}
              <div className="text-[10px] font-mono text-slate-500 mb-2">
                {d.startAge}-{d.endAge}
              </div>

              {/* Pillar Stems/Branches */}
              <div className="flex flex-col items-center gap-0.5">
                <span className={`text-xl font-bold ${ec.text} transition-transform ${isActive ? 'scale-110' : ''}`}>
                  {showChinese && d.stemChinese ? d.stemChinese : d.stem}
                </span>
                <span className={`text-lg font-bold opacity-80 ${ec.text}`}>
                  {showChinese && d.branchChinese ? d.branchChinese : d.branch}
                </span>
              </div>

              {/* Element & Status Indicator */}
              <div className="mt-3 flex flex-col items-center gap-1.5">
                <div className={`text-[9px] px-2 py-0.5 rounded-full border ${ec.bg} ${ec.border} ${ec.text} font-medium uppercase tracking-tighter`}>
                  {element}
                </div>
                {isCurrent && (
                  <div className="flex items-center gap-1">
                    <span className="w-1 h-1 rounded-full bg-indigo-400 animate-pulse" />
                    <span className="text-[8px] font-bold text-indigo-400 uppercase tracking-widest">Active</span>
                  </div>
                )}
              </div>

              {/* Film Perforations (Bottom) */}
              <div className="absolute bottom-1.5 inset-x-0 flex justify-around px-2">
                {[...Array(4)].map((_, idx) => (
                  <div key={idx} className="w-1.5 h-1.5 rounded-sm bg-slate-700/40" />
                ))}
              </div>
            </motion.button>
          );
        })}

        {/* Streaming Placeholder */}
        {isStreaming && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className={`flex-none flex flex-col items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/[0.02] ${compact ? 'w-24' : 'w-32'}`}
          >
            <div className="w-6 h-6 border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
            <span className="text-[8px] text-slate-500 uppercase mt-2 tracking-widest">Calculating</span>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
};
