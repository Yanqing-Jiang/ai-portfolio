import React, { Suspense } from 'react';
import { ChatHistoryProps } from '../types';
import { ClarificationOptions } from './ClarificationOptions';
import {
  AnalysisCard,
  SqlCard,
  CollapsibleSection,
  TradingViewSymbolOverview,
  WebSearchCard,
} from '../common';
import { isValidChartSpec } from '../utils';
import { RobotIcon } from '../../icons/RobotIcon';
import { UserIcon } from '../../icons/UserIcon';

const ChartCard = React.lazy(() => import('../common/ChartCard').then((m) => ({ default: m.ChartCard })));
const MAX_WEB_SNIPPETS = 3;

const buildWebInsightsSection = (webSearch: ChatHistoryProps['messages'][number]['webSearch']) => {
  if (!webSearch || !webSearch.snippets?.length) return null;
  const lines: string[] = [];
  const summary = webSearch.summary?.trim();
  if (summary) {
    const sanitized = summary
      .split(/\n+/)
      .map((line) => line.trim())
      .filter((line) => line && !/^primary (question|topic)/i.test(line))
      .join(' ');
    if (sanitized) {
      lines.push(`- ${sanitized}`);
    }
  }
  webSearch.snippets.slice(0, MAX_WEB_SNIPPETS).forEach((snippet) => {
    const raw = (snippet.snippet ?? '').trim();
    if (!raw) return;
    const sanitized = raw.replace(/\s+/g, ' ').trim();
    const excerpt = sanitized.length > 220 ? `${sanitized.slice(0, 217).trimEnd()}...` : sanitized;
    const safeExcerpt = excerpt.replace(/"/g, "'");
    const title = (snippet.title || snippet.display_url || snippet.url || 'Source').toString().trim();
    const sourceUrl = (snippet.url || snippet.display_url || '').toString().trim();
    const citation = sourceUrl ? `[${title}](${sourceUrl})` : title;
    lines.push(`- "${safeExcerpt}" - ${citation}`);
  });
  if (!lines.length) return null;
  return ['**Online Sources**', ...lines].join('\n');
};

const buildStockInsightsSection = (results: ChatHistoryProps['messages'][number]['toolFanoutResults']) => {
  if (!results?.length) return null;
  const stockResult = results.find(
    (entry) => entry?.tool === 'stock_tracker' && entry.payload && (entry.payload as any).ready,
  );
  if (!stockResult?.payload) return null;
  const payload = stockResult.payload as Record<string, any>;
  const symbol = (payload.symbol || payload.tickers?.[0] || '').toString().toUpperCase();
  const latest = typeof payload.latest_close === 'number' ? payload.latest_close : undefined;
  const previous = typeof payload.previous_close === 'number' ? payload.previous_close : undefined;
  const change = typeof payload.change_percent === 'number' ? payload.change_percent : undefined;
  const fetchedAt = typeof payload.fetched_at === 'string' ? payload.fetched_at : null;
  const lines: string[] = [];
  if (symbol && latest !== undefined) {
    lines.push(`- **${symbol}** close: $${latest.toFixed(2)}`);
  } else if (symbol) {
    lines.push(`- **${symbol}** snapshot available`);
  }
  if (change !== undefined) {
    const formatted = change >= 0 ? `+${change.toFixed(2)}%` : `${change.toFixed(2)}%`;
    lines.push(`- Session move vs prior close: ${formatted}`);
  }
  if (previous !== undefined && latest !== undefined) {
    const delta = latest - previous;
    const formatted = delta >= 0 ? `+${delta.toFixed(2)}` : delta.toFixed(2);
    lines.push(`- Prior close: $${previous.toFixed(2)} (Delta ${formatted})`);
  }
  if (fetchedAt) {
    lines.push(`- Snapshot captured ${fetchedAt}`);
  }
  const bars = Array.isArray(payload.bars) ? payload.bars : [];
  if (bars.length) {
    const ts = bars[bars.length - 1]?.time;
    if (typeof ts === 'number') {
      const date = new Date(ts * 1000);
      if (!Number.isNaN(date.getTime())) {
        lines.push(`- Latest bar date: ${date.toISOString().slice(0, 10)}`);
      }
    }
  }
  if (!lines.length) return null;
  return ['**Market Snapshot Highlights**', ...lines].join('\n');
};

const stripLeadMarkdownHeading = (text: string, patterns: RegExp[]) => {
  if (!text?.trim()) {
    return text;
  }
  const lines = text.split('\n');
  for (let idx = 0; idx < lines.length; idx += 1) {
    const original = lines[idx];
    const trimmed = original.trim();
    if (!trimmed) {
      continue;
    }
    const match = patterns.find((regex) => regex.test(trimmed));
    if (!match) {
      break;
    }
    const headingMatch = trimmed.match(match);
    if (!headingMatch) {
      break;
    }
    const headingLength = headingMatch[0].length;
    const prefixLength = original.length - trimmed.length;
    const remainder = original.slice(prefixLength + headingLength).trimStart();
    if (remainder.length) {
      lines[idx] = remainder;
    } else {
      lines.splice(idx, 1);
    }
    break;
  }
  return lines.join('\n').replace(/^\s+/, '').trim();
};

const cleanTldrCopy = (value?: string | null) => {
  if (!value) return '';
  const stripped = value.replace(/^\s*(?:[#>*-]\s*)*(?:\*\*|__)?\s*TL;?\s*DR\b[:\-\s]*/i, '').trim();
  return stripped.length ? stripped : value.trim();
};

const buildCombinedAnalysis = (message: ChatHistoryProps['messages'][number]) => {
  const sections: string[] = [];
  const tldr = cleanTldrCopy(message.analysisOverview?.tldr);
  const primaryAnalysis =
    message.analysis?.trim() ??
    message.progressiveAnalysis?.trim() ??
    message.progressiveText?.trim() ??
    '';
  const hasFinalAnalysis = Boolean(message.analysis?.trim());

  let base = primaryAnalysis;

  if (base && tldr) {
    const isTldrLine = (line: string) => {
      const trimmed = line.trim();
      if (!trimmed) return false;
      const withoutLeadingMarkdown = trimmed.replace(/^[^a-zA-Z0-9]+/, '').trim();
      const normalized = withoutLeadingMarkdown.toLowerCase();
      return normalized.startsWith('tl;dr');
    };
    const filtered = base
      .split('\n')
      .filter((line) => !isTldrLine(line));
    const cleaned = filtered.join('\n').trim();
    base = cleaned.length ? cleaned : undefined;
  }

  if (tldr) {
    sections.push(`**Quick Take**\n${tldr}`);
  }

  if (base) {
    const headingLabel = hasFinalAnalysis ? 'SQL-Derived Highlights' : 'Analysis Draft (Streaming)';
    const cleanedBase = stripLeadMarkdownHeading(base, [
      /^(\*\*|__)?\s*sql[-\s]*derived highlights?\b[:\-\s]*/i,
      /^(\*\*|__)?\s*analysis draft(?:\s*\(streaming\))?\b[:\-\s]*/i,
    ]);
    if (cleanedBase) {
      sections.push(`**${headingLabel}**\n${cleanedBase}`);
    }
  }
  const stockSection = buildStockInsightsSection(message.toolFanoutResults);
  if (stockSection) sections.push(stockSection);
  const webSection = buildWebInsightsSection(message.webSearch);
  if (webSection) sections.push(webSection);
  return sections.join('\n\n');
};

const formatStatusTimestamp = (value?: string | null) => {
  const source = value ? new Date(value) : new Date();
  if (Number.isNaN(source.getTime())) {
    return undefined;
  }
  return source.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

export const ChatHistory: React.FC<ChatHistoryProps> = ({
  messages,
  status,
  isLoading,
  onSubmitClarification,
  processSteps: _processSteps = [],
}) => {
  const rawStatusText = status?.text ?? '';
  const normalizedStatusText = React.useMemo(() => {
    if (!rawStatusText) {
      return '';
    }
    const trimmed = rawStatusText.trim().replace(/\u2026/g, '');
    const withoutTrailingDots = trimmed.replace(/\s*\.\.\.$/, '').replace(/\s*…$/, '');
    return withoutTrailingDots.trim();
  }, [rawStatusText]);
  const statusTimestamp = formatStatusTimestamp(status?.timestamp);
  const showStatusBubble = Boolean(normalizedStatusText);
  const renderStatusBubble = React.useCallback(
    (compact?: boolean) => {
      if (!showStatusBubble || !normalizedStatusText) {
        return null;
      }
      const spacingClass = compact ? '' : 'mb-3 ';
      return (
        <div
          className={`${spacingClass}flex flex-wrap items-center gap-3 rounded-xl border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs text-blue-100/80`}
        >
          <span className="text-sm text-blue-100">{normalizedStatusText}</span>
          {isLoading && (
            <div className="flex space-x-1" aria-hidden="true">
              <div className="w-2 h-2 bg-blue-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
              <div className="w-2 h-2 bg-blue-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
              <div className="w-2 h-2 bg-blue-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            </div>
          )}
          {statusTimestamp ? (
            <span className="ml-auto text-[11px] uppercase tracking-wide text-blue-200/70">
              {statusTimestamp}
            </span>
          ) : null}
        </div>
      );
    },
    [isLoading, normalizedStatusText, showStatusBubble, statusTimestamp],
  );

  const statusInlineBubble = React.useMemo(() => renderStatusBubble(true), [renderStatusBubble]);
  const statusStandaloneRow = React.useMemo(() => {
    if (!showStatusBubble || !statusInlineBubble) {
      return null;
    }
    const lastMessage = messages.length ? messages[messages.length - 1] : null;
    const awaitingAssistantReply = !lastMessage || lastMessage.type === 'user';
    if (!awaitingAssistantReply) {
      return null;
    }
    return (
      <div className="flex gap-3">
        <div className="w-9 h-9 flex-shrink-0" aria-hidden="true" />
        <div className="max-w-[960px] flex flex-col items-start">
          <div className="transition-all hover:shadow-sm bg-gray-800/60 text-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
            {statusInlineBubble}
          </div>
        </div>
      </div>
    );
  }, [messages, showStatusBubble, statusInlineBubble]);

  return (
    <div className="bg-gray-900 py-4 mb-6 relative">
      <div className="space-y-4">
        {messages.map((message, idx) => {
          const isUser = message.type === 'user';
          const isResult = message.type === 'result';
          const combinedAnalysis = isResult ? buildCombinedAnalysis(message) : undefined;
          const isAnalysisRevisionResult =
            isResult && message.banner?.route === 'analysis_only';
          const revisionFocus =
            typeof message.revisionFocus === 'string' && message.revisionFocus.trim().length
              ? message.revisionFocus.trim()
              : undefined;
          const primaryAnalysisContent =
            (combinedAnalysis && combinedAnalysis.trim().length ? combinedAnalysis : undefined) ??
            (typeof message.analysis === 'string' && message.analysis.trim().length
              ? message.analysis
              : undefined) ??
            (typeof message.progressiveAnalysis === 'string' && message.progressiveAnalysis.trim().length
              ? message.progressiveAnalysis
              : undefined) ??
            (typeof message.progressiveText === 'string' && message.progressiveText.trim().length
              ? message.progressiveText
              : undefined);
          const baseWebSearch = message.webSearch;
          const resolvedWebSearch = isAnalysisRevisionResult
            ? (() => {
                if (baseWebSearch) {
                  return {
                    ...baseWebSearch,
                    snippets: Array.isArray(baseWebSearch.snippets) ? baseWebSearch.snippets : [],
                  };
                }
                return {
                  query: revisionFocus ?? '',
                  summary: '',
                  snippets: [],
                  ready: false,
                  reason: 'no_web_research',
                };
              })()
            : baseWebSearch
            ? {
                ...baseWebSearch,
                snippets: Array.isArray(baseWebSearch.snippets) ? baseWebSearch.snippets : [],
              }
            : null;
          const showTradingView =
            !isAnalysisRevisionResult &&
            Array.isArray(message.stockWidgetConfig?.symbols) &&
            message.stockWidgetConfig?.symbols?.length;
          const attachmentsAvailable = isAnalysisRevisionResult
            ? Boolean(primaryAnalysisContent) || Boolean(resolvedWebSearch)
            : Boolean(
                (message.chartSpec && isValidChartSpec(message.chartSpec)) ||
                  (showTradingView && message.stockWidgetConfig) ||
                  primaryAnalysisContent ||
                  resolvedWebSearch ||
                  message.sqlQuery,
              );
          const contentText =
            typeof message.content === 'string' && message.content.trim().length > 0 ? message.content : '';

          const bubbleClass = isUser
            ? 'bg-blue-600/20 border border-blue-500/40 text-blue-50 rounded-2xl rounded-br-md px-4 py-3'
            : isResult
              ? 'bg-gray-800/30 text-gray-100 rounded-2xl rounded-bl-md p-3 w-full'
              : 'bg-gray-800/60 text-gray-100 rounded-2xl rounded-bl-md px-4 py-3';

          return (
            <div
              key={message.id}
              className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              {!isUser ? (
                <div className="w-9 h-9 rounded-full bg-gray-700/70 flex items-center justify-center flex-shrink-0 overflow-hidden">
                  <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
                    <RobotIcon />
                  </div>
                </div>
              ) : null}

              <div className={`max-w-[960px] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
                {!isUser && idx === messages.length - 1 && statusInlineBubble ? (
                  <div className="transition-all hover:shadow-sm bg-gray-800/60 text-gray-100 rounded-2xl rounded-bl-md px-4 py-3 mb-3">
                    {statusInlineBubble}
                  </div>
                ) : null}
                <div className={`transition-all hover:shadow-sm ${bubbleClass}`}>
                  <div className={isResult ? 'space-y-3' : 'space-y-2'}>
                    {contentText ? (
                      <div className="text-sm leading-relaxed whitespace-pre-line">{message.content}</div>
                    ) : null}

                    {message.answers && Object.keys(message.answers).length > 0 && (
                      <div className="space-y-1 text-xs text-gray-400">
                        {Object.entries(message.answers).map(([key, value]) => (
                          <div key={key}>
                            <span className="font-semibold text-gray-300">{key}: </span>
                            <span>{typeof value === 'string' ? value : JSON.stringify(value)}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {message.clarifications && message.clarifications.length > 0 && onSubmitClarification && (
                      <div>
                        <ClarificationOptions
                          clarification={message.clarifications[0]}
                          onSubmit={async (response) =>
                            onSubmitClarification(response, message.clarifications![0])
                          }
                        />
                      </div>
                    )}

                    {attachmentsAvailable && message.type === 'result' && (
                      isAnalysisRevisionResult ? (
                        <div className="space-y-4">
                          {revisionFocus ? (
                            <div className="text-[11px] uppercase tracking-wide text-emerald-300">
                              Focus: {revisionFocus}
                            </div>
                          ) : null}
                          {primaryAnalysisContent ? (
                            <div className="rounded-xl overflow-hidden border border-blue-500/30 bg-blue-500/10">
                              <AnalysisCard
                                analysis={primaryAnalysisContent}
                                analysisSources={message.analysisSources}
                                evidenceLinks={message.analysisOverview?.evidence}
                              />
                            </div>
                          ) : null}
                          <CollapsibleSection title="Market Research" defaultOpen={false} className="bg-gray-800/50">
                            <WebSearchCard
                              result={
                                resolvedWebSearch ?? {
                                  query: revisionFocus ?? '',
                                  summary: '',
                                  snippets: [],
                                  ready: false,
                                  reason: 'no_web_research',
                                }
                              }
                              title="Market Research"
                              emptyMessage="No web research snippets available."
                            />
                          </CollapsibleSection>
                          <div className="pt-3 border-t border-dashed border-gray-700 text-xs text-gray-400">
                            Need another update? Ask to continue generating results or request the latest status.
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {message.chartSpec && isValidChartSpec(message.chartSpec) && (
                            <Suspense
                              fallback={
                                <div className="rounded-xl border border-gray-700 bg-gray-800/40 p-6 text-sm text-gray-300">
                                  Loading chart...
                                </div>
                              }
                            >
                              <div className="rounded-xl overflow-hidden border border-gray-700 bg-gray-900/40">
                                <ChartCard
                                  chartSpec={message.chartSpec}
                                  dataSample={message.dataSample}
                                  enableDropdown
                                  enableCsvDownload
                                />
                              </div>
                            </Suspense>
                          )}

                          {primaryAnalysisContent ? (
                            <div className="rounded-xl overflow-hidden border border-blue-500/30 bg-blue-500/10">
                              <AnalysisCard
                                analysis={primaryAnalysisContent}
                                analysisSources={message.analysisSources}
                                evidenceLinks={message.analysisOverview?.evidence}
                              />
                            </div>
                          ) : null}

                          {showTradingView && message.stockWidgetConfig && (
                            <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-3 sm:p-4 overflow-hidden">
                              <TradingViewSymbolOverview config={message.stockWidgetConfig} height={480} />
                            </div>
                          )}

                          {resolvedWebSearch ? (
                            <CollapsibleSection title="Market Research" defaultOpen={false} className="bg-gray-800/50">
                              <WebSearchCard
                                result={resolvedWebSearch}
                                title="Market Research"
                                emptyMessage="No market research snippets available."
                              />
                            </CollapsibleSection>
                          ) : null}

                          {message.sqlQuery && (
                            <CollapsibleSection
                              title="Generated SQL Query"
                              defaultOpen={false}
                              className="bg-gray-800/50"
                            >
                              <SqlCard sqlQuery={message.sqlQuery} compact={true} />
                            </CollapsibleSection>
                          )}

                          <div className="pt-3 border-t border-dashed border-gray-700 text-xs text-gray-400">
                            Need another update? Ask to continue generating results or request the latest status.
                          </div>
                        </div>
                      )
                    )}
                  </div>
                </div>

                <div className={`mt-1 text-xs text-gray-500 ${isUser ? 'text-right' : 'text-left'}`}>
                  {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>

              {isUser ? (
                <div className="w-9 h-9 rounded-full bg-blue-600/70 text-white flex items-center justify-center flex-shrink-0">
                  <UserIcon />
                </div>
              ) : null}
            </div>
          );
        })}

        {statusStandaloneRow}

      </div>
    </div>
  );
};

