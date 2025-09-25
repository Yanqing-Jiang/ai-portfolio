import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Node,
  Edge,
  Connection,
  BackgroundVariant,
  NodeTypes,
  ReactFlowProvider,
  ReactFlowInstance,
  FitViewOptions,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { ProcessNode } from './ProcessNode';
import { ProcessStep } from '../types';

interface WorkflowCanvasProps {
  steps: ProcessStep[];
  className?: string;
  isVisible?: boolean;
}

interface ProcessNodeData {
  step: ProcessStep;
  phase: keyof typeof PHASE_COLORS;
  color: string;
  isActive: boolean;
  isCompleted: boolean;
  hasError: boolean;
}

const nodeTypes: NodeTypes = {
  processNode: ProcessNode,
};

const PHASE_COLORS = {
  analysis: 'rgb(59, 130, 246)',
  planning: 'rgb(147, 51, 234)',
  execution: 'rgb(34, 197, 94)',
  synthesis: 'rgb(250, 204, 21)',
  error: 'rgb(239, 68, 68)',
};

const PHASE_SEQUENCE: Array<keyof typeof PHASE_COLORS> = ['analysis', 'planning', 'execution', 'synthesis'];

const PHASE_LABELS: Record<keyof typeof PHASE_COLORS, string> = {
  analysis: 'Analysis',
  planning: 'Planning',
  execution: 'Execution',
  synthesis: 'Synthesis',
  error: 'Error',
};

const STEP_PHASES: Record<string, keyof typeof PHASE_COLORS> = {
  classify: 'analysis',
  classification: 'analysis',
  classification_reasoning: 'analysis',
  intent_detection: 'analysis',
  schema_validation: 'analysis',
  clarification: 'analysis',
  tool_planning: 'planning',
  tool_selection: 'planning',
  provisional_plan: 'planning',
  retrieve_templates_rag: 'planning',
  plan_and_select_template: 'planning',
  planning: 'planning',
  sql_compilation: 'planning',
  compile_sql: 'planning',
  validate_sql: 'planning',
  sql_validation: 'planning',
  tool_execution: 'execution',
  apply_execute_sql: 'execution',
  sql_execution: 'execution',
  plan_chart: 'execution',
  build_chart: 'execution',
  chart_generation: 'execution',
  short_financial_analysis: 'synthesis',
  analysis_generation: 'synthesis',
  finalization: 'synthesis',
};

const STEP_POSITIONS: Record<string, { x: number; y: number }> = {
  classify: { x: 150, y: 50 },
  classification: { x: 250, y: 50 },
  classification_reasoning: { x: 350, y: 50 },
  intent_detection: { x: 250, y: 140 },
  schema_validation: { x: 360, y: 140 },
  clarification: { x: 470, y: 140 },
  tool_planning: { x: 100, y: 260 },
  tool_selection: { x: 250, y: 260 },
  provisional_plan: { x: 400, y: 260 },
  retrieve_templates_rag: { x: 150, y: 340 },
  plan_and_select_template: { x: 260, y: 340 },
  planning: { x: 370, y: 340 },
  sql_compilation: { x: 150, y: 420 },
  compile_sql: { x: 260, y: 420 },
  validate_sql: { x: 370, y: 420 },
  sql_validation: { x: 480, y: 420 },
  tool_execution: { x: 100, y: 520 },
  apply_execute_sql: { x: 210, y: 520 },
  sql_execution: { x: 320, y: 520 },
  plan_chart: { x: 430, y: 520 },
  build_chart: { x: 540, y: 520 },
  chart_generation: { x: 650, y: 520 },
  short_financial_analysis: { x: 260, y: 620 },
  analysis_generation: { x: 370, y: 700 },
  finalization: { x: 480, y: 780 },
};

const WorkflowCanvasInner: React.FC<WorkflowCanvasProps> = ({ steps, className, isVisible = false }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<ProcessNodeData>[]>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge[]>([]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const flowInstanceRef = useRef<ReactFlowInstance | null>(null);

  const handleInit = useCallback((instance: ReactFlowInstance) => {
    flowInstanceRef.current = instance;
  }, []);

  const fitViewToNodes = useCallback(
    (options?: Partial<FitViewOptions>) => {
      const instance = flowInstanceRef.current;
      if (!instance) {
        return;
      }

      const currentNodes = instance.getNodes();
      if (!currentNodes.length) {
        return;
      }

      if (currentNodes.length === 1) {
        const [single] = currentNodes;
        const width = single.width ?? 0;
        const height = single.height ?? 0;
        instance.setCenter(
          single.position.x + width / 2,
          single.position.y + height / 2,
          { zoom: 1.1, duration: 300, ...options }
        );
        return;
      }

      instance.fitView({ padding: 0.2, duration: 300, ...options });
    },
    []
  );

  useEffect(() => {
    const newNodes: Node<ProcessNodeData>[] = steps.map((step, index) => {
      const phase = STEP_PHASES[step.id] || 'execution';
      const position = STEP_POSITIONS[step.id] || { x: 250, y: 200 + index * 110 };

      return {
        id: step.id,
        type: 'processNode',
        position,
        data: {
          step,
          phase,
          color: PHASE_COLORS[phase],
          isActive: step.status === 'in_progress',
          isCompleted: step.status === 'completed',
          hasError: step.status === 'error',
        },
      };
    });

    setNodes(newNodes);
  }, [setNodes, steps]);

  useEffect(() => {
    if (steps.length < 2) {
      setEdges([]);
      return;
    }

    const sequentialEdges: Edge[] = [];

    for (let i = 0; i < steps.length - 1; i += 1) {
      const current = steps[i];
      const next = steps[i + 1];
      const shouldConnect =
        current.status === 'completed' ||
        next.status === 'in_progress' ||
        next.status === 'completed';

      if (shouldConnect) {
        sequentialEdges.push({
          id: `${current.id}-${next.id}`,
          source: current.id,
          target: next.id,
          animated: next.status === 'in_progress' || current.status === 'completed',
          style: {
            stroke: current.status === 'completed' ? '#10b981' :
                   next.status === 'in_progress' ? '#3b82f6' : '#6b7280',
            strokeWidth: next.status === 'in_progress' ? 3 :
                        current.status === 'completed' ? 2.5 : 2,
            strokeDasharray: next.status === 'in_progress' ? '8,4' : undefined,
            filter: next.status === 'in_progress' ?
                   'drop-shadow(0 0 6px rgba(59, 130, 246, 0.6))' :
                   current.status === 'completed' ?
                   'drop-shadow(0 0 4px rgba(16, 185, 129, 0.4))' : 'none',
          },
          markerEnd: {
            type: 'arrowclosed',
            color: current.status === 'completed' ? '#10b981' :
                  next.status === 'in_progress' ? '#3b82f6' : '#6b7280',
          },
          className: next.status === 'in_progress' ? 'animate-pulse' : undefined,
        });
      }
    }

    const planningStep = steps.find((step) => step.id === 'tool_planning');
    const executionTargets = steps.filter((step) =>
      ['provisional_plan', 'validate_sql', 'apply_execute_sql', 'plan_chart'].includes(step.id)
    );

    if (planningStep) {
      executionTargets.forEach((target) => {
        const shouldAttach =
          planningStep.status === 'completed' &&
          (target.status === 'in_progress' || target.status === 'completed');

        if (shouldAttach) {
          sequentialEdges.push({
            id: `${planningStep.id}-${target.id}`,
            source: planningStep.id,
            target: target.id,
            animated: target.status === 'in_progress',
            style: {
              stroke: '#8b5cf6',
              strokeWidth: 1.5,
            },
            markerEnd: {
              type: 'arrowclosed',
              color: '#8b5cf6',
            },
          });
        }
      });
    }

    setEdges(sequentialEdges);
  }, [setEdges, steps]);

  useLayoutEffect(() => {
    if (!isVisible || !nodes.length) {
      return;
    }

    const timeout = window.setTimeout(() => fitViewToNodes(), 180);
    return () => window.clearTimeout(timeout);
  }, [fitViewToNodes, isVisible, nodes]);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const observer = new ResizeObserver(() => {
      if (isVisible) {
        fitViewToNodes({ duration: 0 });
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [fitViewToNodes, isVisible]);

  const onConnect = useCallback(
    (connection: Edge | Connection) => setEdges((existing) => addEdge(connection, existing)),
    [setEdges]
  );

  const phaseState = useMemo(() => {
    const active = steps.find((step) => step.status === 'in_progress');
    const lastCompleted = [...steps].reverse().find((step) => step.status === 'completed');
    const reference = active || lastCompleted || steps[0];
    const phase = reference ? STEP_PHASES[reference.id] || 'analysis' : 'analysis';
    const activeIndex = PHASE_SEQUENCE.indexOf(phase);
    const nextPhase = activeIndex >= 0 && activeIndex < PHASE_SEQUENCE.length - 1
      ? PHASE_SEQUENCE[activeIndex + 1]
      : null;
    const latestDecision = active?.thinking?.slice(-1)[0] || lastCompleted?.thinking?.slice(-1)[0] || '';

    return {
      phase,
      activeIndex,
      nextPhase,
      activeStepName: reference?.name || 'Waiting for agent updates...',
      latestDecision,
    };
  }, [steps]);

  return (
    <div
      ref={containerRef}
      className={`workflow-canvas relative flex h-full flex-col ${className ?? ''}`}
    >
      <div className="border-b border-gray-700 bg-gray-800/80">
        <div className="flex items-center gap-2 overflow-x-auto px-3 py-2 text-[10px] uppercase tracking-wide text-gray-300 sm:text-xs">
          {PHASE_SEQUENCE.map((phase, idx) => (
            <React.Fragment key={phase}>
              <div
                className={`rounded-md px-2 py-1 font-semibold ${
                  idx < phaseState.activeIndex
                    ? 'bg-emerald-500/20 text-emerald-200'
                    : idx === phaseState.activeIndex
                    ? 'bg-blue-500/20 text-blue-200'
                    : 'bg-gray-700/60 text-gray-400'
                }`}
              >
                {PHASE_LABELS[phase]}
              </div>
              {idx < PHASE_SEQUENCE.length - 1 && (
                <span
                  className={`text-sm ${
                    idx === phaseState.activeIndex
                      ? 'text-blue-300'
                      : idx < phaseState.activeIndex
                      ? 'text-emerald-300'
                      : 'text-gray-600'
                  }`}
                >
                  {'->'}
                </span>
              )}
            </React.Fragment>
          ))}
        </div>
        <div className="flex flex-col gap-1 px-3 pb-2 text-xs text-gray-300 sm:flex-row sm:items-center sm:justify-between">
          <div className="font-medium text-gray-200">
            Active Step: <span className="font-normal text-gray-300">{phaseState.activeStepName}</span>
          </div>
          {phaseState.latestDecision && (
            <div className="truncate text-blue-300">
              Latest Decision: {phaseState.latestDecision}
            </div>
          )}
        </div>
      </div>

      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          onInit={handleInit}
          proOptions={{ hideAttribution: true }}
          className="bg-gray-900"
          colorMode="dark"
        >
          <Controls
            className="bg-gray-800 border border-gray-600 text-white"
            showZoom
            showFitView
            showInteractive={false}
          />
          <MiniMap
            className="bg-gray-800 border border-gray-600"
            maskColor="rgba(0, 0, 0, 0.6)"
            nodeColor={(node) => {
              const data = node.data as ProcessNodeData | undefined;
              if (!data) {
                return '#374151';
              }
              if (data.hasError) {
                return '#ef4444';
              }
              if (data.isCompleted) {
                return '#10b981';
              }
              if (data.isActive) {
                return data.color || '#6b7280';
              }
              return '#374151';
            }}
          />
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#374151" />
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


