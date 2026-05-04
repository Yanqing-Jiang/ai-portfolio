import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { PillarRow, ElementRadar, ConnectionLines, ChineseToggle } from '../shared';
import { FLOW_ACCENTS, GLASS } from '../designTokens';
import { tabContentVariants } from '../animations';
import type { PairInteraction } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS.compatibility;

export const PillarsTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [showChinese, setShowChinese] = useState(false);

  const { dataModel, status } = useFortuneStore(useShallow((s) => ({
    dataModel: s.dataModel,
    status: s.status
  })));

  const compat = dataModel?.compatibility;
  const personA = compat?.personA;
  const personB = compat?.personB;
  const allInteractions = (compat?.pairInteractions || []) as PairInteraction[];

  // Trace step logic for animation
  const steps = (dataModel?.trace?.steps as any)?.items || [];
  const visibleInteractionsCount = useMemo(() => {
    if (status === 'complete' || isReplay) return allInteractions.length;
    // Reveal 1 interaction for every 2 steps after step 5
    return Math.min(allInteractions.length, Math.max(0, Math.floor((steps.length - 5) / 2)));
  }, [steps.length, allInteractions.length, status, isReplay]);

  const activeInteractions = allInteractions.slice(0, visibleInteractionsCount);

  return (
    <motion.div
      key="pillars"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6 pb-12"
    >
      <div className="flex justify-between items-center px-1">
        <div className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">
          {activeInteractions.length} / {allInteractions.length} Connections
        </div>
        <ChineseToggle showChinese={showChinese} onToggle={() => setShowChinese(!showChinese)} />
      </div>

      {/* Person A Chart */}
      {personA?.pillars && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-[11px] font-bold uppercase tracking-[0.2em] text-rose-400">
              {personA?.name || 'Person A'}
            </h3>
            <span className="text-[9px] text-slate-500 font-mono">Chart A</span>
          </div>
          <PillarRow
            pillars={personA.pillars}
            showChinese={showChinese}
            accentColor={ACCENT.primary}
            isReplay={isReplay}
          />
        </div>
      )}

      {/* Dynamic Connection lines */}
      <div className="relative py-4">
        <div className="absolute inset-0 flex items-center justify-center opacity-20 pointer-events-none">
          <div className="w-full h-px bg-gradient-to-r from-transparent via-rose-500 to-transparent" />
        </div>
        <div className="flex justify-center overflow-visible">
          <ConnectionLines
            interactions={activeInteractions}
            width={340}
            height={140}
          />
        </div>
      </div>

      {/* Person B Chart */}
      {personB?.pillars && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">
              {personB?.name || 'Person B'}
            </h3>
            <span className="text-[9px] text-slate-500 font-mono">Chart B</span>
          </div>
          <PillarRow
            pillars={personB.pillars}
            showChinese={showChinese}
            accentColor="#94a3b8"
            isReplay={isReplay}
          />
        </div>
      )}

      {/* Element Synergy Radar */}
      {personA?.elements && personB?.elements && (
        <div className={`${GLASS} p-6 flex flex-col items-center`}>
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-6">
            Element Overlay Synergy
          </div>
          <div className="relative">
            {/* Custom gradient background for radar overlap */}
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-rose-500/5 to-slate-500/5 blur-xl" />
            <ElementRadar
              scores={personA.elements}
              accentColor={ACCENT.primary}
              secondaryScores={personB.elements}
              secondaryColor="#94a3b8"
              isReplay={isReplay}
            />
          </div>
          <div className="mt-6 grid grid-cols-2 gap-8 w-full">
            <div className="flex items-center gap-2 justify-center">
              <div className="w-2 h-2 rounded-full bg-rose-500" />
              <span className="text-[10px] text-slate-300 font-medium">A: {personA?.dayMasterElement}</span>
            </div>
            <div className="flex items-center gap-2 justify-center">
              <div className="w-2 h-2 rounded-full bg-slate-400" />
              <span className="text-[10px] text-slate-300 font-medium">B: {personB?.dayMasterElement}</span>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
};
