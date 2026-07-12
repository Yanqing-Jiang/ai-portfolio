/**
 * Tab 1: Top Picks
 * Displays the Hero card and supporting picks with progressive reveal logic.
 */
import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { staggerContainer, pickVariants } from '../animations';
import { HeroPickCard } from '../shared/HeroPickCard';
import { ExpandablePickCard } from './ExpandablePickCard';
import { AgentPhaseStrip } from '../shared/AgentPhaseStrip';
import type { OccasionPick, Citation } from '../../lib/fortuneTypes';

export const TopPicksTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const { dataModel } = useFortuneStore(useShallow((s) => ({
    dataModel: s.dataModel,
  })));

  const picks = (dataModel?.occasion?.topPicks || []) as OccasionPick[];
  const isComplete = dataModel?.narrative?.isComplete ?? false;
  const citations = (dataModel?.classics?.references || []) as Citation[];

  // Identify if rank #1 is currently being computed via trace
  const isHeroComputing = useMemo(() => {
    if (isComplete) return false;
    const steps = dataModel?.trace?.steps;
    if (!steps) return false;
    const stepsArr = Array.isArray(steps) ? steps : Object.values(steps);
    const currentStep = stepsArr.find((s: unknown) => {
      if (!s || typeof s !== 'object') return false;
      const rec = s as Record<string, unknown>;
      return rec.status === 'running';
    }) as Record<string, unknown> | undefined;
    return currentStep?.tool === 'compute_day_score' && picks.length === 0;
  }, [dataModel?.trace?.steps, picks.length, isComplete]);

  return (
    <div className="flex flex-col gap-6 pb-24">
      <AgentPhaseStrip
        progress={dataModel?.meta?.progress}
        isComplete={isComplete}
      />

      <motion.div
        variants={pickVariants(isReplay, staggerContainer(0.1))}
        initial="hidden"
        animate="visible"
        className="flex flex-col gap-4"
      >
        <AnimatePresence mode="popLayout">
          {picks.length > 0 ? (
            <motion.div key="picks-content" className="flex flex-col gap-4">
              {/* Rank 1 Hero */}
              <HeroPickCard
                pick={picks[0]}
                isComputing={isHeroComputing}
                isReplay={isReplay}
              />

              {/* Ranks 2+ — quiet cards, 2-col on sm+ */}
              <div key="supporting" className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                {picks.slice(1, 5).map((pick, idx) => (
                  <ExpandablePickCard
                    key={`${pick.date || 'pick'}-${pick.rank ?? idx + 2}-${idx}`}
                    pick={pick}
                    rank={idx + 2}
                    citations={citations}
                    isReplay={isReplay}
                  />
                ))}
              </div>
            </motion.div>
          ) : (
            /* Skeleton State */
            <div key="skeleton" className="flex flex-col gap-4">
              <div className="h-64 rounded-3xl bg-white/5 animate-pulse border border-white/10" />
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-20 rounded-2xl bg-white/5 animate-pulse border border-white/10" />
              ))}
            </div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
};
