/**
 * Function: MessageBubble — Renders individual chat messages with modern ChatGPT/Claude styling
 * Called from: ConversationalAnalyticsPage for each message in thread
 * Purpose: Displays user/assistant messages with charts, data, news, and markdown content
 */

import React, { useState, useRef, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ThinkingStep, NewsResult, NewsArticle } from './hooks/useSSEStream';
import { theme, motionVariants } from './styles';

type ValueMeta = {
  unit?: string;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  scale?: number;
  from_ratio?: boolean;
};

// Function: getNumericValue — helper used by label/tooltip formatters to coerce ECharts values to numbers.
const getNumericValue = (value: unknown): number | null => {
  if (Array.isArray(value)) {
    const last = value[value.length - 1];
    return typeof last === 'number' && Number.isFinite(last) ? last : null;
  }
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

// Function: resolveValueMeta — derives unit/scale metadata from backend-provided value_meta or chart title hints.
const resolveValueMeta = (option: Record<string, any>): ValueMeta => {
  const rawMeta = (option.value_meta || option.valueMeta || option.meta || {}) as Record<string, any>;
  const unit = (rawMeta.unit || rawMeta.value_unit || rawMeta.valueUnit || rawMeta.metric_unit) as string | undefined;
  const titleText = String(option?.title?.text || '').toLowerCase();
  let resolvedUnit = unit ? unit.toLowerCase() : 'auto';

  if (resolvedUnit === 'auto' || !resolvedUnit) {
    if (titleText.includes('margin') || titleText.includes('%')) {
      resolvedUnit = 'percentage';
    } else if (titleText.includes('revenue') || titleText.includes('sales')) {
      resolvedUnit = 'millions_usd';
    } else {
      resolvedUnit = 'auto';
    }
  }

  const suffix =
    rawMeta.suffix ??
    (resolvedUnit === 'percentage'
      ? '%'
      : resolvedUnit === 'millions_usd'
        ? 'M'
        : resolvedUnit === 'billions_usd'
          ? 'B'
          : '');

  const prefix =
    rawMeta.prefix ??
    (resolvedUnit === 'millions_usd' || resolvedUnit === 'billions_usd' ? '$' : '');

  const scale =
    rawMeta.scale ??
    (resolvedUnit === 'millions_usd'
      ? 1_000_000
      : resolvedUnit === 'billions_usd'
        ? 1_000_000_000
        : 1);

  const decimals = rawMeta.decimals ?? (resolvedUnit === 'percentage' ? 1 : 1);
  const fromRatio = rawMeta.from_ratio ?? resolvedUnit === 'percentage';

  return { unit: resolvedUnit, suffix, prefix, decimals, scale, from_ratio: fromRatio };
};

// Function: formatValueWithUnit — applies UOM/decimal rules before labels/tooltips render.
const formatValueWithUnit = (value: unknown, meta: ValueMeta): string => {
  const numeric = getNumericValue(value);
  if (numeric === null) return '';

  let display = numeric;
  if (meta.unit === 'percentage' && meta.from_ratio && Math.abs(display) <= 1.5) {
    display = display * 100;
  }

  if (meta.scale && meta.scale > 1) {
    display = display / meta.scale;
  }

  const decimals = typeof meta.decimals === 'number' && meta.decimals >= 0 ? meta.decimals : 1;
  const prefix = meta.prefix ?? '';
  const suffix = meta.suffix ?? '';

  return `${prefix}${display.toFixed(decimals)}${suffix}`;
};

// Function: enhanceEChartsConfig — used before rendering to force right-side legend and data labels with units.
const enhanceEChartsConfig = (config: Record<string, unknown>): Record<string, unknown> => {
  const option: any = { ...(config as any) };
  const seriesArray = Array.isArray(option.series) ? option.series.map((s: any) => ({ ...s })) : [];
  option.series = seriesArray;

  const isPie = seriesArray.some((s: any) => s.type === 'pie');
  const valueMeta = resolveValueMeta(option);

  const legendSource = Array.isArray(option.legend) ? option.legend[0] || {} : option.legend || {};
  const legendData =
    legendSource.data ??
    seriesArray
      .map((s: any) => s.name)
      .filter((name: any) => typeof name === 'string' && name.length > 0);

  option.legend = {
    ...legendSource,
    orient: 'vertical',
    right: legendSource.right ?? '2%',
    top: legendSource.top ?? 'middle',
    textStyle: { color: '#374151', ...(legendSource.textStyle || {}) },
    data: legendData,
  };

  if (!isPie) {
    option.grid = {
      left: (option.grid && option.grid.left) || '3%',
      right: '22%',
      bottom: (option.grid && option.grid.bottom) || '3%',
      containLabel: true,
      ...(option.grid || {}),
    };
  }

  const formatWithMeta = (val: any) => formatValueWithUnit(val, valueMeta);

  option.tooltip = {
    ...(option.tooltip || {}),
    valueFormatter: (val: any) => formatWithMeta(val),
  };

  seriesArray.forEach((series: any) => {
    const labelBase = series.label || {};
    if (series.type === 'pie') {
      series.label = {
        ...labelBase,
        show: labelBase.show ?? true,
        formatter: (params: any) => `${params.name}: ${formatWithMeta(params.value)}`,
      };
    } else {
      series.label = {
        ...labelBase,
        show: labelBase.show ?? true,
        position: labelBase.position ?? 'top',
        formatter: (params: any) => formatWithMeta(params.value),
        color: (labelBase as any)?.color || '#111827',
      };
    }
  });

  if (!isPie) {
    const yAxisConfig = option.yAxis ?? { type: 'value' };
    if (Array.isArray(yAxisConfig)) {
      option.yAxis = yAxisConfig.map((axis: any) => ({
        ...axis,
        axisLabel: {
          ...(axis.axisLabel || {}),
          formatter: (val: any) => formatWithMeta(val),
          color: (axis.axisLabel && axis.axisLabel.color) || '#111827',
        },
      }));
    } else {
      option.yAxis = {
        ...yAxisConfig,
        axisLabel: {
          ...(yAxisConfig.axisLabel || {}),
          formatter: (val: any) => formatWithMeta(val),
          color: (yAxisConfig.axisLabel && yAxisConfig.axisLabel.color) || '#111827',
        },
      };
    }
  }

  return option;
};

// Function: TradingViewWidget — called when chartConfig.widget_type === 'tradingview' to render the Advanced Chart widget.
// Called from: MessageBubble render path inside ConversationalAnalyticsPage message list.
// Purpose: Mounts TradingView's latest advanced-chart embed with the required container structure to avoid blank renders.
const TradingViewWidget: React.FC<{ config: Record<string, unknown> }> = ({ config }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetId = useRef(`tradingview_${Date.now()}`);
  const rawHeight = Number((config as any).height);
  const widgetHeight = Number.isFinite(rawHeight) ? rawHeight : 380;

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    container.innerHTML = '';

    const widgetContainer = document.createElement('div');
    widgetContainer.className = 'tradingview-widget-container';
    widgetContainer.style.height = `${widgetHeight}px`;
    widgetContainer.style.width = '100%';

    const innerDiv = document.createElement('div');
    innerDiv.id = widgetId.current;
    innerDiv.className = 'tradingview-widget-container__widget';
    innerDiv.style.height = 'calc(100% - 32px)';
    innerDiv.style.width = '100%';

    const copyright = document.createElement('div');
    copyright.className = 'tradingview-widget-copyright';
    copyright.style.fontSize = '10px';
    copyright.innerHTML =
      '<span>Quotes by <a href="https://www.tradingview.com" rel="noopener nofollow" target="_blank">TradingView</a></span>';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: config.symbol || 'NASDAQ:NVDA',
      interval: config.interval || 'D',
      timezone: config.timezone || 'Etc/UTC',
      theme: (config.theme as string) || 'dark',
      style: String(config.style || '1'),
      locale: (config.locale as string) || 'en',
      hide_top_toolbar: Boolean((config as any).hide_top_toolbar ?? false),
      hide_side_toolbar: Boolean((config as any).hide_side_toolbar ?? false),
      allow_symbol_change: true,
      withdateranges: (config as any).withdateranges ?? true,
      save_image: (config as any).save_image ?? false,
      studies: Array.isArray((config as any).studies) ? (config as any).studies : [],
      support_host: 'https://www.tradingview.com',
    });

    widgetContainer.appendChild(innerDiv);
    widgetContainer.appendChild(copyright);
    widgetContainer.appendChild(script);
    container.appendChild(widgetContainer);

    return () => {
      if (container) {
        container.innerHTML = '';
      }
    };
  }, [config, widgetHeight]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="mb-4 rounded-xl overflow-hidden"
      style={{
        border: `1px solid ${theme.colors.border.medium}`,
        backgroundColor: '#131722',
      }}
    >
      <div
        className="px-4 py-2.5 flex items-center gap-2"
        style={{
          backgroundColor: theme.colors.bg.elevated,
          borderBottom: `1px solid ${theme.colors.border.subtle}`,
        }}
      >
        <span className="text-lg">📈</span>
        <span className="text-sm font-medium" style={{ color: theme.colors.text.secondary }}>
          TradingView Chart
        </span>
        <span className="text-sm font-semibold" style={{ color: theme.colors.text.primary }}>
          {String(config.symbol)}
        </span>
      </div>
      <div ref={containerRef} style={{ height: '380px' }} />
    </motion.div>
  );
};

// News Card Component
const NewsCard: React.FC<{ news: NewsResult }> = ({ news }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-4 rounded-xl overflow-hidden"
      style={{
        backgroundColor: theme.colors.bg.elevated,
        border: `1px solid ${theme.colors.border.medium}`,
      }}
    >
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{ borderBottom: `1px solid ${theme.colors.border.subtle}` }}
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">📰</span>
          <div>
            <span className="text-sm font-medium" style={{ color: theme.colors.text.primary }}>
              News Sentiment: {news.ticker}
            </span>
            <span className="text-xs ml-2" style={{ color: theme.colors.text.muted }}>
              {news.articles.length} articles
            </span>
          </div>
        </div>
        <div
          className="px-3 py-1 rounded-full text-xs font-semibold"
          style={{
            backgroundColor:
              news.aggregate_sentiment >= 0.15
                ? theme.colors.status.success + '20'
                : news.aggregate_sentiment > -0.15
                  ? theme.colors.status.warning + '20'
                  : theme.colors.status.error + '20',
            color:
              news.aggregate_sentiment >= 0.15
                ? theme.colors.status.success
                : news.aggregate_sentiment > -0.15
                  ? theme.colors.status.warning
                  : theme.colors.status.error,
          }}
        >
          {news.aggregate_label} ({news.aggregate_sentiment > 0 ? '+' : ''}
          {news.aggregate_sentiment.toFixed(2)})
        </div>
      </div>

      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-2 text-left flex items-center gap-2 transition-colors"
        style={{ backgroundColor: 'transparent' }}
      >
        <motion.span
          animate={{ rotate: isExpanded ? 90 : 0 }}
          className="text-xs"
          style={{ color: theme.colors.text.muted }}
        >
          ▶
        </motion.span>
        <span className="text-xs" style={{ color: theme.colors.text.secondary }}>
          {isExpanded ? 'Hide' : 'Show'} articles with citations
        </span>
      </button>

      {isExpanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="px-4 pb-4 space-y-3"
        >
          {news.articles.map((article: NewsArticle, idx: number) => (
            <div
              key={idx}
              className="p-3 rounded-lg"
              style={{
                backgroundColor: theme.colors.bg.tertiary,
                border: `1px solid ${theme.colors.border.subtle}`,
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium hover:underline"
                  style={{ color: theme.colors.status.info }}
                >
                  {article.title}
                </a>
                <span
                  className="shrink-0 text-xs px-2 py-0.5 rounded-full"
                  style={{
                    backgroundColor: article.sentiment_color + '20',
                    color: article.sentiment_color,
                  }}
                >
                  {article.sentiment_label}
                </span>
              </div>
              <p className="text-xs mt-2" style={{ color: theme.colors.text.muted }}>
                {article.summary}
              </p>
              <div className="flex items-center gap-2 mt-2">
                <span className="text-xs" style={{ color: theme.colors.text.muted }}>
                  📌 {article.source}
                </span>
                {article.topics.length > 0 && (
                  <span className="text-xs" style={{ color: theme.colors.text.muted }}>
                    • {article.topics.join(', ')}
                  </span>
                )}
              </div>
            </div>
          ))}
        </motion.div>
      )}
    </motion.div>
  );
};

// Data Preview Table
const DataPreview: React.FC<{ data: { rows: unknown[]; columns: string[] } }> = ({ data }) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    className="mb-4 rounded-xl overflow-hidden"
    style={{
      backgroundColor: theme.colors.bg.elevated,
      border: `1px solid ${theme.colors.border.medium}`,
    }}
  >
    <div
      className="px-4 py-2.5 flex items-center gap-2"
      style={{ borderBottom: `1px solid ${theme.colors.border.subtle}` }}
    >
      <span className="text-lg">📑</span>
      <span className="text-sm font-medium" style={{ color: theme.colors.text.secondary }}>
        Data Preview
      </span>
      <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: theme.colors.bg.tertiary, color: theme.colors.text.muted }}>
        {data.rows.length} rows
      </span>
    </div>
    <div className="overflow-x-auto p-4">
      <table className="w-full text-sm">
        <thead>
          <tr>
            {data.columns.map((col) => (
              <th
                key={col}
                className="text-left px-3 py-2 text-xs font-semibold"
                style={{ color: theme.colors.text.muted, borderBottom: `1px solid ${theme.colors.border.subtle}` }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.slice(0, 5).map((row: Record<string, unknown>, idx: number) => (
            <tr key={idx}>
              {data.columns.map((col) => (
                <td
                  key={col}
                  className="px-3 py-2 text-sm"
                  style={{ color: theme.colors.text.secondary, borderBottom: `1px solid ${theme.colors.border.subtle}` }}
                >
                  {String(row[col] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </motion.div>
);

// Main MessageBubble component
interface MessageBubbleProps {
  role: 'user' | 'assistant';
  content: string;
  thinkingSteps?: ThinkingStep[];
  chartConfig?: Record<string, unknown> | null;
  dataResult?: { rows: unknown[]; columns: string[] } | null;
  newsResult?: NewsResult | null;
  isStreaming?: boolean;
  agentLabel?: string | null;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
  role,
  content,
  chartConfig,
  dataResult,
  newsResult,
  isStreaming,
  agentLabel,
}) => {
  const isUser = role === 'user';
  const isTradingView = chartConfig?.widget_type === 'tradingview';
  const chartOptions = useMemo(
    () =>
      chartConfig && !isTradingView
        ? enhanceEChartsConfig(chartConfig as Record<string, unknown>)
        : chartConfig,
    [chartConfig, isTradingView],
  );

  return (
    <motion.div
      {...motionVariants.fadeInUp}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-5`}
    >
      <div
        className={`max-w-[85%] ${isUser ? '' : 'w-full'}`}
        style={{ maxWidth: isUser ? '70%' : '100%' }}
      >
        {/* User message */}
        {isUser && (
          <div
            className="px-5 py-3 rounded-2xl"
            style={{
              background: theme.colors.user.bg,
              color: theme.colors.user.text,
              borderRadius: '20px 20px 4px 20px',
            }}
          >
            <p className="text-sm leading-relaxed">{content}</p>
          </div>
        )}

        {/* Assistant message */}
        {!isUser && (
          <div className="space-y-4">
            {/* TradingView Widget */}
            {chartConfig && isTradingView && <TradingViewWidget config={chartConfig} />}

            {/* ECharts visualization */}
            {chartOptions && !isTradingView && (
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-xl overflow-hidden"
                style={{
                  backgroundColor: theme.colors.bg.elevated,
                  border: `1px solid ${theme.colors.border.medium}`,
                }}
              >
                <div
                  className="px-4 py-2.5 flex items-center gap-2"
                  style={{ borderBottom: `1px solid ${theme.colors.border.subtle}` }}
                >
                  <span className="text-lg">📊</span>
                  <span className="text-sm font-medium" style={{ color: theme.colors.text.secondary }}>
                    Chart
                  </span>
                </div>
                <div className="p-3">
                  <ReactECharts
                    option={chartOptions as Record<string, unknown>}
                    style={{ height: '340px', width: '100%' }}
                    theme="light"
                    opts={{ renderer: 'canvas' }}
                  />
                </div>
              </motion.div>
            )}

            {/* News Card */}
            {newsResult && newsResult.articles && newsResult.articles.length > 0 && (
              <NewsCard news={newsResult} />
            )}

            {/* Data Preview */}
            {dataResult && dataResult.rows && dataResult.rows.length > 0 && (
              <DataPreview data={dataResult} />
            )}

            {/* Markdown content */}
            {content && (
              <div
                className="prose prose-sm max-w-none prose-invert
                  prose-headings:text-slate-100 prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2
                  prose-h2:text-xl prose-h3:text-lg
                  prose-p:text-slate-300 prose-p:leading-relaxed prose-p:my-2
                  prose-strong:text-amber-400 prose-strong:font-semibold
                  prose-ul:my-2 prose-li:text-slate-300 prose-li:my-0.5
                  prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline
                  prose-code:text-amber-400 prose-code:bg-slate-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:text-sm
                  prose-pre:bg-slate-800 prose-pre:rounded-xl prose-pre:p-4
                "
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                {isStreaming && (
                  <motion.span
                    className="inline-block w-0.5 h-5 ml-0.5"
                    style={{ backgroundColor: theme.colors.accent.primary }}
                    animate={{ opacity: [1, 0] }}
                    transition={{ duration: 0.5, repeat: Infinity }}
                  />
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default MessageBubble;

