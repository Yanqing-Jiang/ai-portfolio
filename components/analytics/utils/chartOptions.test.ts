import { describe, expect, it } from 'vitest';

import { resolveChartSpecOption, applyChartOps, hydrateChartSpec } from './chartOptions';

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

describe('hydrateChartSpec', () => {
  it('sorts raw data chronologically before hydrating series output', () => {
    const spec = {
      series: [{ name: 'Revenue', type: 'line', data: [] }],
      xAxis: { type: 'category' },
      meta: {
        rawData: [
          { calendar_year: 2024, calendar_quarter: 'Q2', revenue: 120 },
          { calendar_year: 2023, calendar_quarter: 'Q4', revenue: 90 },
          { calendar_year: 2024, calendar_quarter: 'Q1', revenue: 110 },
        ],
        displayNames: { revenue: 'Revenue' },
        includedColumns: ['revenue'],
      },
    } as any;

    const hydrated = hydrateChartSpec(spec);
    const xAxisData = Array.isArray(hydrated.xAxis) ? hydrated.xAxis[0].data : hydrated.xAxis.data;

    expect(xAxisData).toEqual(['Q4 2023', 'Q1 2024', 'Q2 2024']);
    expect(hydrated.series[0].data).toEqual([90, 110, 120]);
    expect(hydrated.meta?.rawData?.map((row: any) => row.calendar_quarter)).toEqual(['Q4', 'Q1', 'Q2']);
  });

  it('scales decimal percent series to percentage space when metadata marks it as percent', () => {
    const spec = {
      series: [{ name: 'Market Share', type: 'line', data: [0.046, 0.089] }],
      xAxis: { type: 'category', data: ['2024', '2025'] },
      meta: {
        seriesValueType: { 'Market Share': 'percent' },
      },
    } as any;

    const hydrated = hydrateChartSpec(spec);

    expect(hydrated.series[0].data[0]).toBeCloseTo(4.6, 5);
    expect(hydrated.series[0].data[1]).toBeCloseTo(8.9, 5);
    expect(hydrated.meta?.seriesPercentFormat?.['Market Share']).toBe('pre_multiplied');
  });

  it('removes decimal shadow series when a percent variant is present', () => {
    const spec = {
      series: [
        { name: 'Market Share Percent', type: 'line', data: [7.2, 12.5, 19.4] },
        { name: 'Market Share', type: 'line', data: [0.072, 0.125, 0.194] },
        { name: 'Company Revenue', type: 'bar', data: [120, 150, 180] },
      ],
      xAxis: { type: 'category', data: ['2023', '2024', '2025'] },
      legend: {
        data: ['Market Share Percent', 'Market Share', 'Company Revenue'],
        selected: {
          'Market Share Percent': true,
          'Market Share': false,
          'Company Revenue': true,
        },
      },
    } as any;

    const hydrated = hydrateChartSpec(spec);
    const names = hydrated.series.map((entry: any) => entry.name);
    expect(names).toEqual(['Market Share', 'Company Revenue']);

    const legend = Array.isArray(hydrated.legend) ? hydrated.legend[0] : hydrated.legend;
    expect(legend.data).toEqual(['Market Share', 'Company Revenue']);
    expect(legend.selected).toEqual({
      'Market Share': true,
      'Company Revenue': true,
    });
  });
});

describe('applyChartOps', () => {
  const base = {
    xAxis: { type: 'category', data: ['2023', '2024'] },
    yAxis: { type: 'value' },
    legend: { data: ['AMD - Revenue', 'NVDA - Revenue'], selected: { 'AMD - Revenue': true, 'NVDA - Revenue': true } },
    series: [
      { name: 'AMD - Revenue', type: 'line', data: [1, 2] },
      { name: 'NVDA - Revenue', type: 'line', data: [2, 3] },
    ],
    meta: { chartDesign: { chart_type: 'line_multi' } },
  } as any;

  it('set_chart_type switches all series to bar and sets chartDesign hint', () => {
    const next = applyChartOps(base, { ops: [{ op: 'set_chart_type', value: 'bar' }] });
    expect(next.series.every((s: any) => s.type === 'bar')).toBe(true);
    expect(next.meta?.chartDesign?.chart_type).toBe('bar');
  });

  it('toggle_series hides selected legends only', () => {
    const next = applyChartOps(base, { ops: [{ op: 'toggle_series', names: ['NVDA - Revenue'], visible: false }] });
    expect(next.legend.selected['NVDA - Revenue']).toBe(false);
    expect(next.legend.selected['AMD - Revenue']).toBe(true);
  });

  it('set_y_axis_format marks meta.chartValueType', () => {
    const next = applyChartOps(base, { ops: [{ op: 'set_y_axis_format', valueType: 'percent' }] });
    expect(next.meta?.chartValueType).toBe('percent');
  });

  it('set_stack percent sets stack and percent hint', () => {
    const next = applyChartOps(base, { ops: [{ op: 'set_stack', stack: true, mode: 'percent' }] });
    expect(next.series.every((s: any) => s.stack === 'total')).toBe(true);
    expect(next.meta?.chartValueType).toBe('percent');
  });

  it('set_x_axis updates xAxis name and chartDesign x_field', () => {
    const next = applyChartOps(base, { ops: [{ op: 'set_x_axis', field: 'calendar_quarter' }] });
    const arr = Array.isArray(next.xAxis) ? next.xAxis : [next.xAxis];
    expect(arr[0].name).toBe('calendar_quarter');
    expect(next.meta?.chartDesign?.x_field).toBe('calendar_quarter');
  });

  it('filter_companies toggles legend selection by prefix', () => {
    const next = applyChartOps(base, { ops: [{ op: 'filter_companies', tickers: ['AMD'] }] });
    expect(next.legend.selected['AMD - Revenue']).toBe(true);
    expect(next.legend.selected['NVDA - Revenue']).toBe(false);
  });

  it('set_palette assigns color array', () => {
    const colors = ['#111', '#222', '#333'];
    const next = applyChartOps(base, { ops: [{ op: 'set_palette', palette: colors }] });
    expect(next.color).toEqual(colors);
  });

  it('set_axis_scale updates yAxis to log', () => {
    const next = applyChartOps(base, { ops: [{ op: 'set_axis_scale', axis: 'y', scale: 'log' }] });
    const arr = Array.isArray(next.yAxis) ? next.yAxis : [next.yAxis];
    expect(arr[0].type).toBe('log');
  });

  it('select_metrics includes specific metric names (suffix matching)', () => {
    const spec = {
      ...base,
      series: [
        { name: 'AMD - Revenue', type: 'line', data: [1, 2] },
        { name: 'AMD - Gross Margin', type: 'line', data: [0.5, 0.6] },
        { name: 'NVDA - Revenue', type: 'line', data: [2, 3] },
      ],
      legend: {
        data: ['AMD - Revenue', 'AMD - Gross Margin', 'NVDA - Revenue'],
        selected: { 'AMD - Revenue': true, 'AMD - Gross Margin': true, 'NVDA - Revenue': true },
      },
    } as any;
    const next = applyChartOps(spec, { ops: [{ op: 'select_metrics', include: ['Revenue'] }] });
    expect(next.legend.selected['AMD - Revenue']).toBe(true);
    expect(next.legend.selected['NVDA - Revenue']).toBe(true);
    expect(next.legend.selected['AMD - Gross Margin']).toBe(false);
  });

  it('set_grouping writes meta.groupingType', () => {
    const next = applyChartOps(base, { ops: [{ op: 'set_grouping', grouping: 'ticker' }] });
    expect(next.meta?.groupingType).toBe('ticker');
  });
});
