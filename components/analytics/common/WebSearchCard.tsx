import React from 'react';
import { WebSearchResult } from '../types';

interface WebSearchCardProps {
  result: WebSearchResult;
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

export const WebSearchCard: React.FC<WebSearchCardProps> = ({ result }) => {
  if (!result) {
    return null;
  }

  const { query, summary, snippets = [], fromCache, fetchedAt } = result;
  const hasSnippets = snippets.length > 0;

  return (
    <div className="rounded-xl border border-slate-700/70 bg-slate-900/50 overflow-hidden">
      <div className="flex items-start justify-between gap-3 px-4 py-3">
        <div>
          <h4 className="text-sm font-semibold text-slate-100">Search Highlights</h4>
          {query ? <p className="text-xs text-slate-400 mt-0.5">Query: {query}</p> : null}
          {fetchedAt ? (
            <p className="text-xs text-slate-500 mt-0.5">
              Retrieved: {formatPublishedDate(fetchedAt) ?? fetchedAt}
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {typeof result.latencyMs === 'number' ? (
            <span className="text-[11px] text-slate-400 bg-slate-800/80 border border-slate-700/70 rounded-full px-2 py-0.5">
              {result.latencyMs} ms
            </span>
          ) : null}
          {fromCache ? (
            <span className="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/40 rounded-full px-2 py-0.5">
              Cached
            </span>
          ) : (
            <span className="text-[11px] text-emerald-300 bg-emerald-500/10 border border-emerald-500/40 rounded-full px-2 py-0.5">
              Fresh
            </span>
          )}
        </div>
      </div>

      {summary ? (
        <p className="px-4 pb-3 text-sm text-slate-200 leading-relaxed border-b border-slate-800/70">
          {summary}
        </p>
      ) : null}

      {hasSnippets ? (
        <ul className="divide-y divide-slate-800">
          {snippets.map((item, index) => (
            <li key={item.url ?? `snippet-${index}`} className="px-4 py-3 text-sm text-slate-200">
              {item.title ? (
                <a
                  href={item.url ?? '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-slate-100 hover:text-emerald-300 transition"
                >
                  {item.title}
                </a>
              ) : item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-slate-100 hover:text-emerald-300 transition"
                >
                  {item.url}
                </a>
              ) : (
                <span className="font-medium text-slate-100">Result {index + 1}</span>
              )}

              {item.snippet ? (
                <p className="mt-1 text-xs text-slate-300 leading-relaxed">{item.snippet}</p>
              ) : null}

              <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                {item.display_url ? <span>{item.display_url}</span> : null}
                {item.published_at ? <span>· {formatPublishedDate(item.published_at) ?? item.published_at}</span> : null}
                {item.url ? (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-emerald-300 hover:text-emerald-200"
                  >
                    Open source ?
                  </a>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="px-4 py-3 text-sm text-slate-400">No search snippets available.</div>
      )}
    </div>
  );
};
