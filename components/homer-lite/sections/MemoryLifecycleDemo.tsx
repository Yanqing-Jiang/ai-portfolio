import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ArrowRight, Check, Database, GitBranch, Play, RotateCcw, Terminal, X } from 'lucide-react';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

const AUTO_APPROVE_THRESHOLD = 0.95;
const HITL_MIN_CONFIDENCE = 0.20;
const CONFLICT_SIMILARITY_THRESHOLD = 0.85;
const STORAGE_KEY = 'homer-memory-lifecycle-demo-v1';

const OK_GREEN = '#86efac';
const BAD_RED = '#f87171';
const WARN_GOLD = '#f5cf94';

type ReviewDecision = 'approved' | 'rejected';
type ReviewState = Record<string, ReviewDecision>;

type Candidate = {
  id: string;
  claimType: 'fact' | 'preference' | 'decision';
  confidence: number;
  content: string;
  routeRule: string;
  destination: string;
  dropped?: boolean;
  conflict?: {
    existing: string;
    similarity: number;
  };
};

const TRANSCRIPT = [
  ['09:14', 'Ava', 'Quick update: the Warsaw workshop trip is off. Vendor cancelled the whole onsite.'],
  ['09:15', 'Homer', 'Noted. Anything to recover from the booking?'],
  ['09:15', 'Ava', 'Yes, remind ops to chase the flight credit before month-end close.'],
  ['09:17', 'Ava', 'I want weekly reviews on Friday mornings. Monday reviews keep getting stale.'],
  ['09:19', 'Ava', 'We decided reporting moves to dbt next quarter. Keep Looker as the readout layer.'],
  ['09:21', 'Homer', 'I will queue those as memory candidates where policy allows.'],
  ['09:22', 'Ava', 'Also, the cafe downstairs might still have good sesame noodles.'],
] as const;

const CANDIDATES: Candidate[] = [
  {
    id: 'warsaw-cancelled',
    claimType: 'fact',
    confidence: 0.97,
    content: "Ava's Warsaw workshop trip was cancelled; flight credit needs recovery",
    routeRule: '0.97 >= 0.95, then conflict guard cosine 0.91 >= 0.85',
    destination: 'HITL queue',
    conflict: {
      existing: 'Ava plans to attend the Warsaw workshop in September',
      similarity: 0.91,
    },
  },
  {
    id: 'friday-reviews',
    claimType: 'preference',
    confidence: 0.78,
    content: 'Ava prefers weekly reviews on Friday mornings',
    routeRule: '0.20 <= 0.78 < 0.95',
    destination: 'HITL queue',
  },
  {
    id: 'dbt-reporting',
    claimType: 'decision',
    confidence: 0.88,
    content: "Ava's team will move reporting to dbt next quarter",
    routeRule: '0.20 <= 0.88 < 0.95',
    destination: 'HITL queue',
  },
  {
    id: 'sesame-noodles',
    claimType: 'fact',
    confidence: 0.15,
    content: 'Ava said the downstairs cafe might still have good sesame noodles',
    routeRule: '0.15 < 0.20',
    destination: 'dropped as noise',
    dropped: true,
  },
];

const REVIEWABLE_CANDIDATES = CANDIDATES.filter((candidate) => !candidate.dropped);

const STEPS = [
  { label: 'Extraction', meta: 'session -> candidates' },
  { label: 'Routing', meta: 'policy + conflict guard' },
  { label: 'Review', meta: 'visitor is HITL' },
  { label: 'Memory', meta: 'tenant state' },
] as const;

const clampStep = (step: number) => Math.min(STEPS.length - 1, Math.max(0, step));
const formatConfidence = (value: number) => value.toFixed(2);

const statusColor = (decision?: ReviewDecision) => {
  if (decision === 'approved') return OK_GREEN;
  if (decision === 'rejected') return BAD_RED;
  return WARN_GOLD;
};

const TerminalFrame: React.FC<{
  title: string;
  meta?: string;
  children: React.ReactNode;
  className?: string;
}> = ({ title, meta, children, className = '' }) => (
  <div
    className={`rounded-lg border overflow-hidden ${className}`}
    style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bgSoft }}
  >
    <div
      className="flex flex-wrap items-center gap-2 px-4 py-2.5 border-b"
      style={{ borderColor: HOMER_THEME.divider, background: 'rgba(0,0,0,0.25)' }}
    >
      <Terminal size={13} style={{ color: HOMER_THEME.accent }} />
      <span
        className="text-[10px] tracking-[0.24em] uppercase"
        style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
      >
        {title}
      </span>
      {meta && (
        <span
          className="ml-0 sm:ml-auto text-[10px] tabular-nums"
          style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
        >
          {meta}
        </span>
      )}
    </div>
    {children}
  </div>
);

const PolicyPill: React.FC<{ label: string; value: string; tone?: 'ok' | 'warn' | 'drop' }> = ({
  label,
  value,
  tone = 'warn',
}) => {
  const color = tone === 'ok' ? OK_GREEN : tone === 'drop' ? BAD_RED : HOMER_THEME.accent;
  return (
    <div
      className="rounded-md border px-3 py-2 min-w-0"
      style={{ borderColor: HOMER_THEME.divider, background: '#08070a' }}
    >
      <div
        className="text-[9px] uppercase tracking-[0.18em] mb-1"
        style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
      >
        {label}
      </div>
      <div
        className="text-[12px] tabular-nums"
        style={{ color, fontFamily: HOMER_THEME.fontMono }}
      >
        {value}
      </div>
    </div>
  );
};

const ClaimTypeBadge: React.FC<{ candidate: Candidate }> = ({ candidate }) => (
  <span
    className="rounded border px-2 py-1 text-[10px] uppercase tracking-[0.18em]"
    style={{
      borderColor: candidate.dropped ? 'rgba(248,113,113,0.28)' : HOMER_THEME.divider,
      color: candidate.dropped ? BAD_RED : HOMER_THEME.accent,
      fontFamily: HOMER_THEME.fontMono,
    }}
  >
    {candidate.claimType} {formatConfidence(candidate.confidence)}
  </span>
);

const Stepper: React.FC<{
  activeStep: number;
  extractorRan: boolean;
  onStep: (step: number) => void;
}> = ({ activeStep, extractorRan, onStep }) => (
  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 p-3 border-b" style={{ borderColor: HOMER_THEME.divider }}>
    {STEPS.map((step, index) => {
      const active = index === activeStep;
      const disabled = index > 0 && !extractorRan;
      return (
        <button
          key={step.label}
          type="button"
          disabled={disabled}
          onClick={() => onStep(index)}
          className="min-h-[58px] rounded-md border px-3 py-2 text-left transition-colors disabled:opacity-35 disabled:cursor-not-allowed hover:bg-white/[0.03]"
          style={{
            borderColor: active ? HOMER_THEME.accent : HOMER_THEME.divider,
            background: active ? 'rgba(212,160,86,0.10)' : '#08070a',
          }}
          aria-current={active ? 'step' : undefined}
        >
          <div
            className="text-[10px] uppercase tracking-[0.18em] mb-1"
            style={{ color: active ? HOMER_THEME.accent : HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
          >
            {String(index + 1).padStart(2, '0')} · {step.label}
          </div>
          <div className="text-[11px] leading-snug" style={{ color: HOMER_THEME.textMuted }}>
            {step.meta}
          </div>
        </button>
      );
    })}
  </div>
);

const ExtractionPanel: React.FC<{
  extractorRan: boolean;
  visibleCandidateCount: number;
  onRun: () => void;
  onNext: () => void;
}> = ({ extractorRan, visibleCandidateCount, onRun, onNext }) => (
  <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,_0.9fr)_minmax(0,_1.1fr)] gap-4">
    <TerminalFrame title="session.replay" meta="synthetic tenant: Ava Chen">
      <div className="p-4 md:p-5 space-y-3">
        {TRANSCRIPT.map(([time, speaker, line]) => (
          <div key={`${time}-${line}`} className="grid grid-cols-[48px_54px_minmax(0,_1fr)] gap-2 text-[12px] md:text-[13px] leading-relaxed">
            <span className="tabular-nums" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>
              {time}
            </span>
            <span style={{ color: speaker === 'Ava' ? HOMER_THEME.accent : HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>
              {speaker}
            </span>
            <span style={{ color: HOMER_THEME.text }}>{line}</span>
          </div>
        ))}
      </div>
    </TerminalFrame>

    <TerminalFrame
      title="nightly-extractor.out"
      meta={extractorRan ? `${Math.min(visibleCandidateCount, CANDIDATES.length)} candidates` : 'idle'}
    >
      <div className="p-4 md:p-5 min-h-[340px] flex flex-col">
        {!extractorRan ? (
          <div className="flex-1 flex flex-col justify-center">
            <div
              className="text-[11px] uppercase tracking-[0.2em] mb-4"
              style={{ color: HOMER_THEME.accent, fontFamily: HOMER_THEME.fontMono }}
            >
              extractor ready
            </div>
            <p className="text-sm leading-relaxed mb-5" style={{ color: HOMER_THEME.textMuted }}>
              The daemon first converts a conversation into candidate claims, then routes each candidate by confidence and conflict policy.
            </p>
            <button
              type="button"
              onClick={onRun}
              className="inline-flex min-h-[44px] items-center justify-center gap-2 self-start rounded-md border px-4 text-[11px] uppercase tracking-[0.18em] transition-colors hover:bg-white/[0.03]"
              style={{
                borderColor: HOMER_THEME.accentSoft,
                background: HOMER_THEME.accentSoft,
                color: HOMER_THEME.accent,
                fontFamily: HOMER_THEME.fontMono,
              }}
            >
              <Play size={14} />
              run extractor
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <AnimatePresence initial={false}>
              {CANDIDATES.slice(0, visibleCandidateCount).map((candidate) => (
                <motion.div
                  key={candidate.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.22 }}
                  className="rounded-md border p-3"
                  style={{ borderColor: HOMER_THEME.divider, background: '#08070a' }}
                >
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <ClaimTypeBadge candidate={candidate} />
                    {candidate.dropped && (
                      <span
                        className="text-[10px] uppercase tracking-[0.18em]"
                        style={{ color: BAD_RED, fontFamily: HOMER_THEME.fontMono }}
                      >
                        dropped as noise (&lt; 0.20)
                      </span>
                    )}
                  </div>
                  <p
                    className={`text-sm leading-relaxed ${candidate.dropped ? 'line-through opacity-65' : ''}`}
                    style={{ color: candidate.dropped ? HOMER_THEME.textMuted : HOMER_THEME.text }}
                  >
                    {candidate.content}
                  </p>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}

        <div className="mt-auto pt-5 flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
          <div className="grid grid-cols-3 gap-2">
            <PolicyPill label="auto" value=">= 0.95" tone="ok" />
            <PolicyPill label="HITL" value="0.20...0.95" />
            <PolicyPill label="drop" value="< 0.20" tone="drop" />
          </div>
          <button
            type="button"
            disabled={!extractorRan}
            onClick={onNext}
            className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border px-4 text-[11px] uppercase tracking-[0.18em] transition-colors hover:bg-white/[0.03] disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
          >
            route claims
            <ArrowRight size={14} />
          </button>
        </div>
      </div>
    </TerminalFrame>
  </div>
);

const RoutingPanel: React.FC<{ onNext: () => void }> = ({ onNext }) => {
  const conflicted = REVIEWABLE_CANDIDATES.find((candidate) => candidate.conflict);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,_1.25fr)_minmax(280px,_0.75fr)] gap-4">
        <TerminalFrame title="policy-gate.route" meta="surviving candidates only">
          <div className="p-4 md:p-5">
            <div
              className="hidden md:grid grid-cols-[minmax(230px,_1fr)_minmax(270px,_1.15fr)_145px] gap-3 pb-2 mb-2 border-b text-[10px] uppercase tracking-[0.18em]"
              style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
            >
              <span>claim</span>
              <span>rule applied</span>
              <span>destination</span>
            </div>

            <div className="space-y-2">
              {REVIEWABLE_CANDIDATES.map((candidate, index) => (
                <motion.div
                  key={candidate.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.28, delay: index * 0.08 }}
                  className="grid grid-cols-1 md:grid-cols-[minmax(230px,_1fr)_minmax(270px,_1.15fr)_145px] gap-2 md:gap-3 rounded-md border p-3"
                  style={{ borderColor: HOMER_THEME.divider, background: '#08070a' }}
                >
                  <div className="min-w-0">
                    <div className="mb-2">
                      <ClaimTypeBadge candidate={candidate} />
                    </div>
                    <p className="text-sm leading-relaxed" style={{ color: HOMER_THEME.text }}>
                      {candidate.content}
                    </p>
                  </div>
                  <div
                    className="text-[11px] leading-relaxed tabular-nums"
                    style={{ color: candidate.conflict ? WARN_GOLD : HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
                  >
                    {candidate.routeRule}
                  </div>
                  <div
                    className="text-[11px] uppercase tracking-[0.16em]"
                    style={{ color: WARN_GOLD, fontFamily: HOMER_THEME.fontMono }}
                  >
                    {candidate.destination}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </TerminalFrame>

        <TerminalFrame title="conflict-guard.trace" meta={`threshold ${CONFLICT_SIMILARITY_THRESHOLD.toFixed(2)}`}>
          <div className="p-4 md:p-5">
            {conflicted?.conflict && (
              <div className="rounded-md border p-4" style={{ borderColor: 'rgba(245,207,148,0.28)', background: '#08070a' }}>
                <div className="flex items-center gap-2 mb-4">
                  <GitBranch size={15} style={{ color: WARN_GOLD }} />
                  <span
                    className="text-[10px] uppercase tracking-[0.18em]"
                    style={{ color: WARN_GOLD, fontFamily: HOMER_THEME.fontMono }}
                  >
                    demoted - fail-closed
                  </span>
                </div>

                <div className="space-y-3 text-sm leading-relaxed">
                  <div>
                    <div
                      className="text-[10px] uppercase tracking-[0.18em] mb-1"
                      style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
                    >
                      existing tenant claim
                    </div>
                    <p style={{ color: HOMER_THEME.text }}>{conflicted.conflict.existing}</p>
                  </div>

                  <div>
                    <div
                      className="text-[10px] uppercase tracking-[0.18em] mb-1"
                      style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
                    >
                      new claim
                    </div>
                    <p style={{ color: HOMER_THEME.text }}>{conflicted.content}</p>
                  </div>
                </div>

                <div className="mt-5">
                  <div className="flex justify-between text-[10px] tabular-nums mb-2" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>
                    <span>cosine {conflicted.conflict.similarity.toFixed(2)}</span>
                    <span>threshold {CONFLICT_SIMILARITY_THRESHOLD.toFixed(2)}</span>
                  </div>
                  <div className="h-2 rounded-full overflow-hidden" style={{ background: HOMER_THEME.divider }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${conflicted.conflict.similarity * 100}%` }}
                      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
                      className="h-full rounded-full"
                      style={{ background: WARN_GOLD }}
                    />
                  </div>
                </div>

                <div
                  className="mt-4 rounded border px-3 py-2 text-[11px] uppercase tracking-[0.16em]"
                  style={{ borderColor: 'rgba(245,207,148,0.28)', color: WARN_GOLD, fontFamily: HOMER_THEME.fontMono }}
                >
                  verdict: DEMOTED — fail-closed
                </div>
              </div>
            )}
          </div>
        </TerminalFrame>
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={onNext}
          className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border px-4 text-[11px] uppercase tracking-[0.18em] transition-colors hover:bg-white/[0.03]"
          style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
        >
          open review queue
          <ArrowRight size={14} />
        </button>
      </div>
    </div>
  );
};

const ReviewPanel: React.FC<{
  reviews: ReviewState;
  reviewedCount: number;
  onDecision: (id: string, decision: ReviewDecision) => void;
  onReset: () => void;
  onNext: () => void;
}> = ({ reviews, reviewedCount, onDecision, onReset, onNext }) => (
  <TerminalFrame title="telegram-review.queue" meta={`${reviewedCount}/${REVIEWABLE_CANDIDATES.length} decided`}>
    <div className="p-4 md:p-5">
      <div className="mb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <p className="text-sm leading-relaxed max-w-2xl" style={{ color: HOMER_THEME.textMuted }}>
          You are the human in the loop. Approving the Warsaw replacement supersedes the older workshop memory; rejecting it leaves the old claim active.
        </p>
        <button
          type="button"
          onClick={onReset}
          className="inline-flex min-h-[40px] items-center gap-2 self-start rounded-md border px-3 text-[11px] uppercase tracking-[0.18em] transition-colors hover:bg-white/[0.03]"
          style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
        >
          <RotateCcw size={13} />
          reset demo
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {REVIEWABLE_CANDIDATES.map((candidate) => {
          const decision = reviews[candidate.id];
          return (
            <article
              key={candidate.id}
              className="rounded-lg border overflow-hidden flex flex-col"
              style={{ borderColor: HOMER_THEME.divider, background: '#08070a' }}
            >
              <div className="px-4 py-3 border-b" style={{ borderColor: HOMER_THEME.divider, background: 'rgba(255,255,255,0.02)' }}>
                <div className="flex flex-wrap items-center gap-2">
                  <ClaimTypeBadge candidate={candidate} />
                  <span
                    className="ml-auto text-[10px] uppercase tracking-[0.18em]"
                    style={{ color: statusColor(decision), fontFamily: HOMER_THEME.fontMono }}
                  >
                    {decision ?? 'pending'}
                  </span>
                </div>
              </div>

              <div className="p-4 flex-1">
                {candidate.conflict && (
                  <div className="mb-3 rounded-md border p-3" style={{ borderColor: 'rgba(245,207,148,0.22)' }}>
                    <div
                      className="text-[10px] uppercase tracking-[0.18em] mb-1"
                      style={{ color: WARN_GOLD, fontFamily: HOMER_THEME.fontMono }}
                    >
                      conflict found
                    </div>
                    <p className="text-xs leading-relaxed line-through mb-2" style={{ color: HOMER_THEME.textMuted }}>
                      {candidate.conflict.existing}
                    </p>
                    <p className="text-xs leading-relaxed" style={{ color: HOMER_THEME.text }}>
                      {candidate.content}
                    </p>
                  </div>
                )}
                {!candidate.conflict && (
                  <p className="text-sm leading-relaxed" style={{ color: HOMER_THEME.text }}>
                    {candidate.content}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2 p-3 border-t" style={{ borderColor: HOMER_THEME.divider }}>
                <button
                  type="button"
                  onClick={() => onDecision(candidate.id, 'approved')}
                  className="inline-flex min-h-[40px] items-center justify-center gap-2 rounded-md border text-[11px] uppercase tracking-[0.16em] transition-colors hover:bg-white/[0.03]"
                  style={{
                    borderColor: decision === 'approved' ? 'rgba(134,239,172,0.42)' : HOMER_THEME.divider,
                    color: decision === 'approved' ? OK_GREEN : HOMER_THEME.textMuted,
                    fontFamily: HOMER_THEME.fontMono,
                  }}
                >
                  <Check size={14} />
                  approve
                </button>
                <button
                  type="button"
                  onClick={() => onDecision(candidate.id, 'rejected')}
                  className="inline-flex min-h-[40px] items-center justify-center gap-2 rounded-md border text-[11px] uppercase tracking-[0.16em] transition-colors hover:bg-white/[0.03]"
                  style={{
                    borderColor: decision === 'rejected' ? 'rgba(248,113,113,0.42)' : HOMER_THEME.divider,
                    color: decision === 'rejected' ? BAD_RED : HOMER_THEME.textMuted,
                    fontFamily: HOMER_THEME.fontMono,
                  }}
                >
                  <X size={14} />
                  reject
                </button>
              </div>
            </article>
          );
        })}
      </div>

      <div className="mt-5 flex justify-end">
        <button
          type="button"
          onClick={onNext}
          className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border px-4 text-[11px] uppercase tracking-[0.18em] transition-colors hover:bg-white/[0.03]"
          style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
        >
          inspect memory state
          <ArrowRight size={14} />
        </button>
      </div>
    </div>
  </TerminalFrame>
);

const MemoryStatePanel: React.FC<{ reviews: ReviewState; onReset: () => void }> = ({ reviews, onReset }) => {
  const warsawApproved = reviews['warsaw-cancelled'] === 'approved';

  return (
    <TerminalFrame title="knowledge_claims.tenant_view" meta="Ava Chen · ops lead">
      <div className="p-4 md:p-5">
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,_1fr)_280px] gap-4">
          <div className="space-y-2">
            <div
              className="rounded-md border p-3"
              style={{ borderColor: warsawApproved ? 'rgba(248,113,113,0.25)' : HOMER_THEME.divider, background: '#08070a' }}
            >
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span
                  className="rounded border px-2 py-1 text-[10px] uppercase tracking-[0.18em]"
                  style={{
                    borderColor: warsawApproved ? 'rgba(248,113,113,0.30)' : HOMER_THEME.divider,
                    color: warsawApproved ? BAD_RED : OK_GREEN,
                    fontFamily: HOMER_THEME.fontMono,
                  }}
                >
                  {warsawApproved ? 'superseded' : 'approved'}
                </span>
                <span className="text-[10px] tabular-nums" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>
                  existing · decided_by: daemon
                </span>
                {warsawApproved && (
                  <span className="text-[10px] tabular-nums" style={{ color: WARN_GOLD, fontFamily: HOMER_THEME.fontMono }}>
                    superseded -&gt; warsaw-cancelled
                  </span>
                )}
              </div>
              <p
                className={`text-sm leading-relaxed ${warsawApproved ? 'line-through opacity-60' : ''}`}
                style={{ color: warsawApproved ? HOMER_THEME.textMuted : HOMER_THEME.text }}
              >
                Ava plans to attend the Warsaw workshop in September
              </p>
            </div>

            <div className="rounded-md border p-3" style={{ borderColor: HOMER_THEME.divider, background: '#08070a' }}>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span
                  className="rounded border px-2 py-1 text-[10px] uppercase tracking-[0.18em]"
                  style={{ borderColor: HOMER_THEME.divider, color: OK_GREEN, fontFamily: HOMER_THEME.fontMono }}
                >
                  approved
                </span>
                <span className="text-[10px] tabular-nums" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>
                  baseline · decided_by: daemon
                </span>
              </div>
              <p className="text-sm leading-relaxed" style={{ color: HOMER_THEME.text }}>
                Ava owns weekly operational reporting for support and revenue operations
              </p>
            </div>

            {REVIEWABLE_CANDIDATES.map((candidate) => {
              const decision = reviews[candidate.id];
              const pending = !decision;
              const rejected = decision === 'rejected';
              return (
                <div
                  key={candidate.id}
                  className={`rounded-md border p-3 ${rejected ? 'opacity-45' : ''}`}
                  style={{ borderColor: rejected ? 'rgba(248,113,113,0.22)' : HOMER_THEME.divider, background: '#08070a' }}
                >
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <span
                      className="rounded border px-2 py-1 text-[10px] uppercase tracking-[0.18em]"
                      style={{
                        borderColor: pending ? HOMER_THEME.divider : rejected ? 'rgba(248,113,113,0.32)' : 'rgba(134,239,172,0.32)',
                        color: pending ? WARN_GOLD : rejected ? BAD_RED : OK_GREEN,
                        fontFamily: HOMER_THEME.fontMono,
                      }}
                    >
                      {pending ? 'candidate' : decision}
                    </span>
                    <span className="text-[10px] tabular-nums" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>
                      {candidate.claimType} · decided_by: {pending ? 'awaiting visitor' : 'visitor'}
                    </span>
                  </div>
                  <p className="text-sm leading-relaxed" style={{ color: rejected ? HOMER_THEME.textMuted : HOMER_THEME.text }}>
                    {candidate.content}
                  </p>
                </div>
              );
            })}
          </div>

          <div className="rounded-lg border p-4 self-start" style={{ borderColor: HOMER_THEME.divider, background: '#08070a' }}>
            <Database size={18} style={{ color: HOMER_THEME.accent }} />
            <div
              className="mt-3 text-[10px] uppercase tracking-[0.18em]"
              style={{ color: HOMER_THEME.accent, fontFamily: HOMER_THEME.fontMono }}
            >
              production shape
            </div>
            <p className="mt-3 text-sm leading-relaxed" style={{ color: HOMER_THEME.textMuted }}>
              This exact loop runs nightly on the production daemon — extraction, conflict guard, Telegram review, promotion.
            </p>
            <button
              type="button"
              onClick={onReset}
              className="mt-5 inline-flex min-h-[40px] items-center gap-2 rounded-md border px-3 text-[11px] uppercase tracking-[0.18em] transition-colors hover:bg-white/[0.03]"
              style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
            >
              <RotateCcw size={13} />
              reset demo
            </button>
          </div>
        </div>
      </div>
    </TerminalFrame>
  );
};

export const MemoryLifecycleDemo: React.FC = () => {
  const prefersReducedMotion = useReducedMotion();
  const reducedMotion = Boolean(prefersReducedMotion);
  const [expanded, setExpanded] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [extractorRan, setExtractorRan] = useState(false);
  const [visibleCandidateCount, setVisibleCandidateCount] = useState(0);
  const [reviews, setReviews] = useState<ReviewState>({});

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;

    try {
      const parsed = JSON.parse(raw) as ReviewState;
      const next: ReviewState = {};
      for (const candidate of REVIEWABLE_CANDIDATES) {
        const value = parsed[candidate.id];
        if (value === 'approved' || value === 'rejected') {
          next[candidate.id] = value;
        }
      }
      setReviews(next);
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (!extractorRan) {
      setVisibleCandidateCount(0);
      return undefined;
    }

    if (reducedMotion) {
      setVisibleCandidateCount(CANDIDATES.length);
      return undefined;
    }

    setVisibleCandidateCount(0);
    let nextCount = 0;
    const interval = window.setInterval(() => {
      nextCount += 1;
      setVisibleCandidateCount(Math.min(nextCount, CANDIDATES.length));
      if (nextCount >= CANDIDATES.length) {
        window.clearInterval(interval);
      }
    }, 360);

    return () => window.clearInterval(interval);
  }, [extractorRan, reducedMotion]);

  const reviewedCount = useMemo(
    () => REVIEWABLE_CANDIDATES.filter((candidate) => reviews[candidate.id]).length,
    [reviews],
  );

  const persistReviews = (next: ReviewState) => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  };

  const recordDecision = (id: string, decision: ReviewDecision) => {
    setReviews((current) => {
      const next = { ...current, [id]: decision };
      persistReviews(next);
      return next;
    });
  };

  const resetDemo = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(STORAGE_KEY);
    }
    setReviews({});
    setExtractorRan(false);
    setVisibleCandidateCount(0);
    setActiveStep(0);
  };

  const moveToStep = (step: number) => {
    if (step > 0 && !extractorRan) return;
    setActiveStep(clampStep(step));
  };

  return (
    <SectionShell
      id="memory-lifecycle"
      className={expanded ? '!py-12 md:!py-16 lg:!py-20' : '!py-8 md:!py-10 lg:!py-12'}
    >
      <div
        className="rounded-lg border overflow-hidden"
        style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bgSoft }}
      >
        <AnimatePresence mode="wait" initial={false}>
          {!expanded ? (
            <motion.div
              key="launcher"
              initial={reducedMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={reducedMotion ? undefined : { opacity: 0 }}
              transition={{ duration: reducedMotion ? 0 : 0.25 }}
              className="p-5 md:p-8 flex flex-col justify-center"
              style={{ minHeight: 'clamp(280px, 42vh, 360px)' }}
            >
              <div
                className="text-[11px] tracking-[0.32em] uppercase mb-5"
                style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
              >
                MEMORY LIFECYCLE
              </div>
              <h2
                className="text-3xl md:text-5xl leading-[1.1] tracking-tight font-medium max-w-3xl"
                style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
              >
                You be the human in the loop.
              </h2>
              <p className="mt-5 max-w-2xl text-base md:text-lg leading-relaxed" style={{ color: HOMER_THEME.textMuted }}>
                Guided replay of the production promotion pipeline — real thresholds, synthetic tenant data.
                Ava Chen is a fictional ops lead; every claim below is invented for this public demo.
              </p>
              <div className="mt-7 flex flex-col sm:flex-row gap-3 sm:items-center">
                <button
                  type="button"
                  onClick={() => {
                    setExpanded(true);
                    setActiveStep(0);
                  }}
                  className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-md border px-5 text-[11px] uppercase tracking-[0.18em] transition-colors hover:bg-white/[0.03]"
                  style={{
                    borderColor: HOMER_THEME.accentSoft,
                    background: HOMER_THEME.accentSoft,
                    color: HOMER_THEME.accent,
                    fontFamily: HOMER_THEME.fontMono,
                  }}
                >
                  run the pipeline
                  <ArrowRight size={14} />
                </button>
                <span
                  className="text-[11px] tabular-nums"
                  style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
                >
                  auto {AUTO_APPROVE_THRESHOLD.toFixed(2)} · queue {HITL_MIN_CONFIDENCE.toFixed(2)}...{AUTO_APPROVE_THRESHOLD.toFixed(2)} · conflict {CONFLICT_SIMILARITY_THRESHOLD.toFixed(2)}
                </span>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="demo"
              initial={reducedMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reducedMotion ? undefined : { opacity: 0 }}
              transition={{ duration: reducedMotion ? 0 : 0.32, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="p-4 md:p-5 border-b" style={{ borderColor: HOMER_THEME.divider }}>
                <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
                  <div>
                    <div
                      className="text-[11px] tracking-[0.32em] uppercase mb-3"
                      style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
                    >
                      MEMORY LIFECYCLE
                    </div>
                    <h2
                      className="text-2xl md:text-4xl leading-[1.1] tracking-tight font-medium"
                      style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
                    >
                      Promotion policy, with a person in the loop.
                    </h2>
                  </div>
                  <p className="text-sm leading-relaxed max-w-xl" style={{ color: HOMER_THEME.textMuted }}>
                    Guided replay of the production promotion pipeline — real thresholds, synthetic tenant data.
                  </p>
                </div>
              </div>

              <Stepper activeStep={activeStep} extractorRan={extractorRan} onStep={moveToStep} />

              <div className="p-4 md:p-5">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div
                    key={activeStep}
                    initial={reducedMotion ? false : { opacity: 0, x: 12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={reducedMotion ? undefined : { opacity: 0, x: -8 }}
                    transition={{ duration: reducedMotion ? 0 : 0.28, ease: [0.16, 1, 0.3, 1] }}
                  >
                    {activeStep === 0 && (
                      <ExtractionPanel
                        extractorRan={extractorRan}
                        visibleCandidateCount={visibleCandidateCount}
                        onRun={() => setExtractorRan(true)}
                        onNext={() => moveToStep(1)}
                      />
                    )}
                    {activeStep === 1 && <RoutingPanel onNext={() => moveToStep(2)} />}
                    {activeStep === 2 && (
                      <ReviewPanel
                        reviews={reviews}
                        reviewedCount={reviewedCount}
                        onDecision={recordDecision}
                        onReset={resetDemo}
                        onNext={() => moveToStep(3)}
                      />
                    )}
                    {activeStep === 3 && <MemoryStatePanel reviews={reviews} onReset={resetDemo} />}
                  </motion.div>
                </AnimatePresence>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </SectionShell>
  );
};

export default MemoryLifecycleDemo;
