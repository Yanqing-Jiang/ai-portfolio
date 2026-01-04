// --- Function/Class Map ---
// Function: useA2UIStream
//   Role: Manage SSE connections, stream state, clarifications, and action updates.
//   Called from: components/generativeUiDashboard/GenerativeUIPage.tsx
//   Invokes: createMessageProcessor, EventSource, mergeDataAtPath
//   Why: Centralizes A2UI streaming state management for the dashboard UI.
// Function: useSurface
//   Role: Select a single surface + data model from stream state.
//   Called from: components/generativeUiDashboard/GenerativeUIPage.tsx
//   Invokes: Map.get
//   Why: Simplifies surface access for renderers.
// Function: mergeDataAtPath
//   Role: Merge action response data into the data model at a JSON-pointer path.
//   Called from: useA2UIStream.sendAction
//   Invokes: n/a
//   Why: Aligns action responses with /data-bound widgets.
// --- End Function/Class Map ---
/**
 * useA2UIStream Hook
 *
 * React hook for consuming A2UI SSE streams with automatic state management.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { createMessageProcessor, MessageProcessor } from './MessageProcessor';
import type { Surface, DataModel, UserActionMessage } from './types';

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

export interface A2UIStreamActions {
    /** Send a user action to the server */
    sendAction: (action: UserActionMessage['userAction']) => Promise<unknown>;
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
    apiBaseUrl: '/api/dash',
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

    // Update state from processor
    const syncState = useCallback(() => {
        if (!processorRef.current) return;

        const { surfaces, dataModels } = processorRef.current.getState();
        setState((prev) => ({
            ...prev,
            surfaces: new Map(surfaces),
            dataModels: new Map(dataModels),
        }));
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

        // Reset state
        setState((prev) => ({
            ...prev,
            isConnected: false,
            isLoading: true,
            error: null,
            isDone: false,
            connectionStatus: isRetry ? 'reconnecting' : 'connecting',
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

            const response = await fetch(`${opts.apiBaseUrl}/${opts.dashboardId}/action`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ userAction: action }),
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

    const actions: A2UIStreamActions = {
        sendAction,
        reconnect: () => connect(false),
        close,
        clearClarification,
    };

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
