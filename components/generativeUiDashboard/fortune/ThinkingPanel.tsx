/**
 * ThinkingPanel — live agent reasoning surface for fortune result pages.
 *
 * Two modes controlled by `status`:
 *   1. `streaming` — prominent panel docked below the tab bar, streams
 *      trace steps (tool calls / handoffs / progress) as they arrive.
 *   2. `complete`  — animates down into a thin pull-up dock fixed at the
 *      bottom of the viewport. Click to expand the full timeline drawer.
 *
 * Source data:
 *   - `dataModel.trace.steps.items[]`  (A2UIComponent: AgentTraceSidebar)
 *   - `dataModel.meta.progress.message` (the active phase label)
 *
 * Both paths are already emitted by backend/fortune/stream_bridge.py.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
    ArrowRightLeft,
    Brain,
    CheckCircle2,
    ChevronUp,
    MessageSquare,
    Pause,
    Shield,
    Sparkles,
    Users,
    X,
    Zap,
} from 'lucide-react';
import type { FortunePurposeId } from '../fortuneAgentTheme';
import { FORTUNE_THEMES } from '../fortuneAgentTheme';
import { useFortuneStore } from '../stores/fortuneStore';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TraceStep {
    stepId?: string;
    stepType?: string;
    agentName?: string;
    toolName?: string | null;
    label?: string;
    inputSummary?: string;
    outputSummary?: string;
    timestamp?: string;
    durationMs?: number;
    status?: 'pending' | 'running' | 'queued' | 'success' | 'done' | 'error' | 'skipped' | string;
    // PR-Panel: extended fields from the always-visible 5-step schema.
    // These flow through ``/data/thinking/steps`` (NEW) — the legacy
    // ``/data/trace/steps`` surface keeps the operator-side shape above.
    modelId?: string;
    sequence?: number;
    stage?: number;
    statusReason?: string;
    elapsedMs?: number;
    reasoningTokens?: number;
    reasoningEffort?: 'none' | 'low' | 'medium' | 'high' | 'xhigh' | 'deterministic' | string;
    startedAt?: string | null;
    endedAt?: string | null;
}

interface ProgressMeta {
    phase?: string;
    message?: string;
}

type ThinkingStatus = 'streaming' | 'complete';

interface ThinkingPanelProps {
    purpose: FortunePurposeId;
    dataModel: Record<string, unknown> | null;
    status: ThinkingStatus;
    /** Optional pause/cancel handler. When provided, the live view renders
     * a Pause button that fires this callback. Parent is responsible for
     * calling the cancel endpoint and transitioning state. */
    onPause?: () => void;
    /** True once a pause/cancel request is in flight. Disables the button
     * and swaps the label to "Pausing…". */
    paused?: boolean;
    /** When false, suppress the persistent floating "Agent reasoning · N
     * steps" dock once status flips to `complete`. Useful when the parent
     * only wants the live streaming view (e.g. surface the dock only on
     * the Ask tab to avoid clutter on chart/timeline tabs). */
    showCompletedDock?: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Flatten a raw ``steps`` blob — supports the keyed-map (PR-Panel
 * ``/data/thinking/steps``), the ``{ items: [...] }`` initial-batch
 * shape, and a plain array (legacy). When the blob is a keyed map of
 * ``{ stepId: { step: {...} } }`` we unwrap the ``step`` payload so
 * the caller sees a flat ``TraceStep[]``.
 */
function flattenStepsBlob(raw: unknown): TraceStep[] {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw as TraceStep[];
    if (typeof raw === 'object') {
        const items = (raw as { items?: TraceStep[] }).items;
        if (Array.isArray(items)) return items;
        return Object.values(raw as Record<string, unknown>)
            .map((v) => {
                if (v && typeof v === 'object' && 'step' in v) return (v as { step: TraceStep }).step;
                return v as TraceStep;
            })
            .filter(Boolean) as TraceStep[];
    }
    return [];
}

/**
 * Read the 5-row panel timeline. Prefers the PR-Panel
 * ``/data/thinking/steps`` surface (always-visible canonical schema);
 * falls back to the legacy ``/data/trace/steps`` (operator sidebar)
 * during rollout so the UI never goes blank if the panel-aware
 * backend version is rolled back.
 *
 * Steps are sorted by ``sequence`` when present so SSE replay/reconnect
 * out-of-order events still land in a stable visual order.
 */
function extractSteps(dataModel: Record<string, unknown> | null): TraceStep[] {
    if (!dataModel) return [];
    // PR-Panel surface — preferred.
    const thinking = (dataModel as { thinking?: { steps?: unknown } }).thinking;
    const panelSteps = flattenStepsBlob(thinking?.steps);
    if (panelSteps.length > 0) {
        // Stable sort by ``sequence`` (rows without one trail at the end).
        const withSeq = panelSteps.map((s, i) => ({ s, i, seq: s.sequence ?? 999 + i }));
        withSeq.sort((a, b) => a.seq - b.seq || a.i - b.i);
        return withSeq.map((x) => x.s);
    }
    // Legacy fallback: operator trace surface.
    const trace = (dataModel as { trace?: { steps?: unknown } }).trace;
    return flattenStepsBlob(trace?.steps);
}

function extractProgress(dataModel: Record<string, unknown> | null): ProgressMeta | null {
    if (!dataModel) return null;
    const meta = (dataModel as { meta?: { progress?: ProgressMeta } }).meta;
    return meta?.progress ?? null;
}

function iconForStep(step: TraceStep) {
    const type = (step.stepType || '').toLowerCase();
    if (type.includes('tool_call') || type === 'tool_start') return Zap;
    if (type.includes('tool_result') || type.includes('tool_output') || type === 'tool_end') return CheckCircle2;
    if (type.includes('handoff')) return ArrowRightLeft;
    if (type.includes('llm_start') || type.includes('llm_complete')) return Brain;
    if (type.includes('agent')) return Users;
    if (type.includes('message')) return MessageSquare;
    return Sparkles;
}

function formatAgent(name?: string): string {
    if (!name) return 'system';
    return name.replace(/_/g, ' ').toLowerCase();
}

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

interface RowProps {
    step: TraceStep;
    index: number;
    isLast: boolean;
    accent: string;
}

const StepRow: React.FC<RowProps> = ({ step, index, isLast, accent }) => {
    const Icon = iconForStep(step);
    const isActive = step.status === 'running' || step.status === 'pending';
    const isError = step.status === 'error';

    return (
        <motion.div
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.22, delay: Math.min(index * 0.01, 0.1) }}
            className="flex gap-3 group"
        >
            <div className="flex flex-col items-center flex-none pt-0.5">
                <div
                    className="relative flex h-6 w-6 items-center justify-center rounded-full border"
                    style={{
                        background: isActive
                            ? `${accent}33`
                            : isError
                            ? 'rgba(244,63,94,0.12)'
                            : 'rgba(148,163,184,0.08)',
                        borderColor: isActive
                            ? accent
                            : isError
                            ? 'rgba(244,63,94,0.5)'
                            : 'rgba(148,163,184,0.2)',
                    }}
                >
                    <Icon
                        size={12}
                        color={isActive ? accent : isError ? '#fb7185' : '#cbd5e1'}
                    />
                    {isActive && (
                        <span
                            aria-hidden
                            className="absolute inset-0 rounded-full animate-ping"
                            style={{ background: `${accent}40` }}
                        />
                    )}
                </div>
                {!isLast && (
                    <div
                        className="w-px flex-1 my-1"
                        style={{ background: 'rgba(148,163,184,0.12)' }}
                    />
                )}
            </div>
            <div className="pb-3 min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 mb-0.5">
                    <span
                        className="text-[10px] font-mono uppercase tracking-wider"
                        style={{ color: accent, opacity: 0.85 }}
                    >
                        {formatAgent(step.agentName)}
                    </span>
                    {step.toolName && (
                        <span className="text-[10px] font-mono text-slate-400 px-1.5 py-0.5 rounded bg-slate-500/10 border border-slate-500/20">
                            {step.toolName}
                        </span>
                    )}
                    {typeof step.durationMs === 'number' && step.durationMs > 0 && (
                        <span className="text-[10px] text-slate-500 font-mono">
                            {Math.round(step.durationMs)}ms
                        </span>
                    )}
                </div>
                <p className="text-[13px] text-slate-200 leading-snug truncate">
                    {step.label || step.stepType || 'step'}
                </p>
                {step.outputSummary && (
                    <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-2">
                        {step.outputSummary}
                    </p>
                )}
            </div>
        </motion.div>
    );
};

// ---------------------------------------------------------------------------
// Live (streaming) view — sits inline below the tabs
// ---------------------------------------------------------------------------

interface LiveViewProps {
    steps: TraceStep[];
    progressText: string;
    accent: string;
    onPause?: () => void;
    paused?: boolean;
    /** PR5: when true, narrative finished streaming and only the
     * guardrail tail (~3.5–4.5s) is left. We swap the live header to
     * "Verifying Safety" + a Shield icon. The elapsed counter keeps
     * ticking through the guardrail window — the user can still see
     * how long the safety check is taking and the running total mirrors
     * the LiveView header's existing time-on-task signal. */
    narrativeReady?: boolean;
}

const LiveView: React.FC<LiveViewProps> = ({ steps, progressText, accent, onPause, paused, narrativeReady }) => {
    const scrollRef = useRef<HTMLDivElement>(null);
    // Elapsed-time indicator — gives the user a heartbeat during the
    // otherwise-silent narrative generation window. Resets when a new
    // progress message arrives.
    const [elapsedSec, setElapsedSec] = useState(0);
    const phaseStart = useRef<number>(Date.now());
    useEffect(() => {
        phaseStart.current = Date.now();
        setElapsedSec(0);
    }, [progressText]);
    useEffect(() => {
        const t = setInterval(() => {
            setElapsedSec(Math.floor((Date.now() - phaseStart.current) / 1000));
        }, 1000);
        return () => clearInterval(t);
    }, []);

    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return;
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }, [steps.length, progressText]);

    const latest = steps[steps.length - 1];

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            transition={{ type: 'spring', stiffness: 260, damping: 28 }}
            className="relative mb-5 overflow-hidden rounded-2xl border backdrop-blur-xl"
            style={{
                background: 'rgba(15, 14, 28, 0.55)',
                borderColor: `${accent}30`,
                boxShadow: `0 10px 40px -20px ${accent}55`,
            }}
            aria-live="polite"
            aria-label="Agent reasoning stream"
        >
            {/* Header */}
            <div
                className="flex items-center gap-2.5 px-4 py-3 border-b"
                style={{ borderColor: 'rgba(148,163,184,0.12)' }}
            >
                {narrativeReady ? (
                    <motion.div
                        animate={{ scale: [1, 1.08, 1] }}
                        transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
                    >
                        <Shield size={16} color={accent} />
                    </motion.div>
                ) : (
                    <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
                    >
                        <Sparkles size={16} color={accent} />
                    </motion.div>
                )}
                <div className="min-w-0 flex-1">
                    <div
                        className="text-[10px] font-mono uppercase tracking-[0.18em]"
                        style={{ color: accent }}
                    >
                        {narrativeReady ? 'Verifying Safety' : 'Agent Thinking · Live'}
                    </div>
                    <div className="text-[13px] text-slate-200 truncate">
                        {narrativeReady
                            ? 'Reading rendered — running final safety check…'
                            : progressText ||
                              (latest?.label
                                  ? latest.label
                                  : 'Consulting the pillars…')}
                    </div>
                </div>
                <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400">
                    <span
                        className="h-1.5 w-1.5 rounded-full animate-pulse"
                        style={{ background: accent }}
                    />
                    <span>{steps.length}</span>
                    <span className="tabular-nums text-slate-500">{elapsedSec}s</span>
                    {onPause && (
                        <button
                            type="button"
                            onClick={onPause}
                            disabled={paused}
                            aria-label={paused ? 'Pausing…' : 'Pause reading'}
                            className="ml-1 inline-flex items-center gap-1 rounded-full px-2 py-1 text-[10px] font-medium uppercase tracking-wider transition-colors disabled:opacity-50"
                            style={{
                                color: accent,
                                background: `${accent}18`,
                                border: `1px solid ${accent}40`,
                            }}
                        >
                            <Pause size={10} />
                            {paused ? 'Pausing…' : 'Pause'}
                        </button>
                    )}
                </div>
            </div>

            {/* Step feed */}
            <div
                ref={scrollRef}
                className="px-4 py-3 overflow-y-auto"
                style={{ maxHeight: 220 }}
            >
                {steps.length === 0 ? (
                    <p className="text-[12px] text-slate-500 italic">
                        Queueing pipeline…
                    </p>
                ) : (
                    steps.map((step, i) => (
                        <StepRow
                            key={step.stepId || `${step.stepType}-${i}`}
                            step={step}
                            index={i}
                            isLast={i === steps.length - 1}
                            accent={accent}
                        />
                    ))
                )}
            </div>
        </motion.div>
    );
};

// ---------------------------------------------------------------------------
// Dock (collapsed) + Drawer (expanded)
// ---------------------------------------------------------------------------

interface DockProps {
    steps: TraceStep[];
    accent: string;
}

const Dock: React.FC<DockProps> = ({ steps, accent }) => {
    const [isOpen, setIsOpen] = useState(false);
    const reduceMotion = useReducedMotion();

    // ESC closes
    useEffect(() => {
        if (!isOpen) return;
        const handler = (e: KeyboardEvent) => {
            if (e.key === 'Escape') setIsOpen(false);
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [isOpen]);

    const totalMs = useMemo(() => {
        return steps.reduce((sum, s) => sum + (s.durationMs || 0), 0);
    }, [steps]);

    return (
        <>
            {/* Collapsed pill */}
            <AnimatePresence>
                {!isOpen && (
                    <motion.button
                        type="button"
                        onClick={() => setIsOpen(true)}
                        aria-expanded={false}
                        aria-controls="thinking-drawer"
                        initial={reduceMotion ? { opacity: 0 } : { y: 80, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: 80, opacity: 0 }}
                        transition={{
                            type: 'spring',
                            stiffness: 180,
                            damping: 22,
                            delay: 0.25,
                        }}
                        whileHover={{ scale: 1.03 }}
                        whileTap={{ scale: 0.98 }}
                        className="fixed left-1/2 z-40 flex h-10 -translate-x-1/2 items-center gap-2.5 rounded-full border px-4 text-[11px] font-medium backdrop-blur-md"
                        style={{
                            bottom: 'calc(env(safe-area-inset-bottom, 0px) + 20px)',
                            background: 'rgba(15, 14, 28, 0.85)',
                            borderColor: `${accent}4D`,
                            color: '#e2e8f0',
                            boxShadow: `0 8px 32px -12px ${accent}66`,
                            minHeight: 40,
                        }}
                    >
                        <span
                            aria-hidden
                            className="h-1.5 w-1.5 rounded-full animate-pulse"
                            style={{ background: accent }}
                        />
                        <span className="tracking-wide">
                            Agent reasoning · {steps.length} {steps.length === 1 ? 'step' : 'steps'}
                        </span>
                        <ChevronUp size={13} style={{ color: accent }} />
                    </motion.button>
                )}
            </AnimatePresence>

            {/* Expanded drawer */}
            <AnimatePresence>
                {isOpen && (
                    <>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setIsOpen(false)}
                            className="fixed inset-0 z-[60] backdrop-blur-sm"
                            style={{ background: 'rgba(0,0,0,0.55)' }}
                        />
                        <motion.div
                            id="thinking-drawer"
                            role="dialog"
                            aria-modal="true"
                            aria-label="Full agent reasoning timeline"
                            initial={{ y: '100%' }}
                            animate={{ y: 0 }}
                            exit={{ y: '100%' }}
                            transition={{
                                type: 'spring',
                                stiffness: 240,
                                damping: 30,
                            }}
                            drag={reduceMotion ? false : 'y'}
                            dragConstraints={{ top: 0, bottom: 0 }}
                            dragElastic={0.2}
                            onDragEnd={(_, info) => {
                                if (info.offset.y > 120) setIsOpen(false);
                            }}
                            className="fixed inset-x-0 bottom-0 z-[70] flex flex-col overflow-hidden rounded-t-3xl border-t"
                            style={{
                                background: 'rgba(10, 9, 20, 0.98)',
                                borderColor: `${accent}40`,
                                height: '65vh',
                                maxHeight: 720,
                                boxShadow: `0 -20px 60px -20px ${accent}55`,
                            }}
                        >
                            {/* Drag handle */}
                            <div className="mx-auto mt-3 mb-1 h-1.5 w-12 flex-none rounded-full bg-white/20" />

                            {/* Header */}
                            <div
                                className="flex items-center justify-between px-5 py-3 border-b flex-none"
                                style={{ borderColor: 'rgba(148,163,184,0.1)' }}
                            >
                                <div className="flex items-center gap-2">
                                    <Brain size={18} style={{ color: accent }} />
                                    <div>
                                        <h3
                                            className="text-[13px] font-semibold"
                                            style={{ color: '#f8fafc' }}
                                        >
                                            Agent Reasoning
                                        </h3>
                                        <p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
                                            {steps.length} steps
                                            {totalMs > 0 && ` · ${Math.round(totalMs)}ms total`}
                                        </p>
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => setIsOpen(false)}
                                    aria-label="Close"
                                    className="p-2 rounded-full hover:bg-white/5 transition-colors"
                                >
                                    <X size={18} className="text-slate-400" />
                                </button>
                            </div>

                            {/* Body */}
                            <div className="flex-1 overflow-y-auto px-5 py-4">
                                {steps.length === 0 ? (
                                    <p className="text-sm text-slate-500 text-center py-8">
                                        No reasoning steps captured.
                                    </p>
                                ) : (
                                    steps.map((step, i) => (
                                        <StepRow
                                            key={step.stepId || `${step.stepType}-${i}`}
                                            step={step}
                                            index={i}
                                            isLast={i === steps.length - 1}
                                            accent={accent}
                                        />
                                    ))
                                )}
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </>
    );
};

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export const ThinkingPanel: React.FC<ThinkingPanelProps> = ({
    purpose,
    dataModel,
    status,
    onPause,
    paused,
    showCompletedDock = true,
}) => {
    const theme = FORTUNE_THEMES[purpose];
    const accent = theme.accent;

    const steps = useMemo(() => extractSteps(dataModel), [dataModel]);
    const progress = useMemo(() => extractProgress(dataModel), [dataModel]);
    const progressText = progress?.message ?? '';
    // PR5: read the live narrative-complete flag from the store. When the
    // backend ships its ``isComplete: true`` patch on /data/narrative,
    // ``useFortuneStream`` flips this so we can swap the live header to
    // "Verifying safety…" while the guardrail tail finishes.
    const narrativeReady = useFortuneStore((s) => s.narrativeReady);

    // PR-Panel: always-visible — the panel renders the canonical 5-row
    // schema as queued placeholders the moment the stream opens, then
    // transitions them to running/done. We no longer return null on
    // empty/complete; the worst case is a 5-row "queued" skeleton.
    //
    // The ``showCompletedDock=false`` opt-out still suppresses the
    // floating pull-up pill on the Ask tab (which surfaces reasoning
    // inline via OracleChat instead) — but this only matters when
    // ``status === 'complete'``; live streaming is always shown.
    if (status === 'complete' && !showCompletedDock && steps.length === 0) {
        return null;
    }

    return (
        <AnimatePresence mode="wait">
            {status === 'streaming' ? (
                <LiveView
                    key="live"
                    steps={steps}
                    progressText={progressText}
                    accent={accent}
                    onPause={onPause}
                    paused={paused}
                    narrativeReady={narrativeReady}
                />
            ) : (
                <Dock key="dock" steps={steps} accent={accent} />
            )}
        </AnimatePresence>
    );
};

export default ThinkingPanel;
