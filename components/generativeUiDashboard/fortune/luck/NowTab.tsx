import React, { useMemo } from 'react';
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
import { OutlookSection } from '../shared/OutlookSection';
import { buildOutlook } from '../shared/outlook';
import { FLOW_ACCENTS } from '../designTokens';
import { tabContentVariants } from '../animations';
import type { ElementType, SeasonalStrength as SSType, LuckPillar } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS['luck-cycle'];
const CURRENT_YEAR = new Date().getFullYear();

function findCurrentDecadeIndex(decades: LuckPillar[]) {
  const flagged = decades.findIndex((d) => d.isCurrent);
  if (flagged >= 0) return flagged;
  return decades.findIndex((d) => (
    typeof d.startYear === 'number' &&
    typeof d.endYear === 'number' &&
    CURRENT_YEAR >= d.startYear &&
    CURRENT_YEAR <= d.endYear
  ));
}

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
  const currentDecadeIdx = findCurrentDecadeIndex(decades);
  const outlook = useMemo(() => buildOutlook(dataModel), [dataModel]);

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

      {/* The finished tldr is already the page headline — only stream the draft. */}
      {narrative?.streamingText && !narrative.isComplete && (
        <div className="bg-indigo-500/5 border border-indigo-500/10 rounded-2xl p-4">
          <StreamingText
            text={narrative.streamingText}
            isStreaming
            isReplay={isReplay}
            cursorColor={ACCENT.primary}
            className="text-sm italic"
          />
        </div>
      )}

      <OutlookSection entries={outlook} accentColor={ACCENT.primary} isReplay={isReplay} />

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
