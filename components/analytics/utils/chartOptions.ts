// Chart utilities for analytics components

const looksLikeChartSpec = (value: any) => {
  if (!value || typeof value !== 'object') return false;
  if (Array.isArray((value as any).series) && (value as any).series.length > 0) return true;
  if (Array.isArray((value as any).dataset) && (value as any).dataset.length > 0) return true;
  if ((value as any).xAxis || (value as any).yAxis || (value as any).tooltip || (value as any).legend) return true;
  if ((value as any).meta && typeof (value as any).meta === 'object') return true;
  return false;
};

export const resolveChartSpecOption = (payload: any): any | null => {
  if (!payload) return null;

  if (looksLikeChartSpec(payload)) {
    return payload;
  }

  if (payload && typeof payload === 'object') {
    if ((payload as any).chart_spec) {
      const nested = resolveChartSpecOption((payload as any).chart_spec);
      if (nested) return nested;
    }
    if ((payload as any).chart) {
      const nested = resolveChartSpecOption((payload as any).chart);
      if (nested) return nested;
    }
    if ((payload as any).data && (payload as any).data.chart_spec) {
      const nested = resolveChartSpecOption((payload as any).data.chart_spec);
      if (nested) return nested;
    }
  }

  return null;
};

const coerceNumeric = (value: any) => {
  if (typeof value === 'number' || value === null) {
    return value;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return value;
};

const normalizeSeriesNumericValues = (option: any) => {
  if (!option || !Array.isArray(option.series)) return option;
  option.series = option.series.map((series: any) => {
    if (!Array.isArray(series?.data)) {
      return series;
    }
    return {
      ...series,
      data: series.data.map(coerceNumeric),
    };
  });
  return option;
};

export const hydrateChartSpec = (spec: any) => {
  if (!spec || typeof spec !== 'object') return spec;
  const rawData = spec.meta?.rawData;
  const displayNames = spec.meta?.displayNames || {};
  const includedColumns = spec.meta?.includedColumns || Object.keys(displayNames || {});
  const baseClone = JSON.parse(JSON.stringify(spec));
  if (!Array.isArray(rawData) || rawData.length === 0 || !Array.isArray(spec.series)) {
    return normalizeSeriesNumericValues(baseClone);
  }

  const toLabel = (row: Record<string, any>) => {
    const year = row?.calendar_year ?? row?.fiscal_year ?? row?.year;
    const quarter = row?.calendar_quarter ?? row?.fiscal_quarter ?? row?.quarter;
    if (quarter && year) {
      return `${quarter} ${year}`;
    }
    if (year !== undefined && year !== null) {
      return `${year}`;
    }
    const month = row?.calendar_month ?? row?.month;
    if (year !== undefined && month) {
      try {
        const date = new Date(Date.UTC(Number(year), Number(month) - 1, 1));
        if (!Number.isNaN(date.valueOf())) {
          return date.toLocaleString('en-US', { month: 'short', year: 'numeric' });
        }
      } catch {
        /* ignore */
      }
    }
    const period = row?.period ?? row?.period_end_date ?? row?.date ?? row?.timestamp;
    if (period) {
      return String(period);
    }
    return 'Value';
  };

  const hydrated = baseClone;
  const labels = rawData.map(toLabel);

  if (Array.isArray(hydrated.xAxis)) {
    hydrated.xAxis = hydrated.xAxis.map((axis: any) => ({ ...(axis || {}), data: labels }));
  } else {
    hydrated.xAxis = { ...(hydrated.xAxis || {}), data: labels };
  }

  const displayToField = new Map<string, string>();
  Object.entries(displayNames || {}).forEach(([field, name]) => {
    if (name) {
      displayToField.set(String(name), field);
    }
  });

  hydrated.series = hydrated.series.map((series: any) => {
    const seriesName = String(series?.name ?? '');
    const field = series.meta?.field || displayToField.get(seriesName) || includedColumns.find((column: string) => {
      const normalized = column.replace(/_/g, ' ').toLowerCase();
      return seriesName.toLowerCase().includes(normalized);
    });

    if (!field) {
      return series;
    }

    const values = rawData.map((row: any) => {
      const value = row?.[field];
      if (typeof value === 'number' || value === null) {
        return value;
      }
      if (value === undefined) {
        return null;
      }
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    });

    return {
      ...series,
      data: values,
    };
  });

  return normalizeSeriesNumericValues(hydrated);
};
export const isValidChartSpec = (spec: any) => {
  try {
    const option = resolveChartSpecOption(spec) ?? (looksLikeChartSpec(spec) ? spec : null);
    if (!option || typeof option !== 'object') return false;
    if (option.series && !Array.isArray(option.series)) return false;
    const hasSeriesData = Array.isArray(option.series)
      ? option.series.some((series: any) => Array.isArray(series?.data) && series.data.some((value: any) => value !== null && value !== undefined))
      : false;
    const hasDataset = Array.isArray((option as any).dataset) ? (option as any).dataset.length > 0 : false;
    const hasDatasets = Array.isArray((option as any).datasets) ? (option as any).datasets.length > 0 : false;
    return hasSeriesData || hasDataset || hasDatasets;
  } catch {
    return false;
  }
};

export const withLightTheme = (spec: any) => {
  if (!spec || typeof spec !== 'object') return spec;
  const option: any = { ...spec };
  option.backgroundColor = '#ffffff';
  option.textStyle = { ...(spec.textStyle || {}), color: '#333333', fontFamily: 'Inter, ui-sans-serif, system-ui' };
  option.title = {
    ...(spec.title || {}),
    textStyle: { ...((spec.title || {}).textStyle || {}), color: '#111111', fontWeight: 700 },
  };
  option.legend = {
    ...(spec.legend || {}),
    textStyle: { ...((spec.legend || {}).textStyle || {}), color: '#333333' },
  };
  option.tooltip = {
    ...(spec.tooltip || {}),
    backgroundColor: '#ffffff',
    borderColor: '#dddddd',
    textStyle: { ...((spec.tooltip || {}).textStyle || {}), color: '#333333' },
  };
  option.animation = true;

  // Axis formatting: percent vs currency based on series meta, with heuristics fallback
  const percentSeries = new Set<string>(Object.entries((spec.meta?.seriesValueType || {}))
    .filter(([_, v]) => v === 'percent')
    .map(([k]) => k));
  const includedColumns: string[] = spec.meta?.includedColumns || spec.meta?.defaultColumns || [];
  const metaChartValueType = (spec.meta?.chartValueType || '').toLowerCase();
  const isPercentyName = (name: string) => {
    const n = (name || '').toLowerCase();
    return (
      n.includes('share') || n.includes('ratio') || n.includes('margin') ||
      n.includes('pct') || n.includes('percent') || n.includes('growth') || n.includes('qoq')
    );
  };
  const includedPercent = Array.isArray(includedColumns) && includedColumns.some(isPercentyName);
  const usesPercent = metaChartValueType === 'percent' || (percentSeries.size > 0) || includedPercent;

  const chartIsPercent = metaChartValueType === 'percent';
  const formatPercent = (v: any, seriesName?: string) => {
    const num = typeof v === 'number' ? v : Number(v);
    if (Number.isFinite(num)) {
      // Check if backend provided specific format info for this series
      const percentFormat = spec.meta?.seriesPercentFormat?.[seriesName || ''];
      
      if (percentFormat === 'pre_multiplied' || chartIsPercent) {
        // Value is already in 0-100 range (e.g., 53.4 for 53.4%)
        return `${num.toFixed(1)}%`;
      } else if (percentFormat === 'decimal') {
        // Value is in 0-1 range (e.g., 0.534 for 53.4%)
        return `${(num * 100).toFixed(1)}%`;
      } else {
        // Fallback: If value is already in percentage format (> 1), display as-is
        // If value is in decimal format (0-1), multiply by 100
        const percentValue = num > 1 ? num : num * 100;
        return `${percentValue.toFixed(1)}%`;
      }
    }
    return v;
  };
  const formatCurrency0 = (v: any) => {
    const num = typeof v === 'number' ? v : Number(v);
    if (Number.isFinite(num)) return `$${Math.round(num).toLocaleString()}`;
    return v;
  };

  const axisFormatter = (value: any) => {
    // Heuristic: if any series is percent, show percent; else currency
    return usesPercent ? formatPercent(value) : formatCurrency0(value);
  };

  const normalizeXAxis = (ax: any) => ({
    ...(ax || {}),
    axisLabel: { ...((ax || {}).axisLabel || {}), color: '#555555' },
    axisLine: {
      ...((ax || {}).axisLine || {}),
      lineStyle: { ...(((ax || {}).axisLine || {}).lineStyle || {}), color: '#cccccc' },
    },
    splitLine: {
      ...((ax || {}).splitLine || {}),
      show: false,
    },
    nameTextStyle: { ...((ax || {}).nameTextStyle || {}), color: '#333333' },
  });
  const normalizeYAxis = (ax: any) => ({
    ...(ax || {}),
    // Always use smart formatter unless backend explicitly sends a function
    axisLabel: {
      ...((ax || {}).axisLabel || {}),
      color: '#555555',
      formatter: (typeof (ax?.axisLabel?.formatter) === 'function') ? ax.axisLabel.formatter : axisFormatter,
    },
    axisLine: {
      ...((ax || {}).axisLine || {}),
      lineStyle: { ...(((ax || {}).axisLine || {}).lineStyle || {}), color: '#cccccc' },
    },
    splitLine: {
      ...((ax || {}).splitLine || {}),
      show: true,
      lineStyle: { ...(((ax || {}).splitLine || {}).lineStyle || {}), color: '#eeeeee' },
    },
    nameTextStyle: { ...((ax || {}).nameTextStyle || {}), color: '#333333' },
  });
  const xAxisArr = Array.isArray(spec.xAxis) ? spec.xAxis : spec.xAxis ? [spec.xAxis] : [];
  const yAxisArr = Array.isArray(spec.yAxis) ? spec.yAxis : spec.yAxis ? [spec.yAxis] : [];
  if (xAxisArr.length) option.xAxis = xAxisArr.map(normalizeXAxis);
  if (yAxisArr.length) option.yAxis = yAxisArr.map(normalizeYAxis);

  // Tooltip value formatting by series type
  option.tooltip.formatter = (params: any) => {
    const list = Array.isArray(params) ? params : [params];
    const name = list[0]?.axisValueLabel ?? list[0]?.name ?? '';
    const lines = [name];
    for (const p of list) {
      const isSingleSeries = Array.isArray(option.series) && option.series.length === 1;
      const isPercent = percentSeries.has(p.seriesName) || (includedPercent && isSingleSeries);
      const val = p.value;
      const formatted = isPercent ? formatPercent(val, p.seriesName) : formatCurrency0(val);
      lines.push(`${p.marker || ''} ${p.seriesName}: ${formatted}`);
    }
    return lines.join('<br/>');
  };
  // Enable data labels with smart positioning
  if (Array.isArray(option.series)) {
    option.series = option.series.map((s: any) => ({
      ...s,
      label: {
        show: true,
        position: 'top',
        color: '#444',
        formatter: (params: any) => {
          const isSingleSeries = Array.isArray(option.series) && option.series.length === 1;
          const isPercent = percentSeries.has(params.seriesName) || (includedPercent && isSingleSeries);
          return isPercent ? formatPercent(params.value, params.seriesName) : formatCurrency0(params.value);
        },
      },
      smooth: true,
      lineStyle: { ...(s.lineStyle || {}), width: 2 },
      symbol: 'circle',
      symbolSize: 6,
      areaStyle: s.type === 'line' ? { opacity: 0.06 } : undefined,
    }));
  }

  // Fallback: if legend.selected disables all series, auto-enable sensible defaults
  try {
    const legendObj = Array.isArray(option.legend) ? option.legend[0] : option.legend;
    if (legendObj) {
      const names: string[] = Array.isArray(legendObj.data) ? legendObj.data : [];
      const selectedMap: Record<string, boolean> = { ...(legendObj.selected || {}) };
      const hasSelectionKeys = Object.keys(selectedMap).length > 0;
      const allFalse = hasSelectionKeys && Object.values(selectedMap).every(v => v === false);
      if (!hasSelectionKeys || allFalse) {
        const defaults: string[] = (spec.meta?.defaultColumns || spec.meta?.includedColumns || []) as string[];
        const toTitle = (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, (m: string) => m.toUpperCase());
        const defaultTitles = new Set(defaults.map(toTitle));
        const nextSel: Record<string, boolean> = {};
        if (defaultTitles.size > 0) {
          for (const n of names) {
            const metric = n.includes(' - ') ? n.split(' - ', 2)[1] : n;
            nextSel[n] = defaultTitles.has(metric);
          }
        } else {
          // If no defaults, enable first few series to avoid empty chart
          for (let i = 0; i < names.length; i++) {
            nextSel[names[i]] = i < 6; // cap to keep chart readable
          }
        }
        if (Object.values(nextSel).some(v => v)) {
          if (Array.isArray(option.legend)) {
            option.legend[0] = { ...legendObj, selected: nextSel };
          } else {
            option.legend = { ...legendObj, selected: nextSel };
          }
        }
      }
    }
  } catch {
    // ignore fallback errors
  }

  return option;
};

export const buildMetricAwareOption = (spec: any, selectedMetric?: string) => {
  const option = withLightTheme(spec);
  
  if (selectedMetric && option.legend && option.legend.data) {
    const selectedMap: any = {};
    
    // Show all companies for the selected metric
    option.legend.data.forEach((name: string) => {
      selectedMap[name] = name.endsWith(' - ' + selectedMetric);
    });
    
    option.legend.selected = selectedMap;
  }
  
  return option;
};


// Agent-driven chart tool: high-level ops and reducer
export type ChartOp =
  | { op: 'set_chart_type'; value: 'line' | 'bar' | 'area' | 'candlestick' | 'stacked_area' | 'stacked_bar' }
  | { op: 'set_grouping'; grouping: 'ticker' | 'metric' }
  | { op: 'set_stack'; stack: boolean; mode?: 'normal' | 'percent' }
  | { op: 'select_metrics'; include?: string[] | 'ALL'; exclude?: string[] }
  | { op: 'filter_companies'; tickers: string[] }
  | { op: 'set_x_axis'; field: 'calendar_year' | 'calendar_quarter' | 'date' }
  | { op: 'set_y_axis_format'; valueType: 'percent' | 'currency'; percentFormat?: 'decimal' | 'pre_multiplied' }
  | { op: 'set_palette'; palette: string[] }
  | { op: 'set_axis_scale'; axis: 'x' | 'y' | 0 | 1; scale: 'linear' | 'log' }
  | { op: 'toggle_series'; names: string[]; visible: boolean };

export interface ChartPatch { ops: ChartOp[]; reason?: string; chart_id?: string }

export function applyChartOps(base: any, patch: ChartPatch): any {
  if (!base || typeof base !== 'object' || !patch || !Array.isArray(patch.ops)) {
    return base;
  }
  const option: any = JSON.parse(JSON.stringify(base));

  const ensureLegend = () => {
    option.legend = option.legend || {};
    if (Array.isArray(option.legend)) {
      // Normalize first legend object if array form used
      option.legend = option.legend[0] || {};
    }
  };

  for (const p of patch.ops) {
    switch (p.op) {
      case 'set_chart_type': {
        const isStacked = p.value === 'stacked_area' || p.value === 'stacked_bar';
        const type = p.value.includes('bar') ? 'bar' : p.value.includes('area') ? 'line' : p.value; // area => line + areaStyle
        option.series = (option.series || []).map((s: any) => ({
          ...s,
          type,
          areaStyle: p.value === 'area' || p.value === 'stacked_area' ? { opacity: 0.2 } : undefined,
          stack: isStacked ? 'total' : undefined,
        }));
        option.meta = option.meta || {};
        option.meta.chartDesign = { ...(option.meta.chartDesign || {}), chart_type: p.value };
        break;
      }
      case 'set_stack': {
        const stack = p.stack ? 'total' : undefined;
        option.series = (option.series || []).map((s: any) => ({ ...s, stack }));
        if (p.mode === 'percent') {
          option.meta = option.meta || {};
          option.meta.chartValueType = 'percent';
        }
        break;
      }
      case 'toggle_series': {
        ensureLegend();
        const selected = { ...(option.legend.selected || {}) } as Record<string, boolean>;
        for (const name of p.names) selected[name] = p.visible;
        option.legend.selected = selected;
        break;
      }
      case 'set_y_axis_format': {
        option.meta = option.meta || {};
        option.meta.chartValueType = p.valueType;
        // Preserve any per-series overrides in meta.seriesPercentFormat
        option.meta.seriesPercentFormat = option.meta.seriesPercentFormat || {};
        break;
      }
      case 'set_x_axis': {
        const arr = Array.isArray(option.xAxis) ? option.xAxis : option.xAxis ? [option.xAxis] : [];
        option.xAxis = arr.map((ax: any) => ({ ...ax, name: p.field }));
        option.meta = option.meta || {};
        option.meta.chartDesign = { ...(option.meta.chartDesign || {}), x_field: p.field };
        break;
      }
      case 'filter_companies': {
        ensureLegend();
        const selected = { ...(option.legend.selected || {}) } as Record<string, boolean>;
        const whitelist = new Set((p.tickers || []).map(t => String(t).toUpperCase()));
        for (const s of option.series || []) {
          const name: string = s.name || '';
          const prefix = name.includes(' - ') ? name.split(' - ', 1)[0] : name;
          selected[name] = whitelist.size ? whitelist.has(prefix.toUpperCase()) : true;
        }
        option.legend.selected = selected;
        break;
      }
      case 'set_palette': {
        const palette = Array.isArray(p.palette) ? p.palette : [];
        if (palette.length) {
          option.color = palette.slice();
        }
        break;
      }
      case 'set_axis_scale': {
        const normalize = (ax: any) => ({
          ...(ax || {}),
          type: p.scale === 'log' ? 'log' : 'value',
        });
        if (p.axis === 'x') {
          const arr = Array.isArray(option.xAxis) ? option.xAxis : option.xAxis ? [option.xAxis] : [];
          option.xAxis = arr.map(normalize);
        } else {
          const arr = Array.isArray(option.yAxis) ? option.yAxis : option.yAxis ? [option.yAxis] : [];
          option.yAxis = arr.map(normalize);
        }
        break;
      }
      case 'select_metrics': {
        // Best-effort: toggle series by metric suffix (" - <Metric>")
        ensureLegend();
        const selected = { ...(option.legend.selected || {}) } as Record<string, boolean>;
        const includeAll = p.include === 'ALL';
        const include = new Set((Array.isArray(p.include) ? p.include : []) as string[]);
        const exclude = new Set((Array.isArray(p.exclude) ? p.exclude : []) as string[]);
        for (const s of option.series || []) {
          const name: string = s.name || '';
          const metric = name.includes(' - ') ? name.split(' - ', 2)[1] : name;
          if (includeAll) {
            selected[name] = !exclude.has(metric);
          } else if (include.size) {
            selected[name] = include.has(metric) && !exclude.has(metric);
          }
        }
        option.legend.selected = selected;
        break;
      }
      case 'set_grouping': {
        option.meta = option.meta || {};
        option.meta.groupingType = p.grouping;
        break;
      }
      default:
        // no-op for unknown ops
        break;
    }
  }
  return option;
}


