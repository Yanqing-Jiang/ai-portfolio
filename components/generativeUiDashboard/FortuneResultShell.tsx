/**
 * FortuneResultShell — ONE config-driven result page for all 4 functions.
 * Phase 5: Observatory chrome + desktop Glass Box rail.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useShallow } from 'zustand/react/shallow';
import {
  FortuneAgentResultShell,
  type ShellRunState,
} from './FortuneAgentResultShell';
import { useFortuneSession } from './hooks/useFortuneSession';
import { useConversationHydration } from './hooks/useFortuneAsk';
import { useFortuneStore } from './stores/fortuneStore';
import { GlassBoxPanel } from './fortune/shared/GlassBoxPanel';
import { MemoryPanel } from './fortune/shared/MemoryPanel';
import { AskTab } from './fortune/shared/AskTab';
import { WhyTab } from './fortune/shared/WhyTab';
import { HarnessView } from './fortune/shared/HarnessView';
import { ReadingErrorCard } from './fortune/shared/ReadingErrorCard';
import { FLOW_ACCENTS } from './fortune/designTokens';
import {
  FORTUNE_RESULT_CONFIG,
  buildResultHeadline,
  buildResultKpis,
  buildReadingStatus,
  readModelId,
  shortFortuneId,
} from './fortune/shell/resultConfig';
import { detectReadingFailure } from './fortune/shell/readingStatus';
import type { CanonicalFortuneFunction } from '../../lib/fortuneRoutes';
import type { AskContext, AskSectionId } from './lib/fortuneTypes';

import { VerdictTab } from './fortune/wish/VerdictTab';
import { AnchorTab } from './fortune/wish/AnchorTab';
import { NowTab } from './fortune/luck/NowTab';
import { TimelineTab } from './fortune/luck/TimelineTab';
import { OverviewTab } from './fortune/compatibility/OverviewTab';
import { PillarsTab } from './fortune/compatibility/PillarsTab';
import { TopPicksTab } from './fortune/occasion/TopPicksTab';
import { CalendarTab } from './fortune/occasion/CalendarTab';

export interface FortuneResultShellProps {
  functionId: CanonicalFortuneFunction;
  onBack?: () => void;
}

interface FunctionTabProps {
  functionId: CanonicalFortuneFunction;
  activeTab: string;
  isReplay: boolean;
  failed: boolean;
  question?: string;
  askContext?: AskContext;
  askReady?: boolean;
  askDisabledReason?: string;
  onTabChange: (id: string) => void;
}

function renderFunctionTab({
  functionId,
  activeTab,
  isReplay,
  failed,
  question,
  askContext,
  askReady,
  askDisabledReason,
  onTabChange,
}: FunctionTabProps): React.ReactNode {
  if (failed && activeTab === FORTUNE_RESULT_CONFIG[functionId].defaultTab) return null;
  const ask = (id: CanonicalFortuneFunction) => (
    <AskTab
      functionId={id}
      question={id === 'wish' ? question : undefined}
      context={askContext}
      ready={askReady}
      disabledReason={askDisabledReason}
    />
  );
  if (activeTab === 'Why') return (
    <HarnessView accent={FLOW_ACCENTS[FORTUNE_RESULT_CONFIG[functionId].sessionFunctionId].primary}>
      <WhyTab functionId={functionId} isReplay={isReplay} />
    </HarnessView>
  );
  if (functionId === 'wish') {
    if (activeTab === 'Verdict') return <VerdictTab isReplay={isReplay} failed={failed} onTabChange={onTabChange} />;
    if (activeTab === 'Anchor') return <AnchorTab isReplay={isReplay} />;
    if (activeTab === 'Ask') return ask('wish');
  }
  if (functionId === 'cycle') {
    if (activeTab === 'Now') return <NowTab isReplay={isReplay} onTabChange={onTabChange} />;
    if (activeTab === 'Timeline') return <TimelineTab isReplay={isReplay} />;
    if (activeTab === 'Ask') return ask('cycle');
  }
  if (functionId === 'compatibility') {
    if (activeTab === 'Overview') return <OverviewTab isReplay={isReplay} onTabChange={onTabChange} />;
    if (activeTab === 'Pillars') return <PillarsTab isReplay={isReplay} />;
    if (activeTab === 'Ask') return ask('compatibility');
  }
  if (functionId === 'occasion') {
    if (activeTab === 'TopPicks') return <TopPicksTab isReplay={isReplay} onTabChange={onTabChange} />;
    if (activeTab === 'Calendar') return <CalendarTab isReplay={isReplay} />;
    if (activeTab === 'Ask') return ask('occasion');
  }
  return null;
}

/** Explorer selection is only meaningful inside Why; drop it when leaving. */
const EXPLORER_PARAMS = ['view', 'finding', 'palace', 'person'] as const;

const TAB_SECTION_IDS: Record<string, AskSectionId> = {
  Verdict: 'verdict',
  Anchor: 'anchor',
  Why: 'why',
  Now: 'now',
  Timeline: 'timeline',
  Overview: 'overview',
  Pillars: 'pillars',
  TopPicks: 'top_picks',
  Calendar: 'calendar',
};


function useIsLg(): boolean {
  const [isLg, setIsLg] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(min-width: 1024px)');
    const update = () => setIsLg(mq.matches);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);
  return isLg;
}

function resolveRunState(opts: {
  isReplay: boolean;
  status: string;
  failureKind?: 'failed' | 'rejected' | null;
}): ShellRunState {
  if (opts.failureKind === 'rejected') return 'guardrail_failed';
  if (opts.failureKind === 'failed') return 'failed';
  if (opts.isReplay && opts.status !== 'streaming' && opts.status !== 'loading') {
    return 'replay';
  }
  if (opts.status === 'streaming' || opts.status === 'loading') {
    return 'live';
  }
  return opts.isReplay ? 'replay' : 'live';
}

export const FortuneResultShell: React.FC<FortuneResultShellProps> = ({
  functionId,
  onBack,
}) => {
  const config = FORTUNE_RESULT_CONFIG[functionId];
  const { state } = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get('tab');
  const initialTab = config.tabs.some((tab) => tab.id === requestedTab)
    ? requestedTab as string
    : config.defaultTab;
  const [activeTab, setActiveTab] = useState(initialTab);
  const [lastContentTab, setLastContentTab] = useState(
    initialTab === 'Ask' ? config.defaultTab : initialTab,
  );
  const question = (state as { question?: string } | null)?.question;

  useEffect(() => {
    const nextTab = requestedTab && config.tabs.some((tab) => tab.id === requestedTab)
      ? requestedTab
      : config.defaultTab;
    setActiveTab(nextTab);
    if (nextTab !== 'Ask') setLastContentTab(nextTab);
  }, [requestedTab, config.tabs]);

  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
    if (tabId !== 'Ask') setLastContentTab(tabId);
    const next = new URLSearchParams(searchParams);
    if (tabId === config.defaultTab) next.delete('tab');
    else next.set('tab', tabId);
    // Leaving Why drops the explorer selection so returning later doesn't
    // reopen a stale finding/palace for a different part of the reading.
    if (activeTab === 'Why' && tabId !== 'Why') {
      EXPLORER_PARAMS.forEach((key) => next.delete(key));
    }
    setSearchParams(next, { replace: true });
  };

  const session = useFortuneSession({
    functionId: config.sessionFunctionId,
    baseRoute: config.baseRoute,
  });

  const { isReplay, status, error, cancel, pausing, fortuneId } = session;
  useConversationHydration(fortuneId);
  const dataModel = useFortuneStore(useShallow((s) => s.dataModel));

  const accent = FLOW_ACCENTS[config.sessionFunctionId];
  const modelId = readModelId(dataModel);
  const kpis = useMemo(
    () => buildResultKpis(functionId, dataModel),
    [functionId, dataModel],
  );
  const headline = useMemo(
    () => buildResultHeadline(functionId, dataModel, config.eyebrow),
    [functionId, dataModel, config.eyebrow],
  );

  const contextLine =
    functionId === 'wish' ? question || config.subtitle : config.subtitle;

  const occasionType = dataModel?.occasion?.analysis?.occasionType;
  const kicker =
    functionId === 'occasion' && occasionType
      ? `${config.cjkTitle} · ${config.functionLabel} — ${occasionType}`
      : `${config.cjkTitle} · ${config.functionLabel}`;

  const failure = useMemo(
    () => detectReadingFailure({ status, dataModel, sessionError: error }),
    [status, dataModel, error],
  );
  const failed = !!failure;
  const runState = resolveRunState({
    isReplay,
    status,
    failureKind: failure?.kind ?? null,
  });

  const statusPath = `fortune://${config.canonicalId}/${shortFortuneId(fortuneId)}`;
  const readerLine = buildReadingStatus(functionId, dataModel);
  const isLg = useIsLg();
  const askContext: AskContext = {
    sectionId: TAB_SECTION_IDS[lastContentTab] || TAB_SECTION_IDS[config.defaultTab],
    sectionLabel: config.tabs.find((tab) => tab.id === lastContentTab)?.label || lastContentTab,
  };
  const askReady = status === 'complete' && !failed;
  const askDisabledReason = failed
    ? 'This reading did not finish, so follow-up questions are unavailable.'
    : undefined;

  // A failed run is terminal: no pause affordance, no spinner, no "in progress".
  const pauseBar =
    status === 'streaming' && !failed ? (
      <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2">
        <span className="text-[11px] text-slate-400">Reading in progress…</span>
        <button
          type="button"
          onClick={cancel}
          disabled={pausing}
          className="min-h-11 text-[11px] font-semibold text-slate-300 hover:text-white disabled:opacity-50"
        >
          {pausing ? 'Pausing…' : 'Pause'}
        </button>
      </div>
    ) : null;

  const restart = () => navigate(config.baseRoute, { state: null });

  const errorCard = failure ? (
    <ReadingErrorCard
      failure={failure}
      onRestart={restart}
      hasPartialContent={!!dataModel?.harness?.charts?.personA || !!dataModel?.pillars}
    />
  ) : null;

  // Single GlassBox instance — rail on ≥lg, below the reading on mobile.
  const glass = (
    <div className="space-y-3">
      <GlassBoxPanel
        accent={accent.primary}
        variant={isLg ? 'rail' : 'inline'}
        statusPath={statusPath}
        modelId={modelId}
      />
      <MemoryPanel />
    </div>
  );

  return (
    <FortuneAgentResultShell
      purpose={config.purpose}
      accentPrimary={accent.primary}
      glyph={config.glyph}
      kicker={kicker}
      headline={failed && !dataModel?.narrative?.tldr ? 'Reading not completed' : headline}
      contextLine={contextLine}
      readerLine={readerLine}
      kpis={failed ? [] : kpis}
      runState={runState}
      tabs={config.tabs}
      activeTabId={activeTab}
      onTabChange={handleTabChange}
      onBack={onBack}
      rail={isLg ? glass : null}
      mobileChrome={pauseBar || errorCard ? (
        <div className="space-y-3">
          {errorCard}
          {pauseBar}
        </div>
      ) : null}
      telemetry={isLg ? null : glass}
    >
      {status === 'loading' && !session.dataModel && !failed && (
        <div className="flex flex-col items-center gap-3 py-10">
          <div
            className={`h-8 w-8 animate-spin rounded-full border-2 ${config.spinnerClass}`}
          />
          <div className="text-xs text-slate-400">{config.loadingMessage}</div>
        </div>
      )}

      {/* A failure with nothing saved shows only the recovery card. */}
      {(status !== 'loading' || session.dataModel) && (!failed || !!session.dataModel) && (
        <AnimatePresence mode="wait">
          {renderFunctionTab({
            functionId,
            activeTab,
            isReplay,
            failed,
            question,
            askContext,
            askReady,
            askDisabledReason,
            onTabChange: handleTabChange,
          })}
        </AnimatePresence>
      )}
    </FortuneAgentResultShell>
  );
};
