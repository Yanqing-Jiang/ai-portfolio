/**
 * ComponentSwapContext - Track component type overrides for swapping.
 *
 * Context: ComponentSwapContext
 * Called from: GenerativeUIPage.tsx (provider), widgets (consumer)
 * Invokes: React.createContext
 * Why: Enables client-side component swapping without backend calls.
 *      For example, swapping a PriceChart to MetricChart visualization.
 */

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

// ============================================================================
// Types
// ============================================================================

export interface SwapOverride {
    /** ID of the component being swapped */
    targetComponentId: string;
    /** Original component type before swap */
    originalType: string;
    /** New component type after swap */
    swappedType: string;
    /** Timestamp of when the swap occurred */
    timestamp: number;
}

export interface SwapContextValue {
    /** Map of component ID to swap override */
    swapOverrides: Map<string, SwapOverride>;
    /** Swap a component to a new type */
    swapComponent: (componentId: string, originalType: string, newType: string) => void;
    /** Get the current (potentially swapped) type for a component */
    getSwappedType: (componentId: string, defaultType: string) => string;
    /** Reset a single component swap */
    resetSwap: (componentId: string) => void;
    /** Reset all swaps */
    resetAll: () => void;
    /** Check if a component is currently swapped */
    isSwapped: (componentId: string) => boolean;
}

// ============================================================================
// Swap Groups - Components that can swap between each other
// ============================================================================

/**
 * Defines which component types can swap to which other types.
 * Swaps are bidirectional for components within the same group.
 */
const SWAP_GROUPS: Record<string, string[]> = {
    // Time-series visualization swaps
    PriceChart: ['MetricChart'],
    MetricChart: ['PriceChart'],

    // Tabular data swaps
    DataTable: ['CorrelationMatrix'],
    CorrelationMatrix: ['DataTable'],

    // Narrative/news content swaps
    ExplainMovePanel: ['NewsTimeline'],
    NewsTimeline: ['ExplainMovePanel'],
};

/**
 * Check if a swap from sourceType to targetType is valid.
 */
export function canSwapTo(currentType: string, targetType: string): boolean {
    return SWAP_GROUPS[currentType]?.includes(targetType) ?? false;
}

/**
 * Get available swap options for a component type.
 */
export function getSwapOptions(componentType: string): string[] {
    return SWAP_GROUPS[componentType] || [];
}

// ============================================================================
// Context
// ============================================================================

const SwapContext = createContext<SwapContextValue | null>(null);

// ============================================================================
// Provider
// ============================================================================

export interface ComponentSwapProviderProps {
    children: ReactNode;
}

export function ComponentSwapProvider({ children }: ComponentSwapProviderProps) {
    const [swapOverrides, setSwapOverrides] = useState<Map<string, SwapOverride>>(new Map());

    // Swap a component to a new type
    const swapComponent = useCallback((componentId: string, originalType: string, newType: string) => {
        if (!canSwapTo(originalType, newType)) {
            console.warn(`[ComponentSwapContext] Cannot swap ${originalType} to ${newType}`);
            return;
        }

        setSwapOverrides(prev => {
            const next = new Map(prev);
            next.set(componentId, {
                targetComponentId: componentId,
                originalType,
                swappedType: newType,
                timestamp: Date.now(),
            });
            return next;
        });
    }, []);

    // Get the current (potentially swapped) type for a component
    const getSwappedType = useCallback((componentId: string, defaultType: string): string => {
        const override = swapOverrides.get(componentId);
        return override?.swappedType ?? defaultType;
    }, [swapOverrides]);

    // Reset a single component swap
    const resetSwap = useCallback((componentId: string) => {
        setSwapOverrides(prev => {
            const next = new Map(prev);
            next.delete(componentId);
            return next;
        });
    }, []);

    // Reset all swaps
    const resetAll = useCallback(() => {
        setSwapOverrides(new Map());
    }, []);

    // Check if a component is currently swapped
    const isSwapped = useCallback((componentId: string): boolean => {
        return swapOverrides.has(componentId);
    }, [swapOverrides]);

    const value: SwapContextValue = {
        swapOverrides,
        swapComponent,
        getSwappedType,
        resetSwap,
        resetAll,
        isSwapped,
    };

    return (
        <SwapContext.Provider value={value}>
            {children}
        </SwapContext.Provider>
    );
}

// ============================================================================
// Hook
// ============================================================================

export function useComponentSwap(): SwapContextValue {
    const ctx = useContext(SwapContext);
    if (!ctx) {
        throw new Error('useComponentSwap must be used within ComponentSwapProvider');
    }
    return ctx;
}

export default SwapContext;
