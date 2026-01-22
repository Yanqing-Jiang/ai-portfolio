/**
 * SwapButton - Appears on hovering over swappable components.
 *
 * Component: SwapButton
 * Called from: ComponentRenderer (wrapper)
 * Invokes: useComponentSwap(), swapCatalog
 * Why: Provides intuitive UI for component swapping via hover menu.
 *      Now uses catalog for swap targets with mode indicators.
 *      Phase 2: Preview-first flow - hover shows preview, click commits.
 */

import { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { RefreshCw, Undo2, Loader2, Check, Eye } from 'lucide-react';
import { useComponentSwap, getComponentIcon, getComponentLabel, type SwapTarget } from '../context/ComponentSwapContext';

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
        previewSwap,
        commitSwap,
        cancelPreview,
        isSwapped,
        isPreviewing,
        resetSwap,
        getSwappedType,
        getSwapTargets,
        swapLoading,
    } = useComponentSwap();
    const [isOpen, setIsOpen] = useState(false);
    const [hoveredTarget, setHoveredTarget] = useState<string | null>(null);
    const previewTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    const swapTargets = getSwapTargets(componentType);
    const currentType = getSwappedType(componentId, componentType);
    const swapped = isSwapped(componentId);
    const isLoading = swapLoading.get(componentId) ?? false;
    const isInPreview = isPreviewing(componentId);

    // Don't render if no swap options available
    if (swapTargets.length === 0) return null;

    /**
     * Phase 2: Preview-first flow - hover triggers preview with debounce
     */
    const handleOptionHover = useCallback((target: SwapTarget) => {
        // Clear any pending preview
        if (previewTimeoutRef.current) {
            clearTimeout(previewTimeoutRef.current);
        }

        setHoveredTarget(target.targetType);

        // Don't preview if already on this type
        if (target.targetType === currentType) return;

        // Debounce preview to avoid spam on quick hovers
        previewTimeoutRef.current = setTimeout(async () => {
            const result = await previewSwap(componentId, componentType, target.targetType);
            if (!result.success) {
                console.warn('[SwapButton] Preview failed:', result.error);
            }
        }, 150); // 150ms debounce
    }, [componentId, componentType, currentType, previewSwap]);

    /**
     * Phase 2: Cancel preview when leaving option
     */
    const handleOptionLeave = useCallback(() => {
        if (previewTimeoutRef.current) {
            clearTimeout(previewTimeoutRef.current);
        }
        setHoveredTarget(null);
        // Cancel preview when mouse leaves option
        if (isInPreview) {
            cancelPreview(componentId);
        }
    }, [componentId, isInPreview, cancelPreview]);

    /**
     * Phase 2: Click commits the preview (or starts if no preview active)
     */
    const handleOptionClick = useCallback(async (target: SwapTarget) => {
        // Clear any pending preview
        if (previewTimeoutRef.current) {
            clearTimeout(previewTimeoutRef.current);
        }

        // If already previewing this target, commit it
        if (isInPreview) {
            commitSwap(componentId);
            setIsOpen(false);
            return;
        }

        // Otherwise, execute swap directly (for quick clicks without hover)
        const result = await previewSwap(componentId, componentType, target.targetType);
        if (result.success) {
            commitSwap(componentId);
            setIsOpen(false);
        } else {
            console.error('[SwapButton] Swap failed:', result.error);
        }
    }, [componentId, componentType, isInPreview, previewSwap, commitSwap]);

    /**
     * Handle menu close - cancel any active preview
     */
    const handleMenuClose = useCallback(() => {
        if (previewTimeoutRef.current) {
            clearTimeout(previewTimeoutRef.current);
        }
        if (isInPreview) {
            cancelPreview(componentId);
        }
        setIsOpen(false);
        setHoveredTarget(null);
    }, [componentId, isInPreview, cancelPreview]);

    return (
        <div className="absolute top-2 right-2 z-20">
            {/* Swap toggle button */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    if (isOpen) {
                        handleMenuClose();
                    } else {
                        setIsOpen(true);
                    }
                }}
                disabled={isLoading}
                className={`
                    p-2 rounded-lg transition-colors duration-150
                    ${isLoading
                        ? 'bg-slate-800/80 border border-slate-600 cursor-wait'
                        : isInPreview
                            ? 'bg-emerald-900/50 border border-emerald-500/50'
                            : swapped
                                ? 'bg-slate-600/50 border border-slate-500'
                                : 'bg-slate-800/80 border border-slate-700 hover:bg-slate-700/80'
                    }
                `}
                title={isLoading ? 'Swapping...' : isInPreview ? 'Preview active' : swapped ? 'Click to revert or swap again' : 'Swap component visualization'}
                aria-label={isLoading ? 'Swapping' : isInPreview ? 'Preview active' : swapped ? 'Revert swap' : 'Swap visualization'}
                aria-expanded={isOpen}
                aria-haspopup="menu"
            >
                {isLoading ? (
                    <Loader2 size={16} className="animate-spin text-gray-400" />
                ) : isInPreview ? (
                    <Eye size={16} className="text-emerald-400" />
                ) : swapped ? (
                    <Undo2 size={16} className="text-slate-300" />
                ) : (
                    <RefreshCw size={16} className="text-gray-400" />
                )}
            </button>

            {/* Dropdown menu */}
            <AnimatePresence>
                {isOpen && !isLoading && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9, y: -4 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.9, y: -4 }}
                        transition={{ duration: 0.15, ease: 'easeOut' }}
                        className="absolute top-full right-0 mt-1 bg-slate-800/95 backdrop-blur-xl border border-slate-700 rounded-xl p-2 shadow-2xl shadow-black/40 min-w-[200px] z-50"
                        role="menu"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Current type indicator */}
                        <div className="px-2 py-1.5 border-b border-slate-700/50 mb-1">
                            <p className="text-[10px] text-slate-500 uppercase tracking-wide">Current</p>
                            <p className="text-sm text-slate-300 flex items-center gap-2 mt-0.5">
                                <span>{getComponentIcon(currentType)}</span>
                                <span>{getComponentLabel(currentType)}</span>
                            </p>
                        </div>

                        {/* Swap options with mode indicators - Phase 2: preview on hover */}
                        <p className="text-[10px] text-gray-500 px-2 mb-1 mt-2">
                            {isInPreview ? 'Preview active (click to apply):' : 'Hover to preview, click to apply:'}
                        </p>
                        {swapTargets.map(target => {
                            const isCurrentType = currentType === target.targetType;
                            const isHovered = hoveredTarget === target.targetType;

                            return (
                                <button
                                    key={target.targetType}
                                    role="menuitem"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleOptionClick(target);
                                    }}
                                    onMouseEnter={() => handleOptionHover(target)}
                                    onMouseLeave={handleOptionLeave}
                                    className={`
                                        w-full text-left px-2 py-1.5 rounded-lg text-sm flex items-center gap-2
                                        transition-colors duration-150
                                        ${isCurrentType
                                            ? 'bg-slate-600/50 text-slate-200'
                                            : isHovered
                                                ? 'bg-emerald-900/30 text-emerald-200 ring-1 ring-emerald-500/30'
                                                : 'text-gray-300 hover:bg-slate-700/50'
                                        }
                                    `}
                                    title={target.description}
                                >
                                    <span className="text-base">{target.icon}</span>
                                    <span className="flex-1">{target.label}</span>
                                    {/* Preview indicator */}
                                    {isHovered && !isCurrentType && (
                                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-900/50 text-emerald-300 font-medium">
                                            Preview
                                        </span>
                                    )}
                                    {/* Mode indicator */}
                                    {target.mode === 'server' && !isHovered && (
                                        <span
                                            className="text-[9px] px-1.5 py-0.5 rounded bg-slate-600/50 text-gray-400 font-medium"
                                            title="Requires data transformation"
                                        >
                                            API
                                        </span>
                                    )}
                                    {isCurrentType && (
                                        <Check size={14} className="text-slate-300" />
                                    )}
                                </button>
                            );
                        })}

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
                                    className="w-full text-left px-2 py-1.5 rounded-lg text-sm text-gray-400 flex items-center gap-2 hover:bg-slate-700/50 transition-colors"
                                >
                                    <Undo2 size={16} />
                                    <span>Revert to {getComponentLabel(componentType)}</span>
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
