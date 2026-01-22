/**
 * ComponentSwapContext - Track component type overrides for swapping.
 *
 * Context: ComponentSwapContext
 * Called from: GenerativeUIPage.tsx (provider), widgets (consumer)
 * Invokes: React.createContext, swapCatalog
 * Why: Enables client-side and server-side component swapping.
 *      Supports universal swapping with mode detection (client/server).
 *      Refactored to support "Preview-First" flow, history (undo/redo), and state preservation.
 */

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import {
    SWAP_CATALOG,
    getSwapOptionsFromCatalog,
    requiresServerSwap,
    isValidSwap,
    getComponentIcon,
    getComponentLabel,
    type SwapTarget,
    type SwapMode,
} from '../constants/swapCatalog';

// ============================================================================
// Types
// ============================================================================

/**
 * Snapshot of resolved props at a point in time.
 * Used to restore data when reverting/undoing swaps.
 */
export interface PropsSnapshot {
    type: string;
    props: Record<string, unknown>;
    warnings?: string[];
}

export interface SwapState {
    /** ID of the component being swapped */
    componentId: string;
    /** Original component type (base state) */
    originalType: string;
    /** Current active component type */
    currentType: string;
    /** History of component types (for undo/redo) */
    history: string[];
    /** Current position in history stack */
    historyIndex: number;
    /** Preview type (transient, not committed) */
    previewType?: string;
    /** Preview data (transient) */
    previewData?: Record<string, unknown>;
    /** Transformed data for the current type */
    transformedData?: Record<string, unknown>;
    /** Whether the component has been modified from original */
    isDirty: boolean;
    /** Timestamp of last modification */
    lastModified: number;
    /** Whether the current swap required server transformation */
    serverSwap?: boolean;
    /** Warnings returned from server/client transformation */
    warnings?: string[];

    // --- Phase 1: Snapshot System ---
    /** Snapshot of original props before any swap (for safe revert) */
    originalSnapshot?: PropsSnapshot;
    /** Snapshots aligned to history[] for undo/redo data restoration */
    historySnapshots: PropsSnapshot[];
    /** Preview snapshot (transient) */
    previewSnapshot?: PropsSnapshot;
}

// Legacy type alias for backward compatibility during refactor
export type SwapOverride = {
    targetComponentId: string;
    originalType: string;
    swappedType: string;
    timestamp: number;
    serverSwap?: boolean;
    transformedData?: Record<string, unknown>;
    warnings?: string[];
};

export interface SwapRequest {
    componentId: string;
    originalType: string;
    targetType: string;
    mode: SwapMode;
    preview?: boolean;
}

export interface SwapResult {
    success: boolean;
    mode: SwapMode;
    error?: string;
    transformedData?: Record<string, unknown>;
    warnings?: string[];
}

export interface SwapSuggestion {
    targetType: string;
    reason: string;
    score: number;
    icon: string;
}

export interface SwapContextValue {
    /** Map of component ID to swap state */
    swapStates: Map<string, SwapState>;
    /** Dashboard ID for server swaps */
    dashboardId: string | null;

    // --- Core Actions ---
    /** Request a swap (supports preview mode) */
    requestSwap: (componentId: string, originalType: string, targetType: string, isPreview?: boolean) => Promise<SwapResult>;
    /** Enter preview mode for a target type */
    previewSwap: (componentId: string, originalType: string, targetType: string) => Promise<SwapResult>;
    /** Get smart swap suggestions */
    suggestSwaps: (componentId: string, currentType: string) => Promise<SwapSuggestion[]>;
    /** Commit the current preview to active state */
    commitSwap: (componentId: string) => void;
    /** Cancel the current preview and revert to previous state */
    cancelPreview: (componentId: string) => void;
    /** Undo the last swap */
    undoSwap: (componentId: string) => void;
    /** Redo the last undone swap */
    redoSwap: (componentId: string) => void;
    /** Reset a component to its original state */
    resetSwap: (componentId: string) => void;
    /** Reset all swaps */
    resetAll: () => void;

    // --- State Accessors ---
    /** Get the current type to render (resolves preview > current > original) */
    getRenderType: (componentId: string, defaultType: string) => string;
    /** Get the full swap state for a component */
    getSwapState: (componentId: string) => SwapState | undefined;
    /** Get transformed data for the current render type */
    getTransformedData: (componentId: string) => Record<string, unknown> | undefined;
    /** Check if a component is currently swapped (dirty) */
    isSwapped: (componentId: string) => boolean;
    /** Check if a component is in preview mode */
    isPreviewing: (componentId: string) => boolean;
    /** Check if undo is available */
    canUndo: (componentId: string) => boolean;
    /** Check if redo is available */
    canRedo: (componentId: string) => boolean;

    // --- Legacy / Helper ---
    /** Legacy compatibility: Get swap override shape */
    getSwapOverride: (componentId: string) => SwapOverride | undefined;
    /** Legacy compatibility: Get swapped type */
    getSwappedType: (componentId: string, defaultType: string) => string;
    /** Legacy compatibility: Sync swap */
    swapComponent: (componentId: string, originalType: string, newType: string) => void;

    getSwapTargets: (componentType: string) => SwapTarget[];
    needsServerSwap: (fromType: string, toType: string) => boolean;
    swapLoading: Map<string, boolean>;

    // --- Phase 1: Snapshot System ---
    /** Register original props for a component (called by ComponentRenderer on mount) */
    registerOriginalProps: (componentId: string, originalType: string, props: Record<string, unknown>) => void;
    /** Get render props (respects snapshots for data preservation) */
    getRenderProps: (componentId: string, originalProps: Record<string, unknown>) => Record<string, unknown>;
}

// ============================================================================
// Legacy Swap Groups
// ============================================================================

const SWAP_GROUPS: Record<string, string[]> = {
    PriceChart: ['MetricChart'],
    MetricChart: ['PriceChart'],
    DataTable: ['CorrelationMatrix'],
    CorrelationMatrix: ['DataTable'],
    ExplainMovePanel: ['NewsTimeline'],
    NewsTimeline: ['ExplainMovePanel'],
};

export function canSwapTo(currentType: string, targetType: string): boolean {
    if (isValidSwap(currentType, targetType)) return true;
    return SWAP_GROUPS[currentType]?.includes(targetType) ?? false;
}

export function getSwapOptions(componentType: string): string[] {
    const catalogTargets = getSwapOptionsFromCatalog(componentType);
    if (catalogTargets.length > 0) {
        return catalogTargets.map(t => t.targetType);
    }
    return SWAP_GROUPS[componentType] || [];
}

export { getComponentIcon, getComponentLabel, type SwapTarget, type SwapMode };

// ============================================================================
// Context
// ============================================================================

const SwapContext = createContext<SwapContextValue | null>(null);

// ============================================================================
// Provider
// ============================================================================

export interface ComponentSwapProviderProps {
    children: ReactNode;
    dashboardId?: string | null;
}

export function ComponentSwapProvider({ children, dashboardId = null }: ComponentSwapProviderProps) {
    const [swapStates, setSwapStates] = useState<Map<string, SwapState>>(new Map());
    const [swapLoading, setSwapLoading] = useState<Map<string, boolean>>(new Map());

    // Helper: Initialize state for a component if missing
    const getOrCreateState = useCallback((componentId: string, originalType: string): SwapState => {
        return swapStates.get(componentId) || {
            componentId,
            originalType,
            currentType: originalType,
            history: [originalType],
            historyIndex: 0,
            historySnapshots: [], // Phase 1: Initialize empty snapshots array
            isDirty: false,
            lastModified: Date.now(),
        };
    }, [swapStates]);

    // Helper: Update state map
    const updateState = useCallback((componentId: string, newState: SwapState) => {
        setSwapStates(prev => {
            const next = new Map(prev);
            next.set(componentId, newState);
            return next;
        });
    }, []);

    /**
     * Phase 1: Register original props for a component.
     * Called by ComponentRenderer on first render to capture resolved props
     * BEFORE any swap occurs. This ensures we can safely revert.
     */
    const registerOriginalProps = useCallback((
        componentId: string,
        originalType: string,
        props: Record<string, unknown>
    ) => {
        const existingState = swapStates.get(componentId);

        // Only register if no state exists OR state has no original snapshot yet
        if (!existingState || !existingState.originalSnapshot) {
            const originalSnapshot: PropsSnapshot = {
                type: originalType,
                props: { ...props }, // Deep copy to prevent mutation
            };

            const newState: SwapState = existingState ? {
                ...existingState,
                originalSnapshot,
                // Also set first history snapshot if not present
                historySnapshots: existingState.historySnapshots.length === 0
                    ? [originalSnapshot]
                    : existingState.historySnapshots,
            } : {
                componentId,
                originalType,
                currentType: originalType,
                history: [originalType],
                historyIndex: 0,
                historySnapshots: [originalSnapshot],
                originalSnapshot,
                isDirty: false,
                lastModified: Date.now(),
            };

            updateState(componentId, newState);
        }
    }, [swapStates, updateState]);

    /**
     * Phase 1: Get render props for a component.
     * Returns snapshot-backed props when available, otherwise original props.
     * This ensures data persists through swap/revert cycles.
     */
    const getRenderProps = useCallback((
        componentId: string,
        originalProps: Record<string, unknown>
    ): Record<string, unknown> => {
        const state = swapStates.get(componentId);
        if (!state) return originalProps;

        // Priority: preview snapshot → current history snapshot → transformed data → original props
        if (state.previewType && state.previewSnapshot) {
            return { ...originalProps, ...state.previewSnapshot.props };
        }

        // Get snapshot for current history index
        const currentSnapshot = state.historySnapshots[state.historyIndex];
        if (currentSnapshot) {
            return { ...originalProps, ...currentSnapshot.props };
        }

        // Fall back to transformed data if available
        if (state.transformedData) {
            return { ...originalProps, ...state.transformedData };
        }

        // Final fallback to original snapshot
        if (state.originalSnapshot) {
            return { ...originalProps, ...state.originalSnapshot.props };
        }

        return originalProps;
    }, [swapStates]);

    // Core: Perform Swap Logic (Shared by requestSwap and previewSwap)
    const executeSwap = useCallback(async (
        componentId: string,
        originalType: string,
        targetType: string,
        isPreview: boolean
    ): Promise<SwapResult> => {
        if (!canSwapTo(originalType, targetType)) {
            return { success: false, mode: 'client', error: `Cannot swap ${originalType} to ${targetType}` };
        }

        const needsServer = requiresServerSwap(originalType, targetType);

        // Optimistic update for client swaps
        if (!needsServer) {
            const currentState = getOrCreateState(componentId, originalType);

            // FIX: Guard against preview before registration completes
            // If originalSnapshot is undefined, component hasn't registered its resolved props yet
            if (isPreview && !currentState.originalSnapshot) {
                console.warn('[Swap] Cannot preview - component not initialized with resolved props');
                return { success: false, mode: 'client', error: 'Component not ready for swap' };
            }

            const newState: SwapState = { ...currentState, lastModified: Date.now() };

            if (isPreview) {
                newState.previewType = targetType;
                // FIX: Use resolved props from originalSnapshot (now contains actual values, not binding paths)
                const preservedProps = currentState.originalSnapshot?.props ?? {};
                newState.previewData = preservedProps;
                newState.previewSnapshot = { type: targetType, props: preservedProps };
                newState.warnings = [];
            } else {
                // Commit to history
                const newHistory = currentState.history.slice(0, currentState.historyIndex + 1);
                newHistory.push(targetType);

                // Phase 1: Create snapshot for this history entry (client swap uses original props)
                const newHistorySnapshots = currentState.historySnapshots.slice(0, currentState.historyIndex + 1);
                newHistorySnapshots.push({
                    type: targetType,
                    props: currentState.originalSnapshot?.props ?? {},
                });

                newState.currentType = targetType;
                newState.history = newHistory;
                newState.historySnapshots = newHistorySnapshots;
                newState.historyIndex = newHistory.length - 1;
                newState.isDirty = targetType !== originalType;
                newState.previewType = undefined;
                newState.previewSnapshot = undefined;
                newState.serverSwap = false;
                newState.warnings = [];
            }
            updateState(componentId, newState);
            return { success: true, mode: 'client', warnings: [] };
        }

        // Server Swap
        if (!dashboardId) {
            console.warn('[ComponentSwapContext] Server swap requested but no dashboardId');
            return { success: false, mode: 'server', error: 'No dashboard ID' };
        }

        setSwapLoading(prev => new Map(prev).set(componentId, true));

        try {
            // Check if we have a preview for this target already? (Caching could be added here)

            const response = await fetch(`/api/dash/${dashboardId}/swap`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    component_id: componentId,
                    from_type: originalType,
                    to_type: targetType,
                }),
            });

            if (!response.ok) throw new Error(response.statusText);
            const result = await response.json();

            // Apply update
            const currentState = getOrCreateState(componentId, originalType);
            const newState: SwapState = { ...currentState, lastModified: Date.now() };

            if (isPreview) {
                newState.previewType = targetType;
                newState.previewData = result.transformed_data;
                newState.previewSnapshot = {
                    type: targetType,
                    props: result.transformed_data || {},
                    warnings: result.warnings,
                };
                newState.warnings = result.warnings || [];
            } else {
                const newHistory = currentState.history.slice(0, currentState.historyIndex + 1);
                newHistory.push(targetType);

                // Phase 1: Create snapshot for this history entry with server-transformed data
                const newHistorySnapshots = currentState.historySnapshots.slice(0, currentState.historyIndex + 1);
                newHistorySnapshots.push({
                    type: targetType,
                    props: result.transformed_data || {},
                    warnings: result.warnings,
                });

                newState.currentType = targetType;
                newState.history = newHistory;
                newState.historySnapshots = newHistorySnapshots;
                newState.historyIndex = newHistory.length - 1;
                newState.isDirty = true;
                newState.transformedData = result.transformed_data;
                newState.previewType = undefined;
                newState.previewSnapshot = undefined;
                newState.serverSwap = true;
                newState.warnings = result.warnings || [];
            }
            updateState(componentId, newState);

            return {
                success: true,
                mode: 'server',
                transformedData: result.transformed_data,
                warnings: result.warnings
            };

        } catch (error) {
            console.error('[Swap] Error:', error);
            return { success: false, mode: 'server', error: String(error) };
        } finally {
            setSwapLoading(prev => {
                const next = new Map(prev);
                next.delete(componentId);
                return next;
            });
        }
    }, [dashboardId, getOrCreateState, updateState]);

    const requestSwap = useCallback((id: string, orig: string, target: string, isPreview = false) => {
        return executeSwap(id, orig, target, isPreview);
    }, [executeSwap]);

    const previewSwap = useCallback((id: string, orig: string, target: string) => {
        return executeSwap(id, orig, target, true);
    }, [executeSwap]);

    const suggestSwaps = useCallback(async (componentId: string, currentType: string): Promise<SwapSuggestion[]> => {
        if (!dashboardId) return [];
        try {
            const res = await fetch(`/api/dash/${dashboardId}/swap/suggest?component_type=${currentType}`);
            if (res.ok) {
                const data = await res.json();
                return data.suggestions || [];
            }
        } catch (e) { console.error('Error fetching suggestions:', e); }
        return [];
    }, [dashboardId]);

    /**
     * Commit the current preview to active state.
     * Phase 2: Also commits previewSnapshot to historySnapshots.
     */
    const commitSwap = useCallback((componentId: string) => {
        const state = swapStates.get(componentId);
        if (!state?.previewType) return;

        const newHistory = state.history.slice(0, state.historyIndex + 1);
        newHistory.push(state.previewType);

        // Phase 2: Commit preview snapshot to history snapshots
        const newHistorySnapshots = state.historySnapshots.slice(0, state.historyIndex + 1);
        if (state.previewSnapshot) {
            newHistorySnapshots.push(state.previewSnapshot);
        } else {
            // Fallback: create snapshot from preview data
            newHistorySnapshots.push({
                type: state.previewType,
                props: state.previewData || {},
            });
        }

        const newState: SwapState = {
            ...state,
            currentType: state.previewType,
            transformedData: state.previewData || state.previewSnapshot?.props || state.transformedData,
            history: newHistory,
            historySnapshots: newHistorySnapshots,
            historyIndex: newHistory.length - 1,
            isDirty: true,
            previewType: undefined,
            previewData: undefined,
            previewSnapshot: undefined,
            lastModified: Date.now(),
        };
        updateState(componentId, newState);
    }, [swapStates, updateState]);

    /**
     * Cancel the current preview and revert to previous state.
     * Phase 2: Also clears previewSnapshot.
     */
    const cancelPreview = useCallback((componentId: string) => {
        const state = swapStates.get(componentId);
        if (!state) return;

        const newState: SwapState = {
            ...state,
            previewType: undefined,
            previewData: undefined,
            previewSnapshot: undefined,
            warnings: undefined,
            lastModified: Date.now(),
        };
        updateState(componentId, newState);
    }, [swapStates, updateState]);

    /**
     * Undo the last swap.
     * Phase 1 FIX: Restore transformedData from historySnapshots.
     */
    const undoSwap = useCallback((componentId: string) => {
        const state = swapStates.get(componentId);
        if (!state || state.historyIndex <= 0) return;

        const newIndex = state.historyIndex - 1;
        const prevType = state.history[newIndex];

        // Phase 1 FIX: Restore data from history snapshot
        const prevSnapshot = state.historySnapshots[newIndex];

        const newState: SwapState = {
            ...state,
            historyIndex: newIndex,
            currentType: prevType,
            // Restore transformed data from snapshot
            transformedData: prevSnapshot?.props ?? state.transformedData,
            isDirty: prevType !== state.originalType,
            previewType: undefined,
            previewData: undefined,
            lastModified: Date.now(),
        };
        updateState(componentId, newState);
    }, [swapStates, updateState]);

    /**
     * Redo the last undone swap.
     * Phase 1 FIX: Restore transformedData from historySnapshots.
     */
    const redoSwap = useCallback((componentId: string) => {
        const state = swapStates.get(componentId);
        if (!state || state.historyIndex >= state.history.length - 1) return;

        const newIndex = state.historyIndex + 1;
        const nextType = state.history[newIndex];

        // Phase 1 FIX: Restore data from history snapshot
        const nextSnapshot = state.historySnapshots[newIndex];

        const newState: SwapState = {
            ...state,
            historyIndex: newIndex,
            currentType: nextType,
            // Restore transformed data from snapshot
            transformedData: nextSnapshot?.props ?? state.transformedData,
            isDirty: nextType !== state.originalType,
            previewType: undefined,
            previewData: undefined,
            lastModified: Date.now(),
        };
        updateState(componentId, newState);
    }, [swapStates, updateState]);

    /**
     * Reset a component to its original state.
     * Phase 1 FIX: Restore from originalSnapshot instead of deleting state.
     * This preserves resolved data values instead of falling back to broken bindings.
     */
    const resetSwap = useCallback((componentId: string) => {
        const state = swapStates.get(componentId);
        if (!state) return;

        // Phase 1 FIX: Restore from original snapshot if available
        if (state.originalSnapshot) {
            const newState: SwapState = {
                ...state,
                currentType: state.originalType,
                transformedData: state.originalSnapshot.props,
                history: [state.originalType],
                historyIndex: 0,
                historySnapshots: [state.originalSnapshot],
                isDirty: false,
                previewType: undefined,
                previewData: undefined,
                previewSnapshot: undefined,
                serverSwap: false,
                lastModified: Date.now(),
            };
            updateState(componentId, newState);
        } else {
            // Fallback: delete state if no snapshot (shouldn't happen normally)
            setSwapStates(prev => {
                const next = new Map(prev);
                next.delete(componentId);
                return next;
            });
        }
    }, [swapStates, updateState]);

    const resetAll = useCallback(() => setSwapStates(new Map()), []);

    // --- Accessors ---

    const getRenderType = useCallback((componentId: string, defaultType: string): string => {
        const state = swapStates.get(componentId);
        if (!state) return defaultType;
        return state.previewType ?? state.currentType ?? defaultType;
    }, [swapStates]);

    /**
     * Get transformed data for rendering.
     * Phase 1 FIX: Uses snapshot system to ensure data persists through undo/redo/reset.
     */
    const getTransformedData = useCallback((componentId: string): Record<string, unknown> | undefined => {
        const state = swapStates.get(componentId);
        if (!state) return undefined;

        // Priority: preview → current history snapshot → transformedData → original snapshot
        if (state.previewType && state.previewData) {
            return state.previewData;
        }

        // Phase 1 FIX: Use history snapshot for current index
        const currentSnapshot = state.historySnapshots?.[state.historyIndex];
        if (currentSnapshot?.props && Object.keys(currentSnapshot.props).length > 0) {
            return currentSnapshot.props;
        }

        // Fall back to transformedData
        if (state.transformedData) {
            return state.transformedData;
        }

        // Final fallback to original snapshot
        if (state.originalSnapshot?.props) {
            return state.originalSnapshot.props;
        }

        return undefined;
    }, [swapStates]);

    const isSwapped = useCallback((componentId: string): boolean => {
        const state = swapStates.get(componentId);
        return !!state && (state.isDirty || !!state.previewType);
    }, [swapStates]);

    const isPreviewing = useCallback((componentId: string): boolean => {
        return !!swapStates.get(componentId)?.previewType;
    }, [swapStates]);

    const canUndo = useCallback((componentId: string): boolean => {
        const state = swapStates.get(componentId);
        return !!state && state.historyIndex > 0;
    }, [swapStates]);

    const canRedo = useCallback((componentId: string): boolean => {
        const state = swapStates.get(componentId);
        return !!state && state.historyIndex < state.history.length - 1;
    }, [swapStates]);

    // --- Legacy Compatibility ---

    const getSwapOverride = useCallback((componentId: string): SwapOverride | undefined => {
        const state = swapStates.get(componentId);
        if (!state) return undefined;
        return {
            targetComponentId: componentId,
            originalType: state.originalType,
            swappedType: state.currentType,
            timestamp: state.lastModified,
            serverSwap: state.serverSwap,
            transformedData: state.transformedData,
        };
    }, [swapStates]);

    const getSwappedType = useCallback((componentId: string, defaultType: string): string => {
        return getRenderType(componentId, defaultType);
    }, [getRenderType]);

    const swapComponent = useCallback((id: string, orig: string, target: string) => {
        requestSwap(id, orig, target, false);
    }, [requestSwap]);

    const getSwapTargets = useCallback((type: string) => getSwapOptionsFromCatalog(type), []);
    const needsServerSwap = useCallback((from: string, to: string) => requiresServerSwap(from, to), []);

    const value: SwapContextValue = {
        swapStates,
        dashboardId,
        requestSwap,
        previewSwap,
        suggestSwaps,
        commitSwap,
        cancelPreview,
        undoSwap,
        redoSwap,
        resetSwap,
        resetAll,
        getRenderType,
        getSwapState: (id) => swapStates.get(id),
        getTransformedData,
        isSwapped,
        isPreviewing,
        canUndo,
        canRedo,
        // Legacy
        getSwapOverride,
        getSwappedType,
        swapComponent,
        getSwapTargets,
        needsServerSwap,
        swapLoading,
        // Phase 1: Snapshot System
        registerOriginalProps,
        getRenderProps,
    };

    return (
        <SwapContext.Provider value={value}>
            {children}
        </SwapContext.Provider>
    );
}

// Hook
export function useComponentSwap(): SwapContextValue {
    const ctx = useContext(SwapContext);
    if (!ctx) {
        throw new Error('useComponentSwap must be used within ComponentSwapProvider');
    }
    return ctx;
}

export default SwapContext;
