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
});
