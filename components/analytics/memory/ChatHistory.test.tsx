import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';

vi.mock('../common', () => ({
  AnalysisCard: ({ analysis }: { analysis: string }) => (
    <div data-testid="analysis-card">{analysis}</div>
  ),
  SqlCard: ({ sqlQuery }: { sqlQuery: string }) => (
    <div data-testid="sql-card">{sqlQuery}</div>
  ),
  TradingViewSymbolOverview: ({ config }: { config: any }) => (
    <div data-testid="stock-widget">{JSON.stringify(config)}</div>
  ),
  CollapsibleSection: ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div data-testid={`section-${title}`}>{children}</div>
  ),
  WebSearchCard: ({ title, result }: { title?: string; result: any }) => (
    <div data-testid="web-card">{`${title ?? 'Web'}:${result?.summary ?? ''}`}</div>
  ),
}));

vi.mock('../common/ChartCard', () => ({
  ChartCard: () => <div data-testid="chart-card">Mock Chart</div>,
}));

import { ChatHistory } from './ChatHistory';

describe('ChatHistory attachments', () => {
  it('renders SQL, chart, stock, and web attachments for result messages', async () => {
    const messages = [
      {
        id: '1',
        type: 'result' as const,
        content: 'Here is your analysis.',
        timestamp: new Date().toISOString(),
        chartSpec: { series: [{ data: [1, 2, 3] }] },
        sqlQuery: 'SELECT 1;',
        stockWidgetConfig: { symbols: [['NASDAQ:NVDA', 'NVDA']] },
        webSearch: {
          query: 'NVDA',
          summary: 'Market summary',
          snippets: [{ title: 'Example', snippet: 'Snippet' }],
          ready: true,
        },
      },
    ];

    render(<ChatHistory messages={messages} isLoading={false} processSteps={[]} />);

    expect(await screen.findByTestId('chart-card')).toBeInTheDocument();
    expect(screen.getByTestId('sql-card')).toHaveTextContent('SELECT 1;');
    expect(screen.getByTestId('stock-widget')).toBeInTheDocument();
    expect(screen.getByTestId('web-card')).toHaveTextContent('Market summary');
  });
});
