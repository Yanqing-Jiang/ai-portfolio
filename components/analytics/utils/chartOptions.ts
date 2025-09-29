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

export const isValidChartSpec = (spec: any) => {
  try {
    if (!spec || typeof spec !== 'object') return false;
    if (spec.series && !Array.isArray(spec.series)) return false;
    return true;
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