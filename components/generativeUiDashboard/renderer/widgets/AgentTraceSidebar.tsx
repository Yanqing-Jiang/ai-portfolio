/**
 * AgentTraceSidebar -- Real-time vertical timeline of agent trace steps.
 *
 * Shows the THINK -> CALL -> RECEIVE -> INTERPRET rhythm:
 * - Tool calls with function name, input/output, duration
 * - LLM calls with label and timing
 * - Aggregate stats (total duration, tool calls, LLM calls)
 *
 * Data paths: /data/trace/steps, /data/trace/summary
 */

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TraceStepData {
    stepId: string;
    stepType: string;   // "tool_call" | "tool_result" | "llm_start" | "llm_complete" | "data_emit"
    agentName: string;
    toolName: string | null;
    label: string;
    inputSummary: string;
    outputSummary: string;
    timestamp: string;
    durationMs: number;
    status: string;     // "pending" | "running" | "success" | "error"
}

interface TraceSummaryData {
    totalDurationMs: number;
    toolCallCount: number;
    llmCallCount: number;
    stepCount: number;
}

// ---------------------------------------------------------------------------
// Icons & Colors
// ---------------------------------------------------------------------------

const STEP_STYLES: Record<string, { icon: string; color: string; label: string }> = {
    tool_call: { icon: '\u2699\uFE0F', color: '#6366f1', label: 'Tool' },
    tool_result: { icon: '\u{1F4E6}', color: '#6366f1', label: 'Result' },
    llm_start: { icon: '\u{1F9E0}', color: '#f59e0b', label: 'LLM' },
    llm_complete: { icon: '\u2728', color: '#f59e0b', label: 'LLM' },
    data_emit: { icon: '\u{1F4E1}', color: '#22c55e', label: 'Emit' },
};

const STATUS_ICONS: Record<string, string> = {
    pending: '\u23F3',
    running: '\u{1F504}',
    success: '\u2705',
    error: '\u274C',
};

// ---------------------------------------------------------------------------
// Single Step Component
// ---------------------------------------------------------------------------

function TraceStepCard({ step }: { step: TraceStepData }) {
    const [expanded, setExpanded] = useState(false);
    const style = STEP_STYLES[step.stepType] || STEP_STYLES.tool_call;

    return (
        <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.15 }}
            className="relative flex gap-2 py-1"
        >
            {/* Dot */}
            <div className="flex flex-col items-center pt-0.5">
                <span className="text-sm">{style.icon}</span>
                <div className="mt-1 flex-1 w-px bg-slate-700/40" />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="flex w-full items-center gap-1.5 text-left"
                >
                    <span className="truncate text-xs font-medium text-slate-300">
                        {step.label || step.toolName || step.stepType}
                    </span>
                    {step.durationMs > 0 && (
                        <span
                            className="shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-mono"
                            style={{
                                backgroundColor: `${style.color}15`,
                                color: style.color,
                            }}
                        >
                            {step.durationMs < 1000
                                ? `${step.durationMs.toFixed(0)}ms`
                                : `${(step.durationMs / 1000).toFixed(1)}s`}
                        </span>
                    )}
                    <span className="shrink-0 text-[10px]">
                        {STATUS_ICONS[step.status] || '\u2B55'}
                    </span>
                </button>

                <AnimatePresence>
                    {expanded && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.15 }}
                            className="mt-1 overflow-hidden"
                        >
                            <div className="rounded-md bg-slate-800/60 p-2 text-[11px] font-mono space-y-1">
                                {step.toolName && (
                                    <div>
                                        <span className="text-slate-500">tool: </span>
                                        <span className="text-indigo-400">{step.toolName}</span>
                                    </div>
                                )}
                                {step.inputSummary && (
                                    <div>
                                        <span className="text-slate-500">input: </span>
                                        <span className="text-slate-300">{step.inputSummary}</span>
                                    </div>
                                )}
                                {step.outputSummary && (
                                    <div>
                                        <span className="text-slate-500">output: </span>
                                        <span className="text-emerald-400">{step.outputSummary}</span>
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    );
}

// ---------------------------------------------------------------------------
// Main Sidebar Component
// ---------------------------------------------------------------------------

export function AgentTraceSidebar({
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement | null {
    const stepsPath = props.stepsPath as BoundValue | undefined;
    const summaryPath = props.summaryPath as BoundValue | undefined;

    const rawSteps = stepsPath ? resolveBoundValue(stepsPath, dataModel) : null;
    const rawSummary = summaryPath ? resolveBoundValue(summaryPath, dataModel) : null;

    const steps = useMemo<TraceStepData[]>(() => {
        if (!rawSteps) return [];
        const items = (rawSteps as any)?.items ?? rawSteps;
        return Array.isArray(items) ? items : [];
    }, [rawSteps]);

    const summary = useMemo<TraceSummaryData | null>(() => {
        if (!rawSummary || typeof rawSummary !== 'object') return null;
        return rawSummary as TraceSummaryData;
    }, [rawSummary]);

    if (steps.length === 0) {
        return (
            <div className="space-y-2 p-3">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-200">Agent Trace</span>
                    <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-400" />
                </div>
                <p className="text-xs text-slate-500">Waiting for pipeline steps...</p>
            </div>
        );
    }

    const toolCalls = steps.filter((s) => s.stepType === 'tool_call').length;
    const llmCalls = steps.filter((s) => s.stepType === 'llm_start' || s.stepType === 'llm_complete').length;
    const totalMs = summary?.totalDurationMs ?? steps.reduce((sum, s) => sum + s.durationMs, 0);

    return (
        <div className="space-y-3 p-3">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-200">
                        Agent Trace
                    </span>
                    <span className="text-xs text-slate-500">
                        Glass Box
                    </span>
                </div>
            </div>

            {/* Steps timeline */}
            <div className="space-y-0">
                {steps.map((step) => (
                    <TraceStepCard key={step.stepId} step={step} />
                ))}
            </div>

            {/* Aggregate stats */}
            <div className="flex items-center gap-3 rounded-lg bg-slate-800/40 px-3 py-2">
                <div className="flex items-center gap-1">
                    <span className="text-[10px] text-slate-500">Tools:</span>
                    <span className="text-xs font-mono font-semibold text-indigo-400">
                        {toolCalls}
                    </span>
                </div>
                <div className="flex items-center gap-1">
                    <span className="text-[10px] text-slate-500">LLM:</span>
                    <span className="text-xs font-mono font-semibold text-amber-400">
                        {Math.floor(llmCalls / 2)}
                    </span>
                </div>
                <div className="flex items-center gap-1">
                    <span className="text-[10px] text-slate-500">Total:</span>
                    <span className="text-xs font-mono font-semibold text-slate-300">
                        {totalMs < 1000
                            ? `${totalMs.toFixed(0)}ms`
                            : `${(totalMs / 1000).toFixed(1)}s`}
                    </span>
                </div>
            </div>

            {/* Computation receipt footer */}
            <div className="border-t border-slate-700/40 pt-2 text-[10px] text-slate-600">
                Ming Engine v2.0 | {steps.length} steps | Computed {new Date().toISOString().slice(0, 19)}Z
            </div>
        </div>
    );
}
