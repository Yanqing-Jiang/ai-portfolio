/**
 * ComponentActionMenu - Floating menu for selected component actions.
 *
 * Component: ComponentActionMenu
 * Called from: GenerativeUIPage.tsx (rendered conditionally when component selected)
 * Invokes: useComponentSelection(), useComponentSwap(), useLayoutPreferences()
 * Why: Provides unified action interface for targeted component operations.
 *      Now uses catalog for swap options with mode indicators.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, Undo2, X, Eye, EyeOff, Crosshair, GripVertical, Check } from 'lucide-react';
import { useComponentSelection } from '../context/ComponentSelectionContext';
import { useComponentSwap, getComponentIcon, getComponentLabel } from '../context/ComponentSwapContext';
import { useLayoutPreferences } from '../context/LayoutContext';

// ============================================================================
// Component
// ============================================================================

export function ComponentActionMenu() {
    const { selectedComponent, showActionMenu, clearSelection } = useComponentSelection();
    const { requestSwap, isSwapped, resetSwap, getSwapTargets, swapLoading, previewSwap, cancelPreview } = useComponentSwap();
    const { toggleWidget, isWidgetHidden, toggleReorderMode, preferences } = useLayoutPreferences();
    const [swapError, setSwapError] = useState<string | null>(null);
    const prefetchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // Extract values safely (may be null)
    const componentId = selectedComponent?.componentId ?? '';
    const componentType = selectedComponent?.componentType ?? '';
    const originalType = selectedComponent?.originalType ?? '';
    const boundingRect = selectedComponent?.boundingRect;

    // Escape key handler - close menu on Escape
    useEffect(() => {
        if (!showActionMenu) return;
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                clearSelection();
            }
        };
        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [showActionMenu, clearSelection]);

    // Click-outside handler - close menu when clicking outside
    useEffect(() => {
        if (!showActionMenu) return;
        const handleClickOutside = (e: MouseEvent) => {
            const target = e.target as HTMLElement;
            // Don't close if clicking on the menu itself or on a component
            if (target.closest('[role="dialog"]') || target.closest('[data-component-id]')) {
                return;
            }
            clearSelection();
        };
        // Use capture to handle before other handlers
        document.addEventListener('mousedown', handleClickOutside, { capture: true });
        return () => document.removeEventListener('mousedown', handleClickOutside, { capture: true });
    }, [showActionMenu, clearSelection]);

    // Handle hover to preview
    const handlePreview = useCallback((targetType: string) => {
        if (!componentId || !originalType) return;
        
        if (prefetchTimeoutRef.current) {
            clearTimeout(prefetchTimeoutRef.current);
        }

        prefetchTimeoutRef.current = setTimeout(() => {
            previewSwap(componentId, originalType, targetType);
        }, 150); 
    }, [componentId, originalType, previewSwap]);

    const handleCancelPreview = useCallback(() => {
        if (prefetchTimeoutRef.current) {
            clearTimeout(prefetchTimeoutRef.current);
        }
        cancelPreview(componentId);
    }, [componentId, cancelPreview]);

    const handleSwap = useCallback(async (targetType: string) => {
        if (!componentId || !originalType) return;
        setSwapError(null);
        // Commit the swap (handles both client and server)
        const result = await requestSwap(componentId, originalType, targetType);
        if (!result.success) {
            setSwapError(result.error || 'Swap failed');
        } else {
            // Close menu after successful swap
            clearSelection();
        }
    }, [componentId, originalType, requestSwap, clearSelection]);

    // Don't render if nothing selected or menu hidden (after all hooks)
    if (!selectedComponent || !showActionMenu) return null;

    const swapTargets = getSwapTargets(originalType);
    const isHidden = isWidgetHidden(originalType);
    const swapped = isSwapped(componentId);
    const isLoading = swapLoading.get(componentId) ?? false;

    // Position menu near the selected component (center-biased algorithm)
    const menuWidth = 320; // w-80 = 20rem = 320px
    const menuHeight = 450; // Approximate max height
    const gap = 12;
    const viewportPadding = 16;

    const calculateMenuPosition = (): React.CSSProperties => {
        if (!boundingRect) {
            return {
                position: 'fixed',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                zIndex: 1000,
            };
        }

        // Available space on each side
        const spaceRight = window.innerWidth - boundingRect.right - gap;
        const spaceLeft = boundingRect.left - gap;

        let left: number;

        // Priority: right > left > center overlay
        if (spaceRight >= menuWidth + viewportPadding) {
            // Fits on right
            left = boundingRect.right + gap;
        } else if (spaceLeft >= menuWidth + viewportPadding) {
            // Fits on left
            left = boundingRect.left - menuWidth - gap;
        } else {
            // Center overlay on component
            left = Math.max(
                viewportPadding,
                Math.min(
                    boundingRect.left + (boundingRect.width / 2) - (menuWidth / 2),
                    window.innerWidth - menuWidth - viewportPadding
                )
            );
        }

        // Vertical: align with component top, constrained to viewport
        const top = Math.max(
            viewportPadding,
            Math.min(boundingRect.top, window.innerHeight - menuHeight - viewportPadding)
        );

        return {
            position: 'fixed',
            top,
            left,
            maxHeight: window.innerHeight - 2 * viewportPadding,
            overflowY: 'auto',
            zIndex: 1000,
        };
    };

    const menuStyle = calculateMenuPosition();

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0, y: -8, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -8, scale: 0.96 }}
                transition={{
                    type: 'spring',
                    stiffness: 400,
                    damping: 28,
                    mass: 0.8,
                }}
                className="bg-slate-900/95 backdrop-blur-xl border border-slate-700 rounded-xl shadow-2xl shadow-black/50 p-3 w-80"
                style={menuStyle}
                role="dialog"
                aria-label={`Actions for ${getComponentLabel(componentType)}`}
                data-ignore-selection="true"
                onMouseLeave={handleCancelPreview} // Revert preview on mouse leave
            >
                {/* Header */}
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-700">
                    <div className="flex items-center gap-2">
                        <span className="text-lg">{getComponentIcon(componentType)}</span>
                        <span className="text-sm font-medium text-white">
                            {getComponentLabel(componentType)}
                        </span>
                        {swapped && (
                            <span className="text-[10px] bg-slate-600/50 text-slate-300 px-1.5 py-0.5 rounded">
                                Swapped
                            </span>
                        )}
                        {isLoading && (
                            <Loader2 size={14} className="animate-spin text-gray-400" />
                        )}
                    </div>
                    <button
                        onClick={clearSelection}
                        className="text-slate-500 hover:text-white transition-colors p-1 rounded hover:bg-slate-700"
                        aria-label="Close menu"
                    >
                        <X size={14} />
                    </button>
                </div>

                {/* Error message */}
                {swapError && (
                    <div className="mb-2 px-2 py-1.5 rounded bg-red-500/20 text-red-400 text-xs">
                        {swapError}
                    </div>
                )}

                {/* Actions */}
                <div className="space-y-1">
                    {/* Swap options from catalog */}
                    {swapTargets.length > 0 && (
                        <div className="mb-2">
                            <p className="text-[10px] text-slate-500 mb-1 px-2 uppercase tracking-wide">
                                Options
                            </p>
                            {swapTargets.map(target => {
                                return (
                                    <button
                                        key={target.targetType}
                                        onClick={() => handleSwap(target.targetType)}
                                        onMouseEnter={() => handlePreview(target.targetType)}
                                        disabled={isLoading}
                                        className={`
                                            w-full text-left px-2 py-1.5 rounded-lg text-sm flex items-center gap-2 transition-all
                                            ${isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:bg-slate-700/50 hover:scale-[1.01]'}
                                            text-slate-300
                                        `}
                                        title={target.description}
                                    >
                                        <span className="text-base">{target.icon}</span>
                                        <span className="flex-1">View as {target.label}</span>
                                        {/* Mode indicator */}
                                        {target.mode === 'server' && (
                                            <span
                                                className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 font-medium"
                                                title="Requires data fetch"
                                            >
                                                API
                                            </span>
                                        )}
                                    </button>
                                );
                            })}
                            {swapped && (
                                <button
                                    onClick={() => {
                                        resetSwap(componentId);
                                        clearSelection();
                                    }}
                                    disabled={isLoading}
                                    className={`
                                        w-full text-left px-2 py-1.5 rounded-lg text-sm text-slate-300 flex items-center gap-2 transition-colors
                                        ${isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:bg-slate-700/50'}
                                    `}
                                >
                                    <Undo2 size={16} className="text-gray-400" />
                                    <span>Revert to original</span>
                                </button>
                            )}
                        </div>
                    )}

                    {/* Divider if swap options exist */}
                    {swapTargets.length > 0 && (
                        <div className="border-t border-slate-700/50 my-2" />
                    )}

                    {/* Visibility toggle */}
                    <button
                        onClick={() => {
                            toggleWidget(originalType);
                            clearSelection();
                        }}
                        className="w-full text-left px-2 py-1.5 rounded-lg hover:bg-slate-700/50 text-sm text-slate-300 flex items-center gap-2 transition-colors"
                    >
                        {isHidden ? (
                            <Eye size={16} className="text-gray-400" />
                        ) : (
                            <EyeOff size={16} className="text-gray-400" />
                        )}
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
                        <Crosshair size={16} className="text-gray-400" />
                        <span>Focus on this</span>
                    </button>

                    {/* Divider before reorder */}
                    <div className="border-t border-slate-700/50 my-2" />

                    {/* Reorder widgets toggle */}
                    <button
                        onClick={() => {
                            toggleReorderMode();
                            clearSelection();
                        }}
                        className={`
                            w-full text-left px-2 py-1.5 rounded-lg text-sm flex items-center gap-2 transition-colors
                            ${preferences.reorderModeEnabled
                                ? 'bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30'
                                : 'text-slate-300 hover:bg-slate-700/50'}
                        `}
                    >
                        {preferences.reorderModeEnabled ? (
                            <Check size={16} className="text-emerald-400" />
                        ) : (
                            <GripVertical size={16} className="text-gray-400" />
                        )}
                        <span>{preferences.reorderModeEnabled ? 'Done reordering' : 'Reorder widgets'}</span>
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
