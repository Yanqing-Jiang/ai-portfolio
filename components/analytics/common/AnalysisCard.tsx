import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion } from 'framer-motion';
import { AnalysisCardProps } from '../types';

const truncate = (value: string, limit = 220) => {
  if (value.length <= limit) {
    return value;
  }
  return `${value.slice(0, limit).trimEnd()}...`;
};

export const AnalysisCard: React.FC<AnalysisCardProps> = ({ analysis, analysisSources, evidenceLinks }) => {
  const sourceEntries = useMemo(() => {
    if (!analysisSources) {
      return [];
    }

    return Object.entries(analysisSources)
      .map(([key, insight]) => {
        if (!insight) {
          return null;
        }

        const title =
          insight.label ??
          key
            .replace(/[_-]/g, ' ')
            .replace(/\b\w/g, (char) => char.toUpperCase());

        const reused = Boolean(insight.reused);
        const lines: string[] = [];

        if (insight.summary) {
          lines.push(truncate(insight.summary));
        }
        if (insight.rowCount !== undefined) {
          lines.push(`Rows analysed: ${insight.rowCount.toLocaleString()}`);
        }
        if (Array.isArray(insight.columns) && insight.columns.length) {
          const columns = insight.columns.slice(0, 4).join(', ');
          const suffix = insight.columns.length > 4 ? '...' : '';
          lines.push(`Columns: ${columns}${suffix}`);
        }
        if (Array.isArray(insight.symbols) && insight.symbols.length) {
          lines.push(`Symbols: ${insight.symbols.join(', ')}`);
        }
        if (typeof insight.latestClose === 'number') {
          const change =
            typeof insight.changePercent === 'number'
              ? ` (${insight.changePercent > 0 ? '+' : ''}${insight.changePercent.toFixed(2)}%)`
              : '';
          lines.push(`Latest close: ${insight.latestClose.toFixed(2)}${change}`);
        }
        if (typeof insight.snippetCount === 'number') {
          lines.push(`Snippets reviewed: ${insight.snippetCount}`);
        }
        if (!lines.length && reused) {
          lines.push('Cached insight reused for this run.');
        }

        return {
          key,
          title,
          reused,
          lines,
        };
      })
      .filter(Boolean) as Array<{ key: string; title: string; reused: boolean; lines: string[] }>;
  }, [analysisSources]);

  const evidenceList = useMemo(() => {
    if (!Array.isArray(evidenceLinks)) {
      return [];
    }

    return evidenceLinks
      .map((entry, index) => {
        if (!entry || typeof entry !== 'object' || !entry.sourceUrl) {
          return null;
        }

        const title =
          entry.title?.trim() ??
          entry.displayUrl?.trim() ??
          `Source ${index + 1}`;

        const snippet = entry.claim?.trim() ?? entry.snippet?.trim() ?? '';

        return {
          key: `${entry.sourceUrl}-${index}`,
          title,
          url: entry.sourceUrl,
          snippet,
        };
      })
      .filter(Boolean) as Array<{ key: string; title: string; url: string; snippet: string }>;
  }, [evidenceLinks]);

  const displaySourceEntries = useMemo(() => sourceEntries.slice(0, 3), [sourceEntries]);

  if (!analysis && sourceEntries.length === 0 && evidenceList.length === 0) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-900 border border-gray-700/80 rounded-xl shadow-xl p-4 sm:p-6 md:p-8"
    >
      <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">
        Financial Analysis
      </h2>

      {analysis && (
        <div className="prose prose-invert max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{analysis}</ReactMarkdown>
        </div>
      )}

      {sourceEntries.length > 0 && (
        <div className="mt-6">
          <div className="text-xs uppercase tracking-wide text-blue-300 font-semibold mb-3">
            Data Inputs
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {displaySourceEntries.map(({ key, title, reused, lines }) => (
              <div
                key={key}
                className="rounded-lg border border-blue-500/40 bg-blue-500/10 p-3 shadow-inner shadow-blue-900/20"
              >
                <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-blue-200">
                  <span className="font-semibold">{title}</span>
                  {reused && (
                    <span className="rounded border border-blue-300/60 px-2 py-px text-[10px] text-blue-100">
                      Cached
                    </span>
                  )}
                </div>
                {lines.map((line, idx) => (
                  <div key={`${key}-line-${idx}`} className="mt-1 text-sm text-blue-100/85 leading-relaxed">
                    {line}
                  </div>
                ))}
              </div>
            ))}
          </div>
          {sourceEntries.length > 3 && (
            <div className="mt-2 text-[11px] text-blue-200/70">
              +{sourceEntries.length - 3} more sources persisted in the run log.
            </div>
          )}
        </div>
      )}

      {evidenceList.length > 0 && (
        <div className="mt-6">
          <div className="text-xs uppercase tracking-wide text-blue-300 font-semibold mb-3">
            Sources
          </div>
          <ol className="mt-2 space-y-2 list-decimal list-inside text-sm text-blue-200/90">
            {evidenceList.map(({ key, title, url, snippet }) => (
              <li key={key} className="leading-relaxed">
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-400 underline decoration-blue-500 hover:text-blue-300 transition"
                >
                  {title}
                </a>
                {snippet && (
                  <div className="mt-1 text-xs text-slate-300/90 italic">
                    "{truncate(snippet, 280)}"
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </motion.div>
  );
};

export default AnalysisCard;
