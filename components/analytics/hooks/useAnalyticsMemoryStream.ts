import { useState, useRef, useCallback, useEffect } from 'react';
import { ChatMessage, ClarifyRequest, ClarifyAnswer, ToolCallTelemetry, AgentTurnTelemetry, AgentReasoningTelemetry, ProcessStep, ToolFanoutManifest, ToolFanoutResult, StockWidgetConfig, WebSearchResult, SingleAgentFanout, SingleAgentFanoutBranch, FanoutBranchStatus } from '../types';
import { apiService } from '../../../services/apiService';
import { useAnalyticsStream } from './useAnalyticsStream';

const AGENT_ROLE_CONFIG: Record<string, { stepId: string; lane: string; label: string }> = {
  planner_agent: { stepId: 'planner_agent', lane: 'planner', label: 'Planner Agent' },
  query_agent: { stepId: 'query_agent', lane: 'query', label: 'Query Agent' },
  analyst_agent: { stepId: 'analyst_agent', lane: 'analyst', label: 'Analyst Agent' },
  chart_agent: { stepId: 'chart_agent', lane: 'chart', label: 'Chart Agent' },
  market_agent: { stepId: 'market_agent', lane: 'market', label: 'Market Agent' },
  web_research_agent: { stepId: 'web_research_agent', lane: 'web', label: 'Web Research Agent' },
};

const DEFAULT_AGENT_ROLE = { stepId: 'agent_coordination', lane: 'coordination', label: 'Agent Coordination' };

import { useProcessSteps } from './useProcessSteps';
import { resolveChartSpecOption, applyChartOps } from '../utils';

export const useAnalyticsMemoryStream = (
  flow: 'planner-executor' | 'single-agent' | 'multi-agent' = 'planner-executor',
) => {
  const [sessionId, setSessionId] = useState<string>('');
  const [pendingClarification, setPendingClarification] = useState<ClarifyRequest | null>(null);

  const [criteria, setCriteria] = useState<any | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chartSpec, setChartSpec] = useState<any>(null);
  const [analysis, setAnalysis] = useState('');
  const [sqlQuery, setSqlQuery] = useState('');
  const [dataSample, setDataSample] = useState<any[] | null>(null);
  const [streamingText, setStreamingText] = useState('');
  const [webSearch, setWebSearch] = useState<WebSearchResult | null>(null);
  const [singleAgentFanout, setSingleAgentFanout] = useState<SingleAgentFanout | null>(null);
  const resultSentRef = useRef<boolean>(false);
  const summarySentRef = useRef<boolean>(false);
  const emitResultOnce = useCallback(() => {
    if (resultSentRef.current) return;
    resultSentRef.current = true;
    const newMessage = {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      type: 'result' as const,
      content: 'Analysis completed! Here are your results:',
      analysis: workflowDataRef.current.analysis || workflowDataRef.current.streamingText,
      chartSpec: workflowDataRef.current.chartSpec,
      sqlQuery: workflowDataRef.current.sqlQuery,
      dataSample: workflowDataRef.current.dataSample,
      stockWidgetConfig: workflowDataRef.current.stockWidget,
      toolFanoutManifest: workflowDataRef.current.toolFanoutManifest,
      toolFanoutResults: workflowDataRef.current.toolFanoutResults,
      webSearch: workflowDataRef.current.webSearch,
    };
    setChatHistory((prev) => [...prev, newMessage]);
  }, [setChatHistory]);
  
  // Progressive rendering: update state immediately instead of accumulating in refs
  const [progressiveAnalysis, setProgressiveAnalysis] = useState('');
  const [progressiveText, setProgressiveText] = useState('');

  const normalizeWebContext = (raw: any): WebSearchResult | null => {
    if (!raw) {
      return null;
    }
    const coerceString = (value: unknown): string | undefined => {
      if (typeof value !== 'string') {
        return undefined;
      }
      const trimmed = value.trim();
      return trimmed.length > 0 ? trimmed : undefined;
    };
    const snippets = Array.isArray(raw.snippets)
      ? raw.snippets.map((item: any) => ({
          title: coerceString(item?.title),
          url: coerceString(item?.url),
          snippet: coerceString(item?.snippet),
          display_url: coerceString(item?.display_url) ?? coerceString(item?.displayUrl),
          published_at: coerceString(item?.published_at) ?? coerceString(item?.publishedAt),
        }))
      : [];
    const error = coerceString(raw.error);
    const reason = coerceString(raw.reason) ?? coerceString(raw.error_stage);
    let summary = coerceString(raw.summary);
    // Override outdated Responses API summary lines with Gemini wording
    if (summary && /responses api/i.test(summary)) {
      summary = 'Web search unavailable (Gemini search error).';
    }
    if (!summary && (error === 'search_api_missing' || reason === 'search_api_missing')) {
      summary = 'Web search disabled until Gemini or Google Search API credentials are configured.';
    }
    const queryTerms = coerceString(raw.query_terms) ?? coerceString(raw.queryTerms);
    const searchTopic = coerceString(raw.search_topic) ?? coerceString(raw.searchTopic) ?? queryTerms;
    const query = coerceString(raw.query) ?? queryTerms ?? searchTopic;
    let searchTopicValue = searchTopic;
    const searchTopics = Array.isArray(raw.search_topics)
      ? raw.search_topics.map(coerceString).filter(Boolean) as string[]
      : (Array.isArray(raw.searchTopics) ? raw.searchTopics.map(coerceString).filter(Boolean) as string[] : undefined);
    const normalizeSnippet = (item: any) => ({
      title: coerceString(item?.title),
      url: coerceString(item?.url),
      snippet: coerceString(item?.snippet),
      display_url: coerceString(item?.display_url) ?? coerceString(item?.displayUrl),
      published_at: coerceString(item?.published_at) ?? coerceString(item?.publishedAt),
    });
    const topics = Array.isArray(raw.topics)
      ? raw.topics
          .map((topic: any, index: number) => ({
            label: coerceString(topic?.label) ?? `Topic ${index + 1}`,
            query: coerceString(topic?.query) ?? '',
            reason: coerceString(topic?.reason),
            summary: coerceString(topic?.summary),
            search_id: coerceString(topic?.search_id) ?? coerceString(topic?.searchId),
            latency_ms: typeof topic?.latency_ms === 'number' ? topic.latency_ms : (typeof topic?.latencyMs === 'number' ? topic.latencyMs : null),
            snippets: Array.isArray(topic?.snippets) ? topic.snippets.map(normalizeSnippet) : [],
          }))
          .filter((topic: any) => topic.query)
      : [];
    if (searchTopics && searchTopics.length && !searchTopicValue) {
      searchTopicValue = searchTopics[0];
    }
    return {
      query,
      queryTerms,
      searchTopic: searchTopicValue,
      searchTopics,
      summary,
      error,
      reason,
      snippets,
      annotations: Array.isArray(raw.annotations) ? raw.annotations : [],
      topics,
      searchId: coerceString(raw.search_id) ?? coerceString(raw.searchId),
      fromCache: raw.from_cache ?? raw.fromCache ?? raw.cache_hit ?? false,
      fetchedAt: coerceString(raw.fetched_at) ?? coerceString(raw.fetchedAt),
      latencyMs: typeof raw.latency_ms === 'number' ? raw.latency_ms : (typeof raw.latencyMs === 'number' ? raw.latencyMs : null),
      ready: raw.ready ?? (error !== 'search_api_missing' && reason !== 'search_api_missing'),
      provider: coerceString(raw.provider) ?? (raw.model ? 'Gemini' : undefined),
      model: coerceString(raw.model) ?? coerceString(raw.model_name) ?? coerceString(raw.modelName),
    };
  };

  // Ref for debouncing rapid updates
  const updateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pendingUpdatesRef = useRef<{
    analysis?: string;
    streamingText?: string;
    chartSpec?: any;
    sqlQuery?: string;
    dataSample?: any[];
  }>({});

  const toolTelemetryRef = useRef<ToolCallTelemetry[]>([]);
  const agentTurnsRef = useRef<AgentTurnTelemetry[]>([]);
  const agentReasoningRef = useRef<AgentReasoningTelemetry[]>([]);
  const toolFanoutRef = useRef<{ manifest: ToolFanoutManifest[]; results: ToolFanoutResult[]; concurrencyLimit: number }>({ manifest: [], results: [], concurrencyLimit: 0 });

  const refreshFanoutState = useCallback(() => {
    if (flow !== 'single-agent') {
      setSingleAgentFanout(null);
      return;
    }

    const manifest = toolFanoutRef.current.manifest || [];
    if (!manifest.length) {
      setSingleAgentFanout(null);
      return;
    }

    const canonical = (value?: string | null) => (
      value ? value.toString().toLowerCase().replace(/[^a-z0-9]+/g, '') : ''
    );

    const branchMap = new Map<string, SingleAgentFanoutBranch>();
    const aliasMap = new Map<string, string>();
    const branchOrder = new Map<string, number>();

    manifest.forEach((tool, index) => {
      const fallbackLabel = `Tool ${index + 1}`;
      const labelSource = tool.display_name || tool.name || fallbackLabel;
      const label = labelSource.replace(/_/g, ' ');
      const branchIdCandidate = canonical(tool.name) || canonical(tool.display_name) || `tool_${index}`;
      const branchId = branchIdCandidate || `tool_${index}`;
      const branch: SingleAgentFanoutBranch = {
        id: branchId,
        tool: tool.name || labelSource,
        label,
        description: tool.description || tool.summary,
        status: 'queued',
      };

      const metadata: Record<string, any> = {};
      if (tool.capabilities?.length) metadata.capabilities = tool.capabilities;
      if (tool.outputs?.length) metadata.outputs = tool.outputs;
      if (typeof tool.preview_only === 'boolean') metadata.preview_only = tool.preview_only;
      if (tool.summary) metadata.summary = tool.summary;
      if (Object.keys(metadata).length) {
        branch.metadata = metadata;
      }

      branchMap.set(branchId, branch);
      branchOrder.set(branchId, index);

      const aliasCandidates = [
        tool.name,
        tool.display_name,
        tool.description,
        tool.summary,
        labelSource,
      ];

      aliasCandidates.forEach((alias) => {
        const key = canonical(alias);
        if (key && !aliasMap.has(key)) {
          aliasMap.set(key, branchId);
        }
      });

      aliasMap.set(branchId, branchId);
    });

    const resolveBranchId = (rawName?: string | null) => {
      const canonicalName = canonical(rawName);
      if (canonicalName && aliasMap.has(canonicalName)) {
        return aliasMap.get(canonicalName)!;
      }
      if (canonicalName) {
        for (const [key, value] of aliasMap.entries()) {
          if (key && (key.includes(canonicalName) || canonicalName.includes(key))) {
            return value;
          }
        }
      }
      return undefined;
    };

    const ensureBranch = (rawName?: string | null, labelFallback?: string) => {
      const resolved = resolveBranchId(rawName);
      if (resolved && branchMap.has(resolved)) {
        return resolved;
      }
      const canonicalName = canonical(rawName);
      const branchId = canonicalName || `tool_${branchMap.size}`;
      const labelSource = rawName || labelFallback || `Tool ${branchMap.size + 1}`;
      const branch: SingleAgentFanoutBranch = {
        id: branchId,
        tool: rawName || labelSource,
        label: labelSource.replace(/_/g, ' '),
        status: 'queued',
      };
      branchMap.set(branchId, branch);
      branchOrder.set(branchId, branchOrder.size + manifest.length);
      if (canonicalName && !aliasMap.has(canonicalName)) {
        aliasMap.set(canonicalName, branchId);
      }
      aliasMap.set(branchId, branchId);
      return branchId;
    };

    const resultsByBranch = new Map<string, ToolFanoutResult>();
    toolFanoutRef.current.results.forEach((result) => {
      const branchId = ensureBranch(result.tool, result.tool);
      resultsByBranch.set(branchId, result);
    });

    const telemetryByBranch = new Map<string, ToolCallTelemetry[]>();
    toolTelemetryRef.current.forEach((entry) => {
      const branchId = ensureBranch(entry.tool, entry.tool);
      const list = telemetryByBranch.get(branchId) ?? [];
      list.push(entry);
      telemetryByBranch.set(branchId, list);
    });

    const normalizeStatus = (raw?: string | null, fallback: FanoutBranchStatus = 'queued'): FanoutBranchStatus => {
      if (!raw) {
        return fallback;
      }
      const value = raw.toString().toLowerCase();
      if (['success', 'complete', 'completed', 'ok', 'done', 'finished', 'end'].includes(value)) {
        return 'completed';
      }
      if (['running', 'in_progress', 'active', 'processing', 'start', 'started', 'working'].includes(value)) {
        return 'running';
      }
      if (['pending', 'queued', 'waiting', 'idle', 'ready'].includes(value)) {
        return 'queued';
      }
      if (['cancelled', 'canceled', 'skipped', 'reuse', 'stopped', 'aborted', 'halted'].includes(value)) {
        return 'stopped';
      }
      if (['failed', 'error', 'timeout', 'fatal', 'exception', 'unavailable', 'bad_request'].includes(value)) {
        return 'failed';
      }
      return fallback;
    };

    const branches = Array.from(branchMap.entries())
      .map(([id, branch]) => {
        const telemetry = telemetryByBranch.get(id) ?? [];
        const result = resultsByBranch.get(id);

        let status: FanoutBranchStatus = branch.status ?? 'queued';
        let startedAt: string | null | undefined;
        let completedAt: string | null | undefined;
        let elapsedMs: number | undefined;
        let error: string | null | undefined = branch.error ?? null;

        const startEvent = telemetry.find((event) => event.status === 'start');
        const endEvent = [...telemetry].reverse().find((event) => event.status === 'end');

        if (startEvent) {
          startedAt = startEvent.ts ?? null;
          status = 'running';
        }

        if (endEvent && !result) {
          completedAt = endEvent.ts ?? null;
          elapsedMs = endEvent.elapsed_ms ?? elapsedMs;
          if (status === 'running') {
            status = 'completed';
          }
        }

        if (result) {
          status = normalizeStatus(result.status, result.error || result.fatal ? `failed` : status);
          startedAt = result.started_at ?? startedAt ?? null;
          completedAt = result.completed_at ?? completedAt ?? null;
          elapsedMs = result.elapsed_ms ?? elapsedMs;
          if (result.error) {
            error = result.error;
          }
          if (result.metadata) {
            branch.metadata = { ...(branch.metadata ?? {}), resultMetadata: result.metadata };
          }
          if (result.payload) {
            branch.payload = result.payload;
          }
          if (result.fatal && status !== `failed`) {
            status = 'failed';
          }
        }

        branch.status = status;
        branch.startedAt = startedAt ?? branch.startedAt ?? null;
        branch.completedAt = completedAt ?? branch.completedAt ?? null;
        if (elapsedMs !== undefined) {
          branch.elapsedMs = elapsedMs;
        }
        if (error) {
          branch.error = error;
        }

        return branch;
      })
      .sort((a, b) => {
        const orderA = branchOrder.get(a.id) ?? Number.MAX_SAFE_INTEGER;
        const orderB = branchOrder.get(b.id) ?? Number.MAX_SAFE_INTEGER;
        if (orderA !== orderB) {
          return orderA - orderB;
        }
        return a.label.localeCompare(b.label);
      });

    let completedCount = 0;
    let runningCount = 0;
    let failedCount = 0;
    let queuedCount = 0;
    let stoppedCount = 0;

    branches.forEach((branch) => {
      switch (branch.status) {
        case 'completed':
          completedCount += 1;
          break;
        case 'running':
          runningCount += 1;
          break;
        case 'failed':
          failedCount += 1;
          break;
        case 'stopped':
          stoppedCount += 1;
          break;
        default:
          queuedCount += 1;
          break;
      }
    });

    setSingleAgentFanout({
      hasFanout: true,
      branches,
      concurrencyLimit: toolFanoutRef.current.concurrencyLimit || manifest.length,
      activeCount: runningCount,
      runningCount,
      completedCount,
      failedCount,
      queuedCount,
      stoppedCount,
      lastUpdated: new Date().toISOString(),
    });
  }, [flow]);

  useEffect(() => {
    if (flow !== 'single-agent') {
      setSingleAgentFanout(null);
      return;
    }
    refreshFanoutState();
  }, [flow, refreshFanoutState]);

  const sqlAttemptsRef = useRef<any[]>([]);
  const agentLaneStateRef = useRef<Record<string, ProcessStep['status']>>({});

  // Workflow data ref for result accumulation
  const workflowDataRef = useRef<{
    chartSpec: any;
    analysis: string;
    sqlQuery: string;
    dataSample: any[] | null;
    streamingText: string;
    criteria: any | null;
    stockWidget: StockWidgetConfig | null;
    toolFanoutManifest: ToolFanoutManifest[];
    toolFanoutResults: ToolFanoutResult[];
    concurrencyLimit: number;
  }>({
    chartSpec: null,
    analysis: '',
    sqlQuery: '',
    dataSample: null,
    streamingText: '',
    criteria: null,
    stockWidget: null,
    toolFanoutManifest: [],
    toolFanoutResults: [],
    concurrencyLimit: 0,
    webSearch: null
  });

  const streamHook = useAnalyticsStream();
  const stepsHook = useProcessSteps();

  // Progressive update function with debouncing
  const scheduleProgressiveUpdate = (updates: Partial<typeof pendingUpdatesRef.current>) => {
    // Merge pending updates
    Object.assign(pendingUpdatesRef.current, updates);

    // Clear existing timeout
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }

    // Schedule batched update for better performance
    updateTimeoutRef.current = setTimeout(() => {
      const pending = pendingUpdatesRef.current;

      if (pending.analysis !== undefined) {
        setAnalysis(pending.analysis);
        setProgressiveAnalysis(pending.analysis);
        workflowDataRef.current.analysis = pending.analysis;
      }
      if (pending.streamingText !== undefined) {
        setStreamingText(pending.streamingText);
        setProgressiveText(pending.streamingText);
        workflowDataRef.current.streamingText = pending.streamingText;
      }
      if (pending.chartSpec !== undefined) {
        setChartSpec(pending.chartSpec);
        workflowDataRef.current.chartSpec = pending.chartSpec;
      }
      if (pending.sqlQuery !== undefined) {
        setSqlQuery(pending.sqlQuery);
        workflowDataRef.current.sqlQuery = pending.sqlQuery;
      }
      if (pending.dataSample !== undefined) {
        setDataSample(pending.dataSample);
        workflowDataRef.current.dataSample = pending.dataSample;
      }

      // Clear pending updates
      pendingUpdatesRef.current = {};
    }, 50); // 50ms debounce for smooth updates
  };

  const resolveAgentConfig = (role: string) => AGENT_ROLE_CONFIG[role] ?? DEFAULT_AGENT_ROLE;

  const computeAggregateStatus = (fallback: ProcessStep['status'] = 'pending'): ProcessStep['status'] => {
    const laneStates = Object.values(agentLaneStateRef.current);
    if (laneStates.some((state) => state === 'error')) {
      return 'error';
    }
    if (laneStates.some((state) => state === 'in_progress')) {
      return 'in_progress';
    }
    if (laneStates.some((state) => state === 'completed')) {
      return 'completed';
    }
    return fallback;
  };

  const buildLaneSummary = () => {
    const entries = Object.entries(agentLaneStateRef.current);
    if (!entries.length) {
      return ['Awaiting agent activity'];
    }
    return entries.map(([stepId, status]) => {
      const roleConfig = Object.values(AGENT_ROLE_CONFIG).find((config) => config.stepId === stepId) ?? DEFAULT_AGENT_ROLE;
      const statusLabel = status.replace('_', ' ');
      return `${roleConfig.label}: ${statusLabel}`;
    });
  };

  const updateAgentCoordination = (
    messages: string[] = [],
    statusOverride?: ProcessStep['status'],
    meta?: { ts?: string; elapsed_ms?: number; sequence?: number },
  ) => {
    const summary = messages.length ? messages : buildLaneSummary();
    const aggregateStatus = statusOverride ?? computeAggregateStatus();
    stepsHook.updateStepStatus(
      'agent_coordination',
      aggregateStatus,
      summary,
      {
        agent_turns: [...agentTurnsRef.current],
        agent_reasoning: [...agentReasoningRef.current],
        agent_status: { ...agentLaneStateRef.current },
      },
      meta?.elapsed_ms,
      meta?.ts,
      meta?.sequence,
      'coordination',
    );
  };

  const recordToolCallEvent = (payload: any, meta?: { ts?: string; elapsed_ms?: number; sequence?: number; parallel_group?: string; tool_group?: string }) => {
    if (!payload || !payload.tool || !payload.status) {
      return;
    }

    const entry: ToolCallTelemetry = {
      tool: payload.tool,
      status: payload.status,
      ts: meta?.ts || payload.ts,
      elapsed_ms: meta?.elapsed_ms ?? payload.elapsed_ms,
      details: payload.details,
      sequence: meta?.sequence ?? payload.sequence,
      parallelGroup: meta?.parallel_group ?? payload.parallel_group,
      toolGroup: meta?.tool_group ?? payload.tool_group,
    };

    toolTelemetryRef.current = [...toolTelemetryRef.current, entry].slice(-15);

    const elapsed = meta?.elapsed_ms ?? payload.elapsed_ms;
    const ts = meta?.ts || payload.ts;
    const statusLabel = payload.status === 'start' ? 'started' : payload.status === 'end' ? 'completed' : payload.status;
    const durationText = elapsed ? ` (${elapsed}ms)` : '';
    const message = `Tool ${payload.tool} ${statusLabel}${durationText}`;

    stepsHook.updateStepStatus(
      'tool_execution',
      'in_progress',
      [message],
      { tool_calls: [...toolTelemetryRef.current] },
      elapsed,
      ts,
      meta?.sequence,
      meta?.parallel_group,
    );
    refreshFanoutState();
  };

  const recordAgentTurnEvent = (payload: any, meta?: { ts?: string; elapsed_ms?: number; sequence?: number; parallel_group?: string }) => {
    if (!payload || !payload.role || !payload.status) {
      return;
    }

    const config = resolveAgentConfig(payload.role);
    const ts = meta?.ts || payload.ts;
    const elapsed = meta?.elapsed_ms ?? payload.elapsed_ms;
    const sequence = meta?.sequence ?? payload.sequence;

    const entry: AgentTurnTelemetry = {
      role: payload.role,
      status: payload.status,
      ts,
      elapsed_ms: elapsed,
      summary: payload.summary,
      sequence,
      parallelGroup: meta?.parallel_group ?? payload.parallel_group ?? config.lane,
    };
    agentTurnsRef.current = [...agentTurnsRef.current, entry].slice(-15);

    const status: ProcessStep['status'] = payload.status === 'complete'
      ? 'completed'
      : payload.status === 'error'
        ? 'error'
        : payload.status === 'skip' || payload.status === 'reuse'
          ? 'completed'
          : 'in_progress';

    agentLaneStateRef.current[config.stepId] = status;

    const rawSummary = payload.summary;
    const summaryText = typeof rawSummary === 'string'
      ? rawSummary
      : rawSummary
        ? JSON.stringify(rawSummary)
        : undefined;
    const laneMessage = summaryText
      ? `${config.label}: ${summaryText}`
      : `${config.label}: ${payload.status}`;

    stepsHook.updateStepStatus(
      config.stepId,
      status,
      [laneMessage],
      {
        agent_turns: [...agentTurnsRef.current],
        agent_reasoning: [...agentReasoningRef.current],
        latest_summary: rawSummary,
      },
      elapsed,
      ts,
      sequence,
      config.lane,
    );

    updateAgentCoordination([laneMessage], status === 'error' ? 'error' : undefined, { ts, elapsed_ms: elapsed, sequence });
  };



  const recordAgentReasoningEvent = (payload: any, meta?: { ts?: string; elapsed_ms?: number; sequence?: number; parallel_group?: string }) => {
    if (!payload || (!payload.thought && !payload.message)) {
      return;
    }

    const config = resolveAgentConfig(payload.role || 'agent_coordination');
    const ts = meta?.ts || payload.ts;
    const elapsed = meta?.elapsed_ms ?? payload.elapsed_ms;
    const sequence = meta?.sequence ?? payload.sequence;
    const parallelGroup = meta?.parallel_group ?? payload.parallel_group ?? config.lane;

    const entry: AgentReasoningTelemetry = {
      role: payload.role || config.stepId,
      thought: payload.thought || payload.message,
      ts,
      sequence,
      parallelGroup,
    };
    agentReasoningRef.current = [...agentReasoningRef.current, entry].slice(-40);

    const thoughtText = typeof entry.thought === 'string' ? entry.thought : JSON.stringify(entry.thought);
    const laneStatus = agentLaneStateRef.current[config.stepId] ?? 'in_progress';

    stepsHook.updateStepStatus(
      config.stepId,
      laneStatus === 'completed' ? laneStatus : 'in_progress',
      [thoughtText],
      {
        agent_reasoning: [...agentReasoningRef.current],
        agent_turns: [...agentTurnsRef.current],
        latest_thought: entry.thought,
      },
      elapsed,
      ts,
      sequence,
      parallelGroup,
    );

    updateAgentCoordination([`${config.label}: ${thoughtText}`], undefined, { ts, elapsed_ms: elapsed, sequence });

    if (config.stepId === 'analyst_agent') {
      stepsHook.updateStepStatus(
        'analysis_generation',
        'in_progress',
        [thoughtText],
        undefined,
        undefined,
        ts,
      );
    }
  };




  // Chat history management
  const addChatMessage = (message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
    };
    setChatHistory(prev => [...prev, newMessage]);
    return newMessage.id;
  };

  const updateChatMessage = (id: string, updates: Partial<ChatMessage>) => {
    setChatHistory(prev => prev.map(msg => msg.id === id ? { ...msg, ...updates } : msg));
  };

  const submitClarification = async (value: any, request?: ClarifyRequest) => {
    const req = request || pendingClarification;
    if (!req) return;
    try {
      const answer: ClarifyAnswer = {
        session_id: req.session_id || sessionId,
        request_id: req.request_id,
        slot: req.slot,
        value,
        ts: new Date().toISOString(),
      };
      await apiService.post('/api/analytics/memory/clarify', answer);
      setPendingClarification(null);
    } catch (e: any) {
      streamHook.setError(`Failed to submit clarification: ${e?.message || e}`);
    }
  };

  const handleQuery = async (query: string) => {
    if (!query.trim()) return;
    
    // Stop any existing stream before starting a new one
    if (streamHook.isLoading) {
      streamHook.stopStream();
      // Wait a brief moment for the stream to be properly closed
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    // Add user query to chat history
    addChatMessage({
      type: 'user',
      content: query.trim(),
    });
    
    // Reset only temporary state for new query (keep results in chat history)
    setStreamingText('');
    setProgressiveText('');
    setProgressiveAnalysis('');
    setWebSearch(null);
    workflowDataRef.current.webSearch = null;
    setPendingClarification(null);
    setCriteria(null);
    stepsHook.resetSteps();

    // Clear any pending updates
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }
    pendingUpdatesRef.current = {};

    toolTelemetryRef.current = [];
    agentTurnsRef.current = [];
    agentReasoningRef.current = [];

    const baseEndpoint = `/api/analytics/memory/stream`;

    const params = new URLSearchParams({ query: query.trim() });
    if (sessionId) {
      params.append('session_id', sessionId);
    }
    if (flow) {
      params.append('flow', flow);
    }

    const endpoint = `${baseEndpoint}?${params.toString()}`;

    await streamHook.startStream(endpoint, (data) => {
      const eventType = data.event || data.type;
      // Handle both old (heavy) and new (lightweight) event formats
      const eventData = data.data || data;
      const eventVisibility =
        typeof data.event_type === 'string' ? data.event_type : 'user';
      const isThinkingEvent = eventVisibility === 'thinking';

      // For lightweight events, extract step and timing info from top level
      const stepInfo = {
        step: data.step || eventData.step,
        ts: data.ts || eventData.ts,
        elapsed_ms: data.elapsed_ms || eventData.elapsed_ms
      };
            const sequence: number | undefined =
        typeof data.seq === 'number'
          ? data.seq
          : typeof eventData.sequence === 'number'
          ? eventData.sequence
          : undefined;
      const parallelGroup: string | undefined =
        typeof data.parallel_group === 'string'
          ? data.parallel_group
          : typeof eventData.parallel_group === 'string'
          ? eventData.parallel_group
          : undefined;
      const toolGroup: string | undefined =
        typeof data.tool_group === 'string'
          ? data.tool_group
          : typeof eventData.tool_group === 'string'
          ? eventData.tool_group
          : undefined;

      const updateStep = (
        stepId: string,
        status: ProcessStep['status'],
        thinking: string[] = [],
        details?: any,
        elapsed?: number,
        ts?: string,
      ) => {
        stepsHook.updateStepStatus(stepId, status, thinking, details, elapsed, ts, sequence, parallelGroup);
      };
      
      switch (eventType) {
        case 'session_started':
          setSessionId(eventData.session_id);
          break;
          

        case 'status':
        case 'progress':
          // Handle both old 'status' and new 'progress' event types
          const statusMessage = eventData.message || data.message || '';
          streamHook.setCurrentStatus(statusMessage);
          if (stepInfo.step) {
            const thinkingLogs: string[] = [];
            if (isThinkingEvent && statusMessage) {
              thinkingLogs.push(statusMessage);
            }
            if (eventData.code) {
              const codeTag = statusMessage ? `${statusMessage} [${eventData.code}]` : `Code: ${eventData.code}`;
              if (!thinkingLogs.includes(codeTag)) {
                thinkingLogs.push(codeTag);
              }
            }
            const detailPayload = eventData.code || eventData.attempt
              ? {
                  code: eventData.code,
                  attempt: eventData.attempt,
                  message: statusMessage,
                }
              : undefined;
            updateStep((stepInfo.step === 'web_search' ? 'web_research_agent' : stepInfo.step), 'in_progress', thinkingLogs, detailPayload, stepInfo.elapsed_ms, stepInfo.ts);
          }
          break;
          
        case 'intent_draft':
          updateStep('intent_detection', 'in_progress', ['Intent detected; needs clarification'], eventData, eventData.elapsed_ms);
          break;
          
        case 'intent_decided':
        case 'intent_resolved':
          // Handle both old heavy format and new lightweight format
          const intentData = eventData.intent || eventData; // Old format has nested intent, new format is flat
          updateStep('intent_detection', 'completed', [], intentData, stepInfo.elapsed_ms, stepInfo.ts);
          updateStep('clarification', 'completed', ['Clarifications resolved'], intentData, stepInfo.elapsed_ms, stepInfo.ts);
          setPendingClarification(null);
          break;
          
        case 'clarification_request':
          console.log('?? [DEBUG] Received clarification_request:', eventData);
          setPendingClarification(eventData as ClarifyRequest);
          updateStep('clarification', 'in_progress', [eventData.question]);
          streamHook.setCurrentStatus(`Clarification needed: ${eventData.question}`);
          const clarificationMessage = {
            type: 'clarification' as const,
            content: eventData.question,
            clarifications: [eventData as ClarifyRequest],
          };
          console.log('?? [DEBUG] Adding clarification message:', clarificationMessage);
          addChatMessage(clarificationMessage);
          break;
          
        case 'clarification_ack':
          setPendingClarification(null);
          addChatMessage({
            type: 'user',
            content: `${eventData.answer}`,
          });
          stepsHook.updateStepStatus('clarification', 'in_progress', ['Processing your answer...']);
          streamHook.setCurrentStatus('Processing your clarification answer...');
          break;
          
        case 'plan_built':
          // Combined planning step for streamlined agent flow
          // Handle both old (eventData.plan) and new (simplified) formats
          const planData = eventData.plan || { metrics_count: eventData.metrics_count, granularity: eventData.granularity, comparison: eventData.comparison };
          stepsHook.updateStepStatus('plan_and_select_template', 'in_progress', ['Plan built'], { plan: planData }, stepInfo.elapsed_ms);
          break;

        case 'template_selected':
          // Complete combined planning + selection step
          // Handle both old (eventData.template) and new (eventData.template_id) formats
          const templateId = eventData.template?.id || eventData.template_id;
          const templateData = eventData.template || { id: templateId, has_template: eventData.has_template };
          stepsHook.updateStepStatus('plan_and_select_template', 'completed', [
            templateId ? `Selected template: ${templateId}` : 'Template selected'
          ], { template: templateData }, stepInfo.elapsed_ms);
          break;
          
        case 'sql_compiled':
          {
            const attempt = eventData.attempt ?? 1;
            const messages = [`SQL compiled (len: ${eventData.sql_length})`];
            if (eventData.fallback_reason) {
              messages.push(`Fallback: ${eventData.fallback_reason.replace(/_/g, ' ')}`);
            }
            stepsHook.updateStepStatus(
              'sql_compilation',
              'completed',
              messages,
              {
                sql_length: eventData.sql_length,
                template_used: eventData.template_used,
                template_fallback: eventData.template_fallback,
                fallback_reason: eventData.fallback_reason,
                attempt,
                llm_used: eventData.llm_used,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts
            );
            if (eventData.fallback_reason) {
              streamHook.setCurrentStatus(`Template fallback applied: ${eventData.fallback_reason.replace(/_/g, ' ')}`);
            }
          }
          break;

        case 'sql_generated':
          if (typeof eventData.sql === 'string') {
            scheduleProgressiveUpdate({ sqlQuery: eventData.sql });
          }
          stepsHook.updateStepStatus(
            'sql_compilation',
            'completed',
            [`SQL ready (attempt ${eventData.attempt ?? 1})`],
            {
              sql: eventData.sql,
              attempt: eventData.attempt,
              llm_used: eventData.llm_used,
              fallback_reason: eventData.fallback_reason,
            },
            stepInfo.elapsed_ms,
            stepInfo.ts
          );
          break;


        case 'sql_validated':
          {
            const attempt = eventData.attempt ?? 1;
            const issues = Array.isArray(eventData.issues) ? eventData.issues : [];
            const validationMessages = eventData.ok
              ? [`SQL validation passed (attempt ${attempt})`]
              : [issues.length ? `Validation issues: ${issues.join(', ')}` : `Validation failed (attempt ${attempt})`];
            stepsHook.updateStepStatus(
              'sql_validation',
              eventData.ok ? 'completed' : 'error',
              validationMessages,
              {
                ok: eventData.ok,
                issues,
                issues_count: eventData.issues_count,
                attempt,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts
            );
            if (!eventData.ok) {
              streamHook.setCurrentStatus('SQL validation issues detected; applying fallback');
            }
          }
          break;
          
        case 'execution_stats':
          // Handle both old (eventData.columns) and new (eventData.columns_count) formats
          const executionData = {
            row_count: eventData.row_count,
            columns: eventData.columns || [],
            columns_count: eventData.columns_count || (eventData.columns ? eventData.columns.length : 0)
          };
          stepsHook.updateStepStatus('sql_execution', 'completed', [], executionData, stepInfo.elapsed_ms);
          break;
          
        case 'data_retrieved':
          // Handle both old and new formats
          if (Array.isArray(eventData.sample_data)) {
            scheduleProgressiveUpdate({ dataSample: eventData.sample_data });
          }
          stepsHook.updateStepStatus('sql_execution', 'completed', [], {
            rowCount: eventData.row_count,
            sampleData: eventData.sample_data || []
          });
          try {
            const rc = typeof eventData.row_count === 'number' ? eventData.row_count : (eventData.sample_data?.length ?? 0);
            updateAgentCoordination([`Rows retrieved: ${rc}`]);
          } catch {}
          break;
          
        case 'echarts_complete': {
          const normalizedChartSpec =
            resolveChartSpecOption(eventData) ??
            resolveChartSpecOption(data) ??
            eventData.chart_spec ??
            (data as any)?.chart_spec ??
            null;

          const chartType =
            eventData.chart_type ??
            (typeof eventData.chart_spec === 'object' && eventData.chart_spec
              ? eventData.chart_spec.chart_type
              : undefined) ??
            (typeof (data as any)?.chart_spec === 'object'
              ? (data as any).chart_spec.chart_type
              : undefined) ??
            normalizedChartSpec?.meta?.chartDesign?.chart_type;

          if (normalizedChartSpec) {
            scheduleProgressiveUpdate({ chartSpec: normalizedChartSpec });
          } else {
            console.warn('[AnalyticsMemoryStream] echarts_complete event without chart_spec payload', { event: data });
            streamHook.setError('Chart generation completed without a chart spec payload.');
          }

          stepsHook.updateStepStatus(
            'chart_generation',
            normalizedChartSpec ? 'completed' : 'error',
            normalizedChartSpec ? [] : ['Chart spec missing in echarts_complete event'],
            { chart_spec: normalizedChartSpec, chart_type: chartType },
            stepInfo.elapsed_ms,
            stepInfo.ts
          );
          try {
            const seriesCount = Array.isArray(normalizedChartSpec?.series) ? normalizedChartSpec.series.length : undefined;
            const msg = `Chart complete${chartType ? ` (type: ${chartType})` : ''}${seriesCount!=null ? `, series: ${seriesCount}` : ''}`;
            updateAgentCoordination([msg]);
          } catch {}
          break;
        }

        case 'echarts_error': {
          const errorMessage = eventData.error || 'Chart generation failed';
          stepsHook.updateStepStatus(
            'chart_generation',
            'error',
            [errorMessage],
            {
              error: errorMessage,
              details: eventData.details,
            },
            stepInfo.elapsed_ms,
            stepInfo.ts
          );
          streamHook.setError('Chart generation error: ' + errorMessage);
          break;
        }

        case 'chart_generated': {
          // Normalize chart payloads from legacy + lightweight emitters
          const normalizedChartSpec =
            resolveChartSpecOption(eventData) ?? resolveChartSpecOption(data);
          const chartType =
            eventData.chart_type ??
            (typeof eventData.chart_spec === 'object' && eventData.chart_spec
              ? eventData.chart_spec.chart_type
              : undefined) ??
            (typeof (data as any)?.chart_spec === 'object'
              ? (data as any).chart_spec.chart_type
              : undefined) ??
            normalizedChartSpec?.meta?.chartDesign?.chart_type;

          if (normalizedChartSpec) {
            scheduleProgressiveUpdate({ chartSpec: normalizedChartSpec });
          } else {
            console.warn('[AnalyticsMemoryStream] chart_generated event without resolvable chart spec', { event: data });
          }

          stepsHook.updateStepStatus(
            'chart_generation',
            'completed',
            [],
            { chart_spec: normalizedChartSpec, chart_type: chartType },
            stepInfo.elapsed_ms
          );
          try {
            const seriesCount = Array.isArray(normalizedChartSpec?.series) ? normalizedChartSpec.series.length : undefined;
            const msg = `Chart generated${chartType ? ` (type: ${chartType})` : ''}${seriesCount!=null ? `, series: ${seriesCount}` : ''}`;
            updateAgentCoordination([msg]);
          } catch {}
          break;
        }

        case 'chart_patch': {
          try {
            if (Array.isArray(eventData?.ops)) {
              setChartSpec(prev => {
                const next = applyChartOps(prev, eventData);
                // keep workflow data in sync for ChatHistory result messages
                workflowDataRef.current.chartSpec = next;
                return next;
              });
              // Build human-readable op summaries for the Agent Thinking panel
              const opLines: string[] = eventData.ops.map((op: any) => {
                try {
                  switch (op.op) {
                    case 'set_chart_type': return `Chart type -> ${op.value}`;
                    case 'set_stack': return `Stacking -> ${op.stack ? (op.mode || 'normal') : 'off'}`;
                    case 'toggle_series': return `Toggle series (${op.visible ? 'show' : 'hide'}): ${Array.isArray(op.names) ? op.names.join(', ') : ''}`;
                    case 'set_y_axis_format': return `Y format -> ${op.valueType}`;
                    case 'set_x_axis': return `X axis field -> ${op.field}`;
                    case 'filter_companies': return `Companies -> ${Array.isArray(op.tickers) ? op.tickers.join(', ') : ''}`;
                    case 'set_palette': return `Palette set (${Array.isArray(op.palette) ? op.palette.length : 0} colors)`;
                    case 'set_axis_scale': return `Axis ${op.axis} scale -> ${op.scale}`;
                    case 'select_metrics': {
                      const inc = op.include === 'ALL' ? 'ALL' : (Array.isArray(op.include) ? op.include.join(', ') : '');
                      const exc = Array.isArray(op.exclude) ? op.exclude.join(', ') : '';
                      return `Metrics include=[${inc}] exclude=[${exc}]`;
                    }
                    case 'set_grouping': return `Grouping -> ${op.grouping}`;
                    default: return `Patch: ${JSON.stringify(op)}`;
                  }
                } catch { return 'Patch applied'; }
              });

              streamHook.setCurrentStatus('Chart updated');
              stepsHook.updateStepStatus(
                'chart_revision',
                'in_progress',
                opLines.length ? opLines : ['Applied chart patch'],
                { patch: eventData },
                stepInfo.elapsed_ms,
                stepInfo.ts
              );
              // Reflect in Agent Coordination lane for visibility
              updateAgentCoordination(opLines.length ? opLines : ['Applied chart revision']);
            }
          } catch (e) {
            console.warn('[AnalyticsMemoryStream] Failed to apply chart_patch', e);
          }
          break;
        }
          
        case 'analysis_revision': {
          try {
            const updatedAnalysis = typeof eventData?.analysis === 'string' ? eventData.analysis : '';
            if (updatedAnalysis) {
              setAnalysis(updatedAnalysis);
              workflowDataRef.current.analysis = updatedAnalysis;
            }
            const lines: string[] = updatedAnalysis
              ? [`Analysis -> ${updatedAnalysis.length > 140 ? updatedAnalysis.slice(0, 140).trimEnd() + '...' : updatedAnalysis}`]
              : ['Applied analysis revision'];
            stepsHook.updateStepStatus(
              'analysis_revision',
              'completed',
              lines,
              { analysis: updatedAnalysis, reason: eventData?.reason, source: eventData?.source },
              stepInfo.elapsed_ms,
              stepInfo.ts
            );
            updateAgentCoordination(lines.length ? lines : ['Applied analysis revision']);
            streamHook.setCurrentStatus('Analysis updated');
          } catch (e) {
            console.warn('[AnalyticsMemoryStream] Failed to apply analysis_revision', e);
          }
          break;
        }
          
        case 'web_search': {
          const stepId = 'web_research_agent';
          if (eventData.web_context) {
            const webContext = normalizeWebContext(eventData.web_context);
            if (webContext) {
              setWebSearch(webContext);
              workflowDataRef.current.webSearch = webContext;

              const thinking: string[] = [];
              const primaryTopic = webContext.searchTopic || webContext.queryTerms || webContext.query || '';
              const topicLabels = Array.isArray(webContext.searchTopics) && webContext.searchTopics.length
                ? webContext.searchTopics
                : (Array.isArray(webContext.topics) ? webContext.topics.map((t: any) => t?.label || t?.query).filter(Boolean) : []);
              if (primaryTopic) thinking.push(`Primary topic: ${primaryTopic}`);
              if (topicLabels && topicLabels.length) {
                thinking.push(`Topics: ${topicLabels.slice(0, 3).join('; ')}`);
              }
              const snippetsCount = Array.isArray(webContext.snippets)
                ? webContext.snippets.length
                : (Array.isArray(webContext.topics)
                    ? webContext.topics.reduce((acc: number, topic: any) => acc + (Array.isArray(topic?.snippets) ? topic.snippets.length : 0), 0)
                    : 0);
              thinking.push(`Snippets: ${snippetsCount}`);
              const previewSnippet = (() => {
                if (Array.isArray(webContext.topics)) {
                  for (const topic of webContext.topics) {
                    if (topic?.snippets && topic.snippets.length) {
                      return topic.snippets[0];
                    }
                  }
                }
                if (Array.isArray(webContext.snippets) && webContext.snippets.length) {
                  return webContext.snippets[0];
                }
                return null;
              })();
              if (previewSnippet) {
                const hostFromUrl = (url?: string) => {
                  if (!url || typeof url !== 'string') return undefined;
                  try {
                    const parsed = new URL(url);
                    return parsed.hostname.replace(/^www\./, '');
                  } catch {
                    return undefined;
                  }
                };
                const hostLabel = hostFromUrl(previewSnippet.url);
                if (previewSnippet.title) {
                  thinking.push(`Result: ${previewSnippet.title}${hostLabel ? ` - ${hostLabel}` : ''}`);
                } else if (hostLabel) {
                  thinking.push(`Result host: ${hostLabel}`);
                }
                if (previewSnippet.snippet) {
                  const clean = previewSnippet.snippet.replace(/\s+/g, ' ').trim();
                  const excerpt = clean.length > 140 ? `${clean.slice(0, 137).trimEnd()}...` : clean;
                  if (excerpt) {
                    thinking.push(`Excerpt: ${excerpt}`);
                  }
                }
              }
              const latency = typeof webContext.latencyMs === 'number' ? webContext.latencyMs : null;
              if (latency !== null) {
                thinking.push(`Latency: ${latency}ms`);
              }
              if (webContext.model) {
                thinking.push(`Model: ${webContext.model}`);
              }
              stepsHook.updateStepStatus(stepId, 'completed', thinking, webContext, stepInfo.elapsed_ms, stepInfo.ts);
            }
          } else {
            const msg = eventData.message || '';
            if (msg) {
              stepsHook.updateStepStatus(stepId, 'in_progress', [msg], undefined, stepInfo.elapsed_ms, stepInfo.ts);
            }
          }
          break;
        }

        case 'analysis_streaming':
          if (!isThinkingEvent) {
            const chunk: string =
              typeof eventData?.partial_analysis === 'string'
                ? eventData.partial_analysis
                : typeof eventData?.delta === 'string'
                ? eventData.delta
                : typeof eventData?.text === 'string'
                ? eventData.text
                : typeof data?.partial_analysis === 'string' // New format: direct access
                ? data.partial_analysis
                : '';
            if (chunk) {
              // Progressive streaming: update immediately for each chunk
              setStreamingText(prev => {
                const newText = prev + chunk;
                scheduleProgressiveUpdate({ streamingText: newText });
                return newText;
              });
            }
          }
          stepsHook.updateStepStatus('analysis_generation', 'in_progress', ['Generating financial analysis...']);
          break;
        case 'cohesive_result':
          {
            const bundle = { ...eventData };
            delete (bundle as any).step;

            if (typeof bundle.analysis === 'string') {
              scheduleProgressiveUpdate({ analysis: bundle.analysis });
              workflowDataRef.current.analysis = bundle.analysis;
            }
            if (bundle.chart_spec) {
              scheduleProgressiveUpdate({ chartSpec: bundle.chart_spec });
              workflowDataRef.current.chartSpec = bundle.chart_spec;
            }
            if (bundle.sql) {
              scheduleProgressiveUpdate({ sqlQuery: bundle.sql });
              workflowDataRef.current.sqlQuery = bundle.sql;
            }
            if (Array.isArray(bundle.data_sample)) {
              scheduleProgressiveUpdate({ dataSample: bundle.data_sample });
              workflowDataRef.current.dataSample = bundle.data_sample;
            }
            if ('stock_widget' in bundle) {
              const widgetPayload = bundle.stock_widget as StockWidgetConfig | null | undefined;
              workflowDataRef.current.stockWidget = widgetPayload ? widgetPayload : null;
            }
            if (bundle.criteria) {
              workflowDataRef.current.criteria = bundle.criteria;
            }
            if (Array.isArray(bundle.tool_manifest)) {
              workflowDataRef.current.toolFanoutManifest = bundle.tool_manifest as ToolFanoutManifest[];
              toolFanoutRef.current.manifest = bundle.tool_manifest as ToolFanoutManifest[];
            } else {
              workflowDataRef.current.toolFanoutManifest = [];
              toolFanoutRef.current.manifest = [];
            }
            if (Array.isArray(bundle.tool_results)) {
              const results = bundle.tool_results as ToolFanoutResult[];
              workflowDataRef.current.toolFanoutResults = results;
              toolFanoutRef.current.results = results;
            } else {
              workflowDataRef.current.toolFanoutResults = [];
              toolFanoutRef.current.results = [];
            }
            refreshFanoutState();
            if (bundle.web_context) {
              const webContext = normalizeWebContext(bundle.web_context);
              if (webContext) {
                setWebSearch(webContext);
                workflowDataRef.current.webSearch = webContext;
              }
            }

            updateStep(
              'analysis_generation',
              'completed',
              bundle.analysis ? [bundle.analysis.slice(0, 120)] : [],
              {
                analysis: bundle.analysis,
                chart_spec: bundle.chart_spec,
                sql: bundle.sql,
                data_sample: bundle.data_sample,
                stock_widget: bundle.stock_widget,
                tool_manifest: workflowDataRef.current.toolFanoutManifest,
                tool_fanout_results: workflowDataRef.current.toolFanoutResults,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts,
              sequence,
              parallelGroup,
            );

            // Emit the result bubble exactly once; guard handles subsequent workflow_complete
            if (!isThinkingEvent) {
              emitResultOnce();
            }
          }
          break;

        case 'analysis_complete':
          // Handle both old and new formats for analysis
          {
            const finalAnalysis =
              !isThinkingEvent
                ? eventData.analysis || data.analysis || streamingText
                : eventData.analysis || data.analysis;

            if (!isThinkingEvent && typeof finalAnalysis === 'string') {
              scheduleProgressiveUpdate({ analysis: finalAnalysis });
            }

            if (!isThinkingEvent) {
              if (eventData.stock_widget !== undefined) {
                workflowDataRef.current.stockWidget = eventData.stock_widget
                  ? (eventData.stock_widget as StockWidgetConfig)
                  : null;
              }

              if (eventData.web_context) {
                const webContext = normalizeWebContext(eventData.web_context);
                if (webContext) {
                  setWebSearch(webContext);
                  workflowDataRef.current.webSearch = webContext;
                }
              }

              if (Array.isArray(eventData.tool_manifest)) {
                workflowDataRef.current.toolFanoutManifest = eventData.tool_manifest as ToolFanoutManifest[];
                toolFanoutRef.current.manifest = eventData.tool_manifest as ToolFanoutManifest[];
              }

              if (Array.isArray(eventData.tool_results)) {
                const fanoutResults = eventData.tool_results as ToolFanoutResult[];
                workflowDataRef.current.toolFanoutResults = fanoutResults;
                toolFanoutRef.current.results = fanoutResults;
              }
              refreshFanoutState();
            }

            setStreamingText('');
            setProgressiveText('');

            stepsHook.updateStepStatus(
              'short_financial_analysis',
              'completed',
              ['Short financial analysis complete'],
              { analysis: finalAnalysis, analysis_length: eventData.analysis_length },
              stepInfo.elapsed_ms
            );

            stepsHook.updateStepStatus(
              'analysis_generation',
              'completed',
              [],
              { analysis: finalAnalysis, analysis_length: eventData.analysis_length },
              stepInfo.elapsed_ms
            );

            // Emit the result bubble exactly once to avoid duplicates from later workflow_complete
            if (!isThinkingEvent) {
              emitResultOnce();
            }
          }
          break;

        // Optional richer logs for agent demo

        case 'sql_attempts': {
          const attempts = Array.isArray(eventData.attempts) ? eventData.attempts : [];
          sqlAttemptsRef.current = attempts;

          const lastAttempt = attempts.length ? attempts[attempts.length - 1] : undefined;
          const attemptMessages = attempts.slice(-3).map((attempt: any) => {
            const attemptId = attempt.attempt ?? attempts.indexOf(attempt) + 1;
            const source = attempt.source ? String(attempt.source).replace(/_/g, ' ') : 'unknown source';
            const statusLabel = attempt.status ? String(attempt.status).replace(/_/g, ' ') : 'pending';
            const duration = typeof attempt.elapsed_ms === 'number' ? ` (${attempt.elapsed_ms}ms)` : '';
            const details: string[] = [];
            if (attempt.error_code) details.push(`[${attempt.error_code}]`);
            if (attempt.error_detail) details.push(String(attempt.error_detail));
            if (attempt.rows !== undefined) details.push(`${attempt.rows} rows`);
            return `Attempt ${attemptId} via ${source}: ${statusLabel}${duration}${details.length ? ' - ' + details.join(' ') : ''}`;
          });

          const details = { attempts, last_attempt: lastAttempt };

          let compilationStatus: ProcessStep['status'] = 'in_progress';
          const statusCode = typeof lastAttempt?.status === 'string' ? lastAttempt.status : undefined;
          if (statusCode === 'success') {
            compilationStatus = 'completed';
          } else if (statusCode === 'llm_error' || statusCode === 'empty') {
            compilationStatus = 'error';
          }

          const summaryMessages = attemptMessages.length ? attemptMessages : ['Tracking SQL retry attempts'];

          stepsHook.updateStepStatus(
            'sql_compilation',
            compilationStatus,
            summaryMessages,
            details,
            stepInfo.elapsed_ms,
            stepInfo.ts,
            sequence,
            parallelGroup
          );

          if (statusCode === 'success') {
            stepsHook.updateStepStatus(
              'sql_validation',
              'completed',
              summaryMessages,
              details,
              stepInfo.elapsed_ms,
              stepInfo.ts,
              sequence,
              parallelGroup
            );
            stepsHook.updateStepStatus(
              'sql_execution',
              'completed',
              summaryMessages,
              { ...details, rows: lastAttempt?.rows },
              stepInfo.elapsed_ms,
              stepInfo.ts,
              sequence,
              parallelGroup
            );
          } else if (statusCode === 'validation_failed') {
            stepsHook.updateStepStatus(
              'sql_validation',
              'error',
              summaryMessages,
              details,
              stepInfo.elapsed_ms,
              stepInfo.ts,
              sequence,
              parallelGroup
            );
          } else if (statusCode === 'execution_failed' || statusCode === 'result_invalid') {
            stepsHook.updateStepStatus(
              'sql_execution',
              'error',
              summaryMessages,
              details,
              stepInfo.elapsed_ms,
              stepInfo.ts,
              sequence,
              parallelGroup
            );
          }
          break;
        }

        case 'tool_call':
          recordToolCallEvent(eventData, { ts: stepInfo.ts, elapsed_ms: stepInfo.elapsed_ms, sequence, parallel_group: parallelGroup, tool_group: toolGroup });
          break;

        case 'tool_parallel_start':
          {
            const manifest = (eventData.tools ?? []) as ToolFanoutManifest[];
            const concurrencyLimit = eventData.concurrency_limit ?? eventData.tool_count ?? toolFanoutRef.current.concurrencyLimit;
            toolFanoutRef.current = {
              manifest,
              results: [],
              concurrencyLimit,
            };
            workflowDataRef.current.toolFanoutManifest = manifest;
            workflowDataRef.current.toolFanoutResults = [];
            workflowDataRef.current.concurrencyLimit = concurrencyLimit;
            refreshFanoutState();
            const fanoutThought = `Fan-out launched with ${eventData.tool_count ?? manifest.length} tools (limit ${concurrencyLimit}).`;
            updateStep('tool_fanout', 'in_progress', [fanoutThought], {
              tool_manifest: manifest,
              concurrency_limit: concurrencyLimit,
            }, stepInfo.elapsed_ms, stepInfo.ts, sequence, parallelGroup);
          }
          break;

        case 'tool_parallel_result':
          {
            const resultSummary: ToolFanoutResult = {
              tool: eventData.tool,
              status: eventData.status,
              elapsed_ms: eventData.elapsed_ms,
              started_at: eventData.started_at,
              completed_at: eventData.completed_at,
              fatal: eventData.fatal,
              error: eventData.error,
              metadata: eventData.metadata,
              payload: eventData.payload,
            };
            toolFanoutRef.current.results = [...toolFanoutRef.current.results, resultSummary].slice(-10);
            workflowDataRef.current.toolFanoutResults = toolFanoutRef.current.results;

            const payloadForWidget = (eventData.payload ?? {}) as Record<string, unknown>;
            if (payloadForWidget && 'stock_widget' in payloadForWidget) {
              const widgetCandidate = (payloadForWidget as { stock_widget?: StockWidgetConfig | null }).stock_widget;
              workflowDataRef.current.stockWidget = widgetCandidate ?? null;
            }

            if (eventData.tool === 'web_retriever') {
              const fromPayload = eventData.payload || {};
              const webContext = normalizeWebContext({
                ...fromPayload,
                summary: fromPayload.summary ?? eventData.metadata?.summary,
                from_cache: fromPayload.from_cache ?? eventData.metadata?.cache_hit,
                provider: fromPayload.provider ?? eventData.metadata?.provider,
                model: fromPayload.model ?? eventData.metadata?.model,
              });
              if (webContext) {
                setWebSearch(webContext);
                workflowDataRef.current.webSearch = webContext;

                const stepId = 'web_research_agent';
                const thinking: string[] = [];
                const primaryTopic = webContext.searchTopic || webContext.queryTerms || webContext.query || '';
                const topicLabels = Array.isArray(webContext.searchTopics) && webContext.searchTopics.length
                  ? webContext.searchTopics
                  : (Array.isArray(webContext.topics) ? webContext.topics.map((t: any) => t?.label || t?.query).filter(Boolean) : []);
                if (primaryTopic) thinking.push(`Primary topic: ${primaryTopic}`);
                if (topicLabels && topicLabels.length) {
                  thinking.push(`Topics: ${topicLabels.slice(0, 3).join('; ')}`);
                }
                const count = Array.isArray(webContext.snippets)
                  ? webContext.snippets.length
                  : (Array.isArray(webContext.topics)
                      ? webContext.topics.reduce((acc: number, topic: any) => acc + (Array.isArray(topic?.snippets) ? topic.snippets.length : 0), 0)
                      : 0);
                thinking.push(`Snippets: ${count}`);
                if (typeof webContext.latencyMs === 'number') thinking.push(`Latency: ${webContext.latencyMs}ms`);
                if (webContext.model) thinking.push(`Model: ${webContext.model}`);
                stepsHook.updateStepStatus(stepId, 'completed', thinking, webContext, eventData.elapsed_ms ?? stepInfo.elapsed_ms, stepInfo.ts);
              }
            }

            const manifest = toolFanoutRef.current.manifest;
            updateStep(
              'tool_fanout',
              'in_progress',
              [`${eventData.tool} status: ${eventData.status}`],
              {
                tool_manifest: manifest,
                tool_fanout_results: toolFanoutRef.current.results,
                concurrency_limit: toolFanoutRef.current.concurrencyLimit,
              },
              eventData.elapsed_ms ?? stepInfo.elapsed_ms,
              stepInfo.ts,
              sequence,
              parallelGroup,
            );
            refreshFanoutState();
          }
          break;

        case 'tool_parallel_complete':
          {
            workflowDataRef.current.toolFanoutResults = toolFanoutRef.current.results;
            const completionStatus = eventData.status || 'complete';
            const finalState = completionStatus === 'complete' ? 'completed' : completionStatus === 'cancelled' ? 'stopped' : 'completed';
            updateStep(
              'tool_fanout',
              finalState as ProcessStep['status'],
              [`Fan-out ${completionStatus}.`],
              {
                tool_manifest: toolFanoutRef.current.manifest,
                tool_fanout_results: toolFanoutRef.current.results,
                concurrency_limit: toolFanoutRef.current.concurrencyLimit,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts,
              sequence,
              parallelGroup,
            );
            refreshFanoutState();
          }
          break;

        case 'agent_turn':
          recordAgentTurnEvent(eventData, { ts: stepInfo.ts, elapsed_ms: stepInfo.elapsed_ms, sequence, parallel_group: parallelGroup });
          break;

        case 'agent_reasoning':
          recordAgentReasoningEvent(eventData, { ts: stepInfo.ts, elapsed_ms: stepInfo.elapsed_ms, sequence, parallel_group: parallelGroup });
          break;

        case 'policy_decision': {
          const rawScore = typeof eventData.score === 'number' ? eventData.score : Number(eventData.score || 0);
          const rawThreshold = typeof eventData.threshold === 'number' ? eventData.threshold : Number(eventData.threshold || 0);
          const safeScore = Number.isFinite(rawScore) ? rawScore : 0;
          const safeThreshold = Number.isFinite(rawThreshold) ? rawThreshold : 0;
          const decisionStep = eventData.policy === 'planner_sql_retry' ? 'sql_compilation' : 'agent_coordination';
          const message = `Policy ${eventData.action === 'skip_retry' ? 'blocked' : 'allowed'} (score ${safeScore.toFixed(2)} / threshold ${safeThreshold.toFixed(2)})`;
          updateAgentCoordination([message], eventData.action === 'skip_retry' ? 'stopped' : undefined, {
            ts: eventData.ts ?? stepInfo.ts,
            elapsed_ms: stepInfo.elapsed_ms,
            sequence,
          });
          const policyMessages = eventData.reason ? [message, String(eventData.reason)] : [message];
          stepsHook.updateStepStatus(
            decisionStep,
            eventData.action === 'skip_retry' ? 'stopped' : 'in_progress',
            policyMessages,
            {
              policy: eventData.policy,
              action: eventData.action,
              score: rawScore,
              threshold: rawThreshold,
              attempt: eventData.attempt,
            },
            stepInfo.elapsed_ms,
            eventData.ts ?? stepInfo.ts,
            sequence,
            parallelGroup,
          );
          break;
        }

        case 'catalog_trace':
          {
            const targetStep = eventData.tool ?? 'plan_and_select_template';
            const notes = ['YAML catalogue lookup via ' + (eventData.tool || 'lookup')];
            const metadata = eventData.metadata ?? {};
            const candidates = Array.isArray(eventData.candidates) ? eventData.candidates : [];
            stepsHook.updateStepStatus(targetStep, 'in_progress', notes, { candidates, metadata }, eventData.elapsed_ms);
          }
          break;
        case 'thinking_log':
          stepsHook.updateStepStatus('tool_execution', 'in_progress', [eventData.message]);
          break;
          
        // ===== NEW ENHANCED EVENTS =====
        case 'classification_started':
          stepsHook.updateStepStatus('classification', 'in_progress', ['Starting query classification...'], { model: eventData.model }, undefined, eventData.ts);
          streamHook.setCurrentStatus('Classifying query...');
          break;

        case 'classification_reasoning':
          stepsHook.updateStepStatus('classification', 'in_progress', [eventData.thinking || 'Analyzing query type...'], {
            confidence: eventData.confidence,
            category: eventData.category
          }, undefined, eventData.ts);
          break;

        case 'classification_complete':
          stepsHook.updateStepStatus('classification', 'completed', [
            eventData.is_financial ? 'Query classified as financial analytics' : 'Query classified as non-financial'
          ], {
            is_financial: eventData.is_financial,
            category: eventData.category,
            confidence: eventData.confidence
          }, eventData.elapsed_ms, eventData.ts);
          break;

        case 'classification_error':
          stepsHook.updateStepStatus('classification', 'error', [`Classification failed: ${eventData.error}`], undefined, eventData.elapsed_ms, eventData.ts);
          break;

        case 'classification_fallback':
          updateStep('classification', 'completed', [`Fallback to ${eventData.method}`], { method: eventData.method }, undefined, eventData.ts);
          break;


        case 'intent_detection_started':
          stepsHook.updateStepStatus('intent_detection', 'in_progress', ['Detecting query intent...'], undefined, undefined, eventData.ts);
          streamHook.setCurrentStatus('Analyzing query intent...');
          break;

        case 'intent_detection_complete':
          stepsHook.updateStepStatus('intent_detection', 'completed', [
            `Intent: ${eventData.intent_key} (${Math.round((eventData.confidence || 0) * 100)}%)`
          ], {
            intent_key: eventData.intent_key,
            confidence: eventData.confidence,
            slots_detected: eventData.slots_detected
          }, undefined, eventData.ts);
          break;

        case 'schema_validation_started':
          stepsHook.updateStepStatus('schema_validation', 'in_progress', ['Validating required fields...'], undefined, undefined, eventData.ts);
          streamHook.setCurrentStatus('Validating schema...');
          break;

        case 'schema_validation_complete':
          const validationPassed = eventData.validation_passed;
          stepsHook.updateStepStatus('schema_validation', validationPassed ? 'completed' : 'in_progress', [
            validationPassed ? 'All required fields present' : `Missing: ${eventData.missing_fields?.join(', ')}`
          ], {
            required_fields: eventData.required_fields,
            provided_fields: eventData.provided_fields,
            missing_fields: eventData.missing_fields,
            validation_passed: validationPassed
          }, undefined, eventData.ts);
          break;

        case 'criteria_ready':
          workflowDataRef.current.criteria = eventData;
          setCriteria(eventData);
          stepsHook.updateStepStatus('schema_validation', 'completed', ['SQL criteria ready'], eventData, eventData.elapsed_ms, eventData.ts);
          streamHook.setCurrentStatus('SQL criteria locked in.');
          break;

        case 'clarification_needed':
          stepsHook.updateStepStatus('clarification', 'in_progress', [`Missing fields: ${eventData.missing_fields?.join(', ')}`], { missing_fields: eventData.missing_fields }, undefined, eventData.ts);
          break;

        case 'clarification_skipped':
          stepsHook.updateStepStatus('clarification', 'completed', [eventData.reason || 'Clarification not needed'], undefined, undefined, eventData.ts);
          setPendingClarification(null);
          break;

        case 'intent_finalized':
          stepsHook.updateStepStatus('intent_detection', 'completed', ['Intent and schema finalized'], eventData, undefined, eventData.ts);
          break;

        case 'tool_planning_started':
          stepsHook.updateStepStatus('tool_planning', 'in_progress', [eventData.message || 'Planning tool execution...'], { intent_key: eventData.intent_key }, undefined, eventData.ts);
          streamHook.setCurrentStatus('Agent planning tools...');
          break;

        case 'tool_selection_reasoning':
          stepsHook.updateStepStatus('tool_planning', 'in_progress', [`Strategy: ${eventData.strategy}`], {
            available_tools: eventData.available_tools,
            strategy: eventData.strategy
          }, undefined, eventData.ts);
          break;

        // ===== SUPERVISOR MODE EVENTS =====
        case 'planning_proposed':
          stepsHook.updateStepStatus('planning', 'completed', [eventData.plan]);
          streamHook.setCurrentStatus('Plan proposed by flow coordinator');
          if (!isThinkingEvent) {
            addChatMessage({
              type: 'assistant',
              content: `**Plan Proposed:**\n${eventData.plan}\n\n**Steps:** ${eventData.steps?.length || 0} tools planned`,
            });
          }
          break;

        case 'tool_start':
          stepsHook.updateStepStatus('tool_execution', 'in_progress', [`Executing: ${eventData.tool}`]);
          streamHook.setCurrentStatus(`Executing tool: ${eventData.tool}`);
          break;
          
        case 'tool_end':
          // Tool completed - keep execution phase active until all tools done
          stepsHook.updateStepStatus('tool_execution', 'in_progress', [`Completed: ${eventData.tool}`]);
          break;
          
        case 'tool_error':
          stepsHook.updateStepStatus('tool_execution', 'error', [`Error in ${eventData.tool}: ${eventData.error}`]);
          streamHook.setCurrentStatus(`Tool error: ${eventData.error}`);
          addChatMessage({
            type: 'assistant',
            content: `**Tool Error:** ${eventData.tool} - ${eventData.error}`,
          });
          break;
          
                case 'final_summary':
          stepsHook.updateStepStatus('finalization', 'completed', ['Workflow summary generated']);
          const summaryStatusMessage =
            flow === 'single-agent'
              ? 'Single-agent tools workflow completed!'
              : flow === 'multi-agent'
                ? 'Multi-agent workflow completed!'
                : 'Direct workflow completed!';
          streamHook.setCurrentStatus(summaryStatusMessage);
          if (!isThinkingEvent && !summarySentRef.current) { /* patched: disable malformed content */
            summarySentRef.current = true;
            const keyFindings = Array.isArray(eventData.key_findings)
              ? (eventData.key_findings as string[]).map((f: string) => ' ' + f).join('\\n')
              : 'No findings available';
            addChatMessage({
  type: 'assistant'
  ,content: `**Final Summary:**\n\n**Key Findings:**\n${keyFindings}`
});
          }
          break;

                case 'workflow_complete':
          const workflowStatusMessage =
            flow === 'single-agent'
              ? 'Single-agent tools workflow completed!'
              : flow === 'multi-agent'
                ? 'Multi-agent workflow completed!'
                : 'Direct workflow completed!';
          const isEarlyExit = Boolean(eventData?.early_exit);
          const completionMessage = eventData?.message || (typeof eventData.total_elapsed_ms === 'number' ? `Completed in ${eventData.total_elapsed_ms} ms` : null);
          streamHook.setCurrentStatus(completionMessage || workflowStatusMessage);
          if (!isThinkingEvent && !isEarlyExit) { emitResultOnce(); }

          if (isEarlyExit) {
            // Clear any partial workflow artifacts for clarity
            workflowDataRef.current = {
              chartSpec: null,
              analysis: '',
              sqlQuery: '',
              dataSample: null,
              streamingText: '',
              criteria: null,
            };
            setChartSpec(null);
            setAnalysis('');
            setSqlQuery('');
            setDataSample(null);
            setStreamingText('');
          }
          break;

        case 'final_answer':
          stepsHook.updateStepStatus('finalization', 'completed', ['Provided final response']);
          streamHook.setCurrentStatus(eventData?.message || 'Completed');
          if (!isThinkingEvent) {
            addChatMessage({
              type: 'assistant',
              content: eventData?.message || 'Happy to help with financial analytics questions!',
            });
          }
          break;
          
        case 'done':
          streamHook.setCurrentStatus('Analysis completed successfully!');
          break;
          
        case 'error':
          {
            const errorStep = eventData.step || stepInfo.step || 'unknown';
            const errorMessage = eventData.error || eventData.message || 'Analytics error occurred';
            const errorCodeLabel = eventData.code ? `[${eventData.code}] ` : '';
            streamHook.setError(eventData.code ? `${eventData.code}: ${errorMessage}` : errorMessage);
            stepsHook.updateStepStatus(
              errorStep,
              'error',
              [`${errorCodeLabel}${errorMessage}`],
              {
                error: errorMessage,
                code: eventData.code,
                details: eventData.details,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts
            );
          }
          break;
      }
    });
  };

  const stopAnalysis = () => {
    streamHook.stopStream();
    stepsHook.stopInProgressSteps();
  };

  const resetAll = () => {
    streamHook.resetState();
    stepsHook.resetSteps();
    setSessionId('');
    setPendingClarification(null);
    setCriteria(null);
    setChatHistory([]);
    setChartSpec(null);
    setAnalysis('');
    setSqlQuery('');
    setDataSample(null);
    setStreamingText('');
    setProgressiveAnalysis('');
    setProgressiveText('');
    setSingleAgentFanout(null);

    // Clear any pending updates
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }
    pendingUpdatesRef.current = {};
    toolTelemetryRef.current = [];
    agentTurnsRef.current = [];
    agentReasoningRef.current = [];
    sqlAttemptsRef.current = [];
    agentLaneStateRef.current = {};
    resultSentRef.current = false;
    summarySentRef.current = false;
    toolFanoutRef.current = { manifest: [], results: [], concurrencyLimit: 0 };

    // Reset workflow data ref
    workflowDataRef.current = {
      chartSpec: null,
      analysis: '',
      sqlQuery: '',
      dataSample: null,
      streamingText: '',
      criteria: null,
      stockWidget: null,
      toolFanoutManifest: [],
      toolFanoutResults: [],
      concurrencyLimit: 0,
      webSearch: null
    };
  };

  return {
    // State
    sessionId,
    pendingClarification,
    chatHistory,
    chartSpec,
    analysis,
    sqlQuery,
    dataSample,
    criteria,
    streamingText,
    webSearch,
    singleAgentFanout,

    // Progressive rendering state
    progressiveAnalysis,
    progressiveText,

    // Stream state
    isLoading: streamHook.isLoading,
    error: streamHook.error,
    currentStatus: streamHook.currentStatus,

    // Process steps
    processSteps: stepsHook.processSteps,

    // Supervisor state

    // Actions
    handleQuery,
    submitClarification,
    stopAnalysis,
    resetAll,
    addChatMessage,
    updateChatMessage,
  };
};


