/**
 * ActivityRail — compact "what is the agent doing right now" strip.
 *
 * Sits docked at the bottom of the viewport, above GlassBoxDrawer. Shows:
 * - A pulsing dot while a step is running, solid when done
 * - The most-recently-started step's label and agent name
 * - Cumulative counts (tool calls / LLM calls / total duration) once the run
 *   is summarised
 * - A "Open Glass Box" chevron that expands the full trace drawer
 *
 * Intentionally thin. For deep inspection users open the drawer; the rail is
 * the ambient "I can see what the model is up to" signal that makes this feel
 * like an agent harness rather than a slow text generator.
 *
 * Trace data comes from the SSE stream's `/data/trace/steps` + `/data/trace/summary`
 * paths. The caller (MingEnginePage) reads from the A2UI data model and forwards
 * the normalized shape. No business logic lives here.
 */

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';

export interface ActivityRailStep {
    stepId: string;
    stepType: string;
    agentName: string;
    toolName?: string | null;
    label: string;
    durationMs?: number;
    status: 'pending' | 'running' | 'success' | 'error' | string;
}

export interface ActivityRailSummary {
    totalDurationMs?: number;
    toolCallCount?: number;
    llmCallCount?: number;
    stepCount?: number;
}

interface Props {
    steps: ActivityRailStep[];
    summary?: ActivityRailSummary | null;
    isStreaming: boolean;
    isOpen: boolean;
    onToggle: () => void;
}

const statusDot = (status: ActivityRailStep['status'], streaming: boolean) => {
    if (status === 'error') return 'bg-rose-500';
    if (status === 'success') return streaming ? 'bg-emerald-400' : 'bg-emerald-500';
    return 'bg-amber-400 animate-pulse';
};

export const ActivityRail: React.FC<Props> = ({
    steps,
    summary,
    isStreaming,
    isOpen,
    onToggle,
}) => {
    // Pick the most relevant step to display: the latest step whose status is
    // running, else the last-completed step. That matches the user's mental
    // model of "what is the agent busy with right now".
    const currentStep = useMemo(() => {
        if (steps.length === 0) return null;
        const running = [...steps].reverse().find((s) => s.status === 'running');
        return running ?? steps[steps.length - 1];
    }, [steps]);

    const showSummary = !isStreaming && summary && steps.length > 0;

    return (
        <motion.button
            type="button"
            onClick={onToggle}
            aria-expanded={isOpen}
            aria-controls="glass-box-drawer"
            className="fixed inset-x-0 bottom-0 z-30 w-full border-t border-slate-700/60 bg-slate-950/85 px-4 py-2 text-left backdrop-blur-md transition-colors hover:bg-slate-900/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/40"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 260, damping: 28 }}
        >
            <div className="mx-auto flex max-w-5xl items-center gap-3">
                {/* Status dot */}
                <span
                    className={`h-2.5 w-2.5 flex-none rounded-full ${statusDot(
                        currentStep?.status ?? 'pending',
                        isStreaming,
                    )}`}
                />

                {/* Current activity */}
                <div className="min-w-0 flex-1">
                    {currentStep ? (
                        <div className="flex items-baseline gap-2">
                            <span className="truncate text-sm font-medium text-slate-100">
                                {currentStep.label || currentStep.toolName || currentStep.agentName}
                            </span>
                            <span className="truncate text-[11px] uppercase tracking-wide text-slate-500">
                                {currentStep.agentName}
                                {currentStep.toolName ? ` · ${currentStep.toolName}` : ''}
                            </span>
                        </div>
                    ) : (
                        <span className="text-sm text-slate-400">
                            {isStreaming ? 'Waking the pillars…' : 'Glass Box ready'}
                        </span>
                    )}
                </div>

                {/* Summary badges — shown when run is complete */}
                {showSummary && (
                    <div className="hidden sm:flex items-center gap-3 text-[11px] text-slate-400">
                        <SummaryBadge label="steps" value={summary?.stepCount} />
                        <SummaryBadge label="tools" value={summary?.toolCallCount} />
                        <SummaryBadge label="LLMs" value={summary?.llmCallCount} />
                        {typeof summary?.totalDurationMs === 'number' && (
                            <SummaryBadge
                                label="ms"
                                value={Math.round(summary.totalDurationMs)}
                            />
                        )}
                    </div>
                )}

                {/* Toggle chevron */}
                <motion.span
                    className="text-slate-400"
                    animate={{ rotate: isOpen ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                    aria-hidden="true"
                >
                    ▲
                </motion.span>
            </div>
        </motion.button>
    );
};

function SummaryBadge({ label, value }: { label: string; value: number | undefined }) {
    if (typeof value !== 'number') return null;
    return (
        <span className="inline-flex items-center gap-1 rounded-full border border-slate-700/60 px-2 py-0.5">
            <span className="font-medium text-slate-200">{value}</span>
            <span className="text-slate-500">{label}</span>
        </span>
    );
}
