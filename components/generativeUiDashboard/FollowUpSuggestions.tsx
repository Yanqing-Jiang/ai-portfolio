// --- Function/Class Map ---
// Component: FollowUpSuggestions
//   Role: Render follow-up suggestion chips with loading and empty states.
//   Called from: components/generativeUiDashboard/GenerativeUIPage.tsx
//   Invokes: onSelect callbacks, framer-motion animations
//   Why: Keeps the analysis flow conversational with guided next steps.
// --- End Function/Class Map ---
/**
 * FollowUpSuggestions Component
 *
 * Displays AI-generated follow-up questions at the bottom of the dashboard.
 * Clicking a suggestion replaces this component with new dashboard content.
 * 
 * Called from: GenerativeUIPage.tsx after dashboard completes
 * Why: Enables conversational flow by suggesting next analytical steps
 */

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface FollowUpSuggestion {
    /** Unique ID for this suggestion */
    id: string;
    /** The question/query to execute */
    query: string;
    /** Short label for the chip */
    label: string;
    /** Optional icon */
    icon?: string;
}

interface FollowUpSuggestionsProps {
    /** List of suggestions to display */
    suggestions: FollowUpSuggestion[];
    /** Callback when user clicks a suggestion */
    onSelect: (suggestion: FollowUpSuggestion) => void;
    /** Whether suggestions are being generated */
    isLoading?: boolean;
    /** Optional title override */
    title?: string;
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

const ICONS = {
    header: '>>',
    action: '>',
};

/**
 * FollowUpSuggestions Component
 */
export function FollowUpSuggestions({
    suggestions,
    onSelect,
    isLoading = false,
    title = 'Continue your analysis',
}: FollowUpSuggestionsProps): React.ReactElement {
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
                            }}
                            whileHover={{
                                backgroundColor: theme.colors.bg.chipHover,
                                borderColor: theme.colors.accent.primary + '50',
                                scale: 1.02,
                            }}
                            whileTap={{ scale: 0.98 }}
                        >
                            {suggestion.icon && (
                                <span className="text-sm">{suggestion.icon}</span>
                            )}
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

export type { FollowUpSuggestion };
export default FollowUpSuggestions;
