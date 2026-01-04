/**
 * Function: CorrelationMatrix — renders an ECharts heatmap for asset correlations.
 * Called from: ComponentRenderer via Registry when the A2UI catalog type `CorrelationMatrix` is present.
 * Invokes: LazyECharts (shared Suspense loader) to code-split the echarts bundle shared across Conversational Analytics and A2UI widgets.
 * Purpose: Visualize cross-asset correlations with shared loader + dark styling while keeping the initial dashboard bundle light.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import { resolveArray } from '../../a2ui/DataBinder';
import type { CorrelationMatrixProps } from '../../a2ui/types';
import LazyECharts from '../../../shared/LazyECharts';

export function CorrelationMatrix({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const matrixProps = props as unknown as CorrelationMatrixProps;

    const tickers = resolveArray<string>(matrixProps.tickers, dataModel, []);
    const matrix = resolveArray<number[]>(matrixProps.matrix, dataModel, []);

    // Convert matrix to ECharts heatmap data format
    // Format: [x, y, value]
    const heatmapData: [number, number, number][] = [];
    matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            heatmapData.push([x, y, value]);
        });
    });

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            position: 'top',
            formatter: (params: { value: [number, number, number] }) => {
                const [x, y, value] = params.value;
                const ticker1 = tickers[x] || `Asset ${x + 1}`;
                const ticker2 = tickers[y] || `Asset ${y + 1}`;
                return `${ticker1} ↔ ${ticker2}<br/>Correlation: ${value.toFixed(3)}`;
            },
        },
        grid: {
            left: '80px',
            right: '80px',
            top: '60px',
            bottom: '60px',
        },
        xAxis: {
            type: 'category',
            data: tickers,
            splitArea: {
                show: true,
            },
            axisLine: {
                lineStyle: { color: 'rgba(99, 102, 241, 0.3)' },
            },
            axisLabel: {
                color: '#94a3b8',
                fontSize: 11,
                rotate: 45,
            },
        },
        yAxis: {
            type: 'category',
            data: tickers,
            splitArea: {
                show: true,
            },
            axisLine: {
                lineStyle: { color: 'rgba(99, 102, 241, 0.3)' },
            },
            axisLabel: {
                color: '#94a3b8',
                fontSize: 11,
            },
        },
        visualMap: {
            min: -1,
            max: 1,
            calculable: true,
            orient: 'vertical',
            right: '0',
            top: 'center',
            inRange: {
                color: ['#ef4444', '#fbbf24', '#22c55e'],
            },
            textStyle: {
                color: '#94a3b8',
            },
        },
        series: [
            {
                name: 'Correlation',
                type: 'heatmap',
                data: heatmapData,
                label: {
                    show: tickers.length <= 6,
                    color: '#f8fafc',
                    fontSize: 10,
                    formatter: (params: { value: [number, number, number] }) => {
                        return params.value[2].toFixed(2);
                    },
                },
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowColor: 'rgba(0, 0, 0, 0.5)',
                    },
                },
            },
        ],
    };

    if (tickers.length === 0) {
        return (
            <div
                className="a2ui-correlation-matrix"
                data-component-id={componentId}
                style={{
                    padding: '2rem',
                    textAlign: 'center',
                    color: '#64748b',
                    backgroundColor: 'rgba(30, 41, 59, 0.3)',
                    borderRadius: '8px',
                }}
            >
                No correlation data available
            </div>
        );
    }

    return (
        <div
            className="a2ui-correlation-matrix"
            data-component-id={componentId}
            style={{
                width: '100%',
                height: '400px',
            }}
        >
            <LazyECharts
                option={option}
                style={{ height: '100%', width: '100%' }}
                theme="dark"
                fallbackHeight="100%"
            />
        </div>
    );
}
