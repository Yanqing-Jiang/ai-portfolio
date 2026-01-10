/**
 * SwapButton - Appears on hovering over swappable components.
 *
 * Component: SwapButton
 * Called from: ComponentRenderer (wrapper)
 * Invokes: useComponentSwap()
 * Why: Provides intuitive UI for component swapping via hover menu.
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useComponentSwap, getSwapOptions } from '../context/ComponentSwapContext';

// ============================================================================
// Types
// ============================================================================

export interface SwapButtonProps {
    /** Component ID to swap */
    componentId: string;
    /** Original component type (before any swaps) */
    componentType: string;
}

// ============================================================================
// Icon mappings for component types
// ============================================================================

const TYPE_ICONS: Record<string, string> = {
    PriceChart: '📈',
    MetricChart: '📊',
    DataTable: '📋',
    CorrelationMatrix: '🔗',
    ExplainMovePanel: '💡',
    NewsTimeline: '📰',
    KpiCard: '🎯',
    PeerComparePanel: '⚖️',
};

const TYPE_LABELS: Record<string, string> = {
    PriceChart: 'Price Chart',
    MetricChart: 'Metric Chart',
    DataTable: 'Data Table',
    CorrelationMatrix: 'Correlation Matrix',
    ExplainMovePanel: 'AI Explanation',
    NewsTimeline: 'News Timeline',
    KpiCard: 'KPI Card',
    PeerComparePanel: 'Peer Comparison',
};

// ============================================================================
// Component
// ============================================================================

export function SwapButton({ componentId, componentType }: SwapButtonProps) {
    const { swapComponent, isSwapped, resetSwap, getSwappedType } = useComponentSwap();
    const [isOpen, setIsOpen] = useState(false);

    const swapOptions = getSwapOptions(componentType);
    const currentType = getSwappedType(componentId, componentType);
    const swapped = isSwapped(componentId);

    // Don't render if no swap options available
    if (swapOptions.length === 0) return null;

    return (
        <div className="absolute top-2 right-2 z-20">
            {/* Swap toggle button */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    setIsOpen(!isOpen);
                }}
                className={`
                    p-1.5 rounded-lg transition-all duration-200 text-sm
                    ${swapped
                        ? 'bg-rose-500/30 border border-rose-500/50 text-rose-400 shadow-lg shadow-rose-500/20'
                        : 'bg-slate-800/80 border border-slate-700 text-slate-400 hover:border-slate-600 hover:bg-slate-700/80'
                    }
                `}
                title={swapped ? 'Click to revert or swap again' : 'Swap component visualization'}
                aria-label={swapped ? 'Revert swap' : 'Swap visualization'}
                aria-expanded={isOpen}
                aria-haspopup="menu"
            >
                {swapped ? '↩️' : '🔄'}
            </button>

            {/* Dropdown menu */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9, y: -4 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.9, y: -4 }}
                        transition={{ duration: 0.15, ease: 'easeOut' }}
                        className="absolute top-full right-0 mt-1 bg-slate-800/95 backdrop-blur-xl border border-slate-700 rounded-xl p-2 shadow-2xl shadow-black/40 min-w-[180px] z-50"
                        role="menu"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Current type indicator */}
                        <div className="px-2 py-1.5 border-b border-slate-700/50 mb-1">
                            <p className="text-[10px] text-slate-500 uppercase tracking-wide">Current</p>
                            <p className="text-sm text-slate-300 flex items-center gap-2 mt-0.5">
                                <span>{TYPE_ICONS[currentType] || '📦'}</span>
                                <span>{TYPE_LABELS[currentType] || currentType}</span>
                            </p>
                        </div>

                        {/* Swap options */}
                        <p className="text-[10px] text-slate-500 px-2 mb-1 mt-2">Swap to:</p>
                        {swapOptions.map(targetType => (
                            <button
                                key={targetType}
                                role="menuitem"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    swapComponent(componentId, componentType, targetType);
                                    setIsOpen(false);
                                }}
                                className={`
                                    w-full text-left px-2 py-1.5 rounded-lg text-sm flex items-center gap-2
                                    transition-all duration-150
                                    ${currentType === targetType
                                        ? 'bg-rose-500/20 text-rose-400'
                                        : 'text-slate-300 hover:bg-slate-700/50'
                                    }
                                `}
                            >
                                <span className="text-base">{TYPE_ICONS[targetType] || '📦'}</span>
                                <span>{TYPE_LABELS[targetType] || targetType}</span>
                                {currentType === targetType && (
                                    <span className="ml-auto text-rose-400">✓</span>
                                )}
                            </button>
                        ))}

                        {/* Revert option (only if swapped) */}
                        {swapped && (
                            <>
                                <div className="border-t border-slate-700 my-1.5" />
                                <button
                                    role="menuitem"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        resetSwap(componentId);
                                        setIsOpen(false);
                                    }}
                                    className="w-full text-left px-2 py-1.5 rounded-lg text-sm text-amber-400 flex items-center gap-2 hover:bg-slate-700/50 transition-colors"
                                >
                                    <span className="text-base">↩️</span>
                                    <span>Revert to {TYPE_LABELS[componentType] || componentType}</span>
                                </button>
                            </>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

export default SwapButton;
