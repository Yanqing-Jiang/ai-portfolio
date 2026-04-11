/**
 * MingResultsTabs — Tab shell for Ming Engine fortune results.
 *
 * Wraps the A2UISurface and controls which widgets are visible per tab.
 * Uses CSS data-attribute selectors on component IDs — no changes to the
 * A2UI rendering pipeline or backend.
 *
 * Tabs: Your Story (default) | Life Map | Forecast | Birth Chart
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Surface, DataModel } from './a2ui/types';
import { A2UISurface } from './renderer/A2UISurface';
import { HeroSummaryCard } from './HeroSummaryCard';
import { YearSpotlightCard, UpcomingYearsSwim } from './YearSpotlightCard';
import { CurrentCycleBanner } from './CurrentCycleBanner';
import { ElementRing } from './ElementRing';

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

interface TabDef {
    id: string;
    label: string;
    labelZh: string;
    icon: string;
}

const TABS: TabDef[] = [
    { id: 'story', label: 'Your Story', labelZh: '\u4F60\u7684\u547D', icon: '\uD83D\uDCD6' },
    { id: 'lifemap', label: 'Life Map', labelZh: '\u5927\u8FD0', icon: '\uD83D\uDDFA\uFE0F' },
    { id: 'forecast', label: 'Forecast', labelZh: '\u6D41\u5E74', icon: '\uD83D\uDD2E' },
    { id: 'chart', label: 'Birth Chart', labelZh: '\u516B\u5B57', icon: '\uD83E\uDDED' },
];

// Component IDs visible per tab. Everything else is hidden.
// Tab → visible component IDs. Everything else is hidden.
// NOTE: row_reading_citations contains fortune_reading_card (InsightAccordion)
// AND fortune_citations_card (CitationViewer). The parent row must be visible
// on any tab that shows either child. We then hide the unwanted child per-tab.
const TAB_COMPONENTS: Record<string, string[]> = {
    story: [
        'row_reading_citations',     // parent row — must be visible for InsightAccordion
        'fortune_reading_card',      // InsightAccordion
        'fortune_spooky_card',       // SpookyAccuracy
        'fortune_disclaimer_card',   // Disclaimer
    ],
    lifemap: [
        'fortune_timeline_card',
    ],
    forecast: [
        'fortune_actions_row',
    ],
    chart: [
        'kpi_row',
        'row_pillars_elements',
        'row_interactions_gods',
        'row_reading_citations',     // parent row — visible for CitationViewer
        'fortune_citations_card',    // CitationViewer
    ],
};

// All component IDs that should be managed by tabs
const ALL_MANAGED_IDS = [
    'kpi_row',
    'row_pillars_elements',
    'row_interactions_gods',
    'fortune_spooky_card',
    'fortune_timeline_card',
    'fortune_dag_card',
    'row_reading_citations',
    'fortune_actions_row',
    'fortune_disclaimer_card',
    'fortune_reading_card',
    'fortune_citations_card',
];

// ---------------------------------------------------------------------------
// CSS generation — hide/show components per tab
// ---------------------------------------------------------------------------

function generateTabCSS(): string {
    // Hide all managed components by default
    const hideRules = ALL_MANAGED_IDS.map(
        (id) => `[data-active-tab] [data-component-id="${id}"] { display: none !important; }`
    ).join('\n');

    // Show components for each tab
    const showRules = Object.entries(TAB_COMPONENTS).map(([tabId, ids]) =>
        ids.map(
            (id) => `[data-active-tab="${tabId}"] [data-component-id="${id}"] { display: block !important; }`
        ).join('\n')
    ).join('\n');

    // Always hide trace card in reading mode (inspector handles it)
    const traceRule = `[data-active-tab] [data-component-id="fortune_trace_card"] { display: none !important; }`;

    // Always hide dag card unless in inspector
    const dagRule = `[data-active-tab] [data-component-id="fortune_dag_card"] { display: none !important; }`;

    // Inspector override: when inspector mode is active, show everything
    const inspectorOverride = `.ming-inspector-mode [data-active-tab] [data-component-id] { display: block !important; }`;

    return [hideRules, showRules, traceRule, dagRule, inspectorOverride].join('\n\n');
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface MingResultsTabsProps {
    surface: Surface;
    dataModel: DataModel;
    onAction: (actionName: string, context: Record<string, unknown>) => void;
}

export function MingResultsTabs({ surface, dataModel, onAction }: MingResultsTabsProps) {
    // Read initial tab from URL hash
    const initialTab = useMemo(() => {
        const hash = window.location.hash.replace('#', '');
        return TABS.some((t) => t.id === hash) ? hash : 'story';
    }, []);

    const [activeTab, setActiveTab] = useState(initialTab);

    // Persist tab in URL hash
    const handleTabChange = useCallback((tabId: string) => {
        setActiveTab(tabId);
        window.history.replaceState(null, '', `#${tabId}`);
    }, []);

    // Listen for hash changes (back/forward)
    useEffect(() => {
        const onHashChange = () => {
            const hash = window.location.hash.replace('#', '');
            if (TABS.some((t) => t.id === hash)) {
                setActiveTab(hash);
            }
        };
        window.addEventListener('hashchange', onHashChange);
        return () => window.removeEventListener('hashchange', onHashChange);
    }, []);

    const tabCSS = useMemo(() => generateTabCSS(), []);

    return (
        <>
            <style>{tabCSS}</style>

            {/* Desktop top tabs (>= 768px) */}
            <div className="hidden md:block mb-4">
                <div className="flex gap-1 border-b border-slate-700/50">
                    {TABS.map((tab) => {
                        const isActive = tab.id === activeTab;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => handleTabChange(tab.id)}
                                className="relative px-4 py-3 text-sm font-medium transition-colors"
                                style={{
                                    color: isActive ? 'var(--ming-gold, #eab308)' : '#94a3b8',
                                }}
                            >
                                <span className="mr-1.5">{tab.icon}</span>
                                {tab.label}
                                {isActive && (
                                    <motion.div
                                        layoutId="tab-underline"
                                        className="absolute bottom-0 left-0 right-0 h-0.5"
                                        style={{ background: 'var(--ming-gold, #eab308)' }}
                                        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                                    />
                                )}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Tab content with crossfade */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={activeTab}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                >
                    {/* Tab-specific injected components (not in A2UI tree) */}
                    {activeTab === 'story' && (
                        <div className="mb-5">
                            <HeroSummaryCard dataModel={dataModel as Record<string, unknown>} />
                        </div>
                    )}
                    {activeTab === 'lifemap' && (
                        <CurrentCycleBanner dataModel={dataModel as Record<string, unknown>} />
                    )}
                    {activeTab === 'forecast' && (
                        <div className="space-y-5">
                            <YearSpotlightCard dataModel={dataModel as Record<string, unknown>} />
                            <UpcomingYearsSwim dataModel={dataModel as Record<string, unknown>} />
                        </div>
                    )}
                    {activeTab === 'chart' && (
                        <div className="flex justify-center mb-5">
                            <ElementRing dataModel={dataModel as Record<string, unknown>} />
                        </div>
                    )}

                    {/* A2UI Surface — always rendered, CSS controls visibility */}
                    <div data-active-tab={activeTab}>
                        <A2UISurface
                            surface={surface}
                            dataModel={dataModel}
                            onAction={onAction}
                        />
                    </div>
                </motion.div>
            </AnimatePresence>

            {/* Mobile bottom tab bar (< 768px) */}
            <div
                className="fixed bottom-0 inset-x-0 z-40 flex md:hidden"
                style={{
                    height: 56,
                    background: 'rgba(12, 10, 20, 0.95)',
                    borderTop: '1px solid rgba(148, 163, 184, 0.12)',
                    backdropFilter: 'blur(12px)',
                    WebkitBackdropFilter: 'blur(12px)',
                }}
            >
                {TABS.map((tab) => {
                    const isActive = tab.id === activeTab;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => handleTabChange(tab.id)}
                            className="flex flex-1 flex-col items-center justify-center gap-0.5 transition-all"
                            style={{
                                color: isActive ? 'var(--ming-gold, #eab308)' : '#64748b',
                                transform: isActive ? 'scale(1.05)' : 'scale(1)',
                            }}
                        >
                            <span className="text-lg leading-none">{tab.icon}</span>
                            <span className="text-[10px] font-medium">{tab.label}</span>
                        </button>
                    );
                })}
            </div>

            {/* Bottom spacer for mobile tab bar */}
            <div className="h-16 md:hidden" />
        </>
    );
}
