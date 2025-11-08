import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  ControlButton,
  Background,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
  Node,
  Edge,
  Position,
  ReactFlowProvider,
  ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { ProcessNode, type ProcessNodeData as ProcessNodeComponentData, type ToolBadgeMeta } from './ProcessNode';
import {
  ProcessStep,
  FlowMode,
  FlowVisualTheme,
  LaneReuseNotice,
  ToolCallTelemetry,
  AgentTurnTelemetry,
} from '../types';

const LANE_ORDER = ['overview', 'coordination', 'planner', 'sql', 'market', 'web', 'chart', 'analysis', 'fanout'] as const;
type LaneKey = (typeof LANE_ORDER)[number];

const LANE_LABELS: Record<LaneKey, string> = {
  overview: 'Overview',
  coordination: 'Supervisor Hub',
  planner: 'Planner Lane',
  sql: 'SQL Lane',
  market: 'Market Lane',
  web: 'Web Research',
  chart: 'Charting',
  analysis: 'Analysis Writer',
  fanout: 'Tool Fan-Out',
};

const LANE_BASE_POSITIONS: Record<LaneKey, { x: number; y: number }> = {
  overview: { x: -540, y: -260 },
  coordination: { x: 0, y: -120 },
  planner: { x: -360, y: 40 },
  sql: { x: -180, y: 40 },
  market: { x: 0, y: 40 },
  web: { x: 180, y: 40 },
  chart: { x: 360, y: 40 },
  analysis: { x: 540, y: 40 },
  fanout: { x: -360, y: -200 },
};

const SINGLE_AGENT_LANE_BASE_POSITIONS: Record<LaneKey, { x: number; y: number }> = {
  overview: { x: -520, y: -260 },
  coordination: { x: 60, y: -80 },
  planner: { x: -240, y: -180 },
  sql: { x: -220, y: 40 },
  market: { x: 20, y: 40 },
  web: { x: 260, y: 40 },
  chart: { x: 500, y: 40 },
  analysis: { x: 300, y: 240 },
  fanout: { x: -40, y: -200 },
};

const START_NODE_ID = 'fanout_start';
const START_NODE_LABEL = '__start__';

const LANE_STACK_SPACING = 120;
const COORDINATION_STACK_SPACING = 100;

type MultiAgentLaneConfig = {
  spineId: string;
  offsetX?: number;
  baseOffset?: number;
  direction?: 'up' | 'down';
  stride?: number;
};

const MULTI_AGENT_MAINLINE_Y = -360;
const MULTI_AGENT_VERTICAL_OFFSET = 220;
const MULTI_AGENT_COLUMN_STRIDE = 160;

const MULTI_AGENT_SPINE_POSITIONS: Record<string, { x: number; y: number }> = {
  [START_NODE_ID]: { x: -1080, y: MULTI_AGENT_MAINLINE_Y },
  agent_coordination: { x: -320, y: MULTI_AGENT_MAINLINE_Y },
  tool_fanout: { x: 200, y: MULTI_AGENT_MAINLINE_Y },
  analysis_generation: { x: 680, y: MULTI_AGENT_MAINLINE_Y },
  follow_up_route: { x: 960, y: MULTI_AGENT_MAINLINE_Y },
};

const MULTI_AGENT_SPINE_STEPS = new Set(Object.keys(MULTI_AGENT_SPINE_POSITIONS));

const DEFAULT_MULTI_AGENT_LANE_CONFIG: MultiAgentLaneConfig = {
  spineId: 'tool_fanout',
  direction: 'down',
  baseOffset: MULTI_AGENT_VERTICAL_OFFSET,
  stride: MULTI_AGENT_COLUMN_STRIDE,
};

const MULTI_AGENT_LANE_CONFIG: Record<LaneKey, MultiAgentLaneConfig> = {
  overview: {
    spineId: START_NODE_ID,
    direction: 'down',
    offsetX: 300,
    baseOffset: MULTI_AGENT_VERTICAL_OFFSET,
    stride: MULTI_AGENT_COLUMN_STRIDE,
  },
  coordination: {
    spineId: 'agent_coordination',
    direction: 'down',
    baseOffset: MULTI_AGENT_VERTICAL_OFFSET,
    stride: MULTI_AGENT_COLUMN_STRIDE,
  },
  planner: {
    spineId: START_NODE_ID,
    direction: 'down',
    offsetX: 660,
    baseOffset: MULTI_AGENT_VERTICAL_OFFSET,
    stride: MULTI_AGENT_COLUMN_STRIDE,
  },
  sql: {
    spineId: 'tool_fanout',
    direction: 'down',
    offsetX: -460,
    baseOffset: MULTI_AGENT_VERTICAL_OFFSET,
    stride: MULTI_AGENT_COLUMN_STRIDE,
  },
  market: {
    spineId: 'tool_fanout',
    direction: 'down',
    offsetX: -160,
    baseOffset: MULTI_AGENT_VERTICAL_OFFSET,
    stride: MULTI_AGENT_COLUMN_STRIDE,
  },
  web: {
    spineId: 'tool_fanout',
    direction: 'down',
    offsetX: 140,
    baseOffset: MULTI_AGENT_VERTICAL_OFFSET,
    stride: MULTI_AGENT_COLUMN_STRIDE,
  },
  chart: {
    spineId: 'tool_fanout',
    direction: 'down',
    offsetX: 400,
    baseOffset: MULTI_AGENT_VERTICAL_OFFSET,
    stride: MULTI_AGENT_COLUMN_STRIDE,
  },
  analysis: {
    spineId: 'analysis_generation',
    direction: 'down',
    offsetX: -80,
    baseOffset: MULTI_AGENT_VERTICAL_OFFSET,
    stride: MULTI_AGENT_COLUMN_STRIDE,
  },
  fanout: {
    spineId: 'tool_fanout',
    direction: 'down',
    offsetX: 400,
    baseOffset: MULTI_AGENT_VERTICAL_OFFSET,
    stride: MULTI_AGENT_COLUMN_STRIDE,
  },
};

const FLOW_START_POSITIONS: Partial<Record<FlowMode, { x: number; y: number }>> = {
  'single-agent': { x: -620, y: -260 },
  'multi-agent': MULTI_AGENT_SPINE_POSITIONS[START_NODE_ID],
};

const SINGLE_AGENT_PREPROCESS_SEQUENCE = [
  'classification',
  'intent_classifier',
  'intent_detection',
  'clarification_manager',
  'clarification',
  'schema_validation',
] as const;
const PREPROCESS_HORIZONTAL_SPACING = 180;
const SINGLE_AGENT_PREPROCESS_BASE = { x: -340, y: -190 };
const LANE_GROUP_HORIZONTAL_SPACING = 180;
const LANE_GROUP_VERTICAL_SPACING = 110;

const PLANNER_INTENT_STEPS = new Set<string>([
  'initializing',
  'classification',
  'intent_classifier',
  'intent_detection',
  'schema_clarifier',
  'clarification_manager',
  'clarification',
  'schema_validation',
  'plan_and_select_template',
]);

const HORIZONTAL_GROUP_KEYS = new Set<string>(['planner:intent_prep', 'coordination:supervisor_spine']);
const FANOUT_TARGET_LANES: LaneKey[] = ['sql', 'market', 'web', 'chart'];

const HUB_STEP_IDS: Record<FlowMode, string> = {
  'planner-executor': 'agent_coordination',
  'single-agent': 'tool_fanout',
  'multi-agent': 'agent_coordination',
};
const SQL_SPINE_STEPS = new Set([
  'sql_generator',
  'sql_validator',
  'sql_executor',
  'sql_result_bridge',
  'sql_compilation',
  'sql_validation',
  'sql_execution',
]);
const STRICT_VERTICAL_LANES = new Set<LaneKey>(['sql']);

const isBrowser = typeof window !== 'undefined';

const resolveLaneLabel = (lane?: string) => {
  if (!lane) {
    return null;
  }
  const normalized = lane as (typeof LANE_ORDER)[number];
  return LANE_LABELS[normalized] ?? lane;
};

const buildReusedEdgeTooltip = (step: ProcessStep, lane?: string, parallelGroup?: string) => {
  const laneCandidate = lane ?? parallelGroup ?? '';
  const laneLabel = resolveLaneLabel(laneCandidate);
  const stepName = step.name || 'Cached step';
  if (laneLabel) {
    return `Reused ${laneLabel.toLowerCase()} lane from cache (${stepName})`;
  }
  return `Reused cached output from ${stepName}`;
};

const TOOL_BADGE_LIMIT = 4;
const TOOL_STATUS_PRIORITY: Record<string, number> = {
  completed: 4,
  complete: 4,
  end: 4,
  cached: 3,
  reuse: 3,
  running: 3,
  start: 2,
  queued: 1,
  pending: 1,
};

const normalizeStatusKey = (status?: string) => (typeof status === 'string' ? status.trim().toLowerCase() : '');

const friendlyToolStatus = (status?: string) => {
  const key = normalizeStatusKey(status);
  switch (key) {
    case 'start':
    case 'running':
      return 'Running';
    case 'end':
    case 'complete':
    case 'completed':
      return 'Complete';
    case 'error':
      return 'Error';
    case 'reuse':
    case 'cached':
      return 'Cached';
    case 'queued':
    case 'pending':
      return 'Queued';
    default:
      return status ? status.replace(/[_-]/g, ' ') : undefined;
  }
};

const formatToolDuration = (value?: number) => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return undefined;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}s`;
  }
  return `${Math.round(value)}ms`;
};

const formatToolLabel = (raw?: string) => {
  if (!raw) {
    return 'Tool';
  }
  return raw
    .split(/[_-]/g)
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(' ');
};

type ToolBadgeCandidate = ToolBadgeMeta & {
  statusKey?: string;
  ts?: number;
  seq?: number;
};

const parseTimestamp = (value?: string) => {
  if (!value) {
    return undefined;
  }
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? undefined : ms;
};

const buildToolBadges = (step: ProcessStep): ToolBadgeMeta[] => {
  const details = step.details;
  const toolCalls = Array.isArray(details?.tool_calls) ? (details?.tool_calls as ToolCallTelemetry[]) : [];
  const agentTurns = Array.isArray(details?.agent_turns) ? (details?.agent_turns as AgentTurnTelemetry[]) : [];

  if (!toolCalls.length && !agentTurns.length) {
    return [];
  }

  const candidates: ToolBadgeCandidate[] = [];

  toolCalls.forEach((entry, index) => {
    const toolName = formatToolLabel(entry.tool || entry.toolGroup || entry.details?.tool_call?.name);
    const laneLabel = resolveLaneLabel(entry.lane ?? entry.toolGroup ?? '') ?? undefined;
    candidates.push({
      id: entry.details?.tool_call?.id ?? `${entry.tool ?? entry.toolGroup ?? 'tool'}:${entry.sequence ?? index}`,
      tool: toolName,
      laneLabel,
      statusLabel: friendlyToolStatus(entry.status),
      statusKey: normalizeStatusKey(entry.status),
      elapsedLabel: formatToolDuration(entry.elapsed_ms),
      reused: entry.reused ?? undefined,
      ts: parseTimestamp(entry.ts),
      seq: typeof entry.sequence === 'number' ? entry.sequence : index,
    });
  });

  agentTurns.forEach((turn, index) => {
    const toolName = formatToolLabel(turn.tool || turn.specialist || turn.role);
    const laneLabel = resolveLaneLabel(turn.lane ?? turn.parallelGroup ?? turn.specialist ?? '') ?? undefined;
    candidates.push({
      id: `turn:${turn.role}:${turn.sequence ?? index}`,
      tool: toolName,
      laneLabel,
      statusLabel: friendlyToolStatus(turn.status),
      statusKey: normalizeStatusKey(turn.status),
      elapsedLabel: formatToolDuration(turn.elapsed_ms),
      reused: turn.reused ?? undefined,
      ts: parseTimestamp(turn.ts),
      seq: typeof turn.sequence === 'number' ? turn.sequence : index,
    });
  });

  const deduped = new Map<string, ToolBadgeCandidate>();
  candidates.forEach((candidate) => {
    const existing = deduped.get(candidate.id);
    if (!existing) {
      deduped.set(candidate.id, candidate);
      return;
    }
    const existingRank = TOOL_STATUS_PRIORITY[existing.statusKey ?? ''] ?? 0;
    const candidateRank = TOOL_STATUS_PRIORITY[candidate.statusKey ?? ''] ?? 0;
    if (candidateRank >= existingRank) {
      deduped.set(candidate.id, {
        ...existing,
        ...candidate,
        ts: candidate.ts ?? existing.ts,
        seq: candidate.seq ?? existing.seq,
      });
    }
  });

  return Array.from(deduped.values())
    .sort((a, b) => {
      const tsDiff = (a.ts ?? a.seq ?? 0) - (b.ts ?? b.seq ?? 0);
      if (tsDiff !== 0) {
        return tsDiff;
      }
      return (a.seq ?? 0) - (b.seq ?? 0);
    })
    .slice(-TOOL_BADGE_LIMIT)
    .reverse()
    .map(({ statusKey: _statusKey, ts: _ts, seq: _seq, ...badge }) => badge);
};

const dedupeThinking = (thinking?: string[]) => {
  if (!Array.isArray(thinking) || thinking.length === 0) {
    return [];
  }
  const seen = new Set<string>();
  const result: string[] = [];
  thinking.forEach((entry) => {
    const normalized = typeof entry === 'string' ? entry.trim() : '';
    if (!normalized) {
      return;
    }
    if (seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    result.push(entry);
  });
  return result;
};

const formatAgeSeconds = (value?: number) => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return undefined;
  }
  if (value >= 3600) {
    const hours = Math.floor(value / 3600);
    const minutes = Math.round((value % 3600) / 60);
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
  if (value >= 90) {
    const minutes = Math.floor(value / 60);
    const seconds = Math.round(value % 60);
    return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
  }
  if (value >= 60) {
    return `${(value / 60).toFixed(1)}m`;
  }
  if (value >= 1) {
    return `${Math.round(value)}s`;
  }
  return '<1s';
};

type LaneReusePill = { key: string; text: string; title?: string };

const buildLaneReusePills = (notices?: LaneReuseNotice[] | null): LaneReusePill[] => {
  if (!Array.isArray(notices) || notices.length === 0) {
    return [];
  }
  return notices
    .slice(-4)
    .reverse()
    .map((notice, index) => {
      const laneLabel = resolveLaneLabel(notice.lane) ?? (notice.lane ? notice.lane : 'Accessory lane');
      const ageLabel = formatAgeSeconds(notice.ageSeconds);
      const text = ageLabel ? `${laneLabel} reused (${ageLabel})` : `${laneLabel} reused`;
      return {
        key: `${notice.lane ?? 'lane'}-${notice.ts ?? index}`,
        text,
        title: notice.message ?? notice.reason ?? text,
      };
    });
};

interface WorkflowCanvasProps {
  steps: ProcessStep[];
  flowMode: FlowMode;
  className?: string;
  isVisible?: boolean;
  currentStepLabel?: string;
  currentStatus?: string;
  currentTimestamp?: string;
  currentDuration?: string;
  progressPercent?: number;
  laneReuseNotices?: LaneReuseNotice[] | null;
  redirectNotice?: string | null;
}

type CanvasProcessNodeData = ProcessNodeComponentData & {
  resolvedLane?: LaneKey;
  laneGroupId?: string;
  bandIndex?: number;
  memberIndex?: number;
};

const nodeTypes = {
  processNode: ProcessNode,
};

const PHASE_SEQUENCE = ['analysis', 'planning', 'execution', 'synthesis'] as const;

const PHASE_COLORS: Record<(typeof PHASE_SEQUENCE)[number], string> = {
  analysis: '#facc15',
  planning: '#38bdf8',
  execution: '#a855f7',
  synthesis: '#34d399',
};

const FLOW_THEMES: Record<FlowMode, FlowVisualTheme> = {
  'planner-executor': {
    id: 'planner-executor',
    accent: '#22d3a6',
    nodeGradient: ['rgba(14, 116, 144, 0.35)', 'rgba(6, 95, 70, 0.68)'],
    nodeBorder: 'border-emerald-400/50',
    nodeGlow: 'shadow-[0_0_22px_rgba(16,185,129,0.35)]',
    edgeIdle: '#0f766e55',
    edgeActive: '#34d399',
    edgeCompleted: '#bbf7d0',
    badgeClass: 'text-emerald-200 bg-emerald-500/15 border border-emerald-400/30',
    pulseClass: 'bg-emerald-400/90',
  },
  'single-agent': {
    id: 'single-agent',
    accent: '#60a5fa',
    nodeGradient: ['rgba(30, 64, 175, 0.32)', 'rgba(15, 23, 42, 0.78)'],
    nodeBorder: 'border-blue-400/60',
    nodeGlow: 'shadow-[0_0_22px_rgba(96,165,250,0.35)]',
    edgeIdle: '#3b82f655',
    edgeActive: '#60a5fa',
    edgeCompleted: '#bfdbfe',
    badgeClass: 'text-blue-200 bg-blue-500/15 border border-blue-400/30',
    pulseClass: 'bg-blue-400/90',
  },
  'multi-agent': {
    id: 'multi-agent',
    accent: '#c084fc',
    nodeGradient: ['rgba(76, 29, 149, 0.32)', 'rgba(30, 8, 52, 0.78)'],
    nodeBorder: 'border-purple-400/60',
    nodeGlow: 'shadow-[0_0_24px_rgba(192,132,252,0.35)]',
    edgeIdle: '#a855f755',
    edgeActive: '#c084fc',
    edgeCompleted: '#e9d5ff',
    badgeClass: 'text-purple-200 bg-purple-500/15 border border-purple-400/30',
    pulseClass: 'bg-purple-400/90',
  },
};

const FLOW_LAYOUT: Record<FlowMode, { columns: number; horizontalGap: number; verticalGap: number }> = {
  'planner-executor': { columns: 4, horizontalGap: 420, verticalGap: 280 },
  'single-agent': { columns: 5, horizontalGap: 400, verticalGap: 270 },
  'multi-agent': { columns: 5, horizontalGap: 640, verticalGap: 360 },
};

const STEP_LANE_OVERRIDES: Record<string, LaneKey> = {
  agent_coordination: 'coordination',
  planner_agent: 'planner',
  planner_phase: 'planner',
  initializing: 'planner',
  classification: 'planner',
  intent_classifier: 'planner',
  intent_detection: 'planner',
  schema_clarifier: 'planner',
  clarification_manager: 'planner',
  clarification: 'planner',
  schema_validation: 'planner',
  plan_and_select_template: 'planner',
  query_agent: 'sql',
  query_phase: 'sql',
  sql_lane: 'sql',
  sql_spine: 'sql',
  sql_generator: 'sql',
  sql_validator: 'sql',
  sql_executor: 'sql',
  sql_result_bridge: 'sql',
  sql_compilation: 'sql',
  sql_validation: 'sql',
  sql_execution: 'sql',
  analyst_agent: 'analysis',
  analyst_phase: 'analysis',
  market_agent: 'market',
  market_phase: 'market',
  market_lane: 'market',
  tool_execution: 'market',
  web_research_agent: 'web',
  web_research_phase: 'web',
  web_lane: 'web',
  chart_agent: 'chart',
  chart_phase: 'chart',
  chart_generation: 'chart',
  chart_designer: 'chart',
  analysis_generation: 'analysis',
  analysis_revision: 'analysis',
  analysis_writer: 'analysis',
  follow_up_route: 'analysis',
  tool_fanout: 'fanout',
};

const inferHubLane = (step: ProcessStep, mode: FlowMode): LaneKey => {
  if (mode === 'multi-agent' && (step.id === 'analysis_generation' || step.id === 'follow_up_route')) {
    return 'coordination';
  }
  if (STEP_LANE_OVERRIDES[step.id]) {
    return STEP_LANE_OVERRIDES[step.id];
  }
  if (step.lane) {
    if (STEP_LANE_OVERRIDES[step.lane]) {
      return STEP_LANE_OVERRIDES[step.lane];
    }
    if (Object.prototype.hasOwnProperty.call(LANE_BASE_POSITIONS, step.lane)) {
      return step.lane as (typeof LANE_ORDER)[number];
    }
  }
  if (step.parallelGroup && STEP_LANE_OVERRIDES[step.parallelGroup]) {
    return STEP_LANE_OVERRIDES[step.parallelGroup];
  }
  if (typeof step.parallelGroup === 'string' && Object.prototype.hasOwnProperty.call(LANE_BASE_POSITIONS, step.parallelGroup)) {
    return step.parallelGroup as (typeof LANE_ORDER)[number];
  }
  const id = step.id || '';
  if (id.includes('coordination') || id.includes('supervisor')) {
    return 'coordination';
  }
  if (id.includes('planner') || id.includes('clarification') || id.includes('plan')) {
    return 'planner';
  }
  if (id.includes('query') || id.includes('sql')) {
    return 'sql';
  }
  if (id.includes('analysis') || id.includes('insight')) {
    return 'analysis';
  }
  if (id.includes('chart')) {
    return 'chart';
  }
  if (id.includes('web')) {
    return 'web';
  }
  if (id.includes('market')) {
    return 'market';
  }
  if (id.includes('fanout') || id.includes('parallel')) {
    return 'fanout';
  }
  return 'overview';
};

const SNAP_GRID = 40;

const FLOW_CANVAS_DECOR: Record<FlowMode, { wrapperClass: string; overlayClass: string }> = {
  'planner-executor': {
    wrapperClass: 'bg-gradient-to-br from-gray-950 via-slate-950 to-gray-900',
    overlayClass: 'bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.18),transparent_55%)]',
  },
  'single-agent': {
    wrapperClass: 'bg-gradient-to-br from-slate-950 via-gray-950 to-blue-950',
    overlayClass: 'bg-[radial-gradient(circle_at_top,rgba(96,165,250,0.2),transparent_60%)]',
  },
  'multi-agent': {
    wrapperClass: 'bg-gradient-to-br from-gray-950 via-purple-950 to-black',
    overlayClass: 'bg-[radial-gradient(circle_at_top_right,rgba(192,132,252,0.22),transparent_60%)]',
  },
};

const STEP_PHASES: Record<string, (typeof PHASE_SEQUENCE)[number]> = {
  classification: 'analysis',
  classify: 'analysis',
  intent_classifier: 'analysis',
  intent_detection: 'analysis',
  clarification_manager: 'analysis',
  clarification: 'analysis',
  schema_validation: 'analysis',
  plan_and_select_template: 'planning',
  planning: 'planning',
  tool_planning: 'planning',
  provisional_plan: 'planning',
  sql_generator: 'execution',
  sql_validation: 'execution',
  sql_validator: 'execution',
  sql_executor: 'execution',
  sql_compilation: 'execution',
  sql_execution: 'execution',
  sql_result_bridge: 'execution',
  tool_execution: 'execution',
  plan_chart: 'execution',
  chart_designer: 'execution',
  chart_generation: 'execution',
  agent_coordination: 'execution',
  sql_lane: 'execution',
  market_lane: 'execution',
  web_lane: 'execution',
  analysis_writer: 'synthesis',
  analysis_generation: 'synthesis',
  finalization: 'synthesis',
};

const toFriendlyStatus = (status: ProcessStep['status']) => {
  switch (status) {
    case 'in_progress':
      return 'Running';
    case 'completed':
      return 'Finished';
    case 'error':
      return 'Error';
    case 'stopped':
      return 'Stopped';
    default:
      return 'Queued';
  }
};

interface SerpentinePlacement {
  position: { x: number; y: number };
  row: number;
  stepInRow: number;
  columnsInRow: number;
  isEvenRow: boolean;
}

const computeSerpentinePlacement = (
  index: number,
  columns: number,
  horizontalGap: number,
  verticalGap: number,
  totalSteps: number,
): SerpentinePlacement => {
  const row = Math.floor(index / columns);
  const stepInRow = index % columns;
  const rows = Math.ceil(totalSteps / columns) || 1;
  const isLastRow = row === rows - 1;
  const columnsInRow = isLastRow ? Math.max(1, ((totalSteps - 1) % columns) + 1) : columns;
  const isEvenRow = row % 2 === 0;

  const displayColumn = isEvenRow ? stepInRow : columnsInRow - 1 - stepInRow;
  const rowOffset = ((columns - columnsInRow) * horizontalGap) / 2;
  const x = displayColumn * horizontalGap + rowOffset;
  const y = row * verticalGap;

  return {
    position: { x, y },
    row,
    stepInRow,
    columnsInRow,
    isEvenRow,
  };
};

const getLaneBasePosition = (lane: LaneKey, mode: FlowMode): { x: number; y: number } => {
  if (mode === 'multi-agent') {
    const config = MULTI_AGENT_LANE_CONFIG[lane] ?? DEFAULT_MULTI_AGENT_LANE_CONFIG;
    const anchor = MULTI_AGENT_SPINE_POSITIONS[config.spineId] ?? MULTI_AGENT_SPINE_POSITIONS[START_NODE_ID];
    const offsetX = config.offsetX ?? 0;
    const direction = config.direction ?? DEFAULT_MULTI_AGENT_LANE_CONFIG.direction ?? 'down';
    const stride = config.stride ?? DEFAULT_MULTI_AGENT_LANE_CONFIG.stride ?? LANE_STACK_SPACING;
    const defaultOffset = direction === 'up' ? -stride : stride;
    const baseOffset = config.baseOffset ?? defaultOffset;
    return {
      x: anchor.x + offsetX,
      y: anchor.y + baseOffset,
    };
  }
  if (mode === 'single-agent') {
    return SINGLE_AGENT_LANE_BASE_POSITIONS[lane] ?? SINGLE_AGENT_LANE_BASE_POSITIONS.overview;
  }
  return LANE_BASE_POSITIONS[lane] ?? LANE_BASE_POSITIONS.overview;
};

const computeLaneGroupId = (lane: LaneKey, step: ProcessStep): string => {
  if (lane === 'planner' && PLANNER_INTENT_STEPS.has(step.id)) {
    return 'intent_prep';
  }
  if (
    lane === 'coordination' &&
    (step.id === 'agent_coordination' || step.id === 'analysis_generation' || step.id === 'follow_up_route')
  ) {
    return 'supervisor_spine';
  }
  if (lane === 'analysis' && (step.id === 'analysis_generation' || step.id === 'follow_up_route')) {
    return 'analysis_merge';
  }
  if (lane === 'sql' && SQL_SPINE_STEPS.has(step.id)) {
    return 'sql_spine';
  }
  if (lane === 'fanout') {
    return 'fanout_hub';
  }
  return step.parallelGroup ?? step.lane ?? step.id;
};

const extractLatestThinking = (step: ProcessStep): string | undefined => {
  const sanitized = dedupeThinking(step.thinking);
  const trailing = sanitized[sanitized.length - 1];
  if (step.id === 'tool_fanout') {
    const results = step.details?.tool_fanout_results;
    if (Array.isArray(results) && results.length > 0) {
      const winner = results.find((result) => result?.status === 'completed' && result?.tool);
      if (winner?.tool) {
        return `Winning branch: ${winner.tool}`;
      }
      const running = results.find((result) => result?.status === 'running' && result?.tool);
      if (running?.tool) {
        return `Running branch: ${running.tool}`;
      }
      if (!trailing) {
        return `Branches fan-out: ${results.length}`;
      }
    }
  }
  return trailing;
};

const getStartPosition = (mode: FlowMode): { x: number; y: number } => {
  const override = FLOW_START_POSITIONS[mode];
  if (override) {
    return override;
  }
  return { x: -480, y: -260 };
};

const isSpeculativeStep = (step?: ProcessStep): boolean => {
  if (!step) {
    return false;
  }
  if (step.status === 'pending' || step.status === 'queued') {
    return true;
  }
  if (step.details?.hedged) {
    return true;
  }
  return false;
};

const WorkflowCanvasInner: React.FC<WorkflowCanvasProps> = ({
  steps,
  flowMode,
  className,
  isVisible = true,
  currentStepLabel,
  currentStatus,
  currentTimestamp,
  currentDuration,
  progressPercent,
  laneReuseNotices,
  redirectNotice,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<CanvasProcessNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const flowInstanceRef = useRef<ReactFlowInstance | null>(null);
  const hasInitialFit = useRef(false);
  const lastStepCountRef = useRef(0);

  const theme = FLOW_THEMES[flowMode];
  const layout = FLOW_LAYOUT[flowMode];
  const laneReusePills = useMemo(() => buildLaneReusePills(laneReuseNotices), [laneReuseNotices]);

  const processedSteps = useMemo(() => {
    const prioritizedSteps = flowMode === 'multi-agent'
      ? (() => {
          const targetIndex = steps.findIndex((step) => step.id === 'tool_fanout');
          if (targetIndex <= 0) {
            return steps;
          }
          const clone = [...steps];
          const [fanoutStep] = clone.splice(targetIndex, 1);
          return [fanoutStep, ...clone];
        })()
      : steps;

    const total = prioritizedSteps.length || 1;
    const useLaneLayout = flowMode !== 'planner-executor';

    if (!useLaneLayout) {
      return prioritizedSteps.map((step, index) => {
        const phase = STEP_PHASES[step.id] || 'analysis';
        const placement = computeSerpentinePlacement(
          index,
          layout.columns,
          layout.horizontalGap,
          layout.verticalGap,
          total,
        );
        const latestThinking = extractLatestThinking(step);
        const isActive = step.status === 'in_progress';
        const isCompleted = step.status === 'completed';
        const hasError = step.status === 'error';
        const laneGroupId = step.parallelGroup ?? step.lane ?? step.id;

        return {
          step,
          phase,
          position: placement.position,
          row: placement.row,
          stepInRow: placement.stepInRow,
          columnsInRow: placement.columnsInRow,
          isEvenRow: placement.isEvenRow,
          isActive,
          isCompleted,
          hasError,
          latestThinking,
          index,
          parallelGroup: step.parallelGroup ?? step.lane,
          sequence: step.sequence,
          lane: step.lane,
          resolvedLane: undefined,
          laneGroupId,
          bandKey: undefined,
          bandIndex: placement.row,
          memberIndex: placement.stepInRow - 1,
        reused: Boolean(step.reused),
        finalAnswerOnly: Boolean(step.finalAnswerOnly),
        missingComponents: step.missingComponents,
        analysisAvailable: step.analysisAvailable,
        toolBadges: buildToolBadges(step),
      };
    });
  }

    const presentPreSequence = flowMode === 'single-agent'
      ? SINGLE_AGENT_PREPROCESS_SEQUENCE.filter((id) => prioritizedSteps.some((entry) => entry.id === id))
      : [];

    const laneMeta = prioritizedSteps.map((step, index) => {
      const phase = STEP_PHASES[step.id] || 'analysis';
      const resolvedLane = inferHubLane(step, flowMode);
      const laneGroupId = computeLaneGroupId(resolvedLane, step);
      const bandKey = `${resolvedLane}:${laneGroupId}`;
      return { step, index, phase, resolvedLane, laneGroupId, bandKey };
    });

    if (flowMode === 'multi-agent') {
      const multiGroupCounters = new Map<string, number>();

      return laneMeta.map((meta) => {
        const { step, index, phase, resolvedLane, laneGroupId, bandKey } = meta;

        let positionX: number;
        let positionY: number;
        let bandIndex = 0;
        let memberIndex = 0;

        if (MULTI_AGENT_SPINE_STEPS.has(step.id)) {
          const spinePosition = MULTI_AGENT_SPINE_POSITIONS[step.id];
          positionX = spinePosition?.x ?? 0;
          positionY = spinePosition?.y ?? 0;
        } else {
          const config = {
            ...DEFAULT_MULTI_AGENT_LANE_CONFIG,
            ...(MULTI_AGENT_LANE_CONFIG[resolvedLane] ?? {}),
          };
          const anchor =
            MULTI_AGENT_SPINE_POSITIONS[config.spineId] ?? MULTI_AGENT_SPINE_POSITIONS[START_NODE_ID];
          const direction = config.direction ?? 'down';
          const stride = config.stride ?? LANE_STACK_SPACING;
          const defaultOffset = direction === 'up' ? -stride : stride;
          const baseOffset = config.baseOffset ?? defaultOffset;

          const groupIndex = multiGroupCounters.get(bandKey) ?? 0;
          multiGroupCounters.set(bandKey, groupIndex + 1);

          const directionMultiplier = direction === 'up' ? -1 : 1;

          positionX = anchor.x + (config.offsetX ?? 0);
          positionY = anchor.y + baseOffset + groupIndex * stride * directionMultiplier;
          bandIndex = groupIndex;
          memberIndex = groupIndex;
        }

        const latestThinking = extractLatestThinking(step);
        const isActive = step.status === 'in_progress';
        const isCompleted = step.status === 'completed';
        const hasError = step.status === 'error';

        return {
          step,
          phase,
          position: { x: positionX, y: positionY },
          row: bandIndex,
          stepInRow: memberIndex + 1,
          columnsInRow: 1,
          isEvenRow: bandIndex % 2 === 0,
          isActive,
          isCompleted,
          hasError,
          latestThinking,
          index,
          parallelGroup: step.parallelGroup ?? laneGroupId,
          sequence: step.sequence,
          lane: step.lane ?? resolvedLane,
          resolvedLane,
          laneGroupId,
          bandKey,
          bandIndex,
          memberIndex,
        reused: Boolean(step.reused),
        finalAnswerOnly: Boolean(step.finalAnswerOnly),
        missingComponents: step.missingComponents,
        analysisAvailable: step.analysisAvailable,
        toolBadges: buildToolBadges(step),
      };
    });
  }

    const laneGroupSizes = new Map<string, number>();
    laneMeta.forEach((meta) => {
      laneGroupSizes.set(meta.bandKey, (laneGroupSizes.get(meta.bandKey) ?? 0) + 1);
    });

    const laneNextBandIndex = new Map<LaneKey, number>();
    const bandIndexMap = new Map<string, number>();
    const bandMemberIndexMap = new Map<string, number>();

    return laneMeta.map((meta) => {
      const { step, index, phase, resolvedLane, laneGroupId, bandKey } = meta;
      const base = getLaneBasePosition(resolvedLane, flowMode);
      const stackSpacing = resolvedLane === 'coordination' ? COORDINATION_STACK_SPACING : LANE_STACK_SPACING;

      let bandIndex = bandIndexMap.get(bandKey);
      if (bandIndex === undefined) {
        const nextIndex = laneNextBandIndex.get(resolvedLane) ?? 0;
        bandIndex = nextIndex;
        bandIndexMap.set(bandKey, bandIndex);
        laneNextBandIndex.set(resolvedLane, nextIndex + 1);
      }

      const groupSize = laneGroupSizes.get(bandKey) ?? 1;
      const memberIndex = bandMemberIndexMap.get(bandKey) ?? 0;
      bandMemberIndexMap.set(bandKey, memberIndex + 1);

      let positionX = base.x;
      let positionY = base.y + bandIndex * stackSpacing;

      if (flowMode === 'single-agent' && SINGLE_AGENT_PREPROCESS_SEQUENCE.includes(step.id)) {
        const orderIndex = presentPreSequence.indexOf(step.id);
        if (orderIndex >= 0) {
          positionX = SINGLE_AGENT_PREPROCESS_BASE.x + orderIndex * PREPROCESS_HORIZONTAL_SPACING;
          positionY = SINGLE_AGENT_PREPROCESS_BASE.y;
        }
      } else if (flowMode !== 'multi-agent' && HORIZONTAL_GROUP_KEYS.has(bandKey)) {
        const offset = (memberIndex - (groupSize - 1) / 2) * LANE_GROUP_HORIZONTAL_SPACING;
        positionX = base.x + offset;
      } else {
        positionY += memberIndex * LANE_GROUP_VERTICAL_SPACING;
        if (flowMode !== 'multi-agent' && !STRICT_VERTICAL_LANES.has(resolvedLane) && memberIndex > 0) {
          const indent = Math.min(memberIndex, 3) * 28;
          positionX += indent;
        }
      }

      const latestThinking = extractLatestThinking(step);
      const isActive = step.status === 'in_progress';
      const isCompleted = step.status === 'completed';
      const hasError = step.status === 'error';

      return {
        step,
        phase,
        position: { x: positionX, y: positionY },
        row: bandIndex,
        stepInRow: memberIndex + 1,
        columnsInRow: groupSize,
        isEvenRow: bandIndex % 2 === 0,
        isActive,
        isCompleted,
        hasError,
        latestThinking,
        index,
        parallelGroup: step.parallelGroup ?? laneGroupId,
        sequence: step.sequence,
        lane: step.lane ?? resolvedLane,
        resolvedLane,
        laneGroupId,
        bandKey,
        bandIndex,
        memberIndex,
        reused: Boolean(step.reused),
        finalAnswerOnly: Boolean(step.finalAnswerOnly),
        missingComponents: step.missingComponents,
        analysisAvailable: step.analysisAvailable,
        toolBadges: buildToolBadges(step),
      };
    });
  }, [steps, flowMode, layout.columns, layout.horizontalGap, layout.verticalGap]);


  const translateExtent = useMemo(() => {
    const basePadX = layout.horizontalGap * 0.75;
    const basePadY = layout.verticalGap * 0.75;

    if (!processedSteps.length) {
      return [
        [-basePadX, -basePadY],
        [basePadX, basePadY],
      ] as [[number, number], [number, number]];
    }

    const positions = processedSteps.map(({ position }) => position);
    if (flowMode !== 'planner-executor') {
      positions.push(getStartPosition(flowMode));
    }
    const maxX = Math.max(...positions.map(({ x }) => x));
    let maxY = Math.max(...positions.map(({ y }) => y));
    let minX = Math.min(...positions.map(({ x }) => x));
    const extraWidth = layout.horizontalGap;
    const extraHeight = layout.verticalGap;

    if (flowMode === 'multi-agent') {
      const hubPlacement = processedSteps.find((entry) => entry.step.id === 'agent_coordination');
      if (hubPlacement) {
        minX = Math.min(minX, hubPlacement.position.x - layout.horizontalGap * 2.5);
        maxY = Math.max(maxY, hubPlacement.position.y + layout.verticalGap * 1.6);
      }
    }

    return [
      [Math.min(-basePadX, minX - basePadX), -basePadY],
      [maxX + basePadX + extraWidth, maxY + basePadY + extraHeight],
    ] as [[number, number], [number, number]];
  }, [processedSteps, layout.horizontalGap, layout.verticalGap, flowMode]);




  const handleInit = useCallback((instance: ReactFlowInstance) => {
    flowInstanceRef.current = instance;
    hasInitialFit.current = false;
    requestAnimationFrame(() => {
      if (!hasInitialFit.current) {
        instance.fitView({ padding: 0.04, includeHiddenNodes: true });
        const currentZoom = instance.getZoom();
        const targetZoom = Math.min(1.25, Math.max(0.8, currentZoom * 1.12));
        instance.zoomTo(targetZoom);
        hasInitialFit.current = true;
      }
    });
  }, []);

  const handleResetView = useCallback(() => {
    const instance = flowInstanceRef.current;
    if (!instance) {
      return;
    }
    instance.fitView({ padding: 0.08, includeHiddenNodes: true });
  }, []);

  useEffect(() => {
    const includeStart = flowMode !== 'planner-executor';
    const totalSteps = (processedSteps.length || 0) + (includeStart ? 1 : 0);
    const sequenceOffset = includeStart ? 1 : 0;
    setNodes((prevNodes) => {
      const previous = new Map(prevNodes.map((node) => [node.id, node]));
      const baseNodes = processedSteps.map(
        ({
          step,
          phase,
          position,
          isActive,
          isCompleted,
          hasError,
          latestThinking,
          index,
          parallelGroup,
          sequence,
          lane,
          resolvedLane,
          laneGroupId,
          bandIndex,
          memberIndex,
          reused,
          finalAnswerOnly,
          missingComponents,
          analysisAvailable,
          toolBadges,
        }) => {
          const priorPosition = previous.get(step.id)?.position ?? position;
          return {
            id: step.id,
            type: 'processNode',
            position: priorPosition,
            dragHandle: '.process-node__drag-handle',
            sourcePosition: Position.Right,
            targetPosition: Position.Left,
            data: {
              step,
              phase,
              theme,
              isActive,
              isCompleted,
              hasError,
              statusLabel: toFriendlyStatus(step.status),
              sequenceIndex: index + sequenceOffset,
              totalSteps,
              latestThinking,
              currentStatus,
              currentDuration,
              currentTimestamp,
              progressPercent,
              parallelGroup,
              sequence,
              lane: lane ?? resolvedLane,
              resolvedLane,
              laneGroupId,
              bandIndex,
              memberIndex,
              reused,
              finalAnswerOnly,
              missingComponents,
              analysisAvailable,
              toolBadges,
            },
          } as Node<ProcessNodeData>;
        },
      );

      const nodesWithStructure = [...baseNodes];

      if (includeStart && !nodesWithStructure.some((node) => node.id === START_NODE_ID)) {
        const startStep: ProcessStep = {
          id: START_NODE_ID,
          name: START_NODE_LABEL,
          status: 'completed',
          thinking: ['User prompt received'],
          details: { description: 'Conversation start' },
          lane: 'overview',
          parallelGroup: 'overview',
          sequence: -1,
        };
        const startPosition = previous.get(START_NODE_ID)?.position ?? getStartPosition(flowMode);
        const startNode: Node<ProcessNodeData> = {
          id: START_NODE_ID,
          type: 'processNode',
          position: startPosition,
          dragHandle: '.process-node__drag-handle',
          sourcePosition: Position.Right,
          targetPosition: Position.Left,
          data: {
            step: startStep,
            phase: 'analysis',
            theme,
            isActive: false,
            isCompleted: true,
            hasError: false,
            statusLabel: toFriendlyStatus(startStep.status),
            sequenceIndex: 0,
            totalSteps,
            latestThinking: startStep.thinking?.[0],
            currentStatus,
            currentDuration,
            currentTimestamp,
            progressPercent,
            parallelGroup: 'overview',
            sequence: startStep.sequence,
            lane: 'overview',
            resolvedLane: 'overview',
            laneGroupId: 'overview:start',
            bandIndex: 0,
            memberIndex: 0,
            reused: false,
            finalAnswerOnly: false,
            missingComponents: undefined,
            analysisAvailable: true,
            toolBadges: [],
          },
        };
        nodesWithStructure.unshift(startNode);
      }

      return nodesWithStructure;
    });
  }, [
    processedSteps,
    setNodes,
    theme,
    currentStatus,
    currentDuration,
    currentTimestamp,
    progressPercent,
    flowMode,
  ]);

  useEffect(() => {
    if (processedSteps.length !== lastStepCountRef.current) {
      lastStepCountRef.current = processedSteps.length;
      hasInitialFit.current = false;
    }
  }, [processedSteps.length]);

  useEffect(() => {
    hasInitialFit.current = false;
  }, [flowMode]);

  useEffect(() => {
    if (!isVisible) {
      hasInitialFit.current = false;
    }
  }, [isVisible]);

  useEffect(() => {
    if (!isVisible) {
      return;
    }
    const instance = flowInstanceRef.current;
    if (!instance || nodes.length === 0) {
      return;
    }
    if (instance.setTranslateExtent) {
      instance.setTranslateExtent(translateExtent);
    }
    if (!hasInitialFit.current) {
      hasInitialFit.current = true;
      instance.fitView({ padding: 0.04, includeHiddenNodes: true, duration: 400 });
      const currentZoom = instance.getZoom();
      const targetZoom = Math.min(1.25, Math.max(0.8, currentZoom * 1.12));
      instance.zoomTo(targetZoom);
    }
  }, [isVisible, nodes.length, translateExtent]);

  useEffect(() => {
    if (!processedSteps.length) {
      setEdges([]);
      return;
    }

    const includeStart = flowMode !== 'planner-executor';
    const stepEntries = new Map(processedSteps.map((entry) => [entry.step.id, entry]));

    const edges: Edge[] = [];
    const seenEdgeIds = new Set<string>();

    const pushEdge = (edge: Edge) => {
      if (!edge.id || seenEdgeIds.has(edge.id)) {
        return;
      }
      seenEdgeIds.add(edge.id);
      edges.push(edge);
    };

    const makeArrow = (color: string, size = 18) => ({
      type: 'arrowclosed',
      color,
      width: size,
      height: size,
    });

    if (processedSteps.length > 1) {
      for (let i = 0; i < processedSteps.length - 1; i += 1) {
        const current = processedSteps[i];
        const next = processedSteps[i + 1];
        const hasTransitioned = current.step.status === 'completed' || current.step.status === 'error';
        const isActiveChain = next.step.status === 'in_progress';
        const shouldAnimate = hasTransitioned || isActiveChain;
        const targetReused = Boolean(next.reused);
        const tooltip = targetReused ? buildReusedEdgeTooltip(next.step, next.lane ?? next.resolvedLane, next.parallelGroup) : undefined;

        const baseStroke = isActiveChain
          ? theme.edgeActive
          : hasTransitioned
            ? theme.edgeCompleted
            : theme.edgeIdle;

        const style: React.CSSProperties = {
          stroke: targetReused ? theme.edgeCompleted : baseStroke,
          strokeWidth: isActiveChain ? 3 : hasTransitioned ? 2.2 : 1.4,
          strokeDasharray: targetReused ? '6 3' : shouldAnimate ? '16 12' : undefined,
          filter: shouldAnimate && !targetReused ? 'drop-shadow(0 0 8px rgba(148,163,184,0.35))' : undefined,
          opacity: targetReused ? 0.95 : 1,
          cursor: targetReused ? 'help' : undefined,
        };

        pushEdge({
          id: `${current.step.id}-${next.step.id}`,
          source: current.step.id,
          target: next.step.id,
          sourceHandle: 'right',
          targetHandle: 'left',
          type: 'smoothstep',
          animated: !targetReused && shouldAnimate,
          style,
          className: targetReused ? 'edge-reused' : undefined,
          data: tooltip ? { tooltip } : undefined,
          markerEnd: makeArrow(targetReused ? theme.edgeCompleted : baseStroke),
        });
      }
    }

    if (flowMode !== 'planner-executor') {
      const hubId = HUB_STEP_IDS[flowMode];
      const hubEntry = hubId ? stepEntries.get(hubId) : undefined;
      const analysisEntry = stepEntries.get('analysis_generation');
      const followUpEntry = stepEntries.get('follow_up_route');
      const toolFanoutEntry = stepEntries.get('tool_fanout');

      const laneBuckets = new Map<LaneKey, Array<(typeof processedSteps)[number]>>();
      processedSteps.forEach((entry) => {
        if (!entry.resolvedLane) {
          return;
        }
        const existing = laneBuckets.get(entry.resolvedLane);
        if (existing) {
          existing.push(entry);
        } else {
          laneBuckets.set(entry.resolvedLane, [entry]);
        }
      });

      const connectEdge = (
        id: string,
        source: string,
        target: string,
        style: React.CSSProperties,
        tooltip?: string,
        animated = false,
        markerColor?: string,
      ) => {
        pushEdge({
          id,
          source,
          target,
          sourceHandle: 'right',
          targetHandle: 'left',
          type: 'smoothstep',
          animated,
          style,
          data: tooltip ? { tooltip } : undefined,
          markerEnd: makeArrow(markerColor ?? (typeof style.stroke === 'string' ? style.stroke : theme.edgeIdle), 16),
        });
      };

      if (includeStart) {
        const startSequence =
          flowMode === 'single-agent'
            ? SINGLE_AGENT_PREPROCESS_SEQUENCE.filter((id) => stepEntries.has(id))
            : [];
        let previousId = START_NODE_ID;
        if (flowMode === 'single-agent' && startSequence.length > 0) {
          startSequence.forEach((stepId) => {
            const targetEntry = stepEntries.get(stepId);
            if (!targetEntry) {
              return;
            }
            connectEdge(
              `${previousId}-${stepId}-prep`,
              previousId,
              stepId,
              {
                stroke: theme.edgeIdle,
                strokeWidth: 2,
              },
              undefined,
              false,
              theme.edgeIdle,
            );
            previousId = stepId;
          });
          if (hubEntry) {
            connectEdge(
              `${previousId}-${hubEntry.step.id}-hub`,
              previousId,
              hubEntry.step.id,
              {
                stroke: theme.edgeActive,
                strokeWidth: 2.4,
                filter: 'drop-shadow(0 0 6px rgba(96,165,250,0.35))',
              },
              undefined,
              false,
              theme.edgeActive,
            );
          }
        } else if (hubEntry) {
          connectEdge(
            `${START_NODE_ID}-${hubEntry.step.id}`,
            START_NODE_ID,
            hubEntry.step.id,
            {
              stroke: theme.edgeActive,
              strokeWidth: 2.4,
              filter: 'drop-shadow(0 0 6px rgba(96,165,250,0.35))',
            },
            undefined,
            false,
            theme.edgeActive,
          );
        }
      }

      const targetLanes =
        flowMode === 'single-agent'
          ? FANOUT_TARGET_LANES
          : LANE_ORDER.filter((lane) => !['overview', 'coordination', 'analysis', 'fanout'].includes(lane));

      targetLanes.forEach((lane) => {
        const laneEntries = laneBuckets.get(lane);
        if (!laneEntries || laneEntries.length === 0) {
          return;
        }
        const first = laneEntries[0];
        if (hubEntry) {
          const reused = Boolean(first.reused);
          const speculative = isSpeculativeStep(first.step);
          const stroke = reused ? theme.edgeCompleted : speculative ? theme.edgeIdle : theme.edgeActive;
          const style: React.CSSProperties = {
            stroke,
            strokeWidth: speculative ? 1.8 : 2.4,
            strokeDasharray: reused ? '6 3' : speculative ? '10 6' : undefined,
            opacity: reused ? 0.95 : 1,
            cursor: reused ? 'help' : undefined,
            filter: !reused && !speculative ? 'drop-shadow(0 0 6px rgba(148,163,184,0.28))' : undefined,
          };
          const tooltip = reused ? buildReusedEdgeTooltip(first.step, first.lane ?? first.resolvedLane, first.parallelGroup) : undefined;
          connectEdge(
            `hub-${hubEntry.step.id}-${first.step.id}`,
            hubEntry.step.id,
            first.step.id,
            style,
            tooltip,
            !reused && !speculative && first.step.status === 'in_progress',
            stroke,
          );
        }

        const last = laneEntries[laneEntries.length - 1];
        if (analysisEntry) {
          connectEdge(
            `merge-${last.step.id}-${analysisEntry.step.id}`,
            last.step.id,
            analysisEntry.step.id,
            {
              stroke: theme.edgeActive,
              strokeWidth: 2.2,
              filter: 'drop-shadow(0 0 6px rgba(148,163,184,0.35))',
            },
            undefined,
            false,
            theme.edgeActive,
          );
        }

        if (flowMode === 'multi-agent' && hubEntry && last.step.id !== hubEntry.step.id) {
          connectEdge(
            `return-${last.step.id}-${hubEntry.step.id}`,
            last.step.id,
            hubEntry.step.id,
            {
              stroke: theme.edgeIdle,
              strokeWidth: 1.4,
              strokeDasharray: '6 6',
              opacity: 0.6,
            },
            undefined,
            false,
            theme.edgeIdle,
          );
        }
      });

      if (hubEntry && analysisEntry) {
        connectEdge(
          `spine-${hubEntry.step.id}-${analysisEntry.step.id}`,
          hubEntry.step.id,
          analysisEntry.step.id,
          {
            stroke: theme.edgeActive,
            strokeWidth: 2.6,
            filter: 'drop-shadow(0 0 6px rgba(148,163,184,0.35))',
          },
          undefined,
          hubEntry.step.status === 'in_progress',
          theme.edgeActive,
        );
      }

      if (analysisEntry && followUpEntry) {
        connectEdge(
          `${analysisEntry.step.id}-${followUpEntry.step.id}`,
          analysisEntry.step.id,
          followUpEntry.step.id,
          {
            stroke: theme.edgeActive,
            strokeWidth: 2.4,
            filter: 'drop-shadow(0 0 6px rgba(148,163,184,0.35))',
          },
          undefined,
          followUpEntry.step.status === 'in_progress',
          theme.edgeActive,
        );
      }

      if (flowMode === 'single-agent') {
        const sqlLane = laneBuckets.get('sql');
        const chartEntry = stepEntries.get('chart_generation');
        if (sqlLane && sqlLane.length && chartEntry) {
          const sqlTerminal = sqlLane[sqlLane.length - 1];
          connectEdge(
            `dependency-${sqlTerminal.step.id}-${chartEntry.step.id}`,
            sqlTerminal.step.id,
            chartEntry.step.id,
            {
              stroke: theme.edgeIdle,
              strokeWidth: 1.6,
              strokeDasharray: '8 6',
              opacity: 0.7,
            },
            'Chart generation waits on SQL results',
            false,
            theme.edgeIdle,
          );
        }
      }

      if (flowMode === 'multi-agent' && hubEntry && toolFanoutEntry && toolFanoutEntry.step.id !== hubEntry.step.id) {
        connectEdge(
          `${toolFanoutEntry.step.id}-${hubEntry.step.id}`,
          toolFanoutEntry.step.id,
          hubEntry.step.id,
          {
            stroke: theme.edgeIdle,
            strokeWidth: 1.8,
            strokeDasharray: '8 6',
            opacity: 0.7,
          },
          undefined,
          false,
          theme.edgeIdle,
        );
      }
    }

    setEdges(edges);
  }, [processedSteps, setEdges, theme, flowMode]);

  useEffect(() => {
    if (!isVisible) {
      return;
    }
    const raf = requestAnimationFrame(() => {
      containerRef.current?.dispatchEvent(new CustomEvent('resize'));
    });
    return () => cancelAnimationFrame(raf);
  }, [isVisible, nodes.length, edges.length]);

  useEffect(() => {
    if (!isBrowser || !containerRef.current) {
      return;
    }
    edges.forEach((edge) => {
      const tooltip = (edge.data as { tooltip?: string } | undefined)?.tooltip;
      const edgeElement = containerRef.current?.querySelector(`[data-id="reactflow__edge-${edge.id}"]`);
      if (!edgeElement) {
        return;
      }
      if (tooltip) {
        edgeElement.setAttribute('title', tooltip);
        edgeElement.setAttribute('data-tooltip', tooltip);
      } else {
        edgeElement.removeAttribute('title');
        edgeElement.removeAttribute('data-tooltip');
      }
    });
  }, [edges]);

  const activePhase = useMemo(() => {
    const active = steps.find((step) => step.status === 'in_progress');
    if (active) {
      return STEP_PHASES[active.id] || 'analysis';
    }
    const completed = [...steps].reverse().find((step) => step.status === 'completed');
    if (completed) {
      return STEP_PHASES[completed.id] || 'analysis';
    }
    return 'analysis';
  }, [steps]);

  const decor = FLOW_CANVAS_DECOR[flowMode];
  const fitViewOptions = useMemo(
    () => ({
      padding: flowMode === 'multi-agent' ? 0.12 : 0.06,
      maxZoom: 1.6,
      minZoom: 0.35,
      includeHiddenNodes: true,
    }),
    [flowMode],
  );

  return (
    <div
      ref={containerRef}
      data-testid="workflow-canvas-root"
      data-screenshot-target="workflow-canvas"
      className={`relative flex h-full flex-col overflow-hidden ${decor.wrapperClass} ${className ?? ''}`}
    >
      <div className={`pointer-events-none absolute inset-0 ${decor.overlayClass}`} />
      <div className="flex flex-col gap-2 border-b border-white/5 bg-black/10 px-4 py-2 text-[11px] text-gray-300 backdrop-blur-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide ${FLOW_THEMES[flowMode].badgeClass}`}>
              {flowMode.replace('-', ' ')}
            </span>
            {currentStepLabel && <span className="font-medium text-gray-100">{currentStepLabel}</span>}
            {currentStatus && <span className="text-gray-400">{currentStatus}</span>}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-[10px] text-gray-400">
            <span>{`Phase ? ${activePhase.toUpperCase()}`}</span>
            {typeof progressPercent === 'number' && <span>{progressPercent}% complete</span>}
            {currentTimestamp && <span>{new Date(currentTimestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}
            {currentDuration && <span>{currentDuration}</span>}
          </div>
        </div>
        {laneReusePills.length > 0 && (
          <div className="flex flex-wrap gap-2 text-[10px] text-sky-100">
            {laneReusePills.map((pill) => (
              <span
                key={pill.key}
                title={pill.title}
                className="rounded-full border border-sky-400/40 bg-sky-600/20 px-2 py-0.5 uppercase tracking-wide"
              >
                {pill.text}
              </span>
            ))}
          </div>
        )}
        {redirectNotice && (
          <div className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-amber-100 shadow-inner" role="status">
            <span className="text-xs font-semibold uppercase tracking-wide text-amber-200">Redirect</span>
            <span className="ml-2 text-[11px] text-amber-100">{redirectNotice}</span>
          </div>
        )}
      </div>

      <div className="relative flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          onInit={handleInit}
          fitView
          fitViewOptions={fitViewOptions}
          colorMode="dark"
          className="bg-transparent"
          proOptions={{ hideAttribution: true }}
          translateExtent={translateExtent}
          defaultViewport={{ x: 0, y: 0, zoom: 1 }}
          nodesDraggable
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag
          autoPanOnNodeDrag
          panOnScroll
          snapToGrid
          snapGrid={[SNAP_GRID, SNAP_GRID]}
          minZoom={0.35}
          maxZoom={1.75}
          selectionOnDrag={false}
          zoomOnDoubleClick={false}
          elevateEdgesOnSelect
        >
          <Controls
            className="bg-gray-800/80 text-white border border-gray-700"
            showInteractive
            showFitView
            showZoom
            position="top-right"
          >
            <ControlButton onClick={handleResetView} title="Reset view">
              Reset
            </ControlButton>
          </Controls>
          <MiniMap
            className="bg-gray-900/90 border border-gray-700"
            nodeColor={(node) => {
              const data = node.data as ProcessNodeData | undefined;
              if (!data) {
                return '#4b5563';
              }
              if (data.hasError) {
                return '#ef4444';
              }
              if (data.isActive) {
                return theme.edgeActive;
              }
              if (data.isCompleted) {
                return theme.edgeCompleted;
              }
              return theme.edgeIdle;
            }}
            pannable
            zoomable
            maskColor="rgba(8, 11, 20, 0.75)"
          />
          <Background variant={BackgroundVariant.Lines} gap={32} size={1} color="#1f2937" />
        </ReactFlow>
      </div>
    </div>
  );
};

export const WorkflowCanvas: React.FC<WorkflowCanvasProps> = (props) => (
  <ReactFlowProvider>
    <WorkflowCanvasInner {...props} />
  </ReactFlowProvider>
);

export default WorkflowCanvas;

