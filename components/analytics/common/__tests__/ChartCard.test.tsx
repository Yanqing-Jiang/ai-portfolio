// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChartCard } from '../ChartCard';

// Mock echarts-for-react so we can intercept onChartReady and props
vi.mock('echarts-for-react', () => {
  return {
    default: ({ onChartReady }: any) => {
      // provide a minimal instance with resize
      const instance = { resize: vi.fn(), getOption: vi.fn(() => ({ legend: [{ data: [] }] })) };
      // simulate chart becoming ready immediately
      setTimeout(() => onChartReady && onChartReady(instance), 0);
      return <div data-testid="echarts-mock" />;
    },
  };
});

const sampleSpec = {
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
});

