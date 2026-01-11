// --- Function/Class Map ---
// Component: FollowUpSuggestions
//   Role: Render follow-up suggestion chips with loading, empty states, and anomaly alerts.
//   Called from: components/generativeUiDashboard/GenerativeUIPage.tsx
//   Invokes: onSelect callbacks, framer-motion animations, AnomalyAlert component
//   Why: Keeps the analysis flow conversational with guided next steps and proactive insights.
// Function: getSuggestionIcon
//   Role: Resolve the icon displayed for a suggestion pill.
//   Called from: FollowUpSuggestions render loop.
//   Invokes: ICONS lookup.
//   Why: Keeps icon fallback behavior consistent.
// Function: getPriorityStyles
//   Role: Apply visual emphasis for high-priority suggestions.
//   Called from: FollowUpSuggestions render loop.
//   Invokes: n/a.
//   Why: Makes anomaly/priority suggestions visually distinct.
// Function: deriveAnomaliesFromSuggestions
//   Role: Pull anomaly data from suggestion metadata when explicit anomalies are absent.
//   Called from: FollowUpSuggestions.
//   Invokes: n/a.
//   Why: Ensures anomaly alerts render from backend suggestion metadata.
// --- End Function/Class Map ---
/**
 * FollowUpSuggestions Component
 *
 * Displays AI-generated follow-up questions at the bottom of the dashboard.
 * Clicking a suggestion replaces this component with new dashboard content.
 * Now includes anomaly alerts for proactive insights.
 * 
 * Called from: GenerativeUIPage.tsx after dashboard completes
 * Why: Enables conversational flow by suggesting next analytical steps
 */

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AnomalyAlertList, type AnomalyData } from './widgets/AnomalyAlert';

export interface FollowUpSuggestion {
    /** Unique ID for this suggestion */
    id: string;
    /** The question/query to execute */
    query: string;
    /** Short label for the chip */
    label: string;
    /** Optional icon */
    icon?: string;
    /** Category for styling/prioritization */
    category?: 'skill' | 'anomaly' | 'web_search' | 'insight';
    /** Priority for ordering */
    priority?: 'high' | 'medium' | 'low';
    /** Optional metadata payload for rich suggestions */
    metadata?: Record<string, unknown>;
}

export interface FollowUpSuggestionsProps {
    /** List of suggestions to display */
    suggestions: FollowUpSuggestion[];
    /** Callback when user clicks a suggestion */
    onSelect: (suggestion: FollowUpSuggestion) => void;
    /** Whether suggestions are being generated */
    isLoading?: boolean;
    /** Optional title override */
    title?: string;
    /** Anomalies to display as proactive alerts */
    anomalies?: AnomalyData[];
    /** Callback when user clicks "Investigate" on an anomaly */
    onInvestigateAnomaly?: (anomaly: AnomalyData) => void;
    /** Callback when user clicks "Compare" on an anomaly */
    onCompareAnomaly?: (anomaly: AnomalyData, peerTicker: string) => void;
    /** Callback when user dismisses an anomaly */
    onDismissAnomaly?: (anomaly: AnomalyData) => void;
}

const theme = {
    colors: {
        bg: {
            card: 'rgba(30, 41, 59, 0.6)',
            cardBorder: 'rgba(148, 163, 184, 0.15)',
            chipHover: 'rgba(244, 63, 94, 0.1)',
        },
        accent: {
            primary: '#f43f5e',
            secondary: '#f59e0b',
        },
        text: {
            primary: '#f8fafc',
            secondary: '#94a3b8',
            muted: '#64748b',
        },
    },
};

const ICONS: Record<string, string> = {
    header: '>>',
    action: '>',
    skill: '🎯',
    anomaly: '💡',
    web_search: '🔍',
    insight: '✨',
};

/**
 * Get icon for suggestion based on category or explicit icon
 */
function getSuggestionIcon(suggestion: FollowUpSuggestion): string {
    if (suggestion.icon) return suggestion.icon;
    if (suggestion.category && ICONS[suggestion.category]) {
        return ICONS[suggestion.category];
    }
    return ICONS.action;
}

/**
 * Get priority styling for high-priority suggestions
 */
function getPriorityStyles(suggestion: FollowUpSuggestion): React.CSSProperties {
    if (suggestion.priority === 'high' || suggestion.category === 'anomaly') {
        return {
            borderColor: 'rgba(244, 63, 94, 0.4)',
            backgroundColor: 'rgba(244, 63, 94, 0.1)',
        };
    }
    return {};
}

/**
 * Derive anomaly data from suggestion metadata when present.
 */
function deriveAnomaliesFromSuggestions(suggestions: FollowUpSuggestion[]): AnomalyData[] {
    return suggestions
        .filter((suggestion) => suggestion.category === 'anomaly' && suggestion.metadata)
        .map((suggestion) => suggestion.metadata as AnomalyData)
        .filter((anomaly) => Boolean(anomaly?.ticker && anomaly?.metric));
}

/**
 * FollowUpSuggestions Component
 */
export function FollowUpSuggestions({
    suggestions,
    onSelect,
    isLoading = false,
    title = 'Continue your analysis',
    anomalies = [],
    onInvestigateAnomaly,
    onCompareAnomaly,
    onDismissAnomaly,
}: FollowUpSuggestionsProps): React.ReactElement {
    const fallbackAnomalies = React.useMemo(
        () => (anomalies.length > 0 ? anomalies : deriveAnomaliesFromSuggestions(suggestions)),
        [anomalies, suggestions]
    );
    // State for dismissed anomalies
    const [dismissedAnomalies, setDismissedAnomalies] = React.useState<Set<string>>(new Set());

    // Filter out dismissed anomalies
    const visibleAnomalies = fallbackAnomalies.filter(
        a => !dismissedAnomalies.has(`${a.ticker}-${a.metric}`)
    );

    // Handle dismiss
    const handleDismiss = (anomaly: AnomalyData) => {
        setDismissedAnomalies(prev => new Set([...prev, `${anomaly.ticker}-${anomaly.metric}`]));
        onDismissAnomaly?.(anomaly);
    };

    // Handle investigate - convert anomaly to suggestion and select it
    const handleInvestigate = (anomaly: AnomalyData) => {
        if (onInvestigateAnomaly) {
            onInvestigateAnomaly(anomaly);
        } else {
            // Default behavior: create a suggestion and select it
            const suggestion: FollowUpSuggestion = {
                id: `anomaly-${anomaly.ticker}-${anomaly.metric}`,
                label: `Investigate ${anomaly.metric}`,
                query: `Explain why ${anomaly.ticker}'s ${anomaly.metric} is ${anomaly.comparison.percentageDiff > 0 ? 'high' : 'low'}`,
                icon: ICONS.anomaly,
                category: 'anomaly',
                priority: 'high',
            };
            onSelect(suggestion);
        }
    };

    const handleCompare = (anomaly: AnomalyData, peerTicker: string) => {
        if (onCompareAnomaly) {
            onCompareAnomaly(anomaly, peerTicker);
            return;
        }

        const suggestion: FollowUpSuggestion = {
            id: `compare-${anomaly.ticker}-${peerTicker}`,
            label: `Compare ${anomaly.ticker} to ${peerTicker}`,
            query: `Compare ${anomaly.ticker} to ${peerTicker}`,
            icon: ICONS.anomaly,
            category: 'anomaly',
            priority: 'high',
        };
        onSelect(suggestion);
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="follow-up-suggestions"
            style={{
                backgroundColor: theme.colors.bg.card,
                border: `1px solid ${theme.colors.bg.cardBorder}`,
                borderRadius: '16px',
                padding: '1rem 1.25rem',
                backdropFilter: 'blur(8px)',
            }}
        >
            {/* Anomaly Alerts (proactive insights) */}
            {visibleAnomalies.length > 0 && (
                <div className="mb-4">
                    <AnomalyAlertList
                        anomalies={visibleAnomalies}
                        onInvestigate={handleInvestigate}
                        onCompare={handleCompare}
                        onDismiss={handleDismiss}
                    />
                </div>
            )}

            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <span className="text-lg">{ICONS.header}</span>
                <h4
                    className="text-sm font-medium"
                    style={{ color: theme.colors.text.secondary }}
                >
                    {title}
                </h4>
                {isLoading && (
                    <motion.span
                        className="ml-2"
                        animate={{ opacity: [0.5, 1, 0.5] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                        style={{ color: theme.colors.text.muted, fontSize: '12px' }}
                    >
                        Generating...
                    </motion.span>
                )}
            </div>

            {/* Suggestions */}
            <AnimatePresence mode="popLayout">
                <div className="flex flex-wrap gap-2">
                    {suggestions.map((suggestion, idx) => (
                        <motion.button
                            key={suggestion.id}
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9 }}
                            transition={{ delay: idx * 0.05 }}
                            onClick={() => onSelect(suggestion)}
                            className="group flex items-center gap-2 px-3 py-2 rounded-full transition-all"
                            style={{
                                backgroundColor: 'transparent',
                                border: `1px solid ${theme.colors.bg.cardBorder}`,
                                color: theme.colors.text.primary,
                                cursor: 'pointer',
                                ...getPriorityStyles(suggestion),
                            }}
                            whileHover={{
                                backgroundColor: theme.colors.bg.chipHover,
                                borderColor: theme.colors.accent.primary + '50',
                                scale: 1.02,
                            }}
                            whileTap={{ scale: 0.98 }}
                        >
                            <span className="text-sm">{getSuggestionIcon(suggestion)}</span>
                            <span className="text-sm font-medium">{suggestion.label}</span>
                            <motion.span
                                className="opacity-0 group-hover:opacity-100 transition-opacity"
                                style={{ color: theme.colors.accent.primary }}
                            >
                                {ICONS.action}
                            </motion.span>
                        </motion.button>
                    ))}

                    {/* Empty state */}
                    {suggestions.length === 0 && !isLoading && (
                        <p
                            className="text-sm italic py-2"
                            style={{ color: theme.colors.text.muted }}
                        >
                            No suggestions available
                        </p>
                    )}

                    {/* Loading skeleton */}
                    {isLoading && suggestions.length === 0 && (
                        <>
                            {[1, 2, 3].map((i) => (
                                <motion.div
                                    key={i}
                                    className="px-4 py-2 rounded-full"
                                    style={{
                                        backgroundColor: theme.colors.bg.cardBorder,
                                        width: `${80 + i * 20}px`,
                                        height: '32px',
                                    }}
                                    animate={{
                                        opacity: [0.3, 0.6, 0.3],
                                    }}
                                    transition={{
                                        duration: 1.5,
                                        repeat: Infinity,
                                        delay: i * 0.15,
                                    }}
                                />
                            ))}
                        </>
                    )}
                </div>
            </AnimatePresence>
        </motion.div>
    );
}

export default FollowUpSuggestions;

