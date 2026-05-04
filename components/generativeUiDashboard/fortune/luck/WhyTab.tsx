import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { MechanismCard, ChineseToggle } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { Mechanism, Citation } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS['luck-cycle'];

export const WhyTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [showChinese, setShowChinese] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { dataModel, status } = useFortuneStore(useShallow((s) => ({
    dataModel: s.dataModel,
    status: s.status,
  })));

  const mechanisms = (dataModel?.luckCycle?.mechanisms || []) as Mechanism[];
  const citations = (dataModel?.classics?.references || []) as Citation[];

  return (
    <motion.div
      key="why"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6 pb-20"
    >
      <div className="flex items-center justify-between px-1">
        <div className="max-w-[70%]">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
            Mechanism Analysis
          </h3>
          <p className="text-[11px] text-slate-500 leading-tight mt-1">
            How the agent synthesized your chart against the cycles.
          </p>
        </div>
        <ChineseToggle showChinese={showChinese} onToggle={() => setShowChinese(!showChinese)} />
      </div>

      {mechanisms.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 px-8 text-center space-y-4 rounded-3xl bg-slate-900/40 border border-white/5">
          <div className="w-10 h-10 rounded-full bg-indigo-500/10 flex items-center justify-center animate-pulse">
            <div className="w-5 h-5 rounded-full bg-indigo-500/20" />
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">
            The agent is currently tracing elemental interactions and clashing pillars...
          </p>
        </div>
      ) : (
        <motion.div
          variants={pickVariants(isReplay, staggerContainer(0.12))}
          initial="hidden"
          animate="visible"
          className="space-y-3"
        >
          {mechanisms.map((m, i) => (
            <MechanismCard
              key={m.id || i}
              mechanism={m}
              citations={citations}
              accentColor={ACCENT.primary}
              showChinese={showChinese}
              isExpanded={expandedId === (m.id || String(i))}
              onToggle={() => setExpandedId(expandedId === (m.id || String(i)) ? null : (m.id || String(i)))}
              isReplay={isReplay}
            />
          ))}
        </motion.div>
      )}

      {status === 'streaming' && mechanisms.length > 0 && (
        <div className="flex items-center gap-2 justify-center py-4">
          <span className="w-1 h-1 rounded-full bg-indigo-500 animate-bounce" />
          <span className="w-1 h-1 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.2s]" />
          <span className="w-1 h-1 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.4s]" />
          <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider ml-1">Agent is Thinking</span>
        </div>
      )}
    </motion.div>
  );
};
