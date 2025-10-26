import React, { useCallback, useEffect, useMemo, useRef, useState, useId } from 'react';
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

  const parseCompositeKey = useCallback((column: string | undefined) => {
    if (typeof column !== 'string' || !column.length) {
      return { ticker: undefined as string | undefined, metric: undefined as string | undefined };
    }
    const parts = column.split('|');
    if (parts.length >= 2) {
      const [ticker, ...rest] = parts;
      return {
        ticker: ticker?.trim() || undefined,
        metric: rest.join('|').trim() || undefined,
      };
    }
    return { ticker: undefined, metric: column.trim() || undefined };
  }, []);

  const includedColumnsRaw = useMemo(() => {
    const fromMeta = spec?.meta?.includedColumns;
    if (Array.isArray(fromMeta)) {
      return fromMeta.filter((value): value is string => typeof value === 'string' && value.length > 0);
    }
    return [] as string[];
  }, [spec]);

  const metricSeriesColumns = useMemo(() => {
    const lookup = spec?.meta?.metricSeriesColumns;
    if (lookup && typeof lookup === 'object') {
      const normalized: Record<string, string[]> = {};
      Object.entries(lookup).forEach(([metric, columns]) => {
        if (Array.isArray(columns)) {
          const sanitized = columns.filter((value): value is string => typeof value === 'string' && value.length > 0);
          if (sanitized.length) {
            normalized[metric] = sanitized;
          }
        }
      });
      if (Object.keys(normalized).length) {
        return normalized;
      }
    }
    const fallback: Record<string, string[]> = {};
    includedColumnsRaw.forEach((column) => {
      const { metric } = parseCompositeKey(column);
      if (!metric) {
        return;
      }
      if (!fallback[metric]) {
        fallback[metric] = [];
      }
      if (!fallback[metric].includes(column)) {
        fallback[metric].push(column);
      }
    });
    return fallback;
  }, [includedColumnsRaw, parseCompositeKey, spec]);

  const metricLegendMap = useMemo(() => {
    const lookup = spec?.meta?.metricLegendMap;
    if (lookup && typeof lookup === 'object') {
      const normalized: Record<string, string[]> = {};
      Object.entries(lookup).forEach(([metric, legendNames]) => {
        if (Array.isArray(legendNames)) {
          const sanitized = legendNames.filter((value): value is string => typeof value === 'string' && value.length > 0);
          if (sanitized.length) {
            normalized[metric] = sanitized;
          }
        }
      });
      if (Object.keys(normalized).length) {
        return normalized;
      }
    }
    return {} as Record<string, string[]>;
  }, [spec]);

  const metricDisplayNames = useMemo(() => {
    const lookup = spec?.meta?.metricDisplayNames;
    if (lookup && typeof lookup === 'object') {
      const normalized: Record<string, string> = {};
      Object.entries(lookup).forEach(([metric, label]) => {
        if (typeof label === 'string' && label.trim().length) {
          normalized[metric] = label.trim();
        }
      });
      if (Object.keys(normalized).length) {
        return normalized;
      }
    }
    return {} as Record<string, string>;
  }, [spec]);

  const metricKeys = useMemo(() => {
    const metaMetrics = spec?.meta?.metricColumns;
    if (Array.isArray(metaMetrics) && metaMetrics.length) {
      return metaMetrics.filter(
        (value: unknown): value is string => typeof value === 'string' && value.trim().length,
      );
    }
    const dedup = new Set<string>();
    if (Object.keys(metricSeriesColumns).length) {
      Object.keys(metricSeriesColumns).forEach((metric) => {
        if (metric && metric.trim().length) {
          dedup.add(metric);
        }
      });
    } else {
      includedColumnsRaw.forEach((column) => {
        const { metric } = parseCompositeKey(column);
        if (metric) {
          dedup.add(metric);
        }
      });
    }
    return Array.from(dedup);
  }, [includedColumnsRaw, metricSeriesColumns, parseCompositeKey, spec]);

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
    return metricKeys.map((metric) => ({
      value: metric,
      label: metricDisplayNames[metric] ?? formatColumnLabel(metric),
    }));
  }, [enableDropdown, intentKey, metricDisplayNames, metricKeys]);

  const defaultDropdownValue = useMemo(() => {
    if (!dropdownOptions.length) {
      return undefined;
    }
    if (intentKey === 'revenue_growth_vs_avg') {
      return 'yoy_growth';
    }
    const defaults = Array.isArray(spec?.meta?.defaultColumns) ? spec.meta.defaultColumns : [];
    const preferredMetric = defaults.find((metric) =>
      dropdownOptions.some((option) => option.value === metric),
    );
    if (preferredMetric) {
      return preferredMetric;
    }
    return dropdownOptions[0]?.value;
  }, [dropdownOptions, intentKey, spec]);

  const [activeMetric, setActiveMetric] = useState<string | undefined>(defaultDropdownValue);
  useEffect(() => {
    setActiveMetric((prev) => {
      if (!defaultDropdownValue) {
        return prev;
      }
      if (prev === defaultDropdownValue) {
        return prev;
      }
      return defaultDropdownValue;
    });
  }, [defaultDropdownValue]);

  const [legendSelection, setLegendSelection] = useState<Record<string, boolean>>({});

  const selectValue = useMemo(() => {
    if (!dropdownOptions.length) {
      return '';
    }
    const candidate = activeMetric ?? defaultDropdownValue ?? dropdownOptions[0]?.value ?? '';
    if (dropdownOptions.some((option) => option.value === candidate)) {
      return candidate;
    }
    return dropdownOptions[0]?.value ?? '';
  }, [activeMetric, defaultDropdownValue, dropdownOptions]);

  useEffect(() => {
    const normalizeSelection = (source: unknown): Record<string, boolean> | undefined => {
      if (!source || typeof source !== 'object') {
        return undefined;
      }
      const result: Record<string, boolean> = {};
      Object.entries(source as Record<string, unknown>).forEach(([key, value]) => {
        if (typeof key === 'string') {
          result[key] = Boolean(value);
        }
      });
      return Object.keys(result).length ? result : undefined;
    };

    const fromMeta = normalizeSelection(spec?.meta?.defaultLegendSelection);
    const fromLegend = (() => {
      const legendOption = (spec?.legend as any) || {};
      if (Array.isArray(legendOption)) {
        for (const entry of legendOption) {
          const normalized = normalizeSelection(entry?.selected);
          if (normalized) {
            return normalized;
          }
        }
        return undefined;
      }
      return normalizeSelection(legendOption?.selected);
    })();

    const candidate = fromMeta ?? fromLegend;
    if (!candidate) {
      return;
    }
    setLegendSelection((prev) => {
      const prevKeys = Object.keys(prev);
      const candidateKeys = Object.keys(candidate);
      if (prevKeys.length === candidateKeys.length && candidateKeys.every((key) => prev[key] === candidate[key])) {
        return prev;
      }
      return candidate;
    });
  }, [spec]);

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

  const handleMetricChange = useCallback(
    (metricKey: string) => {
      if (!metricKey) {
        return;
      }
      setActiveMetric(metricKey);
      const instance = chartRef.current;
      if (!instance || typeof instance.getOption !== 'function') {
        return;
      }
      const option = instance.getOption() || {};
      const legendOption = option?.legend;
      const legendEntries = Array.isArray(legendOption)
        ? legendOption
        : legendOption
        ? [legendOption]
        : [];
      if (!legendEntries.length) {
        return;
      }
      const nextSelection: Record<string, boolean> = {};
      legendEntries.forEach((entry: any) => {
        if (Array.isArray(entry?.data)) {
          entry.data.forEach((name: unknown) => {
            if (typeof name === 'string') {
              nextSelection[name] = false;
            }
          });
        }
      });
      const enableSeries = (name: string) => {
        if (Object.prototype.hasOwnProperty.call(nextSelection, name)) {
          nextSelection[name] = true;
          return true;
        }
        return false;
      };

      const explicitNames = new Set(
        (metricLegendMap[metricKey] ?? []).filter(
          (value) => typeof value === 'string' && value.trim().length > 0,
        ),
      );
      let matched = false;
      if (explicitNames.size) {
        Object.keys(nextSelection).forEach((name) => {
          if (explicitNames.has(name)) {
            matched = enableSeries(name) || matched;
          }
        });
      }

      if (!matched) {
        const compositeTargets = metricSeriesColumns[metricKey] ?? [];
        if (compositeTargets.length) {
          Object.keys(nextSelection).forEach((name) => {
            const nameLower = name.trim().toLowerCase();
            compositeTargets.forEach((target) => {
              const parsed = parseCompositeKey(target);
              if (parsed.ticker && nameLower.startsWith(parsed.ticker.toLowerCase())) {
                matched = enableSeries(name) || matched;
              } else if (parsed.metric) {
                const normalizedMetric = parsed.metric.replace(/_/g, ' ').toLowerCase();
                if (normalizedMetric && nameLower.includes(normalizedMetric)) {
                  matched = enableSeries(name) || matched;
                }
              }
            });
          });
        }
      }

      if (!matched) {
        const label = metricDisplayNames[metricKey] ?? formatColumnLabel(metricKey);
        const selectedLower = label.trim().toLowerCase();
        Object.keys(nextSelection).forEach((name) => {
          const nameLower = name.trim().toLowerCase();
          if (nameLower === selectedLower || nameLower.endsWith(` - ${selectedLower}`)) {
            matched = enableSeries(name) || matched;
          } else if (
            selectedLower.includes('growth') &&
            (nameLower.includes('yoy growth') || nameLower.includes('growth'))
          ) {
            matched = enableSeries(name) || matched;
          }
        });
      }

      if (!matched) {
        const fallback =
          Object.entries(legendSelection).find(([, value]) => Boolean(value))?.[0] ??
          Object.keys(nextSelection)[0];
        if (fallback) {
          nextSelection[fallback] = true;
        }
      }

      setLegendSelection((prev) => {
        const prevKeys = Object.keys(prev);
        const nextKeys = Object.keys(nextSelection);
        if (
          prevKeys.length === nextKeys.length &&
          nextKeys.every((key) => prev[key] === nextSelection[key])
        ) {
          return prev;
        }
        return nextSelection;
      });
    },
    [
      formatColumnLabel,
      legendSelection,
      metricDisplayNames,
      metricLegendMap,
      metricSeriesColumns,
      parseCompositeKey,
      setActiveMetric,
    ],
  );

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

  useEffect(() => {
    const instance = chartRef.current;
    if (!instance) {
      return;
    }
    if (!legendSelection || typeof legendSelection !== 'object') {
      return;
    }
    try {
      const current = instance.getOption ? instance.getOption() : {};
      const legendOption = current?.legend;
      const legendEntries = Array.isArray(legendOption)
        ? legendOption
        : legendOption
        ? [legendOption]
        : [];
      const patched =
        legendEntries.length > 0
          ? legendEntries.map((entry: any) => ({
              ...(entry || {}),
              selected: {
                ...(entry?.selected || {}),
                ...legendSelection,
              },
            }))
          : [
              {
                selected: { ...legendSelection },
              },
            ];
      instance.setOption(
        {
          legend: patched,
        },
        { notMerge: false, replaceMerge: ['legend'] },
      );
    } catch (err) {
      console.warn('[ChartCard] Failed to apply legend selection', err);
    }
  }, [legendSelection]);

  return (
    <div ref={containerRef} className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8 w-full h-full flex flex-col">
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
      <div className={`${height} bg-white rounded-lg p-2 sm:p-3 flex flex-col h-full`}>
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
                  value={selectValue}
                >
                  {/* Always show metrics */}
                  {dropdownOptions.map((option) => (
                    <option key={option.value} value={option.value}>
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
        
        <div className="flex-1 min-h-0">
          <ChartErrorBoundary 
            key={`chart-${chartRetryCount}-${JSON.stringify(spec)?.substring(0,50)}`} 
            onError={handleChartError}
          >
            <EChartsReact 
              option={withLightTheme(spec)} 
              style={{ 
                height: '100%', 
                width: '100%' 
              }} 
              notMerge={false}
              lazyUpdate={true}
              opts={{ renderer: 'canvas', devicePixelRatio: window.devicePixelRatio || 1 }} 
              onChartReady={(instance) => { 
                chartRef.current = instance;
                if (instance && legendSelection && Object.keys(legendSelection).length) {
                  try {
                    const patched = {
                      legend: [
                        {
                          selected: { ...legendSelection },
                        },
                      ],
                    };
                    instance.setOption(patched, { notMerge: false, replaceMerge: ['legend'] });
                  } catch (err) {
                    console.warn('[ChartCard] Unable to apply legend selection on ready', err);
                  }
                }
                // Small delay to ensure proper initialization
                setTimeout(() => instance.resize(), 100);
              }}
            />
          </ChartErrorBoundary>
        </div>
      </div>
    </div>
  );
};





