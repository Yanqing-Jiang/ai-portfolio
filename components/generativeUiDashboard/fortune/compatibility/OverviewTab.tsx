import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { ChevronDown, ArrowDown, ShieldCheck, AlertCircle } from 'lucide-react';
import { useFortuneStore } from '../../stores/fortuneStore';
import { DualRingGauge, StreamingText, GuardrailBanner } from '../shared';
import { FLOW_ACCENTS, OBSERVATORY_SERIF, OBSERVATORY_MONO, observatoryAccent } from '../designTokens';
import { tabContentVariants, slideDown } from '../animations';

const ACCENT = FLOW_ACCENTS.compatibility;

export const OverviewTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));
  const [expandedIndex, setExpandedIndex] = useState<string | null>(null);

  const compat = dataModel?.compatibility;
  const overview = compat?.overview;
  const guardrail = dataModel?.guardrail;

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
        <div
          className="text-[40px] font-bold leading-none"
          style={{ fontFamily: OBSERVATORY_SERIF, color: ACCENT.primary }}
        >
          {Math.round(overview.score)}
          <small
            className="mt-1 block text-[8px] font-semibold uppercase tracking-[0.25em] text-[#8a8f98]"
            style={{ fontFamily: OBSERVATORY_MONO }}
          >
            Harmony
          </small>
        </div>

        <div className="relative mx-auto w-[55vw] max-w-[220px] aspect-square">
          <DualRingGauge
            score={overview.score}
            personAName={compat?.personA?.name || 'Person A'}
            personBName={compat?.personB?.name || 'Person B'}
            accentColor={ACCENT.primary}
            size={200}
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
          animate={{ y: [0, 5, 0] }}
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
                <SplitItem
                  key={`s-${i}`}
                  label={s}
                  type="strength"
                  isExpanded={expandedIndex === `s-${i}`}
                  onToggle={() => setExpandedIndex(expandedIndex === `s-${i}` ? null : `s-${i}`)}
                />
              ))}
            </div>

            {/* Frictions Column */}
            <div className="space-y-1">
              <div className="flex items-center gap-2 px-3 py-2 justify-end">
                <span className="text-[10px] font-bold uppercase tracking-tighter text-rose-400/80">Frictions</span>
                <AlertCircle size={12} className="text-rose-400" />
              </div>
              {overview.frictions.map((f, i) => (
                <SplitItem
                  key={`f-${i}`}
                  label={f}
                  type="friction"
                  isExpanded={expandedIndex === `f-${i}`}
                  onToggle={() => setExpandedIndex(expandedIndex === `f-${i}` ? null : `f-${i}`)}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      {guardrail && <GuardrailBanner guardrail={guardrail} />}
    </motion.div>
  );
};

const SplitItem: React.FC<{
  label: string;
  type: 'strength' | 'friction';
  isExpanded: boolean;
  onToggle: () => void;
}> = ({ label, type, isExpanded, onToggle }) => {
  const isStrength = type === 'strength';
  return (
    <div className="relative">
      <button
        onClick={onToggle}
        className={`w-full p-3 text-left rounded-xl transition-all duration-300 ${
          isExpanded
            ? (isStrength ? 'bg-green-500/20' : 'bg-rose-500/20')
            : 'bg-white/5 hover:bg-white/10'
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span className={`text-[11px] font-medium leading-tight ${isStrength ? 'text-green-100' : 'text-rose-100'}`}>
            {label}
          </span>
          <ChevronDown
            size={10}
            className={`transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''} ${isStrength ? 'text-green-500' : 'text-rose-500'}`}
          />
        </div>
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              variants={slideDown}
              initial="hidden"
              animate="visible"
              exit="hidden"
              className="mt-2 text-[10px] text-slate-400 leading-normal border-t border-white/5 pt-2"
            >
              The {label.toLowerCase()} indicates a positive flow of {isStrength ? 'supportive' : 'clashing'} energy between your charts.
            </motion.div>
          )}
        </AnimatePresence>
      </button>
    </div>
  );
};
