/**
 * FortuneResultShell — ONE config-driven result page for all 4 functions.
 * Replaces FortuneAgent{CustomWish,Cycle,Compatibility,Occasion}Result wrappers.
 */
import React, { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { useLocation } from 'react-router-dom';
import {
  FortuneAgentResultShell,
} from './FortuneAgentResultShell';
import { useFortuneSession } from './hooks/useFortuneSession';
import { ThinkingPanel } from './fortune/ThinkingPanel';
import { AskTab } from './fortune/shared/AskTab';
import { WhyTab } from './fortune/shared/WhyTab';
import { FORTUNE_RESULT_CONFIG } from './fortune/shell/resultConfig';
import type { CanonicalFortuneFunction } from '../../lib/fortuneRoutes';

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
): React.ReactNode {
  if (functionId === 'wish') {
    if (activeTab === 'Verdict') return <VerdictTab isReplay={isReplay} question={question} />;
    if (activeTab === 'Anchor') return <AnchorTab isReplay={isReplay} />;
    if (activeTab === 'Why') return <WhyTab functionId="wish" isReplay={isReplay} />;
    if (activeTab === 'Ask') return <AskTab functionId="wish" question={question} />;
  }
  if (functionId === 'cycle') {
    if (activeTab === 'Now') return <NowTab isReplay={isReplay} />;
    if (activeTab === 'Timeline') return <TimelineTab isReplay={isReplay} />;
    if (activeTab === 'Why') return <WhyTab functionId="cycle" isReplay={isReplay} />;
    if (activeTab === 'Ask') return <AskTab functionId="cycle" />;
  }
  if (functionId === 'compatibility') {
    if (activeTab === 'Overview') return <OverviewTab isReplay={isReplay} />;
    if (activeTab === 'Pillars') return <PillarsTab isReplay={isReplay} />;
    if (activeTab === 'Why') return <WhyTab functionId="compatibility" isReplay={isReplay} />;
    if (activeTab === 'Ask') return <AskTab functionId="compatibility" />;
  }
  if (functionId === 'occasion') {
    if (activeTab === 'TopPicks') return <TopPicksTab isReplay={isReplay} />;
    if (activeTab === 'Calendar') return <CalendarTab isReplay={isReplay} />;
    if (activeTab === 'Why') return <WhyTab functionId="occasion" isReplay={isReplay} />;
    if (activeTab === 'Ask') return <AskTab functionId="occasion" />;
  }
  return null;
}

export const FortuneResultShell: React.FC<FortuneResultShellProps> = ({
  functionId,
  onBack,
}) => {
  const config = FORTUNE_RESULT_CONFIG[functionId];
  const [activeTab, setActiveTab] = useState(config.defaultTab);
  const { state } = useLocation();
  const question = (state as { question?: string } | null)?.question;

  const session = useFortuneSession({
    functionId: config.sessionFunctionId,
    baseRoute: config.baseRoute,
  });

  const { isReplay, status, error, dataModel, cancel, pausing } = session;
  const thinkingStatus: 'streaming' | 'complete' =
    status === 'complete' ? 'complete' : 'streaming';

  const subtitle =
    functionId === 'wish' ? question : config.subtitle;

  return (
    <FortuneAgentResultShell
      purpose={config.purpose}
      eyebrow={config.eyebrow}
      subtitle={subtitle}
      tabs={config.tabs}
      activeTabId={activeTab}
      onTabChange={setActiveTab}
      onBack={onBack}
    >
      {!error && (
        <ThinkingPanel
          purpose={config.purpose}
          dataModel={dataModel as Record<string, unknown> | null}
          status={thinkingStatus}
          onPause={cancel}
          paused={pausing}
          showCompletedDock={true}
        />
      )}

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
          {renderFunctionTab(functionId, activeTab, isReplay, question)}
        </AnimatePresence>
      )}
    </FortuneAgentResultShell>
  );
};
