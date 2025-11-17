import React, { useCallback, useEffect, useMemo, useRef } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  Position,
  ReactFlowInstance,
  Controls,
  ControlButton,
  MiniMap,
  Background,
  BackgroundVariant,
} from '@xyflow/react';
import "@xyflow/react/dist/style.css";

import { ProcessNode } from "./ProcessNode";
import {
  FlowVisualTheme,
  FlowMode,
  ProcessStep,
  SingleAgentFanout,
  FanoutBranchStatus,
  SingleAgentFanoutBranch,
} from "../types";

const BRANCH_GROUP_MAP: Record<string, string> = {
  sql_planner: 'planner',
  chart_builder: 'chart',
  stock_tracker: 'chart',
  web_retriever: 'web',
  narrative_synthesizer: 'analyst',
};

interface ProcessNodeData {
  step: ProcessStep;
  phase: "analysis" | "planning" | "execution" | "synthesis";
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

const FANOUT_THEMES: Record<FlowMode, FlowVisualTheme> = {
  'single-agent': {
    id: "single-agent",
    accent: "#60a5fa",
    nodeGradient: ["rgba(30, 64, 175, 0.32)", "rgba(15, 23, 42, 0.78)"],
    nodeBorder: "border-blue-400/60",
    nodeGlow: "shadow-[0_0_22px_rgba(96,165,250,0.35)]",
    edgeIdle: "#3b82f655",
    edgeActive: "#60a5fa",
    edgeCompleted: "#bfdbfe",
    badgeClass: "text-blue-200 bg-blue-500/15 border border-blue-400/30",
    pulseClass: "bg-blue-400/90",
  },
  'planner-executor': {
    id: "planner-executor",
    accent: "#34d399",
    nodeGradient: ["rgba(6, 95, 70, 0.32)", "rgba(5, 46, 22, 0.78)"],
    nodeBorder: "border-emerald-400/70",
    nodeGlow: "shadow-[0_0_22px_rgba(16,185,129,0.35)]",
    edgeIdle: "#04785755",
    edgeActive: "#34d399",
    edgeCompleted: "#a7f3d0",
    badgeClass: "text-emerald-100 bg-emerald-500/15 border border-emerald-400/30",
    pulseClass: "bg-emerald-300/90",
  },
  'multi-agent': {
    id: "multi-agent",
    accent: "#c084fc",
    nodeGradient: ["rgba(91, 33, 182, 0.35)", "rgba(46, 16, 101, 0.75)"],
    nodeBorder: "border-purple-400/70",
    nodeGlow: "shadow-[0_0_22px_rgba(192,132,252,0.4)]",
    edgeIdle: "#7c3aed55",
    edgeActive: "#c084fc",
    edgeCompleted: "#e9d5ff",
    badgeClass: "text-purple-100 bg-purple-500/15 border border-purple-400/30",
    pulseClass: "bg-purple-300/90",
  },
};

const resolveFanoutTheme = (mode: FlowMode): FlowVisualTheme => FANOUT_THEMES[mode] ?? FANOUT_THEMES['single-agent'];

const mapBranchStatus = (status: FanoutBranchStatus): ProcessStep["status"] => {
  switch (status) {
    case "running":
      return "in_progress";
    case "completed":
      return "completed";
    case "failed":
      return "error";
    case "stopped":
      return "stopped";
    default:
      return "pending";
  }
};

const sanitizeLabel = (branch: SingleAgentFanoutBranch) => {
  if (branch.label && branch.label.trim().length > 0) {
    return branch.label.trim();
  }
  if (branch.tool && branch.tool.trim().length > 0) {
    return branch.tool.trim();
  }
  return "Tool";
};

interface SingleAgentFanoutCanvasProps {
  fanout: SingleAgentFanout;
  flowMode?: FlowMode;
}

const SingleAgentFanoutCanvasInner: React.FC<SingleAgentFanoutCanvasProps> = ({ fanout, flowMode = 'single-agent' }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<ProcessNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge[]>([]);
  const instanceRef = useRef<ReactFlowInstance | null>(null);
  const activeTheme = useMemo(() => resolveFanoutTheme(flowMode), [flowMode]);

  const { nodeConfigs, edgeConfigs } = useMemo(() => {
    const branches = fanout.branches ?? [];
    const branchCount = branches.length || 1;
    const horizontalSpacing = 220;
    const verticalSpacing = 170;
    const centerX = 0;
    const startY = 0;
    const agentY = startY + verticalSpacing;
    const branchY = agentY + verticalSpacing;
    const endY = branchY + verticalSpacing;

    const activeCount = fanout.runningCount ?? 0;
    const completedCount = fanout.completedCount ?? 0;
    const failedCount = fanout.failedCount ?? 0;
    const queuedCount = fanout.queuedCount ?? 0;
    const stoppedCount = fanout.stoppedCount ?? 0;

    const nodesList: Node<ProcessNodeData>[] = [];
    const edgesList: Edge[] = [];
    const totalSteps = branchCount + 3;

    const startStep: ProcessStep = {
      id: "fanout_start",
      name: "__start__",
      status: "completed",
      thinking: [],
      details: { branches: branchCount, launched_at: fanout.lastUpdated },
      timestamp: fanout.lastUpdated ?? undefined,
      parallelGroup: "fanout",
      sequence: 0,
    };

    nodesList.push({
      id: startStep.id,
      type: "processNode",
      position: { x: centerX, y: startY },
      data: {
        step: startStep,
        phase: "analysis",
        theme: activeTheme,
        isActive: false,
        isCompleted: true,
        hasError: false,
        statusLabel: "Finished",
        sequenceIndex: 0,
        totalSteps,
        latestThinking: "Entry point initialised",
        progressPercent: Math.min(100, Math.round((completedCount / branchCount) * 100)),
        parallelGroup: "fanout",
        sequence: 0,
      },
      draggable: true,
      connectable: false,
      dragHandle: '.process-node__drag-handle',
    });

    let agentStatus: ProcessStep["status"] = "pending";
    if (failedCount > 0) {
      agentStatus = "error";
    } else if (activeCount > 0) {
      agentStatus = "in_progress";
    } else if (completedCount >= branchCount && queuedCount === 0 && stoppedCount === 0) {
      agentStatus = "completed";
    }

    const agentHighlights: string[] = [];
    if (activeCount) agentHighlights.push(activeCount + " running");
    if (completedCount) agentHighlights.push(completedCount + " completed");
    if (failedCount) agentHighlights.push(failedCount + " failed");
    if (queuedCount) agentHighlights.push(queuedCount + " queued");
    if (stoppedCount) agentHighlights.push(stoppedCount + " stopped");

    const agentStep: ProcessStep = {
      id: "fanout_agent",
      name: "Agent Hub",
      status: agentStatus,
      thinking: agentHighlights.length ? [agentHighlights.join(" / ")] : [],
      details: {
        activeCount,
        completedCount,
        failedCount,
        queuedCount,
        stoppedCount,
      },
      timestamp: fanout.lastUpdated ?? undefined,
      parallelGroup: "fanout",
      sequence: 1,
    };

    nodesList.push({
      id: agentStep.id,
      type: "processNode",
      position: { x: centerX, y: agentY },
      data: {
        step: agentStep,
        phase: "planning",
        theme: activeTheme,
        isActive: agentStatus === "in_progress",
        isCompleted: agentStatus === "completed",
        hasError: agentStatus === "error",
        statusLabel: agentStatus === "completed" ? "Finished" : agentStatus === "in_progress" ? "Running" : agentStatus === "error" ? "Error" : "Queued",
        sequenceIndex: 1,
        totalSteps,
        latestThinking: agentHighlights.join(" / ") || undefined,
        progressPercent: Math.min(100, Math.round((completedCount / branchCount) * 100)),
        parallelGroup: "fanout",
        sequence: 1,
      },
      draggable: true,
      connectable: false,
      dragHandle: '.process-node__drag-handle',
    });

    const halfSpread = (branchCount - 1) / 2;
    const branchEdgeColor = (status: FanoutBranchStatus) => {
      switch (status) {
        case "running":
          return "#60a5fa";
        case "completed":
          return "#34d399";
        case "failed":
          return "#f87171";
        case "stopped":
          return "#facc15";
        default:
          return "#94a3b8";
      }
    };

    branches.forEach((branch, index) => {
      const status = mapBranchStatus(branch.status);
      const offset = (index - halfSpread) * horizontalSpacing;
      const label = sanitizeLabel(branch);
      const latest = branch.status === "failed" && branch.error ? branch.error : branch.status === "running" ? "Executing tool" : branch.description;

      const branchStep: ProcessStep = {
        id: "fanout_tool_" + branch.id,
        name: label,
        status,
        thinking: latest ? [latest] : [],
        details: {
          metadata: branch.metadata,
          payload: branch.payload,
          error: branch.error,
          elapsedMs: branch.elapsedMs,
        },
        elapsed_ms: branch.elapsedMs,
        timestamp: branch.completedAt ?? branch.startedAt ?? undefined,
        parallelGroup: "fanout",
        sequence: index + 2,
      };

      nodesList.push({
        id: branchStep.id,
        type: "processNode",
        position: { x: centerX + offset, y: branchY },
        data: {
          step: branchStep,
          phase: "execution",
          theme: activeTheme,
          isActive: status === "in_progress",
          isCompleted: status === "completed",
          hasError: status === "error",
          statusLabel: status === "in_progress" ? "Running" : status === "completed" ? "Finished" : status === "error" ? "Error" : status === "stopped" ? "Stopped" : "Queued",
          sequenceIndex: index + 2,
          totalSteps,
          latestThinking: latest ?? undefined,
          progressPercent: Math.min(100, Math.round((completedCount / branchCount) * 100)),
          parallelGroup: "fanout",
          sequence: index + 2,
        },
        draggable: false,
        connectable: false,
      });

      const color = branchEdgeColor(branch.status);
      const dashed = branch.status === "queued" || branch.status === "stopped";

      edgesList.push({
        id: "edge-agent-" + branchStep.id,
        source: agentStep.id,
        target: branchStep.id,
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        type: "smoothstep",
        animated: branch.status === "running",
        style: {
          stroke: color,
          strokeWidth: branch.status === "running" ? 3 : 2,
          strokeDasharray: dashed ? "6 6" : undefined,
        },
        markerEnd: { type: "arrowclosed", color },
      });

      edgesList.push({
        id: "edge-" + branchStep.id + "-end",
        source: branchStep.id,
        target: "fanout_end",
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        type: "smoothstep",
        animated: branch.status === "running",
        style: {
          stroke: color,
          strokeWidth: 1.6,
          strokeDasharray: "8 8",
          strokeOpacity: 0.65,
        },
        markerEnd: { type: "arrowclosed", color },
      });
    });

    const endStatus: ProcessStep["status"] = failedCount > 0 ? "stopped" : (completedCount >= branchCount && activeCount === 0 && queuedCount === 0 ? "completed" : "pending");

    const endStep: ProcessStep = {
      id: "fanout_end",
      name: "__end__",
      status: endStatus,
      thinking: endStatus === "completed" ? ["All tool results collected"] : ["Awaiting remaining tools"],
      details: {
        completedCount,
        failedCount,
        queuedCount,
        stoppedCount,
        total: branchCount,
      },
      timestamp: fanout.lastUpdated ?? undefined,
      parallelGroup: "fanout",
      sequence: branchCount + 2,
    };

    nodesList.push({
      id: endStep.id,
      type: "processNode",
      position: { x: centerX, y: endY },
      data: {
        step: endStep,
        phase: "synthesis",
        theme: activeTheme,
        isActive: endStatus === "in_progress",
        isCompleted: endStatus === "completed",
        hasError: endStatus === "error",
        statusLabel: endStatus === "completed" ? "Finished" : endStatus === "stopped" ? "Stopped" : "Queued",
        sequenceIndex: branchCount + 2,
        totalSteps,
        latestThinking: endStatus === "completed" ? "Fan-out complete" : "Collecting results",
        progressPercent: Math.min(100, Math.round((completedCount / branchCount) * 100)),
        parallelGroup: "fanout",
        sequence: branchCount + 2,
      },
      draggable: true,
      connectable: false,
      dragHandle: '.process-node__drag-handle',
    });

    edgesList.push({
      id: "edge-start-agent",
      source: startStep.id,
      target: agentStep.id,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      type: "smoothstep",
      animated: false,
      style: {
        stroke: "#f9a8d4",
        strokeWidth: 2,
        strokeDasharray: "6 6",
      },
      markerEnd: { type: "arrowclosed", color: "#f472b6" },
    });

    edgesList.push({
      id: "edge-agent-end",
      source: agentStep.id,
      target: endStep.id,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      type: "smoothstep",
      animated: false,
      style: {
        stroke: "#facc15",
        strokeWidth: 1.8,
        strokeDasharray: "8 8",
      },
      markerEnd: { type: "arrowclosed", color: "#facc15" },
    });

    return { nodeConfigs: nodesList, edgeConfigs: edgesList };
  }, [fanout]);

  useEffect(() => {
    setNodes(nodeConfigs);
  }, [nodeConfigs, setNodes]);

  useEffect(() => {
    setEdges(edgeConfigs);
  }, [edgeConfigs, setEdges]);

  const translateExtent = useMemo(() => {
    if (!nodeConfigs.length) {
      return [
        [-400, -200],
        [400, 600],
      ] as [[number, number], [number, number]];
    }
    const xs = nodeConfigs.map((node) => node.position.x);
    const ys = nodeConfigs.map((node) => node.position.y);
    const minX = Math.min(...xs) - 260;
    const maxX = Math.max(...xs) + 260;
    const minY = Math.min(...ys) - 200;
    const maxY = Math.max(...ys) + 260;
    return [
      [minX, minY],
      [maxX, maxY],
    ] as [[number, number], [number, number]];
  }, [nodeConfigs]);

  const handleInit = useCallback((instance: ReactFlowInstance) => {
    instanceRef.current = instance;
    requestAnimationFrame(() => {
      instance.fitView({ padding: 0.18, includeHiddenNodes: true, duration: 320 });
    });
  }, []);

  const handleResetView = useCallback(() => {
    if (!instanceRef.current) {
      return;
    }
    instanceRef.current.fitView({ padding: 0.18, includeHiddenNodes: true, duration: 320 });
  }, []);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
      onInit={handleInit}
      fitView
      deleteKeyCode={null}
      panOnScroll
      nodesDraggable={false}
      nodesConnectable={false}
      zoomOnDoubleClick={false}
      panOnDrag
      proOptions={{ hideAttribution: true }}
      className="bg-transparent"
      translateExtent={translateExtent}
      fitViewOptions={{ padding: 0.18, includeHiddenNodes: true, duration: 320 }}
      minZoom={0.35}
      maxZoom={1.75}
      colorMode="dark"
    >
      <Controls
        className="bg-gray-800/80 text-white border border-gray-700"
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
        pannable
        zoomable
        maskColor="rgba(8, 11, 20, 0.75)"
        nodeColor={(node) => {
          const data = node.data as ProcessNodeData | undefined;
          if (!data) {
            return '#4b5563';
          }
          if (data.hasError) {
            return '#ef4444';
          }
          if (data.isActive) {
            return activeTheme.edgeActive;
          }
          if (data.isCompleted) {
            return activeTheme.edgeCompleted;
          }
          return activeTheme.edgeIdle;
        }}
      />
      <Background variant={BackgroundVariant.Lines} gap={32} size={1} color="#1f2937" />
    </ReactFlow>
  );
};

export const SingleAgentFanoutCanvas: React.FC<SingleAgentFanoutCanvasProps> = (props) => (
  <ReactFlowProvider>
    <SingleAgentFanoutCanvasInner {...props} />
  </ReactFlowProvider>
);

export default SingleAgentFanoutCanvas;
