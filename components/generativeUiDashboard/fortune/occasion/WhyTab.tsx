/**
 * Tab 3: Reasoning & Mechanisms
 * Visualizing the "Key vs Avoid" elements and filtered mechanisms.
 */
import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { Zap, ShieldAlert } from 'lucide-react';
import { useFortuneStore } from '../../stores/fortuneStore';
import { StreamingText } from '../shared/StreamingText';
import { MechanismCard } from '../shared/MechanismCard';
import { FLOW_ACCENTS, ELEMENT_COLORS, GLASS } from '../designTokens';
import { fadeInUp, staggerContainer, pickVariants } from '../animations';
import type { Mechanism, Citation, ElementType } from '../../lib/fortuneTypes';

export const WhyTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [filter, setFilter] = useState<string>('All');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { dataModel } = useFortuneStore(useShallow((s) => ({
    dataModel: s.dataModel,
  })));

  const analysis = dataModel?.occasion?.analysis;
  const mechanisms = (dataModel?.occasion?.mechanisms || []) as Mechanism[];
  const citations = (dataModel?.classics?.references || []) as Citation[];
  const accent = FLOW_ACCENTS['lucky-day'];

  // Mechanism filtering logic
  const filteredMechs = useMemo(() => {
    if (filter === 'All') return mechanisms;
    return mechanisms.filter((m) => m.type === filter);
  }, [mechanisms, filter]);

  const filterOptions = useMemo(() => {
    const types = new Set<string>();
    mechanisms.forEach((m) => {
      if (m.type) types.add(m.type);
    });
    return ['All', ...Array.from(types)];
  }, [mechanisms]);

  return (
    <div className="flex flex-col gap-6 pb-24">
      {/* 1. Key vs Avoid Elements */}
      <motion.div
        variants={pickVariants(isReplay, fadeInUp)}
        initial="hidden"
        animate="visible"
        className="grid grid-cols-2 gap-3"
      >
        <div className={`${GLASS} p-4 border-green-500/20 flex flex-col gap-2`}>
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-green-400 uppercase">
            <Zap size={12} /> Key Boosters
          </div>
          <div className="flex flex-wrap gap-1.5">
            {analysis?.keyElements?.map((el: ElementType) => (
              <span
                key={el}
                className="px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-medium"
                style={{ color: ELEMENT_COLORS[el]?.hex }}
              >
                {el}
              </span>
            ))}
          </div>
        </div>
        <div className={`${GLASS} p-4 border-red-500/20 flex flex-col gap-2`}>
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-red-400 uppercase">
            <ShieldAlert size={12} /> Elements to Avoid
          </div>
          <div className="flex flex-wrap gap-1.5">
            {analysis?.avoidElements?.map((el: ElementType) => (
              <span
                key={el}
                className="px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-medium line-through decoration-red-500/50"
                style={{ color: `${ELEMENT_COLORS[el]?.hex}80` }}
              >
                {el}
              </span>
            ))}
          </div>
        </div>
      </motion.div>

      {/* 2. Agent Narrative */}
      {analysis?.description && (
        <div className={`${GLASS} p-5 bg-amber-500/[0.02]`}>
          <StreamingText
            text={analysis.description}
            isStreaming={!dataModel?.narrative?.isComplete}
            isReplay={isReplay}
            cursorColor={accent.primary}
          />
        </div>
      )}

      {/* 3. Mechanisms with Filter */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[11px] font-bold text-white/30 uppercase tracking-widest shrink-0">
            Detailed Mechanisms
          </span>
          <div className="flex gap-2 overflow-x-auto scrollbar-hide">
            {filterOptions.map((opt) => (
              <button
                type="button"
                key={opt}
                onClick={() => setFilter(opt)}
                className={`shrink-0 px-3 py-1 rounded-full text-[10px] font-medium transition-colors border ${
                  filter === opt
                    ? 'bg-amber-500 text-slate-950 border-amber-500'
                    : 'bg-white/5 text-white/40 border-white/10'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>

        <motion.div
          variants={pickVariants(isReplay, staggerContainer(0.08))}
          initial="hidden"
          animate="visible"
          className="flex flex-col gap-3"
        >
          <AnimatePresence mode="popLayout">
            {filteredMechs.map((mech, idx) => {
              const id = mech.id || String(idx);
              return (
                <MechanismCard
                  key={id}
                  mechanism={mech}
                  citations={citations}
                  accentColor={accent.primary}
                  isExpanded={expandedId === id}
                  onToggle={() => setExpandedId(expandedId === id ? null : id)}
                  isReplay={isReplay}
                />
              );
            })}
          </AnimatePresence>
        </motion.div>
      </div>

      {/* 4. Classics Reference Footer */}
      <div className="mt-4 pt-6 border-t border-white/10 text-center">
        <span className="text-[10px] text-white/20 font-serif uppercase tracking-[0.2em]">
          Derived from Classical Sources
        </span>
      </div>
    </div>
  );
};
