import React from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { PickCard, StreamingText, GuardrailBanner } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { OccasionPick } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS['lucky-day'];

export const TopPicksTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  const topPicks = (dataModel?.occasion?.topPicks || []) as OccasionPick[];
  const narrative = dataModel?.narrative;
  const guardrail = dataModel?.guardrail;

  return (
    <motion.div
      key="top-picks"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-5"
    >
      {/* Narrative TLDR */}
      {narrative?.tldr && (
        <StreamingText
          text={narrative.streamingText || narrative.tldr}
          isStreaming={!narrative.isComplete}
          isReplay={isReplay}
          cursorColor={ACCENT.primary}
          className="px-1"
        />
      )}

      {/* Top picks */}
      {topPicks.length > 0 ? (
        <motion.div
          variants={pickVariants(isReplay, staggerContainer(0.1))}
          initial="hidden"
          animate="visible"
          className="space-y-3"
        >
          {topPicks.map((pick) => (
            <PickCard
              key={pick.rank}
              pick={pick}
              rank={pick.rank}
              accentColor={ACCENT.primary}
              isReplay={isReplay}
            />
          ))}
        </motion.div>
      ) : (
        <div className="text-center py-8 text-xs text-slate-500">
          Searching for auspicious dates...
        </div>
      )}

      {guardrail && <GuardrailBanner guardrail={guardrail} />}
    </motion.div>
  );
};
