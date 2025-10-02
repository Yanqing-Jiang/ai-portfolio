import React, { memo, useCallback, useMemo, useState } from 'react';
import { Handle, NodeProps, Position } from '@xyflow/react';
import { motion, AnimatePresence } from 'framer-motion';
import { ProcessStep, FlowVisualTheme } from '../types';

const MAX_DETAIL_ITEMS = 4;
const MAX_THOUGHTS = 4;

const LANE_LABELS: Record<string, string> = {
  overview: 'Overview',
  planner: 'Planner Agent',
  query: 'Query Agent',
  analyst: 'Analyst Agent',
  chart: 'Chart Agent',
  market: 'Market Agent',
  coordination: 'Coordination',
};

const LANE_BADGE_CLASS: Record<string, string> = {
  overview: 'bg-gray-900/60 text-gray-200 border border-gray-700/40',
  planner: 'bg-purple-500/25 text-purple-200 border border-purple-400/40',
  query: 'bg-sky-500/25 text-sky-200 border border-sky-400/40',
  analyst: 'bg-emerald-500/25 text-emerald-200 border border-emerald-400/40',
  chart: 'bg-amber-500/25 text-amber-200 border border-amber-400/40',
  market: 'bg-rose-500/25 text-rose-200 border border-rose-400/40',
  coordination: 'bg-slate-500/25 text-slate-200 border border-slate-400/40',
};

const defaultLaneBadge = 'bg-gray-900/60 text-gray-200 border border-gray-700/40';

interface ProcessNodeData {
  step: ProcessStep;
  phase: 'analysis' | 'planning' | 'execution' | 'synthesis';
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
}

const statusAccent = (status: ProcessStep['status']) => {
  switch (status) {
    case 'completed':
      return 'bg-emerald-500/30 text-emerald-200 border border-emerald-400/40';
    case 'in_progress':
      return 'bg-blue-500/30 text-blue-200 border border-blue-400/40';
    case 'error':
      return 'bg-red-500/30 text-red-200 border border-red-400/40';
    case 'stopped':
      return 'bg-yellow-500/30 text-yellow-200 border border-yellow-400/40';
    default:
      return 'bg-gray-600/30 text-gray-200 border border-gray-500/40';
  }
};

const formatTimestamp = (value?: string) => {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const formatDuration = (ms?: number) => {
  if (ms === undefined || ms === null) {
    return undefined;
  }
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${ms}ms`;
};

export const ProcessNode = memo<NodeProps<ProcessNodeData>>(({ data, selected }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const {
    step,
    phase,
    theme,
    isActive,
    isCompleted,
    hasError,
    statusLabel,
    sequenceIndex,
    totalSteps,
    latestThinking,
    currentStatus,
    currentDuration,
    currentTimestamp,
    parallelGroup,
    sequence,
  } = data;

  const laneLabel = parallelGroup ? LANE_LABELS[parallelGroup] ?? parallelGroup : undefined;
  const laneBadgeClass = parallelGroup ? LANE_BADGE_CLASS[parallelGroup] ?? defaultLaneBadge : defaultLaneBadge;

  const confidenceRaw = (step.details as any)?.confidence ?? (step.details as any)?.intent?.confidence;
  const confidenceValue = typeof confidenceRaw === 'number' ? confidenceRaw : undefined;
  const confidencePercent = typeof confidenceValue === 'number' ? Math.round(confidenceValue * 100) : undefined;

  const handleReplay = useCallback((event?: React.MouseEvent<HTMLButtonElement>) => {
    if (event) {
      event.stopPropagation();
    }
    const payload = {
      id: step.id,
      name: step.name,
      status: step.status,
      details: step.details,
      thinking: step.thinking,
    };
    const serialized = JSON.stringify(payload, null, 2);
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(serialized).catch(() => {});
    }
    console.info('[Workflow Replay]', step.id, payload);
  }, [step]);

  const nodeState = useMemo(() => {
    if (hasError || step.status === 'error') {
      return 'error';
    }
    if (isActive) {
      return 'active';
    }
    if (isCompleted) {
      return 'completed';
    }
    if (step.status === 'pending') {
      return 'pending';
    }
    return 'idle';
  }, [hasError, isActive, isCompleted, step.status]);

  const timestampLabel = formatTimestamp(step.timestamp);
  const durationLabel = formatDuration(step.elapsed_ms);
  const progress = totalSteps > 0 ? Math.round(((sequenceIndex + 1) / totalSteps) * 100) : 100;
  const details = step.details ?? {};
  const detailKeys = Object.keys(details).filter((key) => {
    const value = details[key as keyof typeof details];
    if (value === undefined || value === null) {
      return false;
    }
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    if (typeof value === 'object') {
      return Object.keys(value).length > 0;
    }
    if (typeof value === 'string') {
      return value.trim().length > 0;
    }
    return true;
  }).slice(0, MAX_DETAIL_ITEMS);

  const hasDetails = detailKeys.length > 0 || (step.thinking?.length ?? 0) > 0;
  const toggleExpand = useCallback(() => {
    if (!hasDetails) {
      return;
    }
    setIsExpanded((prev) => !prev);
  }, [hasDetails]);

  const expandLabel = isExpanded ? "Collapse" : "Expand";

  const motionVariant = {
    idle: {
      scale: 1,
      boxShadow: '0 6px 18px rgba(0,0,0,0.35)',
      transition: { duration: 0.35 },
    },
    active: {
      scale: [1, 1.03, 1],
      boxShadow: [
        '0 0 0 rgba(0,0,0,0)',
        `0 0 30px ${theme.accent}55`,
        `0 0 18px ${theme.accent}40`,
      ],
      transition: { duration: 1.4, repeat: Infinity, ease: 'easeInOut' },
    },
    completed: {
      scale: 1,
      boxShadow: `0 0 20px ${theme.accent}35`,
      transition: { duration: 0.4 },
    },
    error: {
      scale: [1, 1.02, 1],
      boxShadow: [
        '0 0 0 rgba(0,0,0,0)',
        '0 0 24px rgba(248,113,113,0.6)',
        '0 0 16px rgba(248,113,113,0.4)',
      ],
      transition: { duration: 0.9, repeat: Infinity, ease: 'easeInOut' },
    },
    pending: {
      scale: 1,
      boxShadow: '0 6px 18px rgba(0,0,0,0.35)',
      transition: { duration: 0.35 },
    },
  } as const;

  return (
    <motion.div
      initial="idle"
      animate={motionVariant[nodeState as keyof typeof motionVariant] ? nodeState : 'idle'}
      variants={motionVariant}
      className={`group relative flex w-72 flex-col overflow-hidden rounded-2xl border bg-gray-900/85 text-gray-100 transition ${theme.nodeBorder} ${theme.nodeGlow} ${selected ? 'ring-2 ring-offset-2 ring-offset-gray-900 ring-cyan-400' : ''}`}
      style={{ background: `linear-gradient(135deg, ${theme.nodeGradient[0]}, ${theme.nodeGradient[1]})` }}
      onDoubleClick={() => toggleExpand()}
    >
      <div className="flex items-center justify-between border-b border-white/5 px-4 py-3 text-xs uppercase tracking-wider text-gray-300">
        <div className="process-node__drag-handle flex items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-[10px] ${theme.badgeClass}`}>{phase.toUpperCase()}</span>
          <span className={`rounded-full px-2 py-0.5 text-[10px] ${statusAccent(step.status)}`}>{statusLabel}</span>
          {laneLabel && (
            <span className={`rounded-full px-2 py-0.5 text-[10px] ${laneBadgeClass}`}>{laneLabel}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-400">{String(sequenceIndex + 1).padStart(2, '0')} / {totalSteps}</span>
          <button
            type="button"
            onClick={handleReplay}
            onMouseDown={(event) => event.stopPropagation()}
            className="rounded-md border border-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-indigo-200 transition hover:border-white/25 hover:text-white focus:outline-none focus:ring-1 focus:ring-indigo-300/60 focus:ring-offset-2 focus:ring-offset-gray-900"
            title="Copy telemetry for replay"
          >
            Replay
          </button>
          {hasDetails && (
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                toggleExpand();
              }}
              onMouseDown={(event) => event.stopPropagation()}
              className="rounded-md border border-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-gray-200 transition hover:border-white/25 hover:text-white focus:outline-none focus:ring-1 focus:ring-white/60 focus:ring-offset-2 focus:ring-offset-gray-900"
              aria-expanded={isExpanded}
              aria-label={isExpanded ? 'Collapse node details' : 'Expand node details'}
            >
              {expandLabel}
            </button>
          )}
        </div>
      </div>

      <div className="px-4 py-3">
        <div className="flex items-start justify-between gap-2">
          <h4 className="text-sm font-semibold text-white">{step.name}</h4>
          {isCompleted && <span className="text-xs text-emerald-300">?</span>}
          {hasError && <span className="text-xs text-red-300">!</span>}
        </div>
        {latestThinking && <p className="mt-2 text-xs text-gray-200">{latestThinking}</p>}
        {!latestThinking && step.thinking?.length ? (
          <p className="mt-2 text-xs text-gray-300">{step.thinking[0]}</p>
        ) : null}

        <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] text-gray-400">
          {timestampLabel && <span>{timestampLabel}</span>}
          {durationLabel && <span>{durationLabel}</span>}
          {typeof sequence === 'number' && <span>Seq {sequence}</span>}
          {laneLabel && <span className="uppercase text-gray-200">{laneLabel}</span>}
          {typeof confidencePercent === 'number' && (
            <span className="rounded-full bg-gray-900/70 px-2 py-0.5 text-[10px] text-amber-200">Confidence {confidencePercent}%</span>
          )}
          {currentStatus && isActive && (
            <span className="rounded-full bg-gray-800/70 px-2 py-0.5 text-[10px] text-blue-200">{currentStatus}</span>
          )}
          {currentDuration && isActive && <span className="text-blue-300">{currentDuration}</span>}
        </div>

        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-gray-800/70">
          <div
            className={`h-full rounded-full ${isCompleted ? 'bg-emerald-400' : isActive ? theme.pulseClass : 'bg-gray-600'}`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            key="details"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="border-t border-white/5 bg-gray-950/70 px-4 py-3 text-xs text-gray-300"
          >
            {step.thinking?.length ? (
              <div className="mb-2 space-y-1">
                <div className="text-[10px] uppercase tracking-wider text-gray-500">Agent Thoughts</div>
                <ul className="space-y-1">
                  {step.thinking.slice(-MAX_THOUGHTS).map((thought, idx) => (
                    <li key={idx} className="leading-relaxed text-gray-300">- {thought}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {detailKeys.length > 0 && (
              <div className="space-y-2">
                <div className="text-[10px] uppercase tracking-wider text-gray-500">Telemetry</div>
                {detailKeys.map((key) => {
                  const value = details[key as keyof typeof details];
                  const display = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
                  return (
                    <div key={key} className="rounded-md bg-gray-900/80 p-2 text-[11px] text-gray-200">
                      <div className="text-[10px] uppercase text-gray-500">{key}</div>
                      <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap text-[11px] text-gray-200">{display}</pre>
                    </div>
                  );
                })}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <Handle type="target" position={Position.Left} id="left" className="!h-3 !w-3 !border-0 !bg-transparent" />
      <Handle type="source" position={Position.Right} id="right" className="!h-3 !w-3 !border-0 !bg-transparent" />
    </motion.div>
  );
});

ProcessNode.displayName = 'ProcessNode';














