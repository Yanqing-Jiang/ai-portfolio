// --- Function/Class Map ---
// Function: useA2UIStream
//   Role: Manage SSE connections, stream state, clarifications, and action updates.
//   Called from: components/generativeUiDashboard/GenerativeUIPage.tsx
//   Invokes: createMessageProcessor, EventSource, mergeDataAtPath
//   Why: Centralizes A2UI streaming state management for the dashboard UI.
//
// Optimization #16: Performance improvements
//   - AbortController for proper connection cleanup
//   - useMemo for derived state to prevent re-renders
//   - Debounced state syncing
//
// Function: useSurface
//   Role: Select a single surface + data model from stream state.
//   Called from: components/generativeUiDashboard/GenerativeUIPage.tsx
//   Invokes: Map.get
//   Why: Simplifies surface access for renderers.
// Function: mergeDataAtPath
//   Role: Merge action response data into the data model at a JSON-pointer path.
//   Called from: useA2UIStream.sendAction, useA2UIStream.sendQuery
//   Invokes: n/a
//   Why: Aligns action responses with /data-bound widgets.
// Function: sendQuery
//   Role: Send conversational query through LLM-driven intent classification.
//   Called from: GenerativeUIPage.tsx chat handler
//   Invokes: fetch /api/dash/{id}/query, window.dispatchEvent
//   Why: Enables unified conversational control without hardcoded keywords.
// --- End Function/Class Map ---
/**
 * useA2UIStream Hook
 *
 * React hook for consuming A2UI SSE streams with automatic state management.
 * Optimized for performance with AbortController cleanup and memoized state.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createMessageProcessor, MessageProcessor } from './MessageProcessor';
import type { Surface, DataModel, UserActionMessage } from './types';
import { configService } from '../../../services/config';
import { authService } from '../../../services/auth';

/** Backend clarification field */
export interface BackendClarificationField {
    field_id: string;
    input_type: 'single_choice' | 'multi_choice' | 'dropdown' | 'freeform' | 'ticker_select' | 'timeframe_select';
    label: string;
    prompt?: string;
    required: boolean;
    options?: Array<{ id: string; label: string; description?: string; icon?: string }>;
    placeholder?: string;
    default?: string;
}

/** Backend clarification request */
export interface BackendClarificationRequest {
    request_id: string;
    title: string;
    subtitle?: string;
    fields: BackendClarificationField[];
    timeout_seconds: number;
    skip_allowed: boolean;
    target_component_id?: string;
}

export interface A2UIStreamState {
    /** Whether the stream is currently connected */
    isConnected: boolean;
    /** Whether we're waiting for initial data */
    isLoading: boolean;
    /** Any error that occurred */
    error: Error | null;
    /** Map of surface IDs to surface state */
    surfaces: Map<string, Surface>;
    /** Map of surface IDs to data models */
    dataModels: Map<string, DataModel>;
    /** Whether the stream is complete */
    isDone: boolean;
    /** Number of reconnection attempts */
    retryCount: number;
    /** Connection status for UI display */
    connectionStatus: 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'error' | 'complete';
    /** Pending clarification request from backend */
    pendingClarification: BackendClarificationRequest | null;
}

/** Response from the unified /query endpoint */
export interface QueryResponse {
    status: 'success' | 'new_dashboard' | 'error';
    intent: 'new_analysis' | 'modify_layout' | 'modify_data' | 'switch_component' | 'follow_up' | 'unknown';
    dashboard_id?: string;  // For new_analysis intent
    result?: Record<string, unknown>;
    rationale?: string;
    message?: string;
}

export interface A2UIStreamActions {
    /** Send a user action to the server */
    sendAction: (action: UserActionMessage['userAction']) => Promise<unknown>;
    /** Send a conversational query (LLM routes to appropriate action) */
    sendQuery: (query: string) => Promise<QueryResponse>;
    /** Reconnect to the stream */
    reconnect: () => void;
    /** Close the stream */
    close: () => void;
    /** Clear pending clarification request */
    clearClarification: () => void;
}

export interface UseA2UIStreamOptions {
    /** Whether to auto-connect on mount */
    autoConnect?: boolean;
    /** Dashboard ID for the stream */
    dashboardId?: string;
    /** Base URL for API endpoints */
    apiBaseUrl?: string;
    /** Callback for audit events */
    onAudit?: (event: any) => void;
}

const DEFAULT_OPTIONS: UseA2UIStreamOptions = {
    autoConnect: true,
    apiBaseUrl: `${configService.getBackendUrl()}/api/dash`,
};

// Reconnection constants
const MAX_RETRIES = 5;
const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;

/**
 * Merge data into the model at a given JSON-pointer path.
 */
function mergeDataAtPath(
    existing: DataModel,
    path: string | undefined,
    data: Record<string, unknown>
): DataModel {
    if (!path || path === '' || path === '/') {
        return { ...existing, ...data };
    }

    const segments = path.replace(/^\//, '').split('/');
    const result: Record<string, unknown> = { ...existing };
    let current: Record<string, unknown> = result;

    for (let i = 0; i < segments.length - 1; i += 1) {
        const segment = segments[i];
        const next = current[segment];
        if (!next || typeof next !== 'object') {
            current[segment] = {};
        } else {
            current[segment] = { ...(next as Record<string, unknown>) };
        }
        current = current[segment] as Record<string, unknown>;
    }

    const lastSegment = segments[segments.length - 1];
    const lastValue = current[lastSegment];
    const lastObject = lastValue && typeof lastValue === 'object' ? (lastValue as Record<string, unknown>) : {};
    current[lastSegment] = { ...lastObject, ...data };

    return result as DataModel;
}

/**
 * Hook for consuming A2UI SSE streams.
 *
 * @param streamUrl - URL of the SSE stream
 * @param options - Configuration options
 * @returns State and actions for the A2UI stream
 */
export function useA2UIStream(
    streamUrl: string | null,
    options: UseA2UIStreamOptions = {}
): [A2UIStreamState, A2UIStreamActions] {
    const opts = { ...DEFAULT_OPTIONS, ...options };

    // State
    const [state, setState] = useState<A2UIStreamState>({
        isConnected: false,
        isLoading: true,
        error: null,
        surfaces: new Map(),
        dataModels: new Map(),
        isDone: false,
        retryCount: 0,
        connectionStatus: 'idle',
        pendingClarification: null,
    });

    // Refs
    const eventSourceRef = useRef<EventSource | null>(null);
    const processorRef = useRef<MessageProcessor | null>(null);
    const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    // Optimization #16: AbortController for fetch cleanup
    const abortControllerRef = useRef<AbortController | null>(null);
    // Debounce timer for state sync
    const syncTimerRef = useRef<NodeJS.Timeout | null>(null);

    // Update state from processor (debounced for performance)
    const syncState = useCallback(() => {
        if (!processorRef.current) return;

        // Debounce: cancel pending sync and schedule new one
        if (syncTimerRef.current) {
            clearTimeout(syncTimerRef.current);
        }

        syncTimerRef.current = setTimeout(() => {
            if (!processorRef.current) return;
            const { surfaces, dataModels } = processorRef.current.getState();
            setState((prev) => ({
                ...prev,
                surfaces: new Map(surfaces),
                dataModels: new Map(dataModels),
            }));
        }, 16); // ~1 frame at 60fps
    }, []);

    // Connect to the stream
    const connect = useCallback((isRetry = false) => {
        if (!streamUrl) return;

        // Clear any pending retry
        if (retryTimeoutRef.current) {
            clearTimeout(retryTimeoutRef.current);
            retryTimeoutRef.current = null;
        }

        // Close existing connection
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }

        // Create processor
        processorRef.current = createMessageProcessor(syncState, opts.onAudit);

        // Reset state - don't clear surfaces/dataModels to avoid content flash on cached replay
        // Let beginRendering or deleteSurface handle data updates
        setState((prev) => ({
            ...prev,
            isConnected: false,
            isLoading: true,
            error: null,
            isDone: false,
            connectionStatus: isRetry ? 'reconnecting' : 'connecting',
            pendingClarification: null,
        }));

        // Create EventSource
        const eventSource = new EventSource(streamUrl);
        eventSourceRef.current = eventSource;

        eventSource.onopen = () => {
            setState((prev) => ({
                ...prev,
                isConnected: true,
                isLoading: true,
                retryCount: 0,
                connectionStatus: 'connected',
            }));
        };

        // Handle clarification_request events from backend
        eventSource.addEventListener('clarification_request', (event) => {
            try {
                const clarification = JSON.parse((event as MessageEvent).data) as BackendClarificationRequest;
                setState((prev) => ({
                    ...prev,
                    pendingClarification: clarification,
                }));
            } catch (err) {
                console.error('Failed to parse clarification_request:', err);
            }
        });

        eventSource.onmessage = (event) => {
            const data = event.data;

            // Check for a "done" signal
            try {
                const json = JSON.parse(data);
                if (json && typeof json === 'object' && json.done === true) {
                    setState((prev) => ({
                        ...prev,
                        isDone: true,
                        isConnected: false,
                        connectionStatus: 'complete',
                    }));
                    eventSource.close();
                    return; // Stop processing this message
                }
            } catch (e) {
                // Not a JSON message, or not a "done" signal, proceed as normal
            }

            // Process A2UI messages (may be multiple lines)
            const lines = data.split('\n');
            for (const line of lines) {
                if (line.trim()) {
                    processorRef.current?.processLine(line);
                }
            }

            setState((prev) => ({ ...prev, isLoading: false }));
        };

        eventSource.onerror = (event) => {
            console.error('A2UI stream error:', event);
            eventSource.close();

            setState((prev) => {
                const newRetryCount = prev.retryCount + 1;

                if (newRetryCount <= MAX_RETRIES && !prev.isDone) {
                    // Calculate exponential backoff
                    const backoffMs = Math.min(
                        INITIAL_BACKOFF_MS * Math.pow(2, prev.retryCount),
                        MAX_BACKOFF_MS
                    );

                    console.log(`A2UI: Reconnecting in ${backoffMs}ms (attempt ${newRetryCount}/${MAX_RETRIES})`);

                    retryTimeoutRef.current = setTimeout(() => {
                        connect(true);
                    }, backoffMs);

                    return {
                        ...prev,
                        isConnected: false,
                        retryCount: newRetryCount,
                        connectionStatus: 'reconnecting',
                    };
                }

                // Max retries reached
                return {
                    ...prev,
                    isConnected: false,
                    isLoading: false,
                    error: new Error(`Stream connection lost after ${MAX_RETRIES} retries`),
                    connectionStatus: 'error',
                };
            });
        };
    }, [streamUrl, syncState]);

    // Close the stream
    const close = useCallback(() => {
        // Clear any pending retry
        if (retryTimeoutRef.current) {
            clearTimeout(retryTimeoutRef.current);
            retryTimeoutRef.current = null;
        }
        // Clear sync timer
        if (syncTimerRef.current) {
            clearTimeout(syncTimerRef.current);
            syncTimerRef.current = null;
        }
        // Abort any pending fetch requests (Optimization #16)
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }
        setState((prev) => ({
            ...prev,
            isConnected: false,
            connectionStatus: 'idle',
        }));
    }, []);

    // Send action to server and apply returned data to surface state
    const sendAction = useCallback(
        async (action: UserActionMessage['userAction']): Promise<unknown> => {
            if (!opts.dashboardId) {
                throw new Error('Dashboard ID not set');
            }

            // Create new AbortController for this request (Optimization #16)
            const controller = new AbortController();
            abortControllerRef.current = controller;

            try {
                const authHeaders = await authService.getAuthHeaders();
                const response = await fetch(`${opts.apiBaseUrl}/${opts.dashboardId}/action`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...authHeaders,
                    },
                    body: JSON.stringify({ userAction: action }),
                    signal: controller.signal,
                });

                if (!response.ok) {
                    throw new Error(`Action failed: ${response.statusText}`);
                }

                const result = await response.json();

                // Apply data update from action response to the surface state
                if (result.data && typeof result.data === 'object') {
                    const surfaceId = action.surfaceId;
                    const dataPath = typeof result.data_path === 'string' ? result.data_path : '/data';
                    if (surfaceId) {
                        setState((prev) => {
                            const newDataModels = new Map(prev.dataModels);
                            const existingModel = prev.dataModels.get(surfaceId) || {};
                            const updatedModel = mergeDataAtPath(
                                existingModel,
                                dataPath,
                                result.data as Record<string, unknown>
                            );
                            newDataModels.set(surfaceId, updatedModel);
                            return { ...prev, dataModels: newDataModels };
                        });
                    }
                }

                return result;
            } catch (err) {
                // Don't throw if aborted - component is unmounting
                if (err instanceof Error && err.name === 'AbortError') {
                    console.debug('Action request aborted');
                    return null;
                }
                throw err;
            }
        },
        [opts.dashboardId, opts.apiBaseUrl]
    );

    // Auto-connect on mount
    useEffect(() => {
        if (opts.autoConnect && streamUrl) {
            connect();
        }

        return () => {
            close();
        };
    }, [streamUrl, opts.autoConnect, connect, close]);

    // Clear clarification
    const clearClarification = useCallback(() => {
        setState((prev) => ({ ...prev, pendingClarification: null }));
    }, []);

    // Send conversational query through LLM-driven intent classification
    const sendQuery = useCallback(
        async (query: string): Promise<QueryResponse> => {
            if (!opts.dashboardId) {
                throw new Error('No dashboard ID for query');
            }

            // Create new AbortController for this request
            const controller = new AbortController();
            abortControllerRef.current = controller;

            try {
                const authHeaders = await authService.getAuthHeaders();
                const response = await fetch(`${opts.apiBaseUrl}/${opts.dashboardId}/query`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...authHeaders,
                    },
                    body: JSON.stringify({ query }),
                    signal: controller.signal,
                });

                if (!response.ok) {
                    throw new Error(`Query failed: ${response.statusText}`);
                }

                const result: QueryResponse = await response.json();

                // If this creates a new dashboard, emit event for page to handle
                if (result.status === 'new_dashboard' && result.dashboard_id) {
                    window.dispatchEvent(new CustomEvent('a2ui:new-dashboard', {
                        detail: {
                            dashboardId: result.dashboard_id,
                            surfaceId: result.result?.surface_id,
                            intent: result.intent,
                            rationale: result.rationale,
                        }
                    }));
                }

                // If data was modified, apply to current state
                const details = result.result?.details as Record<string, unknown> | undefined;
                const data = details?.data;
                if (data && typeof data === 'object') {
                    const surfaceId = Array.from(state.surfaces.keys())[0];
                    if (surfaceId) {
                        setState((prev) => {
                            const newDataModels = new Map(prev.dataModels);
                            const existingModel = prev.dataModels.get(surfaceId) || {};
                            const updatedModel = mergeDataAtPath(
                                existingModel,
                                '/data',
                                data as Record<string, unknown>
                            );
                            newDataModels.set(surfaceId, updatedModel);
                            return { ...prev, dataModels: newDataModels };
                        });
                    }
                }

                return result;
            } catch (err) {
                // Don't throw if aborted - component is unmounting
                if (err instanceof Error && err.name === 'AbortError') {
                    console.debug('Query request aborted');
                    return { status: 'error', intent: 'unknown', message: 'Request aborted' };
                }
                throw err;
            }
        },
        [opts.dashboardId, opts.apiBaseUrl, state.surfaces]
    );

    // Memoize actions to prevent unnecessary re-renders (Optimization #16)
    const actions: A2UIStreamActions = useMemo(() => ({
        sendAction,
        sendQuery,
        reconnect: () => connect(false),
        close,
        clearClarification,
    }), [sendAction, sendQuery, connect, close, clearClarification]);

    return [state, actions];
}

/**
 * Helper to get a single surface and its data model.
 */
export function useSurface(
    state: A2UIStreamState,
    surfaceId: string
): { surface: Surface | undefined; dataModel: DataModel } {
    return {
        surface: state.surfaces.get(surfaceId),
        dataModel: state.dataModels.get(surfaceId) || {},
    };
}
