/**
 * ElementBalanceStacked -- Stacked bar chart showing element contributions
 * by pillar source + gauge meters for surplus/deficit.
 *
 * Data path: /data/elementBySource
 * Each pillar (year/month/day/hour) contributes fractional element weights
 * including hidden stems.
 */

import React, { useMemo, useRef } from 'react';
import { useInView } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';
import LazyECharts from '../../../shared/LazyECharts';

const ELEMENTS = ['wood', 'fire', 'earth', 'metal', 'water'] as const;
const PILLAR_NAMES = ['year', 'month', 'day', 'hour'] as const;

const ELEMENT_COLORS: Record<string, string> = {
    wood: '#22c55e',
    fire: '#ef4444',
    earth: '#d97706',
    metal: '#a1a1aa',
    water: '#3b82f6',
};

const ELEMENT_LABELS: Record<string, string> = {
    wood: 'Wood \u6728',
    fire: 'Fire \u706b',
    earth: 'Earth \u571f',
    metal: 'Metal \u91d1',
    water: 'Water \u6c34',
};

interface ElementBySource {
    [pillar: string]: { [element: string]: number };
}

export function ElementBalanceStacked({
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement | null {
    const ref = useRef<HTMLDivElement>(null);
    const isInView = useInView(ref, { once: true, margin: '-50px' });

    const sourcePath = props.sourcePath as BoundValue | undefined;
    const raw = sourcePath ? resolveBoundValue(sourcePath, dataModel) : null;

    const data = useMemo<ElementBySource | null>(() => {
        if (!raw || typeof raw !== 'object') return null;
        return raw as ElementBySource;
    }, [raw]);

    // Compute totals per element
    const totals = useMemo(() => {
        if (!data) return null;
        const result: Record<string, number> = {};
        for (const el of ELEMENTS) {
            result[el] = PILLAR_NAMES.reduce(
                (sum, p) => sum + (data[p]?.[el] ?? 0),
                0,
            );
        }
        return result;
    }, [data]);

    // Stacked bar chart options
    const barOptions = useMemo(() => {
        if (!data) return null;
        const series = PILLAR_NAMES.map((pillar) => ({
            name: pillar.charAt(0).toUpperCase() + pillar.slice(1),
            type: 'bar' as const,
            stack: 'total',
            barWidth: '60%',
            data: ELEMENTS.map((el) => +(data[pillar]?.[el] ?? 0).toFixed(2)),
            itemStyle: {
                borderRadius: 0,
                color: undefined as string | undefined,
            },
            emphasis: { focus: 'series' as const },
        }));

        const pillarColors = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd'];
        series.forEach((s, i) => {
            s.itemStyle.color = pillarColors[i];
        });

        return {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis' as const,
                axisPointer: { type: 'shadow' as const },
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                borderColor: 'rgba(148, 163, 184, 0.2)',
                textStyle: { color: '#e2e8f0', fontSize: 12 },
            },
            legend: {
                data: PILLAR_NAMES.map((p) => p.charAt(0).toUpperCase() + p.slice(1)),
                textStyle: { color: '#94a3b8', fontSize: 11 },
                top: 0,
            },
            grid: {
                left: '3%',
                right: '3%',
                bottom: '3%',
                top: 40,
                containLabel: true,
            },
            xAxis: {
                type: 'category' as const,
                data: ELEMENTS.map((el) => ELEMENT_LABELS[el]),
                axisLabel: { color: '#94a3b8', fontSize: 11 },
                axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.15)' } },
            },
            yAxis: {
                type: 'value' as const,
                axisLabel: { color: '#64748b', fontSize: 10 },
                splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.08)' } },
            },
            series,
        };
    }, [data]);

    if (!data || !totals) {
        return (
            <div ref={ref} className="h-48 animate-pulse rounded-lg bg-slate-800/30" />
        );
    }

    const maxTotal = Math.max(...Object.values(totals), 1);

    return (
        <div ref={ref} className="space-y-4">
            {/* Title */}
            <div className="flex items-center gap-2">
                <span className="text-base font-semibold text-slate-200">
                    Element Balance
                </span>
                <span className="text-xs text-slate-500">(includes hidden stems)</span>
            </div>

            {/* Stacked bar chart */}
            {isInView && barOptions && (
                <div className="rounded-lg bg-slate-800/20 p-2">
                    <LazyECharts
                        option={barOptions}
                        style={{ height: 220, width: '100%' }}
                        opts={{ renderer: 'canvas' }}
                    />
                </div>
            )}

            {/* Gauge meters */}
            <div className="grid grid-cols-5 gap-2">
                {ELEMENTS.map((el) => {
                    const value = totals[el];
                    const pct = (value / maxTotal) * 100;
                    return (
                        <div
                            key={el}
                            className="flex flex-col items-center gap-1 rounded-lg bg-slate-800/30 p-2"
                        >
                            <span className="text-xs text-slate-400 capitalize">
                                {el}
                            </span>
                            <div className="relative h-2 w-full rounded-full bg-slate-700/50">
                                <div
                                    className="absolute inset-y-0 left-0 rounded-full transition-all duration-700"
                                    style={{
                                        width: `${pct}%`,
                                        backgroundColor: ELEMENT_COLORS[el],
                                    }}
                                />
                            </div>
                            <span
                                className="text-sm font-mono font-semibold"
                                style={{ color: ELEMENT_COLORS[el] }}
                            >
                                {value.toFixed(1)}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
