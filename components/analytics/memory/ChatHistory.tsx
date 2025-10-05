import React, { Suspense } from 'react';
import { ChatHistoryProps } from '../types';
import { ClarificationOptions } from './ClarificationOptions';
import { AnalysisCard, SqlCard, CollapsibleSection, TradingViewSymbolOverview, WebSearchCard } from '../common';
import { isValidChartSpec } from '../utils';

const ChartCard = React.lazy(() => import('../common/ChartCard').then((m) => ({ default: m.ChartCard })));
const MAX_WEB_SNIPPETS = 3;

const buildWebInsightsSection = (webSearch: ChatHistoryProps['messages'][number]['webSearch']) => {
  if (!webSearch || !webSearch.snippets?.length) return null;
  const lines: string[] = [];
  const summary = webSearch.summary?.trim();
  if (summary) {
    lines.push(`- ${summary}`);
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
  const stockResult = results.find((entry) => entry?.tool === 'stock_tracker' && entry.payload && (entry.payload as any).ready);
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

const buildCombinedAnalysis = (message: ChatHistoryProps['messages'][number]) => {
  const sections: string[] = [];
  const base = message.analysis?.trim();
  if (base) {
    sections.push('**SQL-Derived Highlights**\n' + base);
  }
  const stockSection = buildStockInsightsSection(message.toolFanoutResults);
  if (stockSection) sections.push(stockSection);
  const webSection = buildWebInsightsSection(message.webSearch);
  if (webSection) sections.push(webSection);
  return sections.join('\n\n');
};

export const ChatHistory: React.FC<ChatHistoryProps> = ({
  messages,
  isLoading,
  onSubmitClarification,
  processSteps = [],
}) => {
  if (messages.length === 0) return null;

  return (
    <div className="bg-gray-900 py-4 mb-6">
      <div className="space-y-4">
        {messages.map((message) => {
          const combinedAnalysis = buildCombinedAnalysis(message);
          const showTradingView = Array.isArray(message.stockWidgetConfig?.symbols) && message.stockWidgetConfig?.symbols?.length;
          const firstSymbol = showTradingView ? message.stockWidgetConfig?.symbols?.[0] : null;
          const primaryTicker = showTradingView
            ? Array.isArray(firstSymbol)
              ? (firstSymbol[1] ?? firstSymbol[0] ?? '').toUpperCase()
              : String(firstSymbol ?? '').toUpperCase()
            : null;
          const bubbleClass = message.type === 'user'
            ? 'bg-gray-800 text-gray-100 rounded-2xl rounded-br-md px-4 py-3'
            : message.type === 'result'
              ? 'bg-gray-800/30 text-gray-100 rounded-2xl rounded-bl-md p-2'
              : 'bg-gray-800/50 text-gray-100 rounded-2xl rounded-bl-md px-4 py-3';

          return (
            <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] ${message.type === 'user' ? 'order-2' : 'order-1'}`}>
                <div className={`transition-all hover:shadow-sm ${bubbleClass}`}>
                  <div className={message.type === 'result' ? 'px-2 py-1' : ''}>
                    <div className="text-sm leading-relaxed">{message.content}</div>

                    {message.answers && Object.keys(message.answers).length > 0 && (
                      <div className="mt-2 space-y-1 text-xs text-gray-400">
                        {Object.entries(message.answers).map(([key, value]) => (
                          <div key={key}>
                            <span className="font-semibold text-gray-300">{key}: </span>
                            <span>{typeof value === 'string' ? value : JSON.stringify(value)}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {message.clarifications && message.clarifications.length > 0 && onSubmitClarification && (
                      <div className="mt-3">
                        <ClarificationOptions
                          clarification={message.clarifications[0]}
                          onSubmit={async (response) => onSubmitClarification(response, message.clarifications![0])}
                        />
                      </div>
                    )}
                  </div>

                  {message.type === 'result' && (
                    <div className="mt-3 space-y-4">
                      {message.chartSpec && isValidChartSpec(message.chartSpec) && (
                        <Suspense fallback={<div className="rounded-xl border border-gray-700 bg-gray-800/40 p-6 text-sm text-gray-300">Loading chart...</div>}>
                          <div className="rounded-xl overflow-hidden border border-gray-700">
                            <ChartCard
                              chartSpec={message.chartSpec}
                              dataSample={message.dataSample}
                              enableDropdown
                              enableCsvDownload
                            />
                          </div>
                        </Suspense>
                      )}

                      {showTradingView && message.stockWidgetConfig && (
                        <CollapsibleSection
                          title="Market Snapshot"
                          defaultOpen={false}
                          className="bg-gray-800/50"
                        >
                          <div className="border border-gray-700 rounded-lg overflow-hidden">
                            <div className="px-4 py-3 border-b border-gray-700/60">
                              <h3 className="text-base sm:text-lg font-semibold text-white">Market Snapshot</h3>
                              <p className="text-xs sm:text-sm text-gray-400">
                                Live TradingView overview for {primaryTicker ?? 'selected ticker'}
                              </p>
                            </div>
                            <TradingViewSymbolOverview config={message.stockWidgetConfig} />
                          </div>
                        </CollapsibleSection>
                      )}

                      {combinedAnalysis && (
                        <div className="rounded-xl overflow-hidden">
                          <AnalysisCard analysis={combinedAnalysis} />
                        </div>
                      )}

                      {message.webSearch && message.webSearch.snippets?.length ? (
                        <CollapsibleSection
                          title="Search Highlights"
                          defaultOpen={false}
                          className="bg-gray-800/50"
                        >
                          <WebSearchCard result={message.webSearch} />
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
                    </div>
                  )}
                </div>

                <div className={`flex items-center gap-2 mt-1 px-1 ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <span className="text-xs text-gray-500">
                    {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>

              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${message.type === 'user' ? 'bg-gray-700 text-gray-300 order-3 ml-2' : 'bg-gray-700/50 text-gray-400 order-0 mr-2'}`}>
                {message.type === 'user' ? 'ðŸ‘¤' : 'ðŸ¤–'}
              </div>
            </div>
          );
        })}

        {isLoading && (
          <div className="flex justify-start">
            <div className="max-w-[80%] order-1">
              <div className="bg-gray-800/50 text-gray-100 rounded-2xl rounded-bl-md px-4 py-3 transition-all">
                <div className="flex items-center gap-2">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                  <span className="text-sm text-gray-300">Analyzing...</span>
                </div>
              </div>
              <div className="flex items-center gap-2 mt-1 px-1 justify-start">
                <span className="text-xs text-gray-500">
                  {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
            <div className="w-8 h-8 rounded-full bg-gray-600 text-gray-300 flex items-center justify-center flex-shrink-0 order-0 mr-2">
              ðŸ¤–
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
