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
import { Loader2, Undo2, X, Eye, EyeOff, Crosshair, Sparkles, Lightbulb } from 'lucide-react';
import { useComponentSelection } from '../context/ComponentSelectionContext';
import { useComponentSwap, getComponentIcon, getComponentLabel, type SwapTarget, type SwapSuggestion } from '../context/ComponentSwapContext';
import { useLayoutPreferences } from '../context/LayoutContext';

// ============================================================================
// Speculative Pre-fetch Cache for Snappy UX
// ============================================================================

/**
 * Cache for speculative pre-fetched swap data.
 * Key format: `${dashboardId}:${componentId}:${targetType}`
 * Caches are invalidated after 60 seconds.
 */
const speculativeCache = new Map<string, { data: unknown; timestamp: number }>();
const CACHE_TTL_MS = 60000; // 60 seconds

/**
 * Pre-fetch swap data on hover for instant swap experience.
 * Called when user hovers over a swap option.
 */
async function prefetchSwapData(
    dashboardId: string | null,
    componentId: string,
    fromType: string,
    toType: string
): Promise<void> {
    if (!dashboardId) return;

    const cacheKey = `${dashboardId}:${componentId}:${toType}`;
    const cached = speculativeCache.get(cacheKey);

    // Skip if already cached and fresh
    if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
        return;
    }

    try {
        const response = await fetch(`/api/dash/${dashboardId}/swap`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                component_id: componentId,
                from_type: fromType,
                to_type: toType,
            }),
        });

        if (response.ok) {
            const result = await response.json();
            speculativeCache.set(cacheKey, {
                data: result.transformed_data,
                timestamp: Date.now(),
            });
            console.log('[Speculative] Pre-fetched swap data for', toType);
        }
    } catch (error) {
        // Silently fail - this is speculative, not critical
        console.debug('[Speculative] Pre-fetch failed:', error);
    }
}

/**
 * Get cached swap data if available.
 */
function getCachedSwapData(
    dashboardId: string | null,
    componentId: string,
    toType: string
): unknown | null {
    if (!dashboardId) return null;

    const cacheKey = `${dashboardId}:${componentId}:${toType}`;
    const cached = speculativeCache.get(cacheKey);

    if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
        return cached.data;
    }

    return null;
}

// ============================================================================
// Component
// ============================================================================

export function ComponentActionMenu() {
    const { selectedComponent, showActionMenu, clearSelection } = useComponentSelection();
    const { requestSwap, isSwapped, resetSwap, getSwapTargets, swapLoading, dashboardId, suggestSwaps, previewSwap, cancelPreview } = useComponentSwap();
    const { toggleWidget, isWidgetHidden } = useLayoutPreferences();
    const [swapError, setSwapError] = useState<string | null>(null);
    const [suggestions, setSuggestions] = useState<SwapSuggestion[]>([]);
    const prefetchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // Extract values safely (may be null)
    const componentId = selectedComponent?.componentId ?? '';
    const componentType = selectedComponent?.componentType ?? '';
    const originalType = selectedComponent?.originalType ?? '';
    const boundingRect = selectedComponent?.boundingRect;

    // Fetch suggestions on open
    useEffect(() => {
        if (componentId && originalType && showActionMenu) {
            suggestSwaps(componentId, originalType).then(setSuggestions);
        }
    }, [componentId, originalType, showActionMenu, suggestSwaps]);

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
        }
    }, [componentId, originalType, requestSwap]);

    // Don't render if nothing selected or menu hidden (after all hooks)
    if (!selectedComponent || !showActionMenu) return null;

    const swapTargets = getSwapTargets(originalType);
    const isHidden = isWidgetHidden(originalType);
    const swapped = isSwapped(componentId);
    const isLoading = swapLoading.get(componentId) ?? false;

    // Position menu near the selected component
    // Use smooth constraint: stay on right side, but slide left to stay in viewport
    const menuWidth = 288; // w-72 = 18rem = 288px
    const rightMargin = 10;
    const viewportPadding = 10;

    const menuStyle: React.CSSProperties = boundingRect ? {
        position: 'fixed',
        top: Math.min(boundingRect.top + 10, window.innerHeight - 400),
        // Calculate ideal position on right, then constrain to viewport
        left: Math.min(
            boundingRect.right + rightMargin,                    // Ideal: right of component
            window.innerWidth - menuWidth - viewportPadding     // Max: stay in viewport
        ),
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
                className="bg-slate-900/95 backdrop-blur-xl border border-slate-700 rounded-xl shadow-2xl shadow-black/50 p-3 w-72"
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

                    {/* AI Suggestions */}
                    {suggestions.length > 0 && (
                        <div className="mb-3">
                            <p className="text-[10px] text-indigo-400 mb-1 px-2 uppercase tracking-wide flex items-center gap-1">
                                <Sparkles size={10} />
                                Smart Suggestions
                            </p>
                            {suggestions.map(s => (
                                <button
                                    key={`suggest-${s.targetType}`}
                                    onClick={() => handleSwap(s.targetType)}
                                    onMouseEnter={() => handlePreview(s.targetType)}
                                    className="w-full text-left px-2 py-2 rounded-lg text-sm bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 mb-1 flex items-start gap-2 transition-all"
                                >
                                    <span className="text-lg mt-0.5">{getComponentIcon(s.targetType)}</span>
                                    <div className="flex-1">
                                        <span className="text-indigo-200 font-medium block text-xs">{getComponentLabel(s.targetType)}</span>
                                        <span className="text-[10px] text-indigo-300/70 leading-tight block">{s.reason}</span>
                                    </div>
                                    <div className="text-[9px] font-bold text-indigo-400 bg-indigo-950/50 px-1.5 py-0.5 rounded-full">
                                        {Math.round(s.score * 100)}%
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Swap options from catalog */}
                    {swapTargets.length > 0 && (
                        <div className="mb-2">
                            <p className="text-[10px] text-slate-500 mb-1 px-2 uppercase tracking-wide">
                                All Options
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
                                    onClick={() => resetSwap(componentId)}
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
                        onClick={() => toggleWidget(originalType)}
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
