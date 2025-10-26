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
    topicTotal,
  } = result;

  const isDisabled = error === 'search_api_missing' || reason === 'search_api_missing';
  const FALLBACK_SNIPPETS_PER_TOPIC = 2;

  const normalizedTopics = useMemo(() => {
    if (!Array.isArray(topics) || !topics.length) {
      return [] as WebSearchTopic[];
    }
    const toNumber = (value: unknown): number | undefined => {
      if (typeof value === 'number' && Number.isFinite(value)) {
        return value;
      }
      if (typeof value === 'string') {
        const parsed = Number(value);
        if (Number.isFinite(parsed)) {
          return parsed;
        }
      }
      return undefined;
    };
    const seen = new Map<string, WebSearchTopic>();
    const normalize = (value: unknown) =>
      typeof value === 'string' ? value.trim().toLowerCase() : undefined;
    topics.forEach((entry, index) => {
      if (!entry) {
        return;
      }
      const topicIndex = toNumber((entry as any).topic_index ?? (entry as any).topicIndex);
      const topicPosition = toNumber((entry as any).topic_position ?? (entry as any).topicPosition);
      const rawTopicLabel = (entry as any).topic_label ?? (entry as any).topicLabel;
      const label = entry.label ?? rawTopicLabel ?? entry.query ?? query ?? '';
      const baseQuery = entry.query || query || '';
      const normalizedTopicLabel = normalize(rawTopicLabel);
      const normalizedLabel = normalize(label);
      const normalizedQuery = normalize(baseQuery);
      const keyParts: string[] = [];
      if (topicIndex !== undefined) {
        keyParts.push(`idx-${topicIndex}`);
      }
      if (topicPosition !== undefined) {
        keyParts.push(`pos-${topicPosition}`);
      }
      if (normalizedTopicLabel) {
        keyParts.push(`topic-${normalizedTopicLabel}`);
      }
      if (normalizedLabel && normalizedLabel !== normalizedTopicLabel) {
        keyParts.push(`label-${normalizedLabel}`);
      }
      if (normalizedQuery) {
        keyParts.push(`query-${normalizedQuery}`);
      }
      if (!keyParts.length) {
        keyParts.push(`ord-${index}`);
      }
      const key = keyParts.join('|');
      const clonedSnippets = Array.isArray(entry.snippets)
        ? entry.snippets.map((item) => ({ ...item }))
        : [];
      const payload: WebSearchTopic = {
        ...entry,
        label: typeof label === 'string' ? label : entry.label,
        topic_label:
          typeof rawTopicLabel === 'string' ? rawTopicLabel : (entry as any).topic_label ?? undefined,
        topicLabel:
          typeof rawTopicLabel === 'string' ? rawTopicLabel : (entry as any).topicLabel ?? undefined,
        query: baseQuery,
        snippets: clonedSnippets,
        topic_index: topicIndex ?? null,
        topicIndex: topicIndex ?? null,
        topic_position: topicPosition ?? null,
        topicPosition: topicPosition ?? null,
      };
      const existing = seen.get(key);
      if (!existing) {
        seen.set(key, payload);
        return;
      }
      existing.snippets = existing.snippets.concat(
        clonedSnippets.filter(
          (item) =>
            !existing.snippets.some(
              (prev) => prev.url === item.url && prev.snippet === item.snippet,
            ),
        ),
      );
      existing.summary = existing.summary ?? payload.summary;
      existing.reason = existing.reason ?? payload.reason;
      const existingLabelTrimmed = existing.label?.trim() ?? '';
      if (!existingLabelTrimmed) {
        existing.label = payload.label;
      } else if (
        payload.label &&
        /^primary (question|topic)$/i.test(existingLabelTrimmed) &&
        !/^primary (question|topic)$/i.test(payload.label.trim())
      ) {
        existing.label = payload.label;
      }
      if (!existing.topic_label && payload.topic_label) {
        existing.topic_label = payload.topic_label;
      }
      if (!existing.topicLabel && payload.topicLabel) {
        existing.topicLabel = payload.topicLabel;
      }
      existing.query = existing.query || payload.query;
      if (existing.topic_index == null && payload.topic_index != null) {
        existing.topic_index = payload.topic_index;
        existing.topicIndex = payload.topic_index;
      }
      if (existing.topic_position == null && payload.topic_position != null) {
        existing.topic_position = payload.topic_position;
        existing.topicPosition = payload.topic_position;
      }
      existing.latency_ms = existing.latency_ms ?? payload.latency_ms;
      existing.search_id = existing.search_id ?? payload.search_id;
    });
    const ordered = Array.from(seen.values());
    ordered.sort((a, b) => {
      const idxA = toNumber(a.topic_index ?? (a as any).topicIndex) ?? Number.MAX_SAFE_INTEGER;
      const idxB = toNumber(b.topic_index ?? (b as any).topicIndex) ?? Number.MAX_SAFE_INTEGER;
      if (idxA !== idxB) {
        return idxA - idxB;
      }
      const posA = toNumber(a.topic_position ?? (a as any).topicPosition) ?? Number.MAX_SAFE_INTEGER;
      const posB = toNumber(b.topic_position ?? (b as any).topicPosition) ?? Number.MAX_SAFE_INTEGER;
      if (posA !== posB) {
        return posA - posB;
      }
      const labelA = ((a.label ?? (a as any).topicLabel ?? a.query) || '').toLowerCase();
      const labelB = ((b.label ?? (b as any).topicLabel ?? b.query) || '').toLowerCase();
      return labelA.localeCompare(labelB);
    });
    return ordered;
  }, [topics, query]);

  const enrichedTopics: WebSearchTopic[] = useMemo(() => {
    if (normalizedTopics.length) {
      return normalizedTopics;
    }
    const baseLabel = searchTopic ?? 'Research topic';
    const baseQuery = searchTopic ?? query ?? '';
    if (!snippets.length) {
      return [
        {
          label: baseLabel,
          query: baseQuery,
          snippets,
          reason: undefined,
          search_id: result.searchId,
          latency_ms: latencyMs ?? null,
        },
      ];
    }
    const grouped: WebSearchTopic[] = [];
    for (let index = 0; index < snippets.length; index += FALLBACK_SNIPPETS_PER_TOPIC) {
      const chunk = snippets.slice(index, index + FALLBACK_SNIPPETS_PER_TOPIC);
      const suffix = grouped.length ? ` (${grouped.length + 1})` : '';
      grouped.push({
        label: `${baseLabel}${suffix}`.trim(),
        query: baseQuery,
        reason: undefined,
        summary: undefined,
        search_id: result.searchId,
        latency_ms: latencyMs ?? null,
        snippets: chunk,
      });
    }
    return grouped;
  }, [normalizedTopics, snippets, searchTopic, query, result.searchId, latencyMs]);

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
    setActiveTopicIndex((prev) => {
      if (!enrichedTopics.length) {
        return 0;
      }
      if (prev >= enrichedTopics.length) {
        return enrichedTopics.length - 1;
      }
      if (prev < 0) {
        return 0;
      }
      return prev;
    });
  }, [enrichedTopics.length, enrichedTopics[0]?.query]);

  const activeTopic = enrichedTopics[Math.min(activeTopicIndex, enrichedTopics.length - 1)];
  const inferredTotal = typeof topicTotal === 'number' && topicTotal > 0 ? topicTotal : undefined;
  const actualTopicCount = enrichedTopics.length;
  const totalTopics = actualTopicCount;
  const announcedTopicTotal =
    inferredTotal !== undefined ? Math.max(inferredTotal, actualTopicCount) : actualTopicCount;
  const topicSnippets = activeTopic?.snippets ?? [];
  const topicBadgeRaw =
    typeof activeTopic?.topic_label === 'string'
      ? activeTopic.topic_label
      : typeof activeTopic?.topicLabel === 'string'
        ? activeTopic.topicLabel
        : undefined;
  const topicBadge = topicBadgeRaw?.trim() || undefined;
  const topicHeading = (() => {
    if (!activeTopic) {
      return `Topic ${activeTopicIndex + 1}`;
    }
    const candidateLabel = typeof activeTopic.label === 'string' ? activeTopic.label.trim() : '';
    const candidateQuery = typeof activeTopic.query === 'string' ? activeTopic.query.trim() : '';
    const labelIsGeneric =
      !candidateLabel ||
      /^primary (question|topic)/i.test(candidateLabel) ||
      /^secondary (question|topic)/i.test(candidateLabel);
    if (!labelIsGeneric && candidateLabel) {
      return candidateLabel.replace(/^Primary (question|topic):\s*/i, '').trim() || candidateLabel;
    }
    if (candidateQuery) {
      return candidateQuery;
    }
    if (candidateLabel) {
      return candidateLabel;
    }
    return `Topic ${activeTopicIndex + 1}`;
  })();

  const handlePrev = () => setActiveTopicIndex((idx) => Math.max(0, idx - 1));
  const handleNext = () =>
    setActiveTopicIndex((idx) => {
      if (totalTopics <= 0) {
        return 0;
      }
      return Math.min(totalTopics - 1, idx + 1);
    });
  const snippetNumber = (index: number) => index + 1;
  const displayTopics = useMemo(() => {
    if (Array.isArray(searchTopics) && searchTopics.length) {
      return searchTopics;
    }
    if (normalizedTopics.length) {
      const labels = normalizedTopics
        .map((topic) => topic.label ?? (topic as any).topicLabel ?? topic.query)
        .filter((value): value is string => Boolean(value && value.trim()));
      return labels.length ? Array.from(new Set(labels)) : undefined;
    }
    return undefined;
  }, [searchTopics, normalizedTopics]);
  const resolveTopicOrdinal = (topic: WebSearchTopic | undefined, fallbackIndex: number) => {
    if (!topic) {
      return fallbackIndex + 1;
    }
    const position =
      typeof topic.topic_position === 'number'
        ? topic.topic_position
        : typeof (topic as any).topicPosition === 'number'
          ? (topic as any).topicPosition
          : undefined;
    if (position && Number.isFinite(position)) {
      return Math.round(position);
    }
    const index =
      typeof topic.topic_index === 'number'
        ? topic.topic_index
        : typeof (topic as any).topicIndex === 'number'
          ? (topic as any).topicIndex
          : undefined;
    if (index !== undefined && Number.isFinite(index)) {
      return Math.round(index) + 1;
    }
    return fallbackIndex + 1;
  };
  const displayedTopicNumber = resolveTopicOrdinal(activeTopic, activeTopicIndex);

  return (
    <div className="rounded-xl border border-slate-700/70 bg-slate-900/50 overflow-hidden">
      <div className="flex items-start justify-between gap-3 px-4 py-3">
        <div>
          <h4 className="text-sm font-semibold text-slate-100">{title}</h4>
          {displayTopics && displayTopics.length ? (
            <p className="text-xs text-slate-300 mt-0.5">Topics: {displayTopics.join('; ')}</p>
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
          {'< Prev'}
        </button>
        <span>Topic {displayedTopicNumber} of {announcedTopicTotal}</span>
        <button
          type="button"
          onClick={handleNext}
          disabled={totalTopics === 0 || activeTopicIndex >= totalTopics - 1}
          className={`rounded-full border border-slate-700/70 px-2 py-1 transition ${activeTopicIndex >= totalTopics - 1 ? 'opacity-40 cursor-not-allowed' : 'hover:border-emerald-400 hover:text-emerald-300'}`}
          aria-label="Next topic"
        >
          {'Next >'}
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
              {topicBadge ? (
                <span className="inline-flex items-center rounded-full border border-slate-700/70 bg-slate-800/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-200">
                  {topicBadge}
                </span>
              ) : null}
              <p className="text-sm font-semibold text-slate-100 mt-1">
                {topicHeading}
              </p>
              {activeTopic.reason ? (
                <p className="text-xs text-slate-500 italic mt-0.5">Why: {activeTopic.reason}</p>
              ) : null}
            </div>
          </div>

          {topicSnippets.length > 0 ? (
            <ol className="mt-2 max-h-64 overflow-y-auto space-y-3 border-l border-slate-800/70 pl-4 pr-2">
              {topicSnippets.map((item, snippetIdx) => {
                const title = item.title || displayHost(item.url) || `Result ${snippetNumber(snippetIdx)}`;
                const indexLabel = `[${snippetNumber(snippetIdx)}]`;
                const indexClass = "text-xs text-slate-500 font-mono mt-0.5 inline-flex items-center";
                return (
                  <li key={item.url ?? `snippet-${activeTopicIndex}-${snippetIdx}`} className="text-sm text-slate-200">
                    <div className="flex items-start gap-2">
                      {item.url ? (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={`${indexClass} hover:text-emerald-300 transition`}
                          aria-label={`Open source ${snippetNumber(snippetIdx)}`}
                        >
                          {indexLabel}
                        </a>
                      ) : (
                        <span className={indexClass}>{indexLabel}</span>
                      )}
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
                              View source
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
