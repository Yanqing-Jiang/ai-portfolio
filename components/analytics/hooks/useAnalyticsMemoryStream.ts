import { useState, useRef, useCallback, useEffect } from 'react';
import {
  ChatMessage,
  ClarifyRequest,
  ClarifyAnswer,
  ToolCallTelemetry,
  AgentTurnTelemetry,
  AgentReasoningTelemetry,
  ProcessStep,
  ToolFanoutManifest,
  ToolFanoutResult,
  StockWidgetConfig,
  WebSearchResult,
  WebSearchTopic,
  WebSearchTopicProgress,
  WebTopicBranchProgress,
  WebTopicBranchStatus,
  AnalysisOverview,
  AnalysisEvidenceLink,
  AnalysisSources,
  AnalysisSourceInsight,
  FollowUpBanner,
  SpecialistCard,
  SingleAgentFanout,
  SingleAgentFanoutBranch,
  FanoutBranchStatus,
  FlowMode,
  LatencyGuardrail,
  SlotStatusMap,
  SlotStatusPayload,
  LaneReuseNotice,
  FreshLaneStatus,
  AgentEvidence,
} from '../types';
import { apiService } from '../../../services/apiService';
import { STEP_NAME } from '../../../constants/analytics';
import { useAnalyticsStream } from './useAnalyticsStream';

// Phase 4.1: Import decomposed sub-hooks for gradual integration
// These hooks centralize event parsing, agent events, workflow state, badge logic, and planner events
import {
  useEventParser,
  useAgentEvents,
  useWorkflowState,
  useBadgeLogic,
  usePlannerEvents,
  type ParsedEvent,
  type ReceiptData,
} from './index';

import { useProcessSteps } from './useProcessSteps';
import {
  resolveChartSpecOption,
  applyChartOps,
  sanitizeStructuredText,
  sanitizeStructuredList,
} from '../utils';
import * as analyticsUtils from './useAnalyticsUtils';
import type { ChartGranularity } from './useAnalyticsUtils';

 

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

 

const formatTimeframeDisplay = analyticsUtils.formatTimeframeDisplay;

const coerceFlowMode = analyticsUtils.coerceFlowMode;

const extractAnalysisFocus = analyticsUtils.extractAnalysisFocus;

const detectGranularityFromText = analyticsUtils.detectGranularityFromText;

const normalizeGranularityValue = analyticsUtils.normalizeGranularityValue;

const extractGranularityFromTimeframe = analyticsUtils.extractGranularityFromTimeframe;

const resolveGranularityCandidate = analyticsUtils.resolveGranularityCandidate;

const coerceClarificationValue = analyticsUtils.coerceClarificationValue;

const formatClarificationEcho = analyticsUtils.formatClarificationEcho;

export const useAnalyticsMemoryStream = (
  flow: 'planner-executor' | 'single-agent' | 'multi-agent' = 'single-agent',
) => {
  const [sessionId, setSessionId] = useState<string>('');
  const [pendingClarification, setPendingClarification] = useState<ClarifyRequest | null>(null);

  const [criteria, setCriteria] = useState<any | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chartSpec, setChartSpec] = useState<any>(null);
  const [analysis, setAnalysis] = useState('');
  const [sqlQuery, setSqlQuery] = useState('');
  const [dataSample, setDataSample] = useState<any[] | null>(null);
  const [revisionMode, setRevisionMode] = useState<'none' | 'chart' | 'analysis' | 'market' | 'mixed'>('none');
  const [streamingText, setStreamingText] = useState('');
  const [webSearch, setWebSearch] = useState<WebSearchResult | null>(null);
  const [topicProgress, setTopicProgress] = useState<WebSearchTopicProgress>({ total: 0, completed: 0, pending: 0, branches: {} });
  const [agentEvidence, setAgentEvidence] = useState<AgentEvidence | null>(null);
  const agentEvidenceRef = useRef<AgentEvidence | null>(null);
  const applyAgentEvidenceUpdate = useCallback(
    (updater: (prev: AgentEvidence | null) => AgentEvidence | null) => {
      setAgentEvidence((prev) => {
        const next = updater(prev);
        agentEvidenceRef.current = next;
        return next;
      });
    },
    [],
  );
  const [stockWidget, setStockWidget] = useState<StockWidgetConfig | null>(null);
  const [singleAgentFanout, setSingleAgentFanout] = useState<SingleAgentFanout | null>(null);
  const [analysisOverview, setAnalysisOverview] = useState<AnalysisOverview | null>(null);
  const [analysisSources, setAnalysisSources] = useState<AnalysisSources | null>(null);
  const [analysisBundle, setAnalysisBundle] = useState<Record<string, any> | null>(null);
  const [followUpBanner, setFollowUpBanner] = useState<FollowUpBanner | null>(null);
  const [latencyGuardrail, setLatencyGuardrail] = useState<LatencyGuardrail | null>(null);
  useEffect(() => {
    agentEvidenceRef.current = agentEvidence;
  }, [agentEvidence]);
  const [specialistCards, setSpecialistCards] = useState<SpecialistCard[]>([]);
  const [slotStatuses, setSlotStatuses] = useState<SlotStatusMap>({});
  const [slotFollowups, setSlotFollowups] = useState<ClarifyRequest[]>([]);
  const [snapshotReuse, setSnapshotReuse] = useState<SnapshotReuseInfo | null>(null);
  const [laneReuseNotices, setLaneReuseNotices] = useState<LaneReuseNotice[]>([]);
  const [agenticRevisionActive, setAgenticRevisionActive] = useState<boolean>(false);
  const [freshLaneStates, setFreshLaneStates] = useState<Record<string, FreshLaneStatus>>({});
  const [redirectNotice, setRedirectNotice] = useState<string | null>(null);
  const [telemetryFlowMode, setTelemetryFlowMode] = useState<FlowMode>(flow);
  const revisionContextRef = useRef<{ id?: string; lanes: string[]; focus?: string }>({
    id: undefined,
    lanes: [],
    focus: undefined,
  });
  const pendingRevisionFocusRef = useRef<string | undefined>(undefined);
  const revisionModeRef = useRef<'none' | 'chart' | 'analysis' | 'market' | 'mixed'>('none');
  const lastClarificationEchoRef = useRef<{ slot: string; content: string } | null>(null);
  const lastClarificationRequestIdRef = useRef<string | null>(null);
  const lastClarificationMissingRef = useRef<string | null>(null);
  const resultSentRef = useRef<boolean>(false);
  const summarySentRef = useRef<boolean>(false);
  const lastSessionIdRef = useRef<string>('');
  const resultMessageIdRef = useRef<string | null>(null);
  const analysisReadyEmittedRef = useRef<boolean>(false);
  const finalResultMergedRef = useRef<boolean>(false);
  const hasExplicitResultContentRef = useRef<boolean>(false);
  const telemetryFlowModeRef = useRef<FlowMode>(flow);
  const finalizationMessageRef = useRef<string | null>(null);
  const thoughtHistoryRef = useRef<Record<string, Set<string>>>({});
  const pendingAnalysisBufferRef = useRef<string>('');



  const markThoughtIfNew = (stepId?: string, thoughtId?: string | null) => {
    if (!stepId || !thoughtId) {
      return true;
    }
    const normalizedStep = stepId.trim();
    if (!normalizedStep) {
      return true;
    }
    let bucket = thoughtHistoryRef.current[normalizedStep];
    if (!bucket) {
      bucket = new Set<string>();
      thoughtHistoryRef.current[normalizedStep] = bucket;
    }
    if (bucket.has(thoughtId)) {
      return false;
    }
    bucket.add(thoughtId);
    if (bucket.size > 120) {
      const first = bucket.values().next().value;
      if (first) {
        bucket.delete(first);
      }
    }
    return true;
  };

  const storageKey = typeof window !== 'undefined' ? `analytics:lastSessionId:${flow}` : null;

  useEffect(() => {
    if (!storageKey) {
      return;
    }
    try {
      const stored = window.sessionStorage.getItem(storageKey);
      if (stored && !sessionId && !lastSessionIdRef.current) {
        lastSessionIdRef.current = stored;
        setSessionId(stored);
      }
    } catch {
      // Ignore storage errors (e.g., server-side rendering or private mode).
    }
  }, [storageKey, sessionId]);

  const buildResultMessageFields = () => ({
    flowMode: workflowDataRef.current.flowMode ?? flow,
    analysis: workflowDataRef.current.analysis || workflowDataRef.current.streamingText,
    progressiveAnalysis: workflowDataRef.current.progressiveAnalysis,
    progressiveText: workflowDataRef.current.progressiveText,
    chartSpec: workflowDataRef.current.chartSpec,
    sqlQuery: workflowDataRef.current.sqlQuery,
    dataSample: workflowDataRef.current.dataSample,
    stockWidgetConfig: workflowDataRef.current.stockWidget,
    toolFanoutManifest: workflowDataRef.current.toolFanoutManifest,
    toolFanoutResults: workflowDataRef.current.toolFanoutResults,
    webSearch: workflowDataRef.current.webSearch,
    analysisOverview: workflowDataRef.current.analysisOverview,
    analysisSources: workflowDataRef.current.analysisSources,
    analysisBundle: workflowDataRef.current.analysisBundle,
    banner: workflowDataRef.current.followUpBanner,
    specialistCards: workflowDataRef.current.specialistCards,
    latencyGuardrail: workflowDataRef.current.latencyGuardrail,
  });

  const generateMessageId = () =>
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

  const persistSessionId = (nextSessionId?: string | null) => {
    if (!nextSessionId) {
      return;
    }
    if (sessionId === nextSessionId) {
      return;
    }
    lastSessionIdRef.current = nextSessionId;
    setSessionId(nextSessionId);
    if (storageKey) {
      try {
        window.sessionStorage.setItem(storageKey, nextSessionId);
      } catch {
        /* ignore storage errors */
      }
    }
  };

  const clearSessionTracking = () => {
    if (!sessionId && !lastSessionIdRef.current) {
      return;
    }
    setSessionId('');
    setAgenticRevisionActive(false);
    setFreshLaneStates({});
    lastSessionIdRef.current = '';
    if (storageKey) {
      try {
        window.sessionStorage.removeItem(storageKey);
      } catch {
        /* ignore */
      }
    }
  };

  const emitResultOnce = useCallback((options?: { content?: string }) => {
    if (resultSentRef.current) return;
    resultSentRef.current = true;
    finalResultMergedRef.current = false;
    const hasCustomContent = typeof options?.content === 'string';
    const content = hasCustomContent
      ? (options?.content as string)
      : 'Streaming analysis - cards will update below as tools finish.';
    const newMessage = {
      id: generateMessageId(),
      timestamp: new Date().toISOString(),
      type: 'result' as const,
      content,
      ...buildResultMessageFields(),
    };
    resultMessageIdRef.current = newMessage.id;
    hasExplicitResultContentRef.current =
      hasCustomContent && content.trim().length > 0;
    setChatHistory((prev) => [...prev, newMessage]);
  }, [setChatHistory, flow]);

  const refreshResultMessage = useCallback((overrides?: Partial<ChatMessage>) => {
    const messageId = resultMessageIdRef.current;
    if (!messageId) return;
    const baseFields = buildResultMessageFields();
    const payload = { ...baseFields, ...overrides };
    if (overrides && Object.prototype.hasOwnProperty.call(overrides, 'content')) {
      const overrideContent = (overrides as { content?: unknown }).content;
      if (typeof overrideContent === 'string') {
        hasExplicitResultContentRef.current = overrideContent.trim().length > 0;
      } else if (overrideContent == null) {
        hasExplicitResultContentRef.current = false;
      }
    }
    setChatHistory((prev) =>
      prev.map((message) => (message.id === messageId ? { ...message, ...payload } : message)),
    );
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

  const normalizeTopicBranchPayload = (
    rawBranches: any,
    fallbackStatus: WebTopicBranchStatus,
  ): Record<string, WebTopicBranchProgress> => {
    if (!rawBranches) {
      return {};
    }
    const entries = Array.isArray(rawBranches)
      ? rawBranches
      : typeof rawBranches === 'object'
        ? Object.values(rawBranches)
        : [];
    const normalized: Record<string, WebTopicBranchProgress> = {};
    entries.forEach((entry: any, index: number) => {
      if (!entry || typeof entry !== 'object') {
        return;
      }
      const identifier =
        coerceString(entry.id) ||
        coerceString(entry.question_kind) ||
        coerceString(entry.questionKind) ||
        `topic_${index}`;
      if (!identifier) {
        return;
      }
      normalized[identifier] = {
        id: identifier,
        questionKind: coerceString(entry.question_kind ?? entry.questionKind) ?? undefined,
        label: coerceString(entry.label ?? entry.title) ?? undefined,
        status: (entry.status as WebTopicBranchStatus) ?? fallbackStatus,
        latencyMs:
          typeof entry.latency_ms === 'number'
            ? entry.latency_ms
            : typeof entry.latencyMs === 'number'
              ? entry.latencyMs
              : undefined,
        startedAt: coerceString(entry.started_at ?? entry.startedAt) ?? undefined,
        completedAt: coerceString(entry.completed_at ?? entry.completedAt) ?? undefined,
        error: coerceString(entry.error) ?? undefined,
      };
    });
    return normalized;
  };

  const normalizeSlotStatuses = (payload: any): SlotStatusMap => {
    if (!payload || typeof payload !== 'object') {



      return {};
    }
    const result: SlotStatusMap = {};
    Object.entries(payload as Record<string, any>).forEach(([slot, raw]) => {
      if (!raw || typeof raw !== 'object') {
        return;
      }
      const status = typeof (raw as any).status === 'string' ? (raw as any).status : 'missing';
      const suggestions = Array.isArray((raw as any).suggestions)
        ? (raw as any).suggestions.filter((entry: unknown) => typeof entry === 'string')
        : undefined;
      result[slot] = {
        status: status as SlotStatusPayload['status'],
        value: (raw as any).value,
        reason: typeof (raw as any).reason === 'string' ? (raw as any).reason : undefined,
        suggestions,
        allow_custom: typeof (raw as any).allow_custom === 'boolean' ? (raw as any).allow_custom : undefined,
      };
    });
    return result;
  };

  const upsertSlotStatus = (slot: string, update: Partial<SlotStatusPayload>) => {
    setSlotStatuses((prev) => {
      const existing = prev[slot] ?? { status: 'missing' as SlotStatusPayload['status'] };
      const owns = Object.prototype.hasOwnProperty;
      const next: SlotStatusPayload = {
        status: (update.status ?? existing.status ?? 'missing') as SlotStatusPayload['status'],
        value: owns.call(update, 'value') ? update.value : existing.value,
        reason: owns.call(update, 'reason') ? update.reason : existing.reason,
        suggestions: owns.call(update, 'suggestions') ? update.suggestions : existing.suggestions,
        allow_custom: owns.call(update, 'allow_custom') ? update.allow_custom : existing.allow_custom,
      };

      return { ...prev, [slot]: next };
    });
  };

  const clearClarificationState = () => {
    setSlotStatuses({});
    setSlotFollowups([]);
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
      const telemetryLane = coerceString((source as any).telemetry_step);
      if (telemetryLane) {
        return telemetryLane;
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
    const tldrValue = sanitizeStructuredText(coerceString(source.tldr ?? source.summary));
    const highlightsValue = sanitizeStructuredList(coerceStringList(source.highlights ?? source.bullets));
    const keyNumbersValue = sanitizeStructuredList(coerceStringList(source.key_numbers ?? source.keyNumbers));
    const riskWatchValue = sanitizeStructuredList(
      coerceStringList(source.risk_watch ?? source.riskWatch ?? source.watchlist),
    );
    const nextStepsValue = sanitizeStructuredList(
      coerceStringList(source.next_steps ?? source.nextSteps ?? source.actions),
    );
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
        const snippet = sanitizeStructuredText(coerceString(item.snippet ?? item.excerpt));
        if (snippet) {
          entry.snippet = snippet.length > 260 ? `${snippet.slice(0, 257).trimEnd()}...` : snippet;
        }
        const claim = sanitizeStructuredText(coerceString(item.claim));
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

    const hasHighlights = Array.isArray(highlightsValue) && highlightsValue.length > 0;
    const hasKeyNumbers = Array.isArray(keyNumbersValue) && keyNumbersValue.length > 0;
    const hasRiskWatch = Array.isArray(riskWatchValue) && riskWatchValue.length > 0;
    const hasNextSteps = Array.isArray(nextStepsValue) && nextStepsValue.length > 0;

    if (
      !tldrValue &&
      !hasHighlights &&
      !hasKeyNumbers &&
      !hasRiskWatch &&
      !hasNextSteps &&
      !evidenceEntries.length
    ) {
      return null;
    }

    return {
      tldr: tldrValue || undefined,
      highlights: hasHighlights ? highlightsValue?.slice(0, 3) : undefined,
      keyNumbers: hasKeyNumbers ? keyNumbersValue?.slice(0, 3) : undefined,
      riskWatch: hasRiskWatch ? riskWatchValue?.slice(0, 3) : undefined,
      nextSteps: hasNextSteps ? nextStepsValue?.slice(0, 3) : undefined,
      evidence: evidenceEntries.length ? evidenceEntries.slice(0, 5) : undefined,
    };
  };

  const parseAnalysisSources = (source: any): AnalysisSources | null => {
    if (!source || typeof source !== 'object') {
      return null;
    }
    const entries: AnalysisSources = {};
    for (const [rawKey, rawValue] of Object.entries(source as Record<string, any>)) {
      if (!rawValue || typeof rawValue !== 'object') {
        continue;
      }
      const lane = resolveLane(rawValue, (rawValue as any).lane, (rawValue as any).telemetry_step, rawKey) ?? rawKey;
      const id = coerceString((rawValue as any).id) ?? coerceString((rawValue as any).lane) ?? coerceString(rawKey) ?? rawKey;
      const label =
        coerceString((rawValue as any).label) ??
        (lane === 'sql'
          ? 'SQL data'
          : lane === 'web'
            ? 'Online research'
            : lane === 'stock'
              ? 'Stock data'
              : undefined);
      const summary = coerceString((rawValue as any).summary);
      const reused = resolveReusedFlag(
        (rawValue as any).reused,
        (rawValue as any).status,
        (rawValue as any).source,
        (rawValue as any).cache_hit,
        (rawValue as any).from_cache
      );
      const rowCount = coerceNumber((rawValue as any).row_count);
      const columns = coerceStringList((rawValue as any).columns).slice(0, 6);
      const snippetCount = coerceNumber((rawValue as any).snippet_count);
      const symbols = coerceStringList((rawValue as any).symbols).slice(0, 4);
      const latestClose = coerceNumber((rawValue as any).latest_close);
      const changePercent = coerceNumber((rawValue as any).change_percent);
      const topic = coerceString((rawValue as any).topic);
      entries[id] = {
        id,
        lane,
        label,
        summary: summary ?? undefined,
        reused: reused ?? undefined,
        rowCount: rowCount ?? undefined,
        columns: columns.length ? columns : undefined,
        snippetCount: typeof snippetCount === 'number' ? snippetCount : undefined,
        symbols: symbols.length ? symbols : undefined,
        latestClose: latestClose ?? undefined,
        changePercent: changePercent ?? undefined,
        topic: topic ?? undefined,
      };
    }
    return Object.keys(entries).length ? entries : null;
  };

  const makeAnalysisSourceFingerprint = (key: string, insight: AnalysisSourceInsight): string => {
    const lane = (insight.lane ?? '').toString().toLowerCase();
    const id = (insight.id ?? '').toString().toLowerCase();
    const label = (insight.label ?? '').toString().toLowerCase();
    const normalizedKey = key.toLowerCase();
    const identifier = id || label || normalizedKey;
    return [lane, identifier].filter(Boolean).join('::');
  };

  const mergeAnalysisInsights = (
    existing: AnalysisSourceInsight | undefined,
    incoming: AnalysisSourceInsight,
    fallbackKey: string,
  ): AnalysisSourceInsight => {
    const pickArray = (next?: string[], prev?: string[]) =>
      Array.isArray(next) && next.length ? next : prev;

    return {
      id: incoming.id ?? existing?.id ?? fallbackKey,
      lane: incoming.lane ?? existing?.lane,
      label: incoming.label ?? existing?.label,
      summary: incoming.summary ?? existing?.summary,
      reused: incoming.reused ?? existing?.reused,
      rowCount: incoming.rowCount ?? existing?.rowCount,
      columns: pickArray(incoming.columns, existing?.columns),
      snippetCount: incoming.snippetCount ?? existing?.snippetCount,
      symbols: pickArray(incoming.symbols, existing?.symbols),
      latestClose: incoming.latestClose ?? existing?.latestClose,
      changePercent: incoming.changePercent ?? existing?.changePercent,
      topic: incoming.topic ?? existing?.topic,
    };
  };

  const mergeAnalysisSources = (
    baseline: AnalysisSources | null,
    incoming: AnalysisSources,
  ): AnalysisSources => {
    const result: AnalysisSources = baseline ? { ...baseline } : {};
    const fingerprintIndex = new Map<string, string>();

    if (baseline) {
      for (const [key, insight] of Object.entries(baseline)) {
        fingerprintIndex.set(makeAnalysisSourceFingerprint(key, insight), key);
      }
    }

    for (const [incomingKey, insight] of Object.entries(incoming)) {
      const fingerprint = makeAnalysisSourceFingerprint(incomingKey, insight);
      const targetKey = fingerprintIndex.get(fingerprint) ?? incomingKey;
      fingerprintIndex.set(fingerprint, targetKey);
      result[targetKey] = mergeAnalysisInsights(result[targetKey], insight, targetKey);
    }

    return result;
  };

  /*
  Function: normalizeQuestionBundle — called from useAnalyticsMemoryStream SSE handlers
  (follow_up_route, web_ready, agent HTML revisions) to sanitize Gemini question payloads before
  emitting revision cards and follow-up banners. Invokes coerceString to strip unsafe text and keep
  the UI inputs consistent, giving downstream emitRevisionQuestionCard/followUpBanner writers one
  reliable representation of user/industry questions. Exists so non-React callers can normalize
  question metadata without tripping hook rules.
  */
  const normalizeQuestionBundle = (
    raw: any,
  ): { keywordFocus?: string | null; user?: string | null; industry?: string | null } | undefined => {
    if (!raw || typeof raw !== 'object') {
      return undefined;
    }
    const keywordFocus = coerceString(raw.keyword_focus ?? raw.keywordFocus);
    const userQuestion = coerceString(raw.user_question ?? raw.userQuestion);
    const industryQuestion = coerceString(raw.industry_question ?? raw.industryQuestion);
    if (!keywordFocus && !userQuestion && !industryQuestion) {
      return undefined;
    }

    return {
      keywordFocus: keywordFocus ?? null,
      user: userQuestion ?? null,
      industry: industryQuestion ?? null,
    };
  };

  const normalizeWebContext = (raw: any): WebSearchResult | null => {
    if (!raw) {
      return null;
    }
    const cloneSnippet = (item: any) => ({
      title: coerceString(item?.title),
      url: coerceString(item?.url),
      snippet: coerceString(item?.snippet),
      display_url: coerceString(item?.display_url) ?? coerceString(item?.displayUrl),
      published_at: coerceString(item?.published_at) ?? coerceString(item?.publishedAt),
    });
    const snippets = Array.isArray(raw.snippets) ? raw.snippets.map(cloneSnippet) : [];
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
    const topicIndex = coerceNumber((raw as any).topic_index ?? (raw as any).topicIndex);
    const topicPosition = coerceNumber((raw as any).topic_position ?? (raw as any).topicPosition);
    const topicLabel = coerceString((raw as any).topic_label ?? (raw as any).topicLabel);
    const topicReason = coerceString((raw as any).topic_reason ?? (raw as any).topicReason ?? reason);
    const latencyValue = typeof raw.latency_ms === 'number'
      ? raw.latency_ms
      : (typeof raw.latencyMs === 'number' ? raw.latencyMs : null);
    const topics = Array.isArray(raw.topics)
      ? raw.topics
        .map((topic: any, index: number) => ({
          label: coerceString(topic?.label) ?? coerceString(topic?.topic_label) ?? `Topic ${index + 1}`,
          topic_label: coerceString(topic?.topic_label) ?? coerceString(topic?.label),
          topicLabel: coerceString(topic?.topic_label) ?? coerceString(topic?.label),
          query: coerceString(topic?.query) ?? coerceString(topic?.base_query) ?? query ?? '',
          reason: coerceString(topic?.reason),
          summary: coerceString(topic?.summary),
          search_id: coerceString(topic?.search_id) ?? coerceString(topic?.searchId),
          latency_ms: typeof topic?.latency_ms === 'number'
            ? topic.latency_ms
            : (typeof topic?.latencyMs === 'number' ? topic.latencyMs : null),
          snippets: Array.isArray(topic?.snippets) ? topic.snippets.map((item: any) => normalizeSnippet(item)) : [],
          topic_index: coerceNumber(topic?.topic_index ?? topic?.topicIndex),
          topicIndex: coerceNumber(topic?.topic_index ?? topic?.topicIndex),
          topic_position: coerceNumber(topic?.topic_position ?? topic?.topicPosition),
          topicPosition: coerceNumber(topic?.topic_position ?? topic?.topicPosition),
        }))
        .filter((topic: any) => topic.query)
      : [];
    if (searchTopics && searchTopics.length && !searchTopicValue) {
      searchTopicValue = searchTopics[0];
    }
    if ((topicLabel || topicIndex != null) && !topics.some((topic: any) => {
      const currentIndex = typeof topic.topic_index === 'number' ? topic.topic_index : (typeof topic.topicIndex === 'number' ? topic.topicIndex : undefined);
      if (currentIndex != null && topicIndex != null) {
        return currentIndex === topicIndex;
      }
      if (topicLabel && topic.label) {
        return topic.label.trim().toLowerCase() === topicLabel.trim().toLowerCase();
      }
      return false;
    })) {
      topics.push({
        label: topicLabel ?? searchTopicValue ?? query ?? `Topic ${(topicIndex ?? topics.length) + 1}`,
        topic_label: topicLabel ?? undefined,
        topicLabel: topicLabel ?? undefined,
        query: coerceString((raw as any).base_query) ?? query ?? '',
        reason: topicReason,
        summary,
        search_id: coerceString(raw.search_id) ?? coerceString(raw.searchId),
        latency_ms: latencyValue,
        snippets: snippets.map((item: any) => ({ ...item })),
        topic_index: topicIndex ?? null,
        topicIndex: topicIndex ?? null,
        topic_position: topicPosition ?? null,
        topicPosition: topicPosition ?? null,
      });
    }
    const mergedSearchTopics = (() => {
      const source = new Set<string>();
      (searchTopics ?? []).forEach((entry) => { if (entry) source.add(entry); });
      if (topicLabel) {
        source.add(topicLabel);
      }
      topics.forEach((topic: any) => {
        if (topic.label) {
          source.add(topic.label);
        }
      });
      if (source.size === 0) {
        return searchTopics;
      }
      return Array.from(source);
    })();
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
    const questions = normalizeQuestionBundle(raw.questions);



    return {
      query,
      queryTerms,
      searchTopic: searchTopicValue,
      summary,
      error,
      reason,
      snippets,
      annotations: Array.isArray(raw.annotations) ? raw.annotations : [],
      topics,
      searchId: coerceString(raw.search_id) ?? coerceString(raw.searchId),
      topicLabel: topicLabel ?? undefined,
      fromCache: raw.from_cache ?? raw.fromCache ?? raw.cache_hit ?? false,
      fetchedAt: coerceString(raw.fetched_at) ?? coerceString(raw.fetchedAt),
      latencyMs: latencyValue,
      topicIndex: topicIndex ?? null,
      topicPosition: topicPosition ?? null,
      ready: raw.ready ?? (error !== 'search_api_missing' && reason !== 'search_api_missing'),
      provider: coerceString(raw.provider) ?? (raw.model ? 'Gemini' : undefined),
      model: coerceString(raw.model) ?? coerceString(raw.model_name) ?? coerceString(raw.modelName),
      latencyStats,
      questions,
      searchTopics: mergedSearchTopics ?? searchTopics,
      topicTotal:
        typeof raw.topic_total === 'number'
          ? raw.topic_total
          : typeof raw.topicTotal === 'number'
            ? raw.topicTotal
            : undefined,
    };
  };

  type WebSnippet = WebSearchTopic['snippets'][number];

  const mergeSnippetArrays = (existing: WebSnippet[] = [], incoming: WebSnippet[] = []) => {
    const seen = new Set<string>();
    const result: WebSnippet[] = [];
    const pushUnique = (snippet?: WebSnippet | null) => {
      if (!snippet) {
        return;
      }
      const key = `${snippet.url ?? ''}|${snippet.snippet ?? ''}|${snippet.title ?? ''}`;
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      result.push({
        title: snippet.title,
        url: snippet.url,
        snippet: snippet.snippet,
        display_url: snippet.display_url,
        published_at: snippet.published_at,
      });
    };

    [...existing, ...incoming].forEach(pushUnique);
    return result;
  };

  const mergeWebContexts = (current: WebSearchResult | null, incoming: WebSearchResult): WebSearchResult => {
    const coerceTopicTotal = (...values: Array<unknown>): number | undefined => {
      for (const value of values) {
        if (typeof value === 'number' && Number.isFinite(value)) {
          return value;
        }
        if (typeof value === 'string') {
          const parsed = Number(value);
          if (Number.isFinite(parsed)) {
            return parsed;
          }
        }
      }
      return undefined;
    };

    if (!current) {
      return {
        ...incoming,
        snippets: mergeSnippetArrays([], incoming.snippets),
        topics: (incoming.topics ?? []).map((topic) => ({
          ...topic,
          snippets: mergeSnippetArrays([], topic.snippets),
        })),
        searchTopics: incoming.searchTopics ? [...incoming.searchTopics] : undefined,
        annotations: Array.isArray(incoming.annotations) ? [...incoming.annotations] : [],
        topicTotal: coerceTopicTotal(incoming.topicTotal, (incoming as any).topic_total) ?? incoming.topics?.length,
      };
    }

    const mergedSearchTopicsSet = new Set<string>();
    const pushSearchTopic = (value?: string) => {
      if (value) {
        mergedSearchTopicsSet.add(value);
      }
    };
    (current.searchTopics ?? []).forEach(pushSearchTopic);
    pushSearchTopic(current.topicLabel);
    (incoming.searchTopics ?? []).forEach(pushSearchTopic);
    pushSearchTopic(incoming.searchTopic);
    pushSearchTopic(incoming.topicLabel);
    const searchTopics = mergedSearchTopicsSet.size ? Array.from(mergedSearchTopicsSet) : undefined;

    const resolveTopicIndex = (topic: WebSearchTopic): number | undefined => {
      const direct = (topic as any)?.topic_index ?? (topic as any)?.topicIndex;
      if (typeof direct === 'number' && Number.isFinite(direct)) {
        return direct;
      }
      return undefined;
    };
    const resolveTopicPosition = (topic: WebSearchTopic): number | undefined => {
      const direct = (topic as any)?.topic_position ?? (topic as any)?.topicPosition;
      if (typeof direct === 'number' && Number.isFinite(direct)) {
        return direct;
      }
      return undefined;
    };
    const topicEntries: Array<{ key: string; topic: WebSearchTopic }> = [];
    const topicKey = (topic: WebSearchTopic, fallbackIndex: number) => {
      const idx = resolveTopicIndex(topic);
      if (idx !== undefined) {
        return `idx-${idx}`;
      }
      const position = resolveTopicPosition(topic);
      if (position !== undefined) {
        return `pos-${position}`;
      }
      const label = topic.label ?? (topic as any)?.topicLabel;
      if (label) {
        return `label-${label.trim().toLowerCase()}`;
      }
      if (topic.query) {
        return `query-${topic.query.trim().toLowerCase()}`;
      }
      return `ord-${fallbackIndex}`;
    };

    (current.topics ?? []).forEach((topic, index) => {
      topicEntries.push({
        key: topicKey(topic, index),
        topic: {
          ...topic,
          topic_index: resolveTopicIndex(topic) ?? null,
          topicIndex: resolveTopicIndex(topic) ?? null,
          topic_position: resolveTopicPosition(topic) ?? null,
          topicPosition: resolveTopicPosition(topic) ?? null,
          topic_label: (topic as any)?.topic_label ?? (topic as any)?.topicLabel ?? topic.label,
          topicLabel: (topic as any)?.topicLabel ?? (topic as any)?.topic_label ?? topic.label,
          snippets: mergeSnippetArrays([], topic.snippets),
        },
      });
    });

    (incoming.topics ?? []).forEach((topic, index) => {
      topicEntries.push({
        key: topicKey(topic, index),
        topic: {
          ...topic,
          topic_index: resolveTopicIndex(topic) ?? null,
          topicIndex: resolveTopicIndex(topic) ?? null,
          topic_position: resolveTopicPosition(topic) ?? null,
          topicPosition: resolveTopicPosition(topic) ?? null,
          topic_label: (topic as any)?.topic_label ?? (topic as any)?.topicLabel ?? topic.label,
          topicLabel: (topic as any)?.topicLabel ?? (topic as any)?.topic_label ?? topic.label,
          snippets: mergeSnippetArrays([], topic.snippets),
        },
      });
    });

    const mergedTopicMap = new Map<string, WebSearchTopic>();
    topicEntries.forEach(({ key, topic }) => {
      const existingTopic = mergedTopicMap.get(key);
      if (!existingTopic) {
        mergedTopicMap.set(key, topic);
        return;
      }
      mergedTopicMap.set(key, {
        label: topic.label ?? (topic as any)?.topicLabel ?? existingTopic.label,
        query: topic.query || existingTopic.query || '',
        reason: existingTopic.reason ?? topic.reason,
        summary: topic.summary ?? existingTopic.summary,
        search_id: topic.search_id ?? existingTopic.search_id,
        latency_ms: typeof topic.latency_ms === 'number' ? topic.latency_ms : existingTopic.latency_ms,
        snippets: mergeSnippetArrays(existingTopic.snippets, topic.snippets),
        topic_index: resolveTopicIndex(topic) ?? resolveTopicIndex(existingTopic) ?? null,
        topicIndex: resolveTopicIndex(topic) ?? resolveTopicIndex(existingTopic) ?? null,
        topic_position: resolveTopicPosition(topic) ?? resolveTopicPosition(existingTopic) ?? null,
        topicPosition: resolveTopicPosition(topic) ?? resolveTopicPosition(existingTopic) ?? null,
        topic_label: (topic as any)?.topic_label ?? (existingTopic as any)?.topic_label,
        topicLabel: (topic as any)?.topicLabel ?? (existingTopic as any)?.topicLabel,
      });
    });

    const mergedTopics = Array.from(mergedTopicMap.values());
    mergedTopics.sort((a, b) => {
      const idxA = resolveTopicIndex(a) ?? Number.MAX_SAFE_INTEGER;
      const idxB = resolveTopicIndex(b) ?? Number.MAX_SAFE_INTEGER;
      if (idxA !== idxB) {
        return idxA - idxB;
      }
      const posA = resolveTopicPosition(a) ?? Number.MAX_SAFE_INTEGER;
      const posB = resolveTopicPosition(b) ?? Number.MAX_SAFE_INTEGER;
      if (posA !== posB) {
        return posA - posB;
      }
      const labelA = ((a.label ?? (a as any)?.topicLabel ?? a.query) || '').toLowerCase();
      const labelB = ((b.label ?? (b as any)?.topicLabel ?? b.query) || '').toLowerCase();
      return labelA.localeCompare(labelB);
    });

    const mergeAnnotations = () => {
      if (!Array.isArray(current.annotations) && !Array.isArray(incoming.annotations)) {
        return current.annotations;
      }
      const currentList = Array.isArray(current.annotations) ? current.annotations : [];
      const incomingList = Array.isArray(incoming.annotations) ? incoming.annotations : [];
      const seen = new Set<string>();
      const combined: any[] = [];
      [...currentList, ...incomingList].forEach((annotation: any) => {
        if (!annotation || typeof annotation !== 'object') {
          return;
        }
        const key = JSON.stringify([
          annotation.url ?? annotation.source ?? '',
          annotation.snippet ?? annotation.text ?? annotation.segment?.text ?? '',
        ]);
        if (seen.has(key)) {
          return;
        }
        seen.add(key);
        combined.push(annotation);
      });
      return combined;
    };

    const selectDate = (a?: string, b?: string) => {
      if (!a) return b;
      if (!b) return a;
      const aTime = Date.parse(a);
      const bTime = Date.parse(b);
      if (Number.isFinite(aTime) && Number.isFinite(bTime)) {
        return bTime > aTime ? b : a;
      }
      return b ?? a;
    };




    return {
      ...current,
      query: incoming.query ?? current.query,
      queryTerms: incoming.queryTerms ?? current.queryTerms,
      searchTopic: incoming.searchTopic ?? current.searchTopic,
      searchTopics,
      summary: incoming.summary ?? current.summary,
      snippets: mergeSnippetArrays(current.snippets, incoming.snippets),
      annotations: mergeAnnotations(),
      topics: mergedTopics,
      searchId: incoming.searchId ?? current.searchId,
      fromCache: incoming.fromCache ?? current.fromCache,
      fetchedAt: selectDate(current.fetchedAt, incoming.fetchedAt),
      latencyMs: incoming.latencyMs ?? current.latencyMs,
      ready: current.ready || incoming.ready,
      error: incoming.error ?? current.error,
      reason: incoming.reason ?? current.reason,
      provider: incoming.provider ?? current.provider,
      model: incoming.model ?? current.model,
      latencyStats: incoming.latencyStats ?? current.latencyStats,
      topicLabel: incoming.topicLabel ?? current.topicLabel,
      topicIndex: (typeof incoming.topicIndex === 'number' ? incoming.topicIndex : current.topicIndex) ?? null,
      topicPosition:
        (typeof incoming.topicPosition === 'number' ? incoming.topicPosition : current.topicPosition) ?? null,
      topicTotal:
        coerceTopicTotal(
          current.topicTotal,
          (current as any).topic_total,
          incoming.topicTotal,
          (incoming as any).topic_total,
        ) ?? mergedTopics.length,
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
        .filter((symbol: any): symbol is string => Boolean(symbol))
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
    let lane = resolveLane(raw, raw.meta, raw.telemetry_step);
    if (!lane && card.type) {
      const fallbackLane =
        analyticsUtils.SPECIALIST_TYPE_TO_LANE[card.type] ??
        analyticsUtils.SPECIALIST_TYPE_TO_LANE[card.type.toLowerCase()];
      if (fallbackLane) {
        lane = fallbackLane;
      }
    }
    if (lane) {
      card.lane = lane.toLowerCase();
    }
    const source = coerceString(raw.source ?? raw.meta?.source ?? raw.details?.source ?? raw.tool);
    if (source) {
      card.source = source;
    }
    const parallelGroup = coerceString(raw.parallel_group ?? raw.parallelGroup ?? raw.meta?.parallel_group);
    if (parallelGroup) {
      card.parallelGroup = parallelGroup;
    }
    const reusedFlag = resolveReusedFlag(raw, raw.meta);
    if (reusedFlag !== undefined) {
      card.reused = reusedFlag;
    }
    const sessionToken = coerceString(raw.session_id ?? raw.sessionId ?? raw.meta?.session_id);
    if (sessionToken) {
      card.sessionId = sessionToken;
    }
    const revisionId = coerceString(raw.revision_id ?? raw.revisionId ?? raw.meta?.revision_id);
    if (revisionId) {
      card.revisionId = revisionId;
      card.revision = true;
    }
    const revisionFlag = coerceBoolean(raw.revision ?? raw.meta?.revision);
    if (revisionFlag !== undefined) {
      card.revision = revisionFlag;
    }
    const revisionEventFlag = coerceBoolean(raw.revision_event ?? raw.revisionEvent ?? raw.meta?.revision_event);
    if (revisionEventFlag !== undefined) {
      card.revisionEvent = revisionEventFlag;
    }
    const providedPayloadHash = coerceString(raw.payload_hash ?? raw.payloadHash ?? raw.meta?.payload_hash);
    card.payloadHash = providedPayloadHash ?? analyticsUtils.computeCardPayloadHash(card);

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
    analysisBundle?: Record<string, any> | null;
  }>({});

  const toolTelemetryRef = useRef<ToolCallTelemetry[]>([]);
  const agentTurnsRef = useRef<AgentTurnTelemetry[]>([]);
  const agentReasoningRef = useRef<AgentReasoningTelemetry[]>([]);
  const seenThoughtIdsRef = useRef<Set<string>>(new Set());
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
    progressiveAnalysis: string;
    progressiveText: string;
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
    analysisSources: AnalysisSources | null;
    analysisBundle: Record<string, any> | null;
    followUpBanner: FollowUpBanner | null;
    followUpLanes?: string[];
    specialistCards: SpecialistCard[];
    latencyGuardrail: LatencyGuardrail | null;
    snapshotReuse: SnapshotReuseInfo | null;
    requestedGranularity: ChartGranularity | null;
    revisionFocus: string | null;
    revisionQuestions?: { keywordFocus?: string | null; user?: string | null; industry?: string | null };
    webQuestions?: { keywordFocus?: string | null; user?: string | null; industry?: string | null };
  }>({
    chartSpec: null,
    analysis: '',
    progressiveAnalysis: '',
    progressiveText: '',
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
    analysisSources: null,
    analysisBundle: null,
    followUpBanner: null,
    followUpLanes: [],
    specialistCards: [],
    latencyGuardrail: null,
    snapshotReuse: null,
    requestedGranularity: null,
    revisionFocus: null,
  });

  const commitRequestedGranularity = useCallback(
    (candidate: ChartGranularity | null) => {
      if (!candidate) {
        return;
      }
      const current = workflowDataRef.current.requestedGranularity;
      if (current === 'quarterly' && candidate !== 'quarterly') {
        return;
      }
      if (current !== candidate) {
        workflowDataRef.current.requestedGranularity = candidate;
      }
    },
    [],
  );

  const applyGranularityToChartSpec = useCallback(
    (spec: any): any => {
      if (!spec || typeof spec !== 'object') {
        return spec;
      }
      const granularity = workflowDataRef.current.requestedGranularity;
      if (!granularity) {
        return spec;
      }
      const currentMeta = (spec as any).meta ?? {};
      const requestedMatches = currentMeta.requestedGranularity === granularity;
      const hasMetaGranularity =
        typeof currentMeta.granularity === 'string' && currentMeta.granularity.length > 0;
      const timeframeMeta =
        currentMeta.timeframe && typeof currentMeta.timeframe === 'object'
          ? (currentMeta.timeframe as Record<string, any>)
          : null;
      const timeframeHasGranularity =
        timeframeMeta && typeof timeframeMeta.granularity === 'string' && timeframeMeta.granularity.length > 0;
      if (requestedMatches && (hasMetaGranularity || !currentMeta.granularity) && (!timeframeMeta || timeframeHasGranularity)) {
        return spec;
      }
      const nextMeta: Record<string, any> = { ...currentMeta, requestedGranularity: granularity };
      if (!hasMetaGranularity) {
        nextMeta.granularity = granularity;
      }
      if (timeframeMeta) {
        nextMeta.timeframe = { ...timeframeMeta };
        if (!timeframeHasGranularity) {
          nextMeta.timeframe.granularity = granularity;
        }
      } else {
        nextMeta.timeframe = { granularity };
      }



      return {
        ...spec,
        meta: nextMeta,
      };
    },
    [],
  );

  const applyAnalysisSourcesUpdate = useCallback((incoming: AnalysisSources | null | undefined) => {
    if (!incoming || !Object.keys(incoming).length) {
      return;
    }
    const merged = mergeAnalysisSources(workflowDataRef.current.analysisSources, incoming);
    workflowDataRef.current.analysisSources = merged;
    setAnalysisSources(merged);
    refreshResultMessage();
  }, [refreshResultMessage]);

  const upsertSpecialistCard = useCallback((card: SpecialistCard) => {
    setSpecialistCards((prev) => {
      const normalizedLane = card.lane ? card.lane.toLowerCase() : undefined;
      const candidate: SpecialistCard = {
        ...card,
        lane: normalizedLane,
      };
      if (!candidate.sessionId && sessionId) {
        candidate.sessionId = sessionId;
      }
      candidate.payloadHash = candidate.payloadHash ?? analyticsUtils.computeCardPayloadHash(candidate);
      const keyFor = (entry: SpecialistCard) => {
        const meta = entry.meta ?? {};
        const questionKey =
          typeof meta.question_id === 'string'
            ? meta.question_id
            : typeof meta.questionId === 'string'
              ? meta.questionId
              : entry.topic ?? '';
        const metaSession =
          typeof meta.session_id === 'string'
            ? meta.session_id
            : typeof meta.sessionId === 'string'
              ? meta.sessionId
              : undefined;
        const sessionToken = entry.sessionId ?? metaSession ?? sessionId ?? '';
        const revisionToken = entry.revisionId ?? 'baseline';
        return [
          sessionToken,
          revisionToken,
          entry.type ?? 'accessory',
          entry.lane ?? '',
          questionKey,
          entry.parallelGroup ?? '',
        ].join('::');
      };
      const targetKey = keyFor(candidate);
      const existingIndex = prev.findIndex((item) => keyFor(item) === targetKey);
      let next: SpecialistCard[];
      if (existingIndex >= 0) {
        const current = prev[existingIndex];
        const prevHash = current.payloadHash;
        const nextHash = candidate.payloadHash;
        if (prevHash && nextHash && prevHash === nextHash) {
          const revisionChanged = candidate.revisionId && candidate.revisionId !== current.revisionId;
          if (!revisionChanged) {
            return prev;
          }
        }
        next = [...prev];
        next[existingIndex] = {
          ...current,
          ...candidate,
          source: candidate.source ?? current.source,
          reused: candidate.reused ?? current.reused,
          payloadHash: candidate.payloadHash ?? current.payloadHash,
        };
      } else {
        next = [...prev, candidate];
      }
      const priorityForCard = (entry: SpecialistCard) => {
        const typeKey = typeof entry.type === 'string' ? entry.type.toLowerCase() : '';
        const laneKeyRaw = entry.lane ?? (typeKey ? analyticsUtils.SPECIALIST_TYPE_TO_LANE[typeKey] : undefined);
        const laneKey = laneKeyRaw ? laneKeyRaw.toLowerCase() : '';
        if (laneKey && Object.prototype.hasOwnProperty.call(analyticsUtils.SPECIALIST_LANE_PRIORITY, laneKey)) {
          return analyticsUtils.SPECIALIST_LANE_PRIORITY[laneKey];
        }
        return 100;
      };
      next.sort((a, b) => {
        const diff = priorityForCard(a) - priorityForCard(b);
        if (diff !== 0) {
          return diff;
        }
        const tsA = a.ts ? Date.parse(a.ts) : 0;
        const tsB = b.ts ? Date.parse(b.ts) : 0;
        if (Number.isFinite(tsA) && Number.isFinite(tsB) && tsA !== tsB) {
          return tsA - tsB;
        }
        return (a.title || '').localeCompare(b.title || '');
      });
      if (next.length > 1) {
        const seen = new Set<string>();
        const deduped: SpecialistCard[] = [];
        for (let idx = next.length - 1; idx >= 0; idx -= 1) {
          const entry = next[idx];
          const hash = entry.payloadHash;
          if (hash) {
            if (seen.has(hash)) {
              continue;
            }
            seen.add(hash);
          }
          deduped.push(entry);
        }
        next = deduped.reverse();
      }
      workflowDataRef.current.specialistCards = next;
      return next;
    });
    refreshResultMessage();
  }, [refreshResultMessage, sessionId]);

  const emitRevisionQuestionCard = useCallback(
    (
      bundle: { keywordFocus?: string | null; user?: string | null; industry?: string | null } | undefined,
      laneHint?: string | null,
      revisionId?: string | null,
    ) => {
      if (!bundle) {
        return;
      }
      const normalizedLane = laneHint ? laneHint.trim().toLowerCase() : undefined;
      const resolvedLane = normalizedLane === 'chart' ? 'chart' : 'analysis';
      const snippets: SpecialistCard['snippets'] = [];
      if (bundle.user) {
        snippets.push({ title: 'User prompt', snippet: bundle.user });
      }
      if (bundle.industry) {
        snippets.push({ title: 'Industry prompt', snippet: bundle.industry });
      }
      upsertSpecialistCard({
        type: 'revision_questions',
        lane: resolvedLane,
        title: resolvedLane === 'chart' ? 'Chart Revision Questions' : 'Narrative Revision Questions',
        message: bundle.keywordFocus ?? undefined,
        snippets,
        revision: true,
        revisionId: revisionId ?? revisionContextRef.current.id ?? undefined,
        ts: new Date().toISOString(),
      });
    },
    [upsertSpecialistCard],
  );

  const streamHook = useAnalyticsStream();
  const stepsHook = useProcessSteps();

  useEffect(() => {
    telemetryFlowModeRef.current = flow;
    setTelemetryFlowMode(flow);
  }, [flow]);

  useEffect(() => {
    workflowDataRef.current.flowMode = telemetryFlowMode;
  }, [telemetryFlowMode]);

  useEffect(() => {
    const bufferedAnalysis = pendingAnalysisBufferRef.current;
    if (topicProgress.total > 0 && topicProgress.pending === 0 && bufferedAnalysis) {
      // Flush buffered analysis updates once topic branches complete
      setAnalysis(bufferedAnalysis);
      workflowDataRef.current.analysis = bufferedAnalysis;
      pendingAnalysisBufferRef.current = '';
    }
  }, [topicProgress.total, topicProgress.pending]);

  // Progressive update function with debouncing
  const scheduleProgressiveUpdate = (updates: Partial<typeof pendingUpdatesRef.current>) => {
    const normalizedUpdates: Partial<typeof pendingUpdatesRef.current> = { ...updates };
    if (typeof normalizedUpdates.analysis === 'string') {
      const sanitized = sanitizeStructuredText(normalizedUpdates.analysis);
      normalizedUpdates.analysis = sanitized ?? normalizedUpdates.analysis;
    }
    if (normalizedUpdates.chartSpec !== undefined) {
      normalizedUpdates.chartSpec = applyGranularityToChartSpec(normalizedUpdates.chartSpec);
      workflowDataRef.current.chartSpec = normalizedUpdates.chartSpec;
    }
    // Merge pending updates
    Object.assign(pendingUpdatesRef.current, normalizedUpdates);

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
        workflowDataRef.current.progressiveAnalysis = pending.analysis ?? '';
      }
      if (pending.streamingText !== undefined) {
        setStreamingText(pending.streamingText);
        setProgressiveText(pending.streamingText);
        workflowDataRef.current.streamingText = pending.streamingText;
        workflowDataRef.current.progressiveText = pending.streamingText ?? '';
      }
      if (pending.chartSpec !== undefined) {
        const annotatedSpec = applyGranularityToChartSpec(pending.chartSpec);
        setChartSpec(annotatedSpec);
        workflowDataRef.current.chartSpec = annotatedSpec;
        pending.chartSpec = annotatedSpec;
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
      if (pending.analysisBundle !== undefined) {
        setAnalysisBundle(pending.analysisBundle ?? null);
        workflowDataRef.current.analysisBundle = pending.analysisBundle ?? null;
      }

      refreshResultMessage();

      // Clear pending updates
      pendingUpdatesRef.current = {};
    }, 50); // 50ms debounce for smooth updates
  };

  const markRevisionMode = useCallback((mode: 'chart' | 'analysis' | 'market') => {
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

  const resolveAgentConfig = (role: string) => analyticsUtils.AGENT_ROLE_CONFIG[role] ?? analyticsUtils.DEFAULT_AGENT_ROLE;

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
      const roleConfig =
        Object.values(analyticsUtils.AGENT_ROLE_CONFIG).find((config) => config.stepId === stepId) ?? analyticsUtils.DEFAULT_AGENT_ROLE;
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

    const metadata = (payload.metadata ?? {}) as Record<string, any>;
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
    if (!entry.toolGroup && typeof payload.tool_group === 'string') {
      entry.toolGroup = payload.tool_group;
    }
    const lane = resolveLane(payload, payload.metadata, { lane: meta?.parallel_group });
    if (lane) {
      entry.lane = lane;
    }
    const reusedFlag = resolveReusedFlag(payload, payload.metadata);
    if (reusedFlag !== undefined) {
      entry.reused = reusedFlag;
    }
    const toolCallId =
      coerceString((payload as any).tool_call_id) ??
      coerceString((payload as any).id) ??
      coerceString(metadata.id);
    if (toolCallId) {
      entry.toolCallId = toolCallId;
    }
    const specialistRole = coerceString(metadata.specialist_role ?? (payload as any).specialist_role);
    if (specialistRole) {
      entry.specialistRole = specialistRole;
    }
    const specialistLabel =
      coerceString(metadata.specialist_label ?? (payload as any).specialist_label) ??
      analyticsUtils.formatSpecialistRoleLabel(specialistRole);
    if (specialistLabel) {
      entry.specialistLabel = specialistLabel;
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
    const schemaVersion = coerceString(metadata.schema_version ?? (payload as any).schema_version);
    if (schemaVersion) {
      entry.schemaVersion = schemaVersion;
    }
    const retryCount = coerceNumber(metadata.retry_count ?? (payload as any).retry_count);
    if (retryCount !== undefined) {
      entry.retryCount = retryCount;
    }
    const cacheAgeSeconds = coerceNumber(metadata.cache_age_seconds ?? (payload as any).cache_age_seconds);
    if (cacheAgeSeconds !== undefined) {
      entry.cacheAgeSeconds = cacheAgeSeconds;
    }
    const cacheSource = coerceString(metadata.cache_source ?? (payload as any).cache_source);
    if (cacheSource) {
      entry.cacheSource = cacheSource;
    }
    const fastPathLatency = coerceNumber(metadata.fast_path_latency_ms ?? (payload as any).fast_path_latency_ms);
    if (fastPathLatency !== undefined) {
      entry.fastPathLatencyMs = fastPathLatency;
    }
    const guardrailPayload =
      payload.guardrail ??
      payload.latency_guardrail ??
      payload.metadata?.guardrail ??
      payload.metadata?.latency_guardrail;
    if (guardrailPayload) {
      entry.guardrail = guardrailPayload as Record<string, any>;
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
    if (payload.tool) {
      entry.tool = String(payload.tool);
    }
    if (payload.specialist) {
      entry.specialist = String(payload.specialist);
    } else if (payload.tool) {
      entry.specialist = String(payload.tool);
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
    const turnId = coerceString(payload.agent_turn_id ?? payload.turn_id ?? payload.tool_call?.id);
    if (turnId) {
      entry.id = turnId;
    }
    if (entry.id) {
      const existingIndex = agentTurnsRef.current.findIndex((turn) => turn.id === entry.id);
      if (existingIndex >= 0) {
        const merged = { ...agentTurnsRef.current[existingIndex], ...entry };
        agentTurnsRef.current = [
          ...agentTurnsRef.current.slice(0, existingIndex),
          merged,
          ...agentTurnsRef.current.slice(existingIndex + 1),
        ];
      } else {
        agentTurnsRef.current = [...agentTurnsRef.current, entry].slice(-15);
      }
    } else {
      agentTurnsRef.current = [...agentTurnsRef.current, entry].slice(-15);
    }

    applyAgentEvidenceUpdate((prev) => {
      if (prev && prev.status !== 'agent_run') {
        return prev;
      }
      const priorTurns = prev?.turns ?? [];
      if (entry.id) {
        const existingIndex = priorTurns.findIndex((turn) => turn.id === entry.id);
        if (existingIndex >= 0) {
          const merged = { ...priorTurns[existingIndex], ...entry };
          const nextTurns = [
            ...priorTurns.slice(0, existingIndex),
            merged,
            ...priorTurns.slice(existingIndex + 1),
          ];
          return { status: 'agent_run', turns: nextTurns };
        }
      }
      const nextTurns = [...priorTurns, entry].slice(-15);
      return { status: 'agent_run', turns: nextTurns };
    });

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
      id: generateMessageId(),
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
      replacePriorResult?: boolean;
      pruneFreshResults?: boolean;
      revisionId?: string | null;
      revisionFocus?: string | null;
    },
  ) => {
    const snapshot = workflowDataRef.current;
    const payload: Omit<ChatMessage, 'id' | 'timestamp'> = {
      type: 'result',
      content: options.content,
    };
    if (options.revisionId) {
      (payload as any).revisionId = options.revisionId;
      (payload as any).revision = true;
    }

    const applyField = (
      field: keyof Omit<ChatMessage, 'id' | 'timestamp' | 'type'>,
      override: any,
      fallback: any,
    ) => {
      if (override !== undefined) {
        (payload as any)[field] = override;
      } else if (fallback !== undefined) {
        (payload as any)[field] = fallback;
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
    applyField('revisionFocus', options.revisionFocus, snapshot.revisionFocus);

    workflowDataRef.current.revisionFocus =
      (payload as any).revisionFocus !== undefined
        ? ((payload as any).revisionFocus ?? null)
        : snapshot.revisionFocus ?? null;

    setChatHistory((prev) => {
      const lastResultIndex = (() => {
        for (let idx = prev.length - 1; idx >= 0; idx -= 1) {
          if (prev[idx].type === 'result') {
            return idx;
          }
        }
        return -1;
      })();

      const filtered = options.pruneFreshResults
        ? prev.filter((message) => message.type !== 'result')
        : options.replacePriorResult
        ? prev.filter((message, index) => {
          if (message.type !== 'result') {
            return true;
          }
          if (options.revisionId && message.revisionId === options.revisionId) {
            return false;
          }
          if (!options.revisionId && message.revision) {
            return false;
          }
          if (index === lastResultIndex) {
            return false;
          }
          return true;
        })
        : prev;
      let base = filtered;
      let mutated = false;
      if (options.chartSpec != null) {
        base = filtered.map((message, index) => {
          if (index !== filtered.length - 1 || message.type !== 'result') {
            return message;
          }
          if (
            !message.chartSpec &&
            !message.dataSample &&
            !message.stockWidgetConfig &&
            (!message.toolFanoutManifest || message.toolFanoutManifest.length === 0) &&
            (!message.toolFanoutResults || message.toolFanoutResults.length === 0) &&
            !message.webSearch
          ) {
            return message;
          }
          mutated = true;



          return {
            ...message,
            chartSpec: null,
            dataSample: null,
            stockWidgetConfig: null,
            toolFanoutManifest: [],
            toolFanoutResults: [],
            webSearch: null,
          };
        });
      }

      const working = mutated ? base : filtered;
      const nextMessage: ChatMessage = {
        ...payload,
        id: generateMessageId(),
        timestamp: new Date().toISOString(),
      };
      const last = working[working.length - 1];
      const shouldMerge =
        last?.type === 'result' &&
        typeof last.content === 'string' &&
        typeof nextMessage.content === 'string' &&
        last.content.trim() === nextMessage.content.trim();

      if (shouldMerge) {
        const merged: ChatMessage = {
          ...last,
          ...nextMessage,
          id: last.id,
        };
        const withoutLast = working.slice(0, -1);
        resultSentRef.current = true;
        resultMessageIdRef.current = merged.id;
        hasExplicitResultContentRef.current =
          typeof merged.content === 'string' && merged.content.trim().length > 0;
        return [...withoutLast, merged];
      }

      resultSentRef.current = true;
      resultMessageIdRef.current = nextMessage.id;
      hasExplicitResultContentRef.current =
        typeof nextMessage.content === 'string' && nextMessage.content.trim().length > 0;
      return [...working, nextMessage];
    });
  };

  const submitClarification = async (value: any, request?: ClarifyRequest) => {
    const req = request || pendingClarification;
    if (!req) return;
    const normalizedValue = typeof value === 'string' ? value.trim() : value;
    const echo = formatClarificationEcho(req.slot, normalizedValue);
    if (echo) {
      addChatMessage({
        type: 'user',
        content: echo,
      });
      lastClarificationEchoRef.current = { slot: req.slot, content: echo };
    } else {
      lastClarificationEchoRef.current = null;
    }
    try {
      const activeSessionId = req.session_id || sessionId || lastSessionIdRef.current;
      const answer: ClarifyAnswer = {
        session_id: activeSessionId,
        request_id: req.request_id,
        slot: req.slot,
        value: normalizedValue,
        ts: new Date().toISOString(),
      };
      await apiService.post('/api/analytics/memory/clarify', answer);
      setPendingClarification(null);
    } catch (e: any) {
      streamHook.setError(`Failed to submit clarification: ${e?.message || e}`);
    }
  };

  const handleQuery = async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) return;

    // Stop any existing stream before starting a new one
    if (streamHook.isLoading) {
      streamHook.stopStream();
      // Wait a brief moment for the stream to be properly closed
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    const activeSessionId = sessionId || lastSessionIdRef.current;
    const usageResponse = await apiService.countUserInput({ scope: 'next-gen-analytics-agent' });
    if (!usageResponse.success) {
      const errorMessage = usageResponse.error || 'Rate limit exceeded. Please try again later.';
      streamHook.setError(errorMessage);
      streamHook.setCurrentStatus(`Error: ${errorMessage}`);
      addChatMessage({
        type: 'assistant',
        content: errorMessage,
      });
      return;
    }

    // Add user query to chat history
    addChatMessage({
      type: 'user',
      content: trimmed,
    });


    const hadResult = resultSentRef.current;
    const isFollowUp = Boolean(hadResult && activeSessionId);
    if (hadResult && !activeSessionId) {
      const fallbackMessage =
        'The previous analysis session expired. Please start a new analysis run before requesting revisions.';
      streamHook.setError(fallbackMessage);
      streamHook.setCurrentStatus(`Error: ${fallbackMessage}`);
      addChatMessage({
        type: 'assistant',
        content: fallbackMessage,
      });
      return;
    }
    const focusCandidate = extractAnalysisFocus(trimmed);
    if (isFollowUp) {
      revisionModeRef.current = revisionModeRef.current === 'none' ? 'mixed' : revisionModeRef.current;
      pendingRevisionFocusRef.current = focusCandidate;
    } else {
      revisionModeRef.current = 'none';
      revisionContextRef.current = { id: undefined, lanes: [], focus: undefined };
      pendingRevisionFocusRef.current = undefined;
    }
    workflowDataRef.current.revisionFocus = null;

    // Reset stream accumulators for new query while preserving prior cards when revising
    setStreamingText('');
    setProgressiveText('');
    setProgressiveAnalysis('');
    thoughtHistoryRef.current = {};
    workflowDataRef.current.streamingText = '';
    workflowDataRef.current.progressiveText = '';
    workflowDataRef.current.progressiveAnalysis = '';

    if (!isFollowUp) {
      setWebSearch(null);
      setStockWidget(null);
      setAnalysisOverview(null);
      setFollowUpBanner(null);
      setSpecialistCards([]);
      setRevisionMode('none');
      revisionModeRef.current = 'none';
      setSnapshotReuse(null);
      workflowDataRef.current.webSearch = null;
      workflowDataRef.current.analysisOverview = null;
      workflowDataRef.current.followUpBanner = null;
      workflowDataRef.current.specialistCards = [];
      workflowDataRef.current.snapshotReuse = null;
    } else {
      setRevisionMode((prev) => (prev === 'none' ? 'mixed' : prev));
    }
    setLaneReuseNotices([]);
    setAgenticRevisionActive(false);
    setFreshLaneStates({});
    setRedirectNotice(null);
    setLatencyGuardrail(null);
    workflowDataRef.current.latencyGuardrail = null;
    setPendingClarification(null);
    clearClarificationState();
    lastClarificationMissingRef.current = null;
    lastClarificationRequestIdRef.current = null;
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
    seenThoughtIdsRef.current = new Set();
    resultSentRef.current = false;
    summarySentRef.current = false;
    resultMessageIdRef.current = null;
    analysisReadyEmittedRef.current = false;
    finalResultMergedRef.current = false;
    hasExplicitResultContentRef.current = false;
    finalizationMessageRef.current = null;

    const baseEndpoint = `/api/analytics/memory/stream`;
    const ensureSessionToken = () => {
      if (activeSessionId) {
        return activeSessionId;
      }
      const generated =
        (typeof crypto !== 'undefined' && (crypto as any)?.randomUUID
          ? (crypto as any).randomUUID()
          : undefined) || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
      persistSessionId(generated);
      return generated;
    };
    const sessionTokenForRun = ensureSessionToken();

    const params = new URLSearchParams({ query: trimmed });
    if (sessionTokenForRun) {
      params.append('session_id', sessionTokenForRun);
    }
    if (flow) {
      params.append('flow', flow);
    }

    const endpoint = `${baseEndpoint}?${params.toString()}`;

    await streamHook.startStream(endpoint, (data) => {
      const rawEventType = data.event || data.type;
      const eventType =
        typeof rawEventType === 'string'
          ? analyticsUtils.REVISION_EVENT_ALIASES[rawEventType] ?? rawEventType
          : rawEventType;
      // Handle both old (heavy) and new (lightweight) event formats
      const eventData = data.data || data;
      const rawThoughtId = coerceString(eventData.thought_id ?? data.thought_id);
      const eventVisibility =
        typeof data.event_type === 'string' ? data.event_type : 'user';
      const isThinkingEvent = eventVisibility === 'thinking';
      const revisionId = coerceString(data.revision_id ?? eventData.revision_id);
      const revisionLanesRaw =
        Array.isArray(data.revision_lanes)
          ? data.revision_lanes
          : Array.isArray(eventData.revision_lanes)
            ? eventData.revision_lanes
            : undefined;
      const normalizedRevisionLanes = Array.isArray(revisionLanesRaw)
        ? (revisionLanesRaw as unknown[])
          .map((lane) => (typeof lane === 'string' ? lane.toLowerCase() : ''))
          .filter((lane): lane is string => lane.length > 0)
        : [];
      if (revisionId || normalizedRevisionLanes.length) {
        revisionContextRef.current = {
          id: revisionId ?? revisionContextRef.current.id,
          lanes: normalizedRevisionLanes.length ? normalizedRevisionLanes : revisionContextRef.current.lanes,
          focus: revisionContextRef.current.focus,
        };
      }
      const revisionFlag = coerceBoolean(data.revision ?? eventData.revision);
      const revisionEventFlag =
        coerceBoolean(data.revision_event ?? eventData.revision_event) ||
        (typeof rawEventType === 'string' &&
          Object.prototype.hasOwnProperty.call(analyticsUtils.REVISION_EVENT_ALIASES, rawEventType));
      const isRevisionEvent = Boolean(revisionFlag || revisionEventFlag || revisionId);
      const effectiveRevisionId = revisionId ?? revisionContextRef.current.id;
      const effectiveRevisionLanes = revisionContextRef.current.lanes ?? [];
      const fallbackSessionId = coerceString(eventData.session_id ?? data.session_id);
      if (fallbackSessionId) {
        persistSessionId(fallbackSessionId);
      }
      if (rawThoughtId && isThinkingEvent) {
        if (seenThoughtIdsRef.current.has(rawThoughtId)) {
          return;
        }
        seenThoughtIdsRef.current.add(rawThoughtId);
      }

      // For lightweight events, extract step and timing info from top level
      const stepInfo = {
        step: data.step || eventData.step,
        ts: data.ts || eventData.ts,
        elapsed_ms: data.elapsed_ms || eventData.elapsed_ms,
        event: typeof eventType === 'string' ? eventType : undefined,
      };
      const normalizedStepName =
        typeof stepInfo.step === 'string' ? (stepInfo.step as string).toLowerCase() : '';
      if (normalizedStepName && normalizedStepName.startsWith('fresh_')) {
        const freshMatch = normalizedStepName.match(/^fresh_([a-z0-9]+)_(started|completed|failed)$/);
        if (freshMatch) {
          const [, laneKey, statusKey] = freshMatch;
          const reasoningEffortValue =
            coerceString(eventData.reasoning_effort ?? data.reasoning_effort) ?? undefined;
          const reasonValue = coerceString(eventData.reason ?? data.reason) ?? undefined;
          setFreshLaneStates((prev) => {
            const existing = prev[laneKey];
            const nextState: FreshLaneStatus = {
              lane: laneKey,
              status: statusKey as FreshLaneStatus['status'],
              ts: typeof stepInfo.ts === 'string' ? stepInfo.ts : undefined,
              reasoningEffort: reasoningEffortValue,
              reason: reasonValue,
            };
            if (
              existing &&
              existing.status === nextState.status &&
              existing.ts === nextState.ts &&
              existing.reason === nextState.reason
            ) {
              return prev;
            }

            return {
              ...prev,
              [laneKey]: nextState,
            };
          });
        }
      }
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
        coerceFlowMode(data.mode) ??
        coerceFlowMode((data as any)?.flow_mode) ??
        coerceFlowMode(eventData.mode) ??
        coerceFlowMode((eventData as any)?.flow_mode);
      const resolvedFlowMode: FlowMode = flowModeValue ?? telemetryFlowModeRef.current ?? flow;
      if (flowModeValue && flowModeValue !== telemetryFlowModeRef.current) {
        telemetryFlowModeRef.current = flowModeValue;
        setTelemetryFlowMode(flowModeValue);
      }
      const toolGroup: string | undefined =
        typeof data.tool_group === 'string'
          ? data.tool_group
          : typeof eventData.tool_group === 'string'
            ? eventData.tool_group
            : undefined;
      const laneFromEvent = resolveLane(
        eventData,
        eventData?.metadata,
        eventData?.details,
        data,
        (eventData as any)?.telemetry_step,
      );
      const reusedFlag = resolveReusedFlag(eventData, eventData?.metadata, eventData?.details, data);

      const suppressedRevisionSteps = new Set([
        'classification',
        'intent_detection',
        'clarification',
        'schema_validation',
        'plan_and_select_template',
        'sql_generator',
        'sql_compilation',
        'sql_validation',
        'sql_executor',
        'sql_lane',
      ]);

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
        if (revisionModeRef.current !== 'none' && suppressedRevisionSteps.has(stepId)) {
          return;
        }
        const enrichedDetails =
          details ||
          sequence !== undefined ||
          parallelGroup !== undefined ||
          scheduleStage !== undefined ||
          resolvedFlowMode
            ? {
                ...(details ?? {}),
                sequence,
                parallelGroup,
                scheduleStage,
                flowMode: resolvedFlowMode,
                lane: overrides?.lane ?? laneFromEvent,
                reused: overrides?.reused ?? reusedFlag,
                finalAnswerOnly: overrides?.finalAnswerOnly,
                missingComponents: overrides?.missingComponents,
                followUpRoute: overrides?.followUpRoute,
                analysisAvailable: overrides?.analysisAvailable,
              }
            : details;
        stepsHook.updateStepStatus(
          stepId,
          status,
          thinking,
          enrichedDetails,
          elapsed,
          ts,
          sequence,
          parallelGroup,
          scheduleStage,
          resolvedFlowMode,
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

      /*
      Function: upsertAgentToolStep — called from agent tool SSE handlers to
      materialize one ProcessStep per tool_call_id with enriched metadata so the
      ProcessPanel ledger can display specialist, guardrail, retry, and cache
      badges that match the backend receipts.
      */
      const upsertAgentToolStep = (
        toolCall: Record<string, any>,
        status: ProcessStep['status'],
        summary: string[],
        detailOverrides?: Record<string, any>,
        extras?: {
          lane?: string;
          reused?: boolean;
          guardrail?: Record<string, any>;
          toolCallId?: string;
          specialistRole?: string;
          specialistLabel?: string;
          schemaVersion?: string;
          retryCount?: number;
          cacheAgeSeconds?: number;
          cacheSource?: string;
          fastPathLatencyMs?: number;
          displayName?: string;
        },
        eventTimestamp?: string,
      ) => {
        const toolCallId =
          extras?.toolCallId ??
          coerceString(toolCall.id) ??
          coerceString((toolCall as any).tool_call_id) ??
          coerceString((toolCall as any).call_id) ??
          `${toolCall.name ?? 'agent_tool'}-${sequence ?? Date.now()}`;
        const metadata = (toolCall.metadata ?? {}) as Record<string, any>;
        stepsHook.updateStepStatus(
          toolCallId,
          status,
          summary,
          {
            ...detailOverrides,
            tool_call: toolCall,
            metadata,
          },
          stepInfo.elapsed_ms,
          eventTimestamp ?? stepInfo.ts,
          sequence,
          parallelGroup,
          scheduleStage,
          resolvedFlowMode,
          {
            lane: extras?.lane ?? resolveLane(toolCall, metadata, { lane: laneFromEvent }) ?? laneFromEvent,
            reused: extras?.reused ?? resolveReusedFlag(toolCall, metadata, eventData, data),
            guardrail: extras?.guardrail,
            toolCallId,
            specialistRole: extras?.specialistRole,
            specialistLabel: extras?.specialistLabel,
            schemaVersion: extras?.schemaVersion,
            retryCount: extras?.retryCount,
            cacheAgeSeconds: extras?.cacheAgeSeconds,
            cacheSource: extras?.cacheSource,
            fastPathLatencyMs: extras?.fastPathLatencyMs,
            displayName: extras?.displayName,
          },
        );
      };

      if (eventData.specialist_card) {
        const normalizedCard = normalizeSpecialistCard(eventData.specialist_card, stepInfo.ts);
        if (normalizedCard) {
          const mergedCard: SpecialistCard = {
            ...normalizedCard,
            revisionId: normalizedCard.revisionId ?? effectiveRevisionId,
            revision: normalizedCard.revision ?? (isRevisionEvent || Boolean(effectiveRevisionId)),
            revisionEvent: normalizedCard.revisionEvent ?? isRevisionEvent,
            lane: normalizedCard.lane ?? laneFromEvent ?? normalizedCard.lane,
          };
          mergedCard.payloadHash = mergedCard.payloadHash ?? analyticsUtils.computeCardPayloadHash(mergedCard);
          upsertSpecialistCard(mergedCard);
        }
      }

      switch (eventType) {
        case 'session_started':
          {
            const nextSessionId = coerceString(eventData.session_id);
            persistSessionId(nextSessionId);
          }
          break;
        case 'revision_request': {
          const normalizedLanes = effectiveRevisionLanes.length
            ? effectiveRevisionLanes
            : Array.isArray(eventData.lanes)
              ? (eventData.lanes as unknown[])
                .map((lane) => (typeof lane === 'string' ? lane.toLowerCase() : ''))
                .filter((lane): lane is string => lane.length > 0)
              : [];
          revisionContextRef.current = {
            id: effectiveRevisionId ?? revisionContextRef.current.id,
            lanes: normalizedLanes,
            focus: revisionContextRef.current.focus,
          };
          if (normalizedLanes.length === 1) {
            const lane = normalizedLanes[0] === 'web' ? 'analysis' : normalizedLanes[0] === 'stock' ? 'market' : normalizedLanes[0];
            if (lane === 'chart' || lane === 'analysis' || lane === 'market') {
              setRevisionMode(lane);
              revisionModeRef.current = lane;
            } else {
              setRevisionMode('mixed');
              revisionModeRef.current = revisionModeRef.current === 'none' ? 'mixed' : revisionModeRef.current;
            }
          } else if (normalizedLanes.length > 1) {
            setRevisionMode('mixed');
            revisionModeRef.current = 'mixed';
          } else if (revisionModeRef.current === 'none') {
            setRevisionMode('mixed');
            revisionModeRef.current = 'mixed';
          }
          if (normalizedLanes.length) {
            streamHook.setCurrentStatus(`Revision requested: ${normalizedLanes.join(', ')}`);
          }
          break;
        }


        case 'status':
        case 'progress':
          // Handle both old 'status' and new 'progress' event types
          const deltaSnippet = coerceString((eventData as any)?.delta_text ?? (data as any)?.delta_text);
          const statusMessage = deltaSnippet ?? eventData.message ?? data.message ?? '';
          const bannerPayload = eventData.banner || data.banner;
          if (stepInfo.step === 'follow_up_route' || bannerPayload) {
            const route = coerceString(bannerPayload?.route ?? eventData.route ?? data.route) ?? 'full_pipeline';
            const reasonKey = coerceString(bannerPayload?.reason ?? eventData.reason);
            const copyKey = reasonKey && analyticsUtils.FOLLOW_UP_BANNER_COPY[reasonKey] ? reasonKey : route;
            const copy =
              analyticsUtils.FOLLOW_UP_BANNER_COPY[copyKey] ?? analyticsUtils.FOLLOW_UP_BANNER_COPY.full_pipeline;
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
              flowMode: resolvedFlowMode,
              finalAnswerOnly: finalAnswerOnly ?? undefined,
              missingComponents,
              analysisAvailable,
              summary: summaryCopy,
              reason: reasonKey ?? undefined,
            };
            const normalizedQuestions =
              normalizeQuestionBundle(
                bannerPayload?.questions ??
                bannerPayload?.revision_questions ??
                eventData.revision_questions ??
                data.revision_questions,
              ) ?? undefined;
            if (normalizedQuestions) {
              banner.questions = normalizedQuestions;
              workflowDataRef.current.revisionQuestions = normalizedQuestions;
              const laneFromRoute =
                route.startsWith('chart')
                  ? 'chart'
                  : route.includes('analysis') || route.includes('narrative')
                    ? 'analysis'
                    : undefined;
              emitRevisionQuestionCard(
                normalizedQuestions,
                laneFromRoute,
                effectiveRevisionId ?? revisionContextRef.current.id ?? null,
              );
            }
            setFollowUpBanner(banner);
            workflowDataRef.current.followUpBanner = banner;
            refreshResultMessage();
            const allowBannerThought = markThoughtIfNew('follow_up_route', rawThoughtId);
            const thinkingLogs = allowBannerThought
              ? banner.message
                ? [banner.message]
                : statusMessage
                  ? [statusMessage]
                  : []
              : [];
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
            const normalizedStep =
              stepInfo.step === 'web_search' ? 'web_research_agent' : stepInfo.step;
            const allowThoughtLogs = markThoughtIfNew(normalizedStep, rawThoughtId);
            const thinkingLogs: string[] = [];
            if (allowThoughtLogs && isThinkingEvent && statusMessage) {
              thinkingLogs.push(statusMessage);
            }
            if (allowThoughtLogs && eventData.code) {
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
            updateStep(
              normalizedStep,
              'in_progress',
              thinkingLogs,
              detailPayload,
              stepInfo.elapsed_ms,
              stepInfo.ts,
            );
          }
          break;

        case 'complete':
          if (stepInfo.step) {
            const summaryText = coerceString(eventData.summary) ?? coerceString(data.summary);
            const thinkingLogs = summaryText ? [summaryText] : [];
            stepsHook.updateStepStatus(stepInfo.step, 'completed', thinkingLogs, eventData, stepInfo.elapsed_ms, stepInfo.ts);
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

        case 'baseline_still_streaming': {
          const bannerPayload = eventData.banner || data.banner || {};
          const pendingComponents = Array.isArray(eventData.pending_components)
            ? (eventData.pending_components as unknown[])
              .map((component) => coerceString(component))
              .filter((component): component is string => Boolean(component))
            : Array.isArray(bannerPayload?.pending_components)
              ? (bannerPayload.pending_components as unknown[])
                .map((component) => coerceString(component))
                .filter((component): component is string => Boolean(component))
              : undefined;
          const route = 'baseline_still_streaming';
          const banner: FollowUpBanner = {
            title: coerceString(bannerPayload?.title) ?? 'Baseline Still Running',
            message:
              coerceString(bannerPayload?.message) ??
              'Waiting for the current analysis run to seal required inputs before revisions can start.',
            route,
            flowMode: resolvedFlowMode,
            missingComponents: pendingComponents,
          };
          setFollowUpBanner(banner);
          workflowDataRef.current.followUpBanner = banner;
          streamHook.setCurrentStatus(banner.message);
          const thinkingLogs = banner.message ? [banner.message] : [];
          stepsHook.updateStepStatus(
            'follow_up_route',
            'in_progress',
            thinkingLogs,
            { banner },
            stepInfo.elapsed_ms,
            stepInfo.ts,
            undefined,
            undefined,
            undefined,
            resolvedFlowMode,
            {
              followUpRoute: route,
              missingComponents: pendingComponents,
            },
          );
          break;
        }

        case 'follow_up_route': {
          const route = coerceString(eventData.route) ?? 'full_pipeline';
          const agenticFlag =
            coerceBoolean(eventData.agentic_revision ?? data.agentic_revision) ?? false;
          setAgenticRevisionActive(agenticFlag);
          applyAgentEvidenceUpdate(() => null);
          const guardrailPayload =
            (eventData.guardrail as Record<string, any> | undefined) ?? undefined;
          if (guardrailPayload) {
            workflowDataRef.current.followUpGuardrail = guardrailPayload;
          }
          const bannerPayload = (eventData.banner as Record<string, any> | undefined) ?? undefined;
          const reasonKey = coerceString(bannerPayload?.reason ?? eventData.reason) ?? undefined;
          const bannerKey =
            reasonKey && analyticsUtils.FOLLOW_UP_BANNER_COPY[reasonKey] ? reasonKey : route;
          const copy =
            (bannerPayload?.title && bannerPayload?.message
              ? { title: bannerPayload.title, message: bannerPayload.message }
              : analyticsUtils.FOLLOW_UP_BANNER_COPY[bannerKey]) ?? analyticsUtils.FOLLOW_UP_BANNER_COPY.full_pipeline;
          const normalizedLanes = Array.isArray(eventData.lanes)
            ? (eventData.lanes as unknown[])
              .map((lane) => (typeof lane === 'string' ? lane.toLowerCase() : ''))
              .filter((lane): lane is string => Boolean(lane))
            : undefined;
          const banner: FollowUpBanner = {
            title: copy.title,
            message: copy.message,
            route,
            reason: reasonKey ?? undefined,
            lanes: normalizedLanes,
          };
          if (guardrailPayload) {
            banner.guardrail = guardrailPayload;
          }
          if (normalizedLanes && normalizedLanes.length) {
            workflowDataRef.current.followUpLanes = normalizedLanes;
          }
          const questionBundle =
            normalizeQuestionBundle(
              eventData.revision_questions ?? eventData.questions ?? (eventData.banner as any)?.questions,
            ) ?? undefined;
          if (questionBundle) {
            banner.questions = questionBundle;
            workflowDataRef.current.revisionQuestions = questionBundle;
            const laneFromBanner =
              coerceString(eventData.selected_lane) ??
              (normalizedLanes && normalizedLanes.length === 1 ? normalizedLanes[0] : undefined);
            emitRevisionQuestionCard(
              questionBundle,
              laneFromBanner,
              effectiveRevisionId ?? revisionContextRef.current.id ?? null,
            );
          }
          setFollowUpBanner(banner);
          const rawFocus =
            coerceString((eventData as Record<string, unknown>)?.analysis_focus) ??
            coerceString((eventData as Record<string, unknown>)?.requested_focus) ??
            coerceString((eventData as Record<string, unknown>)?.focus);
          const trimmedFocus =
            rawFocus && typeof rawFocus === 'string' && rawFocus.trim().length ? rawFocus.trim() : undefined;
          const pendingFocus =
            trimmedFocus ??
            (route === 'analysis_only' || route === 'narrative_only'
              ? pendingRevisionFocusRef.current
              : undefined);
          if (normalizedLanes && normalizedLanes.length) {
            revisionContextRef.current = {
              id: revisionContextRef.current.id,
              lanes: normalizedLanes,
              focus: pendingFocus ?? revisionContextRef.current.focus,
            };
          }
          switch (route) {
            case 'full_pipeline': {
              setRevisionMode('none');
              revisionModeRef.current = 'none';
              revisionContextRef.current.focus = undefined;
              workflowDataRef.current.revisionFocus = null;
              pendingRevisionFocusRef.current = undefined;
              break;
            }
            case 'analysis_only':
            case 'narrative_only': {
              setRevisionMode('analysis');
              revisionModeRef.current = 'analysis';
              revisionContextRef.current.focus =
                pendingFocus ?? revisionContextRef.current.focus ?? pendingRevisionFocusRef.current;
              workflowDataRef.current.revisionFocus = revisionContextRef.current.focus ?? null;
              pendingRevisionFocusRef.current = undefined;
              break;
            }
            case 'market_only': {
              setRevisionMode('market');
              revisionModeRef.current = 'market';
              workflowDataRef.current.revisionFocus = null;
              pendingRevisionFocusRef.current = undefined;
              break;
            }
            case 'chart_revision':
            case 'chart_only': {
              setRevisionMode('chart');
              revisionModeRef.current = 'chart';
              workflowDataRef.current.revisionFocus = null;
              pendingRevisionFocusRef.current = undefined;
              break;
            }
            case 'mixed_revision': {
              setRevisionMode('mixed');
              revisionModeRef.current = 'mixed';
              workflowDataRef.current.revisionFocus =
                normalizedLanes?.includes('analysis') ? pendingFocus ?? revisionContextRef.current.focus ?? null : null;
              pendingRevisionFocusRef.current = undefined;
              break;
            }
            case 'reuse_sql': {
              setRevisionMode((prev) => (prev === 'none' ? 'mixed' : prev));
              if (revisionModeRef.current === 'none') {
                revisionModeRef.current = 'mixed';
              }
              workflowDataRef.current.revisionFocus = null;
              pendingRevisionFocusRef.current = undefined;
              break;
            }
            case 'cannot_revise': {
              setRevisionMode('none');
              revisionModeRef.current = 'none';
              workflowDataRef.current.revisionFocus = null;
              pendingRevisionFocusRef.current = undefined;
              break;
            }
            default: {
              if (route !== 'full_pipeline') {
                setRevisionMode((prev) => (prev === 'none' ? 'mixed' : prev));
                if (revisionModeRef.current === 'none') {
                  revisionModeRef.current = 'mixed';
                }
              }
              if (route !== 'analysis_only' && route !== 'narrative_only') {
                workflowDataRef.current.revisionFocus = null;
                pendingRevisionFocusRef.current = undefined;
              }
              break;
            }
          }
          workflowDataRef.current.followUpBanner = banner;
          refreshResultMessage();
          const thinking = [`Route selected: ${route.replace(/[_-]/g, ' ')}`];
          if (guardrailPayload?.status) {
            thinking.push(`Guardrail: ${guardrailPayload.status}`);
          }
          if (normalizedLanes && normalizedLanes.length) {
            thinking.push(`Revision lanes: ${normalizedLanes.join(', ')}`);
          }
          const stepDetails: Record<string, any> = { banner };
          if (guardrailPayload) {
            stepDetails.guardrail = guardrailPayload;
          }
          if (normalizedLanes && normalizedLanes.length) {
            stepDetails.lanes = normalizedLanes;
          }
          updateStep(
            'follow_up_route',
            'in_progress',
            thinking,
            stepDetails,
            stepInfo.elapsed_ms,
            stepInfo.ts,
          );
          streamHook.setCurrentStatus(hasExplicitResultContentRef.current ? '' : copy.message);
          break;
        }

        case 'clarification_request': {
          const request = eventData as ClarifyRequest;
          if (request.request_id && request.request_id === lastClarificationRequestIdRef.current) {
            break;
          }
          lastClarificationRequestIdRef.current = request.request_id ?? null;
          console.log('?? [DEBUG] Received clarification_request:', request);
          setPendingClarification(request);
          upsertSlotStatus(request.slot, {
            status: 'missing',
            reason: request.reason,
            suggestions: request.options,
            allow_custom: request.allow_custom,
          });
          setSlotFollowups((prev) => {
            const filtered = prev.filter((item) => item.request_id !== request.request_id);
            return [...filtered, request];
          });
          updateStep('clarification', 'in_progress', [request.question], { request });
          streamHook.setCurrentStatus(`Clarification needed: ${request.question}`);
          const clarificationMessage = {
            type: 'clarification' as const,
            content: request.question,
            clarifications: [request],
          };
          console.log('?? [DEBUG] Adding clarification message:', clarificationMessage);
          addChatMessage(clarificationMessage);
          break;
        }

        case 'clarification_ack': {
          setPendingClarification(null);
          setSlotFollowups((prev) => prev.filter((item) => item.request_id !== eventData.request_id));
          lastClarificationMissingRef.current = null;
          lastClarificationRequestIdRef.current = null;
          if (eventData.slot) {
            if (eventData.slot_status) {
              const ackStatus = normalizeSlotStatuses({ [eventData.slot]: eventData.slot_status });
              const statusPayload = ackStatus[eventData.slot];
              if (statusPayload) {
                upsertSlotStatus(eventData.slot, statusPayload);
              }
            } else {
              upsertSlotStatus(eventData.slot, { status: 'filled', value: eventData.answer });
            }
          }
          const ackSlot = typeof eventData.slot === 'string' ? eventData.slot : 'answer';
          if (ackSlot === 'timeframe') {
            const statusValue =
              (eventData.slot_status as any)?.value ??
              (eventData.slot_status as any)?.display ??
              (eventData.slot_status as any)?.label ??
              eventData.slot_status;
            const granularityCandidate =
              resolveGranularityCandidate(statusValue) ??
              resolveGranularityCandidate(eventData.answer);
            commitRequestedGranularity(granularityCandidate);
          }
          const pendingEcho = lastClarificationEchoRef.current;
          const ackEcho = formatClarificationEcho(ackSlot, eventData.answer);
          const isDuplicate =
            Boolean(ackEcho) &&
            Boolean(
              pendingEcho &&
              pendingEcho.slot === ackSlot &&
              pendingEcho.content === ackEcho
            );
          if (!isDuplicate) {
            if (ackEcho) {
              addChatMessage({
                type: 'user',
                content: ackEcho,
              });
            } else {
              const fallback = coerceClarificationValue(eventData.answer);
              const trimmedFallback = fallback?.trim();
              if (trimmedFallback) {
                const label = analyticsUtils.formatSlotLabel(ackSlot);
                const display = trimmedFallback.toLowerCase().startsWith(label.toLowerCase())
                  ? trimmedFallback
                  : `${label}: ${trimmedFallback}`;
                addChatMessage({
                  type: 'user',
                  content: display,
                });
              }
            }
          }
          lastClarificationEchoRef.current = null;
          stepsHook.updateStepStatus('clarification', 'in_progress', ['Processing your answer...'], {
            slot: eventData.slot,
            answer: eventData.answer,
          });
          streamHook.setCurrentStatus('Processing your clarification answer');
          break;
        }

        case 'plan_built': {
          // Combined planning step for streamlined agent flow
          // Handle both old (eventData.plan) and new (simplified) formats
          const planData =
            eventData.plan || {
              metrics_count: eventData.metrics_count,
              granularity: eventData.granularity,
              comparison: eventData.comparison,
              timeframe: eventData.timeframe,
            };
          const candidateGranularity =
            resolveGranularityCandidate((planData as any)?.granularity) ??
            resolveGranularityCandidate((planData as any)?.timeframe) ??
            resolveGranularityCandidate(eventData.granularity) ??
            resolveGranularityCandidate(eventData.timeframe);
          commitRequestedGranularity(candidateGranularity);
          stepsHook.updateStepStatus(
            'plan_and_select_template',
            'in_progress',
            ['Plan built'],
            { plan: planData },
            stepInfo.elapsed_ms,
          );
          break;
        }

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
            stepsHook.updateStepStatus(
              'sql_lane',
              'in_progress',
              ['SQL lane running'],
              {
                attempt,
                template_used: eventData.template_used,
                template_fallback: eventData.template_fallback,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts,
              sequence,
              parallelGroup,
              scheduleStage,
              resolvedFlowMode,
              { lane: 'sql' }
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
          stepsHook.updateStepStatus(
            'sql_lane',
            'in_progress',
            [
              eventData.row_count != null
                ? `Rows retrieved: ${eventData.row_count}`
                : 'SQL execution completed',
            ],
            executionData,
            stepInfo.elapsed_ms,
            stepInfo.ts,
            sequence,
            parallelGroup,
            scheduleStage,
            resolvedFlowMode,
            { lane: 'sql' }
          );
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
          } catch { }
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
          stepsHook.updateStepStatus(
            'sql_lane',
            'completed',
            sqlPreview,
            eventData,
            stepInfo.elapsed_ms,
            stepInfo.ts,
            sequence,
            parallelGroup,
            scheduleStage,
            resolvedFlowMode,
            { lane: 'sql', reused: Boolean(eventData.reused) }
          );
          emitResultOnce();
          if (isRevisionEvent) {
            markRevisionMode('chart');
          }
          refreshResultMessage();
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
          if (isRevisionEvent) {
            markRevisionMode('chart');
            appendResultSnapshot({
              content: 'Revision: Chart updated',
              analysis: null,
              chartSpec: normalizedChartSpec ?? workflowDataRef.current.chartSpec ?? null,
              sqlQuery: workflowDataRef.current.sqlQuery ?? null,
              dataSample: null,
              stockWidgetConfig: null,
              toolFanoutManifest: [],
              toolFanoutResults: [],
              webSearch: null,
              replacePriorResult: true,
              pruneFreshResults: true,
              revisionId: revisionContextRef.current.id ?? null,
              revisionFocus: workflowDataRef.current.revisionFocus ?? revisionContextRef.current.focus ?? null,
            });
          }
          emitResultOnce();
          refreshResultMessage();
          break;
        }

        case 'stock_ready': {
          if (eventData.stock_widget) {
            scheduleProgressiveUpdate({ stockWidget: eventData.stock_widget as StockWidgetConfig });
            const widgetPayload = eventData.stock_widget as StockWidgetConfig;
            setStockWidget(widgetPayload);
            workflowDataRef.current.stockWidget = widgetPayload;
            refreshResultMessage();
          }
          stepsHook.updateStepStatus(
            'market_lane',
            'completed',
            ['Market data ready'],
            eventData,
            stepInfo.elapsed_ms,
            stepInfo.ts,
            sequence,
            parallelGroup,
            scheduleStage,
            resolvedFlowMode,
            { lane: eventData.lane ?? 'market', reused: Boolean(eventData.reused) }
          );
          updateStep('tool_execution', 'completed', ['Stock widget ready'], eventData, stepInfo.elapsed_ms, stepInfo.ts);
          emitResultOnce();
          if (isRevisionEvent) {
            markRevisionMode('market');
          }
          refreshResultMessage();
          break;
        }

        case 'web_ready': {
          const webContext = normalizeWebContext(eventData.web_context || eventData);
          if (webContext) {
            scheduleProgressiveUpdate({ webSearch: webContext });
            workflowDataRef.current.webSearch = webContext;
            if (webContext.questions) {
              workflowDataRef.current.webQuestions = webContext.questions;
            }
            refreshResultMessage();
          }
          stepsHook.updateStepStatus(
            'web_lane',
            'completed',
            ['Web research ready'],
            eventData,
            stepInfo.elapsed_ms,
            stepInfo.ts,
            sequence,
            parallelGroup,
            scheduleStage,
            resolvedFlowMode,
            { lane: eventData.lane ?? 'web', reused: Boolean(eventData.reused) }
          );
          updateStep('web_research_agent', 'completed', ['Web context ready'], eventData, stepInfo.elapsed_ms, stepInfo.ts);
          emitResultOnce();
          if (isRevisionEvent) {
            markRevisionMode('analysis');
          }
          refreshResultMessage();
          const fromCache = coerceBoolean(eventData.from_cache ?? data.from_cache);
          if (fromCache && agenticRevisionActive && !agentEvidenceRef.current) {
            const fallbackReason = coerceString(eventData.reason) ?? 'cached_revision';
            applyAgentEvidenceUpdate(() => ({ status: 'agent_fallback', reason: fallbackReason }));
          }
          break;
        }

        case 'analysis_ready': {
          const isFirstReady = !analysisReadyEmittedRef.current;
          analysisReadyEmittedRef.current = true;
          finalResultMergedRef.current = false;
          if (typeof eventData.analysis === 'string') {
            scheduleProgressiveUpdate({ analysis: eventData.analysis });
          }
          const readySources = parseAnalysisSources(
            (eventData.analysis_sources && typeof eventData.analysis_sources === 'object' && eventData.analysis_sources) ??
            (typeof eventData.analysis === 'object' && eventData.analysis !== null
              ? (eventData.analysis as any).analysis_sources ?? (eventData.analysis as any).sources
              : undefined)
          );
          if (readySources) {
            applyAnalysisSourcesUpdate(readySources);
          }
          const readyQuestions =
            normalizeQuestionBundle(eventData.questions ?? eventData.revision_questions ?? data.questions) ?? undefined;
          if (readyQuestions) {
            workflowDataRef.current.revisionQuestions = readyQuestions;
            emitRevisionQuestionCard(
              readyQuestions,
              coerceString(eventData.selected_lane),
              effectiveRevisionId ?? revisionContextRef.current.id ?? null,
            );
          }
          updateStep('analysis_generation', 'completed', ['Analysis ready'], eventData, stepInfo.elapsed_ms, stepInfo.ts);
          if (isFirstReady) {
            emitResultOnce();
          }
          if (isRevisionEvent) {
            markRevisionMode('analysis');
          }
          refreshResultMessage();
          break;
        }

        case 'revision_agent_disabled': {
          const laneLabel = analyticsUtils.formatLaneName(coerceString(eventData.lane) || 'analysis');
          const reasonText = coerceString(eventData.reason) || 'agent runtime unavailable';
          updateAgentCoordination(
            [`${laneLabel}: ${reasonText}`],
            'error',
            { ts: stepInfo.ts, elapsed_ms: stepInfo.elapsed_ms, sequence },
          );
          stepsHook.updateStepStatus(
            'agent_coordination',
            'error',
            [`Revision blocked: ${reasonText}`],
            eventData,
            stepInfo.elapsed_ms,
            stepInfo.ts,
          );
          const disabledBanner: FollowUpBanner = {
            title: 'Agent Runtime Disabled',
            message: 'Switch to a deterministic revision or rerun the full workflow once the agent service is restored.',
            route: 'cannot_revise',
          };
          setFollowUpBanner(disabledBanner);
          workflowDataRef.current.followUpBanner = disabledBanner;
          refreshResultMessage();
          applyAgentEvidenceUpdate(() => ({ status: 'agent_disabled', reason: reasonText }));
          break;
        }

        case 'agent_coordination': {
          const laneLabel = analyticsUtils.formatLaneName(coerceString(eventData.lane) || 'analysis');
          const reasonText = coerceString(eventData.reason);
          const summaryMessages = reasonText
            ? [`${laneLabel}: ${reasonText}`]
            : [`${laneLabel}: coordinating revisions`];
          updateAgentCoordination(summaryMessages, undefined, {
            ts: stepInfo.ts,
            elapsed_ms: stepInfo.elapsed_ms,
            sequence,
          });
          const coordinationQuestions =
            normalizeQuestionBundle(eventData.questions ?? data.questions) ?? undefined;
          if (coordinationQuestions) {
            workflowDataRef.current.revisionQuestions = coordinationQuestions;
          }
          applyAgentEvidenceUpdate(() => ({ status: 'agent_run', turns: [] }));
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
            const msg = `Chart complete${chartType ? ` (type: ${chartType})` : ''}${seriesCount != null ? `, series: ${seriesCount}` : ''}`;
            updateAgentCoordination([msg]);
          } catch { }
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
              flowMode: resolvedFlowMode,
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
            const msg = `Chart generated${chartType ? ` (type: ${chartType})` : ''}${seriesCount != null ? `, series: ${seriesCount}` : ''}`;
            updateAgentCoordination([msg]);
          } catch { }
          break;
        }

        case 'chart_patch': {
          const normalizedStatus =
            typeof eventData?.status === 'string' ? eventData.status.toLowerCase() : '';
          const hasOps = Array.isArray(eventData?.ops) && eventData.ops.length > 0;

          try {
            let opLines: string[] = [];
            let patchedChartSpec: any = null;
            if (hasOps) {
              const baseCandidate =
                (pendingUpdatesRef.current.chartSpec && typeof pendingUpdatesRef.current.chartSpec === 'object'
                  ? pendingUpdatesRef.current.chartSpec
                  : undefined) ??
                (workflowDataRef.current.chartSpec && typeof workflowDataRef.current.chartSpec === 'object'
                  ? workflowDataRef.current.chartSpec
                  : undefined) ??
                (eventData?.chart_spec && typeof eventData.chart_spec === 'object'
                  ? eventData.chart_spec
                  : undefined);

              if (baseCandidate && typeof baseCandidate === 'object') {
                const next = applyChartOps(baseCandidate, eventData);
                const annotatedNext = applyGranularityToChartSpec(next);
                workflowDataRef.current.chartSpec = annotatedNext;
                pendingUpdatesRef.current.chartSpec = annotatedNext;
                patchedChartSpec = annotatedNext;
                setChartSpec(annotatedNext);
              }

              opLines = eventData.ops.map((op: any) => {
                try {
                  switch (op.op) {
                    case 'set_chart_type':
                      return `Chart type -> ${op.value}`;
                    case 'set_stack':
                      return `Stacking -> ${op.stack ? op.mode || 'normal' : 'off'}`;
                    case 'toggle_series':
                      return `Toggle series (${op.visible ? 'show' : 'hide'}): ${Array.isArray(op.names) ? op.names.join(', ') : ''
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

            const resolvedChartSpecRaw =
              patchedChartSpec && typeof patchedChartSpec === 'object'
                ? patchedChartSpec
                : eventData?.chart_spec && typeof eventData.chart_spec === 'object'
                  ? eventData.chart_spec
                  : workflowDataRef.current.chartSpec && typeof workflowDataRef.current.chartSpec === 'object'
                    ? workflowDataRef.current.chartSpec
                    : undefined;
            const resolvedChartSpec = resolvedChartSpecRaw
              ? applyGranularityToChartSpec(resolvedChartSpecRaw)
              : undefined;

            const stepDetails: Record<string, any> = {
              patch: eventData,
              status: normalizedStatus || (hasOps ? 'applied' : undefined),
            };

            if (stepStatus !== 'error' && resolvedChartSpec) {
              stepDetails.chart_spec = resolvedChartSpec;
            }

            stepsHook.updateStepStatus(
              'chart_revision',
              stepStatus,
              statusLines.length ? statusLines : ['Chart revision received'],
              stepDetails,
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
              if (resolvedChartSpecRaw) {
                scheduleProgressiveUpdate({ chartSpec: resolvedChartSpecRaw });
              }

              streamHook.setCurrentStatus('Chart revision applied');
              // Drop previously rendered attachments before reusing the existing result bubble for the revision.
              setAnalysis('');
              workflowDataRef.current.analysis = '';
              setAnalysisOverview(null);
              workflowDataRef.current.analysisOverview = null;
              setAnalysisSources(null);
              workflowDataRef.current.analysisSources = null;
              setProgressiveAnalysis('');
              setProgressiveText('');
              setStreamingText('');
              workflowDataRef.current.progressiveAnalysis = '';
              workflowDataRef.current.progressiveText = '';
              workflowDataRef.current.streamingText = '';
              setSqlQuery('');
              workflowDataRef.current.sqlQuery = '';
              setDataSample(null);
              workflowDataRef.current.dataSample = null;
              setStockWidget(null);
              workflowDataRef.current.stockWidget = null;
              setWebSearch(null);
              workflowDataRef.current.webSearch = null;
              workflowDataRef.current.toolFanoutManifest = [];
              workflowDataRef.current.toolFanoutResults = [];
              setSpecialistCards([]);
              workflowDataRef.current.specialistCards = [];
              workflowDataRef.current.latencyGuardrail = null;
              setFollowUpBanner(null);
              workflowDataRef.current.followUpBanner = null;
              emitResultOnce();
              const revisionLines = opLines.length ? opLines : ['Applied chart revision'];
              const revisionSummary =
                ['Revision: Chart updated', ...revisionLines.map((line) => `- ${line}`)].join('\n');

              refreshResultMessage({
                content: revisionSummary,
                chartSpec: patchedChartSpec ?? workflowDataRef.current.chartSpec,
                analysis: '',
                analysisOverview: null,
                sqlQuery: null,
                dataSample: null,
                stockWidgetConfig: null,
                toolFanoutManifest: [],
                toolFanoutResults: [],
                webSearch: null,
                specialistCards: [],
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
          const revisionIdForSnapshot =
            effectiveRevisionId ?? coerceString(eventData?.revision_id ?? eventData?.revisionId);

          try {
            const updatedAnalysis =
              typeof eventData?.analysis === 'string'
                ? sanitizeStructuredText(eventData.analysis) ?? eventData.analysis
                : '';

            if (revisionApplied && updatedAnalysis) {
            const readyTopicStatus = coerceString(eventData.topic_status) ?? (topicProgress.pending === 0 ? 'ready' : 'pending');
            const shouldBufferAnalysis = readyTopicStatus !== 'ready' || (topicProgress.total > 0 && topicProgress.pending > 0);
            if (shouldBufferAnalysis) {
              pendingAnalysisBufferRef.current = updatedAnalysis;
            } else {
              setAnalysis(updatedAnalysis);
              workflowDataRef.current.analysis = updatedAnalysis;
              pendingAnalysisBufferRef.current = '';
            }
            if (shouldBufferAnalysis) {
              workflowDataRef.current.analysis = updatedAnalysis;
            }
            }
            if (revisionApplied) {
              analysisReadyEmittedRef.current = false;
              finalResultMergedRef.current = false;
            }

            const summaryLine =
              updatedAnalysis && revisionApplied
                ? `Analysis -> ${updatedAnalysis.length > 140
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
                analysis: updatedAnalysis,
                chartSpec: null,
                sqlQuery: null,
                dataSample: null,
                stockWidgetConfig: null,
                toolFanoutManifest: [],
                toolFanoutResults: [],
                specialistCards: [],
                replacePriorResult: true,
                pruneFreshResults: true,
                revisionId: revisionIdForSnapshot ?? null,
                revisionFocus:
                  workflowDataRef.current.revisionFocus ?? revisionContextRef.current.focus ?? null,
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

        case 'web_topics_pending': {
          const totalFromPayload =
            typeof eventData.total === 'number'
              ? eventData.total
              : Array.isArray(eventData.branches)
                ? eventData.branches.length
                : topicProgress.total || 0;
          const completedFromPayload =
            typeof eventData.completed === 'number' ? eventData.completed : 0;
          const pendingFromPayload =
            typeof eventData.pending === 'number'
              ? eventData.pending
              : Math.max(totalFromPayload - completedFromPayload, 0);
          const branches = normalizeTopicBranchPayload(eventData.branches, 'queued');
          setTopicProgress({
            total: totalFromPayload,
            completed: completedFromPayload,
            pending: pendingFromPayload,
            branches,
            pendingSince: eventData.ts ?? new Date().toISOString(),
            lastUpdated: eventData.ts ?? new Date().toISOString(),
            guardrailStatus: 'pending',
          });
          break;
        }
        case 'web_topics_branch': {
          const derivedStatus = coerceString(eventData.status)?.toLowerCase() === 'error' ? 'error' : 'ready';
          const normalizedBranch = normalizeTopicBranchPayload(
            [
              {
                id: eventData.branch ?? eventData.id,
                question_kind: eventData.question_kind,
                label: eventData.topic_label ?? eventData.label,
                status: derivedStatus,
                summary: eventData.summary,
              },
            ],
            derivedStatus as WebTopicBranchStatus,
          );
          const branchId = Object.keys(normalizedBranch)[0];
          if (!branchId) {
            break;
          }
          setTopicProgress((prev) => {
            const previousStatus = prev.branches[branchId]?.status;
            const nextBranches = { ...prev.branches, ...normalizedBranch };
            const totalTopics = prev.total || Math.max(Object.keys(nextBranches).length, 2);
            const alreadyCompleted = previousStatus && ['ready', 'error'].includes(previousStatus) ? 0 : 1;
            const completedCount = Math.min((prev.completed || 0) + alreadyCompleted, totalTopics);
            const pendingCount = Math.max(totalTopics - completedCount, 0);
            return {
              ...prev,
              total: totalTopics,
              completed: completedCount,
              pending: pendingCount,
              branches: nextBranches,
              lastUpdated: eventData.ts ?? new Date().toISOString(),
            };
          });
          break;
        }

        case 'web_topics_ready': {
          const readyBranches = normalizeTopicBranchPayload(eventData.branches, 'ready');
          setTopicProgress((prev) => {
            const derivedTotal = Object.keys(readyBranches).length || prev.total || 0;
            const totalFromPayload =
              typeof eventData.total === 'number' ? eventData.total : derivedTotal;
            const completedFromPayload =
              typeof eventData.completed === 'number' ? eventData.completed : totalFromPayload;
            const pendingFromPayload =
              typeof eventData.pending === 'number'
                ? eventData.pending
                : Math.max(totalFromPayload - completedFromPayload, 0);
            return {
              total: totalFromPayload,
              completed: completedFromPayload,
              pending: pendingFromPayload,
              branches: Object.keys(readyBranches).length ? readyBranches : prev.branches,
              pendingSince: prev.pendingSince,
              lastUpdated: eventData.ts ?? new Date().toISOString(),
              guardrailStatus: 'ready',
            };
          });
          const readyQuestions =
            normalizeQuestionBundle(eventData.questions ?? data.questions) ?? undefined;
          if (readyQuestions) {
            workflowDataRef.current.revisionQuestions = readyQuestions;
            emitRevisionQuestionCard(
              readyQuestions,
              coerceString(eventData.selected_lane),
              effectiveRevisionId ?? revisionContextRef.current.id ?? null,
            );
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
              refreshResultMessage();

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
              if (!resultSentRef.current) {
                emitResultOnce();
              }
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
              const normalizedAnalysis =
                sanitizeStructuredText(bundle.analysis) ?? bundle.analysis;
              scheduleProgressiveUpdate({ analysis: normalizedAnalysis });
              workflowDataRef.current.analysis = normalizedAnalysis;
            }
            if (bundle.chart_spec) {
              const annotatedBundleSpec = applyGranularityToChartSpec(bundle.chart_spec);
              bundle.chart_spec = annotatedBundleSpec;
              scheduleProgressiveUpdate({ chartSpec: annotatedBundleSpec });
              workflowDataRef.current.chartSpec = annotatedBundleSpec;
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
              refreshResultMessage();
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
            if ('analysis_bundle' in bundle) {
              const normalizedBundle = (bundle as any).analysis_bundle ?? null;
              scheduleProgressiveUpdate({ analysisBundle: normalizedBundle });
              workflowDataRef.current.analysisBundle = normalizedBundle;
            }
            refreshFanoutState();
            if (bundle.web_context) {
              const webContext = normalizeWebContext(bundle.web_context);
              if (webContext) {
                setWebSearch(webContext);
                workflowDataRef.current.webSearch = webContext;
                refreshResultMessage();
              }
            }
            if (bundle.analysis_overview && typeof bundle.analysis_overview === 'object') {
              const overview = parseAnalysisOverview(bundle.analysis_overview);
              if (overview) {
                setAnalysisOverview(overview);
                workflowDataRef.current.analysisOverview = overview;
                refreshResultMessage();
              }
            }
            const cohesiveSources = parseAnalysisSources(
              (bundle.analysis_sources && typeof bundle.analysis_sources === 'object' && bundle.analysis_sources) ||
              (bundle.analysis_overview && typeof bundle.analysis_overview === 'object' ? (bundle.analysis_overview as any).sources : undefined) ||
              (bundle.analysis && typeof bundle.analysis === 'object' ? (bundle.analysis as any).analysis_sources ?? (bundle.analysis as any).sources : undefined)
            );
            if (cohesiveSources) {
              applyAnalysisSourcesUpdate(cohesiveSources);
            }
            if (bundle.latency_guardrail) {
              const guardrail = bundle.latency_guardrail as LatencyGuardrail;
              setLatencyGuardrail(guardrail);
              workflowDataRef.current.latencyGuardrail = guardrail;
              refreshResultMessage();
            }
            if (bundle.banner) {
              const bannerData = bundle.banner as Record<string, any>;
              const route = coerceString(bannerData.route) ?? followUpBanner?.route ?? 'full_pipeline';
              const copy =
                analyticsUtils.FOLLOW_UP_BANNER_COPY[route] ?? analyticsUtils.FOLLOW_UP_BANNER_COPY.full_pipeline;
              const banner: FollowUpBanner = {
                title: coerceString(bannerData.title) ?? copy.title,
                message: coerceString(bannerData.message) ?? followUpBanner?.message ?? copy.message,
                route,
              };
              setFollowUpBanner(banner);
              workflowDataRef.current.followUpBanner = banner;
              refreshResultMessage();
            }
            finalResultMergedRef.current = true;

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
                analysis_sources: workflowDataRef.current.analysisSources,
                banner: workflowDataRef.current.followUpBanner,
                latency_guardrail: workflowDataRef.current.latencyGuardrail,
                parallelGroup,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts,
            );

            // Emit the result bubble exactly once; guard handles subsequent workflow_complete
            if (!isThinkingEvent) {
              emitResultOnce();
              refreshResultMessage();
            }
            finalResultMergedRef.current = true;
          }
          break;

        case 'analysis_complete':
          // Handle both old and new formats for analysis
          {
            const finalAnalysis =
              !isThinkingEvent
                ? eventData.analysis || data.analysis || streamingText
                : eventData.analysis || data.analysis;
            const refreshModeRaw = coerceString(eventData.refresh_mode ?? data.refresh_mode);
            const refreshMode = refreshModeRaw ? (refreshModeRaw.toLowerCase() as 'light' | 'full') : undefined;
            const reusedFlag = coerceBoolean(eventData.reused ?? data.reused);
            const revisionFlag = coerceBoolean(eventData.revision ?? data.revision);
            if (revisionFlag || reusedFlag || refreshMode === 'light') {
              markRevisionMode('analysis');
            }

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
                refreshResultMessage();
              }

              if (eventData.web_context) {
                const webContext = normalizeWebContext(eventData.web_context);
                if (webContext) {
                  setWebSearch(webContext);
                  workflowDataRef.current.webSearch = webContext;
                  refreshResultMessage();
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
                refreshResultMessage();
              }
              const sourcesCandidate =
                (eventData.analysis_sources && typeof eventData.analysis_sources === 'object' && eventData.analysis_sources) ??
                (overviewCandidate && typeof overviewCandidate === 'object' ? (overviewCandidate as any).sources : undefined) ??
                (typeof eventData.analysis === 'object' && eventData.analysis !== null
                  ? (eventData.analysis as any).analysis_sources ?? (eventData.analysis as any).sources
                  : undefined);
              const sources = parseAnalysisSources(sourcesCandidate);
              if (sources) {
                applyAnalysisSourcesUpdate(sources);
              }
              const guardrailCandidate =
                (eventData.latency_guardrail as LatencyGuardrail | undefined) ??
                (data.latency_guardrail as LatencyGuardrail | undefined);
              if (guardrailCandidate) {
                setLatencyGuardrail(guardrailCandidate);
                workflowDataRef.current.latencyGuardrail = guardrailCandidate;
                refreshResultMessage();
              }
            }

            setStreamingText('');
            setProgressiveText('');

            if (refreshMode === 'light' && !isThinkingEvent) {
              const existingBanner = followUpBanner ?? workflowDataRef.current.followUpBanner ?? null;
              const routeCandidate = existingBanner?.route ?? (revisionFlag ? 'narrative_only' : 'reuse_sql');
              const banner: FollowUpBanner = {
                title: 'Narrative Updated (Cached)',
                message: 'Quickly refreshed the narrative using cached SQL and web context.',
                route: routeCandidate,
                flowMode: existingBanner?.flowMode ?? resolvedFlowMode,
                refreshMode: 'light',
              };
              setFollowUpBanner(banner);
              workflowDataRef.current.followUpBanner = banner;
              refreshResultMessage();
            }

            stepsHook.updateStepStatus(
              'analysis_generation',
              'completed',
              [],
              {
                analysis: finalAnalysis,
                analysis_length: eventData.analysis_length,
                analysis_overview: workflowDataRef.current.analysisOverview,
                analysis_sources: workflowDataRef.current.analysisSources,
                latency_guardrail: workflowDataRef.current.latencyGuardrail,
              },
              stepInfo.elapsed_ms
            );

            // Emit the result bubble exactly once to avoid duplicates from later workflow_complete
            if (!isThinkingEvent) {
              emitResultOnce();
              refreshResultMessage();
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

        case 'tool_call_delta':
        case 'tool_call_arguments':
        case 'agent_tool_call':
        case 'agent_tool_complete': {
          const toolCall = (eventData.tool_call ?? {}) as Record<string, any>;
          const toolMetadata = (toolCall.metadata ?? {}) as Record<string, any>;
          const specialistRole = coerceString(toolMetadata.specialist_role);
          const specialistLabel =
            coerceString(toolMetadata.specialist_label) ?? analyticsUtils.formatSpecialistRoleLabel(specialistRole);
          const displayName = analyticsUtils.resolveToolDisplayName(coerceString(toolCall.name), specialistLabel);
          const toolCallId =
            coerceString(toolCall.id) ??
            coerceString((toolCall as any).tool_call_id) ??
            coerceString((toolCall as any).call_id);
          const eventTimestamp = coerceString(eventData.ts) ?? stepInfo.ts ?? new Date().toISOString();
          const guardrailPayload =
            (eventData.guardrail as Record<string, any> | undefined) ??
            (eventData.latency_guardrail as Record<string, any> | undefined) ??
            (toolMetadata.guardrail as Record<string, any> | undefined);
          const retryCount = coerceNumber(toolMetadata.retry_count);
          const cacheAgeSeconds = coerceNumber(toolMetadata.cache_age_seconds);
          const cacheSource = coerceString(toolMetadata.cache_source);
          const schemaVersion = coerceString(toolMetadata.schema_version);
          const fastPathLatencyMs = coerceNumber(toolMetadata.fast_path_latency_ms);
          const statusLabel = analyticsUtils.resolveToolStatusLabel(eventType, coerceString(toolCall.status));
          const summaryMessages = [`${displayName}: ${statusLabel}`];
          if (retryCount && retryCount > 0) {
            summaryMessages.push(`Retry ${retryCount}`);
          }
          if (cacheAgeSeconds !== undefined && cacheAgeSeconds !== null) {
            const ageNumber = Number(cacheAgeSeconds);
            if (Number.isFinite(ageNumber)) {
              summaryMessages.push(`Cache age ~${Math.round(ageNumber)}s`);
            }
          }
          const toolStepStatus =
            eventType === 'agent_tool_complete'
              ? analyticsUtils.mapToolCompletionStatus(coerceString(toolCall.status))
              : 'in_progress';
          const detailOverrides: Record<string, any> = {
            arguments: toolCall.arguments,
            arguments_delta: toolCall.arguments_delta,
            status: toolCall.status,
            sequence_number: toolCall.sequence_number ?? toolCall.sequenceNumber,
            output_index: toolCall.output_index ?? toolCall.outputIndex,
          };
          upsertAgentToolStep(
            toolCall,
            toolStepStatus,
            summaryMessages,
            detailOverrides,
            {
              lane: laneFromEvent,
              reused: reusedFlag ?? resolveReusedFlag(toolCall, toolMetadata, eventData, data),
              guardrail: guardrailPayload,
              toolCallId,
              specialistRole,
              specialistLabel,
              schemaVersion,
              retryCount,
              cacheAgeSeconds,
              cacheSource,
              fastPathLatencyMs,
              displayName,
            },
            eventTimestamp,
          );
          const syntheticMetadata: Record<string, any> = {};
          const laneCandidate = resolveLane(eventData, toolCall, { lane: laneFromEvent });
          if (laneCandidate) {
            syntheticMetadata.lane = laneCandidate;
          }
          if (toolCall.sequence_number !== undefined && toolCall.sequence_number !== null) {
            syntheticMetadata.sequence_number = toolCall.sequence_number;
          }
          if (toolCall.output_index !== undefined && toolCall.output_index !== null) {
            syntheticMetadata.output_index = toolCall.output_index;
          }
          if (eventType === 'tool_call_delta' && toolCall.arguments_delta) {
            syntheticMetadata.arguments_delta = toolCall.arguments_delta;
          }
          if (toolCall.arguments) {
            syntheticMetadata.arguments = toolCall.arguments;
          }
          if (typeof toolCall.status === 'string') {
            syntheticMetadata.status = toolCall.status;
          }
          const cacheAge = toolMetadata.cache_age_seconds ?? toolMetadata.age_seconds ?? eventData.age_seconds;
          if (cacheAge !== undefined) {
            syntheticMetadata.cache_age_seconds = cacheAge;
          }
          const syntheticPayload = {
            tool: coerceString(toolCall.name) ?? coerceString(toolCall.tool) ?? toolCallId ?? 'agent_tool',
            status:
              eventType === 'tool_call_arguments' || eventType === 'agent_tool_complete'
                ? 'completed'
                : 'running',
            ts: eventTimestamp,
            metadata: syntheticMetadata,
            details: {
              arguments: toolCall.arguments,
              arguments_delta: toolCall.arguments_delta,
              status: toolCall.status,
            },
          };
          recordToolCallEvent(syntheticPayload, {
            ts: eventTimestamp,
            elapsed_ms: stepInfo.elapsed_ms,
            sequence,
            parallel_group: parallelGroup,
            tool_group: toolGroup ?? syntheticPayload.tool,
          });
          break;
        }

        case 'tool_call':
          recordToolCallEvent(eventData, { ts: stepInfo.ts, elapsed_ms: stepInfo.elapsed_ms, sequence, parallel_group: parallelGroup, tool_group: toolGroup });
          break;

        case 'tool_parallel_start':
          {
            emitResultOnce();
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
              parallelGroup,
            }, stepInfo.elapsed_ms, stepInfo.ts);

            const normalizedTools = manifest.map((entry) => String(entry.name || (entry as any).tool || '').toLowerCase());
            if (normalizedTools.some((tool) => tool.includes('stock') || tool.startsWith('market_question'))) {
              stepsHook.updateStepStatus(
                'market_lane',
                'in_progress',
                ['Fetching market data...'],
                { tool_manifest: manifest },
                stepInfo.elapsed_ms,
                stepInfo.ts,
                sequence,
                parallelGroup,
                scheduleStage,
                resolvedFlowMode,
                { lane: 'market' }
              );
            }
            if (normalizedTools.some((tool) => tool.includes('web_retriever') || tool.includes('web-search'))) {
              stepsHook.updateStepStatus(
                'web_lane',
                'in_progress',
                ['Collecting online research...'],
                { tool_manifest: manifest },
                stepInfo.elapsed_ms,
                stepInfo.ts,
                sequence,
                parallelGroup,
                scheduleStage,
                resolvedFlowMode,
                { lane: 'web' }
              );
            }
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

            const toolNameLower = String(eventData.tool || '').toLowerCase();
            if (toolNameLower.includes('stock') || toolNameLower.startsWith('market_question')) {
              const laneStatus = eventData.status === 'error' ? 'error' : 'in_progress';
              const thinkingLogs = [
                eventData.status === 'error'
                  ? `Market tool error: ${eventData.error || 'Unknown error'}`
                  : `Market tool ${eventData.status ?? 'running'}`,
              ];
              stepsHook.updateStepStatus(
                'market_lane',
                laneStatus,
                thinkingLogs,
                {
                  result: resultSummary,
                  parallelGroup,
                  scheduleStage,
                  flowMode: resolvedFlowMode,
                  laneInfo: { lane: 'market', reused: Boolean(eventData.reused) },
                },
                eventData.elapsed_ms,
                eventData.completed_at,
                sequence,
              );
            }
            if (toolNameLower.includes('web_retriever') || toolNameLower.includes('web-search')) {
              const laneStatus = eventData.status === 'error' ? 'error' : 'in_progress';
              const thinkingLogs = [
                eventData.status === 'error'
                  ? `Web tool error: ${eventData.error || 'Unknown error'}`
                  : `Web tool ${eventData.status ?? 'running'}`,
              ];
              stepsHook.updateStepStatus(
                'web_lane',
                laneStatus,
                thinkingLogs,
                {
                  result: resultSummary,
                  parallelGroup,
                  scheduleStage,
                  flowMode: resolvedFlowMode,
                  laneInfo: { lane: 'web', reused: Boolean(eventData.reused) },
                },
                eventData.elapsed_ms,
                eventData.completed_at,
                sequence,
              );

              if (toolNameLower.startsWith('web_retriever_')) {
                const rawPayload = eventData.payload || {};
                const partialContext = normalizeWebContext({
                  ...rawPayload,
                  summary: rawPayload.summary ?? eventData.metadata?.summary,
                  from_cache: rawPayload.from_cache ?? eventData.metadata?.cache_hit,
                  provider: rawPayload.provider ?? eventData.metadata?.provider,
                  model: rawPayload.model ?? eventData.metadata?.model,
                });
                if (partialContext) {
                  let merged: WebSearchResult | null = null;
                  setWebSearch((prev) => {
                    merged = mergeWebContexts(prev, partialContext);
                    workflowDataRef.current.webSearch = merged;
                    return merged;
                  });
                  if (merged) {
                    refreshResultMessage();
                  }
                }
              }
            }

            const payloadForWidget = (eventData.payload ?? {}) as Record<string, unknown>;
            if (payloadForWidget && 'stock_widget' in payloadForWidget) {
              const widgetCandidate = (payloadForWidget as { stock_widget?: StockWidgetConfig | null }).stock_widget;
              setStockWidget(widgetCandidate ?? null);
              workflowDataRef.current.stockWidget = widgetCandidate ?? null;
              refreshResultMessage();
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
                let merged: WebSearchResult | null = null;
                setWebSearch((prev) => {
                  merged = mergeWebContexts(prev, webContext);
                  workflowDataRef.current.webSearch = merged;
                  return merged;
                });
                const contextForThinking = merged ?? webContext;
                if (merged) {
                  refreshResultMessage();
                }

                const stepId = 'web_research_agent';
                const thinking: string[] = [];
                const primaryTopic = contextForThinking.searchTopic || contextForThinking.queryTerms || contextForThinking.query || '';
                const topicLabels = Array.isArray(contextForThinking.searchTopics) && contextForThinking.searchTopics.length
                  ? contextForThinking.searchTopics
                  : (Array.isArray(contextForThinking.topics) ? contextForThinking.topics.map((t: any) => t?.label || t?.query).filter(Boolean) : []);
                if (primaryTopic) thinking.push(`Primary topic: ${primaryTopic}`);
                if (topicLabels && topicLabels.length) {
                  thinking.push(`Topics: ${topicLabels.slice(0, 3).join('; ')}`);
                }
                const count = Array.isArray(contextForThinking.snippets)
                  ? contextForThinking.snippets.length
                  : (Array.isArray(contextForThinking.topics)
                    ? contextForThinking.topics.reduce((acc: number, topic: any) => acc + (Array.isArray(topic?.snippets) ? topic.snippets.length : 0), 0)
                    : 0);
                thinking.push(`Snippets: ${count}`);
                if (typeof contextForThinking.latencyMs === 'number') thinking.push(`Latency: ${contextForThinking.latencyMs}ms`);
                if (contextForThinking.model) thinking.push(`Model: ${contextForThinking.model}`);
                stepsHook.updateStepStatus(stepId, 'completed', thinking, contextForThinking, eventData.elapsed_ms ?? stepInfo.elapsed_ms, stepInfo.ts);
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
                parallelGroup,
              },
              eventData.elapsed_ms ?? stepInfo.elapsed_ms,
              stepInfo.ts,
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
                parallelGroup,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts,
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
          updateAgentCoordination([message], eventData.action === 'skip_retry' ? 'completed' : undefined, {
            ts: eventData.ts ?? stepInfo.ts,
            elapsed_ms: stepInfo.elapsed_ms,
            sequence,
          });
          const policyMessages = eventData.reason ? [message, String(eventData.reason)] : [message];
          stepsHook.updateStepStatus(
            decisionStep,
            eventData.action === 'skip_retry' ? 'error' : 'in_progress',
            policyMessages,
            {
              policy: eventData.policy,
              action: eventData.action,
              score: rawScore,
              threshold: rawThreshold,
              attempt: eventData.attempt,
              parallelGroup,
            },
            stepInfo.elapsed_ms,
            eventData.ts ?? stepInfo.ts,
            sequence,
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
          streamHook.setCurrentStatus('Classifying query');
          break;

        case 'classification_reasoning':
          stepsHook.updateStepStatus('classification', 'in_progress', [eventData.delta_text || eventData.thinking || 'Analyzing query type...'], {
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
          streamHook.setCurrentStatus('Analyzing query intent');
          break;

        case 'intent_detection_complete': {
          const slotStatusPayload = normalizeSlotStatuses(eventData.slot_statuses);
          setSlotStatuses(slotStatusPayload);
          setSlotFollowups([]);
          stepsHook.updateStepStatus('intent_detection', 'completed', [
            `Intent: ${eventData.intent_key} (${Math.round((eventData.confidence || 0) * 100)}%)`
          ], {
            intent_key: eventData.intent_key,
            confidence: eventData.confidence,
            slots_detected: eventData.slots_detected,
            slot_statuses: slotStatusPayload,
            slot_followups: Array.isArray(eventData.slot_followups) ? eventData.slot_followups : [],
          }, undefined, eventData.ts);
          break;
        }

        case 'schema_validation_started':
          stepsHook.updateStepStatus('schema_validation', 'in_progress', ['Validating required fields...'], undefined, undefined, eventData.ts);
          streamHook.setCurrentStatus('Validating schema');
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

        case 'clarification_needed': {
          const missingText = `Missing fields: ${eventData.missing_fields?.join(', ')}`;
          if (lastClarificationMissingRef.current === missingText) {
            break;
          }
          lastClarificationMissingRef.current = missingText;
          stepsHook.updateStepStatus('clarification', 'in_progress', [missingText], { missing_fields: eventData.missing_fields }, undefined, eventData.ts);
          break;
        }

        case 'clarification_skipped':
          stepsHook.updateStepStatus('clarification', 'completed', [eventData.reason || 'Clarification not needed'], undefined, undefined, eventData.ts);
          setPendingClarification(null);
          setSlotFollowups((prev) => prev.filter((item) => item.slot !== eventData.slot));
          lastClarificationMissingRef.current = null;
          lastClarificationRequestIdRef.current = null;
          if (eventData.slot) {
            upsertSlotStatus(eventData.slot, { status: 'filled' });
          }
          break;

        case 'intent_finalized':
          stepsHook.updateStepStatus('intent_detection', 'completed', ['Intent and schema finalized'], eventData, undefined, eventData.ts);
          break;

        case 'tool_planning_started':
          stepsHook.updateStepStatus('tool_planning', 'in_progress', [eventData.message || 'Planning tool execution...'], { intent_key: eventData.intent_key }, undefined, eventData.ts);
          streamHook.setCurrentStatus('Agent planning tools');
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
            refreshResultMessage({
              content: `**Final Summary:**\n\n**Key Findings:**\n${keyFindings}`,
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
              refreshResultMessage();
            }
          }
          const guardrailMeta = metadata.web_search_guardrail as LatencyGuardrail | undefined;
          if (guardrailMeta) {
            setLatencyGuardrail(guardrailMeta);
            workflowDataRef.current.latencyGuardrail = guardrailMeta;
            refreshResultMessage();
          }
          break;
        }

        case 'workflow_error': {
          // Handle workflow errors in agent modes - show persistent error banner
          const errorCode = coerceString(eventData.code ?? eventData.error_code);
          const errorMessage =
            coerceString(eventData.message) ??
            coerceString(eventData.error) ??
            'An error occurred during analysis. Please try again.';
          const errorReason = coerceString(eventData.reason);
          
          // Build a user-friendly error message
          let displayMessage = errorMessage;
          if (errorCode === 'revision_baseline_missing') {
            displayMessage = 'Run a fresh analysis first before revising. The baseline chart and narrative are required.';
          } else if (errorCode === 'validation_fatal') {
            displayMessage = 'A validation error occurred. Please start a new analysis run.';
          } else if (errorCode === 'agent_runtime_missing_required_artifacts') {
            displayMessage = 'Analysis could not complete - some required artifacts are missing. Please try again.';
          }
          
          // Reset processing state to prevent hanging UI
          streamHook.setIsProcessing(false);
          streamHook.setError(displayMessage);
          streamHook.setCurrentStatus(`Error: ${displayMessage}`);
          setRedirectNotice(displayMessage);
          
          // Clear session tracking to allow fresh start
          clearSessionTracking();
          revisionContextRef.current = { id: undefined, lanes: [], focus: undefined };
          revisionModeRef.current = 'none';
          workflowDataRef.current.revisionFocus = null;
          setRevisionMode('none');
          
          console.error('[AnalyticsMemoryStream] workflow_error:', {
            code: errorCode,
            reason: errorReason,
            message: errorMessage,
          });
          break;
        }

        case 'workflow_redirect':
        case 'workflow_cancelled': {
          const guardrailPayload =
            (eventData.guardrail as Record<string, any> | undefined) ??
            (eventData.metadata?.guardrail as Record<string, any> | undefined);
          const guardrailName = guardrailPayload
            ? coerceString(guardrailPayload.name ?? guardrailPayload.id)
            : undefined;
          const guardrailReason = guardrailPayload ? coerceString(guardrailPayload.reason) : undefined;
          const eventReason = coerceString(eventData.reason ?? guardrailReason);
          const explanationParts = [
            eventReason,
            guardrailName ? `guardrail ${guardrailName}` : undefined,
          ].filter(Boolean);
          const redirectMessage =
            coerceString(eventData.message) ??
            `Agent redirected this session${explanationParts.length ? ` (${explanationParts.join('; ')})` : ''}. Start a new analysis run to continue.`;
          clearSessionTracking();
          revisionContextRef.current = { id: undefined, lanes: [], focus: undefined };
          revisionModeRef.current = 'none';
          workflowDataRef.current.revisionFocus = null;
          setRevisionMode('none');
          streamHook.setIsProcessing(false);
          streamHook.setCurrentStatus(redirectMessage);
          setRedirectNotice(redirectMessage);
          break;
        }

        case 'lane_reused': {
          const laneName = coerceString(eventData.lane);
          if (laneName) {
            const ageSeconds =
              typeof eventData.age_seconds === 'number' && Number.isFinite(eventData.age_seconds)
                ? eventData.age_seconds
                : undefined;
            const baseMessage = coerceString(eventData.message);
            const friendlyLane = analyticsUtils.formatLaneName(laneName);
            const message =
              baseMessage ??
              `${friendlyLane} lane reused${ageSeconds !== undefined ? ` (cache age ~${Math.round(ageSeconds)}s)` : ''}`;
            const notice: LaneReuseNotice = {
              lane: laneName,
              message,
              reason: coerceString(eventData.reason),
              ts: coerceString(eventData.ts) ?? stepInfo.ts,
              ageSeconds,
              source: coerceString(eventData.source),
            };
            const fastPathLatency = coerceNumber(
              eventData.fast_path_latency_ms ?? data.fast_path_latency_ms,
            );
            if (fastPathLatency !== undefined) {
              notice.fastPathLatencyMs = fastPathLatency;
            }
            const guardrailPayload =
              eventData.guardrail ?? eventData.latency_guardrail ?? data.guardrail;
            if (guardrailPayload) {
              notice.guardrail = guardrailPayload as Record<string, any>;
            }
            setLaneReuseNotices((prev) => {
              const filtered = prev.filter((entry) => entry.lane !== laneName);
              filtered.push(notice);
              return filtered.slice(-5);
            });
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
          const finalStatusCopy =
            completionMessage && completionMessage !== workflowStatusMessage
              ? completionMessage
              : workflowStatusMessage;
          const guardrailFinalizationActive = Boolean(finalizationMessageRef.current);
          const treatAsEarlyExit = isEarlyExit || guardrailFinalizationActive;

          if (!isThinkingEvent) {
            emitResultOnce();
            if (treatAsEarlyExit) {
              if (!hasExplicitResultContentRef.current) {
                const guardrailCopy = finalizationMessageRef.current ?? finalStatusCopy ?? '';
                if (guardrailCopy) {
                  refreshResultMessage({ content: guardrailCopy });
                }
              }
            } else if (!hasExplicitResultContentRef.current) {
              refreshResultMessage({ content: '' });
            }
          }

          if (treatAsEarlyExit) {
            const shouldShowStatus = !hasExplicitResultContentRef.current;
            const statusText = finalizationMessageRef.current ?? finalStatusCopy ?? 'Output ready';
            streamHook.setCurrentStatus(shouldShowStatus ? statusText : '');
          } else {
            streamHook.setError('');
            streamHook.setCurrentStatus(hasExplicitResultContentRef.current ? '' : 'Output ready');
            finalizationMessageRef.current = null;
          }

          if (treatAsEarlyExit) {
            // Clear any partial workflow artifacts for clarity
            workflowDataRef.current = {
              chartSpec: null,
              analysis: '',
              progressiveAnalysis: '',
              progressiveText: '',
              sqlQuery: '',
              dataSample: null,
              streamingText: '',
              criteria: null,
              stockWidget: null,
              toolFanoutManifest: [],
              toolFanoutResults: [],
              concurrencyLimit: 0,
              webSearch: null,
              flowMode: telemetryFlowModeRef.current ?? flow,
              analysisOverview: null,
              analysisSources: null,
              analysisBundle: null,
              followUpBanner: null,
              specialistCards: [],
              latencyGuardrail: null,
              snapshotReuse: null,
              requestedGranularity: null,
              revisionFocus: null,
              revisionQuestions: undefined,
              webQuestions: undefined,
            };
            setChartSpec(null);
            setAnalysis('');
            setSqlQuery('');
            setDataSample(null);
            setStreamingText('');
            setAnalysisOverview(null);
            setAnalysisSources(null);
            setFollowUpBanner(null);
            setSpecialistCards([]);
            setLatencyGuardrail(null);
            resultMessageIdRef.current = null;
            resultSentRef.current = false;
            analysisReadyEmittedRef.current = false;
            finalResultMergedRef.current = false;
            hasExplicitResultContentRef.current = Boolean(finalizationMessageRef.current);
          }
          break;

        case 'finalization': {
          const detailsPayload = (eventData.details && typeof eventData.details === 'object') ? eventData.details as Record<string, unknown> : {};
          const bannerPayloadRaw =
            (eventData.banner && typeof eventData.banner === 'object' ? eventData.banner : null) ??
            (detailsPayload.banner && typeof detailsPayload.banner === 'object' ? detailsPayload.banner : null);
          const bannerPayload = (bannerPayloadRaw ?? {}) as Record<string, unknown>;

          const followUpRoute =
            coerceString(bannerPayload['route']) ??
            coerceString(detailsPayload['follow_up_route']) ??
            coerceString(eventData.follow_up_route) ??
            'full_pipeline';

          const finalAnswerOnly = coerceBoolean(
            bannerPayload['final_answer_only'] ?? detailsPayload['final_answer_only'] ?? eventData.final_answer_only,
          );
          const missingComponentsSource =
            (Array.isArray(bannerPayload['missing_components']) && (bannerPayload['missing_components'] as unknown[])) ||
            (Array.isArray(detailsPayload['missing_components']) && (detailsPayload['missing_components'] as unknown[])) ||
            (Array.isArray(eventData.missing_components) && eventData.missing_components) ||
            [];
          const missingComponents = (missingComponentsSource as unknown[])
            .map((value) => coerceString(value))
            .filter(Boolean) as string[];

          const analysisAvailable = coerceBoolean(
            bannerPayload['analysis_available'] ?? detailsPayload['analysis_available'] ?? eventData.analysis_available,
          );
          const flowModeOverride =
            coerceFlowMode(
              bannerPayload['flowMode'] ??
              bannerPayload['flow_mode'] ??
              detailsPayload['flowMode'] ??
              detailsPayload['flow_mode'] ??
              eventData.flow_mode,
            ) ?? resolvedFlowMode;

          const summaryCopy =
            coerceString(bannerPayload['summary'] ?? detailsPayload['summary'] ?? eventData.summary) ?? undefined;
          const finalMessage =
            coerceString(eventData.message) ??
            coerceString(detailsPayload['message']) ??
            coerceString(bannerPayload['message']) ??
            'Output ready';
          if (typeof finalMessage === 'string') {
            const normalizedFinalMessage = finalMessage.trim();
            finalizationMessageRef.current =
              normalizedFinalMessage && normalizedFinalMessage.toLowerCase() !== 'output ready'
                ? finalMessage
                : null;
          } else {
            finalizationMessageRef.current = null;
          }
          const title =
            coerceString(bannerPayload['title']) ??
            coerceString(detailsPayload['title']) ??
            (finalAnswerOnly ? 'Guided Final Answer' : 'Final Answer Ready');

          const banner: FollowUpBanner = {
            title,
            message: finalMessage,
            route: followUpRoute,
            flowMode: flowModeOverride,
            finalAnswerOnly: finalAnswerOnly ?? undefined,
            missingComponents: missingComponents.length ? missingComponents : undefined,
            analysisAvailable,
            summary: summaryCopy,
          };

          setFollowUpBanner(banner);
          workflowDataRef.current.followUpBanner = banner;

          emitResultOnce({ content: finalMessage });
          refreshResultMessage({ content: finalMessage });

          const thinkingLines = finalMessage ? [finalMessage] : ['Workflow finalized'];
          updateStep(
            'finalization',
            'completed',
            thinkingLines,
            {
              banner,
              message: finalMessage,
              follow_up_route: followUpRoute,
            },
            stepInfo.elapsed_ms,
            stepInfo.ts,
            {
              followUpRoute,
              finalAnswerOnly: finalAnswerOnly ?? undefined,
              missingComponents: missingComponents.length ? missingComponents : undefined,
              analysisAvailable,
            },
          );

          const statusCopy = finalMessage || 'Output ready';
          streamHook.setCurrentStatus(hasExplicitResultContentRef.current ? '' : statusCopy);
          break;
        }

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
              coerceFlowMode(eventData?.flow_mode) ?? resolvedFlowMode;
            emitResultOnce({ content: finalMessage });
            finalizationMessageRef.current =
              finalMessage.trim().toLowerCase() !== 'output ready' ? finalMessage : finalizationMessageRef.current;
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
            refreshResultMessage({ content: finalMessage });

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

            const responseStatus = finalMessage || 'Completed';
            streamHook.setCurrentStatus(hasExplicitResultContentRef.current ? '' : responseStatus);
          }
          break;

        case 'done': {
          const hasFinalizationCopy = Boolean(finalizationMessageRef.current);
          streamHook.setCurrentStatus(hasExplicitResultContentRef.current || hasFinalizationCopy ? '' : 'Output ready');
          break;
        }

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
      if (storageKey) {
        try {
          window.sessionStorage.removeItem(storageKey);
        } catch {
          // Best-effort cleanup.
        }
      }
      revisionContextRef.current = { id: undefined, lanes: [], focus: undefined };
      revisionModeRef.current = 'none';
    }
    setPendingClarification(null);
    clearClarificationState();
    setCriteria(null);
    setChatHistory([]);
    setChartSpec(null);
    setAnalysis('');
    setSqlQuery('');
    setDataSample(null);
    setStreamingText('');
    setProgressiveAnalysis('');
    setProgressiveText('');
    workflowDataRef.current.streamingText = '';
    workflowDataRef.current.progressiveAnalysis = '';
    workflowDataRef.current.progressiveText = '';
    setWebSearch(null);
    setTopicProgress({ total: 0, completed: 0, pending: 0, branches: {} });
    setStockWidget(null);
    setSingleAgentFanout(null);
    setRevisionMode('none');
    revisionModeRef.current = 'none';
    setAnalysisOverview(null);
    setAnalysisSources(null);
    setAnalysisBundle(null);
    setFollowUpBanner(null);
    applyAgentEvidenceUpdate(() => null);
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
    seenThoughtIdsRef.current = new Set();
    sqlAttemptsRef.current = [];
    agentLaneStateRef.current = {};
    resultSentRef.current = false;
    summarySentRef.current = false;
    resultMessageIdRef.current = null;
    analysisReadyEmittedRef.current = false;
    finalResultMergedRef.current = false;
    toolFanoutRef.current = { manifest: [], results: [], concurrencyLimit: 0 };
    thoughtHistoryRef.current = {};
    setLaneReuseNotices([]);
    setAgenticRevisionActive(false);
    setFreshLaneStates({});
    setRedirectNotice(null);

    // Reset workflow data ref
    workflowDataRef.current = {
      chartSpec: null,
      analysis: '',
      progressiveAnalysis: '',
      progressiveText: '',
      sqlQuery: '',
      dataSample: null,
      streamingText: '',
      criteria: null,
      stockWidget: null,
      toolFanoutManifest: [],
      toolFanoutResults: [],
      concurrencyLimit: 0,
      webSearch: null,
      flowMode: telemetryFlowModeRef.current ?? flow,
      analysisOverview: null,
      analysisSources: null,
      analysisBundle: null,
      followUpBanner: null,
      specialistCards: [],
      latencyGuardrail: null,
      snapshotReuse: null,
      requestedGranularity: null,
      revisionFocus: null,
      revisionQuestions: undefined,
      webQuestions: undefined,
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

  const clearRedirectNotice = useCallback(() => {
    setRedirectNotice(null);
  }, []);




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
    topicProgress,
    stockWidget,
    analysisOverview,
    analysisSources,
    analysisBundle,
    followUpBanner,
    agentEvidence,
    specialistCards,
    singleAgentFanout,
    revisionMode,
    slotStatuses,
    slotFollowups,

    latencyGuardrail,
    snapshotReuse,
    laneReuseNotices,
    agenticRevisionActive,
    freshLaneStates,
    flowMode: telemetryFlowMode,
    redirectNotice,

    // Progressive rendering state
    progressiveAnalysis,
    progressiveText,

    // Stream state
    isLoading: streamHook.isLoading,
    error: streamHook.error,
    currentStatus: streamHook.currentStatus,
    statusTimestamp: streamHook.statusTimestamp,

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
    clearRedirectNotice,
  };
};






































