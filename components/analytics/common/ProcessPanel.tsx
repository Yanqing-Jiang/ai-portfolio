import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Draggable from 'react-draggable';
import { WorkflowCanvas } from '../visualization/WorkflowCanvas';
import { ProcessStep, FlowMode } from '../types';

interface ProcessPanelProps {
  steps: ProcessStep[];
  flowMode: FlowMode;
  show: boolean;
  onClose: () => void;
  title?: string;
  subtitle?: string;
  draggable?: boolean;
  resizable?: boolean;
  defaultWidth?: number;
  minWidth?: number;
  maxWidth?: number;
}

interface PanelState {
  width: number;
  isMaximized: boolean;
  isDragging: boolean;
  position: { x: number; y: number };
}

type PaneFocus = 'canvas' | 'ledger';

type ExportFormat = 'csv' | 'json';

const STORAGE_KEY = 'processPanelState';
const PANE_KEY = 'processPanelFocusedPane';

const FLOW_META: Record<FlowMode, { title: string; accent: string; description: string }> = {
  'planner-executor': {
    title: 'Planner & Executor',
    accent: 'text-emerald-300',
    description: 'Deterministic SQL planning with ordered tool execution.',
  },
  'single-agent': {
    title: 'Single Agent + Tools',
    accent: 'text-blue-300',
    description: 'Autonomous agent orchestrating structured tool calls.',
  },
  'multi-agent': {
    title: 'Multi-Agent Relay',
    accent: 'text-purple-300',
    description: 'Coordinator handing work across planner, analyst, and viz roles.',
  },
};

const STATUS_STYLES: Record<ProcessStep['status'], { border: string; text: string; indicator: string; pill: string }> = {
  pending: {
    border: 'border-gray-600',
    text: 'text-gray-300',
    indicator: 'bg-gray-500',
    pill: 'bg-gray-700/60 text-gray-300',
  },
  in_progress: {
    border: 'border-blue-500/60',
    text: 'text-blue-200',
    indicator: 'bg-blue-400 animate-ping',
    pill: 'bg-blue-600/30 text-blue-200',
  },
  completed: {
    border: 'border-emerald-500/60',
    text: 'text-emerald-200',
    indicator: 'bg-emerald-400',
    pill: 'bg-emerald-600/30 text-emerald-200',
  },
  error: {
    border: 'border-red-500/70',
    text: 'text-red-200',
    indicator: 'bg-red-500',
    pill: 'bg-red-600/30 text-red-200',
  },
  stopped: {
    border: 'border-yellow-500/70',
    text: 'text-yellow-200',
    indicator: 'bg-yellow-400',
    pill: 'bg-yellow-600/30 text-yellow-200',
  },
};

const friendlyStatus = (status: ProcessStep['status']) => {
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

const formatDuration = (ms?: number) => {
  if (ms === undefined || ms === null) {
    return '';
  }
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${ms}ms`;
};

const formatTimestamp = (value?: string) => {
  if (!value) {
    return '';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '';
  }
  return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const isBrowser = typeof window !== 'undefined';

const exportStepsToCsv = (steps: ProcessStep[]) => {
  const header = ['stepNumber', 'id', 'name', 'status', 'timestamp', 'elapsedMs', 'latestThinking', 'sequence', 'parallelGroup'];
  const rows = steps.map((step, index) => {
    const latestThought = step.thinking?.slice(-1)[0] ?? '';
    return [
      String(index + 1),
      step.id,
      step.name.replace(/"/g, ''),
      friendlyStatus(step.status),
      step.timestamp ? new Date(step.timestamp).toISOString() : '',
      step.elapsed_ms != null ? String(step.elapsed_ms) : '',
      latestThought.replace(/"/g, ''),
      step.sequence !== undefined ? String(step.sequence) : '',
      step.parallelGroup ?? '',
    ];
  });
  return [header, ...rows]
    .map((cols) => cols.map((value) => `"${value.replace(/"/g, '""')}"`).join(','))
    .join('\n');
};

const downloadBlob = (content: string, filename: string, mime: string) => {
  if (!isBrowser) {
    return;
  }
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
};

export const ProcessPanel: React.FC<ProcessPanelProps> = ({
  steps,
  flowMode,
  show,
  onClose,
  title = 'Agent Thinking Process',
  subtitle = 'Live reasoning telemetry rendered as an interactive graph.',
  draggable = true,
  resizable = true,
  defaultWidth = 420,
  minWidth = 320,
  maxWidth = 1180,
}) => {
  const nodeRef = useRef<HTMLDivElement>(null);
  const [panelState, setPanelState] = useState<PanelState>(() => {
    if (!isBrowser) {
      return {
        width: defaultWidth,
        isMaximized: false,
        isDragging: false,
        position: { x: 0, y: 0 },
      };
    }
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as PanelState;
        return {
          width: parsed.width ?? defaultWidth,
          isMaximized: parsed.isMaximized ?? false,
          isDragging: false,
          position: parsed.position ?? { x: 0, y: 0 },
        };
      }
    } catch (error) {
      console.warn('Failed to load panel state', error);
    }
    return {
      width: defaultWidth,
      isMaximized: false,
      isDragging: false,
      position: { x: 0, y: 0 },
    };
  });

  const [focusedPane, setFocusedPane] = useState<PaneFocus>(() => {
    if (!isBrowser) {
      return 'canvas';
    }
    const cached = window.localStorage.getItem(PANE_KEY) as PaneFocus | null;
    return cached === 'ledger' ? 'ledger' : 'canvas';
  });

  const [expandedLedgerSteps, setExpandedLedgerSteps] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!isBrowser) {
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(panelState));
  }, [panelState]);

  useEffect(() => {
    if (!isBrowser) {
      return;
    }
    window.localStorage.setItem(PANE_KEY, focusedPane);
  }, [focusedPane]);

  const orderedSteps = useMemo(() => {
    if (!steps?.length) {
      return [] as ProcessStep[];
    }
    return [...steps]
      .map((step, index) => ({ step, index }))
      .sort((a, b) => {
        const tsA = a.step.timestamp ? Date.parse(a.step.timestamp) : Number.NaN;
        const tsB = b.step.timestamp ? Date.parse(b.step.timestamp) : Number.NaN;
        if (!Number.isNaN(tsA) && !Number.isNaN(tsB) && tsA !== tsB) {
          return tsA - tsB;
        }
        if (!Number.isNaN(tsA)) {
          return -1;
        }
        if (!Number.isNaN(tsB)) {
          return 1;
        }
        return a.index - b.index;
      })
      .map(({ step }) => step);
  }, [steps]);

  const workflowCompleted = useMemo(() => {
    if (!orderedSteps.length) {
      return false;
    }
    const hasPending = orderedSteps.some((step) => step.status === 'pending');
    const hasActive = orderedSteps.some((step) => step.status === 'in_progress');
    if (!hasPending && !hasActive) {
      return true;
    }
    const finalizationDone = orderedSteps.some((step) => step.id === 'finalization' && step.status === 'completed');
    const lastStep = orderedSteps[orderedSteps.length - 1];
    return finalizationDone || lastStep.status === 'completed';
  }, [orderedSteps]);

  const displaySteps = useMemo(() => {
    if (!workflowCompleted) {
      return orderedSteps;
    }
    return orderedSteps.map((step) => {
      if (step.status === 'completed' || step.status === 'error') {
        return step;
      }
      return { ...step, status: 'completed' };
    });
  }, [orderedSteps, workflowCompleted]);

  useEffect(() => {
    setExpandedLedgerSteps((prev) => {
      const next: Record<string, boolean> = {};
      displaySteps.forEach((step) => {
        next[step.id] = prev[step.id] ?? false;
      });
      return next;
    });
  }, [displaySteps]);

  const activeStep = useMemo(
    () => displaySteps.find((step) => step.status === 'in_progress'),
    [displaySteps],
  );

  const lastCompleted = useMemo(() => {
    for (let i = displaySteps.length - 1; i >= 0; i -= 1) {
      if (displaySteps[i].status === 'completed') {
        return displaySteps[i];
      }
    }
    return undefined;
  }, [displaySteps]);

  const contextStep = activeStep || lastCompleted || displaySteps[0];
  const contextStatus = contextStep?.status ?? 'pending';
  const contextStyle = STATUS_STYLES[contextStatus] ?? STATUS_STYLES.pending;

  const progressPercent = useMemo(() => {
    if (!displaySteps.length) {
      return 0;
    }
    if (workflowCompleted) {
      return 100;
    }
    const finished = displaySteps.filter((step) => step.status === 'completed' || step.status === 'error').length;
    return Math.round((finished / displaySteps.length) * 100);
  }, [displaySteps, workflowCompleted]);

  const handleStartDrag = () => setPanelState((prev) => ({ ...prev, isDragging: true }));
  const handleStopDrag = (_: unknown, data: { x: number; y: number }) => {
    setPanelState((prev) => ({ ...prev, isDragging: false, position: { x: data.x, y: data.y } }));
  };

  const toggleMaximize = () => setPanelState((prev) => ({
    ...prev,
    isMaximized: !prev.isMaximized,
    width: prev.isMaximized ? defaultWidth : maxWidth,
  }));

  const handleResize = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();

    const startX = event.clientX;
    const startWidth = panelState.width;

    const onMouseMove = (moveEvent: MouseEvent) => {
      const delta = startX - moveEvent.clientX;
      const nextWidth = Math.min(Math.max(startWidth + delta, minWidth), maxWidth);
      setPanelState((prev) => ({ ...prev, width: nextWidth }));
    };

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  const handlePaneCollapse = (pane: PaneFocus) => {
    setFocusedPane(pane === 'canvas' ? 'ledger' : 'canvas');
  };

  const handlePaneRestore = (pane: PaneFocus) => {
    setFocusedPane(pane);
  };

  const handleLedgerToggle = (stepId: string) => {
    setExpandedLedgerSteps((prev) => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  const handleExport = useCallback((format: ExportFormat) => {
    if (!displaySteps.length) {
      return;
    }
    if (format === 'csv') {
      const csv = exportStepsToCsv(displaySteps);
      downloadBlob(csv, 'agent-process-ledger.csv', 'text/csv;charset=utf-8;');
    } else {
      const json = JSON.stringify(displaySteps, null, 2);
      downloadBlob(json, 'agent-process-ledger.json', 'application/json;charset=utf-8;');
    }
  }, [displaySteps]);

  if (!show) {
    return null;
  }

  const flowMeta = FLOW_META[flowMode];
  const isCanvasExpanded = focusedPane === 'canvas';
  const isLedgerExpanded = focusedPane === 'ledger';

  const renderCollapsedPane = (label: string, description: string, onRestore: () => void) => (
    <button
      type="button"
      onClick={onRestore}
      className="flex h-12 items-center justify-between rounded-2xl border border-dashed border-gray-700 bg-gray-900/70 px-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-400 transition hover:border-gray-500 hover:text-gray-200"
    >
      <span>{label}</span>
      <span className="text-[11px] text-gray-500">{description}</span>
    </button>
  );

  const renderLedgerDetails = (step: ProcessStep) => {
    const detailEntries = Object.entries(step.details ?? {}).filter(([, value]) => {
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
    }).slice(0, 4);

    return (
      <div className="mt-3 space-y-3">
        {step.thinking?.length ? (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-gray-500">Agent Thoughts</div>
            <ul className="mt-1 space-y-1 text-[11px] text-gray-200">
              {step.thinking.slice(-4).map((thought, idx) => (
                <li key={idx} className="leading-relaxed">- {thought}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {detailEntries.length ? (
          <div className="space-y-2">
            <div className="text-[10px] uppercase tracking-wider text-gray-500">Telemetry</div>
            {detailEntries.map(([key, value]) => (
              <div key={key} className="rounded-lg bg-gray-900/80 p-3">
                <div className="text-[10px] uppercase text-gray-500">{key}</div>
                <pre className="mt-1 max-h-40 overflow-x-auto whitespace-pre-wrap text-[11px] text-gray-200">
                  {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
  };

  const renderLedger = () => (
    <div className="flex flex-1 min-h-0 flex-col rounded-3xl border border-gray-800 bg-gray-900/80 shadow-inner">
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3 text-sm font-semibold text-gray-200">
        <div className="flex items-center gap-2">
          <span>Insight Ledger</span>
          {workflowCompleted && (
            <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-200">
              All steps finished
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[11px] text-gray-400">
          <button
            type="button"
            onClick={() => handlePaneCollapse('ledger')}
            className="rounded border border-gray-700 px-2 py-1 text-[10px] uppercase tracking-wide transition hover:border-gray-500 hover:text-gray-200"
          >
            Collapse
          </button>
          <button
            type="button"
            onClick={() => handlePaneRestore('ledger')}
            className="rounded border border-gray-700 px-2 py-1 text-[10px] uppercase tracking-wide transition hover:border-gray-500 hover:text-gray-200"
            disabled={isLedgerExpanded}
          >
            Restore
          </button>
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto modern-scrollbar px-4 py-4 pr-2 sm:pr-4">
          {displaySteps.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-700 bg-gray-800/60 px-4 py-6 text-center text-sm text-gray-400">
              Waiting for telemetry.
            </div>
          ) : (
            <div className="space-y-3">
              {displaySteps.map((step, index) => {
                const style = STATUS_STYLES[step.status];
                const isExpanded = expandedLedgerSteps[step.id];
                const durationLabel = formatDuration(step.elapsed_ms);
                const timestampLabel = formatTimestamp(step.timestamp);
                return (
                  <div
                    key={step.id}
                    className={`rounded-2xl border ${style.border} bg-gray-900/70 p-3 transition shadow-sm hover:shadow-lg`}
                  >
                    <button
                      type="button"
                      onClick={() => handleLedgerToggle(step.id)}
                      className="flex w-full items-start justify-between gap-3 text-left"
                    >
                      <div className="flex flex-1 flex-col gap-2">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2 text-xs text-gray-400">
                              <span className={`inline-flex h-2 w-2 rounded-full ${style.indicator}`} />
                              <span className="font-semibold text-gray-100">
                                {`${String(index + 1).padStart(2, '0')} - ${step.name}`}
                              </span>
                              {typeof step.sequence === 'number' && (
                                <span className="rounded-full bg-gray-800/50 px-2 py-0.5 text-[10px] text-gray-300">#{step.sequence}</span>
                              )}
                              {step.parallelGroup && (
                                <span className="rounded-full bg-gray-800/50 px-2 py-0.5 text-[10px] uppercase tracking-wide text-gray-200">Lane {step.parallelGroup}</span>
                              )}
                            </div>
                            {step.thinking?.length ? (
                              <div className="text-[11px] text-gray-400">{step.thinking.slice(-1)[0]}</div>
                            ) : null}
                          </div>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide ${style.pill}`}>
                            {friendlyStatus(step.status)}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-3 text-[10px] text-gray-500">
                          {timestampLabel && <span>{timestampLabel}</span>}
                          {durationLabel && <span>{durationLabel}</span>}
                          {typeof step.sequence === 'number' && <span>{`Seq ${step.sequence}`}</span>}
                          {step.parallelGroup && <span className="uppercase text-gray-300">{`Lane ${step.parallelGroup}`}</span>}
                          <span>Toggle for full insight</span>
                        </div>
                      </div>
                    </button>
                    <AnimatePresence initial={false}>
                      {isExpanded && (
                        <motion.div
                          key="ledger-details"
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.24 }}
                          className="overflow-hidden border-t border-gray-800/60 pt-3"
                        >
                          {renderLedgerDetails(step)}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          )}
      </div>
    </div>
  );
  const renderCanvas = () => (
    <div className={`flex flex-1 flex-col rounded-3xl border ${contextStyle.border} bg-gray-900/80 shadow-inner`}>
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3 text-sm font-semibold text-gray-200">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-[11px] text-gray-400">
            <span className={`inline-flex h-2 w-2 rounded-full ${contextStyle.indicator}`} />
            <span className="uppercase tracking-wide text-gray-400">Query Planning & Template Selection</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-300">
            <span className="font-medium text-gray-100">{contextStep?.name ?? 'Awaiting events'}</span>
            <span className="rounded-full bg-gray-800/70 px-2 py-0.5 text-[10px] uppercase tracking-wide text-gray-400">
              {friendlyStatus(contextStatus)}
            </span>
            {contextStep?.elapsed_ms != null && (
              <span className="text-[10px] text-gray-500">{formatDuration(contextStep.elapsed_ms)}</span>
            )}
            {contextStep?.timestamp && (
              <span className="text-[10px] text-gray-500">{formatTimestamp(contextStep.timestamp)}</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-gray-400">
          <button
            type="button"
            onClick={() => handlePaneCollapse('canvas')}
            className="rounded border border-gray-700 px-2 py-1 text-[10px] uppercase tracking-wide transition hover:border-gray-500 hover:text-gray-200"
          >
            Collapse
          </button>
          <button
            type="button"
            onClick={() => handlePaneRestore('canvas')}
            className="rounded border border-gray-700 px-2 py-1 text-[10px] uppercase tracking-wide transition hover:border-gray-500 hover:text-gray-200"
            disabled={isCanvasExpanded}
          >
            Restore
          </button>
        </div>
      </div>
      <div className="relative flex-1 overflow-hidden">
        <WorkflowCanvas
          steps={displaySteps}
          flowMode={flowMode}
          isVisible
          currentStepLabel={contextStep?.name}
          currentStatus={friendlyStatus(contextStatus)}
          currentTimestamp={contextStep?.timestamp ?? undefined}
          currentDuration={formatDuration(contextStep?.elapsed_ms)}
          progressPercent={progressPercent}
        />
      </div>
    </div>
  );

  const containerClass = `relative flex h-full w-full flex-col border-l border-gray-800 bg-gray-900/95 text-gray-100 shadow-2xl ${panelState.isMaximized ? 'lg:w-[calc(100vw-4rem)]' : 'sm:max-w-[30rem]'}`;

  return (
    <AnimatePresence>
      <motion.div
        key="process-panel"
        initial={{ opacity: 0, x: 40 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 40 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-y-0 right-0 z-40 flex max-w-full"
      >
        <Draggable
          disabled={!draggable || panelState.isMaximized}
          position={panelState.isMaximized ? { x: 0, y: 0 } : panelState.position}
          onStart={handleStartDrag}
          onStop={handleStopDrag}
          nodeRef={nodeRef}
          bounds="parent"
        >
          <div
            ref={nodeRef}
            className={containerClass}
            style={panelState.isMaximized ? undefined : { width: panelState.width }}
          >
            <div className="flex items-center justify-between border-b border-gray-800 bg-gray-900/90 px-4 py-3">
              <div className="space-y-1">
                <div className="text-xs uppercase tracking-wide text-gray-400">{title}</div>
                <div className={`text-lg font-semibold ${flowMeta.accent}`}>{flowMeta.title}</div>
                <div className="text-[11px] text-gray-500">{subtitle}</div>
                <div className="text-[11px] text-gray-600">{flowMeta.description}</div>
              </div>
              <div className="flex flex-col items-end gap-2 text-xs text-gray-400">
                <div className="flex items-center gap-2">
                  <span className="rounded-full border border-gray-700 px-2 py-0.5 text-[10px] uppercase tracking-wide text-gray-300">
                    Progress {progressPercent}%
                  </span>
                  <button
                    type="button"
                    onClick={() => handleExport('csv')}
                    className="rounded border border-gray-700 px-2 py-0.5 text-[10px] uppercase tracking-wide transition hover:border-gray-500 hover:text-gray-200"
                    title="Download CSV"
                  >
                    CSV
                  </button>
                  <button
                    type="button"
                    onClick={() => handleExport('json')}
                    className="rounded border border-gray-700 px-2 py-0.5 text-[10px] uppercase tracking-wide transition hover:border-gray-500 hover:text-gray-200"
                    title="Download JSON"
                  >
                    JSON
                  </button>
                  {resizable && (
                    <button
                      type="button"
                      onClick={toggleMaximize}
                      className="rounded border border-gray-700 px-2 py-0.5 text-[10px] uppercase tracking-wide transition hover:border-gray-500 hover:text-gray-200"
                      title={panelState.isMaximized ? 'Restore panel size' : 'Maximize panel'}
                    >
                      {panelState.isMaximized ? 'Restore' : 'Maximize'}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={onClose}
                    className="rounded border border-red-600 px-2 py-0.5 text-[10px] uppercase tracking-wide text-red-300 transition hover:border-red-400 hover:text-red-100"
                    title="Close"
                  >
                    Close
                  </button>
                </div>
                {contextStep && (
                  <div className="flex items-center gap-2 text-[11px] text-gray-500">
                    <span className="font-medium text-gray-300">Now tracking:</span>
                    <span className="text-gray-200">{contextStep.name}</span>
                    <span>|</span>
                    <span>{friendlyStatus(contextStatus)}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
              {isCanvasExpanded ? renderCanvas() : renderCollapsedPane('Query Planning & Template Selection', 'Tap to restore canvas view', () => handlePaneRestore('canvas'))}
              {isLedgerExpanded ? renderLedger() : renderCollapsedPane('Insight Ledger', 'Tap to review finalized steps', () => handlePaneRestore('ledger'))}
            </div>

            {resizable && !panelState.isMaximized && (
              <div className="absolute inset-y-0 left-0 w-1 cursor-ew-resize" onMouseDown={handleResize} />
            )}
          </div>
        </Draggable>
      </motion.div>
    </AnimatePresence>
  );
};

export default ProcessPanel;



















