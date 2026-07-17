/**
 * FortuneResultShell — ONE config-driven result page for all 4 functions.
 * Phase 5: Observatory chrome + desktop Glass Box rail.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { useLocation, useSearchParams } from 'react-router-dom';
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
import { FLOW_ACCENTS } from './fortune/designTokens';
import {
  FORTUNE_RESULT_CONFIG,
  buildResultHeadline,
  buildResultKpis,
  readModelId,
  shortFortuneId,
} from './fortune/shell/resultConfig';
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

function renderFunctionTab(
  functionId: CanonicalFortuneFunction,
  activeTab: string,
  isReplay: boolean,
  question?: string,
  askContext?: AskContext,
  askReady?: boolean,
): React.ReactNode {
  if (functionId === 'wish') {
    if (activeTab === 'Verdict') return <VerdictTab isReplay={isReplay} question={question} />;
    if (activeTab === 'Anchor') return <AnchorTab isReplay={isReplay} />;
    if (activeTab === 'Why') return <WhyTab functionId="wish" isReplay={isReplay} />;
    if (activeTab === 'Ask') return <AskTab functionId="wish" question={question} context={askContext} ready={askReady} />;
  }
  if (functionId === 'cycle') {
    if (activeTab === 'Now') return <NowTab isReplay={isReplay} />;
    if (activeTab === 'Timeline') return <TimelineTab isReplay={isReplay} />;
    if (activeTab === 'Why') return <WhyTab functionId="cycle" isReplay={isReplay} />;
    if (activeTab === 'Ask') return <AskTab functionId="cycle" context={askContext} ready={askReady} />;
  }
  if (functionId === 'compatibility') {
    if (activeTab === 'Overview') return <OverviewTab isReplay={isReplay} />;
    if (activeTab === 'Pillars') return <PillarsTab isReplay={isReplay} />;
    if (activeTab === 'Why') return <WhyTab functionId="compatibility" isReplay={isReplay} />;
    if (activeTab === 'Ask') return <AskTab functionId="compatibility" context={askContext} ready={askReady} />;
  }
  if (functionId === 'occasion') {
    if (activeTab === 'TopPicks') return <TopPicksTab isReplay={isReplay} />;
    if (activeTab === 'Calendar') return <CalendarTab isReplay={isReplay} />;
    if (activeTab === 'Why') return <WhyTab functionId="occasion" isReplay={isReplay} />;
    if (activeTab === 'Ask') return <AskTab functionId="occasion" context={askContext} ready={askReady} />;
  }
  return null;
}

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
  guardrailSeverity?: string | null;
}): ShellRunState {
  const sev = (opts.guardrailSeverity || '').toLowerCase();
  if (sev === 'error' || sev === 'failed' || sev === 'reject' || sev === 'rejected') {
    return 'guardrail_failed';
  }
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

  const guardrail = dataModel?.guardrail;
  const runState = resolveRunState({
    isReplay,
    status,
    guardrailSeverity: guardrail?.severity || guardrail?.level || null,
  });

  const statusPath = `fortune://${config.canonicalId}/${shortFortuneId(fortuneId)}`;
  const isLg = useIsLg();
  const askContext: AskContext = {
    sectionId: TAB_SECTION_IDS[lastContentTab] || TAB_SECTION_IDS[config.defaultTab],
    sectionLabel: config.tabs.find((tab) => tab.id === lastContentTab)?.label || lastContentTab,
  };
  const askReady = status === 'complete';

  const pauseBar =
    status === 'streaming' ? (
      <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2">
        <span className="text-[11px] text-slate-400">Reading in progress…</span>
        <button
          type="button"
          onClick={cancel}
          disabled={pausing}
          className="text-[11px] font-semibold text-slate-300 hover:text-white disabled:opacity-50"
        >
          {pausing ? 'Pausing…' : 'Pause'}
        </button>
      </div>
    ) : null;

  // Single GlassBox instance — rail on ≥lg, inline drawer below.
  const glass = !error ? (
    <div className="space-y-3">
      <GlassBoxPanel accent={accent.primary} variant={isLg ? 'rail' : 'inline'} />
      <MemoryPanel />
      {pauseBar}
    </div>
  ) : null;

  const mobileChrome = isLg ? null : glass;
  const rail = isLg ? glass : null;

  return (
    <FortuneAgentResultShell
      purpose={config.purpose}
      accentPrimary={accent.primary}
      glyph={config.glyph}
      kicker={kicker}
      headline={headline}
      contextLine={contextLine}
      kpis={kpis}
      statusPath={statusPath}
      modelId={modelId}
      runState={runState}
      tabs={config.tabs}
      activeTabId={activeTab}
      onTabChange={handleTabChange}
      onBack={onBack}
      rail={rail}
      mobileChrome={mobileChrome}
    >
      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-center text-sm text-red-400">
          {error}
        </div>
      )}

      {status === 'loading' && !session.dataModel && (
        <div className="flex flex-col items-center gap-3 py-12">
          <div
            className={`h-8 w-8 animate-spin rounded-full border-2 ${config.spinnerClass}`}
          />
          <div className="text-xs text-slate-400">{config.loadingMessage}</div>
        </div>
      )}

      {(status !== 'loading' || session.dataModel) && !error && (
        <AnimatePresence mode="wait">
          {renderFunctionTab(
            functionId,
            activeTab,
            isReplay,
            question,
            askContext,
            askReady,
          )}
        </AnimatePresence>
      )}
    </FortuneAgentResultShell>
  );
};
