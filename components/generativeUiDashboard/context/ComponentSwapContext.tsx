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

import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import {
    getSwapOptionsFromCatalog,
    requiresServerSwap,
    isValidSwap,
    getComponentIcon,
    getComponentLabel,
    type SwapTarget,
    type SwapMode,
} from '../constants/swapCatalog';
import { useSwapPersistence, type SwapStateSnapshot as PersistedSwapState } from '../hooks/useSwapPersistence';

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
    /** Whether props contain real data (not just defaults like 0) */
    isComplete?: boolean;
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

    // --- Phase 2: Persistence ---
    /** Whether swap states are being restored from backend (loading state) */
    isRestoringStates: boolean;

    // --- Phase 3: Preview Empty State ---
    /** Check if a component has complete data for swapping */
    hasDataForComponent: (componentId: string) => boolean;
    /** Map of component IDs to preview loading state (fetching data for preview) */
    previewLoading: Map<string, boolean>;
    /** Trigger data fetch for a component that has no data */
    fetchDataForPreview: (componentId: string, componentType: string) => Promise<boolean>;
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
    const [previewLoading, setPreviewLoading] = useState<Map<string, boolean>>(new Map());
    const [isRestoringStates, setIsRestoringStates] = useState(false);

    // Initialize persistence hook
    const { loadSwapStates, saveSwapState, clearSwapStates } = useSwapPersistence({
        dashboardId,
        saveDebounceMs: 500,
        debug: process.env.NODE_ENV === 'development',
    });

    /**
     * Convert frontend SwapState to backend-compatible PersistedSwapState.
     */
    const toPersistedState = useCallback((state: SwapState): PersistedSwapState => ({
        component_id: state.componentId,
        original_type: state.originalType,
        current_type: state.currentType,
        history: state.history,
        history_index: state.historyIndex,
        is_dirty: state.isDirty,
        updated_at: new Date(state.lastModified).toISOString(),
        transformed_data: state.transformedData,
        warnings: state.warnings,
    }), []);

    /**
     * Convert backend PersistedSwapState to frontend SwapState.
     */
    const fromPersistedState = useCallback((persisted: PersistedSwapState): SwapState => ({
        componentId: persisted.component_id,
        originalType: persisted.original_type,
        currentType: persisted.current_type,
        history: persisted.history,
        historyIndex: persisted.history_index,
        historySnapshots: [], // Will be populated by registerOriginalProps
        isDirty: persisted.is_dirty,
        lastModified: new Date(persisted.updated_at).getTime(),
        transformedData: persisted.transformed_data,
        warnings: persisted.warnings,
    }), []);

    /**
     * Load swap states from backend on mount (restore previous session).
     */
    useEffect(() => {
        if (!dashboardId) return;

        let cancelled = false;
        setIsRestoringStates(true);

        loadSwapStates()
            .then((loadedStates) => {
                if (cancelled) return;
                if (loadedStates.size === 0) {
                    setIsRestoringStates(false);
                    return;
                }

                console.log('[SwapContext] Restoring', loadedStates.size, 'swap states');
                setSwapStates((prev) => {
                    const next = new Map(prev);
                    for (const [componentId, persisted] of loadedStates) {
                        // Only restore if not already initialized
                        if (!next.has(componentId)) {
                            next.set(componentId, fromPersistedState(persisted));
                        }
                    }
                    return next;
                });
                setIsRestoringStates(false);
            })
            .catch((error) => {
                console.error('[SwapContext] Failed to restore swap states:', error);
                if (!cancelled) setIsRestoringStates(false);
            });

        return () => {
            cancelled = true;
        };
    }, [dashboardId, loadSwapStates, fromPersistedState]);

    /**
     * Cleanup swap states on unmount (fire-and-forget).
     * Only runs when dashboardId was set and we're unmounting.
     */
    useEffect(() => {
        return () => {
            // Fire-and-forget cleanup on unmount
            if (dashboardId) {
                clearSwapStates().catch((e) =>
                    console.warn('[SwapContext] Cleanup failed:', e)
                );
            }
        };
    }, [dashboardId, clearSwapStates]);

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
     *
     * FIX: Handles race condition where state is created by hover before registration.
     * Also allows re-registration when better data becomes available.
     */
    const registerOriginalProps = useCallback((
        componentId: string,
        originalType: string,
        props: Record<string, unknown>
    ) => {
        const existingState = swapStates.get(componentId);

        // Helper: Check if value is a binding path object (not real data)
        const isBindingPath = (v: unknown): boolean =>
            typeof v === 'object' && v !== null && 'path' in v;

        // Check if props contain meaningful RESOLVED data (not binding paths or defaults)
        // FIX: For numeric KPI props (value, primary_value, etc.), 0 is NOT real data
        // This prevents snapshots with value=0 from being marked as complete
        const numericPropNames = ['value', 'primary_value', 'leader_value', 'delta', 'change', 'percent_change'];
        const hasRealData = Object.entries(props).some(([key, v]) => {
            // For known numeric KPI props, 0 is NOT real data
            if (numericPropNames.includes(key)) {
                return typeof v === 'number' && v !== 0;
            }
            // For other props, use standard checks
            return v !== 0 && v !== '' && v !== null && v !== undefined &&
                !isBindingPath(v) && // Exclude binding path objects
                !(Array.isArray(v) && v.length === 0) &&
                !(typeof v === 'object' && v !== null && Object.keys(v).length === 0);
        });

        const originalSnapshot: PropsSnapshot = {
            type: originalType,
            props: { ...props }, // Deep copy to prevent mutation
            isComplete: hasRealData,
        };

        // Case 1: No existing state - create new
        if (!existingState) {
            const newState: SwapState = {
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
            return;
        }

        // Case 2: State exists but no snapshot (race condition - hover before registration)
        if (!existingState.originalSnapshot) {
            console.debug('[Swap] Backfilling originalSnapshot for', componentId);
            const newState: SwapState = {
                ...existingState,
                originalSnapshot,
                historySnapshots: existingState.historySnapshots.length === 0
                    ? [originalSnapshot]
                    : [originalSnapshot, ...existingState.historySnapshots.slice(1)],
            };
            updateState(componentId, newState);
            return;
        }

        // Case 3: Existing snapshot is incomplete but new data is better
        if (!existingState.originalSnapshot.isComplete && hasRealData) {
            console.debug('[Swap] Upgrading incomplete snapshot for', componentId);
            const newState: SwapState = {
                ...existingState,
                originalSnapshot,
                // Update first history snapshot too
                historySnapshots: [originalSnapshot, ...existingState.historySnapshots.slice(1)],
            };
            updateState(componentId, newState);
        }
        // Case 4: Existing snapshot is complete - do nothing
    }, [swapStates, updateState]);

    /**
     * Phase 1: Get render props for a component.
     * Returns snapshot-backed props when available, otherwise original props.
     * This ensures data persists through swap/revert cycles.
     *
     * BUG FIX: Only use snapshot for components that have been through a swap cycle.
     * For non-swapped components, return original props to allow normal data binding.
     */
    const getRenderProps = useCallback((
        componentId: string,
        originalProps: Record<string, unknown>
    ): Record<string, unknown> => {
        const state = swapStates.get(componentId);
        if (!state) return originalProps;

        // Priority 1: Preview snapshot (transient)
        if (state.previewType && state.previewSnapshot) {
            return { ...originalProps, ...state.previewSnapshot.props };
        }

        // Priority 2: Current history snapshot (when actively swapped)
        // Without isDirty check, resolved props would override binding paths
        const currentSnapshot = state.historySnapshots[state.historyIndex];
        if (state.isDirty && currentSnapshot) {
            return { ...originalProps, ...currentSnapshot.props };
        }

        // Priority 3: Explicit transformedData
        if (state.transformedData) {
            return { ...originalProps, ...state.transformedData };
        }

        // Priority 4: Original snapshot when actively swapped
        if (state.isDirty && state.originalSnapshot) {
            return { ...originalProps, ...state.originalSnapshot.props };
        }

        // Priority 5: After reset from a swap, use snapshot to preserve data
        // CRITICAL: Only apply for components that WERE swapped (history.length > 1)
        // This prevents non-swapped components with literal props from having
        // their snapshot (with value=0) override the actual data binding.
        const wasEverSwapped = state.history.length > 1;
        if (!state.isDirty && wasEverSwapped && state.originalSnapshot?.isComplete &&
            state.originalSnapshot?.props && Object.keys(state.originalSnapshot.props).length > 0) {
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

            // FIX: Guard against swap before registration completes (for both preview AND direct swaps)
            // If originalSnapshot is undefined, component hasn't registered its resolved props yet
            if (!currentState.originalSnapshot) {
                console.warn('[Swap] Cannot swap - component not initialized with resolved props');
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

        // Phase 2: Persist to backend (fire-and-forget)
        if (dashboardId) {
            saveSwapState(componentId, toPersistedState(newState));
        }
    }, [swapStates, updateState, dashboardId, saveSwapState, toPersistedState]);

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
     *
     * CRITICAL FIX: Never delete state - always reset to preserve component in layout.
     */
    const resetSwap = useCallback((componentId: string) => {
        const state = swapStates.get(componentId);
        if (!state) return;

        // FIX: Clear transformedData to undefined so bindings can re-resolve from dataModel
        // This prevents stale snapshot data (with value=0) from overriding live data bindings
        const newState: SwapState = {
            ...state,
            currentType: state.originalType,
            // CRITICAL: Always clear transformedData on reset to let DataBinder re-resolve
            transformedData: undefined,
            history: [state.originalType],
            historyIndex: 0,
            // Clear history snapshots to prevent stale data from being used
            historySnapshots: [],
            isDirty: false,
            previewType: undefined,
            previewData: undefined,
            previewSnapshot: undefined,
            serverSwap: false,
            lastModified: Date.now(),
        };

        console.debug('[Swap] resetSwap:', componentId, '- cleared transformedData, bindings will re-resolve');
        updateState(componentId, newState);
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
     *
     * BUG FIX: Only return snapshot data when component has been through a swap cycle.
     * For non-swapped components, let normal data binding resolve values from dataModel.
     * The previous "Priority 5" logic caused a bug where components with literal string
     * props (like label) would have isComplete=true even when value was still 0,
     * preventing proper data binding on subsequent renders.
     */
    const getTransformedData = useCallback((componentId: string): Record<string, unknown> | undefined => {
        const state = swapStates.get(componentId);
        if (!state) return undefined;

        // Priority 1: Preview data (transient)
        if (state.previewType && state.previewData) {
            return state.previewData;
        }

        // Priority 2: Current history snapshot (when actively swapped)
        // Without isDirty check, resolved props from registerOriginalProps would override binding paths
        const currentSnapshot = state.historySnapshots?.[state.historyIndex];
        if (state.isDirty && currentSnapshot?.props && Object.keys(currentSnapshot.props).length > 0) {
            return currentSnapshot.props;
        }

        // Priority 3: Explicit transformedData (from server swap or reset)
        if (state.transformedData) {
            return state.transformedData;
        }

        // Priority 4: Original snapshot when actively swapped
        if (state.isDirty && state.originalSnapshot?.props) {
            return state.originalSnapshot.props;
        }

        // Priority 5: After reset from a swap, use snapshot to preserve data
        // CRITICAL: Only apply this for components that WERE swapped (history.length > 1)
        // This prevents the bug where non-swapped components with literal label props
        // would have isComplete=true (due to non-empty label) but value=0, causing
        // the snapshot to override the data binding and display 0 instead of real values.
        const wasEverSwapped = state.history.length > 1;
        if (!state.isDirty && wasEverSwapped && state.originalSnapshot?.isComplete &&
            state.originalSnapshot?.props && Object.keys(state.originalSnapshot.props).length > 0) {
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

    // --- Phase 3: Preview Empty State ---

    /**
     * Check if a component has complete data for swapping.
     * Returns true if originalSnapshot exists and isComplete is true.
     */
    const hasDataForComponent = useCallback((componentId: string): boolean => {
        const state = swapStates.get(componentId);
        return state?.originalSnapshot?.isComplete ?? false;
    }, [swapStates]);

    /**
     * Set preview loading state for a component.
     */
    const setComponentPreviewLoading = useCallback((componentId: string, loading: boolean) => {
        setPreviewLoading(prev => {
            const next = new Map(prev);
            if (loading) {
                next.set(componentId, true);
            } else {
                next.delete(componentId);
            }
            return next;
        });
    }, []);

    /**
     * Fetch data for a component that has no data (for preview).
     * Triggers a refresh of the dashboard data and waits for registration to complete.
     * Returns true if data becomes available.
     */
    const fetchDataForPreview = useCallback(async (
        componentId: string,
        _componentType: string
    ): Promise<boolean> => {
        if (!dashboardId) {
            console.warn('[Swap] fetchDataForPreview: No dashboardId available');
            return false;
        }

        setComponentPreviewLoading(componentId, true);

        try {
            // Fetch fresh data from the dashboard endpoint
            const response = await fetch(`/api/dash/${dashboardId}/data`);
            if (!response.ok) {
                throw new Error(`Failed to fetch data: ${response.statusText}`);
            }

            // Wait a tick for the data to propagate through DataBinder
            // and for ComponentRenderer to re-register with new data
            await new Promise(resolve => setTimeout(resolve, 100));

            // Check if data is now available
            const state = swapStates.get(componentId);
            const hasData = state?.originalSnapshot?.isComplete ?? false;

            if (!hasData) {
                console.warn('[Swap] fetchDataForPreview: Data still not available after fetch');
            }

            return hasData;
        } catch (error) {
            console.error('[Swap] fetchDataForPreview error:', error);
            return false;
        } finally {
            setComponentPreviewLoading(componentId, false);
        }
    }, [dashboardId, swapStates, setComponentPreviewLoading]);

    const value: SwapContextValue = {
        swapStates,
        dashboardId,
        requestSwap,
        previewSwap,
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
        // Phase 2: Persistence
        isRestoringStates,
        // Phase 3: Preview Empty State
        hasDataForComponent,
        previewLoading,
        fetchDataForPreview,
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
