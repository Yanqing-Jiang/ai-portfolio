/**
 * useA2UIStream Hook
 *
 * React hook for consuming A2UI SSE streams with automatic state management.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { createMessageProcessor, MessageProcessor } from './MessageProcessor';
import type { Surface, DataModel, UserActionMessage } from './types';

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
}

export interface A2UIStreamActions {
    /** Send a user action to the server */
    sendAction: (action: UserActionMessage['userAction']) => Promise<unknown>;
    /** Reconnect to the stream */
    reconnect: () => void;
    /** Close the stream */
    close: () => void;
}

export interface UseA2UIStreamOptions {
    /** Whether to auto-connect on mount */
    autoConnect?: boolean;
    /** Dashboard ID for the stream */
    dashboardId?: string;
    /** Base URL for API endpoints */
    apiBaseUrl?: string;
}

const DEFAULT_OPTIONS: UseA2UIStreamOptions = {
    autoConnect: true,
    apiBaseUrl: '/api/dash',
};

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
    });

    // Refs
    const eventSourceRef = useRef<EventSource | null>(null);
    const processorRef = useRef<MessageProcessor | null>(null);

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
    const connect = useCallback(() => {
        if (!streamUrl) return;

        // Close existing connection
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }

        // Create processor
        processorRef.current = createMessageProcessor(syncState);

        // Reset state
        setState((prev) => ({
            ...prev,
            isConnected: false,
            isLoading: true,
            error: null,
            isDone: false,
        }));

        // Create EventSource
        const eventSource = new EventSource(streamUrl);
        eventSourceRef.current = eventSource;

        eventSource.onopen = () => {
            setState((prev) => ({ ...prev, isConnected: true, isLoading: true }));
        };

        eventSource.onmessage = (event) => {
            const data = event.data;

            // Check for done signal
            if (data.includes('"done"')) {
                try {
                    const parsed = JSON.parse(data);
                    if (parsed.done === true) {
                        setState((prev) => ({ ...prev, isDone: true, isLoading: false }));
                        eventSource.close();
                        return;
                    }
                } catch {
                    // Not a done message, continue processing
                }
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
            setState((prev) => ({
                ...prev,
                isConnected: false,
                isLoading: false,
                error: new Error('Stream connection lost'),
            }));
            eventSource.close();
        };
    }, [streamUrl, syncState]);

    // Close the stream
    const close = useCallback(() => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }
        setState((prev) => ({
            ...prev,
            isConnected: false,
        }));
    }, []);

    // Send action to server
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

            return response.json();
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

    const actions: A2UIStreamActions = {
        sendAction,
        reconnect: connect,
        close,
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
