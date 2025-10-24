// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ChartCard } from '../ChartCard';
import { hydrateChartSpec } from '../../utils';

let latestInstance: any;

// Mock echarts-for-react so we can intercept onChartReady and props
vi.mock('echarts-for-react', () => {
  return {
    default: ({ onChartReady }: any) => {
      // provide a minimal instance with resize
      const instance = {
        resize: vi.fn(),
        getOption: vi.fn(() => ({ legend: [{ data: [], selected: {} }] })),
        setOption: vi.fn(),
      };
      latestInstance = instance;
      // simulate chart becoming ready immediately
      setTimeout(() => onChartReady && onChartReady(instance), 0);
      return <div data-testid="echarts-mock" />;
    },
  };
});

const sampleSpec = {
  chart_type: 'line',
  legend: { data: ['Revenue'], selected: { Revenue: true } },
  xAxis: { type: 'category', data: ['A', 'B'] },
  yAxis: { type: 'value' },
  series: [{ name: 'Revenue', type: 'line', data: [1, 2] }],
  meta: {
    includedColumns: ['revenue'],
    metricColumns: ['revenue'],
    metricSeriesColumns: { revenue: ['revenue'] },
    metricLegendMap: { revenue: ['Revenue'] },
    metricDisplayNames: { revenue: 'Revenue' },
    defaultColumns: ['revenue'],
  },
};

describe('ChartCard', () => {
  beforeEach(() => {
    // Polyfill ResizeObserver
    (global as any).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  });

  it('renders the Interactive Visualization header', async () => {
    render(<ChartCard chartSpec={sampleSpec as any} />);
    expect(screen.getByText('Interactive Visualization')).toBeInTheDocument();
  });

  it('renders scope banner and ranking pill when metadata provided', async () => {
    const rankingSpec = {
      ...sampleSpec,
      chart_type: 'ranking_bar',
      meta: {
        ...sampleSpec.meta,
        scopeBanner: 'Ranking latest operating leverage across AMD, NVDA',
        chartDesign: { statistic: 'ranking_latest' },
        ranking: { metric: 'operating_margin', tickers: ['NVDA', 'AMD'] },
      },
    };
    render(<ChartCard chartSpec={rankingSpec as any} enableDropdown />);
    expect(screen.getByTestId('chart-scope-banner')).toHaveTextContent('Ranking latest operating leverage across AMD, NVDA');
    expect(screen.getByTestId('chart-ranking-pill')).toHaveTextContent(/operating margin/i);
    expect(screen.getByTestId('chart-ranking-pill')).toHaveTextContent(/NVDA/i);
  });

  it('preserves direct legend selections for plain-label series', async () => {
    const legendOption = {
      legend: [{
        data: ['Market Share Percent', 'Total Market Revenue'],
        selected: {
          'Market Share Percent': true,
          'Total Market Revenue': false,
        },
      }],
    };

    render(
      <ChartCard
        chartSpec={{
          ...sampleSpec,
          meta: {
            includedColumns: ['market_share_percent', 'total_market_revenue'],
            metricColumns: ['market_share_percent', 'total_market_revenue'],
            metricSeriesColumns: {
              market_share_percent: ['market_share_percent'],
              total_market_revenue: ['total_market_revenue'],
            },
            metricLegendMap: {
              market_share_percent: ['Market Share Percent'],
              total_market_revenue: ['Total Market Revenue'],
            },
            metricDisplayNames: {
              market_share_percent: 'Market Share Percent',
              total_market_revenue: 'Total Market Revenue',
            },
            defaultColumns: ['market_share_percent'],
          },
        } as any}
        enableDropdown
      />,
    );

    await waitFor(() => expect(latestInstance).toBeDefined());
    latestInstance.getOption.mockReturnValue(legendOption);

    const select = screen.getByLabelText('Series:');
    fireEvent.change(select, { target: { value: 'market_share_percent' } });

    await waitFor(() => {
      const callWithLegend = [...latestInstance.setOption.mock.calls]
        .reverse()
        .find(([opts]) => opts?.legend);
      expect(callWithLegend).toBeTruthy();
      const selected = callWithLegend?.[0]?.legend?.[0]?.selected ?? {};
      expect(selected['Market Share Percent']).toBe(true);
      expect(selected['Total Market Revenue']).toBe(false);
    });
  });

  it('prefers displayNames metadata for dropdown labels', () => {
    render(
      <ChartCard
        chartSpec={{
          ...sampleSpec,
          meta: {
            includedColumns: ['market_share_percent'],
            metricColumns: ['market_share_percent'],
            metricSeriesColumns: { market_share_percent: ['market_share_percent'] },
            metricLegendMap: { market_share_percent: ['Market Share Percent'] },
            metricDisplayNames: { market_share_percent: 'Market Share' },
            defaultColumns: ['market_share_percent'],
            displayNames: { market_share_percent: 'Market Share Percent' },
          },
        } as any}
        enableDropdown
      />,
    );

    const select = screen.getByLabelText('Series:') as HTMLSelectElement;
    expect(select.value).toBe('market_share_percent');
    expect(screen.getAllByRole('option')[0]).toHaveTextContent('Market Share');
  });

  it('coerces string series values to numbers during hydration', () => {
    const hydrated = hydrateChartSpec({
      series: [
        { name: 'Metric A', data: ['1.5', ''] },
        { name: 'Metric B', data: ['-3.2', null, 'Not a Number'] },
      ],
      meta: {},
    });

    expect(hydrated.series[0].data).toEqual([1.5, null]);
    expect(hydrated.series[1].data).toEqual([-3.2, null, null]);
  });

  it('hydrates composite multi-company metrics from displayNames fallback', () => {
    const spec = {
      legend: {
        data: ['AMD - Revenue', 'NVDA - Revenue'],
        selected: {
          'AMD - Revenue': true,
          'NVDA - Revenue': true,
        },
      },
      xAxis: { type: 'category' },
      yAxis: { type: 'value' },
      series: [
        { name: 'AMD - Revenue', type: 'line' },
        { name: 'NVDA - Revenue', type: 'line' },
      ],
      meta: {
        rawData: [
          { ticker: 'AMD', calendar_year: 2021, revenue: 38_782_001_152 },
          { ticker: 'NVDA', calendar_year: 2021, revenue: 53_822_001_152 },
          { ticker: 'AMD', calendar_year: 2022, revenue: 47_489_998_848 },
          { ticker: 'NVDA', calendar_year: 2022, revenue: 71_101_998_848 },
          { ticker: 'AMD', calendar_year: 2023, revenue: 39_192_002_560 },
          { ticker: 'NVDA', calendar_year: 2023, revenue: 93_702_002_560 },
          { ticker: 'AMD', calendar_year: 2024, revenue: 60_693_000_192 },
          { ticker: 'NVDA', calendar_year: 2024, revenue: 234_000_000_000 },
        ],
        includedColumns: ['AMD|revenue', 'NVDA|revenue'],
        metricColumns: ['revenue'],
        metricSeriesColumns: { revenue: ['AMD|revenue', 'NVDA|revenue'] },
        metricLegendMap: { revenue: ['AMD - Revenue', 'NVDA - Revenue'] },
        metricDisplayNames: { revenue: 'Revenue' },
        defaultColumns: ['revenue'],
        displayNames: {
          'AMD|revenue': 'AMD - Revenue',
          revenue: 'AMD - Revenue',
          'NVDA|revenue': 'NVDA - Revenue',
        },
        grouping: 'ticker',
      },
    };

    const hydrated = hydrateChartSpec(spec);
    const amdSeries = hydrated.series.find((s: any) => s.name === 'AMD - Revenue');
    const nvdaSeries = hydrated.series.find((s: any) => s.name === 'NVDA - Revenue');

    expect(amdSeries?.data).toEqual([
      38_782_001_152,
      47_489_998_848,
      39_192_002_560,
      60_693_000_192,
    ]);
    expect(nvdaSeries?.data).toEqual([
      53_822_001_152,
      71_101_998_848,
      93_702_002_560,
      234_000_000_000,
    ]);
  });
});

