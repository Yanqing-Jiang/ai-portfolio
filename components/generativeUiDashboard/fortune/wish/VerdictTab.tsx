import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { AlertTriangle, ChevronDown } from 'lucide-react';
import { useFortuneStore } from '../../stores/fortuneStore';
import {
  StreamingText,
  ConditionCard,
  YearPredictionBar,
  GuardrailBanner,
  VerdictBadge,
  WeighingTicker,
  VerdictProgressiveGauge,
  ReadingBridge,
} from '../shared';
import { OutlookSection } from '../shared/OutlookSection';
import { buildOutlook } from '../shared/outlook';
import { FLOW_ACCENTS, observatoryAccent } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { Retrodiction, WishModel } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS.wish;

export const VerdictTab: React.FC<{
  isReplay?: boolean;
  failed?: boolean;
  onTabChange?: (id: string) => void;
}> = ({
  isReplay = false,
  failed = false,
  onTabChange,
}) => {
  const { dataModel, status, persistenceDegraded } = useFortuneStore(
    useShallow((s) => ({
      dataModel: s.dataModel,
      status: s.status,
      persistenceDegraded: s.persistenceDegraded
    })),
  );

  const wish = dataModel?.wish as WishModel | undefined;
  const verdict = wish?.verdict;
  const mechanisms = wish?.mechanisms || [];
  const narrative = dataModel?.narrative;
  const retrodictions = dataModel?.retrodictions?.items as Retrodiction[] | undefined;
  const guardrail = dataModel?.guardrail;
  const outlook = useMemo(() => buildOutlook(dataModel), [dataModel]);

  // A stopped run is terminal — never keep "weighing" a reading that ended.
  const isComplete = narrative?.isComplete || status === 'complete' || failed;
  const score = verdict?.score ?? 0;
  
  // Orchestration logic: how many factors are we weighing?
  // If we don't have a total, we estimate based on what we have + a bit more if still streaming
  const totalFactors = isComplete ? mechanisms.length : Math.max(mechanisms.length + 1, 5);
  const currentFactorIdx = mechanisms.length;
  const currentMechanismName = mechanisms[mechanisms.length - 1]?.title;
  const weighedCount = mechanisms.length || narrative?.insights?.length || wish?.anchors?.length || 0;
  
  const streamedFraction = isComplete ? 1 : Math.min(0.9, mechanisms.length / totalFactors);

  return (
    <motion.div
      key="verdict"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6 pb-8"
    >
      {/* 1. Verdict hero card — Observatory accent wash. The question already
          sits in the shell's context line; don't repeat it. A stopped run with
          no verdict shows no hero at all rather than an empty gauge. */}
      {(!failed || !!verdict) && (
        <div
          className="relative flex flex-col items-center gap-3 overflow-hidden rounded-2xl border p-4 text-center sm:gap-4 sm:p-6"
          style={{
            borderColor: observatoryAccent(ACCENT.primary).heroBorder,
            background: observatoryAccent(ACCENT.primary).heroWash,
          }}
        >
          <div
            className="absolute -right-6 -top-8 h-28 w-28 rounded-full opacity-20 blur-3xl"
            style={{ backgroundColor: ACCENT.primary }}
            aria-hidden
          />

          {!isComplete && !failed && verdict && (
            <VerdictProgressiveGauge
              finalScore={score}
              streamedFraction={streamedFraction}
              accentColor={ACCENT.primary}
              isReplay={isReplay}
            />
          )}

          <div className="z-10 space-y-1">
            {verdict ? (
              <VerdictBadge score={score} isReplay={isReplay} />
            ) : (
              <p className="text-sm text-slate-300">Reading your chart…</p>
            )}
            {!failed && (
              <WeighingTicker
                currentMechanism={currentMechanismName}
                count={isComplete ? weighedCount : currentFactorIdx}
                total={totalFactors}
                isComplete={isComplete}
                accentColor={ACCENT.primary}
                onTabChange={onTabChange}
              />
            )}
          </div>

          {verdict?.summary && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="max-w-sm text-[12.5px] leading-relaxed text-[#9aa0a8]"
            >
              {verdict.summary}
            </motion.p>
          )}
        </div>
      )}

      {/* 2. Conditions list */}
      {verdict?.conditions && verdict.conditions.length > 0 && (
        <motion.div
          variants={pickVariants(isReplay, staggerContainer(0.1))}
          initial="hidden"
          animate="visible"
          className="space-y-2"
        >
          {verdict.conditions.map((c, i) => (
            <ConditionCard key={i} type={c.type} text={c.text} isReplay={isReplay} />
          ))}
        </motion.div>
      )}

      {/* 3. Caution card */}
      {verdict?.caution && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 flex gap-3"
        >
          <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0" />
          <p className="text-xs leading-relaxed text-amber-200/80">
            <span className="font-bold text-amber-400 block mb-1 uppercase tracking-wider">Caution</span>
            {verdict.caution}
          </p>
        </motion.div>
      )}

      {/* 4. Dated guidance — year/age → possible event → action */}
      <OutlookSection entries={outlook} accentColor={ACCENT.primary} isReplay={isReplay} />
      <ReadingBridge functionId="wish" dataModel={dataModel} onTabChange={onTabChange} />

      {/* 5. Past-year pattern checks — a diagnostic, not part of the reading */}
      {retrodictions && retrodictions.length > 0 && (
        <details className="group rounded-xl border border-white/[0.06] bg-white/[0.015]">
          <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 px-3 text-[11px] text-slate-400 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-white/40">
            <span>Past-year pattern checks ({retrodictions.length})</span>
            <ChevronDown size={13} className="flex-none transition-transform group-open:rotate-180" aria-hidden />
          </summary>
          <div className="space-y-2 px-3 pb-3">
            <p className="text-[10.5px] leading-relaxed text-slate-500">
              Earlier years the same method flags. They test the chart's patterns; they are not predictions.
            </p>
            <motion.div
              variants={pickVariants(isReplay, staggerContainer(0.08))}
              initial="hidden"
              animate="visible"
              className="space-y-2"
            >
              {retrodictions.map((r, index) => (
                <YearPredictionBar key={`${r.year}-${index}`} item={r} accentColor={ACCENT.primary} isReplay={isReplay} />
              ))}
            </motion.div>
          </div>
        </details>
      )}

      {/* Narrative TLDR streaming (fallback if verdict summary not yet available) */}
      {narrative?.streamingText && !verdict?.summary && (
        <StreamingText
          text={narrative.streamingText}
          isStreaming={!isComplete}
          isReplay={isReplay}
          cursorColor={ACCENT.primary}
          className="px-1 text-sm text-slate-400 italic"
        />
      )}

      {/* Persistence & Guardrails */}
      <div className="space-y-4 pt-4">
        {persistenceDegraded && (
          <div className="flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-[10px] text-amber-400/80">
            <AlertTriangle className="h-3 w-3" />
            <span>Storage is temporarily limited — your reading may not be saved.</span>
          </div>
        )}
        {guardrail && <GuardrailBanner guardrail={guardrail} />}
      </div>
    </motion.div>
  );
};
