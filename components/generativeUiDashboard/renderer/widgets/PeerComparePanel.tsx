/**
 * Function: PeerComparePanel — Consolidated peer comparison view
 * Called from: Registry.tsx when rendering a2ui_peer_compare skill dashboards
 * Invokes: LazyECharts (shared Suspense loader) for chart, useStreamingText for narrative
 * Purpose: Combines revenue comparison chart, comparison table, and AI insight into one panel
 * 
 * Design Pattern: Unified panel replacing separate chart + heatmap + table + insight panels
 */

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import { resolveArray, resolveString, getByPath } from '../../a2ui/DataBinder';
import type { BoundValue } from '../../a2ui/types';
import { useStreamingText } from '../../hooks/useStreamingText';
import LazyECharts from '../../../shared/LazyECharts';

interface ChartDataPoint {
    period: string;
    value: number;
}

interface ChartSeries {
    ticker: string;
    data: ChartDataPoint[];
}

interface TableColumn {
    key: string;
    label: string;
    type: 'string' | 'currency' | 'percentage' | 'number';
}

interface TableRow {
    ticker: string;
    latest_value: number;
    yoy_change: number;
    [key: string]: string | number;
}

interface NewsEvent {
    title: string;
    summary?: string;
    date?: string;
    sentiment?: 'positive' | 'negative' | 'neutral';
    source?: string;
}

interface NewsData {
    ticker: string;
    events: NewsEvent[];
    aggregate_sentiment?: number;
    aggregate_label?: string;
}

// Props come from A2UI as BoundValue objects
interface PeerComparePanelProps {
    title?: BoundValue;
    metric?: BoundValue;
    tickers?: BoundValue;
    chart?: {
        series: BoundValue;
    };
    table?: {
        columns: BoundValue;
        rows: BoundValue;
    };
    explanation?: {
        title: BoundValue;
        text: BoundValue;
    };
}

// Premium theme tokens
const theme = {
    colors: {
        bg: {
            card: 'rgba(15, 23, 42, 0.95)',
            elevated: 'rgba(30, 41, 59, 0.8)',
            section: 'rgba(51, 65, 85, 0.4)',
            hover: 'rgba(71, 85, 105, 0.5)',
        },
        border: {
            subtle: 'rgba(148, 163, 184, 0.15)',
            medium: 'rgba(148, 163, 184, 0.25)',
        },
        text: {
            primary: '#f8fafc',
            secondary: '#94a3b8',
            muted: '#64748b',
        },
        accent: {
            primary: '#6366f1',
            secondary: '#8b5cf6',
            positive: '#10b981',
            negative: '#ef4444',
            info: '#38bdf8',
        },
        chart: ['#6366f1', '#f43f5e', '#10b981', '#f59e0b', '#8b5cf6'],
    },
    shadows: {
        lg: '0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.15)',
        glow: '0 0 20px rgba(99, 102, 241, 0.15)',
    },
};

type TabId = 'overview' | 'data';

export function PeerComparePanel({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const [activeTab, setActiveTab] = useState<TabId>('overview');

    const panelProps = props as unknown as PeerComparePanelProps;

    // Resolve data from props or dataModel
    const title = resolveString(panelProps.title, dataModel, 'Peer Comparison');
    const metric = resolveString(panelProps.metric, dataModel, 'Revenue');
    const tickers = resolveArray<string>(panelProps.tickers, dataModel, []);

    // Chart series
    const chartSeries = useMemo(() => {
        if (panelProps.chart?.series) {
            return resolveArray<ChartSeries>(panelProps.chart.series, dataModel, []);
        }
        return [];
    }, [panelProps.chart?.series, dataModel]);

    // Table data
    const tableColumns = useMemo(() => {
        if (panelProps.table?.columns) {
            return resolveArray<TableColumn>(panelProps.table.columns, dataModel, []);
        }
        return [];
    }, [panelProps.table?.columns, dataModel]);

    const tableRows = useMemo(() => {
        if (panelProps.table?.rows) {
            return resolveArray<TableRow>(panelProps.table.rows, dataModel, []);
        }
        return [];
    }, [panelProps.table?.rows, dataModel]);

    // Explanation - generate a proper comparison-focused title and text
    const defaultTitle = tickers.length > 0
        ? `${tickers.join(' vs ')} ${metric} Analysis`
        : `${metric} Analysis`;
    const defaultText = tickers.length > 0
        ? `Comparing ${metric.toLowerCase()} performance across ${tickers.join(', ')}.`
        : `Analyzing ${metric.toLowerCase()} data.`;

    const explanationTitle = resolveString(panelProps.explanation?.title, dataModel, defaultTitle);
    const explanationText = resolveString(
        panelProps.explanation?.text,
        dataModel,
        defaultText
    );

    // Get news data from dataModel using getByPath
    const newsData = useMemo(() => {
        // Try /data/news first (A2UI data model structure)
        const newsFromPath = getByPath(dataModel, '/data/news') as NewsData | undefined;
        if (newsFromPath) return newsFromPath;

        // Fallback to direct access on dataModel
        const news = (dataModel as Record<string, unknown>)?.news as NewsData | undefined;
        return news || null;
    }, [dataModel]);

    // Streaming text for AI analysis (the main insight)
    // Use explanationTitle as resetKey to force restart when analysis changes (e.g., switching history tabs)
    const { displayText, isComplete } = useStreamingText(explanationText, {
        speed: 15,
        resetKey: `${componentId}-${explanationTitle}`,
    });

    // Process chart data - sort by period and deduplicate
    const processedChartData = useMemo(() => {
        if (!chartSeries.length) return { periods: [], series: [] };

        // Collect all unique periods
        const periodSet = new Set<string>();
        chartSeries.forEach(s => {
            s.data?.forEach(d => periodSet.add(d.period));
        });

        // Sort periods chronologically (Q1.0 2020.0 format)
        const periods = Array.from(periodSet).sort((a, b) => {
            const parseQuarterYear = (str: string) => {
                const match = str.match(/Q(\d+)\.?\d*\s+(\d{4})/);
                if (!match) return 0;
                return parseInt(match[2]) * 10 + parseInt(match[1]);
            };
            return parseQuarterYear(a) - parseQuarterYear(b);
        });

        // Format period labels
        const formattedPeriods = periods.map(p => {
            const match = p.match(/Q(\d+)\.?\d*\s+(\d{4})/);
            return match ? `Q${match[1]} ${match[2]}` : p;
        });

        // Build series data aligned to periods
        const series = chartSeries.map((s, idx) => {
            const dataMap = new Map<string, number>();
            // Use only the latest value for each period (dedupe)
            s.data?.forEach(d => {
                dataMap.set(d.period, d.value);
            });

            return {
                name: s.ticker,
                type: 'line',
                smooth: true,
                symbol: 'circle',
                symbolSize: 6,
                lineStyle: {
                    width: 2.5,
                    color: theme.colors.chart[idx % theme.colors.chart.length],
                },
                itemStyle: {
                    color: theme.colors.chart[idx % theme.colors.chart.length],
                },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                            { offset: 0, color: `${theme.colors.chart[idx % theme.colors.chart.length]}33` },
                            { offset: 1, color: `${theme.colors.chart[idx % theme.colors.chart.length]}05` },
                        ],
                    },
                },
                data: periods.map(p => dataMap.get(p) ?? null),
            };
        });

        return { periods: formattedPeriods, series };
    }, [chartSeries]);

    // ECharts option
    const chartOption = useMemo(() => ({
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            borderColor: 'rgba(99, 102, 241, 0.3)',
            textStyle: { color: '#f8fafc' },
            formatter: (params: Array<{ seriesName: string; value: number; axisValue: string; color: string }>) => {
                const header = `<div style="margin-bottom:8px;font-weight:600">${params[0]?.axisValue}</div>`;
                const items = params.map(p => {
                    const value = p.value != null ? formatCurrency(p.value) : 'N/A';
                    return `<div style="display:flex;align-items:center;gap:8px;margin:4px 0">
                        <span style="width:8px;height:8px;border-radius:50%;background:${p.color}"></span>
                        <span>${p.seriesName}:</span>
                        <span style="font-weight:600">${value}</span>
                    </div>`;
                }).join('');
                return header + items;
            },
        },
        legend: {
            data: chartSeries.map(s => s.ticker),
            top: 10,
            textStyle: { color: '#94a3b8' },
            icon: 'circle',
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            top: '50px',
            containLabel: true,
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: processedChartData.periods,
            axisLine: { lineStyle: { color: 'rgba(99, 102, 241, 0.3)' } },
            axisLabel: { color: '#64748b', fontSize: 10, rotate: 45 },
            splitLine: { show: false },
        },
        yAxis: {
            type: 'value',
            axisLine: { show: false },
            axisLabel: {
                color: '#64748b',
                formatter: (value: number) => formatCompact(value),
            },
            splitLine: { lineStyle: { color: 'rgba(99, 102, 241, 0.1)' } },
        },
        series: processedChartData.series,
    }), [processedChartData, chartSeries]);

    // Format helpers
    function formatCurrency(value: number): string {
        if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
        if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
        return `$${value.toLocaleString()}`;
    }

    function formatCompact(value: number): string {
        if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
        if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
        return value.toLocaleString();
    }

    function formatPercentage(value: number): string {
        if (value === null || value === undefined) return 'N/A';
        const sign = value >= 0 ? '+' : '';
        return `${sign}${value.toFixed(1)}%`;
    }

    const tabs: { id: TabId; label: string; icon: string }[] = [
        { id: 'overview', label: 'Overview', icon: '📊' },
        { id: 'data', label: 'Data Table', icon: '📋' },
    ];

    return (
        <motion.div
            layout
            layoutId={componentId}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="a2ui-peer-compare-panel"
            data-component-id={componentId}
            style={{
                backgroundColor: theme.colors.bg.card,
                borderRadius: '16px',
                border: `1px solid ${theme.colors.border.medium}`,
                boxShadow: `${theme.shadows.lg}, ${theme.shadows.glow}`,
                backdropFilter: 'blur(16px)',
                overflow: 'hidden',
            }}
        >
            {/* Header */}
            <div
                style={{
                    padding: '1rem 1.5rem',
                    borderBottom: `1px solid ${theme.colors.border.subtle}`,
                    background: `linear-gradient(180deg, ${theme.colors.bg.elevated} 0%, ${theme.colors.bg.card} 100%)`,
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div
                            style={{
                                width: '40px',
                                height: '40px',
                                borderRadius: '12px',
                                background: `linear-gradient(135deg, ${theme.colors.accent.primary}33, ${theme.colors.accent.secondary}33)`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '1.25rem',
                            }}
                        >
                            ⚖️
                        </div>
                        <div>
                            <h2
                                style={{
                                    fontSize: '1.1rem',
                                    fontWeight: 700,
                                    color: theme.colors.text.primary,
                                    margin: 0,
                                }}
                            >
                                {title}
                            </h2>
                            <p
                                style={{
                                    fontSize: '0.75rem',
                                    color: theme.colors.text.muted,
                                    margin: 0,
                                }}
                            >
                                {metric} comparison • {tickers.length} companies
                            </p>
                        </div>
                    </div>

                    {/* Ticker badges */}
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        {tickers.map((ticker, idx) => (
                            <span
                                key={ticker}
                                style={{
                                    padding: '0.25rem 0.75rem',
                                    borderRadius: '9999px',
                                    fontSize: '0.75rem',
                                    fontWeight: 600,
                                    backgroundColor: `${theme.colors.chart[idx % theme.colors.chart.length]}22`,
                                    color: theme.colors.chart[idx % theme.colors.chart.length],
                                    border: `1px solid ${theme.colors.chart[idx % theme.colors.chart.length]}44`,
                                }}
                            >
                                {ticker}
                            </span>
                        ))}
                    </div>
                </div>
            </div>

            {/* Tab Navigation */}
            <div
                style={{
                    display: 'flex',
                    gap: '0.25rem',
                    padding: '0.5rem 1.5rem',
                    borderBottom: `1px solid ${theme.colors.border.subtle}`,
                }}
            >
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.375rem',
                            padding: '0.5rem 1rem',
                            borderRadius: '8px',
                            border: 'none',
                            cursor: 'pointer',
                            fontSize: '0.8rem',
                            fontWeight: 500,
                            transition: 'all 0.15s ease',
                            backgroundColor: activeTab === tab.id
                                ? `${theme.colors.accent.primary}22`
                                : 'transparent',
                            color: activeTab === tab.id
                                ? theme.colors.accent.primary
                                : theme.colors.text.secondary,
                        }}
                    >
                        <span>{tab.icon}</span>
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Content */}
            <div style={{ padding: '1.5rem' }}>
                <AnimatePresence mode="wait">
                    {activeTab === 'overview' && (
                        <motion.div
                            key="overview"
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 10 }}
                            transition={{ duration: 0.15 }}
                        >
                            {/* Chart */}
                            <div
                                style={{
                                    backgroundColor: theme.colors.bg.section,
                                    borderRadius: '12px',
                                    padding: '1rem',
                                    marginBottom: '1rem',
                                }}
                            >
                                <h3 style={{
                                    fontSize: '0.85rem',
                                    fontWeight: 600,
                                    color: theme.colors.text.primary,
                                    marginBottom: '0.75rem',
                                }}>
                                    {metric} Comparison
                                </h3>
                                {processedChartData.periods.length > 0 ? (
                                    <LazyECharts
                                        option={chartOption}
                                        style={{ height: '280px', width: '100%' }}
                                        theme="dark"
                                        fallbackHeight={280}
                                    />
                                ) : (
                                    <div style={{
                                        height: '280px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        color: theme.colors.text.muted,
                                    }}>
                                        No chart data available
                                    </div>
                                )}
                            </div>

                            {/* Quick Stats Grid */}
                            <div
                                style={{
                                    display: 'grid',
                                    gridTemplateColumns: `repeat(${Math.min(tickers.length, 3)}, 1fr)`,
                                    gap: '1rem',
                                    marginBottom: '1rem',
                                }}
                            >
                                {tableRows.map((row, idx) => (
                                    <motion.div
                                        key={row.ticker}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: 0.1 * idx }}
                                        style={{
                                            padding: '1rem',
                                            borderRadius: '12px',
                                            backgroundColor: theme.colors.bg.section,
                                            border: `1px solid ${theme.colors.chart[idx % theme.colors.chart.length]}33`,
                                        }}
                                    >
                                        <div style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'space-between',
                                            marginBottom: '0.5rem',
                                        }}>
                                            <span style={{
                                                fontSize: '0.9rem',
                                                fontWeight: 700,
                                                color: theme.colors.chart[idx % theme.colors.chart.length],
                                            }}>
                                                {row.ticker}
                                            </span>
                                            <span style={{
                                                fontSize: '0.75rem',
                                                fontWeight: 600,
                                                padding: '0.125rem 0.5rem',
                                                borderRadius: '4px',
                                                backgroundColor: row.yoy_change != null && row.yoy_change >= 0
                                                    ? `${theme.colors.accent.positive}22`
                                                    : row.yoy_change != null
                                                        ? `${theme.colors.accent.negative}22`
                                                        : `${theme.colors.text.muted}22`,
                                                color: row.yoy_change != null && row.yoy_change >= 0
                                                    ? theme.colors.accent.positive
                                                    : row.yoy_change != null
                                                        ? theme.colors.accent.negative
                                                        : theme.colors.text.muted,
                                            }}>
                                                {formatPercentage(row.yoy_change)} YoY
                                            </span>
                                        </div>
                                        <div style={{
                                            fontSize: '1.25rem',
                                            fontWeight: 700,
                                            color: theme.colors.text.primary,
                                        }}>
                                            {formatCurrency(row.latest_value)}
                                        </div>
                                        <div style={{
                                            fontSize: '0.7rem',
                                            color: theme.colors.text.muted,
                                            marginTop: '0.25rem',
                                        }}>
                                            Latest {metric}
                                        </div>
                                    </motion.div>
                                ))}
                            </div>

                            {/* AI Analysis Section - Streaming text */}
                            <div
                                style={{
                                    borderRadius: '12px',
                                    backgroundColor: theme.colors.bg.section,
                                    border: `1px solid ${theme.colors.border.subtle}`,
                                    padding: '1rem',
                                }}
                            >
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem',
                                    marginBottom: '0.75rem',
                                }}>
                                    <span style={{ fontSize: '1rem' }}>💡</span>
                                    <h3 style={{
                                        fontSize: '0.85rem',
                                        fontWeight: 600,
                                        color: theme.colors.text.primary,
                                        margin: 0,
                                    }}>
                                        {explanationTitle}
                                    </h3>
                                    {!isComplete && (
                                        <motion.span
                                            animate={{ opacity: [0.5, 1, 0.5] }}
                                            transition={{ duration: 1.5, repeat: Infinity }}
                                            style={{
                                                padding: '0.125rem 0.5rem',
                                                borderRadius: '4px',
                                                backgroundColor: `${theme.colors.accent.info}22`,
                                                color: theme.colors.accent.info,
                                                fontSize: '0.65rem',
                                                fontWeight: 500,
                                            }}
                                        >
                                            Streaming...
                                        </motion.span>
                                    )}
                                </div>
                                <p style={{
                                    fontSize: '0.85rem',
                                    lineHeight: 1.7,
                                    color: theme.colors.text.secondary,
                                    margin: 0,
                                }}>
                                    {displayText}
                                    {!isComplete && (
                                        <motion.span
                                            animate={{ opacity: [0, 1, 0] }}
                                            transition={{ repeat: Infinity, duration: 0.8 }}
                                            style={{
                                                display: 'inline-block',
                                                width: '2px',
                                                height: '1em',
                                                backgroundColor: theme.colors.accent.info,
                                                marginLeft: '2px',
                                                verticalAlign: 'middle',
                                            }}
                                        />
                                    )}
                                </p>
                            </div>

                            {/* News Sentiment Section */}
                            {newsData && newsData.events && newsData.events.length > 0 && (
                                <div
                                    style={{
                                        marginTop: '1rem',
                                        borderRadius: '12px',
                                        backgroundColor: theme.colors.bg.section,
                                        border: `1px solid ${theme.colors.border.subtle}`,
                                        overflow: 'hidden',
                                    }}
                                >
                                    {/* News Header */}
                                    <div
                                        style={{
                                            padding: '0.75rem 1rem',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'space-between',
                                            borderBottom: `1px solid ${theme.colors.border.subtle}`,
                                            backgroundColor: theme.colors.bg.elevated,
                                        }}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            <span style={{ fontSize: '1rem' }}>📰</span>
                                            <span style={{
                                                fontSize: '0.8rem',
                                                fontWeight: 600,
                                                color: theme.colors.text.primary,
                                            }}>
                                                News Sentiment: {newsData.ticker}
                                            </span>
                                            <span style={{
                                                fontSize: '0.7rem',
                                                color: theme.colors.text.muted,
                                            }}>
                                                {newsData.events.length} articles
                                            </span>
                                        </div>
                                        <span
                                            style={{
                                                padding: '0.25rem 0.75rem',
                                                borderRadius: '9999px',
                                                fontSize: '0.7rem',
                                                fontWeight: 600,
                                                backgroundColor: newsData.aggregate_label === 'Positive'
                                                    ? `${theme.colors.accent.positive}22`
                                                    : newsData.aggregate_label === 'Negative'
                                                        ? `${theme.colors.accent.negative}22`
                                                        : `${theme.colors.text.muted}22`,
                                                color: newsData.aggregate_label === 'Positive'
                                                    ? theme.colors.accent.positive
                                                    : newsData.aggregate_label === 'Negative'
                                                        ? theme.colors.accent.negative
                                                        : theme.colors.text.secondary,
                                            }}
                                        >
                                            {newsData.aggregate_label || 'Neutral'}
                                            {newsData.aggregate_sentiment !== undefined && (
                                                <> ({newsData.aggregate_sentiment > 0 ? '+' : ''}{newsData.aggregate_sentiment.toFixed(2)})</>
                                            )}
                                        </span>
                                    </div>

                                    {/* News Events List */}
                                    <div style={{ padding: '0.75rem' }}>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                            {newsData.events.slice(0, 3).map((event, idx) => (
                                                <div
                                                    key={idx}
                                                    style={{
                                                        padding: '0.625rem 0.75rem',
                                                        borderRadius: '8px',
                                                        backgroundColor: theme.colors.bg.elevated,
                                                        border: `1px solid ${theme.colors.border.subtle}`,
                                                    }}
                                                >
                                                    <div style={{
                                                        display: 'flex',
                                                        alignItems: 'flex-start',
                                                        gap: '0.5rem',
                                                    }}>
                                                        <span
                                                            style={{
                                                                width: '6px',
                                                                height: '6px',
                                                                borderRadius: '50%',
                                                                marginTop: '0.375rem',
                                                                flexShrink: 0,
                                                                backgroundColor: event.sentiment === 'positive'
                                                                    ? theme.colors.accent.positive
                                                                    : event.sentiment === 'negative'
                                                                        ? theme.colors.accent.negative
                                                                        : theme.colors.text.muted,
                                                            }}
                                                        />
                                                        <div style={{ flex: 1 }}>
                                                            <div style={{
                                                                fontSize: '0.75rem',
                                                                fontWeight: 500,
                                                                color: theme.colors.text.primary,
                                                                lineHeight: 1.4,
                                                            }}>
                                                                {event.title}
                                                            </div>
                                                            {event.summary && (
                                                                <div style={{
                                                                    fontSize: '0.65rem',
                                                                    color: theme.colors.text.muted,
                                                                    marginTop: '0.25rem',
                                                                    lineHeight: 1.4,
                                                                }}>
                                                                    {event.summary.slice(0, 100)}...
                                                                </div>
                                                            )}
                                                            <div style={{
                                                                fontSize: '0.6rem',
                                                                color: theme.colors.text.muted,
                                                                marginTop: '0.375rem',
                                                                display: 'flex',
                                                                gap: '0.5rem',
                                                            }}>
                                                                {event.source && <span>📌 {event.source}</span>}
                                                                {event.date && <span>• {event.date}</span>}
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </motion.div>
                    )}

                    {activeTab === 'data' && (
                        <motion.div
                            key="data"
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -10 }}
                            transition={{ duration: 0.15 }}
                        >
                            {/* Data Table */}
                            <div
                                style={{
                                    backgroundColor: theme.colors.bg.section,
                                    borderRadius: '12px',
                                    overflow: 'hidden',
                                }}
                            >
                                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                    <thead>
                                        <tr style={{ backgroundColor: theme.colors.bg.elevated }}>
                                            {tableColumns.map((col) => (
                                                <th
                                                    key={col.key}
                                                    style={{
                                                        padding: '0.875rem 1rem',
                                                        textAlign: col.type === 'string' ? 'left' : 'right',
                                                        fontSize: '0.75rem',
                                                        fontWeight: 600,
                                                        color: theme.colors.text.secondary,
                                                        borderBottom: `1px solid ${theme.colors.border.subtle}`,
                                                    }}
                                                >
                                                    {col.label}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {tableRows.map((row, rowIdx) => (
                                            <tr
                                                key={row.ticker}
                                                style={{
                                                    backgroundColor: rowIdx % 2 === 0
                                                        ? 'transparent'
                                                        : 'rgba(255, 255, 255, 0.02)',
                                                }}
                                            >
                                                {tableColumns.map((col) => {
                                                    const value = row[col.key];
                                                    let displayValue: string;

                                                    if (col.type === 'currency' && typeof value === 'number') {
                                                        displayValue = formatCurrency(value);
                                                    } else if (col.type === 'percentage' && typeof value === 'number') {
                                                        displayValue = formatPercentage(value);
                                                    } else {
                                                        displayValue = String(value);
                                                    }

                                                    return (
                                                        <td
                                                            key={col.key}
                                                            style={{
                                                                padding: '0.875rem 1rem',
                                                                textAlign: col.type === 'string' ? 'left' : 'right',
                                                                fontSize: '0.85rem',
                                                                color: col.key === 'ticker'
                                                                    ? theme.colors.chart[rowIdx % theme.colors.chart.length]
                                                                    : col.type === 'percentage'
                                                                        ? (typeof value === 'number' && value >= 0
                                                                            ? theme.colors.accent.positive
                                                                            : theme.colors.accent.negative)
                                                                        : theme.colors.text.primary,
                                                                fontWeight: col.key === 'ticker' ? 600 : 400,
                                                                borderBottom: `1px solid ${theme.colors.border.subtle}`,
                                                            }}
                                                        >
                                                            {displayValue}
                                                        </td>
                                                    );
                                                })}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Footer */}
            <div
                style={{
                    padding: '0.75rem 1.5rem',
                    borderTop: `1px solid ${theme.colors.border.subtle}`,
                    backgroundColor: theme.colors.bg.elevated,
                }}
            >
                <p
                    style={{
                        fontSize: '0.65rem',
                        color: theme.colors.text.muted,
                        margin: 0,
                        textAlign: 'center',
                        fontStyle: 'italic',
                    }}
                >
                    📊 AI-powered peer comparison based on financial data. For informational purposes only.
                </p>
            </div>
        </motion.div>
    );
}

export default PeerComparePanel;
