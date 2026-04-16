import React from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { ResultHero, StreamingText, DayMasterCard, SeasonalStrengthBar, MechanismCard, GuardrailBanner } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { ElementType, Mechanism, Citation, SeasonalStrength as SSType } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS['luck-cycle'];

export const NowTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  const luckCycle = dataModel?.luckCycle;
  const kpi = dataModel?.kpi as Record<string, unknown> | undefined;
  const narrative = dataModel?.narrative;
  const seasonal = dataModel?.seasonalStrength as SSType | undefined;
  const guardrail = dataModel?.guardrail;
  const mechanisms = (luckCycle?.mechanisms || []).slice(0, 3) as Mechanism[];
  const citations = (dataModel?.classics?.references || []) as Citation[];

  const score = luckCycle?.currentWindow?.score ?? (kpi?.harmonyScore as number | undefined);
  const dayMaster = (kpi?.dayMaster || '') as string;
  const dayMasterElement = (kpi?.dayMasterElement || 'Wood') as ElementType;

  return (
    <motion.div
      key="now"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-5"
    >
      <ResultHero
        title={luckCycle?.currentWindow?.summary || 'Current cycle reading...'}
        subtitle={luckCycle?.currentWindow?.decade}
        score={score}
        scoreLabel="Current"
        accentColor={ACCENT.primary}
        loading={!luckCycle?.currentWindow}
        isReplay={isReplay}
      />

      {narrative?.tldr && (
        <StreamingText
          text={narrative.streamingText || narrative.tldr}
          isStreaming={!narrative.isComplete}
          isReplay={isReplay}
          cursorColor={ACCENT.primary}
          className="px-1"
        />
      )}

      {dayMaster && (
        <DayMasterCard
          stem={dayMaster}
          element={dayMasterElement}
          strength={seasonal?.strength || 'moderate'}
          accentColor={ACCENT.primary}
          isReplay={isReplay}
        />
      )}

      {seasonal && (
        <SeasonalStrengthBar
          strength={seasonal.strength}
          score={seasonal.score}
          season={seasonal.season}
          accentColor={ACCENT.primary}
          isReplay={isReplay}
        />
      )}

      {mechanisms.length > 0 && (
        <motion.div
          variants={pickVariants(isReplay, staggerContainer(0.1))}
          initial="hidden"
          animate="visible"
          className="space-y-2"
        >
          {mechanisms.map((m, i) => (
            <MechanismCard
              key={m.id || i}
              mechanism={m}
              citations={citations}
              accentColor={ACCENT.primary}
              isExpanded
              isReplay={isReplay}
            />
          ))}
        </motion.div>
      )}

      {guardrail && <GuardrailBanner guardrail={guardrail} />}
    </motion.div>
  );
};
