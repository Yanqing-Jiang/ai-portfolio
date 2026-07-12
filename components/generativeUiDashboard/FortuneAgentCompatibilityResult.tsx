/**
 * FortuneAgentCompatibilityResult — 緣 Compatibility reading.
 *
 * Connected to backend via useFortuneSession.
 * Tabs: Overview · Pillars · Why · Ask
 */

import React, { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import {
    FortuneAgentResultShell,
    type FortuneTab,
} from './FortuneAgentResultShell';
import { useFortuneSession } from './hooks/useFortuneSession';
import { OverviewTab } from './fortune/compatibility/OverviewTab';
import { PillarsTab } from './fortune/compatibility/PillarsTab';
import { WhyTab } from './fortune/compatibility/WhyTab';
import { AskTab } from './fortune/compatibility/AskTab';
import { ThinkingPanel } from './fortune/ThinkingPanel';

interface FortuneAgentCompatibilityResultProps {
    onBack?: () => void;
    inputPayload?: Record<string, unknown> | null;
}

const TABS: FortuneTab[] = [
    { id: 'Overview', label: 'Overview' },
    { id: 'Pillars', label: 'Pillars' },
    { id: 'Why', label: 'Why' },
    { id: 'Ask', label: 'Ask' },
];

export const FortuneAgentCompatibilityResult: React.FC<FortuneAgentCompatibilityResultProps> = ({
    onBack,
}) => {
    const [activeTab, setActiveTab] = useState('Overview');

    const session = useFortuneSession({
        functionId: 'compatibility',
        baseRoute: '/project/fortune-agent/compatibility',
    });

    const { isReplay, status, error, dataModel, cancel, pausing } = session;
    const thinkingStatus: 'streaming' | 'complete' =
        status === 'complete' ? 'complete' : 'streaming';

    return (
        <FortuneAgentResultShell
            purpose="compatibility"
            eyebrow="Compatibility"
            subtitle="兩命 · Two Charts"
            tabs={TABS}
            activeTabId={activeTab}
            onTabChange={setActiveTab}
            onBack={onBack}
        >
            {!error && (
                <ThinkingPanel
                    purpose="compatibility"
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
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-rose-500/30 border-t-rose-500" />
                    <div className="text-xs text-slate-400">Comparing your charts...</div>
                </div>
            )}

            {(status !== 'loading' || session.dataModel) && !error && (
                <AnimatePresence mode="wait">
                    {activeTab === 'Overview' && <OverviewTab isReplay={isReplay} />}
                    {activeTab === 'Pillars' && <PillarsTab isReplay={isReplay} />}
                    {activeTab === 'Why' && <WhyTab isReplay={isReplay} />}
                    {activeTab === 'Ask' && <AskTab />}
                </AnimatePresence>
            )}
        </FortuneAgentResultShell>
    );
};
