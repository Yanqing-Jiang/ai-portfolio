import React, { useEffect, useMemo, useRef, useState, useId } from 'react';
import EChartsReact from 'echarts-for-react';
import { ChartCardProps } from '../types';
import { ChartErrorBoundary } from './ChartErrorBoundary';
import { withLightTheme, hydrateChartSpec, downloadCsv, extractDataFromChartSpec } from '../utils';

export const ChartCard: React.FC<ChartCardProps> = ({
  chartSpec,
  dataSample,
  useAltChart = false,
  height = 'h-[280px] sm:h-[360px] md:h-[440px] lg:h-[520px]',
  onError,
  enableDropdown = false,
  enableCsvDownload = false
}) => {
  const [chartRetryCount, setChartRetryCount] = useState(0);
  const chartRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const dropdownId = useId();
  const resolvedSpec = useMemo(() => hydrateChartSpec(chartSpec), [chartSpec]);
  const spec = resolvedSpec;

  const intentKey =
    spec?.meta?.chartDesign?.intent ??
    spec?.meta?.intent ??
    spec?.meta?.intent_key ??
    spec?.intent_key ??
    spec?.intent;

  const formatColumnLabel = (column: string) =>
    column
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (m: string) => m.toUpperCase());

  const dropdownOptions = useMemo(() => {
    if (!enableDropdown) {
      return [] as Array<{ label: string; value: string }>;
    }

    if (intentKey === 'revenue_growth_vs_avg') {
      return [
        { label: 'YoY Growth', value: 'yoy_growth' },
        { label: 'Company', value: 'company' },
        { label: 'Industry Average', value: 'industry' },
      ];
    }

    const included = Array.isArray(spec?.meta?.includedColumns) ? spec.meta.includedColumns : [];
    return included.map((column: string) => ({
      value: column,
      label: formatColumnLabel(column),
    }));
  }, [enableDropdown, intentKey, spec]);

  const defaultDropdownValue = useMemo(() => {
    if (!dropdownOptions.length) {
      return undefined;
    }
    if (intentKey === 'revenue_growth_vs_avg') {
      return 'YoY Growth';
    }
    const defaults = Array.isArray(spec?.meta?.defaultColumns) ? spec.meta.defaultColumns : [];
    if (defaults.length) {
      const preferred = dropdownOptions.find(
        (option) => option.value === defaults[0] || option.label === formatColumnLabel(defaults[0]),
      );
      if (preferred) {
        return preferred.label;
      }
    }
    return dropdownOptions[0]?.label;
  }, [dropdownOptions, intentKey, spec]);

  const handleChartError = (error: any) => {
    console.log('[ChartCard] Chart error boundary triggered:', error);
    if (chartRetryCount >= 1) {
      onError?.(error);
    } else {
      setChartRetryCount(prev => prev + 1);
      setTimeout(() => {
        // Force re-render by triggering parent update
        onError?.(error);
      }, 200);
    }
  };

  const handleMetricChange = (selectedMetric: string) => {
    const instance = chartRef.current;
    if (instance) {
      const current = instance.getOption();
      const legend = current.legend && current.legend[0];
      if (legend && legend.data) {
        const selectedMap: any = legend.selected || {};
        const selectedLower = selectedMetric.trim().toLowerCase();
        const fallbackSelection = Object.entries(selectedMap).find(([, value]: [string, unknown]) => Boolean(value))?.[0];
        // Hide all series first
        legend.data.forEach((name: string) => selectedMap[name] = false);
        let matched = false;
        // Show series based on selection
        legend.data.forEach((name: string) => {
          const nameLower = name.trim().toLowerCase();

          if (nameLower === selectedLower) {
            selectedMap[name] = true;
            matched = true;
            return;
          }
          // Handle different series name patterns
          if (name.endsWith(' - ' + selectedMetric)) {
            // Standard pattern: "Company - Metric"
            selectedMap[name] = true;
            matched = true;
          } else if (selectedLower === 'yoy growth' && nameLower.includes('yoy growth')) {
            // Revenue growth pattern: show both company and industry average
            selectedMap[name] = true;
            matched = true;
          } else if (selectedLower === 'company' && nameLower.includes(' - yoy growth') && !nameLower.includes('industry')) {
            // Show only company data for revenue growth
            selectedMap[name] = true;
            matched = true;
          } else if (selectedLower === 'industry average' && nameLower.includes('industry average')) {
            // Show only industry average data
            selectedMap[name] = true;
            matched = true;
          } else if (selectedLower.includes('margin change') && nameLower.includes('margin change')) {
            // Margin growth pattern: show both company and industry average
            selectedMap[name] = true;
            matched = true;
          } else if (selectedLower === 'company' && nameLower.includes(' - ') && nameLower.includes('margin change') && !nameLower.includes('industry')) {
            // Show only company data for margin growth
            selectedMap[name] = true;
            matched = true;
          } else if (selectedLower === 'industry average' && nameLower.includes('industry average') && nameLower.includes('margin change')) {
            // Show only industry average data for margin growth
            selectedMap[name] = true;
            matched = true;
          }
        });

        if (!matched) {
          const fallback = legend.data.find((name: string) => name.trim().toLowerCase() === selectedLower) ?? fallbackSelection ?? legend.data[0];
          if (fallback) {
            selectedMap[fallback] = true;
          }
        }

        instance.setOption({ legend: [{ selected: selectedMap }] });
      }
    }
  };

  const scopeBanner = spec?.meta?.scopeBanner;
  const statistic = spec?.meta?.chartDesign?.statistic ?? spec?.statistic;
  const rankingMeta = spec?.meta?.ranking;
  const isRankingChart = statistic === 'ranking_latest' || spec?.chart_type === 'ranking_bar';
  const scheduleStage =
    spec?.meta?.scheduleStage ??
    spec?.meta?.schedule_stage ??
    spec?.meta?.chartStage ??
    spec?.schedule_stage;
  const parallelGroup =
    spec?.meta?.parallelGroup ??
    spec?.meta?.parallel_group ??
    spec?.meta?.telemetryGroup ??
    spec?.parallel_group;
  const flowMode =
    spec?.meta?.flowMode ??
    spec?.meta?.mode ??
    spec?.flow_mode;
  const rankingSummary = useMemo(() => {
    if (!isRankingChart) return null;
    const metricLabel = rankingMeta?.metric?.replace(/_/g, ' ').replace(/\b\w/g, (m: string) => m.toUpperCase());
    const leader = rankingMeta?.tickers?.[0];
    if (metricLabel && leader) {
      return `${metricLabel} leader: ${leader}`;
    }
    if (metricLabel) {
      return `${metricLabel} leaderboard`;
    }
    return 'Ranking leaderboard';
  }, [isRankingChart, rankingMeta]);
  const scheduleLabel = useMemo(() => {
    if (!flowMode && !scheduleStage && !parallelGroup) {
      return null;
    }
    const parts: string[] = [];
    if (flowMode) parts.push(flowMode.replace(/[-_]/g, ' '));
    if (parallelGroup) parts.push(parallelGroup.replace(/[-_]/g, ' '));
    if (scheduleStage) parts.push(scheduleStage.replace(/[-_]/g, ' '));
    return parts.join(' • ');
  }, [flowMode, scheduleStage, parallelGroup]);

  const handleCsvDownload = () => {
    const data = extractDataFromChartSpec(spec);
    downloadCsv(data, 'analytics_data.csv');
  };

  if (!spec || useAltChart) {
    return null;
  }

  // Ensure the chart resizes when its parent panel toggles visibility or changes size
  useEffect(() => {
    const ro = (window as any).ResizeObserver
      ? new (window as any).ResizeObserver(() => {
          if (chartRef.current) {
            try { chartRef.current.resize(); } catch {}
          }
        })
      : null;
    if (ro && containerRef.current) {
      ro.observe(containerRef.current);
    }
    const onWinResize = () => {
      if (chartRef.current) {
        try { chartRef.current.resize(); } catch {}
      }
    };
    window.addEventListener('resize', onWinResize);
    return () => {
      window.removeEventListener('resize', onWinResize);
      if (ro && containerRef.current) ro.unobserve(containerRef.current);
    };
  }, []);

  // Apply updates deterministically with replaceMerge to avoid stale series/axes
  useEffect(() => {
    const instance = chartRef.current;
    if (!instance || !spec) return;
    try {
      const themed = withLightTheme(spec);
      // If echarts-for-react already set option via prop, this is a reinforcement to ensure replaceMerge semantics
      instance.setOption(themed, { replaceMerge: ['series', 'xAxis', 'yAxis'] });
    } catch (e) {
      // swallow to avoid breaking UI in edge cases
      console.warn('[ChartCard] setOption replaceMerge failed', e);
    }
  }, [spec]);

  return (
    <div ref={containerRef} className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8">
      <div className="flex flex-col gap-3 mb-3 sm:mb-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white">Interactive Visualization</h2>
          {rankingSummary && (
            <span
              data-testid="chart-ranking-pill"
              className="inline-flex items-center gap-2 rounded-full bg-emerald-500/20 text-emerald-200 px-3 py-1 text-xs font-medium uppercase tracking-wide"
            >
              <span className="h-2 w-2 rounded-full bg-emerald-300" />
              {rankingSummary}
            </span>
          )}
          {!rankingSummary && scheduleLabel && (
            <span
              data-testid="chart-schedule-pill"
              className="inline-flex items-center gap-2 rounded-full bg-indigo-500/20 text-indigo-200 px-3 py-1 text-xs font-medium uppercase tracking-wide"
            >
              <span className="h-2 w-2 rounded-full bg-indigo-300" />
              {scheduleLabel}
            </span>
          )}
          {rankingSummary && scheduleLabel && (
            <span
              data-testid="chart-schedule-pill"
              className="inline-flex items-center gap-2 rounded-full bg-indigo-500/20 text-indigo-200 px-3 py-1 text-xs font-medium uppercase tracking-wide"
            >
              <span className="h-2 w-2 rounded-full bg-indigo-300" />
              {scheduleLabel}
            </span>
          )}
        </div>
        {scopeBanner && (
          <div
            data-testid="chart-scope-banner"
            className="rounded-lg border border-emerald-400/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100"
          >
            <span className="font-semibold uppercase tracking-wide text-xs text-emerald-300 mr-2">
              Scope
            </span>
            {scopeBanner}
          </div>
        )}
      </div>
      <div className={`${height} bg-white rounded-lg p-2 sm:p-3`}>
        {/* Controls row */}
        {(enableDropdown || enableCsvDownload) && (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-4 mb-3 sm:mb-2">
            {enableDropdown && (
              <div className="flex items-center gap-2 text-gray-700 text-sm sm:text-base">
                <label className="font-medium" htmlFor={dropdownId}>Series:</label>
                <select
                  id={dropdownId}
                  className="bg-gray-100 border border-gray-300 rounded px-2 sm:px-3 py-1 sm:py-1.5 text-sm sm:text-base min-h-[32px] sm:min-h-[36px]"
                  onChange={(e) => handleMetricChange(e.target.value)}
                  defaultValue={defaultDropdownValue}
                >
                  {/* Always show metrics */}
                  {dropdownOptions.map((option) => (
                    <option key={option.value} value={option.label}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {enableCsvDownload && (
              <button
                className="px-3 py-1.5 bg-gray-100 border border-gray-300 rounded text-gray-700 text-sm hover:bg-gray-200"
                onClick={handleCsvDownload}
              >
                Download CSV
              </button>
            )}
          </div>
        )}
        
        <ChartErrorBoundary 
          key={`chart-${chartRetryCount}-${JSON.stringify(spec)?.substring(0,50)}`} 
          onError={handleChartError}
        >
          <EChartsReact 
            option={withLightTheme(spec)} 
            style={{ 
              height: enableDropdown || enableCsvDownload ? 'calc(100% - 36px)' : 'calc(100% - 4px)', 
              width: '100%' 
            }} 
            notMerge={false}
            lazyUpdate={true}
            opts={{ renderer: 'canvas', devicePixelRatio: window.devicePixelRatio || 1 }} 
            onChartReady={(instance) => { 
              chartRef.current = instance;
              // Small delay to ensure proper initialization
              setTimeout(() => instance.resize(), 100);
            }}
          />
        </ChartErrorBoundary>
      </div>
    </div>
  );
};





