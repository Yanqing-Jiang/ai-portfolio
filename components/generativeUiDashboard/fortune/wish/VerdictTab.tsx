import React from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { ResultHero, StreamingText, ConditionCard, YearPredictionBar, GuardrailBanner } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { Retrodiction, NarrativeInsight } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS.wish;

export const VerdictTab: React.FC<{ isReplay?: boolean; question?: string }> = ({ isReplay = false, question }) => {
  const { dataModel, status, persistenceDegraded } = useFortuneStore(
    useShallow((s) => ({ dataModel: s.dataModel, status: s.status, persistenceDegraded: s.persistenceDegraded })),
  );

  const kpi = dataModel?.kpi as Record<string, unknown> | undefined;
  const narrative = dataModel?.narrative;
  const retrodictions = dataModel?.retrodictions?.items as Retrodiction[] | undefined;
  const guardrail = dataModel?.guardrail;
  const score = typeof kpi?.harmonyScore === 'number' ? kpi.harmonyScore as number : undefined;

  // Build hero from real backend paths: narrative.tldr is the main summary,
  // kpi provides the score, narrative.insights[0] gives the lead insight
  const insights = (narrative?.insights || []) as NarrativeInsight[];
  const heroTitle = insights[0]?.heading || narrative?.tldr?.split('.')[0] || 'Reading your chart...';
  const heroSubtitle = narrative?.tldr || undefined;

  // Build conditions from narrative insights (each insight has check/warn semantics
  // based on its icon: ✓ = check, ⚠ = warn, ✗ = cross)
  const conditions = insights.slice(0, 5).map((ins) => ({
    type: (ins.icon === '✗' || ins.icon === '❌') ? 'cross' as const
        : (ins.icon === '⚠' || ins.icon === '⚠️') ? 'warn' as const
        : 'check' as const,
    text: ins.tagline || ins.heading,
  }));

  return (
    <motion.div
      key="verdict"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-5"
    >
      {/* Question quote */}
      {question && (
        <div
          className="rounded-r-2xl border-l-2 py-3 pl-5 pr-4"
          style={{ borderColor: `${ACCENT.primary}40`, background: ACCENT.bg }}
        >
          <p className="text-sm italic leading-relaxed text-white/80">{question}</p>
        </div>
      )}

      {/* Hero */}
      <ResultHero
        title={heroTitle}
        subtitle={heroSubtitle}
        score={score}
        scoreLabel="Harmony"
        accentColor={ACCENT.primary}
        loading={status === 'loading' || (status === 'streaming' && !narrative?.tldr)}
        isReplay={isReplay}
      />

      {/* Narrative TLDR streaming */}
      {narrative?.streamingText && !narrative.isComplete && (
        <StreamingText
          text={narrative.streamingText}
          isStreaming
          isReplay={isReplay}
          cursorColor={ACCENT.primary}
          className="px-1"
        />
      )}

      {/* Conditions from insights */}
      {conditions.length > 0 && (
        <motion.div
          variants={pickVariants(isReplay, staggerContainer(0.08))}
          initial="hidden"
          animate="visible"
          className="space-y-2"
        >
          {conditions.map((c, i) => (
            <ConditionCard key={i} type={c.type} text={c.text} isReplay={isReplay} />
          ))}
        </motion.div>
      )}

      {/* Year predictions (retrodictions) */}
      {retrodictions && retrodictions.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
            Year Predictions
          </h3>
          <motion.div
            variants={pickVariants(isReplay, staggerContainer(0.06))}
            initial="hidden"
            animate="visible"
            className="space-y-2"
          >
            {retrodictions.map((r) => (
              <YearPredictionBar key={r.year} item={r} accentColor={ACCENT.primary} isReplay={isReplay} />
            ))}
          </motion.div>
        </div>
      )}

      {/* Degraded persistence banner */}
      {persistenceDegraded && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-[11px] text-amber-400">
          <span>Storage is temporarily limited — your reading may not be saved for replay.</span>
        </div>
      )}

      {/* Guardrail */}
      {guardrail && <GuardrailBanner guardrail={guardrail} />}
    </motion.div>
  );
};
