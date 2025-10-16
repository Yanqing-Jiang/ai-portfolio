import { useState, useRef, useCallback, useEffect } from 'react';
import { ChatMessage, ClarifyRequest, ClarifyAnswer, ToolCallTelemetry, AgentTurnTelemetry, AgentReasoningTelemetry, ProcessStep, ToolFanoutManifest, ToolFanoutResult, StockWidgetConfig, WebSearchResult, AnalysisOverview, AnalysisEvidenceLink, FollowUpBanner, SpecialistCard, SingleAgentFanout, SingleAgentFanoutBranch, FanoutBranchStatus, FlowMode, LatencyGuardrail } from '../types';
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

const FOLLOW_UP_BANNER_COPY: Record<string, { title: string; message: string }> = {
  full_pipeline: {
    title: 'Fresh Run Scheduled',
    message: 'Running SQL, charts, and narrative again to deliver a fully refreshed answer.',
  },
  reuse_sql: {
    title: 'Reusing Last Dataset',
    message: 'Skipping the SQL rerun-updating visuals and narrative on top of the validated table.',
  },
  stock_only: {
    title: 'Market Snapshot Only',
    message: 'Pulling fresh price data while charts and analysis stay pinned to the prior run.',
  },
};

type SnapshotReuseInfo = {
  reusedSql?: boolean;
  reusedChart?: boolean;
  reusedStock?: boolean;
  reusedWeb?: boolean;
  reusedAnalysis?: boolean;
  criteriaChanged?: boolean;
  source?: string | null;
  followUpRoute?: string | null;
};

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
  const [revisionMode, setRevisionMode] = useState<'none' | 'chart' | 'analysis' | 'mixed'>('none');
  const [streamingText, setStreamingText] = useState('');
  const [webSearch, setWebSearch] = useState<WebSearchResult | null>(null);
  const [stockWidget, setStockWidget] = useState<StockWidgetConfig | null>(null);
  const [singleAgentFanout, setSingleAgentFanout] = useState<SingleAgentFanout | null>(null);
  const [analysisOverview, setAnalysisOverview] = useState<AnalysisOverview | null>(null);
  const [followUpBanner, setFollowUpBanner] = useState<FollowUpBanner | null>(null);
  const [latencyGuardrail, setLatencyGuardrail] = useState<LatencyGuardrail | null>(null);
  const [specialistCards, setSpecialistCards] = useState<SpecialistCard[]>([]);
  const [snapshotReuse, setSnapshotReuse] = useState<SnapshotReuseInfo | null>(null);
  const resultSentRef = useRef<boolean>(false);
  const summarySentRef = useRef<boolean>(false);
  const lastSessionIdRef = useRef<string>('');
  const emitResultOnce = useCallback(() => {
    if (resultSentRef.current) return;
    resultSentRef.current = true;
    const newMessage = {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      type: 'result' as const,
      content: 'Analysis completed! Here are your results:',
      flowMode: workflowDataRef.current.flowMode ?? flow,
      analysis: workflowDataRef.current.analysis || workflowDataRef.current.streamingText,
      chartSpec: workflowDataRef.current.chartSpec,
      sqlQuery: workflowDataRef.current.sqlQuery,
      dataSample: workflowDataRef.current.dataSample,
      stockWidgetConfig: workflowDataRef.current.stockWidget,
      toolFanoutManifest: workflowDataRef.current.toolFanoutManifest,
      toolFanoutResults: workflowDataRef.current.toolFanoutResults,
      webSearch: workflowDataRef.current.webSearch,
      analysisOverview: workflowDataRef.current.analysisOverview,
      banner: workflowDataRef.current.followUpBanner,
      specialistCards: workflowDataRef.current.specialistCards,
      latencyGuardrail: workflowDataRef.current.latencyGuardrail,
    };
    setChatHistory((prev) => [...prev, newMessage]);
  }, [setChatHistory, flow]);
  
  // Progressive rendering: update state immediately instead of accumulating in refs
  const [progressiveAnalysis, setProgressiveAnalysis] = useState('');
  const [progressiveText, setProgressiveText] = useState('');

  const coerceString = (value: unknown): string | undefined => {
    if (typeof value !== 'string') {
      return undefined;
    }
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  };

  const coerceNumber = (value: unknown): number | undefined => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === 'string') {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
    return undefined;
  };

  const coerceBoolean = (value: unknown): boolean | undefined => {
    if (typeof value === 'boolean') {
      return value;
    }
    if (typeof value === 'number') {
      if (!Number.isFinite(value)) {
        return undefined;
      }
      return value !== 0;
    }
    if (typeof value === 'string') {
      const normalized = value.trim().toLowerCase();
      if (!normalized) return undefined;
      if (['true', '1', 'yes', 'y', 'on'].includes(normalized)) return true;
      if (['false', '0', 'no', 'n', 'off'].includes(normalized)) return false;
    }
    return undefined;
  };

  const resolveLane = (...sources: any[]): string | undefined => {
    for (const source of sources) {
      if (!source) {
        continue;
      }
      if (typeof source === 'string') {
        const candidate = coerceString(source);
        if (candidate) {
          return candidate;
        }
        continue;
      }
      if (typeof source !== 'object') {
        continue;
      }
      const direct = coerceString((source as any).lane);
      if (direct) {
        return direct;
      }
      const metadataLane = coerceString((source as any).metadata?.lane);
      if (metadataLane) {
        return metadataLane;
      }
      const detailsLane = coerceString((source as any).details?.lane);
      if (detailsLane) {
        return detailsLane;
      }
    }
    return undefined;
  };

  const resolveReusedFlag = (...sources: any[]): boolean | undefined => {
    for (const source of sources) {
      if (source === undefined || source === null) {
        continue;
      }
      if (typeof source === 'boolean') {
        return source;
      }
      if (typeof source === 'string') {
        const normalized = source.trim().toLowerCase();
        if (!normalized) {
          continue;
        }
        if (['reused', 'cached', 'cache_hit', 'from_cache', 'true', '1', 'yes'].includes(normalized)) {
          return true;
        }
        if (['fresh', 'false', '0', 'no'].includes(normalized)) {
          return false;
        }
      }
      const coerced = coerceBoolean(source);
      if (coerced !== undefined) {
        return coerced;
      }
      if (typeof source === 'object') {
        if (typeof (source as any).status === 'string') {
          const normalizedStatus = coerceString((source as any).status)?.toLowerCase();
          if (normalizedStatus === 'reused' || normalizedStatus === 'cached') {
            return true;
          }
        }
        const nested =
          resolveReusedFlag((source as any).reused) ??
          resolveReusedFlag((source as any).cache_hit) ??
          resolveReusedFlag((source as any).cacheHit) ??
          resolveReusedFlag((source as any).from_cache) ??
          resolveReusedFlag((source as any).fromCache) ??
          resolveReusedFlag((source as any).cached);
        if (nested !== undefined) {
          return nested;
        }
      }
    }
    return undefined;
  };

  const coerceStringList = (value: unknown): string[] => {
    if (!Array.isArray(value)) {
      return [];
    }
    return (value.map((entry) => coerceString(entry)).filter(Boolean) as string[]).filter((entry) => entry.length > 0);
  };

  const parseAnalysisOverview = (source: any): AnalysisOverview | null => {
    if (!source || typeof source !== 'object') {
      return null;
    }
    const tldrValue = coerceString(source.tldr ?? source.summary);
    const highlightsValue = coerceStringList(source.highlights ?? source.bullets);
    const keyNumbersValue = coerceStringList(source.key_numbers ?? source.keyNumbers);
    const riskWatchValue = coerceStringList(source.risk_watch ?? source.riskWatch ?? source.watchlist);
    const nextStepsValue = coerceStringList(source.next_steps ?? source.nextSteps ?? source.actions);
    const evidenceSource = Array.isArray(source.evidence)
      ? source.evidence
      : Array.isArray(source.sources)
        ? source.sources
        : [];
    const evidenceEntries: AnalysisEvidenceLink[] = (evidenceSource as any[])
      .map((item: any) => {
        if (!item || typeof item !== 'object') {
          return null;
        }
        const sourceUrl = coerceString(item.source_url ?? item.url);
        if (!sourceUrl) {
          return null;
        }
        const entry: AnalysisEvidenceLink = {
          sourceUrl,
        };
        const title = coerceString(item.title);
        if (title) {
          entry.title = title;
        }
        const displayUrl = coerceString(item.display_url ?? item.displayUrl);
        if (displayUrl) {
          entry.displayUrl = displayUrl;
        }
        const snippet = coerceString(item.snippet ?? item.excerpt);
        if (snippet) {
          entry.snippet = snippet.length > 260 ? `${snippet.slice(0, 257).trimEnd()}...` : snippet;
        }
        const claim = coerceString(item.claim);
        if (claim) {
          entry.claim = claim;
        }
        const publishedAt = coerceString(item.published_at ?? item.publishedAt);
        if (publishedAt) {
          entry.publishedAt = publishedAt;
        }
        const confidenceValue =
          coerceNumber(item.confidence) ?? coerceNumber(item.confidence_score) ?? coerceNumber(item.short_score);
        if (confidenceValue !== undefined) {
          entry.confidence = Math.max(0, Math.min(Number(confidenceValue.toFixed(2)), 1));
        }
        return entry;
      })
      .filter((entry): entry is AnalysisEvidenceLink => Boolean(entry));

    if (
      !tldrValue &&
      !highlightsValue.length &&
      !keyNumbersValue.length &&
      !riskWatchValue.length &&
      !nextStepsValue.length &&
      !evidenceEntries.length
    ) {
      return null;
    }

    return {
      tldr: tldrValue || undefined,
      highlights: highlightsValue.length ? highlightsValue.slice(0, 3) : undefined,
      keyNumbers: keyNumbersValue.length ? keyNumbersValue.slice(0, 3) : undefined,
      riskWatch: riskWatchValue.length ? riskWatchValue.slice(0, 3) : undefined,
      nextSteps: nextStepsValue.length ? nextStepsValue.slice(0, 3) : undefined,
      evidence: evidenceEntries.length ? evidenceEntries.slice(0, 5) : undefined,
    };
  };

  const normalizeWebContext = (raw: any): WebSearchResult | null => {
    if (!raw) {
      return null;
    }
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
    const rawLatencyStats =
      (raw.latency_stats && typeof raw.latency_stats === 'object' ? raw.latency_stats : null) ??
      (raw.latencyStats && typeof raw.latencyStats === 'object' ? raw.latencyStats : null);
    let latencyStats: { total_ms?: number; p50_ms?: number; max_ms?: number; min_ms?: number; samples?: number } | undefined;
    if (rawLatencyStats) {
      const totalMs = typeof rawLatencyStats.total_ms === 'number' ? rawLatencyStats.total_ms : (typeof rawLatencyStats.totalMs === 'number' ? rawLatencyStats.totalMs : undefined);
      const p50Ms = typeof rawLatencyStats.p50_ms === 'number' ? rawLatencyStats.p50_ms : (typeof rawLatencyStats.p50Ms === 'number' ? rawLatencyStats.p50Ms : undefined);
      const maxMs = typeof rawLatencyStats.max_ms === 'number' ? rawLatencyStats.max_ms : (typeof rawLatencyStats.maxMs === 'number' ? rawLatencyStats.maxMs : undefined);
      const minMs = typeof rawLatencyStats.min_ms === 'number' ? rawLatencyStats.min_ms : (typeof rawLatencyStats.minMs === 'number' ? rawLatencyStats.minMs : undefined);
      const samples = typeof rawLatencyStats.samples === 'number'
        ? rawLatencyStats.samples
        : (typeof rawLatencyStats.latency_samples === 'number'
            ? rawLatencyStats.latency_samples
            : (typeof rawLatencyStats.sample_count === 'number' ? rawLatencyStats.sample_count : undefined));
      latencyStats = {
        total_ms: totalMs,
        p50_ms: p50Ms,
        max_ms: maxMs,
        min_ms: minMs,
        samples,
      };
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
      latencyStats,
    };
  };

  const normalizeSpecialistCard = (raw: any, timestamp?: string): SpecialistCard | null => {
    if (!raw || typeof raw !== 'object') {
      return null;
    }
    const normalizeSnippet = (item: any) => ({
      title: coerceString(item?.title),
      snippet: coerceString(item?.snippet),
      url: coerceString(item?.url),
      display_url: coerceString(item?.display_url) ?? coerceString(item?.displayUrl),
      published_at: coerceString(item?.published_at) ?? coerceString(item?.publishedAt),
    });
    const normalizeSymbol = (value: any): string | undefined => {
      if (typeof value === 'string') {
        const trimmed = value.trim();
        return trimmed.length ? trimmed.toUpperCase() : undefined;
      }
      if (Array.isArray(value) && value.length) {
        const primary = value[0];
        if (typeof primary === 'string') {
          const trimmed = primary.trim();
          return trimmed.length ? trimmed.toUpperCase() : undefined;
        }
      }
      return undefined;
    };

    const snippets = Array.isArray(raw.snippets)
      ? raw.snippets
          .map(normalizeSnippet)
          .filter((entry: any) => entry.title || entry.snippet || entry.url)
      : undefined;
    const symbols = Array.isArray(raw.symbols)
      ? raw.symbols
          .map(normalizeSymbol)
          .filter((symbol): symbol is string => Boolean(symbol))
      : undefined;

    const card: SpecialistCard = {
      type: coerceString(raw.type) ?? 'accessory',
      state: coerceString(raw.state),
      title: coerceString(raw.title),
      message: coerceString(raw.message),
      topic: coerceString(raw.topic),
      summary: coerceString(raw.summary),
      snippets,
      symbols,
      ready: typeof raw.ready === 'boolean' ? raw.ready : undefined,
      ts: coerceString(raw.ts) ?? timestamp ?? new Date().toISOString(),
      meta: typeof raw.meta === 'object' && raw.meta !== null ? raw.meta : undefined,
    };
    const lane = resolveLane(raw, raw.meta);
    if (lane) {
      card.lane = lane;
    }
    const parallelGroup = coerceString(raw.parallel_group ?? raw.parallelGroup ?? raw.meta?.parallel_group);
    if (parallelGroup) {
      card.parallelGroup = parallelGroup;
    }
    const reusedFlag = resolveReusedFlag(raw, raw.meta);
    if (reusedFlag !== undefined) {
      card.reused = reusedFlag;
    }

    return card;
  };

  // Ref for debouncing rapid updates
  const updateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pendingUpdatesRef = useRef<{
    analysis?: string;
    streamingText?: string;
    chartSpec?: any;
    sqlQuery?: string;
    dataSample?: any[];
    stockWidget?: StockWidgetConfig | null;
    webSearch?: WebSearchResult | null;
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
    webSearch: WebSearchResult | null;
  flowMode: FlowMode;
  analysisOverview: AnalysisOverview | null;
  followUpBanner: FollowUpBanner | null;
  specialistCards: SpecialistCard[];
  latencyGuardrail: LatencyGuardrail | null;
  snapshotReuse: SnapshotReuseInfo | null;
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
  webSearch: null,
  flowMode: flow,
  analysisOverview: null,
  followUpBanner: null,
  specialistCards: [],
  latencyGuardrail: null,
  snapshotReuse: null,
});

  const upsertSpecialistCard = useCallback((card: SpecialistCard) => {
    setSpecialistCards((prev) => {
      const keyFor = (entry: SpecialistCard) =>
        [entry.type ?? 'accessory', entry.lane ?? '', entry.parallelGroup ?? ''].join('::');
      const targetKey = keyFor(card);
      const existingIndex = prev.findIndex((item) => keyFor(item) === targetKey);
      let next: SpecialistCard[];
      if (existingIndex >= 0) {
        next = [...prev];
        next[existingIndex] = {
          ...prev[existingIndex],
          ...card,
          reused: card.reused ?? prev[existingIndex].reused,
        };
      } else {
        next = [...prev, card];
      }
      workflowDataRef.current.specialistCards = next;
      return next;
    });
  }, []);

  const streamHook = useAnalyticsStream();
  const stepsHook = useProcessSteps();

  useEffect(() => {
    workflowDataRef.current.flowMode = flow;
  }, [flow]);

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
      if (pending.stockWidget !== undefined) {
        setStockWidget(pending.stockWidget ?? null);
        workflowDataRef.current.stockWidget = pending.stockWidget ?? null;
      }
      if (pending.webSearch !== undefined) {
        setWebSearch(pending.webSearch);
        workflowDataRef.current.webSearch = pending.webSearch;
      }

      // Clear pending updates
      pendingUpdatesRef.current = {};
    }, 50); // 50ms debounce for smooth updates
  };

  const markRevisionMode = useCallback((mode: 'chart' | 'analysis') => {
    setRevisionMode((prev) => {
      if (prev === 'none') {
        return mode;
      }
      if (prev === mode) {
        return prev;
      }
      return 'mixed';
    });
  }, []);

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
    const lane = resolveLane(payload, payload.metadata, { lane: meta?.parallel_group });
    if (lane) {
      entry.lane = lane;
    }
    const reusedFlag = resolveReusedFlag(payload, payload.metadata);
    if (reusedFlag !== undefined) {
      entry.reused = reusedFlag;
    }
    const latencyBudget = typeof payload.latency_budget_ms === 'number' ? payload.latency_budget_ms : undefined;
    const concurrencyLimit = typeof payload.concurrency_limit === 'number' ? payload.concurrency_limit : undefined;
    const outputArtifacts = Array.isArray(payload.output_artifacts)
      ? (payload.output_artifacts as unknown[]).map((value) => String(value))
      : (Array.isArray(payload.outputs) ? (payload.outputs as unknown[]).map((value) => String(value)) : undefined);
    if (latencyBudget !== undefined) {
      entry.latencyBudgetMs = latencyBudget;
    }
    if (concurrencyLimit !== undefined) {
      entry.concurrencyLimit = concurrencyLimit;
    }
    if (outputArtifacts && outputArtifacts.length) {
      entry.outputArtifacts = outputArtifacts;
    }

    toolTelemetryRef.current = [...toolTelemetryRef.current, entry].slice(-15);

    const elapsed = meta?.elapsed_ms ?? payload.elapsed_ms;
    const ts = meta?.ts || payload.ts;
    const statusLabel = payload.status === 'start' ? 'started' : payload.status === 'end' ? 'completed' : payload.status;
    const durationText = elapsed ? ` (${elapsed}ms)` : '';
    const metadataSegments: string[] = [];
    if (entry.latencyBudgetMs !== undefined) {
      metadataSegments.push(`budget ${entry.latencyBudgetMs}ms`);
    }
    if (entry.concurrencyLimit !== undefined) {
      metadataSegments.push(`concurrency ${entry.concurrencyLimit}`);
    }
    if (entry.reused) {
      metadataSegments.push('cached');
    }
    if (entry.outputArtifacts && entry.outputArtifacts.length) {
      metadataSegments.push(`outputs ${entry.outputArtifacts.slice(0, 3).join(', ')}`);
    }
    const metadataText = metadataSegments.length ? ` [${metadataSegments.join('  ')}]` : '';
    const message = `Tool ${payload.tool} ${statusLabel}${durationText}${metadataText}`;

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
    const latencyBudget = typeof payload.latency_budget_ms === 'number' ? payload.latency_budget_ms : undefined;
    const outputArtifacts = Array.isArray(payload.output_artifacts)
      ? (payload.output_artifacts as unknown[]).map((value) => String(value)).filter(Boolean)
      : undefined;

    const entry: AgentTurnTelemetry = {
      role: payload.role,
      status: payload.status,
      ts,
      elapsed_ms: elapsed,
      summary: payload.summary,
      sequence,
      parallelGroup: meta?.parallel_group ?? payload.parallel_group ?? config.lane,
    };
    const lane = resolveLane(payload, payload.metadata, { lane: config.lane }, { lane: meta?.parallel_group });
    if (lane) {
      entry.lane = lane;
    }
    const reusedFlag = resolveReusedFlag(payload, payload.metadata);
    if (reusedFlag !== undefined) {
      entry.reused = reusedFlag;
    }
    if (entry.reused === undefined && typeof payload.status === 'string') {
      const normalizedStatus = payload.status.trim().toLowerCase();
      if (normalizedStatus === 'reuse' || normalizedStatus === 'cached') {
        entry.reused = true;
      }
    }
    const concurrencyLimit = typeof payload.concurrency_limit === 'number' ? payload.concurrency_limit : undefined;
    if (latencyBudget !== undefined) {
      entry.latencyBudgetMs = latencyBudget;
    }
    if (concurrencyLimit !== undefined) {
      entry.concurrencyLimit = concurrencyLimit;
    }
    if (outputArtifacts && outputArtifacts.length) {
      entry.outputArtifacts = outputArtifacts;
    }
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
    const metadataParts: string[] = [];
    if (latencyBudget !== undefined) {
      metadataParts.push(`budget ${latencyBudget}ms`);
    }
    if (concurrencyLimit !== undefined) {
      metadataParts.push(`concurrency ${concurrencyLimit}`);
    }
    if (outputArtifacts && outputArtifacts.length) {
      metadataParts.push(`outputs ${outputArtifacts.slice(0, 3).join(', ')}`);
    }
    const baseMessage = summaryText
      ? `${config.label}: ${summaryText}`
      : `${config.label}: ${payload.status}`;
    const laneMessage = metadataParts.length ? `${baseMessage} [${metadataParts.join('  ')}]` : baseMessage;

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

  // Feature flag: stream specialist outputs as chat bubbles
  const isLiveSpecialistsEnabled = () => {
    try {
      const raw = (typeof window !== 'undefined') ? window.localStorage.getItem('showLiveSpecialists') : null;
      if (raw === null || raw === undefined) return true; // default on
      return raw !== 'false';
    } catch {
      return true;
    }
  };

  const appendResultSnapshot = (
    options: {
      content: string;
      analysis?: string | null;
      chartSpec?: any | null;
      sqlQuery?: string | null;
      dataSample?: any[] | null;
      stockWidgetConfig?: StockWidgetConfig | null;
      toolFanoutManifest?: ToolFanoutManifest[];
      toolFanoutResults?: ToolFanoutResult[];
      webSearch?: WebSearchResult | null;
      analysisOverview?: AnalysisOverview | null;
      banner?: FollowUpBanner | null;
      specialistCards?: SpecialistCard[];
    },
  ) => {
    const snapshot = workflowDataRef.current;
    const message: Omit<ChatMessage, 'id' | 'timestamp'> = {
      type: 'result',
      content: options.content,
    };

    const applyField = (
      field: keyof Omit<ChatMessage, 'id' | 'timestamp' | 'type'>,
      override: any,
      fallback: any,
    ) => {
      if (override !== undefined) {
        (message as any)[field] = override;
      } else if (fallback !== undefined) {
        (message as any)[field] = fallback;
      }
    };

    applyField('analysis', options.analysis, snapshot.analysis);
    applyField('chartSpec', options.chartSpec, snapshot.chartSpec);
    applyField('sqlQuery', options.sqlQuery, snapshot.sqlQuery);
    applyField('dataSample', options.dataSample, snapshot.dataSample);
    applyField('stockWidgetConfig', options.stockWidgetConfig, snapshot.stockWidget);
    applyField('toolFanoutManifest', options.toolFanoutManifest, snapshot.toolFanoutManifest);
    applyField('toolFanoutResults', options.toolFanoutResults, snapshot.toolFanoutResults);
    applyField('webSearch', options.webSearch, snapshot.webSearch);
    applyField('analysisOverview', options.analysisOverview, snapshot.analysisOverview);
    applyField('banner', options.banner, snapshot.followUpBanner);
    applyField('specialistCards', options.specialistCards, snapshot.specialistCards);

    addChatMessage(message);
  };

  const submitClarification = async (value: any, request?: ClarifyRequest) => {
    const req = request || pendingClarification;
    if (!req) return;
    try {
      const activeSessionId = req.session_id || sessionId || lastSessionIdRef.current;
      const answer: ClarifyAnswer = {
        session_id: activeSessionId,
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
    setStockWidget(null);
    setAnalysisOverview(null);
    setFollowUpBanner(null);
    setSpecialistCards([]);
    setRevisionMode('none');
    setLatencyGuardrail(null);
    setSnapshotReuse(null);
    workflowDataRef.current.webSearch = null;
    workflowDataRef.current.analysisOverview = null;
    workflowDataRef.current.followUpBanner = null;
    workflowDataRef.current.specialistCards = [];
    workflowDataRef.current.latencyGuardrail = null;
    workflowDataRef.current.snapshotReuse = null;
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
    const activeSessionId = sessionId || lastSessionIdRef.current;
    if (activeSessionId) {
      params.append('session_id', activeSessionId);
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
      const scheduleStage: string | undefined =
        typeof data.schedule_stage === 'string'
          ? data.schedule_stage
          : typeof eventData.schedule_stage === 'string'
          ? eventData.schedule_stage
          : undefined;
      const flowModeValue: FlowMode | undefined =
        typeof data.mode === 'string'
          ? (data.mode as FlowMode)
          : typeof eventData.mode === 'string'
          ? (eventData.mode as FlowMode)
          : undefined;
      const toolGroup: string | undefined =
        typeof data.tool_group === 'string'
          ? data.tool_group
          : typeof eventData.tool_group === 'string'
          ? eventData.tool_group
          : undefined;
      const laneFromEvent = resolveLane(eventData, eventData?.metadata, eventData?.details, data);
      const reusedFlag = resolveReusedFlag(eventData, eventData?.metadata, eventData?.details, data);

      const updateStep = (
        stepId: string,
        status: ProcessStep['status'],
        thinking: string[] = [],
        details?: any,
        elapsed?: number,
        ts?: string,
        overrides?: {
          lane?: string;
          reused?: boolean;
          finalAnswerOnly?: boolean;
          missingComponents?: string[];
          followUpRoute?: string;
          analysisAvailable?: boolean;
        },
      ) => {
        stepsHook.updateStepStatus(
          stepId,
          status,
          thinking,
          details,
          elapsed,
          ts,
          sequence,
          parallelGroup,
          scheduleStage,
          flowModeValue,
          {
            lane: overrides?.lane ?? laneFromEvent,
            reused: overrides?.reused ?? reusedFlag,
            finalAnswerOnly: overrides?.finalAnswerOnly,
            missingComponents: overrides?.missingComponents,
            followUpRoute: overrides?.followUpRoute,
            analysisAvailable: overrides?.analysisAvailable,
          },
        );
      };

      if (eventData.specialist_card) {
        const normalizedCard = normalizeSpecialistCard(eventData.specialist_card, stepInfo.ts);
        if (normalizedCard) {
          upsertSpecialistCard(normalizedCard);
        }
      }
      
      switch (eventType) {
        case 'session_started':
          {
            const nextSessionId = coerceString(eventData.session_id);
            if (nextSessionId) {
              lastSessionIdRef.current = nextSessionId;
              setSessionId((prev) => (prev === nextSessionId ? prev : nextSessionId));
            }
          }
          break;
          

        case 'status':
        case 'progress':
          // Handle both old 'status' and new 'progress' event types
          const statusMessage = eventData.message || data.message || '';
          const bannerPayload = eventData.banner || data.banner;
          if (stepInfo.step === 'follow_up_route' || bannerPayload) {
            const route = coerceString(bannerPayload?.route) ?? 'full_pipeline';
            const copy = FOLLOW_UP_BANNER_COPY[route] ?? FOLLOW_UP_BANNER_COPY.full_pipeline;
            const finalAnswerOnly = coerceBoolean(bannerPayload?.final_answer_only);
            const missingComponents = Array.isArray(bannerPayload?.missing_components)
              ? (bannerPayload.missing_components as unknown[])
                  .map((component) => coerceString(component))
                  .filter(Boolean) as string[]
              : undefined;
            const analysisAvailable = coerceBoolean(bannerPayload?.analysis_available);
            const summaryCopy = coerceString(bannerPayload?.summary);
            const banner: FollowUpBanner = {
              title: coerceString(bannerPayload?.title) ?? copy.title,
              message: coerceString(bannerPayload?.message) ?? (statusMessage || copy.message),
              route,
              flowMode: flowModeValue ?? flow,
              finalAnswerOnly: finalAnswerOnly ?? undefined,
              missingComponents,
              analysisAvailable,
              summary: summaryCopy,
            };
            setFollowUpBanner(banner);
            workflowDataRef.current.followUpBanner = banner;
            const thinkingLogs = banner.message ? [banner.message] : statusMessage ? [statusMessage] : [];
            updateStep(
              'follow_up_route',
              isThinkingEvent ? 'in_progress' : 'completed',
              thinkingLogs,
              { banner },
              stepInfo.elapsed_ms,
              stepInfo.ts,
              {
                followUpRoute: route,
                finalAnswerOnly: finalAnswerOnly ?? undefined,
                missingComponents,
                analysisAvailable,
              },
            );
            streamHook.setCurrentStatus(banner.message);
            break;
          }
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

        case 'follow_up_route': {
          const route = coerceString(eventData.route) ?? 'full_pipeline';
          const copy = FOLLOW_UP_BANNER_COPY[route] ?? FOLLOW_UP_BANNER_COPY.full_pipeline;
          const banner: FollowUpBanner = {
            title: copy.title,
            message: copy.message,
            route,
          };
          setFollowUpBanner(banner);
          workflowDataRef.current.followUpBanner = banner;
          const thinking = [`Route selected: ${route.replace(/[_-]/g, ' ')}`];
          updateStep('follow_up_route', 'in_progress', thinking, { banner }, stepInfo.elapsed_ms, stepInfo.ts);
          streamHook.setCurrentStatus(copy.message);
          break;
        }
          
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
          
        case 'sql_ready': {
          const sqlPreview = eventData.sql ? [`SQL ready (${eventData.sql.length} chars)`] : ['SQL ready'];
          scheduleProgressiveUpdate({
            sqlQuery: eventData.sql ?? workflowDataRef.current.sqlQuery,
            dataSample: eventData.sample_data ?? workflowDataRef.current.dataSample,
          });
          if (Array.isArray(eventData.columns)) {
            workflowDataRef.current.dataSample = eventData.sample_data ?? workflowDataRef.current.dataSample;
          }
          updateStep('sql_execution', 'completed', [
            eventData.row_count != null ? `Rows: ${eventData.row_count}` : sqlPreview[0],
          ], eventData, stepInfo.elapsed_ms, stepInfo.ts);
          // Live specialist bubble (SQL)
          if (isLiveSpecialistsEnabled() && !isThinkingEvent) {
            const rows = typeof eventData.row_count === 'number' ? eventData.row_count : (eventData.sample_data?.length ?? undefined);
            const header = rows != null ? `SQL Ready (rows: ${rows})` : 'SQL Ready';
            addChatMessage({
              type: 'assistant',
              content: header,
              sqlQuery: typeof eventData.sql === 'string' ? eventData.sql : undefined,
              dataSample: Array.isArray(eventData.sample_data) ? eventData.sample_data.slice(0, 5) : undefined,
              flowMode: flow,
              scheduleStage: eventData.schedule_stage || scheduleStage || 'sql',
              parallelGroup,
              sequence,
            });
          }
          break;
        }
          
        case 'chart_ready': {
          const normalizedChartSpec =
            resolveChartSpecOption(eventData.chart_spec) ??
            resolveChartSpecOption(eventData) ??
            eventData.chart_spec ??
            (data as any)?.chart_spec ??
            null;
          if (normalizedChartSpec) {
            scheduleProgressiveUpdate({ chartSpec: normalizedChartSpec });
          } else if (eventData.chart_spec) {
            console.warn('[AnalyticsMemoryStream] chart_ready event contained an unresolvable chart_spec payload', {
              event: eventData,
            });
          }
          const chartSummary = eventData.chart_summary?.chart_type
            ? [`Chart ${eventData.chart_summary.chart_type}`]
            : ['Chart ready'];
          updateStep(
            'chart_generation',
            'completed',
            chartSummary,
            eventData,
            stepInfo.elapsed_ms,
            stepInfo.ts,
          );
          break;
        }

        case 'stock_ready': {
          if (eventData.stock_widget) {
            scheduleProgressiveUpdate({ stockWidget: eventData.stock_widget as StockWidgetConfig });
            const widgetPayload = eventData.stock_widget as StockWidgetConfig;
            setStockWidget(widgetPayload);
            workflowDataRef.current.stockWidget = widgetPayload;
          }
          updateStep('tool_execution', 'completed', ['Stock widget ready'], eventData, stepInfo.elapsed_ms, stepInfo.ts);
          if (isLiveSpecialistsEnabled() && eventData.stock_widget && !isThinkingEvent) {
            const sw = eventData.stock_widget as StockWidgetConfig;
            const symbolList = Array.isArray(sw.symbols)
              ? sw.symbols
                  .map((s: any) => (Array.isArray(s) ? s[1] : s))
                  .filter((s: any) => typeof s === 'string' && s.trim().length > 0)
                  .join(', ')
              : '';
            const parts: string[] = ['Stock Widget Ready'];
            if (symbolList) parts.push(`Symbols: ${symbolList}`);
            if (sw.chartType) parts.push(`Chart: ${sw.chartType}`);
            const header = parts.join(' | ');
            addChatMessage({
              type: 'assistant',
              content: header,
              stockWidgetConfig: sw,
              flowMode: flow,
              scheduleStage: eventData.schedule_stage || scheduleStage || 'hedged_accessories',
              parallelGroup,
              sequence,
            });
          }
          break;
        }

        case 'web_ready': {
          const webContext = normalizeWebContext(eventData.web_context || eventData);
          if (webContext) {
            scheduleProgressiveUpdate({ webSearch: webContext });
            workflowDataRef.current.webSearch = webContext;
          }
          updateStep('web_research_agent', 'completed', ['Web context ready'], eventData, stepInfo.elapsed_ms, stepInfo.ts);
          if (isLiveSpecialistsEnabled() && webContext && !isThinkingEvent) {
            const primaryTopic = webContext.searchTopic || webContext.queryTerms || webContext.query || '';
            const provider = webContext.provider || '';
            const parts: string[] = ['Web Context Ready'];
            if (primaryTopic) parts.push(`Topic: ${primaryTopic}`);
            if (provider) parts.push(`Source: ${provider}`);
            const header = parts.join(' | ');
            addChatMessage({
              type: 'assistant',
              content: header,
              webSearch: webContext,
              flowMode: flow,
              scheduleStage: eventData.schedule_stage || scheduleStage || 'hedged_accessories',
              parallelGroup,
              sequence,
            });
          }
          break;
        }

        case 'analysis_ready': {
          if (typeof eventData.analysis === 'string') {
            scheduleProgressiveUpdate({ analysis: eventData.analysis });
          }
          updateStep('analysis_generation', 'completed', ['Analysis ready'], eventData, stepInfo.elapsed_ms, stepInfo.ts);
          break;
        }

        case 'hedged_accessories_complete': {
          const missing = Array.isArray(eventData.missing_tools) ? eventData.missing_tools : [];
          const thinking = missing.length ? [`Hedged accessories pending: ${missing.join(', ')}`] : ['Hedged accessories complete'];
          updateStep('tool_fanout', missing.length ? 'in_progress' : 'completed', thinking, eventData, stepInfo.elapsed_ms, stepInfo.ts);
          break;
        }

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
          // Live specialist bubble (Chart)
          if (isLiveSpecialistsEnabled() && normalizedChartSpec && !isThinkingEvent) {
            const seriesCount = Array.isArray(normalizedChartSpec.series) ? normalizedChartSpec.series.length : undefined;
            const primaryXAxis = Array.isArray((normalizedChartSpec as any)?.xAxis)
              ? (normalizedChartSpec as any).xAxis[0]
              : (normalizedChartSpec as any)?.xAxis;
            const xLen = Array.isArray(primaryXAxis?.data) ? primaryXAxis.data.length : undefined;
            const title = (normalizedChartSpec as any)?.title?.text || 'Chart Ready';
            const parts: string[] = [title];
            if (chartType) parts.push(`Type: ${chartType}`);
            if (xLen != null) parts.push(`Points: ${xLen}`);
            if (seriesCount != null) parts.push(`Series: ${seriesCount}`);
            const header = parts.join(' | ');
            addChatMessage({
              type: 'assistant',
              content: header,
              chartSpec: normalizedChartSpec,
              flowMode: flow,
              scheduleStage: eventData.schedule_stage || scheduleStage || 'chart',
              parallelGroup,
              sequence,
            });
          }
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
          const normalizedStatus =
            typeof eventData?.status === 'string' ? eventData.status.toLowerCase() : '';
          const hasOps = Array.isArray(eventData?.ops) && eventData.ops.length > 0;

          try {
            let opLines: string[] = [];
            if (hasOps) {
              setChartSpec((prev) => {
                const next = applyChartOps(prev, eventData);
                workflowDataRef.current.chartSpec = next;
                return next;
              });

              opLines = eventData.ops.map((op: any) => {
                try {
                  switch (op.op) {
                    case 'set_chart_type':
                      return `Chart type -> ${op.value}`;
                    case 'set_stack':
                      return `Stacking -> ${op.stack ? op.mode || 'normal' : 'off'}`;
                    case 'toggle_series':
                      return `Toggle series (${op.visible ? 'show' : 'hide'}): ${
                        Array.isArray(op.names) ? op.names.join(', ') : ''
                      }`;
                    case 'set_y_axis_format':
                      return `Y format -> ${op.valueType}`;
                    case 'set_x_axis':
                      return `X axis field -> ${op.field}`;
                    case 'filter_companies':
                      return `Companies -> ${Array.isArray(op.tickers) ? op.tickers.join(', ') : ''}`;
                    case 'set_palette':
                      return `Palette set (${Array.isArray(op.palette) ? op.palette.length : 0} colors)`;
                    case 'set_axis_scale':
                      return `Axis ${op.axis} scale -> ${op.scale}`;
                    case 'select_metrics': {
                      const inc =
                        op.include === 'ALL'
                          ? 'ALL'
                          : Array.isArray(op.include)
                            ? op.include.join(', ')
                            : '';
                      const exc = Array.isArray(op.exclude) ? op.exclude.join(', ') : '';
                      return `Metrics include=[${inc}] exclude=[${exc}]`;
                    }
                    case 'set_grouping':
                      return `Grouping -> ${op.grouping}`;
                    default:
                      return `Patch: ${JSON.stringify(op)}`;
                  }
                } catch {
                  return 'Patch applied';
                }
              });
            }

            const statusLines = opLines.length ? [...opLines] : [];
            if (normalizedStatus === 'skipped') {
              statusLines.push(
                eventData?.error ? `Revision skipped: ${eventData.error}` : 'Chart revision skipped',
              );
            } else if (!statusLines.length && hasOps) {
              statusLines.push('Applied chart revision');
            }

            const stepStatus: ProcessStep['status'] =
              normalizedStatus === 'skipped'
                ? 'error'
                : hasOps
                  ? 'completed'
                  : 'in_progress';

            stepsHook.updateStepStatus(
              'chart_revision',
              stepStatus,
              statusLines.length ? statusLines : ['Chart revision received'],
              {
                patch: eventData,
                status: normalizedStatus || (hasOps ? 'applied' : undefined),
              },
              stepInfo.elapsed_ms,
              stepInfo.ts,
              sequence,
              parallelGroup,
            );

            updateAgentCoordination(
              statusLines.length ? statusLines : ['Chart revision received'],
              stepStatus,
              { ts: stepInfo.ts, elapsed_ms: stepInfo.elapsed_ms, sequence },
            );

            if (normalizedStatus === 'skipped') {
              const errorMessage = eventData?.error || 'Chart revision skipped';
              streamHook.setError(errorMessage);
            } else if (hasOps) {
              streamHook.setCurrentStatus('Chart revision applied');
              emitResultOnce();
              const revisionLines = opLines.length ? opLines : ['Applied chart revision'];
              const revisionSummary =
                ['Revision: Chart updated', ...revisionLines.map((line) => `- ${line}`)].join('\n');
              appendResultSnapshot({
                content: revisionSummary,
                analysis: '',
                sqlQuery: undefined,
                stockWidgetConfig: null,
                toolFanoutManifest: undefined,
                toolFanoutResults: undefined,
                webSearch: null,
              });
              markRevisionMode('chart');
            }
          } catch (e) {
            console.warn('[AnalyticsMemoryStream] Failed to apply chart_patch', e);
          }
          break;
        }
          
        case 'analysis_revision': {
          const normalizedStatus =
            typeof eventData?.status === 'string' ? eventData.status.toLowerCase() : '';
          const revisionApplied = normalizedStatus !== 'skipped';

          try {
            const updatedAnalysis =
              typeof eventData?.analysis === 'string' ? eventData.analysis : '';

            if (revisionApplied && updatedAnalysis) {
              setAnalysis(updatedAnalysis);
              workflowDataRef.current.analysis = updatedAnalysis;
            }

            const summaryLine =
              updatedAnalysis && revisionApplied
                ? `Analysis -> ${
                    updatedAnalysis.length > 140
                      ? `${updatedAnalysis.slice(0, 140).trimEnd()}...`
                      : updatedAnalysis
                  }`
                : revisionApplied
                  ? 'Applied analysis revision'
                  : undefined;

            const lines: string[] = [];
            if (summaryLine) {
              lines.push(summaryLine);
            }
            if (!revisionApplied) {
              lines.push(
                eventData?.error ? `Revision skipped: ${eventData.error}` : 'Analysis revision skipped',
              );
            } else if (!lines.length) {
              lines.push('Analysis revision received');
            }

            const stepStatus: ProcessStep['status'] = revisionApplied ? 'completed' : 'error';

            stepsHook.updateStepStatus(
              'analysis_revision',
              stepStatus,
              lines,
              {
                analysis: revisionApplied ? updatedAnalysis : undefined,
                reason: eventData?.reason,
                source: eventData?.source,
                status: normalizedStatus || (revisionApplied ? 'applied' : undefined),
                error: eventData?.error,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts,
              sequence,
              parallelGroup,
            );

            updateAgentCoordination(
              lines.length ? lines : ['Analysis revision received'],
              stepStatus,
              { ts: stepInfo.ts, elapsed_ms: stepInfo.elapsed_ms, sequence },
            );

            if (revisionApplied) {
              streamHook.setCurrentStatus('Analysis revision applied');
              emitResultOnce();
              const summaryLines = lines.length ? lines : ['Analysis revision applied'];
              const revisionSummary =
                ['Revision: Analysis updated', ...summaryLines.map((line) => `- ${line}`)].join('\n');
              appendResultSnapshot({
                content: revisionSummary,
                stockWidgetConfig: null,
                toolFanoutManifest: undefined,
                toolFanoutResults: undefined,
                webSearch: null,
              });
              markRevisionMode('analysis');
            } else {
              const errorMessage = eventData?.error || 'Analysis revision skipped';
              streamHook.setError(errorMessage);
            }
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
              const latencyStats = webContext.latencyStats;
              if (latencyStats) {
                if (typeof latencyStats.p50_ms === 'number') {
                  thinking.push(`Latency p50: ${latencyStats.p50_ms}ms`);
                }
                if (typeof latencyStats.total_ms === 'number') {
                  thinking.push(`Latency total: ${latencyStats.total_ms}ms`);
                } else if (latency !== null) {
                  thinking.push(`Latency total: ${latency}ms`);
                }
                if (typeof latencyStats.samples === 'number') {
                  thinking.push(`Latency samples: ${latencyStats.samples}`);
                }
              } else if (latency !== null) {
                thinking.push(`Latency: ${latency}ms`);
              }
              if (webContext.model) {
                thinking.push(`Model: ${webContext.model}`);
              }
              const detailPayload: Record<string, any> = { web_context: webContext };
              if (latencyStats) {
                detailPayload.latency = latencyStats;
              } else if (latency !== null) {
                detailPayload.latency = { total_ms: latency };
              }
              stepsHook.updateStepStatus(stepId, 'completed', thinking, detailPayload, stepInfo.elapsed_ms, stepInfo.ts);
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
              if (widgetPayload !== undefined) {
                setStockWidget(widgetPayload ?? null);
              }
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
            if (bundle.analysis_overview && typeof bundle.analysis_overview === 'object') {
              const overview = parseAnalysisOverview(bundle.analysis_overview);
              if (overview) {
                setAnalysisOverview(overview);
                workflowDataRef.current.analysisOverview = overview;
              }
            }
            if (bundle.latency_guardrail) {
              const guardrail = bundle.latency_guardrail as LatencyGuardrail;
              setLatencyGuardrail(guardrail);
              workflowDataRef.current.latencyGuardrail = guardrail;
            }
            if (bundle.banner) {
              const bannerData = bundle.banner as Record<string, any>;
              const route = coerceString(bannerData.route) ?? followUpBanner?.route ?? 'full_pipeline';
              const copy = FOLLOW_UP_BANNER_COPY[route] ?? FOLLOW_UP_BANNER_COPY.full_pipeline;
              const banner: FollowUpBanner = {
                title: coerceString(bannerData.title) ?? copy.title,
                message: coerceString(bannerData.message) ?? followUpBanner?.message ?? copy.message,
                route,
              };
              setFollowUpBanner(banner);
              workflowDataRef.current.followUpBanner = banner;
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
                analysis_overview: workflowDataRef.current.analysisOverview,
                banner: workflowDataRef.current.followUpBanner,
                latency_guardrail: workflowDataRef.current.latencyGuardrail,
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
                const widgetPayload = eventData.stock_widget
                  ? (eventData.stock_widget as StockWidgetConfig)
                  : null;
                setStockWidget(widgetPayload);
                workflowDataRef.current.stockWidget = widgetPayload;
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

              const overviewCandidate =
                (eventData.analysis_overview && typeof eventData.analysis_overview === 'object' && eventData.analysis_overview) ||
                (typeof eventData.analysis === 'object' && eventData.analysis !== null ? eventData.analysis : eventData);
              const overview = parseAnalysisOverview(overviewCandidate);
              if (overview) {
                setAnalysisOverview(overview);
                workflowDataRef.current.analysisOverview = overview;
              }
              const guardrailCandidate =
                (eventData.latency_guardrail as LatencyGuardrail | undefined) ??
                (data.latency_guardrail as LatencyGuardrail | undefined);
              if (guardrailCandidate) {
                setLatencyGuardrail(guardrailCandidate);
                workflowDataRef.current.latencyGuardrail = guardrailCandidate;
              }
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
              {
                analysis: finalAnalysis,
                analysis_length: eventData.analysis_length,
                analysis_overview: workflowDataRef.current.analysisOverview,
                latency_guardrail: workflowDataRef.current.latencyGuardrail,
              },
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
              setStockWidget(widgetCandidate ?? null);
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
          if (!isThinkingEvent && !summarySentRef.current && !isSpecialistOnlyMode()) { /* patched: disable malformed content or suppress if specialist-only */
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

        case 'planner_result': {
          const metadata = (eventData.metadata ?? {}) as Record<string, any>;
          const hasSnapshotReuseField =
            Object.prototype.hasOwnProperty.call(metadata, 'snapshot_reuse') ||
            Object.prototype.hasOwnProperty.call(metadata, 'reuse_snapshot');
          const reuseCandidate = hasSnapshotReuseField
            ? (metadata.snapshot_reuse ?? metadata.reuse_snapshot)
            : undefined;
          if (reuseCandidate && typeof reuseCandidate === 'object') {
            const reuseInfo: SnapshotReuseInfo = {
              reusedSql: coerceBoolean((reuseCandidate as any).reused_sql),
              reusedChart: coerceBoolean((reuseCandidate as any).reused_chart),
              reusedStock: coerceBoolean((reuseCandidate as any).reused_stock),
              reusedWeb: coerceBoolean((reuseCandidate as any).reused_web),
              reusedAnalysis: coerceBoolean((reuseCandidate as any).reused_analysis),
              criteriaChanged: coerceBoolean((reuseCandidate as any).criteria_changed),
              source: coerceString((reuseCandidate as any).source),
              followUpRoute:
                coerceString((reuseCandidate as any).follow_up_route) ??
                coerceString(metadata.follow_up_route),
            };
            setSnapshotReuse(reuseInfo);
            workflowDataRef.current.snapshotReuse = reuseInfo;
          } else if (hasSnapshotReuseField) {
            setSnapshotReuse((prev) => (prev === null ? prev : null));
            workflowDataRef.current.snapshotReuse = null;
          }
          const overviewCandidate = metadata.analysis_overview;
          if (overviewCandidate) {
            const overview = parseAnalysisOverview(overviewCandidate);
            if (overview) {
              setAnalysisOverview(overview);
              workflowDataRef.current.analysisOverview = overview;
            }
          }
          const guardrailMeta = metadata.web_search_guardrail as LatencyGuardrail | undefined;
          if (guardrailMeta) {
            setLatencyGuardrail(guardrailMeta);
            workflowDataRef.current.latencyGuardrail = guardrailMeta;
          }
          break;
        }

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
              stockWidget: null,
              toolFanoutManifest: [],
              toolFanoutResults: [],
              concurrencyLimit: 0,
              webSearch: null,
              flowMode: flow,
              analysisOverview: null,
              followUpBanner: null,
              specialistCards: [],
              latencyGuardrail: null,
              snapshotReuse: null,
            };
            setChartSpec(null);
            setAnalysis('');
            setSqlQuery('');
            setDataSample(null);
            setStreamingText('');
            setAnalysisOverview(null);
            setFollowUpBanner(null);
            setSpecialistCards([]);
            setLatencyGuardrail(null);
          }
          break;

        case 'final_answer':
          {
            const finalMessage = coerceString(eventData?.message) ?? 'Analysis completed.';
            const finalAnswerOnly = coerceBoolean(eventData?.final_answer_only);
            const missingComponents = Array.isArray(eventData?.missing_components)
              ? (eventData.missing_components as unknown[]).map((item) => coerceString(item)).filter(Boolean) as string[]
              : undefined;
            const followUpRoute = coerceString(eventData?.follow_up_route) ?? 'full_pipeline';
            const analysisAvailable = coerceBoolean(eventData?.analysis_available);
            const flowModeOverride =
              (typeof eventData?.flow_mode === 'string' ? (eventData.flow_mode as FlowMode) : undefined) ?? flowModeValue ?? flow;
            const banner: FollowUpBanner = {
              title: finalAnswerOnly ? 'Guided Final Answer' : 'Final Answer Ready',
              message: finalMessage,
              route: followUpRoute,
              flowMode: flowModeOverride,
              finalAnswerOnly: finalAnswerOnly ?? undefined,
              missingComponents,
              analysisAvailable,
              summary: coerceString(eventData?.summary),
            };
            setFollowUpBanner(banner);
            workflowDataRef.current.followUpBanner = banner;

            updateStep(
              'finalization',
              'completed',
              ['Provided final response'],
              {
                banner,
                final_answer_only: finalAnswerOnly ?? undefined,
                missing_components: missingComponents,
                follow_up_route: followUpRoute,
                analysis_available: analysisAvailable,
                message: finalMessage,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts,
              {
                finalAnswerOnly: finalAnswerOnly ?? undefined,
                missingComponents,
                followUpRoute,
                analysisAvailable,
              },
            );

            streamHook.setCurrentStatus(finalMessage || 'Completed');
            if (!isThinkingEvent && !isSpecialistOnlyMode()) {
              addChatMessage({
                type: 'assistant',
                content: finalMessage,
              });
            }
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

  const resetAll = (options?: { preserveSession?: boolean }) => {
    const preserveSession = Boolean(options?.preserveSession);
    streamHook.resetState();
    stepsHook.resetSteps();
    if (!preserveSession) {
      setSessionId('');
      lastSessionIdRef.current = '';
    }
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
    setWebSearch(null);
    setStockWidget(null);
    setSingleAgentFanout(null);
    setRevisionMode('none');
    setAnalysisOverview(null);
    setFollowUpBanner(null);
    setSpecialistCards([]);
    setLatencyGuardrail(null);
    setSnapshotReuse(null);

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
      webSearch: null,
      flowMode: flow,
      analysisOverview: null,
      followUpBanner: null,
      specialistCards: [],
      latencyGuardrail: null,
      snapshotReuse: null,
    };
  };

  // Optional knob to suppress generic model chat in favor of specialist-only chat
  const isSpecialistOnlyMode = () => {
    try {
      const raw = (typeof window !== 'undefined') ? window.localStorage.getItem('specialistOnlyChat') : null;
      return raw === 'true';
    } catch {
      return false;
    }
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
    stockWidget,
    analysisOverview,
    followUpBanner,
    specialistCards,
    singleAgentFanout,
    revisionMode,
    latencyGuardrail,
    snapshotReuse,

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










