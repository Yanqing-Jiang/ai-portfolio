/**
 * MetricChart Component
 *
 * Data-driven time-series chart for financial metrics (revenue, margins, etc.)
 * using LazyECharts (Suspense-wrapped) for multi-ticker and multi-series visualization.
 *
 * Called from: ComponentRenderer.tsx via Registry
 * Invokes next: Shared LazyECharts loader to code-split the echarts bundle and render the series chart.
 * Why: PriceChart uses TradingView (single-ticker price only); MetricChart
 *      handles multi-series metric data from comp_financials with the shared chart loader used by Conversational Analytics.
 */

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';
import LazyECharts from '../../../shared/LazyECharts';

// Color palette for multi-series
const SERIES_COLORS = [
    '#f43f5e', // rose-500
    '#3b82f6', // blue-500
    '#10b981', // emerald-500
    '#f59e0b', // amber-500
    '#8b5cf6', // violet-500
    '#06b6d4', // cyan-500
];

interface SeriesDataPoint {
    period: string;
    value: number;
}

interface SeriesData {
    ticker: string;
    data: SeriesDataPoint[];
}

interface Annotation {
    period: string;
    ticker: string;
    label: string;
    details?: string;
    type?: 'news' | 'event' | 'alert';
}

/**
 * Format large numbers with K/M/B suffixes.
 */
function formatValue(value: number): string {
    if (Math.abs(value) >= 1e9) {
        return (value / 1e9).toFixed(1) + 'B';
    }
    if (Math.abs(value) >= 1e6) {
        return (value / 1e6).toFixed(1) + 'M';
    }
    if (Math.abs(value) >= 1e3) {
        return (value / 1e3).toFixed(1) + 'K';
    }
    return value.toFixed(1);
}

/**
 * MetricChart Component
 */
export function MetricChart({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    // Resolve bound values
    const resolvedTitle = resolveBoundValue(props.title as BoundValue | undefined, dataModel) as string || 'Metric Chart';
    const resolvedSeries = resolveBoundValue(props.series as BoundValue | undefined, dataModel) as SeriesData[] || [];
    const resolvedMetric = resolveBoundValue(props.metric as BoundValue | undefined, dataModel) as string || 'Value';
    const resolvedChartType = (resolveBoundValue(props.chartType as BoundValue | undefined, dataModel) as string) || 'line';
    const resolvedAnnotations = resolveBoundValue(props.annotations as BoundValue | undefined, dataModel) as Annotation[] || [];

    // Build ECharts option
    const option = useMemo(() => {
        // Extract all unique periods for x-axis
        const allPeriods = new Set<string>();
        for (const s of resolvedSeries) {
            for (const d of s.data || []) {
                allPeriods.add(d.period);
            }
        }
        const xAxisData = Array.from(allPeriods).sort();

        // Build series config
        const seriesConfig = resolvedSeries.map((s, idx) => {
            const dataMap = new Map(s.data?.map(d => [d.period, d.value]) || []);
            const seriesData = xAxisData.map(period => dataMap.get(period) ?? null);
            const color = SERIES_COLORS[idx % SERIES_COLORS.length];

            // Filter annotations for this specific series
            const seriesAnnotations = resolvedAnnotations.filter(a => a.ticker === s.ticker);
            const markPointData = seriesAnnotations.map(a => {
                const value = dataMap.get(a.period);
                if (value === undefined) return null;
                return {
                    name: a.label,
                    coord: [a.period, value],
                    value: a.label,
                    itemStyle: { color: '#f59e0b' },
                    label: {
                        show: true,
                        position: 'top',
                        formatter: '{b}',
                        fontSize: 10,
                        color: '#f8fafc',
                        backgroundColor: 'rgba(15, 23, 42, 0.8)',
                        padding: [4, 8],
                        borderRadius: 4,
                        borderWidth: 1,
                        borderColor: '#f59e0b40',
                    }
                };
            }).filter(Boolean);

            const baseSeries = {
                name: s.ticker,
                type: resolvedChartType === 'area' ? 'line' : resolvedChartType,
                data: seriesData,
                smooth: true,
                symbol: 'circle',
                symbolSize: 6,
                itemStyle: { color },
                lineStyle: { width: 2 },
                markPoint: {
                    symbol: 'pin',
                    symbolSize: 14,
                    data: markPointData,
                    tooltip: {
                        formatter: (params: any) => {
                            const annot = seriesAnnotations.find(a => a.label === params.name);
                            if (annot && annot.details) {
                                return `<div style="max-width: 200px; white-space: normal;">
                                    <div style="font-weight: 600; color: #f59e0b; margin-bottom: 4px;">${annot.label}</div>
                                    <div style="font-size: 11px; line-height: 1.4;">${annot.details}</div>
                                </div>`;
                            }
                            return params.name;
                        }
                    }
                }
            };

            // Add area fill for 'area' type
            if (resolvedChartType === 'area') {
                return {
                    ...baseSeries,
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: color + '40' },
                                { offset: 1, color: color + '05' },
                            ],
                        },
                    },
                };
            }

            return baseSeries;
        });

        return {
            backgroundColor: 'transparent',
            title: {
                text: resolvedTitle,
                textStyle: {
                    color: '#f8fafc',
                    fontSize: 14,
                    fontWeight: 600,
                },
                left: 8,
                top: 8,
            },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                borderColor: 'rgba(148, 163, 184, 0.2)',
                textStyle: { color: '#f8fafc' },
                formatter: (params: unknown[]) => {
                    if (!Array.isArray(params) || params.length === 0) return '';
                    const firstParam = params[0] as { axisValue: string };
                    let content = `<div style="font-weight: 600; margin-bottom: 8px;">${firstParam.axisValue}</div>`;
                    for (const p of params as Array<{ marker: string; seriesName: string; value: number }>) {
                        content += `<div style="display: flex; justify-content: space-between; gap: 16px;">
                            <span>${p.marker} ${p.seriesName}</span>
                            <span style="font-weight: 600;">${formatValue(p.value)}</span>
                        </div>`;
                    }
                    return content;
                },
            },
            legend: {
                show: resolvedSeries.length > 1,
                data: resolvedSeries.map(s => s.ticker),
                textStyle: { color: '#94a3b8' },
                top: 8,
                right: 16,
            },
            grid: {
                left: 60,
                right: 24,
                top: resolvedSeries.length > 1 ? 60 : 48,
                bottom: 32,
            },
            xAxis: {
                type: 'category',
                data: xAxisData,
                axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
                axisLabel: { color: '#94a3b8', fontSize: 10 },
                axisTick: { show: false },
            },
            yAxis: {
                type: 'value',
                name: resolvedMetric,
                nameTextStyle: { color: '#64748b', fontSize: 10 },
                axisLine: { show: false },
                axisLabel: {
                    color: '#94a3b8',
                    fontSize: 10,
                    formatter: (v: number) => formatValue(v),
                },
                splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.1)' } },
            },
            series: seriesConfig,
        };
    }, [resolvedTitle, resolvedSeries, resolvedMetric, resolvedChartType]);

    // Handle empty state
    if (!resolvedSeries.length) {
        return (
            <motion.div
                className="rounded-xl p-6 flex items-center justify-center"
                style={{
                    backgroundColor: 'rgba(30, 41, 59, 0.5)',
                    border: '1px solid rgba(148, 163, 184, 0.1)',
                    aspectRatio: '16/9',
                }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
            >
                <p style={{ color: '#64748b' }}>No data available</p>
            </motion.div>
        );
    }

    return (
        <motion.div
            className="rounded-xl overflow-hidden"
            style={{
                backgroundColor: 'rgba(30, 41, 59, 0.5)',
                border: '1px solid rgba(148, 163, 184, 0.1)',
            }}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            data-component-id={componentId}
        >
            <LazyECharts
                option={option}
                style={{ height: '320px', width: '100%' }}
                opts={{ renderer: 'svg' }}
                theme="dark"
                fallbackHeight={320}
            />
        </motion.div>
    );
}

export default MetricChart;
