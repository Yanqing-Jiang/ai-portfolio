/**
 * ContextRibbon Component
 *
 * Displays a visual breadcrumb/history of queries that led to the current dashboard.
 * Allows users to see the evolution of their analysis and potentially switch back.
 * 
 * Called from: GenerativeUIPage.tsx
 * Why: Part of the "Future of Analytics" wow factor — shows analysis context.
 */

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export interface HistoryItem {
    id: string;
    query: string;
    timestamp: Date;
}

interface ContextRibbonProps {
    history: HistoryItem[];
    currentId: string | null;
    onSelect: (item: HistoryItem) => void;
}

const theme = {
    colors: {
        bg: 'rgba(30, 41, 59, 0.4)',
        border: 'rgba(148, 163, 184, 0.1)',
        activeBg: 'rgba(99, 102, 241, 0.15)',  // Blue tint instead of red
        activeBorder: 'rgba(99, 102, 241, 0.4)',  // Blue border
        text: {
            primary: '#f8fafc',
            secondary: '#94a3b8',
            muted: '#64748b',
        }
    }
};

export function ContextRibbon({
    history,
    currentId,
    onSelect,
}: ContextRibbonProps): React.ReactElement | null {
    if (history.length === 0) return null;

    return (
        <div className="context-ribbon-wrapper mb-4 overflow-hidden">
            <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
                <AnimatePresence mode="popLayout">
                    {history.map((item, idx) => {
                        const isActive = item.id === currentId;
                        return (
                            <motion.div
                                key={item.id}
                                style={{ display: 'contents' }}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                            >
                                {idx > 0 && (
                                    <motion.span
                                        initial={{ opacity: 0, scale: 0.5 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        className="text-slate-600 flex-shrink-0"
                                    >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                        </svg>
                                    </motion.span>
                                )}
                                <motion.button
                                    layout
                                    initial={{ opacity: 0, x: -20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    whileHover={{ scale: 1.02 }}
                                    whileTap={{ scale: 0.98 }}
                                    onClick={() => onSelect(item)}
                                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all whitespace-nowrap flex-shrink-0`}
                                    style={{
                                        backgroundColor: isActive ? theme.colors.activeBg : theme.colors.bg,
                                        borderColor: isActive ? theme.colors.activeBorder : theme.colors.border,
                                        backdropFilter: 'blur(8px)',
                                    }}
                                >
                                    <span
                                        className="text-xs font-medium"
                                        style={{ color: isActive ? '#6366f1' : theme.colors.text.secondary }}
                                    >
                                        {item.query}
                                    </span>
                                </motion.button>
                            </motion.div>
                        );
                    })}
                </AnimatePresence>
            </div>
        </div>
    );
}

export default ContextRibbon;
