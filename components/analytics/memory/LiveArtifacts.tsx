import React from 'react';
import {
  AnalysisCard,
  ChartCard,
  CollapsibleSection,
  SqlCard,
  TradingViewSymbolOverview,
  WebSearchCard,
} from '../common';
import { isValidChartSpec, sanitizeStructuredText } from '../utils';
import type {
  FlowMode,
  StockWidgetConfig,
  WebSearchResult,
  AnalysisOverview,
  SpecialistCard,
  LatencyGuardrail,
  AnalysisSources,
} from '../types';

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
  const analysisForDisplay = showingFinalAnalysis ? finalAnalysis : progressiveDraft;
  const renderedAnalysis = React.useMemo(() => {
    if (!analysisForDisplay) {
      return analysisForDisplay;
    }
    const sanitized = sanitizeStructuredText(analysisForDisplay);
    return sanitized ?? analysisForDisplay;
  }, [analysisForDisplay]);
  const hasAnalysis = Boolean(renderedAnalysis);
  const runComplete = Boolean(finalAnalysis);
  const allowArtifacts = isLoading || !runComplete || persistOnComplete;
  const analysisHeading = showingFinalAnalysis ? 'Financial Analysis' : 'Analysis Draft';
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

  const cards: React.ReactElement[] = [];

  if (hasStock && stockWidget && allowArtifacts) {
    cards.push(
      <div key="stock" className="rounded-xl border border-gray-700 bg-gray-900/50 p-3 sm:p-4 overflow-hidden">
        <TradingViewSymbolOverview config={stockWidget} height={480} />
      </div>,
    );
  }

  if (hasWeb && webSearch && allowArtifacts) {
    cards.push(
      <CollapsibleSection
        key="market"
        title="Market Research"
        defaultOpen={false}
        className="bg-gray-800/50"
      >
        {webSearch.latencyStats ? (
          <div className="mb-3 flex flex-wrap gap-3 text-xs text-emerald-200">
            {typeof webSearch.latencyStats.p50_ms === 'number' && <span>p50: {webSearch.latencyStats.p50_ms} ms</span>}
            {typeof webSearch.latencyStats.total_ms === 'number' && <span>Total: {webSearch.latencyStats.total_ms} ms</span>}
            {typeof webSearch.latencyStats.max_ms === 'number' && <span>Max: {webSearch.latencyStats.max_ms} ms</span>}
            {typeof webSearch.latencyStats.min_ms === 'number' && <span>Min: {webSearch.latencyStats.min_ms} ms</span>}
            {typeof webSearch.latencyStats.samples === 'number' && <span>Samples: {webSearch.latencyStats.samples}</span>}
          </div>
        ) : null}
        {latencyGuardrail ? (
          <div
            className={`mb-3 text-xs ${latencyGuardrail.status === 'violation' ? 'text-amber-300' : 'text-emerald-300'} flex flex-col gap-1`}
          >
            <span>
              Guardrail: {latencyGuardrail.status === 'violation' ? 'Exceeded' : 'Within Thresholds'}
            </span>
            {latencyGuardrail.violations?.length ? (
              <span className="text-[11px] text-amber-200/80">
                Tripped: {latencyGuardrail.violations.join(', ')}
              </span>
            ) : null}
            <span className="text-[11px] text-emerald-200/70">
              p50 = {latencyGuardrail.thresholds.p50_ms} ms - p95 = {latencyGuardrail.thresholds.p95_ms} ms
            </span>
          </div>
        ) : null}
        <WebSearchCard result={webSearch} title="Market Research" emptyMessage="No snippets yet." />
      </CollapsibleSection>,
    );
  }

  if (hasAnalysis && allowArtifacts) {
    cards.push(
      <div key="analysis" className="rounded-xl overflow-hidden border border-blue-500/30 bg-blue-500/10">
        <div className="border-b border-blue-500/25 bg-blue-500/15 px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-blue-100/80">
          {analysisHeading}
        </div>
        {showingFinalAnalysis && analysisOverview ? (
          <div className="space-y-3 border-b border-blue-500/20 bg-blue-500/5 px-4 py-3 text-[11px] leading-relaxed text-blue-50/90">
            {analysisOverview.tldr ? (
              <div>
                <div className="font-semibold uppercase tracking-wide text-emerald-300">Quick Take</div>
                <div className="mt-1">{analysisOverview.tldr}</div>
              </div>
            ) : null}
            {analysisOverview.highlights?.length ? (
              <div>
                <div className="font-semibold uppercase tracking-wide text-emerald-300">Key Highlights</div>
                <ul className="mt-1 space-y-1">
                  {analysisOverview.highlights.slice(0, 3).map((highlight, idx) => (
                    <li key={idx}>- {highlight}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {analysisOverview.keyNumbers?.length ? (
              <div>
                <div className="font-semibold uppercase tracking-wide text-cyan-300">Key Numbers</div>
                <ul className="mt-1 space-y-1 text-cyan-100/90">
                  {analysisOverview.keyNumbers.map((entry, idx) => (
                    <li key={idx}>- {entry}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {analysisOverview.riskWatch?.length ? (
              <div>
                <div className="font-semibold uppercase tracking-wide text-amber-300">Risk Watch</div>
                <ul className="mt-1 space-y-1 text-amber-100/90">
                  {analysisOverview.riskWatch.map((entry, idx) => (
                    <li key={idx}>- {entry}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {analysisOverview.nextSteps?.length ? (
              <div>
                <div className="font-semibold uppercase tracking-wide text-sky-300">Next Steps</div>
                <ul className="mt-1 space-y-1 text-sky-100/90">
                  {analysisOverview.nextSteps.map((entry, idx) => (
                    <li key={idx}>- {entry}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {hasEvidence ? (
              <div>
                <div className="font-semibold uppercase tracking-wide text-emerald-200">Sources</div>
                <ul className="mt-1 space-y-2 text-emerald-100/90">
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
                      {(entry.claim || entry.snippet) ? (
                        <span className="text-[10px] text-emerald-200/80">{entry.claim || entry.snippet}</span>
                      ) : null}
                      {typeof entry.confidence === 'number' ? (
                        <span className="text-[10px] text-emerald-200/60">
                          Confidence: {Math.round(entry.confidence * 100)}%
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
                {lowConfidenceEvidence ? (
                  <div className="mt-2 text-[11px] text-amber-300">
                    Sources flagged for low confidence; consider re-running web research.
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="text-[11px] text-amber-200">
                No grounded sources returned. Consider re-running web research to gather citations.
              </div>
            )}
          </div>
        ) : null}
        <div className="p-4 sm:p-5">
          <AnalysisCard analysis={renderedAnalysis} analysisSources={analysisSources} />
        </div>
      </div>,
    );
  }

  if (hasChart && allowArtifacts) {
    cards.push(
      <div
        key="sql-chart"
        className="rounded-xl border border-gray-700 bg-gray-900/40 p-3 sm:p-4 md:p-5"
      >
        <ChartCard chartSpec={chartSpec} dataSample={dataSample} enableDropdown enableCsvDownload />
      </div>,
    );
  }

  if (hasSql && allowArtifacts) {
    cards.push(
      <CollapsibleSection
        key="sql-card"
        title="Generated SQL Query"
        defaultOpen={false}
        className="bg-gray-800/50"
      >
        <SqlCard sqlQuery={sqlQuery} dataSample={dataSample || undefined} compact />
      </CollapsibleSection>,
    );
  }

  if (hasSupplementalCards && allowArtifacts) {
    cards.push(
      <div key="specialist" className="rounded-xl border border-sky-500/40 bg-sky-500/10 p-3">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-sky-200">Specialist Spotlight</div>
        <div className="mt-2 space-y-2">
          {supplementalCards.map((card) => (
            <div
              key={`${card.type}-${card.ts ?? card.summary ?? card.topic}`}
              className="rounded-lg border border-sky-500/40 bg-sky-500/10 p-3 text-sky-100/90"
            >
              <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-sky-200">
                <span className="font-semibold">{card.title ?? card.type.replace(/[_-]/g, ' ')}</span>
                <div className="flex items-center gap-2">
                  {card.revision ? (
                    <span className="rounded border border-emerald-300/60 bg-emerald-400/10 px-2 py-[1px] text-[9px] font-semibold text-emerald-200">Revision</span>
                  ) : null}
                  {card.state ? <span>{card.state.replace(/[_-]/g, ' ')}</span> : null}
                </div>
              </div>
              {card.message ? <div className="mt-1 text-[11px] leading-relaxed">{card.message}</div> : null}
              {card.topic ? (
                <div className="mt-1 text-[10px] uppercase tracking-wide text-sky-300/90">
                  Focus: <span className="normal-case text-sky-100/90">{card.topic}</span>
                </div>
              ) : null}
              {card.summary ? <div className="mt-1 text-[11px] leading-relaxed">{card.summary}</div> : null}
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
      </div>,
    );
  }
  if (!cards.length) {
    return null;
  }

  return <div className="space-y-4">{cards}</div>;
};

export default LiveArtifacts;





