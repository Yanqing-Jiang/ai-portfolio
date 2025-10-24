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

import { ProcessNode } from './ProcessNode';
import { ProcessStep, FlowMode, FlowVisualTheme } from '../types';

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
  overview: { x: 0, y: -260 },
  coordination: { x: 0, y: -120 },
  planner: { x: -360, y: 30 },
  sql: { x: -180, y: 30 },
  market: { x: 0, y: 30 },
  web: { x: 180, y: 30 },
  chart: { x: 360, y: 30 },
  analysis: { x: 360, y: 220 },
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

const FLOW_START_POSITIONS: Partial<Record<FlowMode, { x: number; y: number }>> = {
  'single-agent': { x: -620, y: -260 },
  'multi-agent': { x: -540, y: -260 },
};

const START_NODE_ID = 'fanout_start';
const START_NODE_LABEL = '__start__';
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

const HORIZONTAL_GROUP_KEYS = new Set<string>(['planner:intent_prep']);
const FANOUT_TARGET_LANES: LaneKey[] = ['sql', 'market', 'web', 'chart'];

const HUB_STEP_IDS: Record<FlowMode, string> = {
  'planner-executor': 'agent_coordination',
  'single-agent': 'tool_fanout',
  'multi-agent': 'agent_coordination',
};

const LANE_STACK_SPACING = 120;
const COORDINATION_STACK_SPACING = 100;
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
}

interface ProcessNodeData {
  step: ProcessStep;
  phase: keyof typeof PHASE_COLORS;
  theme: FlowVisualTheme;
  isActive: boolean;
  isCompleted: boolean;
  hasError: boolean;
  statusLabel: string;
  sequenceIndex: number;
  totalSteps: number;
  latestThinking?: string;
  currentStatus?: string;
  currentDuration?: string;
  currentTimestamp?: string;
  progressPercent?: number;
  parallelGroup?: string;
  sequence?: number;
  lane?: string;
  resolvedLane?: LaneKey;
  laneGroupId?: string;
  bandIndex?: number;
  memberIndex?: number;
  reused?: boolean;
  finalAnswerOnly?: boolean;
  missingComponents?: string[];
  analysisAvailable?: boolean;
}

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
  'multi-agent': { columns: 5, horizontalGap: 520, verticalGap: 340 },
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

const inferHubLane = (step: ProcessStep): (typeof LANE_ORDER)[number] => {
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
  if (mode === 'single-agent') {
    return SINGLE_AGENT_LANE_BASE_POSITIONS[lane] ?? SINGLE_AGENT_LANE_BASE_POSITIONS.overview;
  }
  return LANE_BASE_POSITIONS[lane] ?? LANE_BASE_POSITIONS.overview;
};

const computeLaneGroupId = (lane: LaneKey, step: ProcessStep): string => {
  if (lane === 'planner' && PLANNER_INTENT_STEPS.has(step.id)) {
    return 'intent_prep';
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
  const trailing = step.thinking?.slice(-1)[0];
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
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const flowInstanceRef = useRef<ReactFlowInstance | null>(null);
  const hasInitialFit = useRef(false);
  const lastStepCountRef = useRef(0);

  const theme = FLOW_THEMES[flowMode];
  const layout = FLOW_LAYOUT[flowMode];

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
        };
      });
    }

    const presentPreSequence = flowMode === 'single-agent'
      ? SINGLE_AGENT_PREPROCESS_SEQUENCE.filter((id) => prioritizedSteps.some((entry) => entry.id === id))
      : [];

    const laneMeta = prioritizedSteps.map((step, index) => {
      const phase = STEP_PHASES[step.id] || 'analysis';
      const resolvedLane = inferHubLane(step);
      const laneGroupId = computeLaneGroupId(resolvedLane, step);
      const bandKey = `${resolvedLane}:${laneGroupId}`;
      return { step, index, phase, resolvedLane, laneGroupId, bandKey };
    });

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
      } else if (HORIZONTAL_GROUP_KEYS.has(bandKey)) {
        const offset = (memberIndex - (groupSize - 1) / 2) * LANE_GROUP_HORIZONTAL_SPACING;
        positionX = base.x + offset;
      } else {
        positionY += memberIndex * LANE_GROUP_VERTICAL_SPACING;
        if (!STRICT_VERTICAL_LANES.has(resolvedLane) && memberIndex > 0) {
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
    <div ref={containerRef} className={`relative flex h-full flex-col overflow-hidden ${decor.wrapperClass} ${className ?? ''}`}>
      <div className={`pointer-events-none absolute inset-0 ${decor.overlayClass}`} />
      <div className="flex items-center justify-between border-b border-white/5 bg-black/10 px-4 py-2 text-[11px] text-gray-300 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide ${FLOW_THEMES[flowMode].badgeClass}`}>
            {flowMode.replace('-', ' ')}
          </span>
          {currentStepLabel && <span className="font-medium text-gray-100">{currentStepLabel}</span>}
          {currentStatus && <span className="text-gray-400">{currentStatus}</span>}
        </div>
        <div className="flex items-center gap-3 text-[10px] text-gray-400">
          <span>{`Phase › ${activePhase.toUpperCase()}`}</span>
          {typeof progressPercent === 'number' && <span>{progressPercent}% complete</span>}
          {currentTimestamp && <span>{new Date(currentTimestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}
          {currentDuration && <span>{currentDuration}</span>}
        </div>
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

