import { describe, expect, it } from 'vitest';

import { resolveChartSpecOption } from './chartOptions';

describe('resolveChartSpecOption', () => {
  const baseSpec = {
    series: [{ name: 'Metric', data: [1, 2, 3] }],
    xAxis: { type: 'category', data: ['2023', '2024', '2025'] },
    yAxis: { type: 'value' },
    legend: { data: ['Metric'] },
  };

  it('returns the spec when payload already matches ECharts option shape', () => {
    expect(resolveChartSpecOption(baseSpec)).toBe(baseSpec);
  });

  it('unwraps nested chart_spec envelopes emitted by planner/executor flows', () => {
    const envelope = { chart_type: 'line_multi', chart_spec: baseSpec };
    expect(resolveChartSpecOption(envelope)).toBe(baseSpec);
  });

  it('unwraps EventEmitter result payloads that double wrap the chart spec', () => {
    const ssePayload = {
      event: 'chart_generated',
      data: {
        step: 'chart_generation',
        chart_spec: { chart_type: 'line_multi', chart_spec: baseSpec },
      },
    };
    expect(resolveChartSpecOption(ssePayload)).toBe(baseSpec);
  });

  it('returns null when no chart spec can be resolved', () => {
    expect(resolveChartSpecOption(undefined)).toBeNull();
    expect(resolveChartSpecOption({ foo: 'bar' })).toBeNull();
  });
});
