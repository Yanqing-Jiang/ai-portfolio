import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';

vi.mock('../common', () => ({
  AnalysisCard: ({ analysis }: { analysis: string; analysisSources?: any; evidenceLinks?: any }) => (
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

    render(
      <ChatHistory
        messages={messages}
        isLoading={false}
        status={{ text: 'Streaming analysis...', timestamp: new Date().toISOString() }}
        processSteps={[]}
      />,
    );

    expect(await screen.findByTestId('chart-card')).toBeInTheDocument();
    expect(screen.getByTestId('sql-card')).toHaveTextContent('SELECT 1;');
    expect(screen.getByTestId('stock-widget')).toBeInTheDocument();
    expect(screen.getByTestId('web-card')).toHaveTextContent('Market summary');
  });
});

describe('ChatHistory specialist updates', () => {
  it('suppresses attachments for non-result assistant messages', () => {
    const messages = [
      {
        id: 'assist-1',
        type: 'assistant' as const,
        content: 'Stock context ready',
        timestamp: new Date().toISOString(),
        chartSpec: { series: [{ data: [4, 5, 6] }] },
        sqlQuery: 'SELECT 2;',
        stockWidgetConfig: { symbols: [['NASDAQ:AAPL', 'AAPL']] },
        webSearch: {
          query: 'AAPL',
          summary: 'Cached market summary',
          snippets: [{ title: 'Example', snippet: 'Snippet' }],
          ready: true,
        },
      },
    ];

    render(
      <ChatHistory
        messages={messages}
        isLoading={false}
        status={{ text: 'Assistant idle', timestamp: new Date().toISOString() }}
        processSteps={[]}
      />,
    );

    expect(screen.queryByTestId('chart-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sql-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('stock-widget')).not.toBeInTheDocument();
    expect(screen.queryByTestId('web-card')).not.toBeInTheDocument();
  });
});

describe('ChatHistory status bubble alignment', () => {
  it('anchors streaming status on assistant side when the latest message is from the user', () => {
    const messages = [
      {
        id: 'u-1',
        type: 'user' as const,
        content: 'What is the market share trend?',
        timestamp: new Date().toISOString(),
      },
    ];

    render(
      <ChatHistory
        messages={messages}
        isLoading={true}
        status={{ text: 'Classifying query', timestamp: new Date().toISOString() }}
        processSteps={[]}
      />,
    );

    const statusNode = screen.getByText('Classifying query');
    const placeholder = document.querySelector('.w-9[aria-hidden="true"]') as HTMLElement | null;
    expect(placeholder).not.toBeNull();
    const alignmentRow = placeholder?.parentElement;
    expect(alignmentRow).not.toBeNull();
    expect(alignmentRow?.className).toContain('flex');
    expect(alignmentRow?.className).not.toContain('justify-end');
    expect(alignmentRow?.firstElementChild).toBe(placeholder);
    expect(alignmentRow?.textContent).toContain('Classifying query');
  });

  it('strips trailing ellipses from live status text', () => {
    const messages = [
      {
        id: 'u-1',
        type: 'user' as const,
        content: 'Fetch NVDA metrics',
        timestamp: new Date().toISOString(),
      },
    ];

    render(
      <ChatHistory
        messages={messages}
        isLoading={true}
        status={{ text: 'Analyzing...', timestamp: new Date().toISOString() }}
        processSteps={[]}
      />,
    );

    expect(screen.getByText('Analyzing')).toBeInTheDocument();
  });
});
