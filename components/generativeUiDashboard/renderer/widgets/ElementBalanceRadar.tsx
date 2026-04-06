/**
 * ElementBalanceRadar — Five Elements balance radar chart.
 *
 * Renders an ECharts radar pentagon showing element scores with
 * dominant/weakest indicators and summary text.
 *
 * Called from: ComponentRenderer.tsx via Registry
 * Data path: /data/elements (emitted by stream_bridge.emit_elements)
 */

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';
import LazyECharts from '../../../shared/LazyECharts';

const ELEMENT_COLORS: Record<string, string> = {
    wood: '#22c55e',
    fire: '#ef4444',
    earth: '#d97706',
    metal: '#a1a1aa',
    water: '#3b82f6',
};

interface ElementScore {
    element: string;
    score: number;
}

interface ElementBalanceData {
    scores: ElementScore[];
    dominant: string;
    weakest: string;
    summary: string;
}

export function ElementBalanceRadar({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const data = resolveBoundValue(
        props.elementsPath as BoundValue | undefined,
        dataModel
    ) as ElementBalanceData | undefined;

    const option = useMemo(() => {
        if (!data?.scores?.length) return null;

        const dominantColor = ELEMENT_COLORS[data.dominant] || '#3b82f6';

        return {
            backgroundColor: 'transparent',
            radar: {
                indicator: data.scores.map((s) => ({
                    name: s.element.charAt(0).toUpperCase() + s.element.slice(1),
                    max: 10,
                })),
                axisName: {
                    color: '#94a3b8',
                    fontSize: 12,
                },
                splitArea: {
                    areaStyle: {
                        color: [
                            'rgba(148, 163, 184, 0.02)',
                            'rgba(148, 163, 184, 0.04)',
                        ],
                    },
                },
                splitLine: {
                    lineStyle: { color: 'rgba(148, 163, 184, 0.12)' },
                },
                axisLine: {
                    lineStyle: { color: 'rgba(148, 163, 184, 0.12)' },
                },
            },
            series: [
                {
                    type: 'radar',
                    data: [
                        {
                            value: data.scores.map((s) => s.score),
                            areaStyle: {
                                color: {
                                    type: 'radial',
                                    x: 0.5,
                                    y: 0.5,
                                    r: 0.6,
                                    colorStops: [
                                        { offset: 0, color: `${dominantColor}30` },
                                        { offset: 1, color: `${dominantColor}08` },
                                    ],
                                },
                            },
                            lineStyle: {
                                color: dominantColor,
                                width: 2,
                            },
                            itemStyle: {
                                color: dominantColor,
                            },
                            symbol: 'circle',
                            symbolSize: 6,
                        },
                    ],
                    animationEasing: 'elasticOut',
                    animationDuration: 1200,
                },
            ],
            tooltip: {
                trigger: 'item',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderColor: 'rgba(148, 163, 184, 0.2)',
                textStyle: { color: '#f8fafc', fontSize: 12 },
            },
        };
    }, [data]);

    if (!data || !option) {
        return <div data-component-id={componentId} />;
    }

    return (
        <motion.div
            data-component-id={componentId}
            className="w-full"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 25, mass: 0.8 }}
        >
            <LazyECharts
                option={option}
                theme="dark"
                style={{ height: 'clamp(200px, 50vw, 320px)', width: '100%' }}
                opts={{ renderer: 'svg' }}
            />

            {/* Element chips */}
            <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
                {data.scores.map((s) => {
                    const color = ELEMENT_COLORS[s.element] || '#94a3b8';
                    const isDominant = s.element === data.dominant;
                    const isWeakest = s.element === data.weakest;
                    return (
                        <span
                            key={s.element}
                            className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium"
                            style={{
                                backgroundColor: `${color}20`,
                                color,
                                border: isDominant
                                    ? `1.5px solid ${color}`
                                    : isWeakest
                                      ? `1px dashed ${color}60`
                                      : `1px solid ${color}30`,
                            }}
                        >
                            {s.element}
                            <span className="font-bold">{s.score}</span>
                        </span>
                    );
                })}
            </div>

            {/* Summary */}
            {data.summary && (
                <p className="mt-2 text-center text-sm leading-relaxed text-slate-400">
                    {data.summary}
                </p>
            )}
        </motion.div>
    );
}
