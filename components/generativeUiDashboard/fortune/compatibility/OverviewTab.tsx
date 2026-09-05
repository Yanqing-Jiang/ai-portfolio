import React, { useMemo } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { ArrowDown, ShieldCheck, AlertCircle } from 'lucide-react';
import { useFortuneStore } from '../../stores/fortuneStore';
import { DualRingGauge, StreamingText, GuardrailBanner, ReadingBridge } from '../shared';
import { OutlookSection } from '../shared/OutlookSection';
import { buildOutlook } from '../shared/outlook';
import { FLOW_ACCENTS, observatoryAccent } from '../designTokens';
import { tabContentVariants } from '../animations';

const ACCENT = FLOW_ACCENTS.compatibility;

export const OverviewTab: React.FC<{
  isReplay?: boolean;
  onTabChange?: (id: string) => void;
}> = ({ isReplay = false, onTabChange }) => {
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  const reduceMotion = useReducedMotion();
  const compat = dataModel?.compatibility;
  const overview = compat?.overview;
  const guardrail = dataModel?.guardrail;
  // Birthday ages in the brief are Person A's; say so rather than leaving it open.
  const outlook = useMemo(
    () => buildOutlook(dataModel, { personLabel: compat?.personA?.name || 'Person A' }),
    [dataModel, compat?.personA?.name],
  );

  if (!overview) return null;

  return (
    <motion.div
      key="overview"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-8 pb-10"
    >
      {/* Hero Score Section — Observatory accent wash */}
      <div
        className="relative flex flex-col items-center gap-4 overflow-hidden rounded-2xl border p-6 text-center"
        style={{
          borderColor: observatoryAccent(ACCENT.primary).heroBorder,
          background: observatoryAccent(ACCENT.primary).heroWash,
        }}
      >
        <div className="relative mx-auto w-40">
          <DualRingGauge
            score={overview.score}
            personAName={compat?.personA?.name || 'Person A'}
            personBName={compat?.personB?.name || 'Person B'}
            accentColor={ACCENT.primary}
            size={160}
            isReplay={isReplay}
          />
        </div>

        <div
          className="rounded-full border px-4 py-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.15em]"
          style={{
            color: ACCENT.primary,
            borderColor: observatoryAccent(ACCENT.primary).tabBorder,
            background: observatoryAccent(ACCENT.primary).tabBg,
          }}
        >
          {overview.relationship} Compatibility
        </div>

        <StreamingText
          text={overview.summary}
          isStreaming={false}
          isReplay={isReplay}
          className="max-w-md text-[12.5px] leading-relaxed text-[#9aa0a8]"
        />

        <motion.div
          animate={reduceMotion ? undefined : { y: [0, 5, 0] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="text-slate-500"
        >
          <ArrowDown size={14} />
        </motion.div>
      </div>

      {/* Strengths & Frictions Split Panel */}
      <div className="grid grid-cols-1 gap-4">
        <div className="relative overflow-hidden rounded-3xl border border-white/5 bg-slate-900/40">
          {/* Diagonal Divider Background */}
          <div className="absolute inset-0 opacity-10 pointer-events-none">
            <div className="absolute inset-0 bg-gradient-to-br from-green-500 via-transparent to-rose-500" />
          </div>

          <div className="relative z-10 p-1 grid grid-cols-2 gap-1">
            {/* Strengths Column */}
            <div className="space-y-1">
              <div className="flex items-center gap-2 px-3 py-2">
                <ShieldCheck size={12} className="text-green-400" />
                <span className="text-[10px] font-bold uppercase tracking-tighter text-green-400/80">Strengths</span>
              </div>
              {overview.strengths.map((s, i) => (
                <SplitItem key={`s-${i}`} label={s} type="strength" />
              ))}
            </div>

            {/* Frictions Column */}
            <div className="space-y-1">
              <div className="flex items-center gap-2 px-3 py-2 justify-end">
                <span className="text-[10px] font-bold uppercase tracking-tighter text-rose-400/80">Frictions</span>
                <AlertCircle size={12} className="text-rose-400" />
              </div>
              {overview.frictions.map((f, i) => (
                <SplitItem key={`f-${i}`} label={f} type="friction" />
              ))}
            </div>
          </div>
        </div>
      </div>

      <OutlookSection entries={outlook} accentColor={ACCENT.primary} isReplay={isReplay} />
      <ReadingBridge functionId="compatibility" dataModel={dataModel} onTabChange={onTabChange} />

      {guardrail && <GuardrailBanner guardrail={guardrail} />}
    </motion.div>
  );
};

/** Plain list item: these labels carry no stored detail, so nothing expands. */
const SplitItem: React.FC<{
  label: string;
  type: 'strength' | 'friction';
}> = ({ label, type }) => {
  const isStrength = type === 'strength';
  return (
    <div className="rounded-xl bg-white/5 p-3">
      <span
        className={`text-[11px] font-medium leading-tight ${
          isStrength ? 'text-green-100' : 'text-rose-100'
        }`}
      >
        {label}
      </span>
    </div>
  );
};
