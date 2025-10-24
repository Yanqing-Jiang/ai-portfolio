import { describe, it, expect } from 'vitest';
import { deriveRevisionContext, buildPromptCandidates } from './revisionPrompts';
import type { ChatMessage } from '../types';

const baseResultMessage: ChatMessage = {
  id: 'result-1',
  type: 'result',
  content: 'Analysis complete.',
  timestamp: '2025-10-20T12:00:00.000Z',
};

describe('revision prompt helpers', () => {
  it('derives revision context with merged symbols and lane flags', () => {
    const context = deriveRevisionContext({
      chatHistory: [baseResultMessage],
      chartSpec: {
        meta: { chartDesign: { chart_type: 'line_multi' } },
        series: [{ symbol: 'NVDA' }],
      },
      analysis: 'Nvidia outperformed peers on revenue growth.',
      analysisOverview: {
        tldr: 'Strong data center demand.',
        evidence: [{ sourceUrl: 'https://example.com', publishedAt: '2025-10-18T00:00:00Z' }],
      },
      analysisSources: {
        nvda: { id: 'nvda', symbols: ['NVDA'] },
        avgo: { id: 'avgo', symbols: ['AVGO'] },
      },
      stockWidget: {
        symbols: ['NVDA', ['NASDAQ:AVGO', 'AVGO']],
        bars: [{ time: 1697500800, close: 120 }],
      },
      webSearch: {
        query: 'Nvidia data center outlook',
        searchTopics: ['AI data centre headlines'],
        snippets: [],
      },
      sqlQuery: 'SELECT * FROM metrics',
      dataSample: [{ symbol: 'NVDA', revenue: 10 }],
    });

    expect(context).not.toBeNull();
    expect(context?.availableLanes).toEqual({
      chart: true,
      analysis: true,
      market: true,
      sql: true,
      web: true,
    });
    expect(context?.primarySymbols).toEqual(expect.arrayContaining(['NVDA', 'AVGO']));
    expect(context?.stockSymbols).toEqual(expect.arrayContaining(['NVDA', 'AVGO']));
    expect(context?.chartType).toBe('line_multi');
    expect(context?.timeContext).toBe('2025-10-18');
  });

  it('builds lane-specific candidates with deterministic rotation', () => {
    const context = deriveRevisionContext({
      chatHistory: [baseResultMessage],
      chartSpec: {
        meta: { chartDesign: { chart_type: 'line_multi' } },
        series: [{ symbol: 'NVDA' }],
      },
      analysis: 'AI revenue acceleration continues.',
      analysisOverview: null,
      analysisSources: { nvda: { id: 'nvda', symbols: ['NVDA'] } },
      stockWidget: { symbols: ['NVDA'], bars: [] },
      webSearch: { query: 'Nvidia market share', snippets: [], searchTopics: ['GPU share'] },
      sqlQuery: 'SELECT symbol, revenue FROM metrics',
      dataSample: [],
    });
    expect(context).not.toBeNull();

    const candidates = buildPromptCandidates(context, { rotationKey: 0 });
    expect(candidates).toHaveLength(4);
    const intents = new Set(candidates.map((candidate) => candidate.intent));
    expect(intents.has('chart_revision')).toBe(true);
    expect(intents.has('analysis_revision')).toBe(true);
    expect(intents.has('market_refresh')).toBe(true);
    expect(intents.has('mixed_revision')).toBe(true);
    const chartCopy = candidates.find((candidate) => candidate.intent === 'chart_revision')?.copy ?? '';
    const chartCopyNext =
      buildPromptCandidates(context, { rotationKey: 1 }).find((candidate) => candidate.intent === 'chart_revision')
        ?.copy ?? '';
    expect(chartCopy).not.toBe(chartCopyNext);
  });

  it('fills minimum prompt count even when only chart lane is available', () => {
    const context = {
      availableLanes: { chart: true, analysis: false, market: false, sql: false, web: false },
      primarySymbols: [],
      stockSymbols: [],
      chartType: null,
      timeContext: null,
      webTopics: [],
      hasStockWidget: false,
      hasWebSearch: false,
    };

    const candidates = buildPromptCandidates(context, { rotationKey: 3 });
    expect(candidates.length).toBeGreaterThanOrEqual(3);
    expect(candidates.every((candidate) => candidate.intent === 'chart_revision')).toBe(true);
    const uniqueCopies = new Set(candidates.map((candidate) => candidate.copy));
    expect(uniqueCopies.size).toBeGreaterThan(1);
  });
});
