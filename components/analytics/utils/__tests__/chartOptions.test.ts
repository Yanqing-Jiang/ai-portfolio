import { describe, expect, it } from 'vitest';
import { withLightTheme } from '../chartOptions';

const sampleCurrencySpec = {
  title: { text: 'Financial Analytics' },
  tooltip: {},
  legend: { data: ['NVDA'] },
  xAxis: {
    type: 'category',
    data: ['2021', '2022', '2023'],
  },
  yAxis: [
    {
      type: 'value',
      name: 'Currency',
      axisLabel: {},
    },
  ],
  series: [
    {
      name: 'NVDA',
      type: 'line',
      data: [10, 20, 30],
    },
  ],
  meta: {
    seriesValueType: {
      NVDA: 'currency',
    },
  },
};

const samplePercentSpec = {
  title: { text: 'Margin' },
  tooltip: {},
  legend: { data: ['AMD Margin'] },
  xAxis: {
    type: 'category',
    data: ['Q1', 'Q2', 'Q3'],
  },
  yAxis: [
    {
      type: 'value',
      name: 'Percentage',
      axisLabel: {},
    },
  ],
  series: [
    {
      name: 'AMD Margin',
      type: 'line',
      data: [0.21, 0.24, 0.27],
    },
  ],
  meta: {
    chartValueType: 'percent',
    seriesPercentFormat: {
      'AMD Margin': 'decimal',
    },
  },
};

describe('withLightTheme formatter resiliency', () => {
  it('formats currency axis values when ECharts passes object payloads', () => {
    const themed = withLightTheme(sampleCurrencySpec);
    const formatter = themed.yAxis?.[0]?.axisLabel?.formatter as (value: any) => string;
    expect(typeof formatter).toBe('function');
    expect(formatter({ value: 15123000320 })).toBe('$15,123,000,320');
  });

  it('formats percent axis values when payload arrives as object', () => {
    const themed = withLightTheme(samplePercentSpec);
    const formatter = themed.yAxis?.[0]?.axisLabel?.formatter as (value: any) => string;
    expect(typeof formatter).toBe('function');
    expect(formatter({ value: 0.534 })).toBe('0.5%');
  });

  it('aligns legend entry colors with their matching series colors', () => {
    const paletteSpec = {
      title: { text: 'Margin Comparison' },
      tooltip: {},
      legend: { data: ['Company Operating Margin', 'Peer Avg Operating Margin'] },
      xAxis: {
        type: 'category',
        data: ['2023', '2024'],
      },
      series: [
        { name: 'Company Operating Margin', type: 'line', data: [0.21, 0.26] },
        { name: 'Peer Avg Operating Margin', type: 'line', data: [0.33, 0.35] },
      ],
      meta: {},
    };

    const themed = withLightTheme(paletteSpec as any);
    const themedLegend = Array.isArray(themed.legend) ? themed.legend[0] : themed.legend;
    const legendEntries: any[] = Array.isArray(themedLegend?.data) ? themedLegend.data : [];
    const seriesColors = Array.isArray(themed.series)
      ? themed.series.map((series: any) => series?.lineStyle?.color)
      : [];

    expect(seriesColors[0]).toBeDefined();
    expect(seriesColors[1]).toBeDefined();
    expect(seriesColors[0]).not.toBe(seriesColors[1]);

    const entryA = legendEntries.find((entry) => (entry?.name ?? entry) === 'Company Operating Margin') as any;
    const entryB = legendEntries.find((entry) => (entry?.name ?? entry) === 'Peer Avg Operating Margin') as any;

    expect(entryA).toBeTruthy();
    expect(entryB).toBeTruthy();
    expect(entryA.textStyle?.color).toBe(seriesColors[0]);
    expect(entryA.itemStyle?.color).toBe(seriesColors[0]);
    expect(entryB.textStyle?.color).toBe(seriesColors[1]);
    expect(entryB.itemStyle?.color).toBe(seriesColors[1]);
  });
});
