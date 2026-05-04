/**
 * FortuneAgentCustomWishResult — 問 Custom Wish reading.
 *
 * Now connected to the backend via useFortuneSession.
 * Falls back to the old mock UI when no fortuneId is in the URL
 * (legacy /result?q= route).
 *
 * Tabs: Verdict · Anchor · Why · Ask
 */

import React, { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';
import {
    FortuneAgentResultShell,
    type FortuneTab,
} from './FortuneAgentResultShell';
import { useFortuneSession } from './hooks/useFortuneSession';
import { VerdictTab } from './fortune/wish/VerdictTab';
import { AnchorTab } from './fortune/wish/AnchorTab';
import { WhyTab } from './fortune/wish/WhyTab';
import { AskTab } from './fortune/wish/AskTab';
import { ThinkingPanel } from './fortune/ThinkingPanel';

interface FortuneAgentCustomWishResultProps {
    onBack?: () => void;
    initialQuestion?: string;
}

const TABS: FortuneTab[] = [
    { id: 'Verdict', label: 'Verdict' },
    { id: 'Anchor', label: 'Anchor' },
    { id: 'Why', label: 'Why' },
    { id: 'Ask', label: 'Ask' },
];

export const FortuneAgentCustomWishResult: React.FC<FortuneAgentCustomWishResultProps> = ({
    onBack,
    initialQuestion,
}) => {
    const [activeTab, setActiveTab] = useState('Verdict');
    const [searchParams] = useSearchParams();

    // Support both new /:fortuneId routes and legacy /result?q= routes
    const question = initialQuestion || searchParams.get('q') || undefined;

    const session = useFortuneSession({
        functionId: 'wish',
        baseRoute: '/project/fortune-agent/custom-wish',
    });

    const { isReplay, status, error, dataModel, cancel, pausing } = session;
    const thinkingStatus: 'streaming' | 'complete' =
        status === 'complete' ? 'complete' : 'streaming';

    return (
        <FortuneAgentResultShell
            purpose="custom-wish"
            eyebrow="Custom Wish"
            subtitle={question}
            tabs={TABS}
            activeTabId={activeTab}
            onTabChange={setActiveTab}
            onBack={onBack}
        >
            {!error && (
                <ThinkingPanel
                    purpose="custom-wish"
                    dataModel={dataModel as Record<string, unknown> | null}
                    status={thinkingStatus}
                    onPause={cancel}
                    paused={pausing}
                />
            )}

            {/* Error state */}
            {error && (
                <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-center text-sm text-red-400">
                    {error}
                </div>
            )}

            {/* Loading skeleton when no data yet */}
            {status === 'loading' && !session.dataModel && (
                <div className="flex flex-col items-center gap-3 py-12">
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-500" />
                    <div className="text-xs text-slate-400">Preparing your reading...</div>
                </div>
            )}

            {/* Tab content */}
            {(status !== 'loading' || session.dataModel) && !error && (
                <AnimatePresence mode="wait">
                    {activeTab === 'Verdict' && <VerdictTab isReplay={isReplay} question={question} />}
                    {activeTab === 'Anchor' && <AnchorTab isReplay={isReplay} />}
                    {activeTab === 'Why' && <WhyTab isReplay={isReplay} />}
                    {activeTab === 'Ask' && <AskTab question={question} />}
                </AnimatePresence>
            )}
        </FortuneAgentResultShell>
    );
};
