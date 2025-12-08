import { STEP_NAME } from '../../../constants/analytics';
import { FlowMode, ProcessStep, SpecialistCard } from '../types';

export const AGENT_ROLE_CONFIG: Record<string, { stepId: string; lane: string; label: string }> = {
  agent_coordination: { stepId: 'agent_coordination', lane: 'analysis', label: 'Agent Coordination' },
};

export const DEFAULT_AGENT_ROLE = { stepId: 'agent_coordination', lane: 'analysis', label: 'Agent Coordination' };

export const FOLLOW_UP_BANNER_COPY: Record<string, { title: string; message: string }> = {
  full_pipeline: {
    title: 'Fresh Run Scheduled',
    message: 'Running SQL, charts, and narrative again to deliver a fully refreshed answer.',
  },
  reuse_sql: {
    title: 'Reusing Last Dataset',
    message: 'Skipping the SQL rerun - updating visuals and narrative on top of the validated table.',
  },
  stock_only: {
    title: 'Market Snapshot Only',
    message: 'Pulling fresh price data while charts and analysis stay pinned to the prior run.',
  },
  chart_revision: {
    title: 'Chart Update Requested',
    message: 'Applying the cached dataset to refresh the chart.',
  },
  chart_only: {
    title: 'Chart Revision',
    message: 'Applying the cached dataset to refresh the chart visuals.',
  },
  analysis_only: {
    title: 'Narrative Refresh',
    message: 'Refreshing the analysis narrative and citations without replanning or rerunning SQL.',
  },
  narrative_only: {
    title: 'Narrative Revision',
    message: 'Refreshing the analysis narrative and citations without replanning or rerunning SQL.',
  },
  market_only: {
    title: 'Market Refresh',
    message: 'Updating market context while preserving the previous chart and narrative.',
  },
  mixed_revision: {
    title: 'Targeted Revision',
    message: 'Applying the requested updates without replaying the full pipeline.',
  },
  cannot_revise: {
    title: 'Revision Not Available',
    message: 'Start a new question to rebuild missing results before revising again.',
  },
  missing_analysis: {
    title: 'Baseline Missing',
    message: 'Run a fresh analysis to capture the initial chart and narrative before revising.',
  },
};

export const formatLaneName = (lane?: string) => {
  if (!lane) return 'Lane';
  return lane
    .split(/[_-]/g)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
};

export const SPECIALIST_LANE_PRIORITY: Record<string, number> = {
  chart: 0,
  analysis: 1,
  market: 2,
  web: 3,
  sql: 4,
};

export const SPECIALIST_TYPE_TO_LANE: Record<string, string> = {
  chart_builder: 'chart',
  sql_executor: 'sql',
  sql_generator: 'sql',
  sql_validator: 'sql',
  sql_result_bridge: 'sql',
  stock_widget: 'market',
  web_context: 'web',
  analysis_summary: 'analysis',
  analysis_writer: 'analysis',
  chart_designer: 'chart',
  revision_questions: 'analysis',
  agent_coordination: 'analysis',
};

export const REVISION_EVENT_ALIASES: Record<string, string> = {
  stock_revision_ready: 'stock_ready',
  web_revision_ready: 'web_ready',
  sql_revision_ready: 'sql_ready',
  chart_revision_ready: 'chart_ready',
  analysis_revision_ready: 'analysis_ready',
};

export const FLOW_MODE_ALIASES: Record<string, FlowMode> = {
  'planner-executor': 'planner-executor',
  planner_executor: 'planner-executor',
  planner: 'planner-executor',
  'single-agent': 'single-agent',
  single_agent: 'single-agent',
  'multi-agent': 'multi-agent',
  multi_agent: 'multi-agent',
  supervisor: 'multi-agent',
};

export const coerceFlowMode = (raw: unknown): FlowMode | undefined => {
  if (typeof raw !== 'string') {
    return undefined;
  }
  const normalized = raw.trim().toLowerCase();
  if (!normalized) {
    return undefined;
  }
  return FLOW_MODE_ALIASES[normalized];
};

export const formatSpecialistRoleLabel = (role?: string): string | undefined => {
  if (!role) {
    return undefined;
  }
  const trimmed = role.trim();
  if (!trimmed) {
    return undefined;
  }
  return trimmed
    .split(/[_-]/g)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
};

export const resolveToolDisplayName = (toolName?: string, specialistLabel?: string): string => {
  const normalizedTool = toolName?.trim();
  const friendlyTool = normalizedTool ? STEP_NAME[normalizedTool] ?? formatLaneName(normalizedTool) : 'Agent Tool';
  return specialistLabel ? `${specialistLabel} · ${friendlyTool}` : friendlyTool;
};

export const resolveToolStatusLabel = (eventType: string, toolStatus?: string): string => {
  switch (eventType) {
    case 'agent_tool_call':
      return 'started';
    case 'tool_call_delta':
      return 'streaming arguments';
    case 'tool_call_arguments':
      return 'arguments finalized';
    case 'agent_tool_complete':
      return toolStatus ? toolStatus : 'completed';
    default:
      return toolStatus || 'update';
  }
};

export const mapToolCompletionStatus = (raw?: string): ProcessStep['status'] => {
  if (!raw) {
    return 'completed';
  }
  const normalized = raw.toLowerCase();
  if (normalized.includes('fail') || normalized.includes('error')) {
    return 'error';
  }
  if (normalized === 'skipped' || normalized === 'cancelled' || normalized === 'stopped') {
    return 'stopped';
  }
  return 'completed';
};

export const computeCardPayloadHash = (entry: SpecialistCard): string | undefined => {
  try {
    const fingerprint = {
      type: entry.type ?? '',
      lane: entry.lane ?? '',
      title: entry.title ?? '',
      topic: entry.topic ?? '',
      summary: entry.summary ?? '',
      snippets: entry.snippets ?? [],
      symbols: entry.symbols ?? [],
      meta: entry.meta ?? null,
    };
    return JSON.stringify(fingerprint);
  } catch {
    return undefined;
  }
};

const SLOT_LABEL_CACHE = new Map<string, string>();

export const formatSlotLabel = (slot: string): string => {
  if (!slot) {
    return 'Answer';
  }
  const cached = SLOT_LABEL_CACHE.get(slot);
  if (cached) {
    return cached;
  }
  const label = slot
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
  const finalLabel = label || 'Answer';
  SLOT_LABEL_CACHE.set(slot, finalLabel);
  return finalLabel;
};

export const formatTimeframeDisplay = (raw: any): string | undefined => {
  if (raw == null) {
    return undefined;
  }
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    return trimmed || undefined;
  }
  if (Array.isArray(raw)) {
    const parts = raw
      .map((entry) => {
        if (typeof entry === 'string') {
          return entry.trim();
        }
        if (typeof entry === 'number') {
          return String(entry);
        }
        return formatTimeframeDisplay(entry);
      })
      .filter((entry): entry is string => Boolean(entry && entry.length));
    return parts.length ? parts.join(', ') : undefined;
  }
  if (typeof raw === 'object') {
    const preset = typeof raw.preset === 'string' ? raw.preset.replace(/_/g, ' ').trim() : undefined;
    if (preset) {
      return preset;
    }
    const label = typeof raw.label === 'string' ? raw.label.trim() : undefined;
    if (label) {
      return label;
    }
    const value = typeof raw.value === 'string' ? raw.value.trim() : undefined;
    if (value) {
      return value;
    }
    if ((raw as any).year_to_date === true) {
      return 'year to date';
    }
    const quartersBack = (raw as any).quarters_back;
    if (typeof quartersBack === 'number' && Number.isFinite(quartersBack)) {
      const q = Math.max(0, Math.round(quartersBack));
      if (q > 0) {
        return `last ${q} quarter${q === 1 ? '' : 's'}`;
      }
    }
    const yearsBack = (raw as any).years_back;
    if (typeof yearsBack === 'number' && Number.isFinite(yearsBack)) {
      const y = Math.max(0, Math.round(yearsBack));
      if (y > 0) {
        return `last ${y} year${y === 1 ? '' : 's'}`;
      }
    }
    if (typeof (raw as any).start_year === 'number' && typeof (raw as any).end_year === 'number') {
      return `${(raw as any).start_year} - ${(raw as any).end_year}`;
    }
  }
  return undefined;
};

export type ChartGranularity = 'annual' | 'quarterly';

export const extractAnalysisFocus = (raw: string): string | undefined => {
  if (!raw) {
    return undefined;
  }
  const normalized = raw.trim();
  if (!normalized) {
    return undefined;
  }

  const cleanFocus = (value?: string | null): string | undefined => {
    if (!value) {
      return undefined;
    }
    let result = value.trim();
    if (!result) {
      return undefined;
    }
    result = result.replace(/^[\s:,\-ââ]+/, '').trim();
    result = result.replace(/\s*(?:please|pls)\.?$/i, '').trim();
    result = result.replace(/\s*(?:thanks?|thank you)\.?$/i, '').trim();
    result = result.replace(/^to\s+/, '').trim();
    result = result.replace(/^(?:focus|highlight|emphasize)\s+(?:on\s+)?/i, '').trim();
    result = result.replace(/["']+$/g, '').trim();
    if (!result) {
      return undefined;
    }
    const MAX_LENGTH = 160;
    if (result.length > MAX_LENGTH) {
      result = result.slice(0, MAX_LENGTH).trimEnd();
    }
    return result || undefined;
  };

  const direct = normalized.match(/analysis\s*[:\-ââ]\s*(.+)$/i);
  const directFocus = cleanFocus(direct?.[1]);
  if (directFocus) {
    return directFocus;
  }

  const rewrite = normalized.match(
    /analysis(?:\s+revision|\s+update|\s+refresh|\s+rewrite|\s+redo)?\s*(?:to\s+)?(?:focus|highlight|emphasize)\s+(.*)$/i,
  );
  const rewriteFocus = cleanFocus(rewrite?.[1]);
  if (rewriteFocus) {
    return rewriteFocus;
  }

  const alternate = normalized.match(/focus\s*[:\-ââ]\s*(.+)$/i);
  const alternateFocus = cleanFocus(alternate?.[1]);
  if (alternateFocus) {
    return alternateFocus;
  }

  return cleanFocus(normalized);
};

export const detectGranularityFromText = (value: string): ChartGranularity | null => {
  const normalized = value.toLowerCase();
  if (normalized.includes('quarter') || normalized.includes('qoq') || normalized.includes('q1')) {
    return 'quarterly';
  }
  if (normalized.includes('annual') || normalized.includes('yoy') || normalized.includes('year')) {
    return 'annual';
  }
  return null;
};

export const normalizeGranularityValue = (value: unknown): ChartGranularity | null => {
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (normalized in { annual: true, yearly: true, fiscal: true, fy: true }) {
      return 'annual';
    }
    if (normalized in { quarterly: true, quarter: true, qoq: true }) {
      return 'quarterly';
    }
    return detectGranularityFromText(normalized);
  }
  return null;
};

export const extractGranularityFromTimeframe = (timeframe: unknown): ChartGranularity | null => {
  if (typeof timeframe !== 'object' || timeframe == null) {
    return null;
  }
  const t = timeframe as Record<string, unknown>;
  if (typeof t['granularity'] === 'string') {
    return normalizeGranularityValue(t['granularity']);
  }
  if (t['quarters_back']) {
    return 'quarterly';
  }
  if (t['years_back']) {
    return 'annual';
  }
  if (typeof t['start_year'] === 'number' && typeof t['end_year'] === 'number') {
    return 'annual';
  }
  return null;
};

export const resolveGranularityCandidate = (payload: unknown): ChartGranularity | null => {
  if (typeof payload === 'string') {
    return detectGranularityFromText(payload);
  }
  if (payload && typeof payload === 'object') {
    const direct = normalizeGranularityValue(payload);
    if (direct) {
      return direct;
    }
    const timeframeCandidate = extractGranularityFromTimeframe(payload);
    if (timeframeCandidate) {
      return timeframeCandidate;
    }
    const textual = (() => {
      try {
        return JSON.stringify(payload);
      } catch {
        return undefined;
      }
    })();
    if (textual) {
      return detectGranularityFromText(textual);
    }
    return null;
  }
  return null;
};

export const coerceClarificationValue = (value: any): string | undefined => {
  if (value == null) {
    return undefined;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed || undefined;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    const entries = value
      .map((entry) => coerceClarificationValue(entry))
      .filter((entry): entry is string => Boolean(entry && entry.length));
    return entries.length ? entries.join(', ') : undefined;
  }
  if (typeof value === 'object') {
    const timeframe = formatTimeframeDisplay(value);
    if (timeframe) {
      return timeframe;
    }
    const label = typeof (value as any).label === 'string' ? (value as any).label.trim() : undefined;
    if (label) {
      return label;
    }
    const rawValue = typeof (value as any).value === 'string' ? (value as any).value.trim() : undefined;
    if (rawValue) {
      return rawValue;
    }
    const title = typeof (value as any).title === 'string' ? (value as any).title.trim() : undefined;
    if (title) {
      return title;
    }
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
};

export const formatClarificationEcho = (slot: string, value: any): string | undefined => {
  const label = formatSlotLabel(slot);
  const baseValue =
    slot === 'timeframe' ? formatTimeframeDisplay(value) ?? coerceClarificationValue(value) : coerceClarificationValue(value);
  const trimmed = baseValue?.trim();
  if (!trimmed) {
    return undefined;
  }
  if (trimmed.toLowerCase().startsWith(label.toLowerCase())) {
    return trimmed;
  }
  return `${label}: ${trimmed}`;
};
