import { useState, useCallback, useRef, useEffect } from 'react';
import { authService } from '../../../services/auth';
import { configService } from '../../../services/config';

export interface SSEEvent {
    type: 'status' | 'thinking' | 'tool_start' | 'tool_end' | 'content' | 'chart' | 'data' | 'news' | 'skill' | 'plan' | 'plan_update' | 'done' | 'error' | 'debug' | 'selection_request' | 'selection_timeout' | 'selection_cancelled' | 'agent' | 'handoff' | 'process_node' | 'process_edge' | 'process_update' | 'process_clear' | 'html_artifact';
    data: Record<string, unknown>;
}

export interface SelectionOption {
    id: string;
    label: string;
    description?: string;
    payload: Record<string, unknown>;
}

export interface SelectionRequest {
    request_id: string;
    title: string;
    prompt: string;
    options: SelectionOption[];
    allow_custom: boolean;
    timeout_seconds: number;
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

export interface AgentInfo {
    id: string;
    name: string;
    role: string;
}

export interface HtmlArtifact {
    url: string;
    title: string;
    description: string;
}

export interface HandoffInfo {
    from: string;
    to: string;
    reason?: string;
    timestamp: number;
}

export interface ProcessNode {
    node_id: string;
    node_type: 'input' | 'decision' | 'action' | 'tool' | 'agent' | 'routing' | 'output';
    label: string;
    status: 'pending' | 'running' | 'completed' | 'error' | 'skipped';
    parent_id?: string;
    description?: string;
    data?: Record<string, unknown>;
    timestamp: number;
}

export interface ProcessEdge {
    from_node: string;
    to_node: string;
    edge_type: 'default' | 'decision_yes' | 'decision_no' | 'handoff';
    label?: string;
    animated: boolean;
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
    isPaused: boolean;
    content: string;
    thinkingSteps: ThinkingStep[];
    chartConfig: Record<string, unknown> | null;
    dataResult: { rows: unknown[]; columns: string[]; sql?: string } | null;
    newsResult: NewsResult | null;
    skillInfo: SkillInfo | null;
    htmlArtifact: HtmlArtifact | null;
    planSteps: PlanStep[];
    currentStepId: string | null;
    error: string | null;
    errorDetails: string | null;
    debugLogs: DebugLog[];
    pendingSelection: SelectionRequest | null;
    activeAgent: AgentInfo | null;
    handoffs: HandoffInfo[];
    processNodes: ProcessNode[];
    processEdges: ProcessEdge[];
    lastAgentLabel: string | null;
    runId: string | null;
    permissionState: string | null;
    sendMessage: (message: string, sessionId: string, agentMode?: string | null, options?: { resume?: boolean }) => void;
    pauseStream: () => void;
    resumeLast: () => void;
    submitSelection: (sessionId: string, optionId: string | null, customValue: string | null) => Promise<void>;
    cancelSelection: () => void;
    reset: () => void;
}

/**
 * Function: useSSEStream — called from ConversationalAnalyticsPage to stream Claude agent responses.
 * Invokes: POST to the backend conv-analytics SSE endpoint with Supabase auth headers, then delegates event parsing to handleEvent.
 * Purpose: Keeps the conversational analytics UI decoupled from transport/auth wiring while consuming the Claude Agent stream.
 */
export function useSSEStream(apiUrl: string = '/api/conv-analytics/stream'): UseSSEStreamResult {
    const [isStreaming, setIsStreaming] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [content, setContent] = useState('');
    const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
    const [chartConfig, setChartConfig] = useState<Record<string, unknown> | null>(null);
    const [dataResult, setDataResult] = useState<{ rows: unknown[]; columns: string[]; sql?: string } | null>(null);
    const [newsResult, setNewsResult] = useState<NewsResult | null>(null);
    const [skillInfo, setSkillInfo] = useState<SkillInfo | null>(null);
    const [htmlArtifact, setHtmlArtifact] = useState<HtmlArtifact | null>(null);
    const [planSteps, setPlanSteps] = useState<PlanStep[]>([]);
    const [currentStepId, setCurrentStepId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [errorDetails, setErrorDetails] = useState<string | null>(null);
    const [debugLogs, setDebugLogs] = useState<DebugLog[]>([]);
    const [pendingSelection, setPendingSelection] = useState<SelectionRequest | null>(null);
    const [activeAgent, setActiveAgent] = useState<AgentInfo | null>(null);
    const [handoffs, setHandoffs] = useState<HandoffInfo[]>([]);
    const [processNodes, setProcessNodes] = useState<ProcessNode[]>([]);
    const [processEdges, setProcessEdges] = useState<ProcessEdge[]>([]);
    const [lastAgentLabel, setLastAgentLabel] = useState<string | null>(null);
    const [runId, setRunId] = useState<string | null>(null);
    const [permissionState, setPermissionState] = useState<string | null>(null);

    const abortControllerRef = useRef<AbortController | null>(null);
    const lastMessageRef = useRef<string | null>(null);
    const lastSessionRef = useRef<string | null>(null);
    const lastAgentModeRef = useRef<string | null>(null);

    // Function: reset — called by ConversationalAnalyticsPage after a turn to clear prior stream state and errors.
    const reset = useCallback(() => {
        setContent('');
        setThinkingSteps([]);
        setChartConfig(null);
        setDataResult(null);
        setNewsResult(null);
        setSkillInfo(null);
        setHtmlArtifact(null);
        setPlanSteps([]);
        setCurrentStepId(null);
        setError(null);
        setErrorDetails(null);
        setDebugLogs([]);
        setPendingSelection(null);
        setActiveAgent(null);
        setHandoffs([]);
        setProcessNodes([]);
        setProcessEdges([]);
        setIsPaused(false);
        setRunId(null);
        setPermissionState(null);
    }, []);

    // Function: cancelSelection — clears pending HITL selection without submitting
    const cancelSelection = useCallback(() => {
        setPendingSelection(null);
    }, []);

    // Function: submitSelection — POSTs user's HITL choice to backend and clears pending state
    const submitSelection = useCallback(async (
        sessionId: string,
        optionId: string | null,
        customValue: string | null
    ) => {
        if (!pendingSelection) return;

        try {
            const backendUrl = configService.getBackendUrl();
            const authHeaders = await authService.getAuthHeaders();

            const response = await fetch(`${backendUrl}/api/conv-analytics/selection`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...authHeaders,
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    request_id: pendingSelection.request_id,
                    option_id: optionId,
                    custom_value: customValue,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            // Clear pending selection on success
            setPendingSelection(null);
        } catch (err) {
            setError(`Selection failed: ${(err as Error).message}`);
        }
    }, [pendingSelection]);

    // Function: sendMessage — called by ConversationalAnalyticsPage form submit; posts the user message to Claude SSE backend and streams events.
    const sendMessage = useCallback(async (message: string, sessionId: string, agentMode?: string | null, options?: { resume?: boolean }) => {
        // Abort any existing stream
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        if (!options?.resume) {
            reset();
        } else {
            // keep existing partial UI when resuming
            setError(null);
            setErrorDetails(null);
            setPendingSelection(null);
            setIsPaused(false);
        }
        setIsStreaming(true);
        abortControllerRef.current = new AbortController();
        lastMessageRef.current = message;
        lastSessionRef.current = sessionId;
        lastAgentModeRef.current = agentMode || null;

        try {
            const backendUrl = configService.getBackendUrl();
            const resolvedUrl = apiUrl.startsWith('http') ? apiUrl : `${backendUrl}${apiUrl}`;
            const authHeaders = await authService.getAuthHeaders();
            const payload: Record<string, unknown> = { message, session_id: sessionId };
            if (agentMode) {
                payload.agent_mode = agentMode;
            }

            const response = await fetch(resolvedUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...authHeaders,
                },
                body: JSON.stringify(payload),
                signal: abortControllerRef.current.signal,
            });

            if (response.status === 401) {
                setError('Sign-in required for Next Gen Analytics (Agent). Please log in and try again.');
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

    const pauseStream = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
            setIsStreaming(false);
            setIsPaused(true);
        }
    }, []);

    const resumeLast = useCallback(() => {
        if (!lastMessageRef.current || !lastSessionRef.current) return;
        sendMessage(lastMessageRef.current, lastSessionRef.current, lastAgentModeRef.current, { resume: true });
    }, [sendMessage]);

    // Function: handleEvent — invoked for each SSE payload to keep UI state in sync with Claude agent thinking/data.
    const handleEvent = useCallback((event: SSEEvent) => {
        const incomingRunId = event.data.run_id as string | undefined;
        if (incomingRunId) {
            setRunId(incomingRunId);
        }
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
                    sql: event.data.sql as string | undefined,
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

            case 'html_artifact':
                setHtmlArtifact({
                    url: event.data.url as string,
                    title: event.data.title as string,
                    description: event.data.description as string,
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
                setPermissionState((event.data.code as string) || null);
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

            case 'agent':
                setActiveAgent({
                    id: event.data.id as string,
                    name: event.data.name as string,
                    role: event.data.role as string,
                });
                setLastAgentLabel(`${event.data.name} • ${event.data.role}`);
                break;

            case 'handoff':
                setHandoffs(prev => [
                    ...prev,
                    {
                        from: event.data.from as string,
                        to: event.data.to as string,
                        reason: event.data.reason as string | undefined,
                        timestamp: Date.now() / 1000,
                    },
                ]);
                break;

            case 'selection_request':
                setPendingSelection({
                    request_id: event.data.request_id as string,
                    title: event.data.title as string,
                    prompt: event.data.prompt as string,
                    options: event.data.options as SelectionOption[],
                    allow_custom: event.data.allow_custom as boolean,
                    timeout_seconds: event.data.timeout_seconds as number,
                });
                break;

            case 'selection_timeout':
            case 'selection_cancelled':
                setPendingSelection(null);
                break;

            case 'process_node':
                setProcessNodes(prev => {
                    const newNode: ProcessNode = {
                        node_id: event.data.node_id as string,
                        node_type: event.data.node_type as ProcessNode['node_type'],
                        label: event.data.label as string,
                        status: event.data.status as ProcessNode['status'],
                        parent_id: event.data.parent_id as string | undefined,
                        description: event.data.description as string | undefined,
                        data: event.data.data as Record<string, unknown> | undefined,
                        timestamp: event.data.timestamp as number,
                    };
                    // Check if node already exists, update it
                    const existingIndex = prev.findIndex(n => n.node_id === newNode.node_id);
                    if (existingIndex >= 0) {
                        const updated = [...prev];
                        updated[existingIndex] = newNode;
                        return updated;
                    }
                    return [...prev, newNode];
                });
                break;

            case 'process_edge':
                setProcessEdges(prev => {
                    const newEdge: ProcessEdge = {
                        from_node: event.data.from_node as string,
                        to_node: event.data.to_node as string,
                        edge_type: (event.data.edge_type as ProcessEdge['edge_type']) || 'default',
                        label: event.data.label as string | undefined,
                        animated: event.data.animated as boolean || false,
                    };
                    // Avoid duplicate edges
                    const exists = prev.some(
                        e => e.from_node === newEdge.from_node && e.to_node === newEdge.to_node
                    );
                    if (exists) return prev;
                    return [...prev, newEdge];
                });
                break;

            case 'process_update':
                setProcessNodes(prev => prev.map(node => {
                    if (node.node_id === event.data.node_id) {
                        return {
                            ...node,
                            status: event.data.status as ProcessNode['status'],
                            description: (event.data.summary as string) || node.description,
                            data: event.data.data ? { ...node.data, ...event.data.data as Record<string, unknown> } : node.data,
                            timestamp: event.data.timestamp as number || node.timestamp,
                        };
                    }
                    return node;
                }));
                break;

            case 'process_clear':
                setProcessNodes([]);
                setProcessEdges([]);
                setLastAgentLabel(null);
                break;

            case 'done':
                // Stream completed: mark all nodes as completed unless errored
                setProcessNodes(prev => prev.map(node => (
                    node.status === 'error'
                        ? node
                        : { ...node, status: 'completed' }
                )));
                setPlanSteps(prev => prev.map(step => (
                    step.status === 'error'
                        ? step
                        : { ...step, status: 'completed' }
                )));
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
        htmlArtifact,
        planSteps,
        currentStepId,
        error,
        errorDetails,
        debugLogs,
        pendingSelection,
        activeAgent,
        handoffs,
        processNodes,
        processEdges,
        lastAgentLabel,
        sendMessage,
        pauseStream,
        resumeLast,
        submitSelection,
        cancelSelection,
        reset,
        isPaused,
        runId,
        permissionState,
    };
}
