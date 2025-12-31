/**
 * SkillHeaderBadge Component
 *
 * Displays the active A2UI skill at the top of the dashboard.
 * Shows the skill name and a brief description, with option to expand for details.
 * 
 * Called from: GenerativeUIPage.tsx when a dashboard is rendering
 * Why: Helps users understand what skill is powering the current visualization
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface SkillInfo {
    id: string;
    name: string;
    description?: string;
    icon?: string;
}

interface SkillHeaderBadgeProps {
    skill: SkillInfo | null;
    isLoading?: boolean;
}

// Skill metadata mapping
const SKILL_METADATA: Record<string, { name: string; description: string; icon: string }> = {
    'a2ui_explain_move': {
        name: 'Explain Move',
        description: 'Analyzes price movements with news context and AI explanation',
        icon: '📊',
    },
    'a2ui_margin_analysis': {
        name: 'Margin Analysis',
        description: 'Deep dive into gross, operating, and net margin trends',
        icon: '📈',
    },
    'a2ui_revenue_trend': {
        name: 'Revenue Trend',
        description: 'Historical revenue analysis with growth metrics',
        icon: '💹',
    },
    'a2ui_peer_compare': {
        name: 'Peer Comparison',
        description: 'Compare financial metrics across multiple companies',
        icon: '⚖️',
    },
};

const theme = {
    colors: {
        bg: {
            badge: 'rgba(30, 41, 59, 0.7)',
            badgeBorder: 'rgba(148, 163, 184, 0.2)',
            expanded: 'rgba(15, 23, 42, 0.95)',
        },
        accent: {
            primary: '#f43f5e',
            secondary: '#f59e0b',
            muted: 'rgba(244, 63, 94, 0.15)',
        },
        text: {
            primary: '#f8fafc',
            secondary: '#94a3b8',
            muted: '#64748b',
        },
    },
};

export function SkillHeaderBadge({
    skill,
    isLoading = false,
}: SkillHeaderBadgeProps): React.ReactElement | null {
    const [isExpanded, setIsExpanded] = useState(false);

    // Get enriched skill metadata
    const metadata = skill?.id ? SKILL_METADATA[skill.id] : null;
    const displayName = skill?.name || metadata?.name || 'Unknown Skill';
    const description = skill?.description || metadata?.description || '';
    const icon = skill?.icon || metadata?.icon || '⚡';

    if (!skill && !isLoading) return null;

    return (
        <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="skill-header-badge mb-4"
        >
            <motion.button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full transition-all cursor-pointer"
                style={{
                    backgroundColor: theme.colors.bg.badge,
                    border: `1px solid ${theme.colors.bg.badgeBorder}`,
                    backdropFilter: 'blur(8px)',
                }}
                whileHover={{
                    backgroundColor: theme.colors.accent.muted,
                    borderColor: theme.colors.accent.primary + '40',
                }}
            >
                {isLoading ? (
                    <>
                        <motion.span
                            animate={{ opacity: [0.5, 1, 0.5] }}
                            transition={{ duration: 1.5, repeat: Infinity }}
                            className="text-sm"
                        >
                            ⏳
                        </motion.span>
                        <span
                            className="text-xs font-medium"
                            style={{ color: theme.colors.text.secondary }}
                        >
                            Selecting skill...
                        </span>
                    </>
                ) : (
                    <>
                        <span className="text-sm">{icon}</span>
                        <span
                            className="text-xs font-medium"
                            style={{ color: theme.colors.text.primary }}
                        >
                            {displayName}
                        </span>
                        <motion.span
                            animate={{ rotate: isExpanded ? 180 : 0 }}
                            transition={{ duration: 0.2 }}
                            className="text-xs"
                            style={{ color: theme.colors.text.muted }}
                        >
                            ▾
                        </motion.span>
                    </>
                )}
            </motion.button>

            <AnimatePresence>
                {isExpanded && !isLoading && (
                    <motion.div
                        initial={{ opacity: 0, height: 0, marginTop: 0 }}
                        animate={{ opacity: 1, height: 'auto', marginTop: 8 }}
                        exit={{ opacity: 0, height: 0, marginTop: 0 }}
                        className="overflow-hidden"
                    >
                        <div
                            className="p-3 rounded-lg"
                            style={{
                                backgroundColor: theme.colors.bg.expanded,
                                border: `1px solid ${theme.colors.bg.badgeBorder}`,
                            }}
                        >
                            <div className="flex items-start gap-3">
                                <div
                                    className="w-10 h-10 rounded-lg flex items-center justify-center text-xl flex-shrink-0"
                                    style={{
                                        background: theme.colors.accent.muted,
                                    }}
                                >
                                    {icon}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <h4
                                        className="text-sm font-semibold mb-1"
                                        style={{ color: theme.colors.text.primary }}
                                    >
                                        {displayName}
                                    </h4>
                                    <p
                                        className="text-xs leading-relaxed"
                                        style={{ color: theme.colors.text.secondary }}
                                    >
                                        {description}
                                    </p>
                                    {skill?.id && (
                                        <p
                                            className="text-xs mt-1 font-mono"
                                            style={{ color: theme.colors.text.muted }}
                                        >
                                            ID: {skill.id}
                                        </p>
                                    )}
                                </div>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}

export type { SkillInfo };
export default SkillHeaderBadge;
