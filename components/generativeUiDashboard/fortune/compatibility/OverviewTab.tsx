import React from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { DualRingGauge, StreamingText, DynamicCard, GuardrailBanner } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';

const ACCENT = FLOW_ACCENTS.compatibility;

export const OverviewTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  const compat = dataModel?.compatibility;
  const narrative = dataModel?.narrative;
  const guardrail = dataModel?.guardrail;
  const overview = compat?.overview;

  return (
    <motion.div
      key="overview"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-5"
    >
      {/* Score gauge */}
      {overview && (
        <div className="flex justify-center">
          <DualRingGauge
            score={overview.score}
            personAName={compat?.personA?.name || 'Person A'}
            personBName={compat?.personB?.name || 'Person B'}
            accentColor={ACCENT.primary}
            isReplay={isReplay}
          />
        </div>
      )}

      {/* Summary */}
      {overview?.summary && (
        <StreamingText
          text={narrative?.streamingText || overview.summary}
          isStreaming={narrative ? !narrative.isComplete : false}
          isReplay={isReplay}
          cursorColor={ACCENT.primary}
          className="px-1"
        />
      )}

      {/* Strengths */}
      {overview?.strengths && overview.strengths.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-green-400">
            Strengths
          </h3>
          <motion.div
            variants={pickVariants(isReplay, staggerContainer(0.08))}
            initial="hidden"
            animate="visible"
            className="space-y-2"
          >
            {overview.strengths.map((s, i) => (
              <DynamicCard key={i} title={s} description="" accentColor="#4ade80" isReplay={isReplay} />
            ))}
          </motion.div>
        </div>
      )}

      {/* Frictions */}
      {overview?.frictions && overview.frictions.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-red-400">
            Frictions
          </h3>
          <motion.div
            variants={pickVariants(isReplay, staggerContainer(0.08))}
            initial="hidden"
            animate="visible"
            className="space-y-2"
          >
            {overview.frictions.map((f, i) => (
              <DynamicCard key={i} title={f} description="" accentColor="#f87171" isReplay={isReplay} />
            ))}
          </motion.div>
        </div>
      )}

      {guardrail && <GuardrailBanner guardrail={guardrail} />}
    </motion.div>
  );
};
