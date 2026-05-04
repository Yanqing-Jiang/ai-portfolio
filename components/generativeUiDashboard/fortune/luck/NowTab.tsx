import React from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import {
  ResultHero,
  StreamingText,
  DayMasterCard,
  GuardrailBanner,
  SeasonalStrengthBar,
  LuckFilmStrip,
} from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { tabContentVariants } from '../animations';
import type { ElementType, SeasonalStrength as SSType, LuckPillar } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS['luck-cycle'];

export const NowTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const { dataModel, status } = useFortuneStore(useShallow((s) => ({
    dataModel: s.dataModel,
    status: s.status,
  })));

  const luckCycle = dataModel?.luckCycle;
  const kpi = dataModel?.kpi as Record<string, unknown> | undefined;
  const narrative = dataModel?.narrative;
  const seasonal = dataModel?.seasonalStrength as SSType | undefined;
  const guardrail = dataModel?.guardrail;
  const decades = (dataModel?.luckPillars?.items || luckCycle?.timeline?.decades || []) as LuckPillar[];
  const currentDecadeIdx = decades.findIndex((d) => d.isCurrent);

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
      className="space-y-6 pb-20"
    >
      <ResultHero
        title={luckCycle?.currentWindow?.summary || 'Analyzing your pillars...'}
        subtitle={`Current Decade: ${luckCycle?.currentWindow?.decade || 'Pending'}`}
        score={score}
        scoreLabel="Vitality"
        accentColor={ACCENT.primary}
        loading={status === 'loading' && !luckCycle?.currentWindow}
        isReplay={isReplay}
      />

      {/* Snapshot of the timeline in "Now" view */}
      {decades.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500 px-1">
            Life Path Overview
          </h3>
          <LuckFilmStrip
            decades={decades}
            currentDecadeIndex={currentDecadeIdx}
            compact
            isReplay={isReplay}
          />
        </div>
      )}

      {narrative?.tldr && (
        <div className="bg-indigo-500/5 border border-indigo-500/10 rounded-2xl p-4">
          <StreamingText
            text={narrative.streamingText || narrative.tldr}
            isStreaming={!narrative.isComplete}
            isReplay={isReplay}
            cursorColor={ACCENT.primary}
            className="text-sm italic"
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4">
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
      </div>

      {guardrail && <GuardrailBanner guardrail={guardrail} />}
    </motion.div>
  );
};
