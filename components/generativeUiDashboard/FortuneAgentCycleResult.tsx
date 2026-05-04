/**
 * FortuneAgentCycleResult — 運 Cycle Reading (year/month luck timeline).
 *
 * Now connected to backend via useFortuneSession.
 * Tabs: Now · Timeline · Why · Ask
 */

import React, { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import {
    FortuneAgentResultShell,
    type FortuneTab,
} from './FortuneAgentResultShell';
import { useFortuneSession } from './hooks/useFortuneSession';
import { NowTab } from './fortune/luck/NowTab';
import { TimelineTab } from './fortune/luck/TimelineTab';
import { WhyTab } from './fortune/luck/WhyTab';
import { AskTab } from './fortune/luck/AskTab';
import { ThinkingPanel } from './fortune/ThinkingPanel';

interface FortuneAgentCycleResultProps {
    onBack?: () => void;
    inputPayload?: Record<string, unknown> | null;
}

const TABS: FortuneTab[] = [
    { id: 'Now', label: 'Now' },
    { id: 'Timeline', label: 'Timeline' },
    { id: 'Why', label: 'Why' },
    { id: 'Ask', label: 'Ask' },
];

export const FortuneAgentCycleResult: React.FC<FortuneAgentCycleResultProps> = ({
    onBack,
}) => {
    const [activeTab, setActiveTab] = useState('Now');

    const session = useFortuneSession({
        functionId: 'luck-cycle',
        baseRoute: '/project/fortune-agent/luck-draw',
    });

    const { isReplay, status, error, dataModel, cancel, pausing } = session;
    const thinkingStatus: 'streaming' | 'complete' =
        status === 'complete' ? 'complete' : 'streaming';

    return (
        <FortuneAgentResultShell
            purpose="luck-draw"
            eyebrow="Cycle Reading"
            subtitle="運勢 · Year & Month"
            tabs={TABS}
            activeTabId={activeTab}
            onTabChange={setActiveTab}
            onBack={onBack}
        >
            {!error && (
                <ThinkingPanel
                    purpose="luck-draw"
                    dataModel={dataModel as Record<string, unknown> | null}
                    status={thinkingStatus}
                    onPause={cancel}
                    paused={pausing}
                />
            )}

            {error && (
                <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-center text-sm text-red-400">
                    {error}
                </div>
            )}

            {status === 'loading' && !session.dataModel && (
                <div className="flex flex-col items-center gap-3 py-12">
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
                    <div className="text-xs text-slate-400">Calculating your cycles...</div>
                </div>
            )}

            {(status !== 'loading' || session.dataModel) && !error && (
                <AnimatePresence mode="wait">
                    {activeTab === 'Now' && <NowTab isReplay={isReplay} />}
                    {activeTab === 'Timeline' && <TimelineTab isReplay={isReplay} />}
                    {activeTab === 'Why' && <WhyTab isReplay={isReplay} />}
                    {activeTab === 'Ask' && <AskTab />}
                </AnimatePresence>
            )}
        </FortuneAgentResultShell>
    );
};
