/**
 * ComponentActionMenu - Floating menu for selected component actions.
 *
 * Component: ComponentActionMenu
 * Called from: GenerativeUIPage.tsx (rendered conditionally when component selected)
 * Invokes: useComponentSelection(), useComponentSwap(), useLayoutPreferences()
 * Why: Provides unified action interface for targeted component operations.
 */

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useComponentSelection } from '../context/ComponentSelectionContext';
import { useComponentSwap, getSwapOptions } from '../context/ComponentSwapContext';
import { useLayoutPreferences } from '../context/LayoutContext';

// ============================================================================
// Icon mappings
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

export function ComponentActionMenu() {
    const { selectedComponent, showActionMenu, clearSelection } = useComponentSelection();
    const { swapComponent, isSwapped, resetSwap } = useComponentSwap();
    const { toggleWidget, isWidgetHidden } = useLayoutPreferences();

    // Don't render if nothing selected or menu hidden
    if (!selectedComponent || !showActionMenu) return null;

    const { componentId, componentType, originalType, boundingRect } = selectedComponent;
    const swapOptions = getSwapOptions(originalType);
    const isHidden = isWidgetHidden(originalType);
    const swapped = isSwapped(componentId);

    // Position menu near the selected component
    const menuStyle: React.CSSProperties = boundingRect ? {
        position: 'fixed',
        top: Math.min(boundingRect.top + 10, window.innerHeight - 350),
        left: Math.min(boundingRect.right + 10, window.innerWidth - 280),
        zIndex: 1000,
    } : {
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 1000,
    };

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0, x: -10, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -10, scale: 0.95 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
                className="bg-slate-900/95 backdrop-blur-xl border border-slate-700 rounded-xl shadow-2xl shadow-black/50 p-3 w-64"
                style={menuStyle}
                role="dialog"
                aria-label={`Actions for ${TYPE_LABELS[componentType] || componentType}`}
            >
                {/* Header */}
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-700">
                    <div className="flex items-center gap-2">
                        <span className="text-lg">{TYPE_ICONS[componentType] || '📦'}</span>
                        <span className="text-sm font-medium text-white">
                            {TYPE_LABELS[componentType] || componentType}
                        </span>
                        {swapped && (
                            <span className="text-[10px] bg-rose-500/20 text-rose-400 px-1.5 py-0.5 rounded">
                                Swapped
                            </span>
                        )}
                    </div>
                    <button
                        onClick={clearSelection}
                        className="text-slate-500 hover:text-white transition-colors p-1 rounded hover:bg-slate-700"
                        aria-label="Close menu"
                    >
                        ✕
                    </button>
                </div>

                {/* Actions */}
                <div className="space-y-1">
                    {/* Swap options */}
                    {swapOptions.length > 0 && (
                        <div className="mb-2">
                            <p className="text-[10px] text-slate-500 mb-1 px-2 uppercase tracking-wide">
                                Swap visualization
                            </p>
                            {swapOptions.map(targetType => (
                                <button
                                    key={targetType}
                                    onClick={() => swapComponent(componentId, originalType, targetType)}
                                    className="w-full text-left px-2 py-1.5 rounded-lg hover:bg-slate-700/50 text-sm text-slate-300 flex items-center gap-2 transition-colors"
                                >
                                    <span className="text-base">{TYPE_ICONS[targetType] || '📦'}</span>
                                    <span>View as {TYPE_LABELS[targetType] || targetType}</span>
                                </button>
                            ))}
                            {swapped && (
                                <button
                                    onClick={() => resetSwap(componentId)}
                                    className="w-full text-left px-2 py-1.5 rounded-lg hover:bg-slate-700/50 text-sm text-amber-400 flex items-center gap-2 transition-colors"
                                >
                                    <span className="text-base">↩️</span>
                                    <span>Revert to original</span>
                                </button>
                            )}
                        </div>
                    )}

                    {/* Divider if swap options exist */}
                    {swapOptions.length > 0 && (
                        <div className="border-t border-slate-700/50 my-2" />
                    )}

                    {/* Visibility toggle */}
                    <button
                        onClick={() => toggleWidget(originalType)}
                        className="w-full text-left px-2 py-1.5 rounded-lg hover:bg-slate-700/50 text-sm text-slate-300 flex items-center gap-2 transition-colors"
                    >
                        <span className="text-base">{isHidden ? '👁️' : '🙈'}</span>
                        <span>{isHidden ? 'Show this widget' : 'Hide this widget'}</span>
                    </button>

                    {/* Focus action - scroll into view */}
                    <button
                        onClick={() => {
                            const el = document.querySelector(`[data-component-id="${componentId}"]`);
                            el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            clearSelection();
                        }}
                        className="w-full text-left px-2 py-1.5 rounded-lg hover:bg-slate-700/50 text-sm text-slate-300 flex items-center gap-2 transition-colors"
                    >
                        <span className="text-base">🎯</span>
                        <span>Focus on this</span>
                    </button>
                </div>

                {/* Footer hint */}
                <div className="mt-3 pt-2 border-t border-slate-700/50">
                    <p className="text-[10px] text-slate-500 px-2">
                        Click outside to dismiss • Press Esc to close
                    </p>
                </div>
            </motion.div>
        </AnimatePresence>
    );
}

export default ComponentActionMenu;
