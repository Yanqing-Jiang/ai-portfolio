// --- ExplainMovePanel Function Map ---
// Function: ExplainMovePanelInternal
//   Role: Render the explanation panel UI from resolved props.
//   Called from: components/generativeUiDashboard/renderer/widgets/ExplainMovePanel.ExplainMovePanel
//   Invokes: React + framer-motion primitives
//   Why: Keeps presentation logic isolated from A2UI data binding.
// Function: ExplainMovePanel
//   Role: Resolve A2UI bound props and render ExplainMovePanelInternal.
//   Called from: components/generativeUiDashboard/renderer/Registry (componentRegistry)
//   Invokes: resolveString, resolveArray, ExplainMovePanelInternal
//   Why: Bridges A2UI data binding to the UI component.
// --- End ExplainMovePanel Function Map ---
/**
 * ExplainMovePanel Widget
 *
 * Displays AI-generated explanation for price movements with citations.
 */

import React from 'react';
import { motion } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import { resolveArray, resolveString } from '../../a2ui/DataBinder';
import type { ExplainMovePanelProps } from '../../a2ui/types';

interface Factor {
    title: string;
    description: string;
    impact: 'positive' | 'negative' | 'neutral';
    source?: string;
}

interface Citation {
    title: string;
    url?: string;
    date?: string;
}

interface ExplainMovePanelInternalProps {
    title: string;
    explanation: string;
    factors: Factor[];
    citations: Citation[];
}

const theme = {
    bg: {
        card: 'rgba(30, 41, 59, 0.8)',
    },
    border: {
        subtle: 'rgba(148, 163, 184, 0.15)',
    },
    text: {
        primary: '#f8fafc',
        secondary: '#94a3b8',
        muted: '#64748b',
    },
    impact: {
        positive: '#10b981',
        negative: '#ef4444',
        neutral: '#f59e0b',
    },
};

// Default factors if none provided
const DEFAULT_FACTORS: Factor[] = [
    {
        title: 'Market Conditions',
        description: 'Broader market sentiment and sector rotation affecting price action',
        impact: 'neutral',
        source: 'Market Analysis',
    },
    {
        title: 'Earnings & Guidance',
        description: 'Recent earnings report and forward guidance expectations',
        impact: 'negative',
        source: 'Company Filings',
    },
    {
        title: 'Technical Factors',
        description: 'Key support/resistance levels and momentum indicators',
        impact: 'neutral',
        source: 'Technical Analysis',
    },
];

function ExplainMovePanelInternal({
    title,
    explanation,
    factors,
    citations,
}: ExplainMovePanelInternalProps): React.ReactElement {
    const displayFactors = factors.length > 0 ? factors : DEFAULT_FACTORS;
    const showCitations = citations.length > 0;

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl p-4"
            style={{
                backgroundColor: theme.bg.card,
                border: `1px solid ${theme.border.subtle}`,
            }}
        >
            {/* Header */}
            <div className="flex items-center gap-2 mb-4">
                <span className="text-lg">dY"?</span>
                <h3 className="text-sm font-semibold" style={{ color: theme.text.primary }}>
                    {title}
                </h3>
            </div>

            {/* Summary */}
            <p className="text-sm mb-4" style={{ color: theme.text.secondary }}>
                {explanation}
            </p>

            {/* Factors */}
            <div className="space-y-3">
                {displayFactors.map((factor, idx) => (
                    <motion.div
                        key={factor.title}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className="flex items-start gap-3 p-3 rounded-lg"
                        style={{
                            backgroundColor: 'rgba(15, 23, 42, 0.5)',
                            border: `1px solid ${theme.border.subtle}`,
                        }}
                    >
                        {/* Impact indicator */}
                        <div
                            className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
                            style={{ backgroundColor: theme.impact[factor.impact] }}
                        />

                        <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2">
                                <h4 className="text-sm font-medium" style={{ color: theme.text.primary }}>
                                    {factor.title}
                                </h4>
                                {showCitations && factor.source && (
                                    <span
                                        className="text-xs px-2 py-0.5 rounded"
                                        style={{
                                            backgroundColor: 'rgba(148, 163, 184, 0.1)',
                                            color: theme.text.muted,
                                        }}
                                    >
                                        {factor.source}
                                    </span>
                                )}
                            </div>
                            <p className="text-xs mt-1" style={{ color: theme.text.secondary }}>
                                {factor.description}
                            </p>
                        </div>
                    </motion.div>
                ))}
            </div>

            {showCitations && (
                <div className="mt-4 space-y-2">
                    <p className="text-xs uppercase tracking-wide" style={{ color: theme.text.muted }}>
                        Sources
                    </p>
                    <ul className="space-y-1">
                        {citations.map((citation) => (
                            <li
                                key={`${citation.title}-${citation.url ?? ''}`}
                                className="text-xs"
                                style={{ color: theme.text.secondary }}
                            >
                                {citation.url ? (
                                    <a
                                        href={citation.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{ color: theme.text.secondary, textDecoration: 'underline' }}
                                    >
                                        {citation.title}
                                    </a>
                                ) : (
                                    citation.title
                                )}
                                {citation.date ? ` • ${citation.date}` : ''}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Disclaimer */}
            <p className="text-xs mt-4 opacity-50" style={{ color: theme.text.muted }}>
                ƒsÿ‹,? This analysis is AI-generated for informational purposes only.
            </p>
        </motion.div>
    );
}

/**
 * A2UI-compatible wrapper component
 */
export function ExplainMovePanel({ props, dataModel }: A2UIRendererProps): React.ReactElement {
    const panelProps = props as unknown as ExplainMovePanelProps;
    const title = resolveString(panelProps.title, dataModel, 'Price Movement Analysis');
    const explanation = resolveString(panelProps.explanation, dataModel, 'Analysis in progress...');
    const factors = resolveArray<Factor>(panelProps.factors, dataModel, []);
    const citations = resolveArray<Citation>(panelProps.citations, dataModel, []);

    return (
        <ExplainMovePanelInternal
            title={title}
            explanation={explanation}
            factors={factors}
            citations={citations}
        />
    );
}

export default ExplainMovePanel;
