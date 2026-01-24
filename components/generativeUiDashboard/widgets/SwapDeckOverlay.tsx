/**
 * SwapDeckOverlay - Glassmorphic overlay for component swapping.
 *
 * Component: SwapDeckOverlay
 * Called from: ComponentRenderer (when swap deck is open)
 * Invokes: useComponentSwap(), Framer Motion
 * Why: Provides elegant, accessible UI for component swap selection.
 *      Desktop: Glassmorphic pill at bottom of component.
 *      Mobile: Bottom sheet (full width).
 *
 * Features:
 * - Glassmorphic design with blur backdrop
 * - Smooth Framer Motion animations
 * - Keyboard navigation (Tab, Left/Right arrows, Enter, Escape)
 * - Hover preview with 150ms debounce
 * - Click to commit
 * - Mobile-responsive bottom sheet variant
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, X, Loader2 } from 'lucide-react';
import {
    useComponentSwap,
    getComponentIcon,
    getComponentLabel,
    type SwapTarget,
} from '../context/ComponentSwapContext';
import { WidgetSkeleton, componentTypeToVariant, type SkeletonVariant } from '../renderer/widgets/WidgetSkeleton';

// ============================================================================
// Types
// ============================================================================

export interface SwapDeckOverlayProps {
    /** Component ID being swapped */
    componentId: string;
    /** Original component type */
    componentType: string;
    /** Whether the overlay is open */
    isOpen: boolean;
    /** Callback to close the overlay */
    onClose: () => void;
}

// ============================================================================
// Animation Configs
// ============================================================================

/** Desktop deck appear animation */
const deckDesktopVariants = {
    hidden: { opacity: 0, y: 20, scale: 0.95 },
    visible: { opacity: 1, y: 0, scale: 1 },
    exit: { opacity: 0, y: 10, scale: 0.98 },
};

/** Mobile sheet animation */
const sheetMobileVariants = {
    hidden: { y: '100%' },
    visible: { y: 0 },
    exit: { y: '100%' },
};

/** Item hover animation */
const itemHoverVariants = {
    idle: { scale: 1 },
    hover: { scale: 1.08 },
};

const springTransition = {
    type: 'spring' as const,
    stiffness: 400,
    damping: 25,
};

const easeTransition = {
    duration: 0.2,
    ease: [0.4, 0, 0.2, 1],
};

// ============================================================================
// Hooks
// ============================================================================

/**
 * Simple media query hook for mobile detection.
 */
function useMediaQuery(query: string): boolean {
    const [matches, setMatches] = useState(false);

    useEffect(() => {
        if (typeof window === 'undefined') return;

        const mediaQuery = window.matchMedia(query);
        setMatches(mediaQuery.matches);

        const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
        mediaQuery.addEventListener('change', handler);

        return () => mediaQuery.removeEventListener('change', handler);
    }, [query]);

    return matches;
}

// ============================================================================
// Component
// ============================================================================

export function SwapDeckOverlay({
    componentId,
    componentType,
    isOpen,
    onClose,
}: SwapDeckOverlayProps): React.ReactElement | null {
    const {
        previewSwap,
        commitSwap,
        cancelPreview,
        getSwappedType,
        getSwapTargets,
        isPreviewing,
        swapLoading,
        hasDataForComponent,
        fetchDataForPreview,
        previewLoading,
    } = useComponentSwap();

    const isMobile = useMediaQuery('(max-width: 768px)');
    const [focusedIndex, setFocusedIndex] = useState(-1);
    const [hoveredTarget, setHoveredTarget] = useState<string | null>(null);
    const [showSkeleton, setShowSkeleton] = useState(false);
    const previewTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const fetchAbortRef = useRef(false);
    const containerRef = useRef<HTMLDivElement>(null);
    const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

    const swapTargets = getSwapTargets(componentType);
    const currentType = getSwappedType(componentId, componentType);
    const isLoading = swapLoading.get(componentId) ?? false;
    const isInPreview = isPreviewing(componentId);

    // Focus container when opened
    useEffect(() => {
        if (isOpen && containerRef.current) {
            containerRef.current.focus();
        }
    }, [isOpen]);

    // Reset state when closed
    useEffect(() => {
        if (!isOpen) {
            setFocusedIndex(-1);
            setHoveredTarget(null);
            setShowSkeleton(false);
            fetchAbortRef.current = true;
        }
    }, [isOpen]);

    /**
     * Handle preview on hover with debounce.
     * If component has no data, shows skeleton and fetches data first.
     */
    const handleItemHover = useCallback(
        (target: SwapTarget) => {
            // Clear any pending preview and abort any in-flight fetch
            if (previewTimeoutRef.current) {
                clearTimeout(previewTimeoutRef.current);
            }
            fetchAbortRef.current = true;

            setHoveredTarget(target.targetType);

            // Don't preview if already on this type
            if (target.targetType === currentType) return;

            // Reset abort flag for new operation
            fetchAbortRef.current = false;

            // Debounce preview to avoid spam on quick hovers
            previewTimeoutRef.current = setTimeout(async () => {
                // Check if component has data
                const hasData = hasDataForComponent(componentId);

                if (!hasData) {
                    // Show skeleton while fetching data
                    setShowSkeleton(true);

                    // Fetch data
                    const fetched = await fetchDataForPreview(componentId, componentType);

                    // Check if user moved to different target while fetching
                    if (fetchAbortRef.current) {
                        setShowSkeleton(false);
                        return;
                    }

                    setShowSkeleton(false);

                    if (!fetched) {
                        console.warn('[SwapDeck] No data available for preview');
                        return;
                    }
                }

                // Now proceed with preview
                const result = await previewSwap(componentId, componentType, target.targetType);
                if (!result.success) {
                    console.warn('[SwapDeck] Preview failed:', result.error);
                }
            }, 150);
        },
        [componentId, componentType, currentType, previewSwap, hasDataForComponent, fetchDataForPreview]
    );

    /**
     * Cancel preview when leaving item.
     */
    const handleItemLeave = useCallback(() => {
        if (previewTimeoutRef.current) {
            clearTimeout(previewTimeoutRef.current);
        }
        fetchAbortRef.current = true;
        setHoveredTarget(null);
        setShowSkeleton(false);

        if (isInPreview) {
            cancelPreview(componentId);
        }
    }, [componentId, isInPreview, cancelPreview]);

    /**
     * Handle item click - commit the swap.
     * If component has no data, fetches data first then commits.
     */
    const handleItemClick = useCallback(
        async (target: SwapTarget) => {
            // Clear any pending preview
            if (previewTimeoutRef.current) {
                clearTimeout(previewTimeoutRef.current);
            }

            // If already previewing this target, commit it
            if (isInPreview) {
                commitSwap(componentId);
                onClose();
                return;
            }

            // Check if component has data
            const hasData = hasDataForComponent(componentId);

            if (!hasData) {
                // Show skeleton while fetching data
                setShowSkeleton(true);

                const fetched = await fetchDataForPreview(componentId, componentType);
                setShowSkeleton(false);

                if (!fetched) {
                    console.error('[SwapDeck] Cannot swap - no data available');
                    return;
                }
            }

            // Execute swap
            const result = await previewSwap(componentId, componentType, target.targetType);
            if (result.success) {
                commitSwap(componentId);
                onClose();
            } else {
                console.error('[SwapDeck] Swap failed:', result.error);
            }
        },
        [componentId, componentType, isInPreview, previewSwap, commitSwap, onClose, hasDataForComponent, fetchDataForPreview]
    );

    /**
     * Handle keyboard navigation.
     */
    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            const numTargets = swapTargets.length;

            switch (e.key) {
                case 'Escape':
                    e.preventDefault();
                    if (isInPreview) cancelPreview(componentId);
                    onClose();
                    break;

                case 'ArrowLeft':
                    e.preventDefault();
                    setFocusedIndex((prev) => (prev <= 0 ? numTargets - 1 : prev - 1));
                    break;

                case 'ArrowRight':
                    e.preventDefault();
                    setFocusedIndex((prev) => (prev >= numTargets - 1 ? 0 : prev + 1));
                    break;

                case 'Tab':
                    // Let Tab work naturally for accessibility
                    break;

                case 'Enter':
                case ' ':
                    e.preventDefault();
                    if (focusedIndex >= 0 && focusedIndex < numTargets) {
                        handleItemClick(swapTargets[focusedIndex]);
                    }
                    break;
            }
        },
        [
            swapTargets,
            focusedIndex,
            isInPreview,
            componentId,
            cancelPreview,
            onClose,
            handleItemClick,
        ]
    );

    // Update focus when index changes
    useEffect(() => {
        if (focusedIndex >= 0 && itemRefs.current[focusedIndex]) {
            itemRefs.current[focusedIndex]?.focus();
            // Trigger hover preview for keyboard navigation
            const target = swapTargets[focusedIndex];
            if (target) {
                handleItemHover(target);
            }
        }
    }, [focusedIndex, swapTargets, handleItemHover]);

    /**
     * Handle close - cancel any preview and close.
     */
    const handleClose = useCallback(() => {
        if (previewTimeoutRef.current) {
            clearTimeout(previewTimeoutRef.current);
        }
        fetchAbortRef.current = true;
        setShowSkeleton(false);
        if (isInPreview) {
            cancelPreview(componentId);
        }
        onClose();
    }, [componentId, isInPreview, cancelPreview, onClose]);

    // Determine skeleton variant based on component type
    const skeletonVariant: SkeletonVariant = componentTypeToVariant[componentType] || 'card';
    const isPreviewLoading = showSkeleton || (previewLoading.get(componentId) ?? false);

    if (!isOpen || swapTargets.length === 0) return null;

    // Render mobile bottom sheet or desktop pill
    const variants = isMobile ? sheetMobileVariants : deckDesktopVariants;
    const transition = isMobile
        ? { duration: 0.3, ease: [0.4, 0, 0.2, 1] }
        : easeTransition;

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop for mobile */}
                    {isMobile && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="fixed inset-0 bg-black/50 z-40"
                            onClick={handleClose}
                        />
                    )}

                    {/* Skeleton overlay when loading data for preview */}
                    <AnimatePresence>
                        {isPreviewLoading && (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.2 }}
                                className="absolute inset-0 z-25 bg-slate-900/60 backdrop-blur-sm rounded-xl flex flex-col items-center justify-center p-4"
                            >
                                <WidgetSkeleton
                                    variant={skeletonVariant}
                                    className="w-full h-full"
                                    ariaLabel={`Loading preview data for ${componentType}...`}
                                />
                                <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-2 text-xs text-slate-400">
                                    <Loader2 size={12} className="animate-spin" />
                                    <span>Loading preview data...</span>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Deck/Sheet container */}
                    <motion.div
                        ref={containerRef}
                        variants={variants}
                        initial="hidden"
                        animate="visible"
                        exit="exit"
                        transition={transition}
                        onKeyDown={handleKeyDown}
                        tabIndex={0}
                        role="menu"
                        aria-label="Component swap options"
                        className={`
                            ${isMobile
                                ? 'fixed bottom-0 left-0 right-0 z-50 rounded-t-2xl'
                                : 'absolute bottom-4 left-1/2 -translate-x-1/2 z-30 rounded-full'
                            }
                            backdrop-blur-xl bg-slate-900/80 border border-white/10
                            shadow-2xl shadow-black/40
                            focus:outline-none focus:ring-2 focus:ring-emerald-500/50
                        `}
                    >
                        {/* Mobile header with close button */}
                        {isMobile && (
                            <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
                                <span className="text-sm text-slate-400">
                                    Change visualization
                                </span>
                                <button
                                    onClick={handleClose}
                                    className="p-1 rounded-full hover:bg-slate-700/50 transition-colors"
                                    aria-label="Close"
                                >
                                    <X size={18} className="text-slate-400" />
                                </button>
                            </div>
                        )}

                        {/* Items container */}
                        <div
                            className={`
                                flex items-center gap-1
                                ${isMobile ? 'flex-wrap p-4 justify-center' : 'px-2 py-1.5'}
                            `}
                        >
                            {swapTargets.map((target, index) => {
                                const isCurrentType = currentType === target.targetType;
                                const isHovered = hoveredTarget === target.targetType;
                                const isFocused = focusedIndex === index;

                                return (
                                    <motion.button
                                        key={target.targetType}
                                        ref={(el) => {
                                            itemRefs.current[index] = el;
                                        }}
                                        variants={itemHoverVariants}
                                        initial="idle"
                                        whileHover="hover"
                                        animate={isHovered || isFocused ? 'hover' : 'idle'}
                                        transition={springTransition}
                                        onClick={() => handleItemClick(target)}
                                        onMouseEnter={() => handleItemHover(target)}
                                        onMouseLeave={handleItemLeave}
                                        onFocus={() => setFocusedIndex(index)}
                                        disabled={isLoading}
                                        role="menuitem"
                                        aria-current={isCurrentType ? 'true' : undefined}
                                        className={`
                                            relative flex items-center gap-2
                                            ${isMobile ? 'px-4 py-3 rounded-xl min-w-[120px]' : 'px-3 py-1.5 rounded-full'}
                                            transition-colors duration-150
                                            focus:outline-none focus:ring-2 focus:ring-emerald-500/50
                                            disabled:opacity-50 disabled:cursor-wait
                                            ${isCurrentType
                                                ? 'bg-emerald-500/20 text-emerald-200 border border-emerald-500/30'
                                                : isHovered || isFocused
                                                    ? 'bg-slate-700/60 text-white border border-white/20'
                                                    : 'text-slate-300 hover:bg-slate-700/40'
                                            }
                                        `}
                                        title={target.description}
                                    >
                                        {/* Icon */}
                                        <span className={`text-lg ${isMobile ? '' : 'text-base'}`}>
                                            {target.icon || getComponentIcon(target.targetType)}
                                        </span>

                                        {/* Label */}
                                        <span className={`${isMobile ? 'text-sm' : 'text-xs'} whitespace-nowrap`}>
                                            {target.label || getComponentLabel(target.targetType)}
                                        </span>

                                        {/* Current indicator dot */}
                                        {isCurrentType && (
                                            <motion.span
                                                initial={{ scale: 0 }}
                                                animate={{ scale: 1 }}
                                                className={`
                                                    ${isMobile ? 'ml-auto' : 'ml-1'}
                                                `}
                                            >
                                                <Check size={isMobile ? 16 : 12} className="text-emerald-400" />
                                            </motion.span>
                                        )}

                                        {/* Mode indicator for server swaps (desktop only) */}
                                        {!isMobile && target.mode === 'server' && !isCurrentType && !isHovered && (
                                            <span className="text-[8px] px-1 py-0.5 rounded bg-slate-600/50 text-slate-400">
                                                API
                                            </span>
                                        )}
                                    </motion.button>
                                );
                            })}
                        </div>

                        {/* Keyboard hint (desktop only) */}
                        {!isMobile && (
                            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[10px] text-slate-500 whitespace-nowrap">
                                <kbd className="px-1 py-0.5 bg-slate-800 rounded text-slate-400">
                                    {'\u2190'}
                                </kbd>
                                {' / '}
                                <kbd className="px-1 py-0.5 bg-slate-800 rounded text-slate-400">
                                    {'\u2192'}
                                </kbd>
                                {' navigate \u2022 '}
                                <kbd className="px-1 py-0.5 bg-slate-800 rounded text-slate-400">
                                    Enter
                                </kbd>
                                {' select \u2022 '}
                                <kbd className="px-1 py-0.5 bg-slate-800 rounded text-slate-400">
                                    Esc
                                </kbd>
                                {' close'}
                            </div>
                        )}
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}

export default SwapDeckOverlay;
