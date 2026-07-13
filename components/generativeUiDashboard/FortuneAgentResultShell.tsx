/**
 * FortuneAgentResultShell — Observatory chrome for all 4 result pages.
 *
 * Phase 5 visual direction (mock A + B ledger rail):
 * - Top status bar: fortune://{fn}/{id} · model · LIVE/REPLAY/GUARDRAIL
 * - Kicker (CJK · label) + serif tldr headline + context sub-line
 * - KPI band (4 cards)
 * - Pill tabs (mono uppercase)
 * - Optional desktop Glass Box rail; mobile keeps inline placement
 */

import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import type { FortunePurposeId } from './fortuneAgentTheme';
import type { ResultKpi } from './fortune/shell/resultConfig';
import {
  OBSERVATORY_SERIF,
  OBSERVATORY_MONO,
  OBS_KPI_CARD,
  OBS_KPI_VALUE,
  OBS_KPI_LABEL,
  OBS_TAB,
  observatoryAccent,
  accentAlpha,
} from './fortune/designTokens';

export interface FortuneTab {
  id: string;
  label: string;
}

export type ShellRunState = 'live' | 'replay' | 'guardrail_failed';

interface FortuneAgentResultShellProps {
  purpose: FortunePurposeId;
  /** Accent primary hex from FLOW_ACCENTS (not FORTUNE_THEMES). */
  accentPrimary: string;
  glyph: string;
  kicker: string;
  headline: string;
  contextLine?: string;
  kpis: ResultKpi[];
  statusPath: string;
  modelId?: string;
  runState: ShellRunState;
  tabs: FortuneTab[];
  activeTabId: string;
  onTabChange: (id: string) => void;
  onBack?: () => void;
  /** Desktop (≥lg) sticky execution-trace rail. */
  rail?: React.ReactNode;
  /** Mobile / compact chrome above main (Glass Box + pause). */
  mobileChrome?: React.ReactNode;
  children: React.ReactNode;
}

function StateChip({
  runState,
  accent,
  reduceMotion,
}: {
  runState: ShellRunState;
  accent: string;
  reduceMotion: boolean | null;
}) {
  if (runState === 'guardrail_failed') {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-rose-400">
        Guardrail Failed
      </span>
    );
  }
  if (runState === 'replay') {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-[#8a8f98]">
        Replay
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.2em]"
      style={{ color: accent }}
    >
      <motion.span
        aria-hidden
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: accent }}
        animate={reduceMotion ? undefined : { opacity: [1, 0.3, 1] }}
        transition={reduceMotion ? undefined : { duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
      />
      Live
    </span>
  );
}

export const FortuneAgentResultShell: React.FC<FortuneAgentResultShellProps> = ({
  purpose,
  accentPrimary,
  glyph,
  kicker,
  headline,
  contextLine,
  kpis,
  statusPath,
  modelId,
  runState,
  tabs,
  activeTabId,
  onTabChange,
  onBack,
  rail,
  mobileChrome,
  children,
}) => {
  const reduceMotion = useReducedMotion();
  const obs = observatoryAccent(accentPrimary);
  const gradient = `radial-gradient(1200px 500px at 70% -10%, ${accentAlpha(accentPrimary, 0.07)}, transparent 60%), #0a0c10`;
  const tabDomId = (id: string) => `fortune-tab-${purpose}-${id.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
  const panelDomId = `fortune-panel-${purpose}`;

  const handleTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null;
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const nextTab = tabs[nextIndex];
    onTabChange(nextTab.id);
    document.getElementById(tabDomId(nextTab.id))?.focus();
  };

  return (
    <div
      className="relative min-h-screen overflow-x-hidden text-[#e8e6e1] selection:bg-white/20"
      style={{ background: gradient }}
    >
      {/* Oversized CJK watermark */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-8 -top-10 select-none text-[clamp(140px,28vw,280px)] font-black leading-none"
        style={{
          fontFamily: OBSERVATORY_SERIF,
          color: accentAlpha(accentPrimary, 0.05),
        }}
      >
        {glyph}
      </div>

      {/* ----- Status bar ----- */}
      <div
        className="sticky top-0 z-40 border-b border-white/[0.06] backdrop-blur-md"
        style={{
          background: 'rgba(10, 12, 16, 0.82)',
          paddingTop: 'env(safe-area-inset-top, 0px)',
        }}
      >
        <div className="mx-auto flex w-full max-w-[1100px] items-center justify-between gap-3 px-4 py-2.5">
          <div className="hidden min-w-0 items-center gap-2 sm:flex">
            <span
              className="truncate font-mono text-[10px] uppercase tracking-[0.18em] text-[#5fbf8f]/90"
              style={{ fontFamily: OBSERVATORY_MONO }}
              title={statusPath}
            >
              {statusPath}
              {modelId ? ` · ${modelId}` : ''}
            </span>
          </div>
          <div className="flex flex-1 items-center justify-end gap-3 sm:flex-none">
            <StateChip runState={runState} accent={obs.primary} reduceMotion={reduceMotion} />
            {onBack && (
              <button
                type="button"
                onClick={onBack}
                aria-label="Back"
                className="inline-flex h-8 items-center gap-1.5 rounded-full border px-2.5 text-[10px] font-bold uppercase tracking-[0.16em] transition-colors"
                style={{
                  borderColor: obs.softBorder,
                  color: obs.primary,
                  background: 'rgba(10,12,16,0.4)',
                }}
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Back</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ----- Body: main + optional rail ----- */}
      <div className="relative mx-auto grid w-full max-w-[1100px] grid-cols-1 gap-0 lg:grid-cols-[minmax(0,1fr)_300px]">
        <main
          className="min-w-0 px-4 pt-6"
          style={{
            paddingBottom: 'max(env(safe-area-inset-bottom, 0px) + 32px, 40px)',
          }}
        >
          {/* Kicker — glyph lives in the watermark; kicker already opens with the CJK title */}
          <div
            className="font-mono text-[10px] font-bold uppercase tracking-[0.35em]"
            style={{ color: obs.primary, fontFamily: OBSERVATORY_MONO }}
          >
            {kicker}
          </div>

          {/* Serif display headline */}
          <h1
            className="mt-2.5 max-w-3xl text-[clamp(22px,5vw,34px)] font-semibold leading-[1.15] text-[#f4e9c8]"
            style={{ fontFamily: OBSERVATORY_SERIF }}
          >
            {headline}
          </h1>

          {contextLine && (
            <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-[#8a8f98]">
              {contextLine}
            </p>
          )}

          {/* KPI band — 2×2 on mobile, 4-col on sm+ */}
          {kpis.length > 0 && (
            <motion.div
              className="mt-7 grid grid-cols-2 gap-3 sm:grid-cols-4"
              initial={reduceMotion ? false : { opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={
                reduceMotion
                  ? { duration: 0 }
                  : { duration: 0.45, staggerChildren: 0.06, delayChildren: 0.05 }
              }
            >
              {kpis.map((k) => (
                <motion.div
                  key={k.label}
                  className={OBS_KPI_CARD}
                  initial={reduceMotion ? false : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  <b className={OBS_KPI_VALUE}>{k.value}</b>
                  <span className={OBS_KPI_LABEL}>{k.label}</span>
                </motion.div>
              ))}
            </motion.div>
          )}

          {/* Pill tabs */}
          <nav
            role="tablist"
            aria-label={`${purpose} sections`}
            className="mt-7 flex flex-wrap gap-1 border-t border-white/[0.06] pt-4"
          >
            {tabs.map((t, index) => {
              const active = activeTabId === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  id={tabDomId(t.id)}
                  aria-controls={panelDomId}
                  aria-selected={active}
                  tabIndex={active ? 0 : -1}
                  onClick={() => onTabChange(t.id)}
                  onKeyDown={(event) => handleTabKeyDown(event, index)}
                  className={OBS_TAB}
                  style={
                    active
                      ? {
                          color: obs.primary,
                          borderColor: obs.tabBorder,
                          background: obs.tabBg,
                          fontFamily: OBSERVATORY_MONO,
                        }
                      : { fontFamily: OBSERVATORY_MONO }
                  }
                >
                  {t.label}
                </button>
              );
            })}
          </nav>

          {/* Mobile glass / pause chrome */}
          {mobileChrome && <div className="mt-5 lg:hidden">{mobileChrome}</div>}

          <div
            id={panelDomId}
            role="tabpanel"
            aria-labelledby={tabDomId(activeTabId)}
            tabIndex={0}
            className="mt-5"
          >
            {children}
          </div>
        </main>

        {/* Desktop execution-trace rail */}
        {rail && (
          <aside
            className="relative hidden border-l border-white/[0.06] lg:block"
            aria-label="Execution trace"
          >
            <div className="sticky top-[44px] max-h-[calc(100dvh-44px)] overflow-y-auto p-3">
              {rail}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
};
