/**
 * SkillSection Component
 *
 * A reusable, collapsible section that displays the user query as header,
 * with skill information revealed on click. Features 2 tabs:
 * - "Current Skill Details" - shows the specific skill being used
 * - "What is a Skill?" - educational content about SKILL.md files
 * 
 * Called from: GenerativeUIPage.tsx (top-level, after header)
 * Why: Provides consistent skill information + shows the user's query prominently
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// Skill metadata for different skill types
const SKILL_METADATA: Record<string, {
    name: string;
    description: string;
    icon: string;
    tags: { label: string; color: string }[];
}> = {
    'a2ui_explain_move': {
        name: 'Explain Move',
        description: 'Analyzes price movements by correlating stock data with news events. Fetches real-time news from multiple sources and uses AI to generate insights about why a stock moved.',
        icon: '📊',
        tags: [
            { label: 'chart: candlestick', color: 'positive' },
            { label: 'data: news API', color: 'info' },
            { label: 'insight: AI', color: 'secondary' },
        ],
    },
    'a2ui_margin_analysis': {
        name: 'Margin Analysis',
        description: 'Deep dive into gross, operating, and net margin trends over time. Compares margin performance across quarters and provides AI-powered analysis of margin changes.',
        icon: '📈',
        tags: [
            { label: 'chart: line', color: 'positive' },
            { label: 'data: SQL', color: 'info' },
            { label: 'insight: AI', color: 'secondary' },
        ],
    },
    'a2ui_revenue_trend': {
        name: 'Revenue Trend',
        description: 'Historical revenue analysis with growth metrics. Tracks quarterly and annual revenue changes with YoY comparisons and trend visualization.',
        icon: '💹',
        tags: [
            { label: 'chart: area', color: 'positive' },
            { label: 'data: SQL', color: 'info' },
            { label: 'insight: AI', color: 'secondary' },
        ],
    },
    'a2ui_peer_compare': {
        name: 'Peer Compare',
        description: 'Compares financial metrics across multiple companies. Fetches quarterly financial data from the database and generates a visual comparison with AI-powered analysis.',
        icon: '⚖️',
        tags: [
            { label: 'chart: line', color: 'positive' },
            { label: 'data: SQL', color: 'info' },
            { label: 'insight: AI', color: 'secondary' },
        ],
    },
};

// Theme tokens (matching dashboard design)
const theme = {
    colors: {
        bg: {
            card: 'rgba(15, 23, 42, 0.95)',
            elevated: 'rgba(30, 41, 59, 0.8)',
            section: 'rgba(51, 65, 85, 0.4)',
        },
        border: {
            subtle: 'rgba(148, 163, 184, 0.15)',
        },
        text: {
            primary: '#f8fafc',
            secondary: '#94a3b8',
            muted: '#64748b',
        },
        accent: {
            primary: '#f43f5e', // Rose accent for query
            secondary: '#8b5cf6',
            positive: '#10b981',
            info: '#38bdf8',
        },
    },
};

interface SkillSectionProps {
    /** The skill ID (e.g., 'a2ui_peer_compare') */
    skillId: string;
    /** The user's query to display as the header title */
    query: string;
    /** Custom description to override the default */
    customDescription?: string;
    /** Loading state */
    isLoading?: boolean;
}

type SkillTabId = 'current' | 'what';

export function SkillSection({
    skillId,
    query,
    customDescription,
    isLoading = false,
}: SkillSectionProps): React.ReactElement {
    const [isExpanded, setIsExpanded] = useState(false); // Default collapsed
    const [activeTab, setActiveTab] = useState<SkillTabId>('current');

    // Get skill metadata
    const metadata = SKILL_METADATA[skillId] || {
        name: skillId.replace('a2ui_', '').replace(/_/g, ' '),
        description: 'A skill that processes your request and generates relevant visualizations.',
        icon: '⚡',
        tags: [
            { label: 'chart: auto', color: 'positive' },
            { label: 'data: SQL', color: 'info' },
            { label: 'insight: AI', color: 'secondary' },
        ],
    };

    const description = customDescription || metadata.description;
    const tags = metadata.tags;

    const getTagColor = (color: string) => {
        switch (color) {
            case 'positive': return theme.colors.accent.positive;
            case 'info': return theme.colors.accent.info;
            case 'secondary': return theme.colors.accent.secondary;
            default: return theme.colors.accent.primary;
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            style={{
                borderRadius: '12px',
                backgroundColor: theme.colors.bg.card,
                border: `1px solid ${theme.colors.border.subtle}`,
                overflow: 'hidden',
                marginBottom: '1rem',
            }}
        >
            {/* Clickable Header - Shows Query */}
            <motion.div
                onClick={() => setIsExpanded(!isExpanded)}
                whileHover={{ backgroundColor: 'rgba(30, 41, 59, 0.9)' }}
                whileTap={{ scale: 0.995 }}
                style={{
                    padding: '1rem 1.25rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    backgroundColor: theme.colors.bg.elevated,
                    borderBottom: isExpanded ? `1px solid ${theme.colors.border.subtle}` : 'none',
                    transition: 'background-color 0.2s ease',
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1 }}>
                    {/* Lightning icon */}
                    <div
                        style={{
                            width: '32px',
                            height: '32px',
                            borderRadius: '8px',
                            background: `${theme.colors.accent.primary}22`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '1rem',
                            flexShrink: 0,
                        }}
                    >
                        ⚡
                    </div>

                    {/* Query text as main title */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span
                                style={{
                                    fontSize: '0.95rem',
                                    fontWeight: 600,
                                    color: theme.colors.accent.primary,
                                }}
                            >
                                {query || 'Loading query...'}
                            </span>
                            {isLoading && (
                                <motion.span
                                    animate={{ opacity: [0.5, 1, 0.5] }}
                                    transition={{ duration: 1.5, repeat: Infinity }}
                                    style={{
                                        fontSize: '0.65rem',
                                        padding: '0.125rem 0.5rem',
                                        borderRadius: '4px',
                                        backgroundColor: `${theme.colors.accent.info}22`,
                                        color: theme.colors.accent.info,
                                    }}
                                >
                                    Processing...
                                </motion.span>
                            )}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.25rem' }}>
                            <span style={{ fontSize: '0.7rem', color: theme.colors.text.muted }}>
                                SKILL.md
                            </span>
                            <span
                                style={{
                                    fontSize: '0.65rem',
                                    padding: '0.125rem 0.5rem',
                                    borderRadius: '9999px',
                                    backgroundColor: `${theme.colors.accent.secondary}22`,
                                    color: theme.colors.accent.secondary,
                                }}
                            >
                                {skillId.replace('a2ui_', '')}
                            </span>
                        </div>
                    </div>
                </div>

                {/* Chevron indicator */}
                <motion.div
                    animate={{ rotate: isExpanded ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                    style={{
                        color: theme.colors.text.muted,
                        fontSize: '0.8rem',
                        marginLeft: '1rem',
                    }}
                >
                    ▼
                </motion.div>
            </motion.div>

            {/* Collapsible Content */}
            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25, ease: 'easeInOut' }}
                        style={{ overflow: 'hidden' }}
                    >
                        {/* Sub-tabs */}
                        <div
                            style={{
                                display: 'flex',
                                gap: '0.25rem',
                                padding: '0.5rem 1rem',
                                borderBottom: `1px solid ${theme.colors.border.subtle}`,
                                backgroundColor: theme.colors.bg.section,
                            }}
                        >
                            <button
                                onClick={(e) => { e.stopPropagation(); setActiveTab('current'); }}
                                style={{
                                    padding: '0.375rem 0.75rem',
                                    borderRadius: '6px',
                                    border: 'none',
                                    cursor: 'pointer',
                                    fontSize: '0.7rem',
                                    fontWeight: 500,
                                    backgroundColor: activeTab === 'current' ? `${theme.colors.accent.primary}22` : 'transparent',
                                    color: activeTab === 'current' ? theme.colors.accent.primary : theme.colors.text.secondary,
                                }}
                            >
                                Current Skill Details
                            </button>
                            <button
                                onClick={(e) => { e.stopPropagation(); setActiveTab('what'); }}
                                style={{
                                    padding: '0.375rem 0.75rem',
                                    borderRadius: '6px',
                                    border: 'none',
                                    cursor: 'pointer',
                                    fontSize: '0.7rem',
                                    fontWeight: 500,
                                    backgroundColor: activeTab === 'what' ? `${theme.colors.accent.primary}22` : 'transparent',
                                    color: activeTab === 'what' ? theme.colors.accent.primary : theme.colors.text.secondary,
                                }}
                            >
                                What is a Skill?
                            </button>
                        </div>

                        {/* Tab Content */}
                        <div style={{ padding: '1rem' }}>
                            <AnimatePresence mode="wait">
                                {activeTab === 'current' ? (
                                    <motion.div
                                        key="current"
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        exit={{ opacity: 0, x: 10 }}
                                        transition={{ duration: 0.15 }}
                                    >
                                        {/* Skill Summary */}
                                        <div
                                            style={{
                                                padding: '0.75rem',
                                                borderRadius: '8px',
                                                backgroundColor: theme.colors.bg.elevated,
                                            }}
                                        >
                                            <h4 style={{
                                                fontSize: '0.75rem',
                                                fontWeight: 600,
                                                color: theme.colors.text.primary,
                                                marginBottom: '0.5rem',
                                            }}>
                                                {metadata.icon} Skill: {metadata.name}
                                            </h4>
                                            <p style={{
                                                fontSize: '0.7rem',
                                                color: theme.colors.text.secondary,
                                                lineHeight: 1.5,
                                                marginBottom: '0.5rem',
                                            }}>
                                                {description}
                                            </p>
                                            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                                {tags.map((tag) => (
                                                    <span
                                                        key={tag.label}
                                                        style={{
                                                            fontSize: '0.6rem',
                                                            padding: '0.125rem 0.5rem',
                                                            borderRadius: '4px',
                                                            backgroundColor: `${getTagColor(tag.color)}22`,
                                                            color: getTagColor(tag.color),
                                                        }}
                                                    >
                                                        {tag.label}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    </motion.div>
                                ) : (
                                    <motion.div
                                        key="what"
                                        initial={{ opacity: 0, x: 10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        exit={{ opacity: 0, x: -10 }}
                                        transition={{ duration: 0.15 }}
                                    >
                                        {/* What is a Skill? */}
                                        <div
                                            style={{
                                                padding: '0.75rem',
                                                borderRadius: '8px',
                                                backgroundColor: theme.colors.bg.elevated,
                                                marginBottom: '0.75rem',
                                            }}
                                        >
                                            <h4 style={{
                                                fontSize: '0.75rem',
                                                fontWeight: 600,
                                                color: theme.colors.text.primary,
                                                marginBottom: '0.5rem',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '0.375rem',
                                            }}>
                                                <span style={{ color: theme.colors.accent.primary }}>📄</span>
                                                What is a SKILL.md file?
                                            </h4>
                                            <p style={{
                                                fontSize: '0.7rem',
                                                color: theme.colors.text.secondary,
                                                lineHeight: 1.6,
                                                marginBottom: '0.75rem',
                                            }}>
                                                A <strong style={{ color: theme.colors.text.primary }}>SKILL.md</strong> file is a
                                                structured markdown document that defines how the AI agent should handle specific
                                                types of requests. It acts as a "playbook" that guides the agent's behavior.
                                            </p>
                                            <a
                                                href="https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials/create-custom-slash-commands"
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                onClick={(e) => e.stopPropagation()}
                                                style={{
                                                    display: 'inline-flex',
                                                    alignItems: 'center',
                                                    gap: '0.375rem',
                                                    fontSize: '0.65rem',
                                                    fontWeight: 500,
                                                    color: theme.colors.accent.info,
                                                }}
                                            >
                                                <span>📚</span>
                                                <span>Learn more about Skills.md →</span>
                                            </a>
                                        </div>
                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem' }}>
                                            {[
                                                { icon: '🎯', title: 'Intent & Triggers', desc: 'Keywords that activate this skill' },
                                                { icon: '🛡️', title: 'Guardrails', desc: 'Safety rules and constraints' },
                                                { icon: '📊', title: 'Chart Guidance', desc: 'Visualization rules' },
                                                { icon: '📰', title: 'News Hooks', desc: 'When to fetch context' },
                                            ].map((item) => (
                                                <div
                                                    key={item.title}
                                                    style={{
                                                        padding: '0.5rem',
                                                        borderRadius: '6px',
                                                        backgroundColor: theme.colors.bg.elevated,
                                                    }}
                                                >
                                                    <div style={{ fontSize: '0.9rem', marginBottom: '0.25rem' }}>{item.icon}</div>
                                                    <div style={{ fontSize: '0.65rem', fontWeight: 500, color: theme.colors.text.primary }}>{item.title}</div>
                                                    <div style={{ fontSize: '0.55rem', color: theme.colors.text.muted }}>{item.desc}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}

export default SkillSection;
