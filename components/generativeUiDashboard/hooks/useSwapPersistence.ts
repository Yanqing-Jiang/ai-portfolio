/**
 * useSwapPersistence - Hook for persisting component swap states to backend.
 *
 * Hook: useSwapPersistence
 * Called from: ComponentSwapProvider
 * Invokes: Fetch API to /api/dash/{dashboardId}/swap/state endpoints
 * Why: Enables cross-refresh persistence of component swap states via Redis backend.
 *      Uses fire-and-forget pattern for saves to avoid blocking UI.
 */

import { useCallback, useRef } from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Swap state snapshot format matching backend SwapStateSnapshot.
 */
export interface SwapStateSnapshot {
    component_id: string;
    original_type: string;
    current_type: string;
    history: string[];
    history_index: number;
    is_dirty: boolean;
    updated_at: string;
    transformed_data?: Record<string, unknown>;
    warnings?: string[];
}

export interface UseSwapPersistenceOptions {
    /** Dashboard ID for API calls */
    dashboardId: string | null;
    /** Debounce delay for saves (ms) */
    saveDebounceMs?: number;
    /** Enable debug logging */
    debug?: boolean;
}

export interface UseSwapPersistenceResult {
    /** Load all swap states from backend */
    loadSwapStates: () => Promise<Map<string, SwapStateSnapshot>>;
    /** Save swap states (fire-and-forget, debounced) */
    saveSwapState: (componentId: string, state: SwapStateSnapshot) => void;
    /** Save multiple states at once */
    saveSwapStates: (states: Record<string, SwapStateSnapshot>) => void;
    /** Delete a single component's swap state */
    deleteSwapState: (componentId: string) => Promise<void>;
    /** Clear all swap states for the dashboard */
    clearSwapStates: () => Promise<void>;
    /** Whether currently loading */
    isLoading: boolean;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for swap state persistence to backend Redis storage.
 *
 * Features:
 * - Fire-and-forget saves (non-blocking)
 * - Debounced batch saves
 * - Graceful error handling (logs but doesn't throw)
 * - Load on mount support
 */
export function useSwapPersistence({
    dashboardId,
    saveDebounceMs = 500,
    debug = false,
}: UseSwapPersistenceOptions): UseSwapPersistenceResult {
    const pendingSaves = useRef<Record<string, SwapStateSnapshot>>({});
    const saveTimerRef = useRef<NodeJS.Timeout | null>(null);
    const isLoadingRef = useRef(false);

    const log = useCallback(
        (...args: unknown[]) => {
            if (debug) console.log('[SwapPersistence]', ...args);
        },
        [debug]
    );

    /**
     * Load all swap states from backend.
     * Called on provider mount to restore previous session state.
     */
    const loadSwapStates = useCallback(async (): Promise<Map<string, SwapStateSnapshot>> => {
        if (!dashboardId) {
            log('No dashboardId, skipping load');
            return new Map();
        }

        isLoadingRef.current = true;
        try {
            log('Loading swap states for', dashboardId);
            const response = await fetch(`/api/dash/${dashboardId}/swap/state`);

            if (!response.ok) {
                if (response.status === 404) {
                    log('Dashboard not found, no states to load');
                    return new Map();
                }
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            const states = new Map<string, SwapStateSnapshot>();

            if (data.states) {
                for (const [componentId, state] of Object.entries(data.states)) {
                    states.set(componentId, state as SwapStateSnapshot);
                }
            }

            log('Loaded', states.size, 'swap states');
            return states;
        } catch (error) {
            console.error('[SwapPersistence] Load failed:', error);
            return new Map();
        } finally {
            isLoadingRef.current = false;
        }
    }, [dashboardId, log]);

    /**
     * Flush pending saves to backend.
     * Called after debounce delay.
     */
    const flushSaves = useCallback(async () => {
        if (!dashboardId) return;

        const toSave = { ...pendingSaves.current };
        pendingSaves.current = {};

        if (Object.keys(toSave).length === 0) return;

        try {
            log('Saving', Object.keys(toSave).length, 'swap states');
            const response = await fetch(`/api/dash/${dashboardId}/swap/state`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ states: toSave }),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            log('Saved', data.saved_count, 'states');
        } catch (error) {
            console.error('[SwapPersistence] Save failed:', error);
            // Re-queue failed saves for next attempt
            pendingSaves.current = { ...toSave, ...pendingSaves.current };
        }
    }, [dashboardId, log]);

    /**
     * Queue a single swap state for saving.
     * Debounced - multiple saves within saveDebounceMs will be batched.
     */
    const saveSwapState = useCallback(
        (componentId: string, state: SwapStateSnapshot) => {
            if (!dashboardId) {
                log('No dashboardId, skipping save');
                return;
            }

            // Add to pending saves
            pendingSaves.current[componentId] = state;

            // Reset debounce timer
            if (saveTimerRef.current) {
                clearTimeout(saveTimerRef.current);
            }

            // Schedule flush
            saveTimerRef.current = setTimeout(() => {
                flushSaves();
            }, saveDebounceMs);
        },
        [dashboardId, saveDebounceMs, flushSaves, log]
    );

    /**
     * Queue multiple swap states for saving.
     */
    const saveSwapStates = useCallback(
        (states: Record<string, SwapStateSnapshot>) => {
            if (!dashboardId) return;

            // Add all to pending saves
            Object.assign(pendingSaves.current, states);

            // Reset debounce timer
            if (saveTimerRef.current) {
                clearTimeout(saveTimerRef.current);
            }

            // Schedule flush
            saveTimerRef.current = setTimeout(() => {
                flushSaves();
            }, saveDebounceMs);
        },
        [dashboardId, saveDebounceMs, flushSaves]
    );

    /**
     * Delete a single component's swap state.
     */
    const deleteSwapState = useCallback(
        async (componentId: string) => {
            if (!dashboardId) return;

            // Remove from pending saves
            delete pendingSaves.current[componentId];

            try {
                log('Deleting swap state for', componentId);
                const response = await fetch(
                    `/api/dash/${dashboardId}/swap/state/${componentId}`,
                    { method: 'DELETE' }
                );

                if (!response.ok && response.status !== 404) {
                    throw new Error(`HTTP ${response.status}`);
                }

                log('Deleted swap state for', componentId);
            } catch (error) {
                console.error('[SwapPersistence] Delete failed:', error);
            }
        },
        [dashboardId, log]
    );

    /**
     * Clear all swap states for the dashboard.
     * Called on unmount or session end.
     */
    const clearSwapStates = useCallback(async () => {
        if (!dashboardId) return;

        // Clear pending saves
        pendingSaves.current = {};
        if (saveTimerRef.current) {
            clearTimeout(saveTimerRef.current);
        }

        try {
            log('Clearing all swap states');
            await fetch(`/api/dash/${dashboardId}/swap/state/clear`, {
                method: 'POST',
            });
            log('Cleared all swap states');
        } catch (error) {
            console.error('[SwapPersistence] Clear failed:', error);
        }
    }, [dashboardId, log]);

    return {
        loadSwapStates,
        saveSwapState,
        saveSwapStates,
        deleteSwapState,
        clearSwapStates,
        isLoading: isLoadingRef.current,
    };
}

export default useSwapPersistence;
