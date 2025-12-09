import {
  WebTopicBranchProgress,
  WebTopicBranchStatus,
  SlotStatusMap,
  SlotStatusPayload,
  AnalysisOverview,
  AnalysisEvidenceLink,
  AnalysisSources,
  AnalysisSourceInsight,
  WebSearchResult,
  WebSearchTopic,
  SpecialistCard,
} from '../types';
import { sanitizeStructuredText, sanitizeStructuredList } from '../utils';
import { computeCardPayloadHash, SPECIALIST_TYPE_TO_LANE } from './useAnalyticsUtils';

/*
Function: coerceString — called from useAnalyticsMemoryStream event transformers to normalize unknown inputs into trimmed strings. Invokes no downstream modules. Exists to centralize defensive string parsing for SSE payloads.
*/
export const coerceString = (value: unknown): string | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
};

/*
Function: coerceNumber — called from useAnalyticsMemoryStream SSE parsing to turn loose values into finite numbers. Invokes no downstream modules. Exists to avoid NaN propagation when coercing analytics payload fields.
*/
export const coerceNumber = (value: unknown): number | undefined => {
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

/*
Function: coerceBoolean — called from useAnalyticsMemoryStream transformers to derive booleans from mixed inputs. Invokes no downstream modules. Exists to normalize truthy/falsey flags coming from the analytics SSE stream.
*/
export const coerceBoolean = (value: unknown): boolean | undefined => {
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

/*
Function: coerceStringList — called from analysis/web parsing routines to sanitize arrays of strings. Invokes coerceString to trim entries. Exists to keep downstream transformers resilient to malformed lists.
*/
export const coerceStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return (value.map((entry) => coerceString(entry)).filter(Boolean) as string[]).filter((entry) => entry.length > 0);
};

/*
Function: normalizeSlotStatuses — called from useAnalyticsMemoryStream clarification handlers to coerce slot status payloads. Invokes no downstream modules. Exists to give the UI consistent slot status shapes regardless of backend schema drift.
*/
export const normalizeSlotStatuses = (payload: any): SlotStatusMap => {
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

/*
Function: normalizeTopicBranchPayload — called from useAnalyticsMemoryStream web branch event handlers to coerce topic branches. Invokes coerceString/coerceNumber. Exists to align branch progress data for UI rendering and follow-up calculations.
*/
export const normalizeTopicBranchPayload = (
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

/*
Function: resolveLane — called from useAnalyticsMemoryStream to infer lane metadata from varied payload shapes. Invokes coerceString. Exists to make downstream step tracking resilient to schema changes across backend emitters.
*/
export const resolveLane = (...sources: any[]): string | undefined => {
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

/*
Function: resolveReusedFlag — called from useAnalyticsMemoryStream when labeling cache/reuse status. Invokes coerceBoolean/coerceString. Exists to unify cache markers across legacy and new event shapes.
*/
export const resolveReusedFlag = (...sources: any[]): boolean | undefined => {
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

/*
Function: parseAnalysisOverview — called from useAnalyticsMemoryStream analysis SSE handlers to sanitize TLDR/highlights and evidence. Invokes sanitizeStructuredText/sanitizeStructuredList/coerceStringList. Exists to present consistent analysis overview cards.
*/
export const parseAnalysisOverview = (source: any): AnalysisOverview | null => {
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

/*
Function: parseAnalysisSources — called from analysis SSE handlers to normalize source metadata. Invokes resolveLane/resolveReusedFlag/coerce helpers. Exists to keep analysis source chips consistent across revisions.
*/
export const parseAnalysisSources = (source: any): AnalysisSources | null => {
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

/*
Function: makeAnalysisSourceFingerprint — internal helper used by mergeAnalysisSources to dedupe sources. Invokes no external modules. Exists to create stable keys for merging source insights.
*/
const makeAnalysisSourceFingerprint = (key: string, insight: AnalysisSourceInsight): string => {
  const lane = (insight.lane ?? '').toString().toLowerCase();
  const id = (insight.id ?? '').toString().toLowerCase();
  const label = (insight.label ?? '').toString().toLowerCase();
  const normalizedKey = key.toLowerCase();
  const identifier = id || label || normalizedKey;
  return [lane, identifier].filter(Boolean).join('::');
};

/*
Function: mergeAnalysisInsights — internal helper to merge insight fields when deduping sources. Invokes no external modules. Exists to keep merges predictable when incoming sources overlap.
*/
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

/*
Function: mergeAnalysisSources — called from useAnalyticsMemoryStream when combining progressive analysis sources. Invokes makeAnalysisSourceFingerprint/mergeAnalysisInsights. Exists to maintain stable source ordering across SSE updates.
*/
export const mergeAnalysisSources = (
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
Function: normalizeQuestionBundle — called from useAnalyticsMemoryStream SSE handlers to sanitize Gemini question payloads. Invokes coerceString. Exists to provide a consistent shape for revision/follow-up question banners.
*/
export const normalizeQuestionBundle = (
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

/*
Function: mergeSnippetArrays — internal helper for web context merges, deduping snippets by URL/content. Invokes no downstream modules. Exists to keep merged web snippets compact.
*/
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

/*
Function: coerceTopicTotal — internal helper for mergeWebContexts to keep topic totals finite. Invokes no downstream modules. Exists to avoid NaN when combining topic counters.
*/
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

/*
Function: normalizeWebContext — called from useAnalyticsMemoryStream web SSE handlers to sanitize web search payloads. Invokes coerceString/coerceNumber/normalizeQuestionBundle. Exists to keep web search cards and topic progress consistent.
*/
export const normalizeWebContext = (raw: any): WebSearchResult | null => {
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
    ? (raw.search_topics.map(coerceString).filter(Boolean) as string[])
    : (Array.isArray(raw.searchTopics) ? (raw.searchTopics.map(coerceString).filter(Boolean) as string[]) : undefined);
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
  const latencyStats = raw.latency_stats || raw.latencyStats;
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
    questions: normalizeQuestionBundle(raw.questions),
    searchTopics: searchTopics ?? undefined,
    topicTotal:
      typeof raw.topic_total === 'number'
        ? raw.topic_total
        : typeof raw.topicTotal === 'number'
          ? raw.topicTotal
          : undefined,
  };
};

/*
Function: mergeWebContexts — called from useAnalyticsMemoryStream web SSE handlers to merge partial web contexts. Invokes mergeSnippetArrays/coerceTopicTotal. Exists to keep web search progress stable across incremental updates.
*/
export const mergeWebContexts = (current: WebSearchResult | null, incoming: WebSearchResult): WebSearchResult => {
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

/*
Function: normalizeSpecialistCard — called from useAnalyticsMemoryStream to sanitize accessory/specialist cards. Invokes resolveLane/resolveReusedFlag/computeCardPayloadHash. Exists so downstream ledger rendering receives consistent card metadata.
*/
export const normalizeSpecialistCard = (raw: any, timestamp?: string): SpecialistCard | null => {
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
      SPECIALIST_TYPE_TO_LANE[card.type] ??
      SPECIALIST_TYPE_TO_LANE[card.type.toLowerCase()];
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
  card.payloadHash = providedPayloadHash ?? computeCardPayloadHash(card);

  return card;
};

