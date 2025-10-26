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

const DEFAULT_CHART_PALETTE = [
  '#2563EB',
  '#0EA5E9',
  '#6366F1',
  '#F97316',
  '#10B981',
  '#EC4899',
  '#F59E0B',
  '#14B8A6',
  '#F43F5E',
  '#8B5CF6',
  '#22C55E',
  '#D946EF',
];

const hslToHex = (h: number, s: number, l: number): string => {
  const normalizedS = Math.max(0, Math.min(100, s)) / 100;
  const normalizedL = Math.max(0, Math.min(100, l)) / 100;
  const chroma = (1 - Math.abs(2 * normalizedL - 1)) * normalizedS;
  const huePrime = ((h % 360) + 360) % 360 / 60;
  const x = chroma * (1 - Math.abs((huePrime % 2) - 1));

  let r1 = 0;
  let g1 = 0;
  let b1 = 0;
  if (huePrime >= 0 && huePrime < 1) {
    r1 = chroma;
    g1 = x;
  } else if (huePrime >= 1 && huePrime < 2) {
    r1 = x;
    g1 = chroma;
  } else if (huePrime >= 2 && huePrime < 3) {
    g1 = chroma;
    b1 = x;
  } else if (huePrime >= 3 && huePrime < 4) {
    g1 = x;
    b1 = chroma;
  } else if (huePrime >= 4 && huePrime < 5) {
    r1 = x;
    b1 = chroma;
  } else if (huePrime >= 5 && huePrime < 6) {
    r1 = chroma;
    b1 = x;
  }

  const match = normalizedL - chroma / 2;
  const r = Math.round((r1 + match) * 255);
  const g = Math.round((g1 + match) * 255);
  const b = Math.round((b1 + match) * 255);

  const toHex = (value: number) => value.toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
};

const colorFromString = (input: string): string => {
  const seed = input && input.trim().length ? input : 'series';
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash << 5) - hash + seed.charCodeAt(i);
    hash |= 0;
  }
  const hue = Math.abs(hash) % 360;
  return hslToHex(hue, 68, 55);
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

const extractDisplayCandidate = (value: any, seen: Set<any> = new Set()): any => {
  if (!value || typeof value !== 'object') {
    return undefined;
  }
  if (seen.has(value)) {
    return undefined;
  }
  seen.add(value);

  if (value instanceof Date) {
    return value.toISOString();
  }

  if (Array.isArray(value)) {
    for (const entry of value) {
      const candidate = extractDisplayCandidate(entry, seen);
      if (candidate !== undefined && candidate !== null && candidate !== '') {
        return candidate;
      }
    }
    return undefined;
  }

  const candidateKeys = [
    'formatted',
    'display',
    'text',
    'label',
    'name',
    'title',
    'value',
    'raw',
    'string',
  ];

  for (const key of candidateKeys) {
    if (Object.prototype.hasOwnProperty.call(value, key)) {
      const candidate = (value as any)[key];
      if (candidate !== undefined && candidate !== null && candidate !== '') {
        return candidate;
      }
    }
  }

  const primitiveKeys = Object.keys(value);
  if (primitiveKeys.length === 1) {
    const candidate = (value as any)[primitiveKeys[0]];
    if (candidate !== undefined && candidate !== null && candidate !== '') {
      return candidate;
    }
  }

  return undefined;
};

const toDisplayString = (value: any): string => {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'object') {
    const numeric = extractNumericCandidate(value);
    if (numeric !== null) {
      return String(numeric);
    }
    const candidate = extractDisplayCandidate(value);
    if (candidate !== undefined && candidate !== null && candidate !== '') {
      return toDisplayString(candidate);
    }
    if (value instanceof Date) {
      return value.toISOString();
    }
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  return String(value);
};

const applyAlphaToColor = (color: any, alpha: number): string => {
  const safeAlpha = Number.isFinite(alpha) ? Math.min(Math.max(alpha, 0), 1) : 1;
  if (typeof color !== 'string' || !color.trim()) {
    return `rgba(34, 197, 94, ${safeAlpha})`;
  }
  const trimmed = color.trim();
  const hexMatch = /^#([0-9a-f]{6})$/i.exec(trimmed);
  if (hexMatch) {
    const hex = parseInt(hexMatch[1], 16);
    const r = (hex >> 16) & 255;
    const g = (hex >> 8) & 255;
    const b = hex & 255;
    return `rgba(${r}, ${g}, ${b}, ${safeAlpha})`;
  }
  if (trimmed.startsWith('rgb(')) {
    return trimmed.replace(/^rgb\(([^)]+)\)$/i, (_m, components) => `rgba(${components}, ${safeAlpha})`);
  }
  if (trimmed.startsWith('rgba(')) {
    return trimmed.replace(/rgba\(([^,]+),([^,]+),([^,]+),[^)]+\)/i, (_m, r, g, b) => `rgba(${r}, ${g}, ${b}, ${safeAlpha})`);
  }
  return trimmed;
};

const resolveTemporalComponent = (value: any): string | number | null => {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === 'object') {
    const numeric = extractNumericCandidate(value);
    if (numeric !== null) {
      return numeric;
    }
    const candidate = extractDisplayCandidate(value);
    if (candidate !== undefined && candidate !== null && candidate !== '') {
      return resolveTemporalComponent(candidate);
    }
    if (value instanceof Date) {
      return value.toISOString();
    }
    return toDisplayString(value);
  }
  return value;
};

const flattenRowForDataset = (row: Record<string, any>) => {
  const flattened: Record<string, any> = {};
  Object.entries(row || {}).forEach(([key, value]) => {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      const numeric = extractNumericCandidate(value);
      if (numeric !== null) {
        flattened[key] = numeric;
      } else {
        const displayValue = extractDisplayCandidate(value);
        if (displayValue !== undefined && displayValue !== null && displayValue !== '') {
          if (typeof displayValue === 'object') {
            flattened[key] = toDisplayString(displayValue);
          } else {
            flattened[key] = displayValue;
          }
        } else {
          flattened[key] = toDisplayString(value);
        }
      }
      const formatted =
        (value as any).formatted ??
        (value as any).display ??
        (value as any).text ??
        (value as any).label ??
        extractDisplayCandidate(value);
      if (formatted !== undefined && formatted !== null && formatted !== '') {
        flattened[`${key}__display`] = toDisplayString(formatted);
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
    const ordinalMap: Record<string, number> = {
      first: 1,
      '1st': 1,
      second: 2,
      '2nd': 2,
      third: 3,
      '3rd': 3,
      fourth: 4,
      '4th': 4,
    };
    if (ordinalMap[trimmed] !== undefined) {
      return ordinalMap[trimmed];
    }
    const ordinalMatch = trimmed.match(/(first|second|third|fourth)/);
    if (ordinalMatch && ordinalMap[ordinalMatch[1]]) {
      return ordinalMap[ordinalMatch[1]];
    }
    const suffixMatch = trimmed.match(/([1-4])(st|nd|rd|th)?\s*quarter/);
    if (suffixMatch) {
      return Number(suffixMatch[1]);
    }
    const wordQuarterMatch = trimmed.match(/quarter\s*([1-4])/);
    if (wordQuarterMatch) {
      return Number(wordQuarterMatch[1]);
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
      const quarterValue =
        row?.calendar_quarter ??
        row?.calendar_quarter_num ??
        row?.fiscal_quarter ??
        row?.fiscal_quarter_num ??
        row?.quarter ??
        row?.quarter_num ??
        row?.quarter_number;
      const quarter = parseQuarter(quarterValue);
      const month = parseMonth(row?.calendar_month ?? row?.month ?? row?.calendar_month_num ?? row?.month_num);
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
  const requestedGranularityValue =
    (spec.meta?.requestedGranularity ??
      spec.meta?.granularity ??
      (typeof spec.meta?.timeframe === 'object' ? (spec.meta?.timeframe as any)?.granularity : undefined)) ||
    null;
  const preferQuarterly =
    typeof requestedGranularityValue === 'string' &&
    requestedGranularityValue.toLowerCase() === 'quarterly';
  if (!Array.isArray(rawData) || rawData.length === 0 || !Array.isArray(spec.series)) {
    return dedupePercentShadowSeries(normalizePercentSeriesData(normalizeSeriesNumericValues(baseClone), spec));
  }

  const sortedRawData = sortRawDataChronologically(rawData);
  const flattenedRawData = sortedRawData.map((row: Record<string, any>) => flattenRowForDataset(row));

  const toLabel = (row: Record<string, any>) => {
    const yearRaw = row?.calendar_year ?? row?.fiscal_year ?? row?.year;
    const quarterCandidates = [
      row?.calendar_quarter,
      row?.calendar_quarter_num,
      row?.fiscal_quarter,
      row?.fiscal_quarter_num,
      row?.quarter,
      row?.quarter_num,
      row?.quarter_number,
    ];
    const monthRaw = row?.calendar_month ?? row?.month ?? row?.calendar_month_num ?? row?.month_num;
    const periodRaw = row?.period ?? row?.period_end_date ?? row?.period_start_date ?? row?.date ?? row?.timestamp;

    const parsedYear = parseYear(yearRaw);
    let yearLabel = parsedYear !== null ? String(parsedYear) : undefined;
    if (!yearLabel) {
      const yearResolved = resolveTemporalComponent(yearRaw);
      if (yearResolved !== undefined && yearResolved !== null && `${yearResolved}`.trim()) {
        yearLabel = String(yearResolved).trim();
      }
    }

    let quarterNumber: number | null = null;
    for (const candidate of quarterCandidates) {
      const parsed = parseQuarter(candidate);
      if (parsed !== null) {
        quarterNumber = parsed;
        break;
      }
    }

    if (!quarterNumber && preferQuarterly) {
      const monthNumber = parseMonth(monthRaw);
      if (monthNumber) {
        quarterNumber = Math.floor((monthNumber - 1) / 3) + 1;
      }
    }

    if (!quarterNumber && preferQuarterly) {
      const timestampMs = parseTimestamp(periodRaw);
      if (timestampMs !== null) {
        const date = new Date(timestampMs);
        if (!Number.isNaN(date.valueOf())) {
          quarterNumber = Math.floor(date.getUTCMonth() / 3) + 1;
          if (!yearLabel) {
            yearLabel = String(date.getUTCFullYear());
          }
        }
      }
    }

    if (!quarterNumber && preferQuarterly) {
      const periodQuarter = parseQuarter(resolveTemporalComponent(periodRaw));
      if (periodQuarter !== null) {
        quarterNumber = periodQuarter;
      }
    }

    if (quarterNumber && quarterNumber >= 1 && quarterNumber <= 4) {
      return yearLabel ? `Q${quarterNumber} ${yearLabel}` : `Q${quarterNumber}`;
    }

    const monthResolved = resolveTemporalComponent(monthRaw);
    if (yearLabel && monthResolved) {
      const monthNumber = parseMonth(monthResolved);
      const numericYear = parseYear(yearLabel);
      if (monthNumber && numericYear !== null) {
        try {
          const date = new Date(Date.UTC(numericYear, monthNumber - 1, 1));
          if (!Number.isNaN(date.valueOf())) {
            return date.toLocaleString('en-US', { month: 'short', year: 'numeric' });
          }
        } catch {
          /* ignore */
        }
      }
    }

    if (yearLabel) {
      return yearLabel;
    }

    const periodResolved = resolveTemporalComponent(periodRaw);
    if (periodResolved) {
      return String(periodResolved);
    }
    return 'Value';
  };

  const hydrated = baseClone;
  if (hydrated.meta && typeof hydrated.meta === 'object') {
    hydrated.meta.rawData = sortedRawData.map((row: any) => ({ ...row }));
  }
  const labels = Array.from(new Set(sortedRawData.map(toLabel))).map((label) =>
    label === null || label === undefined || label === '' ? 'Value' : String(label),
  );

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
    'calendar_quarter_num',
    'fiscal_quarter_num',
    'quarter_num',
    'quarter_number',
    'calendar_month',
    'calendar_month_num',
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
  const resolveCandidateField = (candidate?: string | null): string | undefined => {
    if (!candidate || typeof candidate !== 'string') {
      return undefined;
    }
    const direct = numericFieldCandidates.find((column) => column === candidate);
    if (direct) {
      return direct;
    }
    const lowerCandidate = candidate.toLowerCase();
    const caseInsensitive = numericFieldCandidates.find((column) => column.toLowerCase() === lowerCandidate);
    if (caseInsensitive) {
      return caseInsensitive;
    }
    if (candidate.includes('|')) {
      const parts = candidate
        .split('|')
        .map((part) => part.trim())
        .filter((part) => part.length > 0);
      for (let idx = parts.length - 1; idx >= 0; idx -= 1) {
        const part = parts[idx];
        const match = numericFieldCandidates.find(
          (column) => column === part || column.toLowerCase() === part.toLowerCase(),
        );
        if (match) {
          return match;
        }
      }
      const combinedLower = parts.join('_').toLowerCase();
      const combinedMatch = numericFieldCandidates.find(
        (column) => column.toLowerCase() === combinedLower,
      );
      if (combinedMatch) {
        return combinedMatch;
      }
      const suffix = parts[parts.length - 1];
      if (suffix) {
        const suffixLower = suffix.toLowerCase();
        const suffixMatch = numericFieldCandidates.find(
          (column) => column.toLowerCase().endsWith(`_${suffixLower}`),
        );
        if (suffixMatch) {
          return suffixMatch;
        }
      }
    }
    return undefined;
  };
  const displayToField = new Map<string, string>();
  Object.entries(displayNames || {}).forEach(([field, name]) => {
    if (name) {
      displayToField.set(String(name), field);
    }
  });
  const fallbackMetricFieldCandidate =
    (Array.isArray(spec.meta?.defaultColumns) && spec.meta.defaultColumns[0]) ||
    (Array.isArray(spec.meta?.includedColumns) && spec.meta.includedColumns[0]) ||
    valueKey;
  const fallbackMetricField =
    resolveCandidateField(fallbackMetricFieldCandidate) ??
    (typeof valueKey === 'string' ? valueKey : undefined);

  const resolveSeriesField = (series: any): string | undefined => {
    const seriesName = String(series?.name ?? '');
    if (series?.meta?.field) {
      const resolved = resolveCandidateField(series.meta.field);
      if (resolved) return resolved;
    }
    if (series?.meta?.metric_field) {
      const resolved = resolveCandidateField(series.meta.metric_field);
      if (resolved) return resolved;
    }
    if (series?.meta?.metric) {
      const resolved = resolveCandidateField(series.meta.metric);
      if (resolved) return resolved;
    }
    if (displayToField.has(seriesName)) {
      const resolved = resolveCandidateField(displayToField.get(seriesName));
      if (resolved) return resolved;
    }
    const normalized = seriesName.toLowerCase();
    const candidate = numericFieldCandidates.find((column) => {
      const formatted = column.replace(/_/g, ' ').toLowerCase();
      return normalized.includes(formatted);
    });
    if (candidate) return candidate;
    if (Array.isArray(spec.meta?.metricsList)) {
      const fromMetrics = (spec.meta.metricsList as string[]).find((metric) =>
        normalized.includes(metric.replace(/_/g, ' ').toLowerCase()),
      );
      const resolvedFromMetrics = resolveCandidateField(fromMetrics);
      if (resolvedFromMetrics) {
        return resolvedFromMetrics;
      }
    }
    const fromIncluded = includedColumns.find((column: string) => {
      const formatted = column.replace(/_/g, ' ').toLowerCase();
      return normalized.includes(formatted);
    });
    const resolvedIncluded = resolveCandidateField(fromIncluded);
    if (resolvedIncluded) {
      return resolvedIncluded;
    }
    return fallbackMetricField;
  };

  const normalizeGroupValue = (value: any) => {
    if (value === null || value === undefined) return '__default__';
    return String(value).trim().toLowerCase();
  };

  const deriveSeriesGroup = (series: any): string | undefined => {
    if (!splitKey) return '__default__';
    if (series?.meta?.groupValue !== undefined) return String(series.meta.groupValue);
    if (series?.meta?.group !== undefined) return String(series.meta.group);
    if (series?.meta?.ticker !== undefined) return String(series.meta.ticker);
    const seriesName = String(series?.name ?? '');
    if (seriesName.includes(' - ')) {
      return seriesName.split(' - ', 1)[0];
    }
    return seriesName;
  };

  const groupedRows = new Map<string, Map<string, any>>();
  sortedRawData.forEach((row: any, index: number) => {
    const groupKey = splitKey ? normalizeGroupValue(row?.[splitKey]) : '__default__';
    const labelKey = String(toLabel(sortedRawData[index]));
    if (!groupedRows.has(groupKey)) {
      groupedRows.set(groupKey, new Map());
    }
    groupedRows.get(groupKey)!.set(labelKey, row);
  });
  const groupedRowEntries = Array.from(groupedRows.entries());
  const resolveGroupedRows = (key: string) => {
    const direct = groupedRows.get(key);
    if (direct && direct.size) {
      return direct;
    }
    if (groupedRowEntries.length === 1) {
      return groupedRowEntries[0][1];
    }
    if (key === '__default__') {
      const [, fallbackRows] = groupedRowEntries.find(([candidateKey]) => candidateKey !== '__default__') ?? [];
      if (fallbackRows && fallbackRows.size) {
        return fallbackRows;
      }
    }
    return direct ?? new Map<string, any>();
  };

  let datasetApplied = false;
  if (splitKey && valueKey) {
    const datasetSource = flattenedRawData.map((row: any, index: number) => ({
      ...row,
      [categoryDimensionKey]: toLabel(sortedRawData[index]),
    }));
    const metricFields = new Set<string>(numericFieldCandidates.length ? numericFieldCandidates : []);
    if (!metricFields.size && Array.isArray(includedColumns)) {
      includedColumns.forEach((col: string) => metricFields.add(col));
    }
    const seriesFieldMap = new Map<number, string>();
    const seriesGroupMap = new Map<number, string | undefined>();
    (hydrated.series || []).forEach((series: any, idx: number) => {
      const resolvedField = resolveSeriesField(series) ?? fallbackMetricField ?? valueKey;
      if (resolvedField) {
        metricFields.add(resolvedField);
      }
      seriesFieldMap.set(idx, resolvedField ?? '');
      seriesGroupMap.set(idx, deriveSeriesGroup(series));
    });
    const datasetEntry = {
      dimensions: Array.from(new Set([
        categoryDimensionKey,
        splitKey,
        ...metricFields,
      ])),
      source: datasetSource,
    };
    const existingDataset = Array.isArray(hydrated.dataset) ? [...hydrated.dataset] : [];
    const datasetIndex = existingDataset.length;
    existingDataset.push(datasetEntry);
    hydrated.dataset = existingDataset;
    hydrated.series = (hydrated.series || []).map((series: any, idx: number) => {
      const next = { ...series };
      if (next.data !== undefined) {
        delete next.data;
      }
      const fieldForSeries = seriesFieldMap.get(idx) || fallbackMetricField || valueKey;
      const groupValueRaw = seriesGroupMap.get(idx);
      const groupKey = splitKey ? normalizeGroupValue(groupValueRaw) : '__default__';
      const groupRows = resolveGroupedRows(groupKey);
      const dataValues = labels.map((label) => {
        const row = groupRows.get(label);
        if (!row) return null;
        if (!fieldForSeries) return null;
        const value = row?.[fieldForSeries];
        if (typeof value === 'number') return value;
        const parsed = coerceNumeric(value);
        return typeof parsed === 'number' && Number.isFinite(parsed) ? parsed : null;
      });
      if (fieldForSeries) {
        next.encode = {
          x: categoryDimensionKey,
          y: fieldForSeries,
          seriesName: splitKey,
          itemName: categoryDimensionKey,
        };
        next.seriesLayoutBy = 'column';
      }
      next.datasetIndex = datasetIndex;
      next.data = dataValues;
      return next;
    });
    datasetApplied = true;
  }

  if (!datasetApplied) {
    hydrated.series = hydrated.series.map((series: any) => {
      const field = resolveSeriesField(series) ?? fallbackMetricField ?? valueKey;
      const groupValueRaw = deriveSeriesGroup(series);
      const groupKey = splitKey ? normalizeGroupValue(groupValueRaw) : '__default__';
      const groupRows = resolveGroupedRows(groupKey);

      if (!field) {
        return series;
      }

      const values = labels.map((label) => {
        const row = groupRows.get(label);
        if (!row) return null;
        const value = row?.[field];
        if (typeof value === 'number') return value;
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
  const numericSamples = (() => {
    const samples: number[] = [];
    const collectFromEntry = (entry: any) => {
      const candidate = extractNumericCandidate(entry);
      if (typeof candidate === 'number' && Number.isFinite(candidate)) {
        samples.push(candidate);
      }
    };
    if (Array.isArray(option.series)) {
      option.series.forEach((series: any) => {
        if (!Array.isArray(series?.data)) {
          return;
        }
        series.data.forEach(collectFromEntry);
      });
    }
    return samples;
  })();
  const determineValueScale = (values: number[]) => {
    if (!values.length) {
      return { divisor: 1, suffix: '', label: '' };
    }
    const maxAbs = values.reduce((max, value) => {
      const magnitude = Math.abs(value);
      return magnitude > max ? magnitude : max;
    }, 0);
    if (!Number.isFinite(maxAbs) || maxAbs === 0) {
      return { divisor: 1, suffix: '', label: '' };
    }
    const thresholds = [
      { value: 1e12, divisor: 1e12, suffix: 'T', label: 'Trillions' },
      { value: 1e9, divisor: 1e9, suffix: 'B', label: 'Billions' },
      { value: 1e6, divisor: 1e6, suffix: 'M', label: 'Millions' },
      { value: 1e3, divisor: 1e3, suffix: 'K', label: 'Thousands' },
    ];
    const match = thresholds.find((entry) => maxAbs >= entry.value);
    if (match) {
      return { divisor: match.divisor, suffix: match.suffix, label: match.label };
    }
    return { divisor: 1, suffix: '', label: '' };
  };
  const resolveCurrencySymbol = () => {
    const explicit = spec.meta?.valueCurrencySymbol;
    if (typeof explicit === 'string' && explicit.trim().length) {
      return explicit.trim();
    }
    const currency = typeof spec.meta?.valueCurrency === 'string' ? spec.meta.valueCurrency.trim().toUpperCase() : undefined;
    switch (currency) {
      case 'USD':
        return '$';
      case 'EUR':
        return '€';
      case 'GBP':
        return '£';
      case 'JPY':
      case 'CNY':
      case 'RMB':
        return '¥';
      case 'AUD':
        return 'A$';
      case 'CAD':
        return 'C$';
      default:
        return currency && currency.length === 1 ? currency : '$';
    }
  };
  const valueScale = !usesPercent ? determineValueScale(numericSamples) : { divisor: 1, suffix: '', label: '' };
  const currencySymbol = usesPercent ? '' : resolveCurrencySymbol();
  // Normalise formatter payloads (axis/tooltip objects, datasets, etc.) into a primitive.
  const unwrapFormatterInput = (input: any): any => {
    if (input === null || input === undefined) return input;
    if (typeof input === 'number' || typeof input === 'string') return input;

    const visited = new Set<any>();
    const walk = (value: any): any => {
      if (value === null || value === undefined) return value;
      if (typeof value === 'number' || typeof value === 'string') return value;
      if (visited.has(value)) return undefined;

      if (Array.isArray(value)) {
        for (const item of value) {
          const result = walk(item);
          if (result !== undefined) {
            return result;
          }
        }
        return undefined;
      }

      if (typeof value === 'object') {
        visited.add(value);
        const candidateKeys = [
          'value',
          'raw',
          'rawValue',
          'axisValue',
          'axisValueLabel',
          'name',
          'label',
          'text',
          'payload',
          'data',
          'y',
        ];

        for (const key of candidateKeys) {
          if (Object.prototype.hasOwnProperty.call(value, key)) {
            const result = walk((value as any)[key]);
            if (result !== undefined) {
              return result;
            }
          }
        }
      }

      return undefined;
    };

    const resolved = walk(input);
    if (resolved !== undefined) {
      return resolved;
    }
    if (typeof (input as any)?.valueOf === 'function') {
      const primitive = (input as any).valueOf();
      if (primitive !== input) {
        return primitive;
      }
    }
    return input;
  };

  const formatPercent = (v: any, seriesName?: string) => {
    const normalized = unwrapFormatterInput(v);
    const num = typeof normalized === 'number' ? normalized : Number(normalized);
    if (Number.isFinite(num)) {
      const percentFormat = spec.meta?.seriesPercentFormat?.[seriesName || ''];
      
      if (percentFormat === 'pre_multiplied' || chartIsPercent) {
        return `${num.toFixed(1)}%`;
      } else if (percentFormat === 'decimal') {
        return `${(num * 100).toFixed(1)}%`;
      } else {
        const percentValue = num > 1 ? num : num * 100;
        return `${percentValue.toFixed(1)}%`;
      }
    }
    if (normalized === null || normalized === undefined) {
      return '';
    }
    if (typeof normalized === 'object') {
      return toDisplayString(normalized);
    }
    return String(normalized);
  };
  const formatCurrency0 = (v: any) => {
    const normalized = unwrapFormatterInput(v);
    const num = typeof normalized === 'number' ? normalized : Number(normalized);
    if (Number.isFinite(num)) {
      const divisor = valueScale.divisor || 1;
      const scaled = num / divisor;
      const absoluteScaled = Math.abs(scaled);
      const decimals =
        divisor === 1
          ? absoluteScaled >= 100
            ? 0
            : absoluteScaled >= 10
              ? 1
              : absoluteScaled >= 1
                ? 2
                : 3
          : absoluteScaled >= 100
            ? 1
            : 2;
      const formattedNumber = scaled.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
      const suffix = valueScale.suffix ?? '';
      const prefix = currencySymbol ?? '';
      return `${prefix}${formattedNumber}${suffix}`;
    }
    if (normalized === null || normalized === undefined) {
      return '';
    }
    if (typeof normalized === 'object') {
      return toDisplayString(normalized);
    }
    return String(normalized);
  };

  const resolveValueFromParams = (params: any, axis: 'x' | 'y' = 'y') => {
    if (!params) return undefined;
    const encode = params.encode || {};
    const targetDims: any[] = axis === 'y' ? encode.y || encode.value || [] : encode.x || encode.axis || [];
    const dimensionNames: any[] = params.dimensionNames || [];
    const rawValue = params.value ?? params.data?.value ?? params.data;

    const tryFromObject = (valueObj: any) => {
      if (!valueObj || typeof valueObj !== 'object') return undefined;
      if (targetDims.length) {
        for (const dim of targetDims) {
          const name = typeof dim === 'number' ? dimensionNames[dim] : dim;
          if (name && Object.prototype.hasOwnProperty.call(valueObj, name)) {
            return valueObj[name];
          }
          if (Object.prototype.hasOwnProperty.call(valueObj, dim)) {
            return valueObj[dim];
          }
        }
      }
      const fallbackKeys = ['value', 'raw', 'numeric', 'amount'];
      for (const key of fallbackKeys) {
        if (Object.prototype.hasOwnProperty.call(valueObj, key)) {
          return valueObj[key];
        }
      }
      if (axis === 'x' && Object.prototype.hasOwnProperty.call(valueObj, '__label')) {
        return valueObj.__label;
      }
      return undefined;
    };

    if (Array.isArray(rawValue) && targetDims.length) {
      const dimIndex = typeof targetDims[0] === 'number' ? targetDims[0] : dimensionNames.indexOf(targetDims[0]);
      if (dimIndex >= 0 && rawValue[dimIndex] !== undefined) {
        return rawValue[dimIndex];
      }
    }

    if (typeof rawValue === 'object') {
      const objCandidate = tryFromObject(rawValue);
      if (objCandidate !== undefined) {
        return objCandidate;
      }
    }

    const nested = params.data && typeof params.data === 'object' ? tryFromObject(params.data) : undefined;
    if (nested !== undefined) {
      return nested;
    }

    return rawValue;
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
  const normalizeYAxis = (ax: any) => {
    const baseAxis = { ...(ax || {}) };
    const existingName = typeof baseAxis.name === 'string' && baseAxis.name.trim().length ? baseAxis.name : undefined;
    const derivedName = (() => {
      if (usesPercent) {
        return existingName;
      }
      if (!valueScale.label) {
        return existingName ?? (currencySymbol && currencySymbol.trim().length ? currencySymbol : undefined);
      }
      if (existingName) {
        const lower = existingName.toLowerCase();
        if (lower.includes(valueScale.label.toLowerCase())) {
          return existingName;
        }
        return `${existingName} (${valueScale.label})`;
      }
      return currencySymbol && currencySymbol.trim().length
        ? `${currencySymbol} ${valueScale.label}`
        : valueScale.label;
    })();
    return {
      ...baseAxis,
      ...(derivedName ? { name: derivedName } : {}),
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
    };
  };
  const xAxisArr = Array.isArray(spec.xAxis) ? spec.xAxis : spec.xAxis ? [spec.xAxis] : [];
  const yAxisArr = Array.isArray(spec.yAxis) ? spec.yAxis : spec.yAxis ? [spec.yAxis] : [];
  if (xAxisArr.length) option.xAxis = xAxisArr.map(normalizeXAxis);
  if (yAxisArr.length) option.yAxis = yAxisArr.map(normalizeYAxis);

  // Tooltip value formatting by series type
  option.tooltip.formatter = (params: any) => {
    const list = Array.isArray(params) ? params : [params];
    const first = list[0] || {};
    const axisValue = resolveValueFromParams(first, 'x') ?? first.axisValueLabel ?? first.name ?? '';
    const lines = [axisValue];
    for (const p of list) {
      const isSingleSeries = Array.isArray(option.series) && option.series.length === 1;
      const isPercent = percentSeries.has(p.seriesName) || (includedPercent && isSingleSeries);
      const rawVal = resolveValueFromParams(p, 'y');
      const formatted = isPercent ? formatPercent(rawVal, p.seriesName) : formatCurrency0(rawVal);
      lines.push(`${p.marker || ''} ${p.seriesName}: ${formatted}`);
    }
    return lines.join('<br/>');
  };
  // Enable data labels with smart positioning
  const totalSeriesCount = Array.isArray(option.series) ? option.series.length : 0;
  const datapointCount =
    totalSeriesCount > 0
      ? Math.max(
          ...option.series.map((series: any) => (Array.isArray(series?.data) ? series.data.length : 0)),
        )
      : 0;
  const shouldShowPointLabels = totalSeriesCount > 0 && datapointCount > 0;

  const legendNameFormatter = (name: string) => {
    if (typeof name !== 'string') return name;
    const displayName = spec.meta?.displayNames?.[name];
    if (displayName) return displayName;
    if (name.includes(' - ')) {
      const [prefix, suffix] = name.split(' - ', 2);
      if (suffix?.toLowerCase().startsWith('peer')) {
        return suffix.replace(/^peer\s+/i, 'Peer ').trim();
      }
      if (suffix?.toLowerCase().includes(prefix.toLowerCase())) {
        return suffix.trim();
      }
      return `${prefix.trim()} ${suffix.trim()}`;
    }
    return name;
  };

  const applyLegendFormatter = (legend: any) => ({
    ...(legend || {}),
    formatter: legendNameFormatter,
    tooltip: { ...((legend || {}).tooltip || {}), show: true },
  });
  if (Array.isArray(option.legend)) {
    option.legend = option.legend.map((legend: any) => applyLegendFormatter(legend));
  } else if (option.legend) {
    option.legend = applyLegendFormatter(option.legend);
  }

  const paletteCandidates = Array.isArray(option.color)
    ? (option.color as unknown[]).filter(
        (entry): entry is string => typeof entry === 'string' && entry.trim().length > 0,
      )
    : [];
  const palettePool = paletteCandidates.length ? paletteCandidates.slice() : DEFAULT_CHART_PALETTE.slice();
  const resolvedSeriesColors: string[] = [];
  const resolveSeriesName = (series: any) => {
    if (series && typeof series.name === 'string' && series.name.trim().length) {
      return series.name.trim();
    }
    if (series && typeof series.seriesName === 'string' && series.seriesName.trim().length) {
      return series.seriesName.trim();
    }
    return '';
  };
  const isAverageSeries = (name: string) => {
    if (!name) {
      return false;
    }
    const normalized = name.toLowerCase();
    return (
      normalized.includes('industry average') ||
      normalized.includes('industry avg') ||
      normalized.includes('peer average') ||
      normalized.includes('peer avg') ||
      normalized.includes('market average') ||
      normalized.includes('benchmark')
    );
  };
  const applySeriesColor = (series: any, color: string) => {
    const nextItemStyle = {
      ...(series.itemStyle || {}),
      color,
      borderColor: color,
    };
    const baseLineStyle = series.lineStyle || {};
    const nextLineStyle = {
      ...baseLineStyle,
      width: typeof baseLineStyle.width === 'number' ? Math.max(2, baseLineStyle.width) : 2,
      color,
    };
    const emphasisItemStyle = {
      ...(series.emphasis?.itemStyle || {}),
      color,
      borderColor: color,
    };
    let finalAreaStyle = series.areaStyle;
    if (series.type === 'line') {
      const baseOpacity =
        typeof (series.areaStyle || {}).opacity === 'number' ? series.areaStyle.opacity : 0.08;
      finalAreaStyle = {
        ...(series.areaStyle || {}),
        opacity: baseOpacity,
        color: applyAlphaToColor(color, baseOpacity),
      };
    }
    return {
      itemStyle: nextItemStyle,
      lineStyle: nextLineStyle,
      areaStyle: finalAreaStyle,
      emphasis: {
        ...(series.emphasis || {}),
        itemStyle: emphasisItemStyle,
      },
    };
  };

  const legendColorLookup: Record<string, string> = {};
  if (Array.isArray(option.series)) {
    option.series = option.series.map((s: any, seriesIndex: number) => {
      const seriesName = resolveSeriesName(s);
      const averageSeriesColor = '#F59E0B';
      const overrideColor = isAverageSeries(seriesName) ? averageSeriesColor : undefined;
      if (palettePool.length <= seriesIndex) {
        palettePool.push(colorFromString(seriesName || `series-${seriesIndex}`));
      }
      const paletteColor = palettePool[seriesIndex];
      const hashedFallback = colorFromString(seriesName || `series-${seriesIndex}`);
      const seriesColor =
        overrideColor ||
        (s?.itemStyle?.color as string) ||
        paletteColor ||
        hashedFallback;
      if (seriesName) {
        legendColorLookup[seriesName] = seriesColor;
        const formattedLegend = legendNameFormatter(seriesName);
        if (typeof formattedLegend === 'string' && formattedLegend.trim().length) {
          legendColorLookup[formattedLegend] = seriesColor;
        }
      }
      resolvedSeriesColors.push(seriesColor);
      const styledSeries = applySeriesColor(s, seriesColor);
      return {
        ...s,
        itemStyle: styledSeries.itemStyle,
        lineStyle: styledSeries.lineStyle,
        areaStyle: styledSeries.areaStyle,
        emphasis: styledSeries.emphasis,
        label: {
          show: shouldShowPointLabels,
          position: 'top',
          color: seriesColor,
          fontSize: 12,
          fontWeight: 600,
          borderRadius: 6,
          padding: [4, 6],
          backgroundColor: applyAlphaToColor(seriesColor, 0.12),
          borderColor: applyAlphaToColor(seriesColor, 0.32),
          borderWidth: 1,
          shadowBlur: 6,
          shadowColor: applyAlphaToColor(seriesColor, 0.25),
          formatter: (params: any) => {
            const isSingleSeries = Array.isArray(option.series) && option.series.length === 1;
            const isPercent = percentSeries.has(params.seriesName) || (includedPercent && isSingleSeries);
            const value = resolveValueFromParams(params, 'y');
            return isPercent ? formatPercent(value, params.seriesName) : formatCurrency0(value);
          },
        },
      labelLayout: shouldShowPointLabels
        ? (layoutParams: any) => {
            const labelRect = layoutParams.labelRect || layoutParams.rect || { x: layoutParams.x, y: layoutParams.y };
            const clusterOffset = seriesIndex - (totalSeriesCount - 1) / 2;
            const horizontalShift = clusterOffset * 26;
            const verticalShift = -18 - Math.abs(clusterOffset) * 6;
            return {
              x: (labelRect.x ?? layoutParams.x) + horizontalShift,
              y: (labelRect.y ?? layoutParams.y) + verticalShift,
              align: 'center',
              verticalAlign: 'bottom',
            };
          }
        : undefined,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      };
    });
    if (resolvedSeriesColors.length) {
      option.color = resolvedSeriesColors;
    }
  }

  const syncLegendColors = (legendConfig: any) => {
    if (!legendConfig) {
      return legendConfig;
    }
    const baseLegend: any = { ...legendConfig };
    const rawData = Array.isArray(baseLegend.data) ? baseLegend.data.slice() : [];
    const fallbackNames = Array.isArray(option.series)
      ? option.series
          .map((series: any) => resolveSeriesName(series))
          .filter((name): name is string => Boolean(name && name.trim().length))
      : [];
    const dataSource = rawData.length ? rawData : fallbackNames;
    const ensureColor = (name: string | undefined) => {
      if (!name) {
        return undefined;
      }
      if (legendColorLookup[name]) {
        return legendColorLookup[name];
      }
      const formatted = legendNameFormatter(name);
      if (typeof formatted === 'string' && formatted.trim().length && legendColorLookup[formatted]) {
        return legendColorLookup[formatted];
      }
      return undefined;
    };
    baseLegend.data = dataSource.map((entry: any) => {
      if (typeof entry === 'string') {
        const color = ensureColor(entry);
        if (!color) {
          return { name: entry, icon: baseLegend.icon || 'circle' };
        }
        return {
          name: entry,
          icon: baseLegend.icon || 'circle',
          textStyle: { color, fontWeight: 600 },
          itemStyle: { color },
        };
      }
      if (!entry || typeof entry !== 'object') {
        return entry;
      }
      const name = typeof entry.name === 'string' ? entry.name : undefined;
      const color = ensureColor(name);
      const nextIcon = entry.icon || baseLegend.icon || 'circle';
      const nextItemStyle = color
        ? { ...(entry.itemStyle || {}), color }
        : entry.itemStyle;
      const nextTextStyle = color
        ? {
            ...(entry.textStyle || {}),
            color,
            fontWeight: entry.textStyle?.fontWeight ?? 600,
          }
        : entry.textStyle;
      return {
        ...entry,
        icon: nextIcon,
        itemStyle: nextItemStyle,
        textStyle: nextTextStyle,
      };
    });
    baseLegend.icon = baseLegend.icon || 'circle';
    baseLegend.tooltip = { ...(baseLegend.tooltip || {}), show: true };
    const legendTextStyle = { ...(baseLegend.textStyle || {}) };
    if (!legendTextStyle.color) {
      legendTextStyle.color = '#333333';
    }
    baseLegend.textStyle = legendTextStyle;
    return baseLegend;
  };

  if (Array.isArray(option.legend)) {
    option.legend = option.legend.map((legend: any) => syncLegendColors(legend));
  } else if (option.legend) {
    option.legend = syncLegendColors(option.legend);
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


