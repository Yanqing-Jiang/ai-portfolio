/**
 * GlassBoxDrawer — bottom-docked sheet showing the full agent trace.
 *
 * Activated by ActivityRail. Renders every span the backend emitted on
 * `/data/trace/steps` as a vertical list with:
 *  - emoji + color for step type (tool / LLM / emit)
 *  - status glyph (success / running / error)
 *  - duration in ms
 *  - expandable card revealing input_summary / output_summary
 *
 * Visual style matches the Ming result page — dark glass with gold accents —
 * and dismisses on ESC / backdrop click.
 *
 * Intentionally does NOT fetch. The parent owns data by reading from the A2UI
 * data model (live) or `/api/fortune/:id/trace` (replay — not yet implemented);
 * the drawer just renders what it is handed.
 */

import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { ActivityRailStep, ActivityRailSummary } from './ActivityRail';

interface Props {
    open: boolean;
    onClose: () => void;
    steps: ActivityRailStep[];
    summary?: ActivityRailSummary | null;
    /** Rendered as a one-line breadcrumb at the top — e.g. "Run · career_focus". */
    contextLabel?: string;
}

const STEP_STYLES: Record<string, { icon: string; color: string; label: string }> = {
    tool_call: { icon: '⚙️', color: '#6366f1', label: 'Tool' },
    tool_result: { icon: '📦', color: '#6366f1', label: 'Result' },
    llm_start: { icon: '🧠', color: '#f59e0b', label: 'LLM' },
    llm_complete: { icon: '✨', color: '#f59e0b', label: 'LLM' },
    data_emit: { icon: '📡', color: '#22c55e', label: 'Emit' },
};

const STATUS_DOT: Record<string, string> = {
    pending: 'bg-slate-500',
    running: 'bg-amber-400 animate-pulse',
    success: 'bg-emerald-400',
    error: 'bg-rose-500',
};

export const GlassBoxDrawer: React.FC<Props> = ({
    open,
    onClose,
    steps,
    summary,
    contextLabel,
}) => {
    // ESC to close
    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [open, onClose]);

    return (
        <AnimatePresence>
            {open && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm"
                        onClick={onClose}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                    />

                    {/* Sheet */}
                    <motion.aside
                        id="glass-box-drawer"
                        role="dialog"
                        aria-label="Agent trace"
                        className="fixed inset-x-0 bottom-10 z-40 mx-auto max-h-[70vh] w-full max-w-5xl overflow-hidden rounded-t-2xl border border-b-0 border-slate-700/70 bg-slate-950/95 text-slate-200 shadow-2xl backdrop-blur-xl"
                        initial={{ y: '100%' }}
                        animate={{ y: 0 }}
                        exit={{ y: '100%' }}
                        transition={{ type: 'spring', stiffness: 260, damping: 32 }}
                    >
                        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-800/80 bg-slate-950/95 px-4 py-3">
                            <div className="flex items-baseline gap-3 min-w-0">
                                <h2 className="text-sm font-semibold tracking-wide text-amber-300">
                                    Glass Box
                                </h2>
                                {contextLabel && (
                                    <span className="truncate text-xs text-slate-500">
                                        {contextLabel}
                                    </span>
                                )}
                            </div>
                            <div className="flex items-center gap-4">
                                {summary && (
                                    <div className="hidden sm:flex items-center gap-2 text-[11px] text-slate-400">
                                        {typeof summary.stepCount === 'number' && (
                                            <span>{summary.stepCount} steps</span>
                                        )}
                                        {typeof summary.totalDurationMs === 'number' && (
                                            <span>{Math.round(summary.totalDurationMs)} ms</span>
                                        )}
                                    </div>
                                )}
                                <button
                                    type="button"
                                    onClick={onClose}
                                    className="rounded px-2 py-1 text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/40"
                                    aria-label="Close Glass Box"
                                >
                                    ✕
                                </button>
                            </div>
                        </header>

                        <div className="max-h-[calc(70vh-52px)] overflow-y-auto px-4 py-3">
                            {steps.length === 0 ? (
                                <div className="py-8 text-center text-sm text-slate-500">
                                    No trace steps yet. Start a reading to see the agent harness in action.
                                </div>
                            ) : (
                                <ol className="space-y-1">
                                    {steps.map((step) => (
                                        <TraceRow key={step.stepId} step={step} />
                                    ))}
                                </ol>
                            )}
                        </div>
                    </motion.aside>
                </>
            )}
        </AnimatePresence>
    );
};

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

function TraceRow({ step }: { step: ActivityRailStep & { inputSummary?: string; outputSummary?: string } }) {
    const [expanded, setExpanded] = React.useState(false);
    const style = STEP_STYLES[step.stepType] ?? STEP_STYLES.tool_call;
    const dot = STATUS_DOT[step.status] ?? 'bg-slate-500';
    const hasDetail = !!(step.inputSummary || step.outputSummary);

    return (
        <li>
            <button
                type="button"
                onClick={() => hasDetail && setExpanded((v) => !v)}
                className={`flex w-full items-start gap-3 rounded-lg px-2 py-1.5 text-left transition-colors ${hasDetail ? 'hover:bg-slate-900/70' : 'cursor-default'}`}
                aria-expanded={hasDetail ? expanded : undefined}
            >
                <span
                    className="mt-0.5 inline-flex h-5 w-5 flex-none items-center justify-center rounded-full text-[11px]"
                    style={{ background: `${style.color}22`, color: style.color }}
                    aria-hidden="true"
                >
                    {style.icon}
                </span>
                <span className={`mt-1.5 h-1.5 w-1.5 flex-none rounded-full ${dot}`} />
                <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-3">
                        <p className="truncate text-sm text-slate-100">
                            {step.label || step.toolName || style.label}
                        </p>
                        {typeof step.durationMs === 'number' && step.durationMs > 0 && (
                            <span className="flex-none font-mono text-[11px] text-slate-500">
                                {Math.round(step.durationMs)} ms
                            </span>
                        )}
                    </div>
                    <div className="flex items-baseline gap-2 text-[11px] text-slate-500">
                        <span>{step.agentName}</span>
                        {step.toolName && <span>· {step.toolName}</span>}
                    </div>
                </div>
            </button>

            <AnimatePresence initial={false}>
                {expanded && hasDetail && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.18 }}
                        className="ml-11 mr-2 overflow-hidden"
                    >
                        <div className="space-y-1 rounded-md border border-slate-800 bg-slate-900/50 p-2 text-xs">
                            {step.inputSummary && (
                                <div>
                                    <span className="text-slate-500">in: </span>
                                    <span className="text-slate-300">{step.inputSummary}</span>
                                </div>
                            )}
                            {step.outputSummary && (
                                <div>
                                    <span className="text-slate-500">out: </span>
                                    <span className="text-slate-300">{step.outputSummary}</span>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </li>
    );
}
