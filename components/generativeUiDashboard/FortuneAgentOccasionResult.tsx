/**
 * FortuneAgentOccasionResult — 擇 Lucky Day / Occasion reading.
 *
 * Connected to backend via useFortuneSession.
 * Tabs: Top Picks · Calendar · Why · Ask
 */

import React, { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import {
    FortuneAgentResultShell,
    type FortuneTab,
} from './FortuneAgentResultShell';
import { useFortuneSession } from './hooks/useFortuneSession';
import { TopPicksTab } from './fortune/occasion/TopPicksTab';
import { CalendarTab } from './fortune/occasion/CalendarTab';
import { WhyTab } from './fortune/occasion/WhyTab';
import { AskTab } from './fortune/occasion/AskTab';

interface FortuneAgentOccasionResultProps {
    onBack?: () => void;
    inputPayload?: Record<string, unknown> | null;
}

const TABS: FortuneTab[] = [
    { id: 'TopPicks', label: 'Top Picks' },
    { id: 'Calendar', label: 'Calendar' },
    { id: 'Why', label: 'Why' },
    { id: 'Ask', label: 'Ask' },
];

export const FortuneAgentOccasionResult: React.FC<FortuneAgentOccasionResultProps> = ({
    onBack,
}) => {
    const [activeTab, setActiveTab] = useState('TopPicks');

    const session = useFortuneSession({
        functionId: 'lucky-day',
        baseRoute: '/project/fortune-agent/lucky-day',
    });

    const { isReplay, status, error } = session;

    return (
        <FortuneAgentResultShell
            purpose="lucky-day"
            eyebrow="Occasion"
            subtitle="擇日 · Auspicious Date"
            tabs={TABS}
            activeTabId={activeTab}
            onTabChange={setActiveTab}
            onBack={onBack}
        >
            {error && (
                <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-center text-sm text-red-400">
                    {error}
                </div>
            )}

            {status === 'loading' && !session.dataModel && (
                <div className="flex flex-col items-center gap-3 py-12">
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500/30 border-t-amber-500" />
                    <div className="text-xs text-slate-400">Finding auspicious dates...</div>
                </div>
            )}

            {(status !== 'loading' || session.dataModel) && !error && (
                <AnimatePresence mode="wait">
                    {activeTab === 'TopPicks' && <TopPicksTab isReplay={isReplay} />}
                    {activeTab === 'Calendar' && <CalendarTab isReplay={isReplay} />}
                    {activeTab === 'Why' && <WhyTab isReplay={isReplay} />}
                    {activeTab === 'Ask' && <AskTab />}
                </AnimatePresence>
            )}
        </FortuneAgentResultShell>
    );
};
