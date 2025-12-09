import { useState, useCallback, useRef, useEffect } from 'react';
import { authService } from '../../../services/auth';
import { configService } from '../../../services/config';

export interface SSEEvent {
    type: 'status' | 'thinking' | 'tool_start' | 'tool_end' | 'content' | 'chart' | 'data' | 'news' | 'skill' | 'plan' | 'plan_update' | 'done' | 'error' | 'debug';
    data: Record<string, unknown>;
}

export interface DebugLog {
    category: string;
    message: string;
    timestamp: number;
    data?: Record<string, unknown>;
}

export interface NewsArticle {
    title: string;
    summary: string;
    url: string;
    source: string;
    published_at: string;
    sentiment_score: number;
    sentiment_label: string;
    sentiment_color: string;
    topics: string[];
}

export interface NewsResult {
    articles: NewsArticle[];
    ticker: string;
    aggregate_sentiment: number;
    aggregate_label: string;
}

export interface SkillInfo {
    id: string;
    name: string;
    download_url: string;
}

export interface ThinkingStep {
    step: string;
    status: 'pending' | 'running' | 'completed' | 'error';
    message: string;
}

export interface PlanStep {
    id: string;
    label: string;
    status: 'pending' | 'running' | 'completed' | 'error';
    summary?: string;
}

export interface UseSSEStreamResult {
    isStreaming: boolean;
    content: string;
    thinkingSteps: ThinkingStep[];
    chartConfig: Record<string, unknown> | null;
    dataResult: { rows: unknown[]; columns: string[] } | null;
    newsResult: NewsResult | null;
    skillInfo: SkillInfo | null;
    planSteps: PlanStep[];
    currentStepId: string | null;
    error: string | null;
    errorDetails: string | null;
    debugLogs: DebugLog[];
    sendMessage: (message: string, sessionId: string) => void;
    reset: () => void;
}

/**
 * Function: useSSEStream — called from ConversationalAnalyticsPage to stream Claude agent responses.
 * Invokes: POST to the backend conv-analytics SSE endpoint with Supabase auth headers, then delegates event parsing to handleEvent.
 * Purpose: Keeps the conversational analytics UI decoupled from transport/auth wiring while consuming the Claude Agent stream.
 */
export function useSSEStream(apiUrl: string = '/api/conv-analytics/stream'): UseSSEStreamResult {
    const [isStreaming, setIsStreaming] = useState(false);
    const [content, setContent] = useState('');
    const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
    const [chartConfig, setChartConfig] = useState<Record<string, unknown> | null>(null);
    const [dataResult, setDataResult] = useState<{ rows: unknown[]; columns: string[] } | null>(null);
    const [newsResult, setNewsResult] = useState<NewsResult | null>(null);
    const [skillInfo, setSkillInfo] = useState<SkillInfo | null>(null);
    const [planSteps, setPlanSteps] = useState<PlanStep[]>([]);
    const [currentStepId, setCurrentStepId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [errorDetails, setErrorDetails] = useState<string | null>(null);
    const [debugLogs, setDebugLogs] = useState<DebugLog[]>([]);

    const abortControllerRef = useRef<AbortController | null>(null);

    // Function: reset — called by ConversationalAnalyticsPage after a turn to clear prior stream state and errors.
    const reset = useCallback(() => {
        setContent('');
        setThinkingSteps([]);
        setChartConfig(null);
        setDataResult(null);
        setNewsResult(null);
        setSkillInfo(null);
        setPlanSteps([]);
        setCurrentStepId(null);
        setError(null);
        setErrorDetails(null);
        setDebugLogs([]);
    }, []);

    // Function: sendMessage — called by ConversationalAnalyticsPage form submit; posts the user message to Claude SSE backend and streams events.
    const sendMessage = useCallback(async (message: string, sessionId: string) => {
        // Abort any existing stream
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        reset();
        setIsStreaming(true);
        abortControllerRef.current = new AbortController();

        try {
            const backendUrl = configService.getBackendUrl();
            const resolvedUrl = apiUrl.startsWith('http') ? apiUrl : `${backendUrl}${apiUrl}`;
            const authHeaders = await authService.getAuthHeaders();

            const response = await fetch(resolvedUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...authHeaders,
                },
                body: JSON.stringify({ message, session_id: sessionId }),
                signal: abortControllerRef.current.signal,
            });

            if (response.status === 401) {
                setError('Sign-in required for conversational analytics. Please log in and try again.');
                return;
            }

            if (response.status === 429) {
                const retryAfter = response.headers.get('Retry-After');
                setError(retryAfter
                    ? `Rate limit exceeded. Try again in ${retryAfter} seconds.`
                    : 'Rate limit exceeded. Please try again shortly.'
                );
                return;
            }

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

    // Function: handleEvent — invoked for each SSE payload to keep UI state in sync with Claude agent thinking/data.
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

            case 'news':
                setNewsResult({
                    articles: event.data.articles as NewsArticle[],
                    ticker: event.data.ticker as string,
                    aggregate_sentiment: event.data.aggregate_sentiment as number,
                    aggregate_label: event.data.aggregate_label as string,
                });
                break;

            case 'skill':
                setSkillInfo({
                    id: event.data.id as string,
                    name: event.data.name as string,
                    download_url: event.data.download_url as string,
                });
                break;

            case 'plan':
                setPlanSteps((event.data.steps as PlanStep[]) ?? []);
                setCurrentStepId(
                    ((event.data.steps as PlanStep[]) ?? []).find(s => s.status === 'running')?.id || null
                );
                break;

            case 'plan_update':
                setPlanSteps(prev => prev.map(step => {
                    if (step.id === event.data.step_id) {
                        return {
                            ...step,
                            status: event.data.status as PlanStep['status'],
                            summary: (event.data.summary as string) || step.summary,
                        };
                    }
                    return step;
                }));
                setCurrentStepId(event.data.step_id as string);
                break;

            case 'error':
                setError(event.data.message as string);
                if (event.data.details) {
                    setErrorDetails(event.data.details as string);
                }
                // Add error to thinking steps for visibility in thinking panel
                setThinkingSteps(prev => {
                    const errorStep: ThinkingStep = {
                        step: event.data.code as string || 'error',
                        status: 'error',
                        message: event.data.message as string,
                    };
                    return [...prev, errorStep];
                });
                break;

            case 'debug':
                setDebugLogs(prev => [...prev, {
                    category: event.data.category as string,
                    message: event.data.message as string,
                    timestamp: event.data.timestamp as number,
                    data: event.data.data as Record<string, unknown> | undefined,
                }]);
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
        newsResult,
        skillInfo,
        planSteps,
        currentStepId,
        error,
        errorDetails,
        debugLogs,
        sendMessage,
        reset,
    };
}
