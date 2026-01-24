/**
 * SwapButton - Trigger button for component swapping.
 *
 * Component: SwapButton
 * Called from: ComponentRenderer (wrapper)
 * Invokes: useComponentSwap(), SwapDeckOverlay
 * Why: Provides intuitive trigger for the swap deck overlay.
 *      Refactored to delegate all swap UI to SwapDeckOverlay.
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, Undo2, Loader2, Eye } from 'lucide-react';
import { useComponentSwap } from '../context/ComponentSwapContext';
import { SwapDeckOverlay } from './SwapDeckOverlay';

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
// Component
// ============================================================================

export function SwapButton({ componentId, componentType }: SwapButtonProps) {
    const {
        isSwapped,
        isPreviewing,
        resetSwap,
        getSwapTargets,
        swapLoading,
    } = useComponentSwap();

    const [isDeckOpen, setIsDeckOpen] = useState(false);

    const swapTargets = getSwapTargets(componentType);
    const swapped = isSwapped(componentId);
    const isLoading = swapLoading.get(componentId) ?? false;
    const isInPreview = isPreviewing(componentId);

    // Don't render if no swap options available
    if (swapTargets.length === 0) return null;

    /**
     * Handle button click - toggle deck or handle special states.
     */
    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();

        if (isLoading) return;

        // If swapped and deck is closed, show option to revert or open deck
        setIsDeckOpen((prev) => !prev);
    };

    /**
     * Handle reset click - revert to original.
     */
    const handleReset = (e: React.MouseEvent) => {
        e.stopPropagation();
        resetSwap(componentId);
        setIsDeckOpen(false);
    };

    return (
        <>
            {/* Trigger button positioned at top-right */}
            <div className="absolute top-2 right-2 z-20 flex items-center gap-1">
                {/* Reset button (only shown when swapped) */}
                <AnimatePresence>
                    {swapped && !isDeckOpen && (
                        <motion.button
                            initial={{ opacity: 0, scale: 0.8 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.8 }}
                            transition={{ duration: 0.15 }}
                            onClick={handleReset}
                            className="p-1.5 rounded-lg bg-slate-800/80 border border-slate-600 hover:bg-slate-700/80 transition-colors"
                            title="Reset to original"
                            aria-label="Reset to original component"
                        >
                            <Undo2 size={14} className="text-slate-400" />
                        </motion.button>
                    )}
                </AnimatePresence>

                {/* Main swap trigger button */}
                <button
                    onClick={handleClick}
                    disabled={isLoading}
                    className={`
                        p-2 rounded-lg transition-all duration-150
                        ${isLoading
                            ? 'bg-slate-800/80 border border-slate-600 cursor-wait'
                            : isInPreview
                                ? 'bg-emerald-900/50 border border-emerald-500/50 ring-2 ring-emerald-500/30'
                                : isDeckOpen
                                    ? 'bg-slate-700/80 border border-slate-500 ring-2 ring-slate-400/30'
                                    : swapped
                                        ? 'bg-emerald-900/30 border border-emerald-500/30 hover:bg-emerald-800/40'
                                        : 'bg-slate-800/80 border border-slate-700 hover:bg-slate-700/80 hover:border-slate-500'
                        }
                    `}
                    title={
                        isLoading
                            ? 'Swapping...'
                            : isInPreview
                                ? 'Preview active'
                                : isDeckOpen
                                    ? 'Close swap options'
                                    : swapped
                                        ? 'Change visualization'
                                        : 'Swap visualization'
                    }
                    aria-label={
                        isLoading
                            ? 'Swapping'
                            : isInPreview
                                ? 'Preview active'
                                : isDeckOpen
                                    ? 'Close swap options'
                                    : 'Open swap options'
                    }
                    aria-expanded={isDeckOpen}
                    aria-haspopup="menu"
                >
                    {isLoading ? (
                        <Loader2 size={16} className="animate-spin text-gray-400" />
                    ) : isInPreview ? (
                        <Eye size={16} className="text-emerald-400" />
                    ) : (
                        <Sparkles
                            size={16}
                            className={
                                isDeckOpen
                                    ? 'text-slate-200'
                                    : swapped
                                        ? 'text-emerald-400'
                                        : 'text-gray-400'
                            }
                        />
                    )}
                </button>
            </div>

            {/* Swap Deck Overlay */}
            <SwapDeckOverlay
                componentId={componentId}
                componentType={componentType}
                isOpen={isDeckOpen}
                onClose={() => setIsDeckOpen(false)}
            />
        </>
    );
}

export default SwapButton;
