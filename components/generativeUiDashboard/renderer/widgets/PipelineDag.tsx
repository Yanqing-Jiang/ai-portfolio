/**
 * PipelineDag -- ECharts graph showing the agent pipeline as a DAG.
 *
 * Nodes = trace steps (tools, LLM calls)
 * Edges = sequential data flow between steps
 * Nodes light up based on status and color by type.
 *
 * Data path: /data/trace/steps
 * Only visible in Inspector mode.
 */

import React, { useMemo, useRef } from 'react';
import { useInView } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';
import { useInspectorMode } from '../../InspectorModeContext';
import LazyECharts from '../../../shared/LazyECharts';

interface TraceStepData {
    stepId: string;
    stepType: string;
    agentName: string;
    toolName: string | null;
    label: string;
    durationMs: number;
    status: string;
}

const TYPE_COLORS: Record<string, string> = {
    tool_call: '#6366f1',
    llm_start: '#f59e0b',
    llm_complete: '#f59e0b',
    data_emit: '#22c55e',
};

const TYPE_SHAPES: Record<string, string> = {
    tool_call: 'roundRect',
    llm_start: 'diamond',
    llm_complete: 'diamond',
    data_emit: 'circle',
};

export function PipelineDag({
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement | null {
    const ref = useRef<HTMLDivElement>(null);
    const isInView = useInView(ref, { once: true, margin: '-50px' });
    const isInspector = useInspectorMode();

    const stepsPath = props.stepsPath as BoundValue | undefined;
    const rawSteps = stepsPath ? resolveBoundValue(stepsPath, dataModel) : null;

    const steps = useMemo<TraceStepData[]>(() => {
        if (!rawSteps) return [];
        const items = (rawSteps as any)?.items ?? rawSteps;
        return Array.isArray(items) ? items : [];
    }, [rawSteps]);

    const chartOptions = useMemo(() => {
        if (steps.length === 0) return null;

        // Layout: 2-column grid, tools on left, LLM on right
        const nodes = steps.map((step, i) => {
            const isLLM = step.stepType.startsWith('llm');
            const col = isLLM ? 1 : 0;
            const row = i;
            return {
                name: step.stepId,
                x: col * 250 + 80,
                y: row * 55 + 30,
                symbolSize: [140, 32],
                symbol: TYPE_SHAPES[step.stepType] || 'roundRect',
                itemStyle: {
                    color: step.status === 'success'
                        ? TYPE_COLORS[step.stepType] || '#64748b'
                        : step.status === 'running' ? '#f59e0b' : '#334155',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                },
                label: {
                    show: true,
                    formatter: () => {
                        const dur = step.durationMs > 0 ? ` ${step.durationMs < 1000 ? step.durationMs.toFixed(0) + 'ms' : (step.durationMs / 1000).toFixed(1) + 's'}` : '';
                        const name = step.label || step.toolName || step.stepType;
                        return name.length > 22 ? name.slice(0, 20) + '..' + dur : name + dur;
                    },
                    color: '#e2e8f0',
                    fontSize: 10,
                    fontFamily: 'ui-monospace, monospace',
                },
            };
        });

        // Sequential edges
        const edges = steps.slice(1).map((step, i) => ({
            source: steps[i].stepId,
            target: step.stepId,
            lineStyle: {
                color: 'rgba(148, 163, 184, 0.3)',
                width: 1.5,
                curveness: 0,
            },
            symbol: ['none', 'arrow'],
            symbolSize: [0, 8],
        }));

        return {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'item' as const,
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                borderColor: 'rgba(148, 163, 184, 0.2)',
                textStyle: { color: '#e2e8f0', fontSize: 11 },
                formatter: (params: any) => {
                    const step = steps.find((s) => s.stepId === params.name);
                    if (!step) return '';
                    return `<b>${step.label || step.toolName}</b><br/>Type: ${step.stepType}<br/>Duration: ${step.durationMs}ms<br/>Status: ${step.status}`;
                },
            },
            series: [
                {
                    type: 'graph' as const,
                    layout: 'none' as const,
                    roam: false,
                    data: nodes,
                    links: edges,
                    lineStyle: { opacity: 0.6 },
                    emphasis: {
                        focus: 'adjacency' as const,
                    },
                },
            ],
        };
    }, [steps]);

    // Only render in inspector mode
    if (!isInspector) return null;
    if (steps.length === 0) return null;

    return (
        <div ref={ref} className="space-y-2">
            <div className="flex items-center gap-2">
                <span className="text-base font-semibold text-slate-200">Pipeline DAG</span>
                <span className="text-xs text-slate-500">Architecture Diagram</span>
            </div>

            {isInView && chartOptions && (
                <div className="rounded-lg bg-slate-800/20 p-2">
                    <LazyECharts
                        option={chartOptions}
                        style={{ height: Math.max(200, steps.length * 55 + 60), width: '100%' }}
                        opts={{ renderer: 'canvas' }}
                    />
                </div>
            )}

            {/* Legend */}
            <div className="flex gap-3 text-[10px]">
                <span className="flex items-center gap-1">
                    <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: '#6366f1' }} />
                    <span className="text-slate-400">Tool Call</span>
                </span>
                <span className="flex items-center gap-1">
                    <span className="h-2.5 w-2.5 rotate-45" style={{ backgroundColor: '#f59e0b' }} />
                    <span className="text-slate-400">LLM Call</span>
                </span>
            </div>
        </div>
    );
}
