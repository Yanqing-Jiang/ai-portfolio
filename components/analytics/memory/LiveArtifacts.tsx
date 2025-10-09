import React from 'react';
import { AnalysisCard, ChartCard, SqlCard, TradingViewSymbolOverview, WebSearchCard } from '../common';
import { isValidChartSpec } from '../utils';
import type { FlowMode, StockWidgetConfig, WebSearchResult } from '../types';

interface LiveArtifactsProps {
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
}

const SectionHeader: React.FC<{ label: string }> = ({ label }) => (
  <h3 className="text-sm font-semibold uppercase tracking-wide text-emerald-300">{label}</h3>
);

export const LiveArtifacts: React.FC<LiveArtifactsProps> = ({
  chartSpec,
  dataSample,
  sqlQuery,
  analysis,
  progressiveAnalysis,
  progressiveText,
  webSearch,
  stockWidget,
  isLoading,
  flowMode,
}) => {
  const hasChart = chartSpec && isValidChartSpec(chartSpec);
  const hasSql = Boolean(sqlQuery?.trim()) || (Array.isArray(dataSample) && dataSample.length > 0);
  const hasStock = Boolean(stockWidget && Array.isArray(stockWidget.symbols) && stockWidget.symbols.length);
  const hasWeb = Boolean(
    webSearch &&
      (webSearch.summary?.trim() ||
        (Array.isArray(webSearch.snippets) && webSearch.snippets.some((snippet) => snippet?.snippet))),
  );
  const liveAnalysis = progressiveAnalysis || progressiveText;
  const hasAnalysis = Boolean(liveAnalysis);
  const runComplete = Boolean(analysis && analysis.trim());
  const allowArtifacts = isLoading || !runComplete;

  const shouldRender = allowArtifacts && (hasChart || hasSql || hasStock || hasWeb || hasAnalysis || isLoading);
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
            : 'Last streamed outputs from the current prompt.'}{' '}
          {`Mode: ${flowMode.replace(/-/g, ' ')}`}
        </span>
      </div>

      {hasAnalysis && allowArtifacts && (
        <div className="bg-gray-800/60 rounded-lg border border-gray-700 p-3">
          <SectionHeader label="Analysis Draft" />
          <div className="mt-2">
            <AnalysisCard analysis={liveAnalysis} />
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
          <div className="mt-2">
            <WebSearchCard result={webSearch} title="Live Research" emptyMessage="No snippets yet." />
          </div>
        </div>
      )}
    </div>
  );
};

export default LiveArtifacts;
