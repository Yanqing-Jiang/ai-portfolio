import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Draggable from 'react-draggable';
import { WorkflowCanvas } from '../visualization/WorkflowCanvas';
import { SingleAgentFanoutCanvas } from '../visualization/SingleAgentFanoutCanvas';
import {
  ProcessStep,
  FlowMode,
  SingleAgentFanout,
  FollowUpBanner,
  AnalysisOverview,
  AnalysisSources,
  SpecialistCard,
  ClarifyRequest,
  SlotStatusMap,
  SlotStatusPayload,
} from '../types';

interface ProcessPanelProps {
  singleAgentFanout?: SingleAgentFanout | null;
  steps: ProcessStep[];
  flowMode: FlowMode;
  show: boolean;
  onClose: () => void;
  showVisualization?: boolean;
  title?: string;
  subtitle?: string;
  draggable?: boolean;
  resizable?: boolean;
  defaultWidth?: number;
  minWidth?: number;
  maxWidth?: number;
  followUpBanner?: FollowUpBanner | null;
  slotStatuses?: SlotStatusMap | null;
  slotFollowups?: ClarifyRequest[] | null;
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
const FINAL_ANSWER_BANNER_KEY = 'aa.finalAnswerOnlyDismissed';

const FLOW_META: Record<FlowMode, { title: string; accent: string; description: string }> = {
  'planner-executor': {
    title: 'Direct Workflow',
    accent: 'text-emerald-300',
    description: 'Deterministic direct workflow with ordered tool execution.',
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

const SLOT_STATUS_THEME: Record<SlotStatusPayload['status'], { bg: string; text: string; border: string }> = {
  filled: { bg: 'bg-emerald-600/15', text: 'text-emerald-200', border: 'border-emerald-500/40' },
  defaulted: { bg: 'bg-sky-600/15', text: 'text-sky-200', border: 'border-sky-500/40' },
  assumed: { bg: 'bg-amber-600/15', text: 'text-amber-200', border: 'border-amber-500/40' },
  missing: { bg: 'bg-rose-600/15', text: 'text-rose-200', border: 'border-rose-500/40' },
};

const CURATED_METRICS = [
  "Revenue",
  "Net Income",
  "Capital Expenditures",
  "EPS Basic",
  "Income Before Tax",
  "Operating Income",
  "Stockholders' Equity",
  "R&D Expense",
  "Gross Profit",
];

const CURATED_METRIC_LOOKUP = new Map<string, string>(CURATED_METRICS.map((name) => [name.toLowerCase(), name]));
const TIMEFRAME_PRESETS: Record<string, string> = {
  last_4_quarters: "last 4 quarters",
  "last 4 quarters": "last 4 quarters",
  last_8_quarters: "last 8 quarters",
  "last 8 quarters": "last 8 quarters",
  last_5_years: "last 5 years",
  "last 5 years": "last 5 years",
  year_to_date: "year to date",
  "year to date": "year to date",
  ytd: "year to date",
  "year-to-date": "year to date",
};

const formatMetricValue = (raw: unknown): string | undefined => {
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (!trimmed) return undefined;
    const canonical = CURATED_METRIC_LOOKUP.get(trimmed.toLowerCase());
    if (canonical) return canonical;
    return trimmed.replace(/\b\w/g, (char) => char.toUpperCase());
  }
  if (raw != null) {
    return formatMetricValue(String(raw));
  }
  return undefined;
};

const formatMetricStatusValue = (raw: unknown): string | undefined => {
  if (Array.isArray(raw)) {
    const mapped = raw.map((entry) => formatMetricValue(entry)).filter(Boolean) as string[];
    if (mapped.length) {
      const unique = Array.from(new Set(mapped));
      return unique.join(', ');
    }
    return undefined;
  }
  return formatMetricValue(raw);
};

const formatTimeframeValue = (raw: unknown): string | undefined => {
  if (!raw) {
    return undefined;
  }
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (!trimmed) return undefined;
    const presetMatch = TIMEFRAME_PRESETS[trimmed.toLowerCase()];
    return presetMatch ?? trimmed;
  }
  if (typeof raw === 'object') {
    const value = raw as Record<string, unknown>;
    const presetSource =
      typeof value['preset'] === 'string'
        ? (value['preset'] as string)
        : typeof value['value'] === 'string'
        ? (value['value'] as string)
        : undefined;
    if (presetSource) {
      const presetMatch = TIMEFRAME_PRESETS[presetSource.toLowerCase()];
      if (presetMatch) {
        return presetMatch;
      }
    }
    const yearToDate = value['year_to_date'];
    if (yearToDate === true) {
      return 'year to date';
    }
    const yearsBack = value['years_back'];
    if (typeof yearsBack === 'number' && Number.isFinite(yearsBack)) {
      const years = Math.max(0, Math.floor(yearsBack));
      if (years > 0) {
        return `last ${years} year${years === 1 ? '' : 's'}`;
      }
    }
    const quartersBack = value['quarters_back'];
    if (typeof quartersBack === 'number' && Number.isFinite(quartersBack)) {
      const quarters = Math.max(0, Math.floor(quartersBack));
      if (quarters > 0) {
        return `last ${quarters} quarter${quarters === 1 ? '' : 's'}`;
      }
    }
  }
  return undefined;
};

const formatSlotLabel = (slot: string): string => {
  if (!slot) return 'Unknown';
  return slot
    .replace(/_/g, ' ')
    .replace(/\\./g, ' ')
    .replace(/\\s+/g, ' ')
    .trim()
    .replace(/^[a-z]/, (match) => match.toUpperCase());
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

const formatScheduleStage = (value?: string) => {
  if (!value) {
     return '';
  }
  return value.replace(/[_-]/g, ' ').replace(/\b\w/g, (match) => match.toUpperCase());
};

const createCircularReplacer = () => {
  const seen = new WeakSet();
  return (_key: string, value: any) => {
    if (typeof value === 'object' && value !== null) {
      if (seen.has(value)) {
        return '[Circular]';
      }
      seen.add(value);
    }
    return value;
  };
};

const formatDetailValue = (value: unknown): string => {
  if (typeof value === 'string') {
    return value;
  }
  try {
    const serialized = JSON.stringify(value, createCircularReplacer(), 2);
    if (serialized) {
      return serialized;
    }
  } catch {
    // fall through to best-effort formatting
  }
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'object') {
    return '[Unserializable telemetry]';
  }
  return String(value);
};

const isBrowser = typeof window !== 'undefined';

export const exportStepsToCsv = (steps: ProcessStep[]) => {
  const header = [
    'stepNumber',
    'id',
    'name',
    'status',
    'timestamp',
    'elapsedMs',
    'latestThinking',
    'sequence',
    'parallelGroup',
    'lane',
    'reused',
    'analysisSources',
    'finalAnswerOnly',
  ];

  const formatAnalysisSources = (step: ProcessStep): string => {
    const candidate =
      (step.analysisSources as AnalysisSources | undefined) ??
      ((step.details as any)?.analysis_sources as AnalysisSources | undefined);
    if (!candidate || typeof candidate !== 'object') {
      return '';
    }
    const entries = Object.entries(candidate);
    if (!entries.length) {
      return '';
    }
    return entries
      .map(([key, meta]) => {
        if (!meta || typeof meta !== 'object') {
          return key;
        }
        const lane = typeof meta.lane === 'string' && meta.lane && meta.lane !== key ? meta.lane : undefined;
        const reused =
          typeof meta.reused === 'boolean' ? (meta.reused ? 'reused' : 'fresh') : undefined;
        const summary = typeof meta.summary === 'string' && meta.summary.trim().length ? meta.summary.trim() : undefined;
        const symbols =
          Array.isArray((meta as any).symbols) && (meta as any).symbols.length
            ? `symbols:${(meta as any).symbols.slice(0, 3).join('/')}`
            : undefined;
        const descriptorParts = [lane ?? key];
        if (reused) {
          descriptorParts.push(`[${reused}]`);
        }
        if (summary) {
          descriptorParts.push(summary);
        }
        if (symbols) {
          descriptorParts.push(symbols);
        }
        return descriptorParts.join(' ');
      })
      .join(' | ');
  };

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
      step.lane ?? '',
      step.reused === undefined ? '' : String(step.reused),
      formatAnalysisSources(step),
      step.finalAnswerOnly === undefined ? '' : String(step.finalAnswerOnly),
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
  singleAgentFanout = null,
  show,
  onClose,
  showVisualization = true,
  title = 'Agent Thinking Process',
  subtitle = 'Live reasoning telemetry rendered as an interactive graph.',
  draggable = true,
  resizable = true,
  defaultWidth = 420,
  minWidth = 320,
  maxWidth = 1180,
  followUpBanner = null,
  slotStatuses = null,
  slotFollowups = null,
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
    if (!showVisualization) {
      return 'ledger';
    }
    if (!isBrowser) {
      return 'canvas';
    }
    const cached = window.localStorage.getItem(PANE_KEY) as PaneFocus | null;
    return cached === 'ledger' ? 'ledger' : 'canvas';
  });

  const [expandedLedgerSteps, setExpandedLedgerSteps] = useState<Record<string, boolean>>({});
  const [dismissedFinalAnswerSignature, setDismissedFinalAnswerSignature] = useState<string | null>(() => {
    if (!isBrowser) {
      return null;
    }
    try {
      const raw = window.localStorage.getItem(FINAL_ANSWER_BANNER_KEY);
      if (!raw) {
        return null;
      }
      if (raw === 'true') {
        return '__legacy__';
      }
      return raw;
    } catch (error) {
      console.warn('Failed to load final answer banner state', error);
      return null;
    }
  });

  const bannerSignature = useMemo(() => {
    if (!followUpBanner) {
      return null;
    }
    const signatureParts = [
      followUpBanner.title ?? '',
      followUpBanner.message ?? '',
      followUpBanner.route ?? '',
      followUpBanner.finalAnswerOnly ? 'final' : '',
    ];
    return signatureParts.join('|').toLowerCase();
  }, [followUpBanner]);

  const shouldRenderFollowUpBanner = useMemo(() => {
    if (!followUpBanner) {
      return false;
    }
    if (!followUpBanner.finalAnswerOnly) {
      return true;
    }
    if (!bannerSignature) {
      return dismissedFinalAnswerSignature !== '__any__' && dismissedFinalAnswerSignature !== '__legacy__';
    }
    if (dismissedFinalAnswerSignature === '__any__' || dismissedFinalAnswerSignature === '__legacy__') {
      return false;
    }
    return dismissedFinalAnswerSignature !== bannerSignature;
  }, [followUpBanner, bannerSignature, dismissedFinalAnswerSignature]);

  useEffect(() => {
    if (!isBrowser) {
      return;
    }
    if (!dismissedFinalAnswerSignature) {
      window.localStorage.removeItem(FINAL_ANSWER_BANNER_KEY);
      return;
    }
    try {
      window.localStorage.setItem(FINAL_ANSWER_BANNER_KEY, dismissedFinalAnswerSignature);
    } catch (error) {
      console.warn('Failed to persist final answer banner state', error);
    }
  }, [dismissedFinalAnswerSignature]);

  useEffect(() => {
    if (!isBrowser) {
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(panelState));
  }, [panelState]);

  useEffect(() => {
    if (!isBrowser || !showVisualization) {
      return;
    }
    window.localStorage.setItem(PANE_KEY, focusedPane);
  }, [focusedPane, showVisualization]);

  useEffect(() => {
    if (!showVisualization) {
      setFocusedPane('ledger');
    }
  }, [showVisualization]);

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

  const handleDismissFollowUpBanner = useCallback(() => {
    if (!followUpBanner?.finalAnswerOnly) {
      return;
    }
    const signature = bannerSignature ?? '__any__';
    setDismissedFinalAnswerSignature(signature);
  }, [followUpBanner, bannerSignature]);

  if (!show) {
    return null;
  }

  const flowMeta = FLOW_META[flowMode] ?? FLOW_META['planner-executor'];
  const isCanvasExpanded = showVisualization && focusedPane === 'canvas';
  const isLedgerExpanded = !showVisualization || focusedPane === 'ledger';

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
    const details = (step.details ?? {}) as {
      banner?: FollowUpBanner;
      analysis_overview?: AnalysisOverview;
      specialist_card?: SpecialistCard;
      latency?: { total_ms?: number; p50_ms?: number; max_ms?: number; min_ms?: number; samples?: number };
      [key: string]: any;
    };
    const { banner, analysis_overview, analysis_sources, specialist_card, latency, latency_guardrail, web_context: _webContext, ...otherDetails } = details;
    const evidenceEntries = analysis_overview?.evidence ?? [];
    const analysisSourceEntries = normalizeAnalysisSources(analysis_sources as AnalysisSources | undefined);
    const hasEvidence = evidenceEntries.length > 0;
    const lowConfidenceEvidence =
      hasEvidence && evidenceEntries.every((entry) => (entry.confidence ?? 0) < 0.35);
    const finalAnswerOnly =
      step.finalAnswerOnly ??
      (typeof details.final_answer_only === 'boolean'
        ? details.final_answer_only
        : typeof details.final_answer_only === 'string'
        ? details.final_answer_only.toLowerCase() === 'true'
        : undefined);
    const missingComponents =
      step.missingComponents ??
      (Array.isArray(details.missing_components)
        ? (details.missing_components as unknown[])
            .map((component) => (typeof component === 'string' ? component : String(component)))
            .filter((component) => component.trim().length > 0)
        : undefined);
    const followUpRoute =
      step.followUpRoute ??
      (typeof details.follow_up_route === 'string' ? details.follow_up_route : banner?.route);
    const analysisAvailable =
      step.analysisAvailable ??
      (typeof details.analysis_available === 'boolean'
        ? details.analysis_available
        : undefined);
    const resolvedFinalAnswerOnly = banner?.finalAnswerOnly ?? finalAnswerOnly;
    const resolvedMissingComponents = banner?.missingComponents?.length
      ? banner.missingComponents
      : missingComponents;
    const resolvedAnalysisAvailable =
      banner?.analysisAvailable !== undefined ? banner.analysisAvailable : analysisAvailable;
    const resolvedFollowUpRoute = banner?.route ?? followUpRoute ?? 'full_pipeline';

    const detailEntries = Object.entries(otherDetails)
      .filter(([, value]) => {
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
      })
      .slice(0, 4);

    const slotStatusSource = (details.slot_statuses as SlotStatusMap | undefined) ?? slotStatuses ?? undefined;
    const slotStatusEntries = slotStatusSource ? Object.entries(slotStatusSource) : [];
    const detailFollowupsRaw = Array.isArray(details.slot_followups) ? details.slot_followups : undefined;
    const combinedFollowups = detailFollowupsRaw ?? slotFollowups ?? [];
    const followupHints = combinedFollowups
      .map((hint) => {
        const slotId = typeof (hint as any)?.slot === 'string' ? (hint as any).slot : undefined;
        if (!slotId) return null;
        const prompt = typeof (hint as any)?.prompt === 'string'
          ? (hint as any).prompt
          : typeof (hint as any)?.question === 'string'
          ? (hint as any).question
          : undefined;
        const suggestions = Array.isArray((hint as any)?.suggestions)
          ? (hint as any).suggestions
          : Array.isArray((hint as any)?.options)
          ? (hint as any).options
          : [];
        return { slot: slotId, prompt, suggestions };
      })
      .filter((entry): entry is { slot: string; prompt?: string; suggestions: string[] } => entry !== null);
    const showSlotStatuses = (step.id === 'intent_detection' || step.id === 'clarification') && slotStatusEntries.length > 0;
    const showFollowupHints = (step.id === 'intent_detection' || step.id === 'clarification') && followupHints.length > 0;

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
        {banner ? (
          <div className="rounded-xl border border-amber-400/40 bg-amber-500/10 p-3 text-amber-100 shadow-inner">
            <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wide text-amber-300">
              <span className="font-semibold">{banner.title}</span>
              <span className="rounded-full border border-amber-300/60 px-2 py-0.5 text-[9px] font-semibold text-amber-200">
                {formatScheduleStage(resolvedFollowUpRoute)}
              </span>
            </div>
            <div className="mt-1 text-[11px] leading-relaxed">{banner.message}</div>
            {(resolvedFinalAnswerOnly || (resolvedMissingComponents?.length ?? 0) > 0 || resolvedAnalysisAvailable === false) && (
              <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-wide">
                {resolvedFinalAnswerOnly ? (
                  <span className="rounded-full border border-amber-300/60 bg-amber-600/10 px-2 py-0.5 text-amber-200">
                    Final Answer Only
                  </span>
                ) : null}
                {resolvedMissingComponents?.length ? (
                  <span className="rounded-full border border-amber-300/60 bg-amber-600/10 px-2 py-0.5 text-amber-200">
                    Missing: {resolvedMissingComponents.map((component) => formatScheduleStage(component)).join(', ')}
                  </span>
                ) : null}
                {resolvedAnalysisAvailable === false ? (
                  <span className="rounded-full border border-amber-300/60 bg-amber-600/10 px-2 py-0.5 text-amber-200">
                    Analysis Pending
                  </span>
                ) : null}
              </div>
            )}
          </div>
        ) : null}
        {!banner && resolvedFinalAnswerOnly ? (
          <div className="rounded-xl border border-amber-400/40 bg-amber-500/10 p-3 text-amber-100 shadow-inner">
            <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wide text-amber-300">
              <span className="font-semibold">Guided Final Answer</span>
              <span className="rounded-full border border-amber-300/60 px-2 py-0.5 text-[9px] font-semibold text-amber-200">
                {formatScheduleStage(resolvedFollowUpRoute)}
              </span>
            </div>
            {resolvedMissingComponents?.length ? (
              <div className="mt-1 text-[11px] leading-relaxed">
                Missing lanes: {resolvedMissingComponents.map((component) => formatScheduleStage(component)).join(', ')}
              </div>
            ) : null}
            {resolvedAnalysisAvailable === false ? (
              <div className="mt-1 text-[11px] leading-relaxed">Fresh analysis required for a full answer.</div>
            ) : null}
          </div>
        ) : null}
        {analysis_overview ? (
          <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-emerald-100/90">
            {analysis_overview.tldr ? (
              <div>
                <div className="text-[10px] uppercase tracking-wide text-emerald-300">Quick Take</div>
                <div className="mt-1 text-[11px] leading-relaxed">{analysis_overview.tldr}</div>
              </div>
            ) : null}
            {analysis_overview.highlights?.length ? (
              <div className="mt-2">
                <div className="text-[10px] uppercase tracking-wide text-emerald-300">Key Highlights</div>
                <ul className="mt-1 space-y-1 text-[11px] leading-relaxed">
                  {analysis_overview.highlights.slice(0, 3).map((highlight, idx) => (
                    <li key={idx}>- {highlight}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {analysis_overview.keyNumbers?.length ? (
              <div className="mt-2">
                <div className="text-[10px] uppercase tracking-wide text-cyan-300">Key Numbers</div>
                <ul className="mt-1 space-y-1 text-[11px] leading-relaxed text-cyan-100/90">
                  {analysis_overview.keyNumbers.map((entry, idx) => (
                    <li key={idx}>- {entry}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {analysis_overview.riskWatch?.length ? (
              <div className="mt-2">
                <div className="text-[10px] uppercase tracking-wide text-amber-300">Risk Watch</div>
                <ul className="mt-1 space-y-1 text-[11px] leading-relaxed text-amber-100/90">
                  {analysis_overview.riskWatch.map((entry, idx) => (
                    <li key={idx}>- {entry}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {analysis_overview.nextSteps?.length ? (
              <div className="mt-2">
                <div className="text-[10px] uppercase tracking-wide text-sky-300">Next Steps</div>
                <ul className="mt-1 space-y-1 text-[11px] leading-relaxed text-sky-100/90">
                  {analysis_overview.nextSteps.map((entry, idx) => (
                    <li key={idx}>- {entry}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {hasEvidence ? (
              <div className="mt-2">
                <div className="text-[10px] uppercase tracking-wide text-emerald-200">Sources</div>
                <ul className="mt-1 space-y-1 text-[11px] leading-relaxed text-emerald-100/90">
                  {evidenceEntries.map((entry, idx) => (
                    <li key={`${entry.sourceUrl}-${idx}`} className="flex flex-col">
                      <a
                        href={entry.sourceUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-emerald-200 underline hover:text-emerald-100"
                      >
                        {entry.title ?? entry.displayUrl ?? `Source ${idx + 1}`}
                      </a>
                      {(entry.claim || entry.snippet) && (
                        <span className="text-[10px] text-emerald-200/80">{entry.claim || entry.snippet}</span>
                      )}
                      {typeof entry.confidence === 'number' && (
                        <span className="text-[10px] text-emerald-200/60">
                          Confidence: {Math.round(entry.confidence * 100)}%
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
                {lowConfidenceEvidence && (
                  <div className="mt-2 text-[11px] text-amber-300">
                    Sources flagged for low confidenceconsider re-running web research.
                  </div>
                )}
              </div>
            ) : (
              <div className="mt-2 text-[11px] text-amber-200">
                No grounded sources returned. Consider re-running web research to collect citations.
              </div>
            )}
          </div>
        ) : null}
        {latency ? (
          <div className="rounded-xl border border-amber-300/40 bg-amber-500/10 p-3 text-amber-100/90">
            <div className="text-[10px] uppercase tracking-wide text-amber-300">Web Search Latency</div>
            <div className="mt-1 text-[11px] leading-relaxed space-y-1">
              {typeof latency.total_ms === 'number' ? <div>Total: {latency.total_ms} ms</div> : null}
              {typeof latency.p50_ms === 'number' ? <div>p50: {latency.p50_ms} ms</div> : null}
              {typeof latency.max_ms === 'number' ? <div>Max: {latency.max_ms} ms</div> : null}
              {typeof latency.min_ms === 'number' ? <div>Min: {latency.min_ms} ms</div> : null}
              {typeof latency.samples === 'number' ? <div>Samples: {latency.samples}</div> : null}
            </div>
          </div>
        ) : null}
        {latency_guardrail ? (
          <div
            className={`rounded-xl border p-3 ${
              latency_guardrail.status === 'violation'
                ? 'border-amber-500/50 bg-amber-600/10 text-amber-100/90'
                : 'border-emerald-500/40 bg-emerald-600/10 text-emerald-100/90'
            }`}
          >
            <div className="text-[10px] uppercase tracking-wide">
              Guardrail Status: {latency_guardrail.status === 'violation' ? 'Exceeded' : 'Within Thresholds'}
            </div>
            {latency_guardrail.violations?.length ? (
              <div className="mt-1 text-[11px] leading-relaxed">
                Tripped: {latency_guardrail.violations.join(', ')}
              </div>
            ) : null}
            {latency_guardrail.thresholds ? (
              <div className="mt-1 text-[11px] leading-relaxed text-emerald-200/80">
                Targets: p50 = {latency_guardrail.thresholds.p50_ms ?? 'N/A'} ms{' '}
                p95 = {latency_guardrail.thresholds.p95_ms ?? 'N/A'} ms
              </div>
            ) : null}
          </div>
        ) : null}
        {specialist_card ? (
          <div className="rounded-xl border border-sky-500/40 bg-sky-500/10 p-3 text-sky-100/90">
            <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-sky-200">
              <span className="font-semibold">
                {specialist_card.title ?? formatScheduleStage(specialist_card.type)}
              </span>
              {specialist_card.state && <span>{formatScheduleStage(specialist_card.state)}</span>}
            </div>
            {(specialist_card.lane || specialist_card.parallelGroup || specialist_card.reused) ? (
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[9px] uppercase tracking-wide text-sky-300">
                {specialist_card.lane && (
                  <span className="rounded-full border border-sky-400/40 bg-sky-500/20 px-2 py-0.5 text-sky-100">
                    Lane {formatScheduleStage(specialist_card.lane)}
                  </span>
                )}
                {!specialist_card.lane && specialist_card.parallelGroup && (
                  <span className="rounded-full border border-sky-400/40 bg-sky-500/20 px-2 py-0.5 text-sky-100">
                    Group {formatScheduleStage(specialist_card.parallelGroup)}
                  </span>
                )}
                {specialist_card.reused ? (
                  <span className="rounded-full border border-emerald-400/60 bg-emerald-500/20 px-2 py-0.5 text-emerald-100">
                    Cached
                  </span>
                ) : null}
              </div>
            ) : null}
            {specialist_card.message && (
              <div className="mt-1 text-[11px] leading-relaxed">{specialist_card.message}</div>
            )}
            {specialist_card.topic && (
              <div className="mt-1 text-[10px] uppercase tracking-wide text-sky-300/90">
                Focus: <span className="normal-case text-sky-100/90">{specialist_card.topic}</span>
              </div>
            )}
            {specialist_card.summary && (
              <div className="mt-1 text-[11px] leading-relaxed text-sky-100/90">
                {specialist_card.summary}
              </div>
            )}
            {specialist_card.snippets?.length ? (
              <ul className="mt-2 space-y-1 text-[11px] leading-relaxed">
                {specialist_card.snippets.slice(0, 2).map((snippet, idx) => (
                  <li key={idx} className="border-l-2 border-sky-400/50 pl-2">
                    {snippet.title || snippet.snippet}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
        {showSlotStatuses ? (
          <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-3">
            <div className="text-[10px] uppercase tracking-wide text-blue-200">Slot Status</div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {slotStatusEntries.map(([slotName, payload]) => {
                const theme = SLOT_STATUS_THEME[payload.status] ?? SLOT_STATUS_THEME.missing;
                const suggestions = Array.isArray(payload.suggestions) ? payload.suggestions : [];
                const fallbackSuggestions = suggestions
                  .map((item) => {
                    if (item === null || item === undefined) return undefined;
                    const text = String(item).trim();
                    return text.length > 0 ? text : undefined;
                  })
                  .filter((entry): entry is string => Boolean(entry));
                let valueText: string | undefined;
                if (slotName === 'metric') {
                  const source = payload.value !== undefined ? payload.value : suggestions;
                  valueText = formatMetricStatusValue(source);
                } else if (slotName === 'timeframe') {
                  const source = payload.value !== undefined ? payload.value : suggestions;
                  if (Array.isArray(source)) {
                    const formatted = source
                      .map((entry) => formatTimeframeValue(entry))
                      .filter(Boolean) as string[];
                    valueText = formatted.length ? formatted[0] : undefined;
                  } else {
                    valueText = formatTimeframeValue(source);
                  }
                } else if (payload.value !== undefined && payload.value !== null && payload.value !== '') {
                  valueText = String(payload.value);
                }
                const formattedSuggestions =
                  slotName === 'metric'
                    ? suggestions
                        .map((item) => {
                          const formatted = formatMetricValue(item);
                          if (formatted) return formatted;
                          return typeof item === 'string' ? item : undefined;
                        })
                        .filter((entry): entry is string => Boolean(entry))
                    : slotName === 'timeframe'
                    ? suggestions
                        .map((item) => {
                          const formatted = formatTimeframeValue(item);
                          if (formatted) return formatted;
                          return typeof item === 'string' ? item : undefined;
                        })
                        .filter((entry): entry is string => Boolean(entry))
                    : fallbackSuggestions;
                return (
                  <div
                    key={`${step.id}-${slotName}`}
                    className={`rounded-lg border ${theme.border} ${theme.bg} px-3 py-2 text-[11px] ${theme.text}`}
                  >
                    <div className="text-[10px] uppercase tracking-wide opacity-80">{formatSlotLabel(slotName)}</div>
                    <div className="font-semibold">
                      {payload.status.charAt(0).toUpperCase() + payload.status.slice(1)}
                      {valueText ? `  ${valueText}` : ''}
                    </div>
                    {payload.reason ? (
                      <div className="mt-1 text-[10px] opacity-80">{payload.reason}</div>
                    ) : null}
                    {payload.status === 'missing' && formattedSuggestions.length > 0 ? (
                      <div className="mt-1 text-[10px] opacity-70">
                        Suggestions: {formattedSuggestions.slice(0, 3).join(', ')}
                        {formattedSuggestions.length > 3 ? ', ' : ''}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}

        {showFollowupHints ? (
          <div className="rounded-xl border border-blue-400/30 bg-blue-500/5 p-3">
            <div className="text-[10px] uppercase tracking-wide text-blue-200">Awaiting Clarification</div>
            <ul className="mt-2 space-y-1 text-[11px] leading-relaxed text-gray-200">
              {followupHints.map((hint) => (
                <li key={`${step.id}-${hint.slot}`}>
                  <span className="font-semibold text-blue-100">{formatSlotLabel(hint.slot)}</span>
                  {hint.prompt ? `  ${hint.prompt}` : ''}
                  {Array.isArray(hint.suggestions) && hint.suggestions.length ? (
                    <span className="ml-1 text-blue-200/70">
                      ({hint.suggestions.slice(0, 3).join(', ')}
                      {hint.suggestions.length > 3 ? ', ' : ''})
                    </span>
                  ) : null}
                </li>
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
                    {formatDetailValue(value)}
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
                const rawName = step.name || formatScheduleStage(step.id);
                const displayName = step.reused ? `${rawName} (cached)` : rawName;
                const laneLabel = step.lane ?? step.parallelGroup;
                const laneDisplay = laneLabel ? formatScheduleStage(laneLabel) : null;
                const missingComponentsLabel = step.missingComponents?.length
                  ? step.missingComponents.map((component) => formatScheduleStage(component)).join(', ')
                  : null;
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
                                {`${String(index + 1).padStart(2, '0')} - ${displayName}`}
                              </span>
                              {typeof step.sequence === 'number' && (
                                <span className="rounded-full bg-gray-800/50 px-2 py-0.5 text-[10px] text-gray-300">#{step.sequence}</span>
                              )}
                              {laneDisplay && (
                                <span className="rounded-full bg-gray-800/50 px-2 py-0.5 text-[10px] uppercase tracking-wide text-gray-200">
                                  {laneLabel === 'coordination' ? 'Coordinator Lane' : `Lane ${laneDisplay}`}
                                </span>
                              )}
                              {step.scheduleStage && (
                                <span className="rounded-full bg-indigo-800/50 px-2 py-0.5 text-[10px] uppercase tracking-wide text-indigo-200">
                                  Stage {formatScheduleStage(step.scheduleStage)}
                                </span>
                              )}
                              {step.flowMode && (
                                <span className="rounded-full bg-purple-800/50 px-2 py-0.5 text-[10px] uppercase tracking-wide text-purple-200">
                                  {formatScheduleStage(step.flowMode)}
                                </span>
                              )}
                              {step.reused && (
                                <span className="rounded-full border border-emerald-400/60 bg-emerald-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-emerald-200">
                                  Cached
                                </span>
                              )}
                              {step.finalAnswerOnly && (
                                <span className="rounded-full border border-amber-400/60 bg-amber-500/15 px-2 py-0.5 text-[10px] uppercase tracking-wide text-amber-200">
                                  Final Answer Only
                                </span>
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
                          {laneDisplay && <span className="uppercase text-gray-300">{`Lane ${laneDisplay}`}</span>}
                          {step.scheduleStage && (
                            <span className="uppercase text-indigo-300">{formatScheduleStage(step.scheduleStage)}</span>
                          )}
                          {step.analysisAvailable === false && (
                            <span className="uppercase text-amber-300">Analysis Pending</span>
                          )}
                          {missingComponentsLabel && (
                            <span className="uppercase text-amber-200">{`Missing: ${missingComponentsLabel}`}</span>
                          )}
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
  const renderCanvas = () => {
    const isFanoutMode = flowMode === 'single-agent' && !!singleAgentFanout?.hasFanout && (singleAgentFanout?.branches.length ?? 0) > 0;
    const activeCount = singleAgentFanout?.runningCount ?? 0;
    const completedCount = singleAgentFanout?.completedCount ?? 0;
    const failedCount = singleAgentFanout?.failedCount ?? 0;
    const queuedCount = singleAgentFanout?.queuedCount ?? 0;

    return (
      <div className={`flex flex-1 flex-col rounded-3xl border ${contextStyle.border} bg-gray-900/80 shadow-inner`}>
        <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3 text-sm font-semibold text-gray-200">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2 text-[11px] text-gray-400">
              <span className={`inline-flex h-2 w-2 rounded-full ${contextStyle.indicator}`} />
              <span className="uppercase tracking-wide text-gray-400">
                {isFanoutMode ? 'Agent Fan-Out Orchestration' : 'Query Planning & Template Selection'}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-gray-300">
              <span className="font-medium text-gray-100">{contextStep?.name ?? (isFanoutMode ? 'Fan-out orchestration' : 'Awaiting events')}</span>
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
            {isFanoutMode && (
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-gray-400">
                <span className="rounded-full border border-gray-700 px-2 py-0.5 text-[10px] uppercase tracking-wide text-gray-200">
                  Limit {singleAgentFanout?.concurrencyLimit ?? singleAgentFanout?.branches.length ?? 0}
                </span>
                <span className="text-blue-300">{activeCount} running</span>
                <span className="text-emerald-300">{completedCount} completed</span>
                {failedCount > 0 && <span className="text-red-300">{failedCount} failed</span>}
                {queuedCount > 0 && <span className="text-gray-500">{queuedCount} queued</span>}
              </div>
            )}
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
          {isFanoutMode && singleAgentFanout ? (
            <SingleAgentFanoutCanvas fanout={singleAgentFanout} />
          ) : (
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
          )}
        </div>
      </div>
    );
  };

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
                {followUpBanner && shouldRenderFollowUpBanner && (
                  <div className="mt-2 rounded-lg border border-amber-400/40 bg-amber-500/10 px-3 py-2 shadow-sm">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wide text-amber-300">
                        <span className="font-semibold">{followUpBanner.title}</span>
                        <span className="rounded-full border border-amber-400/50 px-2 py-0.5 text-[9px] font-semibold text-amber-200">
                          {formatScheduleStage(followUpBanner.route)}
                        </span>
                      </div>
                      {followUpBanner.finalAnswerOnly ? (
                        <button
                          type="button"
                          onClick={handleDismissFollowUpBanner}
                          className="rounded border border-amber-400/40 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-200 transition hover:border-amber-300 hover:text-amber-100"
                          aria-label="Dismiss final answer guidance"
                          data-testid="final-answer-banner-dismiss"
                        >
                          Dismiss
                        </button>
                      ) : null}
                    </div>
                    <div className="mt-1 text-[11px] leading-relaxed text-amber-100/90">
                      {followUpBanner.message}
                    </div>
                    {(followUpBanner.finalAnswerOnly || (followUpBanner.missingComponents?.length ?? 0) > 0 || followUpBanner.analysisAvailable === false) && (
                      <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-wide">
                        {followUpBanner.finalAnswerOnly ? (
                          <span className="rounded-full border border-amber-300/60 bg-amber-600/10 px-2 py-0.5 text-amber-200">
                            Final Answer Only
                          </span>
                        ) : null}
                        {followUpBanner.missingComponents?.length ? (
                          <span className="rounded-full border border-amber-300/60 bg-amber-600/10 px-2 py-0.5 text-amber-200">
                            Missing: {followUpBanner.missingComponents.map((component) => formatScheduleStage(component)).join(', ')}
                          </span>
                        ) : null}
                        {followUpBanner.analysisAvailable === false ? (
                          <span className="rounded-full border border-amber-300/60 bg-amber-600/10 px-2 py-0.5 text-amber-200">
                            Analysis Pending
                          </span>
                        ) : null}
                      </div>
                    )}
                  </div>
                )}
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
              {showVisualization ? (
                <>
                  {isCanvasExpanded
                    ? renderCanvas()
                    : renderCollapsedPane('Query Planning & Template Selection', 'Tap to restore canvas view', () => handlePaneRestore('canvas'))}
                  {isLedgerExpanded
                    ? renderLedger()
                    : renderCollapsedPane('Insight Ledger', 'Tap to review finalized steps', () => handlePaneRestore('ledger'))}
                </>
              ) : (
                renderLedger()
              )}
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
