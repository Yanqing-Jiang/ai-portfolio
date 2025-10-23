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

const parseNumericString = (input: string): number | null => {
  const trimmed = input.trim();
  if (!trimmed) {
    return null;
  }
  const sanitized = trimmed.replace(/,/g, '');
  const parsed = Number(sanitized);
  return Number.isFinite(parsed) ? parsed : null;
};

const extractNumericCandidate = (value: any, seen: Set<any> = new Set()): number | null => {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === 'string') {
    return parseNumericString(value);
  }
  if (typeof value !== 'object') {
    return null;
  }
  if (seen.has(value)) {
    return null;
  }
  seen.add(value);
  if (Array.isArray(value)) {
    for (const entry of value) {
      const candidate = extractNumericCandidate(entry, seen);
      if (candidate !== null) {
        return candidate;
      }
    }
    return null;
  }
  const numericKeys = ['value', 'raw', 'amount', 'numeric', 'number'];
  for (const key of numericKeys) {
    if (Object.prototype.hasOwnProperty.call(value, key)) {
      const candidate = extractNumericCandidate((value as any)[key], seen);
      if (candidate !== null) {
        return candidate;
      }
    }
  }
  return null;
};

const flattenRowForDataset = (row: Record<string, any>) => {
  const flattened: Record<string, any> = {};
  Object.entries(row || {}).forEach(([key, value]) => {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      const numeric = extractNumericCandidate(value);
      if (numeric !== null) {
        flattened[key] = numeric;
      } else {
        flattened[key] = value;
      }
      const formatted =
        (value as any).formatted ?? (value as any).display ?? (value as any).text ?? (value as any).label;
      if (formatted !== undefined && formatted !== null && formatted !== '') {
        flattened[`${key}__display`] = String(formatted);
      }
    } else {
      flattened[key] = value;
    }
  });
  return flattened;
};

const looksLikePercentMetric = (rawName: string | undefined) => {
  if (!rawName) {
    return false;
  }
  const name = rawName.toLowerCase();
  return (
    name.includes('percent') ||
    name.includes('pct') ||
    name.includes('%') ||
    name.includes('margin') ||
    name.includes('growth') ||
    name.includes('ratio') ||
    name.includes('share') ||
    name.includes('yield')
  );
};

const normalizePercentSeriesData = (option: any, spec: any) => {
  if (!option || !Array.isArray(option.series) || !spec || typeof spec !== 'object') {
    return option;
  }

  const seriesValueType: Record<string, string> = spec.meta?.seriesValueType || {};
  const percentFormatMeta: Record<string, string> = spec.meta?.seriesPercentFormat || {};

  const ensurePercentFormatMeta = (seriesName: string) => {
    option.meta = option.meta || {};
    option.meta.seriesPercentFormat = option.meta.seriesPercentFormat || {};
    option.meta.seriesPercentFormat[seriesName] = 'pre_multiplied';
  };

  option.series = option.series.map((series: any) => {
    const seriesName: string = series?.name ?? '';
    if (!Array.isArray(series?.data)) {
      return series;
    }

    const numericValues = series.data.filter((value: any) => typeof value === 'number' && Number.isFinite(value));
    if (!numericValues.length) {
      return series;
    }

    const declaredPercent = seriesValueType[seriesName] === 'percent';
    const requestedDecimalFormat = percentFormatMeta[seriesName] === 'decimal';
    const heuristicPercent = looksLikePercentMetric(seriesName);

    if (!declaredPercent && !requestedDecimalFormat && !heuristicPercent) {
      return series;
    }

    const hasMagnitude = numericValues.some((value: number) => Math.abs(value) > 0);
    const allWithinDecimalRange = numericValues.every((value: number) => Math.abs(value) <= 1.05);

    if (!hasMagnitude || !allWithinDecimalRange) {
      return series;
    }

    const scaledData = series.data.map((value: any) => {
      if (typeof value !== 'number' || !Number.isFinite(value)) {
        return value;
      }
      return value * 100;
    });

    ensurePercentFormatMeta(seriesName);

    return {
      ...series,
      data: scaledData,
    };
  });

  return option;
};

const normalizeSeriesName = (rawName?: string) => {
  if (!rawName || typeof rawName !== 'string') {
    return '';
  }
  return rawName
    .toLowerCase()
    .replace(/\b(percent|percentage|pct|%|basis points|bps)\b/g, '')
    .replace(/\s+/g, ' ')
    .trim();
};

const dedupePercentShadowSeries = (option: any) => {
  if (!option || !Array.isArray(option.series)) {
    return option;
  }

  const EPSILON = 1e-9;

  type SeriesInfo = {
    index: number;
    name: string;
    normalizedName: string;
    values: Array<number | null>;
    magnitude: number;
  };

  const seriesInfo: SeriesInfo[] = option.series.map((series: any, index: number) => {
    const name = typeof series?.name === 'string' ? series.name : `Series ${index + 1}`;
    const rawValues = Array.isArray(series?.data) ? series.data : [];
    const values = rawValues.map((value: any) =>
      typeof value === 'number' && Number.isFinite(value) ? value : null,
    );
    const numeric = values.filter((value): value is number => value !== null);
    const magnitude =
      numeric.length > 0 ? numeric.reduce((acc, value) => acc + Math.abs(value), 0) / numeric.length : 0;

    return {
      index,
      name,
      normalizedName: normalizeSeriesName(name),
      values,
      magnitude,
    };
  });

  const toDrop = new Set<number>();
  const preferSelectedNames = new Set<string>();

  const scaledWithinTolerance = (pairs: Array<[number, number]>, scale: number) =>
    pairs.every(([a, b]) => Math.abs(a - b * scale) <= Math.max(0.75, Math.abs(b * scale) * 0.06));

  for (let i = 0; i < seriesInfo.length; i += 1) {
    const left = seriesInfo[i];
    if (!left.values.length || toDrop.has(left.index) || !left.normalizedName) continue;

    for (let j = i + 1; j < seriesInfo.length; j += 1) {
      const right = seriesInfo[j];
      if (!right.values.length || toDrop.has(right.index) || !right.normalizedName) continue;
      if (left.normalizedName !== right.normalizedName) continue;

      const pairs: Array<[number, number]> = [];
      const maxLength = Math.max(left.values.length, right.values.length);
      for (let k = 0; k < maxLength; k += 1) {
        const a = left.values[k] ?? null;
        const b = right.values[k] ?? null;
        if (a === null || b === null) continue;
        pairs.push([a, b]);
      }

      if (pairs.length < 2) continue;

      let ratioSum = 0;
      let inverseSum = 0;
      let ratioCount = 0;
      let consistent = true;

      for (const [a, b] of pairs) {
        if (Math.abs(a) < EPSILON && Math.abs(b) < EPSILON) {
          continue;
        }
        if (Math.abs(a) < EPSILON || Math.abs(b) < EPSILON) {
          consistent = false;
          break;
        }
        ratioSum += a / b;
        inverseSum += b / a;
        ratioCount += 1;
      }

      if (!consistent || ratioCount === 0) continue;

      const avgRatio = ratioSum / ratioCount;
      const avgInverse = inverseSum / ratioCount;
      const ratioCloseToHundred = Math.abs(avgRatio - 100) <= 8;
      const inverseCloseToHundred = Math.abs(avgInverse - 100) <= 8;

      const nameHasPercentLeft = /percent|pct|%/i.test(left.name);
      const nameHasPercentRight = /percent|pct|%/i.test(right.name);
      const identicalWithinTolerance = scaledWithinTolerance(pairs, 1);

      if (!ratioCloseToHundred && !inverseCloseToHundred) {
        if (!identicalWithinTolerance) {
          continue;
        }
        if (nameHasPercentLeft === nameHasPercentRight) {
          continue;
        }
        const dropIndex = nameHasPercentLeft ? left.index : right.index;
        const keepName = nameHasPercentLeft ? right.name : left.name;
        toDrop.add(dropIndex);
        if (keepName) {
          preferSelectedNames.add(keepName);
        }
        continue;
      }

      const larger = left.magnitude >= right.magnitude ? left : right;
      const smaller = larger === left ? right : left;

      if (larger.magnitude <= 1.05 || smaller.magnitude > 1.5) {
        continue;
      }

      const referenceScale = ratioCloseToHundred ? avgRatio : avgInverse;
      const validationPairs = ratioCloseToHundred ? pairs : pairs.map(([a, b]) => [b, a] as [number, number]);

      if (!scaledWithinTolerance(validationPairs, referenceScale)) {
        continue;
      }

      if (nameHasPercentLeft !== nameHasPercentRight) {
        const dropIndex = nameHasPercentLeft ? left.index : right.index;
        const keepName = nameHasPercentLeft ? right.name : left.name;
        toDrop.add(dropIndex);
        if (keepName) {
          preferSelectedNames.add(keepName);
        }
      } else {
        toDrop.add(smaller.index);
      }
    }
  }

  if (!toDrop.size) {
    return option;
  }

  option.series = option.series.filter((_: any, index: number) => !toDrop.has(index));

  const keptNames = option.series
    .map((series: any) => (typeof series?.name === 'string' ? series.name : null))
    .filter((name: string | null): name is string => Boolean(name));
  const keptNameSet = new Set(keptNames);

  const filterLegendEntry = (entry: any) => {
    if (!entry || typeof entry !== 'object') return entry;
    const next = { ...entry };
    if (Array.isArray(next.data)) {
      next.data = next.data.filter((name: string) => keptNameSet.has(name));
    }
    if (next.selected && typeof next.selected === 'object') {
      const nextSelected: Record<string, boolean> = {};
      Object.entries(next.selected).forEach(([key, value]) => {
        if (keptNameSet.has(key)) {
          nextSelected[key] = Boolean(value);
        }
      });
      next.selected = Object.fromEntries(
        Object.entries(nextSelected).map(([key, value]) => [
          key,
          preferSelectedNames.has(key) ? true : Boolean(value),
        ]),
      );
      preferSelectedNames.forEach((name) => {
        if (!next.selected.hasOwnProperty(name)) {
          next.selected[name] = true;
        }
      });
    }
    return next;
  };

  if (option.legend) {
    if (Array.isArray(option.legend)) {
      option.legend = option.legend.map(filterLegendEntry);
    } else {
      option.legend = filterLegendEntry(option.legend);
    }
  }

  if (option.meta) {
    const percentFormat = option.meta.seriesPercentFormat;
    if (percentFormat && typeof percentFormat === 'object') {
      const nextPercentFormat: Record<string, string> = {};
      Object.entries(percentFormat).forEach(([key, value]) => {
        if (keptNameSet.has(key)) {
          nextPercentFormat[key] = value;
        }
      });
      option.meta.seriesPercentFormat = nextPercentFormat;
    }
    const valueType = option.meta.seriesValueType;
    if (valueType && typeof valueType === 'object') {
      const nextValueType: Record<string, string> = {};
      Object.entries(valueType).forEach(([key, value]) => {
        if (keptNameSet.has(key)) {
          nextValueType[key] = value;
        }
      });
      option.meta.seriesValueType = nextValueType;
    }
  }

  return option;
};

const parseYear = (value: any): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const match = trimmed.match(/(\d{4})/);
    if (match) {
      return Number(match[1]);
    }
    const numeric = Number(trimmed);
    if (Number.isFinite(numeric)) {
      return Math.trunc(numeric);
    }
  }
  return null;
};

const parseQuarter = (value: any): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  if (typeof value === 'string') {
    const trimmed = value.trim().toLowerCase();
    if (!trimmed) return null;
    const mapping: Record<string, number> = { q1: 1, q2: 2, q3: 3, q4: 4 };
    if (mapping[trimmed] !== undefined) {
      return mapping[trimmed];
    }
    const match = trimmed.match(/q?\s*([1-4])/);
    if (match) {
      return Number(match[1]);
    }
    const numeric = Number(trimmed);
    if (Number.isFinite(numeric)) {
      return Math.trunc(numeric);
    }
  }
  return null;
};

const parseMonth = (value: any): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    const month = Math.trunc(value);
    return month >= 1 && month <= 12 ? month : null;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const numeric = Number(trimmed);
    if (Number.isFinite(numeric)) {
      const month = Math.trunc(numeric);
      return month >= 1 && month <= 12 ? month : null;
    }
  }
  return null;
};

const parseTimestamp = (value: any): number | null => {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.getTime();
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const parsed = Date.parse(trimmed);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return null;
};

const compareNullableNumbers = (a: number | null, b: number | null) => {
  if (a != null && b != null) {
    if (a === b) return 0;
    return a < b ? -1 : 1;
  }
  if (a != null) return -1;
  if (b != null) return 1;
  return 0;
};

const sortRawDataChronologically = (rawData: any[]): any[] => {
  return rawData
    .map((row, index) => {
      const year = parseYear(row?.calendar_year ?? row?.fiscal_year ?? row?.year);
      const quarter = parseQuarter(row?.calendar_quarter ?? row?.fiscal_quarter ?? row?.quarter);
      const month = parseMonth(row?.calendar_month ?? row?.month);
      const timestamp = parseTimestamp(
        row?.period ?? row?.period_end_date ?? row?.period_start_date ?? row?.date ?? row?.timestamp ?? row?.as_of ?? row?.reported_at,
      );
      return {
        row,
        key: { year, quarter, month, timestamp, index },
      };
    })
    .sort((a, b) => {
      const { year: yearA, quarter: quarterA, month: monthA, timestamp: tsA, index: indexA } = a.key;
      const { year: yearB, quarter: quarterB, month: monthB, timestamp: tsB, index: indexB } = b.key;

      let cmp = compareNullableNumbers(yearA, yearB);
      if (cmp !== 0) return cmp;

      cmp = compareNullableNumbers(quarterA, quarterB);
      if (cmp !== 0) return cmp;

      cmp = compareNullableNumbers(monthA, monthB);
      if (cmp !== 0) return cmp;

      cmp = compareNullableNumbers(tsA, tsB);
      if (cmp !== 0) return cmp;

      return indexA - indexB;
    })
    .map((entry) => entry.row);
};

export const hydrateChartSpec = (spec: any) => {
  if (!spec || typeof spec !== 'object') return spec;
  const rawData = spec.meta?.rawData;
  const displayNames = spec.meta?.displayNames || {};
  const includedColumns = spec.meta?.includedColumns || Object.keys(displayNames || {});
  const baseClone = JSON.parse(JSON.stringify(spec));
  if (!Array.isArray(rawData) || rawData.length === 0 || !Array.isArray(spec.series)) {
    return dedupePercentShadowSeries(normalizePercentSeriesData(normalizeSeriesNumericValues(baseClone), spec));
  }

  const sortedRawData = sortRawDataChronologically(rawData);
  const flattenedRawData = sortedRawData.map((row: Record<string, any>) => flattenRowForDataset(row));

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
  if (hydrated.meta && typeof hydrated.meta === 'object') {
    hydrated.meta.rawData = sortedRawData.map((row: any) => ({ ...row }));
  }
  const labels = Array.from(new Set(sortedRawData.map(toLabel)));

  if (Array.isArray(hydrated.xAxis)) {
    hydrated.xAxis = hydrated.xAxis.map((axis: any) => ({ ...(axis || {}), data: labels }));
  } else {
    hydrated.xAxis = { ...(hydrated.xAxis || {}), data: labels };
  }

  const categoryDimensionKey = '__label';
  const groupingCandidates: Array<string | undefined> = [];
  if (typeof spec.meta?.grouping === 'string' && spec.meta.grouping.trim().length) {
    groupingCandidates.push(spec.meta.grouping.trim());
  }
  groupingCandidates.push('ticker', 'company');
  const firstRow = flattenedRawData[0] ?? {};
  const splitKey = groupingCandidates.find((candidate) => candidate && Object.prototype.hasOwnProperty.call(firstRow, candidate));

  const valueIgnoreKeys = new Set<string>([
    categoryDimensionKey,
    splitKey ?? '',
    'calendar_year',
    'fiscal_year',
    'calendar_quarter',
    'fiscal_quarter',
    'calendar_month',
    'month',
    'year',
    'quarter',
    'timestamp',
    'date',
    'period',
    'period_end_date',
    'metric',
    'label',
  ]);

  const numericFieldCandidates = Object.keys(firstRow).filter((key) => {
    if (!key || valueIgnoreKeys.has(key) || key.endsWith('__display')) return false;
    const sample = flattenedRawData.find((row: any) => row?.[key] !== null && row?.[key] !== undefined);
    if (!sample) return false;
    const candidateValue = sample[key];
    return typeof candidateValue === 'number' && Number.isFinite(candidateValue);
  });
  const valueKey = numericFieldCandidates[0];

  let datasetApplied = false;
  if (splitKey && valueKey) {
    const datasetSource = flattenedRawData.map((row: any, index: number) => ({
      ...row,
      [categoryDimensionKey]: toLabel(sortedRawData[index]),
    }));
    const datasetEntry = {
      dimensions: Array.from(new Set([categoryDimensionKey, splitKey, valueKey])),
      source: datasetSource,
    };
    const existingDataset = Array.isArray(hydrated.dataset) ? [...hydrated.dataset] : [];
    const datasetIndex = existingDataset.length;
    existingDataset.push(datasetEntry);
    hydrated.dataset = existingDataset;
    hydrated.series = (hydrated.series || []).map((series: any) => {
      const next = { ...series };
      if (next.data !== undefined) {
        delete next.data;
      }
      next.encode = {
        x: categoryDimensionKey,
        y: valueKey,
        seriesName: splitKey,
        itemName: categoryDimensionKey,
      };
      next.datasetIndex = datasetIndex;
      return next;
    });
    datasetApplied = true;
  }

  if (!datasetApplied) {
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

      const values = flattenedRawData.map((row: any) => {
        const value = row?.[field];
        if (typeof value === 'number' || value === null) {
          return value;
        }
        if (value === undefined) {
          return null;
        }
        const parsed = coerceNumeric(value);
        return typeof parsed === 'number' && Number.isFinite(parsed) ? parsed : null;
      });

      return {
        ...series,
        data: values,
      };
    });
  }

  return dedupePercentShadowSeries(normalizePercentSeriesData(normalizeSeriesNumericValues(hydrated), spec));
};
export const isValidChartSpec = (spec: any) => {
  try {
    const option = resolveChartSpecOption(spec) ?? (looksLikeChartSpec(spec) ? spec : null);
    if (!option || typeof option !== 'object') return false;
    if (option.series && !Array.isArray(option.series)) return false;

    const hydrated = hydrateChartSpec(option);
    const target = hydrated ?? option;

    const hasSeriesData = Array.isArray(target.series)
      ? target.series.some(
          (series: any) =>
            Array.isArray(series?.data) &&
            series.data.some((value: any) => value !== null && value !== undefined),
        )
      : false;

    const hasDataset = Array.isArray((target as any).dataset) ? (target as any).dataset.length > 0 : false;
    const hasDatasets = Array.isArray((target as any).datasets) ? (target as any).datasets.length > 0 : false;
    const hasRawData = Array.isArray(option?.meta?.rawData) ? option.meta.rawData.length > 0 : false;

    return hasSeriesData || hasDataset || hasDatasets || hasRawData;
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


