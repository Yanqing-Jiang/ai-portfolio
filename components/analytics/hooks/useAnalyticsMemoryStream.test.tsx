// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, act, screen } from '@testing-library/react';
import { useAnalyticsMemoryStream } from './useAnalyticsMemoryStream';

// Mock the API service used by useAnalyticsStream to avoid network
vi.mock('../../../services/apiService', () => ({
  apiService: {
    post: vi.fn(async () => ({})),
    streamWithAuth: vi.fn(),
  },
}));

// Mock useAnalyticsStream to synchronously emit provided test events
vi.mock('./useAnalyticsStream', () => {
  return {
    useAnalyticsStream: () => ({
      isLoading: false,
      error: '',
      currentStatus: 'Ready to analyze financial data...',
      setCurrentStatus: vi.fn(),
      setError: vi.fn(),
      startStream: async (_endpoint: string, onEvent: (data: any) => void) => {
        const events = (globalThis as any).__TEST_EVENTS__ as any[] | undefined;
        if (Array.isArray(events)) {
          for (const e of events) {
            onEvent(e);
          }
        }
      },
      stopStream: vi.fn(),
      resetState: vi.fn(),
    }),
  };
});

function HookHarness({ query, flow }: { query: string; flow: 'planner-executor' | 'single-agent' | 'multi-agent' }) {
  const { handleQuery, chatHistory, processSteps, revisionMode } = useAnalyticsMemoryStream(flow);

  React.useEffect(() => {
    (async () => {
      if (query) {
        await handleQuery(query);
      }
    })();
  }, [query]);

  return (
    <div>
      <div data-testid="result-count">{chatHistory.filter((m) => m.type === 'result').length}</div>
      <div data-testid="message-count">{chatHistory.length}</div>
      <div data-testid="revision-mode">{revisionMode}</div>
      <ul data-testid="step-ids">
        {processSteps.map((step) => (
          <li key={step.id}>{`${step.id}:${step.status}`}</li>
        ))}
      </ul>
    </div>
  );
}

describe('useAnalyticsMemoryStream result deduping', () => {
  it('emits a single result for analysis_complete followed by workflow_complete', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      { event: 'analysis_complete', analysis: 'Final narrative here.' },
      { event: 'workflow_complete', total_elapsed_ms: 1234 },
    ];

    await act(async () => {
      render(<HookHarness query="test" flow="planner-executor" />);
    });

    const resultCount = Number(screen.getByTestId('result-count').textContent);
    expect(resultCount).toBe(1);
  });

  it('emits a single result for cohesive_result followed by workflow_complete', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      { event: 'cohesive_result', analysis: 'Cohesive final output', sql: 'SELECT 1', tool_results: [] },
      { event: 'workflow_complete' },
    ];

    await act(async () => {
      render(<HookHarness query="another" flow="single-agent" />);
    });

    const resultCount = Number(screen.getByTestId('result-count').textContent);
    expect(resultCount).toBe(1);
  });

  it('records a chart revision step when chart_patch arrives', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      { event: 'chart_patch', data: { ops: [{ op: 'set_chart_type', value: 'bar' }], status: 'applied' } },
    ];

    await act(async () => {
      render(<HookHarness query="revise chart" flow="single-agent" />);
    });

    const stepIds = Array.from(screen.getByTestId('step-ids').querySelectorAll('li')).map((li) => li.textContent || '');
    expect(stepIds).toContain('chart_revision:completed');

    const resultCount = Number(screen.getByTestId('result-count').textContent);
    expect(resultCount).toBe(2);

    expect(screen.getByTestId('revision-mode').textContent).toBe('chart');
  });

  it('records an analysis revision step when analysis_revision arrives', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      { event: 'analysis_revision', data: { analysis: 'Updated summary', status: 'applied' } },
    ];

    await act(async () => {
      render(<HookHarness query="revise analysis" flow="single-agent" />);
    });

    const stepIds = Array.from(screen.getByTestId('step-ids').querySelectorAll('li')).map((li) => li.textContent || '');
    expect(stepIds).toContain('analysis_revision:completed');

    const resultCount = Number(screen.getByTestId('result-count').textContent);
    expect(resultCount).toBe(2);

    expect(screen.getByTestId('revision-mode').textContent).toBe('analysis');
  });
});

describe('useAnalyticsMemoryStream specialist readiness', () => {
  it('keeps completion status after ready events even when later progress arrives', async () => {
    vi.useFakeTimers();
    const chartSpec = { chart_type: 'line', datasets: [] };
    (globalThis as any).__TEST_EVENTS__ = [
      { event: 'status', step: 'sql_execution', message: 'Running SQL' },
      { event: 'sql_ready', data: { sql: 'SELECT 1', row_count: 10 } },
      { event: 'chart_ready', data: { chart_spec: chartSpec, chart_summary: { chart_type: 'line' } } },
      {
        event: 'stock_ready',
        data: { stock_widget: { symbols: ['NVDA'], chartType: 'candlestick', ready: true } },
      },
      {
        event: 'web_ready',
        data: {
          web_context: {
            summary: 'NVDA growth beats peers',
            snippets: [{ title: 'Headline', snippet: 'NVDA up' }],
          },
        },
      },
      { event: 'analysis_ready', data: { analysis: 'NVDA beats peers' } },
      { event: 'progress', step: 'web_research_agent', message: 'Formatting excerpts' },
      { event: 'progress', step: 'sql_execution', message: 'Finalizing' },
    ];

    await act(async () => {
      render(<HookHarness query="nvda peers" flow="multi-agent" />);
    });

    await act(async () => {
      vi.runAllTimers();
      await Promise.resolve();
    });
    vi.useRealTimers();

    const stepItems = Array.from(screen.getByTestId('step-ids').querySelectorAll('li')).map((li) =>
      li.textContent || '',
    );

    expect(stepItems).toContain('sql_execution:completed');
    expect(stepItems).toContain('chart_generation:completed');
    expect(stepItems).toContain('web_research_agent:completed');
    expect(stepItems).toContain('analysis_generation:completed');
  });
});
