import { useState, useCallback, useRef, useEffect } from 'react';

export interface SSEEvent {
    type: 'status' | 'thinking' | 'tool_start' | 'tool_end' | 'content' | 'chart' | 'data' | 'done' | 'error';
    data: Record<string, unknown>;
}

export interface ThinkingStep {
    step: string;
    status: 'pending' | 'running' | 'completed' | 'error';
    message: string;
}

export interface UseSSEStreamResult {
    isStreaming: boolean;
    content: string;
    thinkingSteps: ThinkingStep[];
    chartConfig: Record<string, unknown> | null;
    dataResult: { rows: unknown[]; columns: string[] } | null;
    error: string | null;
    sendMessage: (message: string, sessionId: string) => void;
    reset: () => void;
}

export function useSSEStream(apiUrl: string = '/api/conv-analytics/stream'): UseSSEStreamResult {
    const [isStreaming, setIsStreaming] = useState(false);
    const [content, setContent] = useState('');
    const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
    const [chartConfig, setChartConfig] = useState<Record<string, unknown> | null>(null);
    const [dataResult, setDataResult] = useState<{ rows: unknown[]; columns: string[] } | null>(null);
    const [error, setError] = useState<string | null>(null);

    const abortControllerRef = useRef<AbortController | null>(null);

    const reset = useCallback(() => {
        setContent('');
        setThinkingSteps([]);
        setChartConfig(null);
        setDataResult(null);
        setError(null);
    }, []);

    const sendMessage = useCallback(async (message: string, sessionId: string) => {
        // Abort any existing stream
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        reset();
        setIsStreaming(true);
        abortControllerRef.current = new AbortController();

        try {
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message, session_id: sessionId }),
                signal: abortControllerRef.current.signal,
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const reader = response.body?.getReader();
            if (!reader) {
                throw new Error('No response body');
            }

            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const event: SSEEvent = JSON.parse(line.slice(6));
                            handleEvent(event);
                        } catch {
                            // Ignore parse errors
                        }
                    }
                }
            }
        } catch (err) {
            if ((err as Error).name !== 'AbortError') {
                setError((err as Error).message);
            }
        } finally {
            setIsStreaming(false);
            abortControllerRef.current = null;
        }
    }, [apiUrl, reset]);

    const handleEvent = useCallback((event: SSEEvent) => {
        switch (event.type) {
            case 'thinking':
                setThinkingSteps(prev => {
                    const step = event.data.step as string;
                    const status = event.data.status as ThinkingStep['status'];
                    const message = (event.data.message as string) || '';

                    const existing = prev.find(s => s.step === step);
                    if (existing) {
                        return prev.map(s => s.step === step ? { ...s, status, message } : s);
                    }
                    return [...prev, { step, status, message }];
                });
                break;

            case 'content':
                setContent(prev => prev + (event.data.delta as string || ''));
                break;

            case 'chart':
                setChartConfig(event.data.config as Record<string, unknown>);
                break;

            case 'data':
                setDataResult({
                    rows: event.data.rows as unknown[],
                    columns: event.data.columns as string[],
                });
                break;

            case 'error':
                setError(event.data.message as string);
                break;

            case 'done':
                // Stream completed
                break;
        }
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, []);

    return {
        isStreaming,
        content,
        thinkingSteps,
        chartConfig,
        dataResult,
        error,
        sendMessage,
        reset,
    };
}
