/**
 * Function: MessageBubble — Renders individual chat messages with charts, tables, news, skills, and artifacts.
 * Called from: ConversationalAnalyticsPage for both historical and streaming message rows.
 * Invokes: Helper format/preview components below plus ProcessPanel when process nodes stream in.
 * Purpose: Prevent runtime crashes during streaming while presenting rich agent responses inside the Next Gen Analytics experience.
 */

import React, { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ThinkingStep, NewsResult, HtmlArtifact, SkillInfo, ProcessNode, ProcessEdge, AgentInfo, DebugLog } from './hooks/useSSEStream';
import { configService } from '../../services/config';
import { theme, motionVariants } from './styles';
import ProcessPanel from './ProcessPanel';

type ValueMeta = {
  unit?: string;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  scale?: number;
  from_ratio?: boolean;
};

/**
 * Function: getNumericValue — called by formatValueWithUnit to coerce incoming cell values to numbers.
 * Invokes: Number/parseFloat to allow formatted strings like "1,234" or "12.3%".
 * Purpose: Avoid NaN/ReferenceError when rendering streaming data tables.
 */
const getNumericValue = (value: unknown): number | null => {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') return value;
  if (typeof value === 'string') {
    const cleaned = value.replace(/[%$,]/g, '');
    const parsed = parseFloat(cleaned);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

/**
 * Function: resolveValueMeta — called by DataPreview to infer display metadata per column name.
 * Invokes: simple heuristics (suffix detection) then merges any explicit meta overrides provided with rows.
 * Purpose: Keep numeric rendering legible without depending on backend-provided formatting.
 */
const resolveValueMeta = (column: string, meta?: ValueMeta): ValueMeta => {
  if (meta) return meta;
  const name = column.toLowerCase();
  if (name.includes('margin') || name.includes('growth') || name.includes('pct') || name.includes('%')) {
    return { suffix: '%', decimals: 1 };
  }
  if (name.includes('revenue') || name.includes('sales') || name.includes('amount') || name.includes('usd')) {
    return { prefix: '$', decimals: 0 };
  }
  return { decimals: 2 };
};

/**
 * Function: formatValueWithUnit — called by DataPreview cell renderer.
 * Invokes: getNumericValue + resolveValueMeta to apply scaling/units/decimals.
 * Purpose: Present numeric cells consistently while leaving non-numeric values untouched.
 */
const formatValueWithUnit = (value: unknown, column: string, meta?: ValueMeta): string => {
  if (value === null || value === undefined) return '—';
  const numeric = getNumericValue(value);
  const finalMeta = resolveValueMeta(column, meta);

  if (numeric === null) {
    return String(value);
  }

  const scaled = finalMeta.scale ? numeric * finalMeta.scale : numeric;
  const decimals = typeof finalMeta.decimals === 'number' ? finalMeta.decimals : 2;
  const formatted = scaled.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return `${finalMeta.prefix ?? ''}${formatted}${finalMeta.suffix ?? ''}`;
};

/**
 * Function: enhanceEChartsConfig — called by MessageBubble before passing chart options to ECharts.
 * Invokes: shallow merge to add dark theming and responsive defaults.
 * Purpose: Prevent undefined helper crash and keep charts readable in the dark theme.
 */
const enhanceEChartsConfig = (config: Record<string, unknown>): Record<string, unknown> => {
  const base = {
    backgroundColor: theme.colors.bg.elevated,
    textStyle: { color: theme.colors.text.primary },
    grid: { left: 50, right: 20, top: 40, bottom: 50 },
    tooltip: { trigger: 'axis', backgroundColor: '#0b1224', borderColor: theme.colors.border.medium },
  };
  return {
    ...base,
    ...config,
    textStyle: { ...base.textStyle, ...(config as any).textStyle },
    grid: { ...base.grid, ...(config as any).grid },
    tooltip: { ...base.tooltip, ...(config as any).tooltip },
  };
};

/**
 * Function: TradingViewWidget — called from MessageBubble when chartConfig.widget_type === 'tradingview'.
 * Invokes: renders an iframe embed using the provided symbol/URL.
 * Purpose: Replace missing helper that previously crashed rendering when trading widgets streamed in.
 */
const TradingViewWidget: React.FC<{ config: Record<string, unknown> }> = ({ config }) => {
  const symbol = (config.symbol as string) || (config.ticker as string) || 'NASDAQ:NVDA';
  const range = (config.range as string) || '1M';
  const embedUrl =
    (config.embed_url as string) ||
    `https://s.tradingview.com/widgetembed/?symbol=${encodeURIComponent(symbol)}&interval=60&range=${range}&hidesidetoolbar=1&symboledit=1&saveimage=0&toolbarbg=f1f3f6&studies=[]&hideideas=1&theme=dark`;

  return (
    <div className="rounded-xl overflow-hidden border border-gray-800">
      <iframe
        title={`TradingView ${symbol}`}
        src={embedUrl}
        style={{ width: '100%', height: 420, border: '0' }}
        loading="lazy"
        allow="fullscreen"
      />
    </div>
  );
};

/**
 * Function: NewsCard — called from MessageBubble when newsResult stream arrives.
 * Invokes: Maps articles into compact cards.
 * Purpose: Prevent undefined component crash and keep news readable during streaming.
 */
const NewsCard: React.FC<{ news: NewsResult }> = ({ news }) => {
  return (
    <div
      className="rounded-xl border p-4 space-y-3"
      style={{ backgroundColor: theme.colors.bg.elevated, borderColor: theme.colors.border.medium }}
    >
      <div className="flex items-center gap-2">
        <span style={{ color: theme.colors.accent.primary }}>News</span>
        <span className="text-xs" style={{ color: theme.colors.text.muted }}>
          {news.ticker}
        </span>
      </div>
      {news.articles.slice(0, 3).map((article, idx) => (
        <div key={idx} className="text-sm space-y-1">
          <a
            href={article.url}
            target="_blank"
            rel="noreferrer"
            className="font-semibold"
            style={{ color: theme.colors.text.primary }}
          >
            {article.title}
          </a>
          <p style={{ color: theme.colors.text.secondary }} className="text-xs leading-relaxed">
            {article.summary}
          </p>
          <div className="text-[11px]" style={{ color: theme.colors.text.muted }}>
            {article.source} • {article.published_at}
          </div>
        </div>
      ))}
    </div>
  );
};

/**
 * Function: SQLPreview — called from MessageBubble when dataResult.sql is present.
 * Invokes: Collapsible disclosure to show executed SQL.
 * Purpose: Restore missing helper so SQL streams don’t crash the UI.
 */
const SQLPreview: React.FC<{ sql: string }> = ({ sql }) => {
  const [open, setOpen] = useState(false);
  return (
    <div
      className="rounded-xl border"
      style={{ backgroundColor: theme.colors.bg.elevated, borderColor: theme.colors.border.medium }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold"
        style={{ color: theme.colors.text.primary }}
      >
        SQL Preview
        <span style={{ color: theme.colors.text.muted }}>{open ? 'Hide' : 'Show'}</span>
      </button>
      {open && (
        <pre
          className="px-4 pb-4 text-xs overflow-x-auto whitespace-pre-wrap"
          style={{ color: theme.colors.text.secondary }}
        >
          {sql}
        </pre>
      )}
    </div>
  );
};

/**
 * Function: DataPreview — called from MessageBubble when tabular data streams in.
 * Invokes: formatValueWithUnit for each cell; renders lightweight table with sticky header.
 * Purpose: Replace missing helper so dataResult rendering no longer throws during streaming.
 */
const DataPreview: React.FC<{ data: { rows: unknown[]; columns: string[] } }> = ({ data }) => {
  const columns = data.columns && data.columns.length > 0
    ? data.columns
    : Object.keys((data.rows?.[0] as Record<string, unknown>) || {});

  return (
    <div
      className="rounded-xl border overflow-auto"
      style={{ borderColor: theme.colors.border.medium }}
    >
      <table className="min-w-full text-left text-sm">
        <thead style={{ backgroundColor: theme.colors.bg.elevated }}>
          <tr>
            {columns.map((col) => (
              <th key={col} className="px-3 py-2 font-semibold" style={{ color: theme.colors.text.primary }}>
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(data.rows || []).slice(0, 20).map((row, idx) => {
            const record = row as Record<string, unknown>;
            return (
              <tr key={idx} style={{ backgroundColor: idx % 2 === 0 ? theme.colors.bg.primary : theme.colors.bg.tertiary }}>
                {columns.map((col) => (
                  <td key={col} className="px-3 py-2 text-xs" style={{ color: theme.colors.text.secondary }}>
                    {formatValueWithUnit(record[col], col)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

/**
 * Function: SkillPreview — called from MessageBubble when skillInfo is present.
 * Invokes: simple download link to the SKILL.md served by backend.
 * Purpose: Ensure skill payloads don’t crash the UI and remain discoverable inline.
 */
const SkillPreview: React.FC<{ skill: SkillInfo }> = ({ skill }) => {
  const backendUrl = configService.getBackendUrl();
  const resolvedUrl = skill.download_url?.startsWith('http')
    ? skill.download_url
    : `${backendUrl}${skill.download_url}`;

  return (
    <div
      className="rounded-xl border p-4 flex items-center justify-between"
      style={{ backgroundColor: theme.colors.bg.elevated, borderColor: theme.colors.border.medium }}
    >
      <div>
        <div className="text-sm font-semibold" style={{ color: theme.colors.text.primary }}>
          Active Skill: {skill.name}
        </div>
        <div className="text-xs" style={{ color: theme.colors.text.muted }}>
          ID: {skill.id}
        </div>
      </div>
      <a
        href={resolvedUrl}
        target="_blank"
        rel="noreferrer"
        className="text-xs font-semibold"
        style={{ color: theme.colors.accent.primary }}
      >
        View SKILL.md
      </a>
    </div>
  );
};

// Main MessageBubble component
interface MessageBubbleProps {
  role: 'user' | 'assistant';
  content: string;
  thinkingSteps?: ThinkingStep[];
  chartConfig?: Record<string, unknown> | null;
  dataResult?: { rows: unknown[]; columns: string[]; sql?: string } | null;
  newsResult?: NewsResult | null;
  isStreaming?: boolean;
  agentLabel?: string | null;
  htmlArtifact?: HtmlArtifact | null;
  skillInfo?: SkillInfo | null;

  // Agent Process Props
  processNodes?: ProcessNode[];
  processEdges?: ProcessEdge[];
  activeAgent?: AgentInfo | null;
  agentMode?: string;
  debugLogs?: DebugLog[];
  runId?: string | null;
  permissionState?: string | null;
}

/**
 * Function: MessageBubble — Called from ConversationalAnalyticsPage message history and active stream.
 * Invokes: ProcessPanel (inline mode) plus TradingViewWidget/NewsCard/SQLPreview/DataPreview/SkillPreview renderers.
 * Purpose: Render rich assistant/user bubbles without crashing when new agent payloads stream in.
 */
const MessageBubble: React.FC<MessageBubbleProps> = ({
  role,
  content,
  chartConfig,
  dataResult,
  newsResult,
  isStreaming,
  agentLabel,
  htmlArtifact,
  skillInfo,
  processNodes,
  processEdges,
  activeAgent,
  agentMode,
  debugLogs,
  runId,
  permissionState,
}) => {
  const isUser = role === 'user';
  const isTradingView = (chartConfig as any)?.widget_type === 'tradingview';

  const chartOptions = useMemo(
    () =>
      chartConfig && !isTradingView
        ? enhanceEChartsConfig(chartConfig as Record<string, unknown>)
        : chartConfig,
    [chartConfig, isTradingView],
  );

  const resolvedHtmlUrl = useMemo(() => {
    if (!htmlArtifact?.url) return null;
    const backendUrl = configService.getBackendUrl();
    return htmlArtifact.url.startsWith('http')
      ? htmlArtifact.url
      : `${backendUrl}${htmlArtifact.url}`;
  }, [htmlArtifact]);

  // Remove [SKILL: xxx] pattern from content since skill info is shown separately in SkillPreview bubble
  const cleanedContent = useMemo(() => {
    if (!content) return content;
    // Remove patterns like [SKILL: margins_vs_peers] or [SKILL: some_skill_name]
    return content.replace(/\[SKILL:\s*[\w_-]+\]\s*/gi, '').trim();
  }, [content]);

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
            {/* Agent Process Flow (Inline) */}
            {processNodes && processNodes.length > 0 && (
              <ProcessPanel
                mode="inline"
                isStreaming={!!isStreaming}
                processNodes={processNodes}
                processEdges={processEdges || []}
                activeAgent={activeAgent || null}
                agentMode={agentMode || 'single'}
                skillInfo={skillInfo}
                debugLogs={debugLogs || []}
                runId={runId}
                permissionState={permissionState}
              />
            )}

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
                  <span className="text-lg">dY"S</span>
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

            {/* Skill Preview - Collapsible widget showing detected SKILL.md */}
            {skillInfo && (
              <SkillPreview skill={skillInfo} />
            )}

            {/* SQL Preview - Collapsible widget showing executed query */}
            {dataResult && dataResult.sql && (
              <SQLPreview sql={dataResult.sql} />
            )}

            {/* Data Preview */}
            {dataResult && dataResult.rows && dataResult.rows.length > 0 && (
              <DataPreview data={dataResult} />
            )}

            {/* HTML Artifact (showcase) */}
            {htmlArtifact && resolvedHtmlUrl && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
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
                  <span className="text-lg">dY-,‹,?</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium" style={{ color: theme.colors.text.secondary }}>
                      {htmlArtifact.title || 'Showcase'}
                    </div>
                    <div className="text-xs" style={{ color: theme.colors.text.muted }}>
                      {htmlArtifact.description}
                    </div>
                  </div>
                  <a
                    href={resolvedHtmlUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-semibold"
                    style={{ color: theme.colors.accent.primary }}
                  >
                    Open ƒ+'
                  </a>
                </div>
                <div className="bg-black" style={{ aspectRatio: '16 / 10', minHeight: 260 }}>
                  <iframe
                    src={resolvedHtmlUrl}
                    title={htmlArtifact.title || 'Showcase'}
                    style={{ border: '0', width: '100%', height: '100%' }}
                    loading="lazy"
                  />
                </div>
              </motion.div>
            )}

            {/* Markdown content */}
            {cleanedContent && (
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
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{cleanedContent}</ReactMarkdown>
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
