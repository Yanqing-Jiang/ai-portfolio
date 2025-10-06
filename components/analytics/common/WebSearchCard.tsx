import React, { useEffect, useMemo, useState } from 'react';
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

  const enrichedTopics: WebSearchTopic[] = topics.length
    ? topics
    : [{
        label: searchTopic ?? 'Primary question',
        query: searchTopic ?? query ?? '',
        snippets,
        reason: undefined,
        search_id: result.searchId,
        latency_ms: latencyMs ?? null,
      }];

  const totalSnippets = useMemo(
    () => enrichedTopics.reduce((count, topic) => count + topic.snippets.length, 0),
    [enrichedTopics],
  );

  const effectiveEmptyMessage = emptyMessage
    ? emptyMessage
    : (isDisabled
      ? 'Provide a valid GOOGLE_API_KEY or GEMINI_API_KEY to re-enable live web context.'
      : 'No market research snippets available.');

  const [activeTopicIndex, setActiveTopicIndex] = useState(0);
  useEffect(() => {
    setActiveTopicIndex(0);
  }, [enrichedTopics.length, enrichedTopics[0]?.query]);

  const activeTopic = enrichedTopics[Math.min(activeTopicIndex, enrichedTopics.length - 1)];
  const totalTopics = enrichedTopics.length;
  const topicSnippets = activeTopic?.snippets ?? [];

  const handlePrev = () => setActiveTopicIndex((idx) => Math.max(0, idx - 1));
  const handleNext = () => setActiveTopicIndex((idx) => Math.min(totalTopics - 1, idx + 1));
  const snippetNumber = (index: number) => index + 1;

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
          {totalSnippets > 0 && (
            <span className="text-[11px] text-slate-200 bg-slate-800/80 border border-slate-700/70 rounded-full px-2 py-0.5">
              {totalSnippets} {totalSnippets === 1 ? 'result' : 'results'}
            </span>
          )}
          {provider && (
            <span className="text-[11px] text-emerald-300 bg-emerald-500/10 border border-emerald-500/40 rounded-full px-2 py-0.5">
              {provider}
            </span>
          )}
          {model && (
            <span className="text-[11px] text-sky-300 bg-sky-500/10 border border-sky-500/40 rounded-full px-2 py-0.5">
              {model}
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between px-4 pb-2 text-xs text-slate-400">
        <button
          type="button"
          onClick={handlePrev}
          disabled={activeTopicIndex === 0}
          className={`rounded-full border border-slate-700/70 px-2 py-1 transition ${activeTopicIndex === 0 ? 'opacity-40 cursor-not-allowed' : 'hover:border-emerald-400 hover:text-emerald-300'}`}
          aria-label="Previous topic"
        >
          < Prev
        </button>
        <span>Topic {activeTopicIndex + 1} of {totalTopics}</span>
        <button
          type="button"
          onClick={handleNext}
          disabled={activeTopicIndex >= totalTopics - 1}
          className={`rounded-full border border-slate-700/70 px-2 py-1 transition ${activeTopicIndex >= totalTopics - 1 ? 'opacity-40 cursor-not-allowed' : 'hover:border-emerald-400 hover:text-emerald-300'}`}
          aria-label="Next topic"
        >
          Next >
        </button>
      </div>

      {isDisabled || totalSnippets === 0 ? (
        <div className="px-4 py-3 text-sm text-slate-400">
          {effectiveEmptyMessage}
        </div>
      ) : (
        <div className="px-4 pb-4 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-100">{activeTopic.label || `Topic ${activeTopicIndex + 1}`}</p>
              {activeTopic.query ? (
                <p className="text-xs text-slate-400 mt-0.5">Focus: {activeTopic.query}</p>
              ) : null}
              {activeTopic.reason ? (
                <p className="text-xs text-slate-500 italic mt-0.5">Why: {activeTopic.reason}</p>
              ) : null}
            </div>
            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              {typeof activeTopic.latency_ms === 'number' ? <span>{activeTopic.latency_ms} ms</span> : null}
              {activeTopic.search_id ? <span>ID: {activeTopic.search_id}</span> : null}
            </div>
          </div>

          {topicSnippets.length > 0 ? (
            <ol className="mt-2 max-h-64 overflow-y-auto space-y-3 border-l border-slate-800/70 pl-4 pr-2">
              {topicSnippets.map((item, snippetIdx) => {
                const title = item.title || displayHost(item.url) || `Result ${snippetNumber(snippetIdx)}`;
                return (
                  <li key={item.url ?? `snippet-${activeTopicIndex}-${snippetIdx}`} className="text-sm text-slate-200">
                    <div className="flex items-start gap-2">
                      <span className="text-xs text-slate-500 font-mono mt-0.5">[{snippetNumber(snippetIdx)}]</span>
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
                              Open source >
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
      )}
    </div>
  );
};
