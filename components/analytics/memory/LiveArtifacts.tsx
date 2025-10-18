import React from 'react';
import { AnalysisCard, ChartCard, SqlCard, TradingViewSymbolOverview, WebSearchCard } from '../common';
import { isValidChartSpec } from '../utils';
import type { FlowMode, StockWidgetConfig, WebSearchResult, AnalysisOverview, SpecialistCard, LatencyGuardrail, AnalysisSources } from '../types';

interface LiveArtifactsProps {
  analysisSources?: AnalysisSources | null;
  chartSpec: any;
  dataSample: any[] | null;
  sqlQuery: string;
  analysis: string;
  progressiveAnalysis: string;
  progressiveText: string;
  webSearch: WebSearchResult | null;
  stockWidget: StockWidgetConfig | null;
  isLoading: boolean;
  flowMode: FlowMode;
  persistOnComplete?: boolean;
  analysisOverview?: AnalysisOverview | null;
  specialistCards?: SpecialistCard[];
  latencyGuardrail?: LatencyGuardrail | null;
}

const SectionHeader: React.FC<{ label: string }> = ({ label }) => (
  <h3 className="text-sm font-semibold uppercase tracking-wide text-emerald-300">{label}</h3>
);

export const LiveArtifacts: React.FC<LiveArtifactsProps> = ({
  chartSpec,
  dataSample,
  sqlQuery,
  analysis,
  analysisSources = null,
  progressiveAnalysis,
  progressiveText,
  webSearch,
  stockWidget,
  isLoading,
  flowMode,
  persistOnComplete = false,
  analysisOverview = null,
  specialistCards = [],
  latencyGuardrail = null,
}) => {
  const hasChart = chartSpec && isValidChartSpec(chartSpec);
  const hasSql = Boolean(sqlQuery?.trim()) || (Array.isArray(dataSample) && dataSample.length > 0);
  const hasStock = Boolean(stockWidget && Array.isArray(stockWidget.symbols) && stockWidget.symbols.length);
  const hasWeb = Boolean(
    webSearch &&
      (webSearch.summary?.trim() ||
        (Array.isArray(webSearch.snippets) && webSearch.snippets.some((snippet) => snippet?.snippet))),
  );
  const progressiveDraft = (progressiveAnalysis || progressiveText || '').trim();
  const finalAnalysis = (analysis || '').trim();
  const showingFinalAnalysis = finalAnalysis.length > 0 && (!progressiveDraft || persistOnComplete);
  const analysisForDisplay = progressiveDraft || (persistOnComplete ? finalAnalysis : '');
  const hasAnalysis = Boolean(analysisForDisplay);
  const runComplete = Boolean(finalAnalysis);
  const allowArtifacts = isLoading || !runComplete || persistOnComplete;
  const analysisHeading = showingFinalAnalysis ? 'Final Analysis' : 'Analysis Draft';
  const supplementalCards = specialistCards.filter((card) => card.type !== 'web_context' && card.type !== 'stock_widget');
  const hasSupplementalCards = supplementalCards.length > 0;
  const evidenceEntries = analysisOverview?.evidence ?? [];
  const hasEvidence = evidenceEntries.length > 0;
  const lowConfidenceEvidence =
    hasEvidence && evidenceEntries.every((entry) => (entry.confidence ?? 0) < 0.35);

  const shouldRender =
    allowArtifacts &&
    (hasChart || hasSql || hasStock || hasWeb || hasAnalysis || hasSupplementalCards || isLoading);
  if (!shouldRender) {
    return null;
  }

  return (
    <div className="rounded-xl border border-emerald-500/30 bg-gray-900/70 p-4 sm:p-5 shadow-lg space-y-4">
      <div className="flex flex-col gap-1">
        <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-emerald-300">
          Live Specialist Outputs
        </span>
        <span className="text-xs text-gray-400">
          {isLoading
            ? 'Streaming agent updates in real time.'
            : persistOnComplete && runComplete
              ? 'Final specialist outputs from the most recent run.'
              : 'Last streamed outputs from the current prompt.'}{' '}
          {`Mode: ${flowMode.replace(/-/g, ' ')}`}
        </span>
      </div>

      {hasAnalysis && allowArtifacts && (
        <div className="bg-gray-800/60 rounded-lg border border-gray-700 p-3">
          <SectionHeader label={analysisHeading} />
          {showingFinalAnalysis && analysisOverview && (
            <div className="mt-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-emerald-100/90">
              {analysisOverview.tldr && (
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-emerald-300">Quick Take</div>
                  <div className="mt-1 text-[11px] leading-relaxed">{analysisOverview.tldr}</div>
                </div>
              )}
              {analysisOverview.highlights?.length ? (
                <div className="mt-2">
                  <div className="text-[10px] uppercase tracking-wide text-emerald-300">Key Highlights</div>
                  <ul className="mt-1 space-y-1 text-[11px] leading-relaxed">
                    {analysisOverview.highlights.slice(0, 3).map((highlight, idx) => (
                      <li key={idx}>- {highlight}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {analysisOverview.keyNumbers?.length ? (
                <div className="mt-2">
                  <div className="text-[10px] uppercase tracking-wide text-cyan-300">Key Numbers</div>
                  <ul className="mt-1 space-y-1 text-[11px] leading-relaxed text-cyan-100/90">
                    {analysisOverview.keyNumbers.map((entry, idx) => (
                      <li key={idx}>- {entry}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {analysisOverview.riskWatch?.length ? (
                <div className="mt-2">
                  <div className="text-[10px] uppercase tracking-wide text-amber-300">Risk Watch</div>
                  <ul className="mt-1 space-y-1 text-[11px] leading-relaxed text-amber-100/90">
                    {analysisOverview.riskWatch.map((entry, idx) => (
                      <li key={idx}>- {entry}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {analysisOverview.nextSteps?.length ? (
                <div className="mt-2">
                  <div className="text-[10px] uppercase tracking-wide text-sky-300">Next Steps</div>
                  <ul className="mt-1 space-y-1 text-[11px] leading-relaxed text-sky-100/90">
                    {analysisOverview.nextSteps.map((entry, idx) => (
                      <li key={idx}>- {entry}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {hasEvidence ? (
                <div className="mt-2">
                  <div className="text-[10px] uppercase tracking-wide text-emerald-200">Sources</div>
                  <ul className="mt-1 space-y-1 text-[11px] leading-relaxed text-emerald-100/90">
                    {evidenceEntries.map((entry, idx) => (
                      <li key={`${entry.sourceUrl}-${idx}`} className="flex flex-col">
                        <a
                          href={entry.sourceUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-emerald-200 underline hover:text-emerald-100"
                        >
                          {entry.title ?? entry.displayUrl ?? `Source ${idx + 1}`}
                        </a>
                        {(entry.claim || entry.snippet) && (
                          <span className="text-[10px] text-emerald-200/80">
                            {entry.claim || entry.snippet}
                          </span>
                        )}
                        {typeof entry.confidence === 'number' && (
                          <span className="text-[10px] text-emerald-200/60">
                            Confidence: {Math.round(entry.confidence * 100)}%
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                  {lowConfidenceEvidence && (
                    <div className="mt-2 text-[11px] text-amber-300">
                      Sources flagged for low confidence—consider re-running web research.
                    </div>
                  )}
                </div>
              ) : (
                <div className="mt-2 text-[11px] text-amber-200">
                  No grounded sources returned. Consider re-running web research to gather citations.
                </div>
              )}
            </div>
          )}
          <div className="mt-2">
            <AnalysisCard analysis={analysisForDisplay} analysisSources={analysisSources} />
          </div>
        </div>
      )}

      {hasChart && allowArtifacts && (
        <div className="bg-gray-800/60 rounded-lg border border-gray-700 p-3">
          <SectionHeader label="Chart (preview)" />
          <div className="mt-3 rounded-lg overflow-hidden bg-gray-900">
            <ChartCard chartSpec={chartSpec} dataSample={dataSample} enableDropdown enableCsvDownload />
          </div>
        </div>
      )}

      {hasSql && allowArtifacts && (
        <div className="bg-gray-800/60 rounded-lg border border-gray-700 p-3">
          <SectionHeader label="SQL Snapshot" />
          <div className="mt-2">
            <SqlCard sqlQuery={sqlQuery} dataSample={dataSample || undefined} compact />
          </div>
        </div>
      )}

      {hasStock && stockWidget && allowArtifacts && (
        <div className="bg-gray-800/60 rounded-lg border border-gray-700 p-3">
          <SectionHeader label="Stock Tracker" />
          <div className="mt-3">
            <TradingViewSymbolOverview config={stockWidget} />
          </div>
        </div>
      )}

      {hasWeb && webSearch && allowArtifacts && (
        <div className="bg-gray-800/60 rounded-lg border border-gray-700 p-3">
          <SectionHeader label="Web Research" />
          {webSearch.latencyStats ? (
            <div className="mt-2 text-xs text-emerald-200 flex flex-wrap gap-3">
              {typeof webSearch.latencyStats.p50_ms === 'number' && <span>p50: {webSearch.latencyStats.p50_ms} ms</span>}
              {typeof webSearch.latencyStats.total_ms === 'number' && <span>Total: {webSearch.latencyStats.total_ms} ms</span>}
              {typeof webSearch.latencyStats.max_ms === 'number' && <span>Max: {webSearch.latencyStats.max_ms} ms</span>}
              {typeof webSearch.latencyStats.min_ms === 'number' && <span>Min: {webSearch.latencyStats.min_ms} ms</span>}
              {typeof webSearch.latencyStats.samples === 'number' && <span>Samples: {webSearch.latencyStats.samples}</span>}
            </div>
          ) : null}
          {latencyGuardrail ? (
            <div
              className={`mt-2 text-xs ${
                latencyGuardrail.status === 'violation' ? 'text-amber-300' : 'text-emerald-300'
              } flex flex-col gap-1`}
            >
              <span>
                Guardrail:{' '}
                {latencyGuardrail.status === 'violation' ? 'Exceeded' : 'Within Thresholds'}
              </span>
              {latencyGuardrail.violations?.length ? (
                <span className="text-[11px] text-amber-200/80">
                  Tripped: {latencyGuardrail.violations.join(', ')}
                </span>
              ) : null}
              <span className="text-[11px] text-emerald-200/70">
                p50 = {latencyGuardrail.thresholds.p50_ms} ms · p95 = {latencyGuardrail.thresholds.p95_ms} ms
              </span>
            </div>
          ) : null}
          <div className="mt-2">
            <WebSearchCard result={webSearch} title="Live Research" emptyMessage="No snippets yet." />
          </div>
        </div>
      )}

      {hasSupplementalCards && allowArtifacts && (
        <div className="bg-gray-800/60 rounded-lg border border-gray-700 p-3">
          <SectionHeader label="Specialist Spotlight" />
          <div className="mt-2 space-y-2">
            {supplementalCards.map((card) => (
              <div
                key={`${card.type}-${card.ts ?? card.summary ?? card.topic}`}
                className="rounded-lg border border-sky-500/40 bg-sky-500/10 p-3 text-sky-100/90"
              >
                <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-sky-200">
                  <span className="font-semibold">{card.title ?? card.type.replace(/[_-]/g, ' ')}</span>
                  {card.state && <span>{card.state.replace(/[_-]/g, ' ')}</span>}
                </div>
                {card.message && (
                  <div className="mt-1 text-[11px] leading-relaxed">{card.message}</div>
                )}
                {card.topic && (
                  <div className="mt-1 text-[10px] uppercase tracking-wide text-sky-300/90">
                    Focus: <span className="normal-case text-sky-100/90">{card.topic}</span>
                  </div>
                )}
                {card.summary && <div className="mt-1 text-[11px] leading-relaxed">{card.summary}</div>}
                {card.snippets?.length ? (
                  <ul className="mt-2 space-y-1 text-[11px] leading-relaxed">
                    {card.snippets.slice(0, 2).map((snippet, idx) => (
                      <li key={idx} className="border-l-2 border-sky-400/50 pl-2">
                        {snippet.title || snippet.snippet}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default LiveArtifacts;

