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
        // no-op by default; individual tests inject events via globals
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
  const { handleQuery, chatHistory } = useAnalyticsMemoryStream(flow);

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
});

