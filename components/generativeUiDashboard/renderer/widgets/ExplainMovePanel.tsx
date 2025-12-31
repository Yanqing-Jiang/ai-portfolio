import React from 'react';
import { motion } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import { resolveArray, resolveString } from '../../a2ui/DataBinder';
import type { ExplainMovePanelProps } from '../../a2ui/types';
import { useStreamingText } from '../../hooks/useStreamingText';


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
    }
};

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
    }
];

export function ExplainMovePanel({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const panelProps = props as unknown as ExplainMovePanelProps;
    const title = resolveString(panelProps.title, dataModel, 'Insight Analysis');
    const fullExplanation = resolveString(panelProps.explanation, dataModel, 'Analysis in progress...');
    const factors = resolveArray<Factor>(panelProps.factors, dataModel, []);
    const citations = resolveArray<Citation>(panelProps.citations, dataModel, []);

    // Use streaming text hook for the narrative
    const { displayText, isComplete } = useStreamingText(fullExplanation, { speed: 25 });

    const displayFactors = factors.length > 0 ? factors : DEFAULT_FACTORS;
    const showCitations = citations.length > 0;

    return (
        <motion.div
            layout
            layoutId={componentId}
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            className="a2ui-explain-panel"
            style={{
                backgroundColor: theme.bg.card,
                padding: '1.5rem',
                borderRadius: '16px',
                border: `1px solid ${theme.border.subtle}`,
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                backdropFilter: 'blur(12px)',
                marginBottom: '1rem',
            }}
        >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    backgroundColor: 'rgba(56, 189, 248, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#38bdf8'
                }}>
                    ✨
                </div>
                <h3 style={{
                    fontSize: '1.125rem',
                    fontWeight: 600,
                    color: theme.text.primary,
                    margin: 0
                }}>
                    {title}
                </h3>
            </div>

            {/* Narrative Summary with Streaming Effect */}
            <div style={{ marginBottom: '1.5rem', position: 'relative' }}>
                <p style={{
                    fontSize: '1rem',
                    lineHeight: '1.6',
                    color: theme.text.secondary,
                    margin: 0,
                    minHeight: '3em'
                }}>
                    {displayText}
                    {!isComplete && (
                        <motion.span
                            animate={{ opacity: [0, 1, 0] }}
                            transition={{ repeat: Infinity, duration: 0.8 }}
                            style={{
                                display: 'inline-block',
                                width: '2px',
                                height: '1.2em',
                                backgroundColor: '#38bdf8',
                                marginLeft: '2px',
                                verticalAlign: 'middle'
                            }}
                        />
                    )}
                </p>
            </div>

            {/* Key Factors */}
            <div style={{ display: 'grid', gap: '1rem', marginBottom: '1.5rem' }}>
                {displayFactors.map((factor, idx) => (
                    <motion.div
                        key={`${factor.title}-${idx}`}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.1 * idx }}
                        style={{
                            display: 'flex',
                            gap: '1rem',
                            padding: '1rem',
                            borderRadius: '12px',
                            backgroundColor: 'rgba(15, 23, 42, 0.3)',
                            border: `1px solid ${theme.border.subtle}`,
                        }}
                    >
                        <div style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            marginTop: '0.5rem',
                            flexShrink: 0,
                            backgroundColor: theme.impact[factor.impact] || theme.impact.neutral,
                            boxShadow: `0 0 10px ${theme.impact[factor.impact] || theme.impact.neutral}`,
                        }} />
                        <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                                <h4 style={{ fontSize: '0.9rem', fontWeight: 500, color: theme.text.primary, margin: 0 }}>
                                    {factor.title}
                                </h4>
                                {factor.source && (
                                    <span style={{
                                        fontSize: '0.75rem',
                                        padding: '2px 8px',
                                        borderRadius: '4px',
                                        backgroundColor: 'rgba(148, 163, 184, 0.1)',
                                        color: theme.text.muted,
                                    }}>
                                        {factor.source}
                                    </span>
                                )}
                            </div>
                            <p style={{ fontSize: '0.85rem', color: theme.text.secondary, margin: 0 }}>
                                {factor.description}
                            </p>
                        </div>
                    </motion.div>
                ))}
            </div>

            {/* Citations */}
            {showCitations && (
                <div style={{ borderTop: `1px solid ${theme.border.subtle}`, paddingTop: '1rem' }}>
                    <p style={{
                        fontSize: '0.75rem',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: theme.text.muted,
                        marginBottom: '0.5rem'
                    }}>
                        Sources
                    </p>
                    <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        {citations.map((citation, idx) => (
                            <li key={idx}>
                                {citation.url ? (
                                    <a
                                        href={citation.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{
                                            fontSize: '0.75rem',
                                            color: '#38bdf8',
                                            textDecoration: 'none',
                                            padding: '4px 10px',
                                            borderRadius: '6px',
                                            backgroundColor: 'rgba(56, 189, 248, 0.1)',
                                            border: '1px solid rgba(56, 189, 248, 0.2)',
                                            transition: 'all 0.2s',
                                        }}
                                        onMouseOver={(e) => {
                                            e.currentTarget.style.backgroundColor = 'rgba(56, 189, 248, 0.2)';
                                        }}
                                        onMouseOut={(e) => {
                                            e.currentTarget.style.backgroundColor = 'rgba(56, 189, 248, 0.1)';
                                        }}
                                    >
                                        {citation.title}
                                    </a>
                                ) : (
                                    <span style={{ fontSize: '0.75rem', color: theme.text.secondary }}>
                                        {citation.title}
                                    </span>
                                )}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Disclaimer */}
            <p style={{
                fontSize: '0.7rem',
                marginTop: '1.5rem',
                opacity: 0.4,
                color: theme.text.muted,
                textAlign: 'center',
                fontStyle: 'italic'
            }}>
                AI-generated analysis. For information purposes only.
            </p>
        </motion.div>
    );
}

export default ExplainMovePanel;
