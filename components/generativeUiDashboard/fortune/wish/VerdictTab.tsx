import React from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { AlertTriangle, Quote } from 'lucide-react';
import { useFortuneStore } from '../../stores/fortuneStore';
import { 
  StreamingText, 
  ConditionCard, 
  YearPredictionBar, 
  GuardrailBanner,
  VerdictBadge,
  WeighingTicker,
  VerdictProgressiveGauge
} from '../shared';
import { FLOW_ACCENTS, GLASS } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { Retrodiction, WishModel } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS.wish;

export const VerdictTab: React.FC<{ isReplay?: boolean; question?: string }> = ({ isReplay = false, question }) => {
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
  
  const isComplete = narrative?.isComplete || status === 'complete';
  const score = verdict?.score ?? 0;
  
  // Orchestration logic: how many factors are we weighing?
  // If we don't have a total, we estimate based on what we have + a bit more if still streaming
  const totalFactors = isComplete ? mechanisms.length : Math.max(mechanisms.length + 1, 5);
  const currentFactorIdx = mechanisms.length;
  const currentMechanismName = mechanisms[mechanisms.length - 1]?.title;
  
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
      {/* 1. Question quote block */}
      {question && (
        <motion.div 
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          className="relative pl-6 py-2"
        >
          <Quote className="absolute left-0 top-0 h-5 w-5 opacity-20" style={{ color: ACCENT.primary }} />
          <p className="text-base italic leading-relaxed text-white/90 font-serif">
            {question}
          </p>
        </motion.div>
      )}

      {/* 2. Verdict hero card */}
      <div className={`${GLASS} p-6 flex flex-col items-center text-center space-y-4 overflow-hidden relative`}>
        {/* Subtle background glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-32 blur-[60px] opacity-20 rounded-full" style={{ backgroundColor: ACCENT.primary }} />
        
        <VerdictProgressiveGauge 
          finalScore={score} 
          streamedFraction={streamedFraction} 
          accentColor={ACCENT.primary}
          isReplay={isReplay}
        />

        <div className="space-y-1 z-10">
          <VerdictBadge score={score} isReplay={isReplay} />
          <WeighingTicker 
            currentMechanism={currentMechanismName}
            count={currentFactorIdx}
            total={totalFactors}
            isComplete={isComplete}
            accentColor={ACCENT.primary}
          />
        </div>

        {verdict?.summary && (
          <motion.p 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-sm leading-relaxed text-slate-300 max-w-xs"
          >
            {verdict.summary}
          </motion.p>
        )}
      </div>

      {/* 3. Conditions list */}
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

      {/* 4. Caution card */}
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

      {/* 5. Year predictions */}
      {retrodictions && retrodictions.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">
              Temporal Outlook
            </h3>
            <span className="text-[10px] text-slate-600 italic">Tap to expand years</span>
          </div>
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
