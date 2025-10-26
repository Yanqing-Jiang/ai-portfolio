import type {
  AnalysisOverview,
  AnalysisSources,
  AnalysisSourceInsight,
  ChatMessage,
  StockWidgetConfig,
  WebSearchResult,
} from '../types';

export type RevisionPromptLane = 'chart' | 'analysis' | 'market' | 'mixed' | 'sql' | 'stock' | 'web';

export interface RevisionContextInput {
  chatHistory: ChatMessage[];
  chartSpec: any;
  analysis: string | null | undefined;
  analysisOverview: AnalysisOverview | null | undefined;
  analysisSources: AnalysisSources | null | undefined;
  stockWidget: StockWidgetConfig | null | undefined;
  webSearch: WebSearchResult | null | undefined;
  sqlQuery: string | null | undefined;
  dataSample: any[] | null | undefined;
}

export interface RevisionContext {
  availableLanes: {
    chart: boolean;
    analysis: boolean;
    market: boolean;
    sql: boolean;
    web: boolean;
  };
  primarySymbols: string[];
  stockSymbols: string[];
  chartType: string | null;
  timeContext: string | null;
  webTopics: string[];
  hasStockWidget: boolean;
  hasWebSearch: boolean;
}

export interface PromptCandidate {
  lane: RevisionPromptLane;
  copy: string;
  intent: string;
}

export interface BuildPromptOptions {
  rotationKey?: number;
  limit?: number;
  minimum?: number;
}

const CHART_STYLE_VOCAB = [
  'a bar chart',
  'a stacked column chart',
  'a heatmap',
];

const ANALYSIS_ANGLE_VOCAB = [
  'industry background',
  'competitive positioning',
  'margin resilience',
  'customer adoption signals',
  'capital expenditure drivers',
];

const MIXED_FOCUS_VOCAB = [
  'margin recovery',
  'AI supply chain impacts',
  'next-quarter catalysts',
  'operating leverage trends',
];

const SQL_METRIC_VOCAB = [
  'revenue growth',
  'gross margin',
  'operating income',
  'free cash flow',
  'R&D spend',
];

const SQL_GROUP_VOCAB = ['company', 'segment', 'fiscal quarter', 'geography'];

const WEB_TOPIC_VOCAB = [
  'AI data centre headlines',
  'semiconductor supply chain updates',
  'chip export policy shifts',
  'earnings preview commentary',
];

const STOCK_FALLBACK_SYMBOLS = ['NVDA', 'AVGO', 'AMD', 'AAPL', 'MSFT', 'GOOGL', 'TSM'];

const DEFAULT_PROMPT_LIMIT = 4;
const DEFAULT_PROMPT_MINIMUM = 3;

const STABLE_HASH_SEED = 1315423911;

const isNonEmptyString = (value: unknown): value is string =>
  typeof value === 'string' && value.trim().length > 0;

const dedupe = (values: string[]): string[] => {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    if (!value) continue;
    if (!seen.has(value)) {
      seen.add(value);
      result.push(value);
    }
  }
  return result;
};

const normaliseSymbol = (raw: unknown): string | null => {
  if (!isNonEmptyString(raw)) {
    return null;
  }
  const cleaned = raw.trim().replace(/^[A-Z]+:\s*/i, '');
  const upper = cleaned.toUpperCase();
  if (!/^[A-Z.\-]{1,8}$/.test(upper)) {
    return null;
  }
  return upper;
};

const collectSymbolsFromAnalysis = (analysisSources: AnalysisSources | null | undefined): string[] => {
  if (!analysisSources) {
    return [];
  }
  const output: string[] = [];
  Object.values(analysisSources as AnalysisSources | Record<string, AnalysisSourceInsight>).forEach((insight) => {
    const symbols = (insight?.symbols ?? []) as string[];
    symbols.forEach((symbol) => {
      const normalised = normaliseSymbol(symbol);
      if (normalised) {
        output.push(normalised);
      }
    });
  });
  return output;
};

const collectSymbolsFromStockWidget = (stockWidget: StockWidgetConfig | null | undefined): string[] => {
  if (!stockWidget?.symbols || !Array.isArray(stockWidget.symbols)) {
    return [];
  }
  const output: string[] = [];
  stockWidget.symbols.forEach((entry) => {
    if (Array.isArray(entry)) {
      entry.forEach((value) => {
        const normalised = normaliseSymbol(value);
        if (normalised) {
          output.push(normalised);
        }
      });
      return;
    }
    const normalised = normaliseSymbol(entry);
    if (normalised) {
      output.push(normalised);
    }
  });
  return output;
};

const collectSymbolsFromChartSpec = (chartSpec: any): string[] => {
  if (!chartSpec || typeof chartSpec !== 'object') {
    return [];
  }
  const collected = new Set<string>();
  const visit = (node: any, depth: number) => {
    if (depth > 6 || node == null) {
      return;
    }
    if (Array.isArray(node)) {
      node.forEach((entry) => visit(entry, depth + 1));
      return;
    }
    if (typeof node !== 'object') {
      return;
    }
    Object.entries(node).forEach(([key, value]) => {
      if (/symbol/i.test(key) || /ticker/i.test(key)) {
        const bucket = Array.isArray(value) ? value : [value];
        bucket.forEach((entry) => {
          if (Array.isArray(entry)) {
            entry.forEach((inner) => {
              const normalised = normaliseSymbol(inner);
              if (normalised) {
                collected.add(normalised);
              }
            });
            return;
          }
          const normalised = normaliseSymbol(entry as string);
          if (normalised) {
            collected.add(normalised);
          }
        });
      }
      if (value && typeof value === 'object') {
        visit(value, depth + 1);
      }
    });
  };
  visit(chartSpec, 0);
  return Array.from(collected.values());
};

const extractEvidenceDates = (analysisOverview: AnalysisOverview | null | undefined): number[] => {
  const evidence = analysisOverview?.evidence ?? [];
  if (!Array.isArray(evidence)) {
    return [];
  }
  return evidence
    .map((item) => {
      const published = (item as any)?.publishedAt ?? (item as any)?.published_at;
      if (!isNonEmptyString(published)) {
        return null;
      }
      const timestamp = Date.parse(published);
      return Number.isFinite(timestamp) ? timestamp : null;
    })
    .filter((value): value is number => typeof value === 'number');
};

const extractStockBarDates = (stockWidget: StockWidgetConfig | null | undefined): number[] => {
  const bars = stockWidget?.bars ?? [];
  if (!Array.isArray(bars)) {
    return [];
  }
  return bars
    .map((bar) => {
      const time = (bar as any)?.time;
      if (typeof time !== 'number') {
        return null;
      }
      // Treat numbers below 1e12 as second-based timestamps.
      return time < 1e12 ? time * 1000 : time;
    })
    .filter((value): value is number => typeof value === 'number');
};

const computeLatestDateIso = (timestamps: number[]): string | null => {
  if (!timestamps.length) {
    return null;
  }
  const newest = Math.max(...timestamps);
  try {
    const iso = new Date(newest).toISOString();
    return iso.slice(0, 10);
  } catch {
    return null;
  }
};

const hasMeaningfulAnalysis = (analysis: string | null | undefined, overview: AnalysisOverview | null | undefined): boolean => {
  if (isNonEmptyString(analysis)) {
    return true;
  }
  if (!overview) {
    return false;
  }
  const { tldr, highlights, keyNumbers, riskWatch, nextSteps } = overview;
  return Boolean(
    (Array.isArray(highlights) && highlights.length > 0) ||
      (Array.isArray(keyNumbers) && keyNumbers.length > 0) ||
      (Array.isArray(riskWatch) && riskWatch.length > 0) ||
      (Array.isArray(nextSteps) && nextSteps.length > 0) ||
      isNonEmptyString(tldr),
  );
};

const stableHash = (input: string): number => {
  let hash = STABLE_HASH_SEED;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= (hash << 5) + input.charCodeAt(index) + (hash >> 2);
  }
  return hash >>> 0;
};

const pickVariant = (
  lane: RevisionPromptLane | 'sql_metric' | 'sql_group',
  options: string[],
  rotationKey: number,
  variantOffset: number,
  salt: string,
): string => {
  if (!options.length) {
    return '';
  }
  const base = stableHash(`${lane}|${rotationKey}|${salt}`);
  const index = Math.abs(base + variantOffset) % options.length;
  return options[index];
};

const pickAlternateSymbol = (context: RevisionContext): string | null => {
  const occupied = new Set([...context.stockSymbols, ...context.primarySymbols]);
  for (const symbol of STOCK_FALLBACK_SYMBOLS) {
    if (!occupied.has(symbol)) {
      return symbol;
    }
  }
  if (context.primarySymbols.length > 1) {
    return context.primarySymbols[1];
  }
  return context.primarySymbols[0] ?? null;
};

export const deriveRevisionContext = (input: RevisionContextInput): RevisionContext | null => {
  const hasResult = (input.chatHistory || []).some((message) => message?.type === 'result');
  if (!hasResult) {
    return null;
  }

  const analysisSymbols = collectSymbolsFromAnalysis(input.analysisSources);
  const stockSymbols = collectSymbolsFromStockWidget(input.stockWidget);
  const chartSymbols = collectSymbolsFromChartSpec(input.chartSpec);

  const primarySymbols = dedupe([...analysisSymbols, ...stockSymbols, ...chartSymbols]);

  const analysisAvailable = hasMeaningfulAnalysis(input.analysis, input.analysisOverview);
  const chartAvailable = Boolean(input.chartSpec);
  const stockAvailable = stockSymbols.length > 0;
  const webAvailable = Boolean(input.webSearch);
  const sqlAvailable =
    (isNonEmptyString(input.sqlQuery) && (input.sqlQuery as string).length > 0) ||
    (Array.isArray(input.dataSample) && input.dataSample.length > 0);

  const marketAvailable = stockAvailable || webAvailable;

  const evidenceDates = extractEvidenceDates(input.analysisOverview);
  const stockDates = extractStockBarDates(input.stockWidget);
  const timeContext = computeLatestDateIso([...evidenceDates, ...stockDates]);

  const webTopicsRaw: string[] = [];
  if (webAvailable) {
    const topics = (input.webSearch?.searchTopics ?? input.webSearch?.searchTopic ?? []) as string[] | string;
    if (Array.isArray(topics)) {
      topics.forEach((topic) => {
        if (isNonEmptyString(topic)) {
          webTopicsRaw.push(topic.trim());
        }
      });
    } else if (isNonEmptyString(topics)) {
      webTopicsRaw.push(topics.trim());
    }
    const query = input.webSearch?.query ?? input.webSearch?.queryTerms;
    if (isNonEmptyString(query)) {
      webTopicsRaw.push(query.trim());
    }
    const snippets = input.webSearch?.snippets ?? [];
    if (Array.isArray(snippets)) {
      snippets.forEach((snippet) => {
        const title = (snippet as any)?.title ?? (snippet as any)?.snippet;
        if (isNonEmptyString(title)) {
          webTopicsRaw.push(title.trim());
        }
      });
    }
  }

  const chartType =
    (input.chartSpec?.meta?.chartDesign?.chart_type as string | undefined) ??
    (input.chartSpec?.chart_type as string | undefined) ??
    null;

  return {
    availableLanes: {
      chart: chartAvailable,
      analysis: analysisAvailable,
      market: marketAvailable,
      sql: sqlAvailable,
      web: webAvailable,
    },
    primarySymbols,
    stockSymbols,
    chartType: chartType ?? null,
    timeContext,
    webTopics: dedupe(webTopicsRaw.map((topic) => topic.trim()).filter(Boolean)),
    hasStockWidget: stockAvailable,
    hasWebSearch: webAvailable,
  };
};

export const buildPromptCandidates = (
  context: RevisionContext | null | undefined,
  options: BuildPromptOptions = {},
): PromptCandidate[] => {
  if (!context) {
    return [];
  }
  const { rotationKey = 0, limit = DEFAULT_PROMPT_LIMIT, minimum = DEFAULT_PROMPT_MINIMUM } = options;
  const targetLimit = Math.max(1, limit);
  const targetMinimum = Math.min(targetLimit, Math.max(1, minimum));
  const primary = context.primarySymbols[0] ?? 'the lead ticker';
  const saltBase = context.primarySymbols.join('|') || context.chartType || 'default';

  const buildChartPrompt = (variantOffset: number): PromptCandidate | null => {
    if (!context.availableLanes.chart) {
      return null;
    }
    const style = pickVariant('chart', CHART_STYLE_VOCAB, rotationKey, variantOffset, saltBase);
    const descriptor = context.availableLanes.sql ? 'the SQL chart' : 'the chart';
    const copy = `Change ${descriptor} to ${style} and reuse the same dataset.`;
    return { lane: 'chart', copy, intent: 'chart_revision' };
  };

  const buildAnalysisPrompt = (variantOffset: number): PromptCandidate | null => {
    if (!context.availableLanes.analysis) {
      return null;
    }
    const angle = pickVariant('analysis', ANALYSIS_ANGLE_VOCAB, rotationKey, variantOffset, saltBase);
    const emphasise = context.primarySymbols.length ? ` for ${primary}` : '';
    const copy = `Rewrite the analysis but focus on ${angle}${emphasise}.`;
    return { lane: 'analysis', copy, intent: 'analysis_revision' };
  };

  const buildMarketPrompt = (variantOffset: number): PromptCandidate | null => {
    if (!context.availableLanes.market) {
      return null;
    }
    const subject = context.hasStockWidget ? primary : 'the tracked symbols';
    const copy = `Refresh only the market data for ${subject}.`;
    return { lane: 'market', copy, intent: 'market_refresh' };
  };

  const buildMixedPrompt = (variantOffset: number): PromptCandidate | null => {
    if (!context.availableLanes.chart || !context.availableLanes.analysis) {
      return null;
    }
    const focus = pickVariant('mixed', MIXED_FOCUS_VOCAB, rotationKey, variantOffset, saltBase);
    const suffix = context.primarySymbols.length ? ` for ${primary}` : '';
    const copy = `Keep the query but update both the chart and analysis to highlight ${focus}${suffix}.`;
    return { lane: 'mixed', copy, intent: 'mixed_revision' };
  };

  const buildSqlPrompt = (variantOffset: number): PromptCandidate | null => {
    if (!context.availableLanes.sql) {
      return null;
    }
    const metric = pickVariant('sql_metric', SQL_METRIC_VOCAB, rotationKey, variantOffset, saltBase);
    const group = pickVariant('sql_group', SQL_GROUP_VOCAB, rotationKey, variantOffset, saltBase);
    const copy = `Reuse the SQL results and adjust the chart to compare ${metric} by ${group}.`;
    return { lane: 'sql', copy, intent: 'sql_reuse' };
  };

  const buildStockPrompt = (variantOffset: number): PromptCandidate | null => {
    if (!context.hasStockWidget) {
      return null;
    }
    const alternate = pickAlternateSymbol(context);
    if (!alternate) {
      return null;
    }
    const copy = `Change the stock chart to ${alternate}.`;
    return { lane: 'stock', copy, intent: 'stock_swap' };
  };

  const buildWebPrompt = (variantOffset: number): PromptCandidate | null => {
    if (!context.hasWebSearch) {
      return null;
    }
    const fallbackTopic = pickVariant('web', WEB_TOPIC_VOCAB, rotationKey, variantOffset, saltBase);
    const contextualTopic =
      context.webTopics.length > 0
        ? context.webTopics[variantOffset % context.webTopics.length]
        : undefined;
    const topic = contextualTopic ?? fallbackTopic;
    const copy = `Refresh the web research only and look for ${topic}.`;
    return { lane: 'web', copy, intent: 'web_refresh' };
  };

  const laneBuilders: Record<RevisionPromptLane, (variantOffset: number) => PromptCandidate | null> = {
    chart: buildChartPrompt,
    analysis: buildAnalysisPrompt,
    market: buildMarketPrompt,
    mixed: buildMixedPrompt,
    sql: buildSqlPrompt,
    stock: buildStockPrompt,
    web: buildWebPrompt,
  };

  const lanePriority: RevisionPromptLane[] = ['chart', 'analysis', 'market', 'mixed', 'sql', 'stock', 'web'];

  const chosen: PromptCandidate[] = [];
  const seenCopy = new Set<string>();

  lanePriority.forEach((lane) => {
    const prompt = laneBuilders[lane](0);
    if (prompt && !seenCopy.has(prompt.copy)) {
      chosen.push(prompt);
      seenCopy.add(prompt.copy);
    }
  });

  const ensureMinimum = () => {
    if (chosen.length >= targetMinimum) {
      return;
    }
    lanePriority.forEach((lane) => {
      if (chosen.length >= targetMinimum) {
        return;
      }
      for (let offset = 1; offset < 4 && chosen.length < targetMinimum; offset += 1) {
        const prompt = laneBuilders[lane](offset);
        if (prompt && !seenCopy.has(prompt.copy)) {
          chosen.push(prompt);
          seenCopy.add(prompt.copy);
        }
      }
    });
  };

  ensureMinimum();

  return chosen.slice(0, targetLimit);
};
