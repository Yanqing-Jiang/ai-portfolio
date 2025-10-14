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

type WorkflowLayoutMode = 'sequential' | 'lanes';

const LANE_ORDER = ['fanout', 'overview', 'planner', 'query', 'analyst', 'chart', 'web', 'market', 'coordination'] as const;

const LANE_LABELS: Record<(typeof LANE_ORDER)[number], string> = {
  fanout: 'Tool Fan-Out',
  overview: 'Overview',
  planner: 'Planner Agent',
  query: 'Query Agent',
  analyst: 'Analyst Agent',
  chart: 'Chart Agent',
  web: 'Web Research',
  market: 'Market Agent',
  coordination: 'Coordination',
};

interface WorkflowCanvasProps {
  steps: ProcessStep[];
  flowMode: FlowMode;
  layoutMode?: WorkflowLayoutMode;
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
  'multi-agent': { columns: 5, horizontalGap: 400, verticalGap: 280 },
};

type HubLaneKey = 'fanout' | 'planner' | 'query' | 'analyst' | 'chart' | 'web' | 'market' | 'overview';

interface HubLaneGeometry {
  angle: number;
  baseRadius: number;
  branchSpacing: number;
  lateralSpacing?: number;
}

const HUB_LANE_CONFIG: Record<HubLaneKey, HubLaneGeometry> = {
  fanout: { angle: -150, baseRadius: 380, branchSpacing: 180, lateralSpacing: 36 },
  planner: { angle: -100, baseRadius: 430, branchSpacing: 190, lateralSpacing: 42 },
  query: { angle: -40, baseRadius: 440, branchSpacing: 190, lateralSpacing: 42 },
  analyst: { angle: 10, baseRadius: 450, branchSpacing: 190, lateralSpacing: 42 },
  chart: { angle: 60, baseRadius: 440, branchSpacing: 190, lateralSpacing: 42 },
  web: { angle: 105, baseRadius: 430, branchSpacing: 190, lateralSpacing: 42 },
  market: { angle: 150, baseRadius: 420, branchSpacing: 190, lateralSpacing: 42 },
  overview: { angle: 0, baseRadius: 520, branchSpacing: 210, lateralSpacing: 40 },
};

const STEP_LANE_OVERRIDES: Record<string, HubLaneKey | 'coordination'> = {
  agent_coordination: 'coordination',
  planner_agent: 'planner',
  planner_phase: 'planner',
  query_agent: 'query',
  query_phase: 'query',
  analyst_agent: 'analyst',
  analyst_phase: 'analyst',
  chart_agent: 'chart',
  chart_phase: 'chart',
  web_research_agent: 'web',
  web_research_phase: 'web',
  market_agent: 'market',
  market_phase: 'market',
  tool_fanout: 'fanout',
  sql_compilation: 'planner',
  sql_validation: 'planner',
  sql_execution: 'query',
  chart_generation: 'chart',
  analysis_generation: 'analyst',
  analysis_revision: 'analyst',
};

const inferHubLane = (step: ProcessStep): HubLaneKey | 'coordination' => {
  if (STEP_LANE_OVERRIDES[step.id]) {
    return STEP_LANE_OVERRIDES[step.id];
  }
  if (step.parallelGroup && STEP_LANE_OVERRIDES[step.parallelGroup]) {
    return STEP_LANE_OVERRIDES[step.parallelGroup] as HubLaneKey | 'coordination';
  }
  if (typeof step.parallelGroup === 'string' && HUB_LANE_CONFIG[step.parallelGroup as HubLaneKey]) {
    return step.parallelGroup as HubLaneKey;
  }
  const id = step.id || '';
  if (id.includes('planner') || id.includes('clarification') || id.includes('plan')) {
    return 'planner';
  }
  if (id.includes('query') || id.includes('sql')) {
    return 'query';
  }
  if (id.includes('analysis') || id.includes('insight')) {
    return 'analyst';
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
  intent_detection: 'analysis',
  clarification: 'analysis',
  schema_validation: 'analysis',
  plan_and_select_template: 'planning',
  planning: 'planning',
  tool_planning: 'planning',
  provisional_plan: 'planning',
  sql_validation: 'execution',
  sql_compilation: 'execution',
  sql_execution: 'execution',
  tool_execution: 'execution',
  plan_chart: 'execution',
  chart_generation: 'execution',
  agent_coordination: 'execution',
  analysis_generation: 'synthesis',
  short_financial_analysis: 'synthesis',
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

const WorkflowCanvasInner: React.FC<WorkflowCanvasProps> = ({
  steps,
  flowMode,
  layoutMode = 'sequential',
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
    const useLaneLayout = flowMode === 'multi-agent' && layoutMode === 'lanes';
    const laneCounts: Record<string, number> = {};

    return prioritizedSteps.map((step, index) => {
      const phase = STEP_PHASES[step.id] || 'analysis';
      const parallelGroup = step.parallelGroup;

      let placement: SerpentinePlacement;
      let laneKey: (typeof LANE_ORDER)[number] | undefined;

      if (useLaneLayout) {
        const resolvedLane = inferHubLane(step);
        if (resolvedLane === 'coordination') {
          const currentCount = laneCounts['coordination'] ?? 0;
          laneCounts['coordination'] = currentCount + 1;
          placement = {
            position: { x: 0, y: currentCount * (layout.verticalGap / 3) },
            row: currentCount,
            stepInRow: 0,
            columnsInRow: 1,
            isEvenRow: true,
          };
          laneKey = 'coordination';
        } else {
          const config = HUB_LANE_CONFIG[resolvedLane] ?? HUB_LANE_CONFIG.overview;
          const currentCount = laneCounts[resolvedLane] ?? 0;
          laneCounts[resolvedLane] = currentCount + 1;
          const radius = config.baseRadius + currentCount * config.branchSpacing;
          const angleRad = (config.angle * Math.PI) / 180;
          const perpendicular = angleRad + Math.PI / 2;
          const lateralSpacing = config.lateralSpacing ?? 0;
          const lateralIndex = Math.floor((currentCount + 1) / 2);
          const lateralDirection = currentCount % 2 === 0 ? 1 : -1;
          const lateralOffset = lateralSpacing ? lateralIndex * lateralSpacing * lateralDirection : 0;
          const x = Math.cos(angleRad) * radius + Math.cos(perpendicular) * lateralOffset;
          const y = Math.sin(angleRad) * radius + Math.sin(perpendicular) * lateralOffset;

          placement = {
            position: { x, y },
            row: currentCount,
            stepInRow: 0,
            columnsInRow: 1,
            isEvenRow: true,
          };
          laneKey = resolvedLane as (typeof LANE_ORDER)[number] | undefined;
        }
      } else {
        placement = computeSerpentinePlacement(
          index,
          layout.columns,
          layout.horizontalGap,
          layout.verticalGap,
          total,
        );
      }

      const latestThinking = step.thinking?.slice(-1)[0];
      const isActive = step.status === 'in_progress';
      const isCompleted = step.status === 'completed';
      const hasError = step.status === 'error';

      const laneGroup = useLaneLayout ? (laneKey ?? inferHubLane(step)) : parallelGroup;

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
        parallelGroup: laneGroup,
        sequence: step.sequence,
      };
    });
  }, [steps, layout.columns, layout.horizontalGap, layout.verticalGap, flowMode, layoutMode]);


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
    const maxX = Math.max(...positions.map(({ x }) => x));
    let maxY = Math.max(...positions.map(({ y }) => y));
    let minX = Math.min(...positions.map(({ x }) => x));
    const extraWidth = layout.horizontalGap;
    const extraHeight = layout.verticalGap;

    if (flowMode === 'multi-agent' && layoutMode === 'lanes') {
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
  }, [processedSteps, layout.horizontalGap, layout.verticalGap, flowMode, layoutMode]);




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
    const totalSteps = processedSteps.length || 1;
    setNodes((prevNodes) => {
      const previous = new Map(prevNodes.map((node) => [node.id, node]));
      const baseNodes = processedSteps.map(
        ({ step, phase, position, isActive, isCompleted, hasError, latestThinking, index, parallelGroup, sequence }) => {
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
              sequenceIndex: index,
              totalSteps,
              latestThinking,
              currentStatus,
              currentDuration,
              currentTimestamp,
              progressPercent,
              parallelGroup,
              sequence,
            },
          } as Node<ProcessNodeData>;
        },
      );

      if (flowMode === 'multi-agent' && layoutMode === 'lanes') {
        const hubPlacement = processedSteps.find((entry) => entry.step.id === 'agent_coordination');
        if (hubPlacement) {
          const hubPosition = previous.get(hubPlacement.step.id)?.position ?? hubPlacement.position;
          const supervisorStatus = hubPlacement.step.status;
          const finalStatus: ProcessStep['status'] =
            supervisorStatus === 'completed'
              ? 'completed'
              : supervisorStatus === 'error'
                ? 'error'
                : supervisorStatus === 'in_progress'
                  ? 'in_progress'
                  : 'pending';

          const userStep: ProcessStep = {
            id: 'user_entry',
            name: 'User Question',
            status: 'completed',
            thinking: [],
            details: { description: 'User prompt captured' },
          };

          const finalStep: ProcessStep = {
            id: 'final_response',
            name: 'Final Response',
            status: finalStatus,
            thinking: [],
            details: { description: 'Supervisor consolidates specialist outputs' },
          };

          const pseudoTotal = totalSteps + 1;
          const pseudoNodes: Node<ProcessNodeData>[] = [
            {
              id: userStep.id,
              type: 'processNode',
              position: { x: hubPosition.x - 520, y: hubPosition.y - 160 },
              dragHandle: '.process-node__drag-handle',
              sourcePosition: Position.Right,
              targetPosition: Position.Left,
              data: {
                step: userStep,
                phase: 'analysis',
                theme,
                isActive: false,
                isCompleted: true,
                hasError: false,
                statusLabel: toFriendlyStatus(userStep.status),
                sequenceIndex: 0,
                totalSteps: pseudoTotal,
                latestThinking: 'User prompt received',
                currentStatus,
                currentDuration,
                currentTimestamp,
                progressPercent,
                parallelGroup: 'overview',
              },
            },
            {
              id: finalStep.id,
              type: 'processNode',
              position: { x: hubPosition.x - 520, y: hubPosition.y + 160 },
              dragHandle: '.process-node__drag-handle',
              sourcePosition: Position.Right,
              targetPosition: Position.Left,
              data: {
                step: finalStep,
                phase: 'synthesis',
                theme,
                isActive: finalStatus === 'in_progress',
                isCompleted: finalStatus === 'completed',
                hasError: finalStatus === 'error',
                statusLabel: toFriendlyStatus(finalStatus),
                sequenceIndex: pseudoTotal - 1,
                totalSteps: pseudoTotal,
                latestThinking:
                  finalStatus === 'completed'
                    ? 'Final answer ready'
                    : finalStatus === 'in_progress'
                      ? 'Packaging narrative'
                      : 'Awaiting supervisor output',
                currentStatus,
                currentDuration,
                currentTimestamp,
                progressPercent,
                parallelGroup: 'overview',
              },
            },
          ];

          return [...pseudoNodes, ...baseNodes];
        }
      }

      return baseNodes;
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
    layoutMode,
  ]);

  useEffect(() => {
    if (processedSteps.length !== lastStepCountRef.current) {
      lastStepCountRef.current = processedSteps.length;
      hasInitialFit.current = false;
    }
  }, [processedSteps.length]);

  useEffect(() => {
    hasInitialFit.current = false;
  }, [flowMode, layoutMode]);

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
    if (processedSteps.length < 2) {
      setEdges([]);
      return;
    }

    const sequentialEdges: Edge[] = [];

    for (let i = 0; i < processedSteps.length - 1; i += 1) {
      const current = processedSteps[i];
      const next = processedSteps[i + 1];
      const hasTransitioned = current.step.status === 'completed' || current.step.status === 'error';
      const isActiveChain = next.step.status === 'in_progress';
      const shouldAnimate = hasTransitioned || isActiveChain;

      sequentialEdges.push({
        id: `${current.step.id}-${next.step.id}`,
        source: current.step.id,
        target: next.step.id,
        sourceHandle: 'right',

        targetHandle: 'left',

        type: 'smoothstep',
        animated: shouldAnimate,
        style: {
          stroke: isActiveChain
            ? theme.edgeActive
            : hasTransitioned
            ? theme.edgeCompleted
            : theme.edgeIdle,
          strokeWidth: isActiveChain ? 3 : hasTransitioned ? 2.2 : 1.4,
          strokeDasharray: shouldAnimate ? '16 12' : undefined,
          filter: shouldAnimate ? 'drop-shadow(0 0 8px rgba(148,163,184,0.35))' : undefined,
        },
        markerEnd: {
          type: 'arrowclosed',
          color: isActiveChain ? theme.edgeActive : hasTransitioned ? theme.edgeCompleted : theme.edgeIdle,
          width: 18,
          height: 18,
        },
      });
    }

    if (flowMode === 'multi-agent' && layoutMode === 'lanes') {
      const hubPlacement = processedSteps.find((node) => node.step.id === 'agent_coordination');
      if (hubPlacement) {
        const added = new Set<string>();
        processedSteps.forEach((node) => {
          if (node.step.id === hubPlacement.step.id) {
            return;
          }
          const lane = node.parallelGroup;
          if (!lane || lane === 'coordination') {
            return;
          }
          const edgeId = `hub-${hubPlacement.step.id}-${node.step.id}`;
          if (added.has(edgeId)) {
            return;
          }
          added.add(edgeId);
          const laneActive = node.step.status === 'in_progress';
          const laneCompleted = node.step.status === 'completed';
          sequentialEdges.push({
            id: edgeId,
            source: hubPlacement.step.id,
            target: node.step.id,
            type: 'smoothstep',
            sourceHandle: 'right',
            targetHandle: 'left',
            animated: laneActive,
            style: {
              stroke: laneActive ? theme.edgeActive : laneCompleted ? theme.edgeCompleted : theme.edgeIdle,
              strokeWidth: laneActive ? 2.6 : laneCompleted ? 2 : 1.6,
              strokeDasharray: laneCompleted ? '12 10' : undefined,
              filter: laneActive ? 'drop-shadow(0 0 8px rgba(192,132,252,0.35))' : undefined,
            },
            markerEnd: {
              type: 'arrowclosed',
              color: laneActive ? theme.edgeActive : laneCompleted ? theme.edgeCompleted : theme.edgeIdle,
              width: 16,
              height: 16,
            },
          });

          const returnEdgeId = `return-${node.step.id}-${hubPlacement.step.id}`;
          sequentialEdges.push({
            id: returnEdgeId,
            source: node.step.id,
            target: hubPlacement.step.id,
            type: 'smoothstep',
            animated: false,
            sourceHandle: 'right',
            targetHandle: 'left',
            style: {
              stroke: theme.edgeIdle,
              strokeWidth: 1.4,
              strokeDasharray: '6 6',
              opacity: 0.65,
            },
            markerEnd: {
              type: 'arrowclosed',
              color: theme.edgeIdle,
              width: 12,
              height: 12,
            },
          });
        });

        sequentialEdges.push({
          id: 'user-entry-to-hub',
          source: 'user_entry',
          target: hubPlacement.step.id,
          type: 'smoothstep',
          animated: false,
          sourceHandle: 'right',
          targetHandle: 'left',
          style: {
            stroke: '#f97316',
            strokeWidth: 2.4,
            filter: 'drop-shadow(0 0 6px rgba(249,115,22,0.35))',
          },
          markerEnd: {
            type: 'arrowclosed',
            color: '#f97316',
            width: 18,
            height: 18,
          },
        });

        sequentialEdges.push({
          id: 'hub-to-final-response',
          source: hubPlacement.step.id,
          target: 'final_response',
          type: 'smoothstep',
          animated: hubPlacement.step.status === 'in_progress',
          sourceHandle: 'right',
          targetHandle: 'left',
          style: {
            stroke: theme.edgeActive,
            strokeWidth: 2.6,
            filter: 'drop-shadow(0 0 6px rgba(192,132,252,0.35))',
          },
          markerEnd: {
            type: 'arrowclosed',
            color: theme.edgeActive,
            width: 18,
            height: 18,
          },
        });

        sequentialEdges.push({
          id: 'final-response-to-user',
          source: 'final_response',
          target: 'user_entry',
          type: 'smoothstep',
          animated: false,
          sourceHandle: 'right',
          targetHandle: 'left',
          style: {
            stroke: '#f97316',
            strokeWidth: 1.8,
            strokeDasharray: '6 6',
            opacity: 0.85,
          },
          markerEnd: {
            type: 'arrowclosed',
            color: '#f97316',
            width: 16,
            height: 16,
          },
        });
      }
    }

    setEdges(sequentialEdges);
  }, [processedSteps, setEdges, theme, flowMode, layoutMode]);

  useEffect(() => {
    if (!isVisible) {
      return;
    }
    const raf = requestAnimationFrame(() => {
      containerRef.current?.dispatchEvent(new CustomEvent('resize'));
    });
    return () => cancelAnimationFrame(raf);
  }, [isVisible, nodes.length, edges.length]);

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
          fitViewOptions={{ padding: 0.04, maxZoom: 1.6, minZoom: 0.35, includeHiddenNodes: true }}
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

