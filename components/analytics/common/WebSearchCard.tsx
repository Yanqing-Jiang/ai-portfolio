import React from 'react';
import { WebSearchResult, WebSearchTopic } from '../types';

interface WebSearchCardProps {
  result: WebSearchResult;
  title?: string;
  emptyMessage?: string;
}

const formatPublishedDate = (value?: string) => {
  if (!value) {
    return undefined;
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return value;
  }
  return new Date(timestamp).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
};

const displayHost = (url?: string) => {
  if (!url) {
    return undefined;
  }
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, '');
  } catch (err) {
    return url;
  }
};

export const WebSearchCard: React.FC<WebSearchCardProps> = ({
  result,
  title = 'Market Research',
  emptyMessage,
}) => {
  if (!result) {
    return null;
  }

  const {
    query,
    searchTopic,
    searchTopics,
    summary,
    snippets = [],
    fromCache,
    fetchedAt,
    latencyMs,
    ready,
    error,
    reason,
    provider,
    model,
    topics = [],
  } = result;

  const isDisabled = error === 'search_api_missing' || reason === 'search_api_missing';
  const summaryText = summary ?? (isDisabled
    ? 'Web search disabled until Gemini or Google Search API credentials are configured.'
    : undefined);
  const statusLabel = isDisabled
    ? 'Disabled'
    : fromCache
      ? 'Cached'
      : ready
        ? 'Fresh'
        : 'Pending';
  const badgeClass = isDisabled
    ? 'text-amber-300 bg-amber-500/10 border border-amber-500/40'
    : fromCache
      ? 'text-violet-200 bg-violet-500/10 border border-violet-500/40'
      : 'text-emerald-300 bg-emerald-500/10 border border-emerald-500/40';

  const enrichedTopics: WebSearchTopic[] = topics.length
    ? topics
    : [{
        label: searchTopic ?? 'Primary question',
        query: searchTopic ?? query ?? '',
        summary: summary ?? undefined,
        snippets,
        reason: undefined,
        search_id: result.searchId,
        latency_ms: latencyMs ?? null,
      }];

  let globalIndex = 1;
  const totalSnippets = enrichedTopics.reduce((count, topic) => count + topic.snippets.length, 0);
  const effectiveEmptyMessage = emptyMessage
    ? emptyMessage
    : (isDisabled
      ? 'Provide a valid GOOGLE_API_KEY or GEMINI_API_KEY to re-enable live web context.'
      : 'No market research snippets available.');

  return (
    <div className="rounded-xl border border-slate-700/70 bg-slate-900/50 overflow-hidden">
      <div className="flex items-start justify-between gap-3 px-4 py-3">
        <div>
          <h4 className="text-sm font-semibold text-slate-100">{title}</h4>
          {searchTopics && searchTopics.length ? (
            <p className="text-xs text-slate-300 mt-0.5">Topics: {searchTopics.join('; ')}</p>
          ) : null}
          {query ? (
            <p className="text-xs text-slate-500 mt-0.5">Question: {query}</p>
          ) : null}
          {fetchedAt ? (
            <p className="text-xs text-slate-500 mt-0.5">
              Retrieved: {formatPublishedDate(fetchedAt) ?? fetchedAt}
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {totalSnippets > 0 ? (
            <span className="text-[11px] text-slate-200 bg-slate-800/80 border border-slate-700/70 rounded-full px-2 py-0.5">
              {totalSnippets} {totalSnippets === 1 ? 'result' : 'results'}
            </span>
          ) : null}
          {provider ? (
            <span className="text-[11px] text-emerald-300 bg-emerald-500/10 border border-emerald-500/40 rounded-full px-2 py-0.5">
              {provider}
            </span>
          ) : null}
          {model ? (
            <span className="text-[11px] text-sky-300 bg-sky-500/10 border border-sky-500/40 rounded-full px-2 py-0.5">
              {model}
            </span>
          ) : null}
          {typeof latencyMs === 'number' && latencyMs >= 0 ? (
            <span className="text-[11px] text-slate-400 bg-slate-800/80 border border-slate-700/70 rounded-full px-2 py-0.5">
              {latencyMs} ms (aggregate)
            </span>
          ) : null}
          <span className={`text-[11px] rounded-full px-2 py-0.5 ${badgeClass}`}>
            {statusLabel}
          </span>
        </div>
      </div>

      {summaryText ? (
        <p className="px-4 pb-3 text-sm text-slate-200 leading-relaxed border-b border-slate-800/70">
          {summaryText}
        </p>
      ) : null}

      {isDisabled || totalSnippets === 0 ? (
        <div className="px-4 py-3 text-sm text-slate-400">
          {effectiveEmptyMessage}
        </div>
      ) : (
        <div className="space-y-4 py-3">
          {enrichedTopics.map((topic, idx) => {
            const topicSnippets = topic.snippets ?? [];
            const topicLatency = topic.latency_ms ?? null;
            return (
              <div key={`${topic.query}-${idx}`} className="px-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-100">{topic.label || `Topic ${idx + 1}`}</p>
                    {topic.query ? (
                      <p className="text-xs text-slate-400 mt-0.5">Focus: {topic.query}</p>
                    ) : null}
                    {topic.reason ? (
                      <p className="text-xs text-slate-500 italic mt-0.5">Why: {topic.reason}</p>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-slate-500">
                    {typeof topicLatency === 'number' ? <span>{topicLatency} ms</span> : null}
                    {topic.search_id ? <span>ID: {topic.search_id}</span> : null}
                  </div>
                </div>
                {topic.summary ? (
                  <p className="mt-2 text-sm text-slate-200 leading-relaxed">{topic.summary}</p>
                ) : null}
                {topicSnippets.length > 0 ? (
                  <ol className="mt-3 space-y-3 border-l border-slate-800/70 pl-4">
                    {topicSnippets.map((item, snippetIdx) => {
                      const currentIndex = globalIndex++;
                      const title = item.title || displayHost(item.url) || `Result ${currentIndex}`;
                      return (
                        <li key={item.url ?? `snippet-${idx}-${snippetIdx}`} className="text-sm text-slate-200">
                          <div className="flex items-start gap-2">
                            <span className="text-xs text-slate-500 font-mono mt-0.5">[{currentIndex}]</span>
                            <div>
                              {item.url ? (
                                <a
                                  href={item.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="font-medium text-slate-100 hover:text-emerald-300 transition"
                                >
                                  {title}
                                </a>
                              ) : (
                                <span className="font-medium text-slate-100">{title}</span>
                              )}
                              {item.snippet ? (
                                <p className="mt-1 text-xs text-slate-300 leading-relaxed">{item.snippet}</p>
                              ) : null}
                              <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                                {displayHost(item.url) ? <span>{displayHost(item.url)}</span> : null}
                                {item.published_at ? (
                                  <span>{formatPublishedDate(item.published_at) ?? item.published_at}</span>
                                ) : null}
                                {item.url ? (
                                  <a
                                    href={item.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-emerald-300 hover:text-emerald-200"
                                  >
                                    Open source →
                                  </a>
                                ) : null}
                              </div>
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                ) : (
                  <p className="mt-3 text-xs text-slate-400">No citations captured for this topic.</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
