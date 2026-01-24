/**
 * Function: ExplainMovePanel — Displays AI-generated explanation for stock movements
 * Called from: Registry.tsx when rendering a2ui_explain_move skill dashboards
 * Invokes: useStreamingText hook for typewriter effect
 * Purpose: Shows factors, citations, and narrative explanation with skill-inspired design
 * 
 * Design Pattern: Modeled after SkillModal.tsx from conversational_analytics for
 * consistent visual language across the portfolio
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import { getByPath, resolveArray, resolveString } from '../../a2ui/DataBinder';
import type { ExplainMovePanelProps } from '../../a2ui/types';
import { useStreamingText } from '../../hooks/useStreamingText';
import { ReasoningDisclosure, type ReasoningStep } from '../../widgets/ReasoningDisclosure';


interface Factor {
    title: string;
    description: string;
    impact: 'positive' | 'negative' | 'neutral';
    source?: string;
    icon?: string;
}

interface Citation {
    title: string;
    url?: string;
    date?: string;
}

// Enhanced theme inspired by SkillModal.tsx
const theme = {
    colors: {
        bg: {
            card: 'rgba(15, 23, 42, 0.95)',
            elevated: 'rgba(30, 41, 59, 0.8)',
            section: 'rgba(51, 65, 85, 0.4)',
        },
        border: {
            subtle: 'rgba(148, 163, 184, 0.15)',
            medium: 'rgba(148, 163, 184, 0.25)',
        },
        text: {
            primary: '#f8fafc',
            secondary: '#94a3b8',
            muted: '#64748b',
        },
        accent: {
            primary: '#f43f5e',
            secondary: '#f59e0b',
            info: '#38bdf8',
            muted: 'rgba(244, 63, 94, 0.15)',
        },
        impact: {
            positive: { bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981', icon: '📈' },
            negative: { bg: 'rgba(239, 68, 68, 0.15)', text: '#ef4444', icon: '📉' },
            neutral: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', icon: '➡️' },
        },
    },
    shadows: {
        lg: '0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.15)',
    },
};

const DEFAULT_FACTORS: Factor[] = [
    {
        title: 'Market Conditions',
        description: 'Broader market sentiment and sector rotation affecting price action',
        impact: 'neutral',
        source: 'Market Analysis',
        icon: '🌍',
    },
    {
        title: 'Earnings & Guidance',
        description: 'Recent earnings report and forward guidance expectations',
        impact: 'negative',
        source: 'Company Filings',
        icon: '📊',
    },
    {
        title: 'Sector Dynamics',
        description: 'Industry-specific trends and competitive positioning',
        impact: 'positive',
        source: 'Industry Reports',
        icon: '🏭',
    }
];

// Tabs for enhanced navigation (inspired by SkillModal)
type TabId = 'analysis' | 'factors' | 'sources';

export function ExplainMovePanel({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const [activeTab, setActiveTab] = useState<TabId>('analysis');

    const panelProps = props as unknown as ExplainMovePanelProps;
    const title = resolveString(panelProps.title, dataModel, 'AI Insight Analysis');
    const DEFAULT_EXPLANATION = 'Analyzing market conditions...';
    const fullExplanation = resolveString(panelProps.explanation, dataModel, DEFAULT_EXPLANATION);
    const factors = resolveArray<Factor>(panelProps.factors, dataModel, []);
    const citations = resolveArray<Citation>(panelProps.citations, dataModel, []);
    const isCached = Boolean(getByPath(dataModel, '/data/explanation/cached'));
    // Check if this is a revisited dashboard (skip streaming animation)
    const isRevisit = Boolean(getByPath(dataModel, '/data/explanation/isRevisit'));
    // Get AI reasoning steps for disclosure
    const reasoningSteps = resolveArray<ReasoningStep>(
        panelProps.reasoningSteps ?? { path: '/data/explanation/reasoning_steps' },
        dataModel,
        []
    );

    // Check if we have real content (not placeholder) to prevent streaming placeholder text
    const hasRealContent = fullExplanation && fullExplanation !== DEFAULT_EXPLANATION;

    // Use streaming text hook for the narrative
    // Skip streaming entirely for revisited dashboards - show full text immediately
    // Use stable resetKey (just componentId) to prevent content clearing on data load
    const { displayText, isComplete } = useStreamingText(fullExplanation, {
        speed: 20,
        resetKey: componentId,
        enabled: !isCached && !isRevisit && hasRealContent,
    });

    // For revisited dashboards, show full text immediately
    // Show placeholder if no real content available (don't show empty)
    const finalDisplayText = hasRealContent
        ? (isRevisit ? fullExplanation : displayText)
        : DEFAULT_EXPLANATION;
    const finalIsComplete = isRevisit && hasRealContent ? true : isComplete;

    const displayFactors = factors.length > 0 ? factors : DEFAULT_FACTORS;
    const showCitations = citations.length > 0;

    // Tab configuration
    const tabs: { id: TabId; label: string; icon: string }[] = [
        { id: 'analysis', label: 'Analysis', icon: '✨' },
        { id: 'factors', label: 'Key Factors', icon: '🎯' },
        ...(showCitations ? [{ id: 'sources' as TabId, label: 'Sources', icon: '📚' }] : []),
    ];

    return (
        <motion.div
            layout
            layoutId={componentId}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="a2ui-explain-panel"
            style={{
                backgroundColor: theme.colors.bg.card,
                borderRadius: '16px',
                border: `1px solid ${theme.colors.border.medium}`,
                boxShadow: theme.shadows.lg,
                backdropFilter: 'blur(16px)',
                overflow: 'hidden',
            }}
        >
            {/* Enhanced Header with Gradient Accent */}
            <div
                style={{
                    padding: '1rem 1.25rem',
                    borderBottom: `1px solid ${theme.colors.border.subtle}`,
                    background: `linear-gradient(180deg, ${theme.colors.bg.elevated} 0%, ${theme.colors.bg.card} 100%)`,
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div
                            style={{
                                width: '36px',
                                height: '36px',
                                borderRadius: '10px',
                                background: theme.colors.accent.muted,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '1.25rem',
                            }}
                        >
                            🔮
                        </div>
                        <div>
                            <h3
                                style={{
                                    fontSize: '1rem',
                                    fontWeight: 600,
                                    color: theme.colors.text.primary,
                                    margin: 0,
                                }}
                            >
                                {title}
                            </h3>
                            <p
                                style={{
                                    fontSize: '0.75rem',
                                    color: theme.colors.text.muted,
                                    margin: 0,
                                }}
                            >
                                AI-powered market analysis
                            </p>
                        </div>
                    </div>

                    {/* Streaming indicator - hide when cached, complete, or revisit */}
                    {!finalIsComplete && !isCached && !isRevisit && (
                        <motion.div
                            animate={{ opacity: [0.5, 1, 0.5] }}
                            transition={{ duration: 1.5, repeat: Infinity }}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.5rem',
                                padding: '0.25rem 0.75rem',
                                borderRadius: '9999px',
                                backgroundColor: theme.colors.accent.muted,
                            }}
                        >
                            <motion.div
                                animate={{ scale: [1, 1.2, 1] }}
                                transition={{ duration: 0.6, repeat: Infinity }}
                                style={{
                                    width: '6px',
                                    height: '6px',
                                    borderRadius: '50%',
                                    backgroundColor: theme.colors.accent.primary,
                                }}
                            />
                            <span style={{ fontSize: '0.7rem', color: theme.colors.accent.primary, fontWeight: 500 }}>
                                Analyzing...
                            </span>
                        </motion.div>
                    )}
                </div>
            </div>

            {/* Tab Navigation (inspired by SkillModal) */}
            <div
                style={{
                    display: 'flex',
                    gap: '0.25rem',
                    padding: '0.5rem 1rem',
                    borderBottom: `1px solid ${theme.colors.border.subtle}`,
                }}
            >
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={(e) => { e.stopPropagation(); setActiveTab(tab.id); }}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.375rem',
                            padding: '0.5rem 0.75rem',
                            borderRadius: '8px',
                            border: 'none',
                            cursor: 'pointer',
                            fontSize: '0.75rem',
                            fontWeight: 500,
                            transition: 'all 0.15s ease',
                            backgroundColor: activeTab === tab.id ? theme.colors.accent.muted : 'transparent',
                            color: activeTab === tab.id ? theme.colors.accent.primary : theme.colors.text.secondary,
                        }}
                    >
                        <span>{tab.icon}</span>
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            <div style={{ padding: '1rem 1.25rem' }}>
                <AnimatePresence mode="wait">
                    {activeTab === 'analysis' && (
                        <motion.div
                            key="analysis"
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 10 }}
                            transition={{ duration: 0.15 }}
                        >
                            {/* Narrative Summary with Streaming Effect */}
                            <div
                                style={{
                                    padding: '1rem',
                                    borderRadius: '12px',
                                    backgroundColor: theme.colors.bg.section,
                                    marginBottom: '1rem',
                                }}
                            >
                                <p
                                    style={{
                                        fontSize: '0.9rem',
                                        lineHeight: 1.7,
                                        color: theme.colors.text.secondary,
                                        margin: 0,
                                        minHeight: '4em',
                                    }}
                                >
                                    {finalDisplayText}
                                    {!finalIsComplete && !isCached && !isRevisit && (
                                        <motion.span
                                            animate={{ opacity: [0, 1, 0] }}
                                            transition={{ repeat: Infinity, duration: 0.8 }}
                                            style={{
                                                display: 'inline-block',
                                                width: '2px',
                                                height: '1em',
                                                backgroundColor: theme.colors.accent.info,
                                                marginLeft: '2px',
                                                verticalAlign: 'middle',
                                            }}
                                        />
                                    )}
                                </p>
                            </div>

                            {/* AI Reasoning Disclosure */}
                            {reasoningSteps.length > 0 && (
                                <div style={{ marginBottom: '1rem' }}>
                                    <ReasoningDisclosure
                                        steps={reasoningSteps}
                                        label="Why this insight?"
                                        defaultExpanded={false}
                                    />
                                </div>
                            )}

                            {/* Quick Stats Grid - responsive */}
                            <div
                                style={{
                                    display: 'grid',
                                    gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', // 1-3 cols based on width
                                    gap: 'clamp(0.5rem, 2vw, 0.75rem)',
                                }}
                            >
                                {displayFactors.slice(0, 3).map((factor, idx) => (
                                    <motion.div
                                        key={`quick-${idx}`}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: 0.1 * idx }}
                                        style={{
                                            padding: '0.75rem',
                                            borderRadius: '10px',
                                            backgroundColor: theme.colors.impact[factor.impact].bg,
                                            border: `1px solid ${theme.colors.border.subtle}`,
                                        }}
                                    >
                                        <div style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>
                                            {factor.icon || theme.colors.impact[factor.impact].icon}
                                        </div>
                                        <p
                                            style={{
                                                fontSize: '0.7rem',
                                                fontWeight: 600,
                                                color: theme.colors.impact[factor.impact].text,
                                                margin: 0,
                                            }}
                                        >
                                            {factor.title}
                                        </p>
                                    </motion.div>
                                ))}
                            </div>
                        </motion.div>
                    )}

                    {activeTab === 'factors' && (
                        <motion.div
                            key="factors"
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -10 }}
                            transition={{ duration: 0.15 }}
                        >
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                                {displayFactors.map((factor, idx) => (
                                    <motion.div
                                        key={`factor-${idx}`}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: 0.05 * idx }}
                                        style={{
                                            display: 'flex',
                                            gap: '0.75rem',
                                            padding: '0.875rem',
                                            borderRadius: '12px',
                                            backgroundColor: theme.colors.bg.section,
                                            border: `1px solid ${theme.colors.border.subtle}`,
                                        }}
                                    >
                                        {/* Impact Indicator */}
                                        <div
                                            style={{
                                                width: '36px',
                                                height: '36px',
                                                borderRadius: '10px',
                                                backgroundColor: theme.colors.impact[factor.impact].bg,
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                flexShrink: 0,
                                            }}
                                        >
                                            <span style={{ fontSize: '1rem' }}>
                                                {factor.icon || theme.colors.impact[factor.impact].icon}
                                            </span>
                                        </div>

                                        <div style={{ flex: 1, minWidth: 0 }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                                                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: theme.colors.text.primary, margin: 0 }}>
                                                    {factor.title}
                                                </h4>
                                                {factor.source && (
                                                    <span
                                                        style={{
                                                            fontSize: '0.65rem',
                                                            padding: '0.125rem 0.5rem',
                                                            borderRadius: '4px',
                                                            backgroundColor: theme.colors.bg.elevated,
                                                            color: theme.colors.text.muted,
                                                        }}
                                                    >
                                                        {factor.source}
                                                    </span>
                                                )}
                                            </div>
                                            <p style={{ fontSize: '0.8rem', color: theme.colors.text.secondary, margin: 0, lineHeight: 1.5 }}>
                                                {factor.description}
                                            </p>
                                        </div>
                                    </motion.div>
                                ))}
                            </div>
                        </motion.div>
                    )}

                    {activeTab === 'sources' && showCitations && (
                        <motion.div
                            key="sources"
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -10 }}
                            transition={{ duration: 0.15 }}
                        >
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                {citations.map((citation, idx) => (
                                    <motion.div
                                        key={idx}
                                        initial={{ opacity: 0, scale: 0.9 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        transition={{ delay: 0.05 * idx }}
                                    >
                                        {citation.url ? (
                                            <a
                                                href={citation.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                style={{
                                                    display: 'inline-flex',
                                                    alignItems: 'center',
                                                    gap: '0.375rem',
                                                    padding: '0.5rem 0.75rem',
                                                    borderRadius: '8px',
                                                    backgroundColor: theme.colors.bg.section,
                                                    border: `1px solid ${theme.colors.border.subtle}`,
                                                    color: theme.colors.accent.info,
                                                    fontSize: '0.75rem',
                                                    textDecoration: 'none',
                                                    transition: 'all 0.2s',
                                                }}
                                            >
                                                <span>📄</span>
                                                {citation.title}
                                                {citation.date && (
                                                    <span style={{ color: theme.colors.text.muted, fontSize: '0.65rem' }}>
                                                        · {citation.date}
                                                    </span>
                                                )}
                                            </a>
                                        ) : (
                                            <span
                                                style={{
                                                    display: 'inline-flex',
                                                    alignItems: 'center',
                                                    gap: '0.375rem',
                                                    padding: '0.5rem 0.75rem',
                                                    borderRadius: '8px',
                                                    backgroundColor: theme.colors.bg.section,
                                                    border: `1px solid ${theme.colors.border.subtle}`,
                                                    color: theme.colors.text.secondary,
                                                    fontSize: '0.75rem',
                                                }}
                                            >
                                                <span>📄</span>
                                                {citation.title}
                                            </span>
                                        )}
                                    </motion.div>
                                ))}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Footer with Disclaimer */}
            <div
                style={{
                    padding: '0.75rem 1.25rem',
                    borderTop: `1px solid ${theme.colors.border.subtle}`,
                    backgroundColor: theme.colors.bg.elevated,
                }}
            >
                <p
                    style={{
                        fontSize: '0.65rem',
                        color: theme.colors.text.muted,
                        margin: 0,
                        textAlign: 'center',
                        fontStyle: 'italic',
                    }}
                >
                    💡 AI-generated analysis based on market data and news. For informational purposes only.
                </p>
            </div>
        </motion.div>
    );
}

export default ExplainMovePanel;
