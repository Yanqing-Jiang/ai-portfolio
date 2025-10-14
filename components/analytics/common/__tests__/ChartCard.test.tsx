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
  xAxis: { type: 'category', data: ['A', 'B'] },
  yAxis: { type: 'value' },
  series: [{ type: 'line', data: [1, 2] }],
  meta: { includedColumns: ['revenue'], defaultColumns: ['revenue'] },
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
            defaultColumns: ['market_share_percent'],
          },
        } as any}
        enableDropdown
      />,
    );

    await waitFor(() => expect(latestInstance).toBeDefined());
    latestInstance.getOption.mockReturnValue(legendOption);

    const select = screen.getByLabelText('Series:');
    fireEvent.change(select, { target: { value: 'Market Share Percent' } });

    await waitFor(() => {
      const selected = latestInstance.setOption.mock.calls.at(-1)?.[0]?.legend?.[0]?.selected ?? {};
      expect(selected['Market Share Percent']).toBe(true);
      expect(selected['Total Market Revenue']).toBe(false);
    });
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
});

