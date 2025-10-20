// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, screen, renderHook } from '@testing-library/react';
import { useAnalyticsMemoryStream } from './useAnalyticsMemoryStream';
import { apiService } from '../../../services/apiService';

// Mock the API service used by useAnalyticsStream to avoid network
vi.mock('../../../services/apiService', () => ({
  apiService: {
    post: vi.fn(async () => ({})),
    streamWithAuth: vi.fn(),
  },
}));

const setCurrentStatusMock = vi.fn();
const setErrorMock = vi.fn();
const stopStreamMock = vi.fn();
const resetStateMock = vi.fn();

// Mock useAnalyticsStream to synchronously emit provided test events
vi.mock('./useAnalyticsStream', () => {
  return {
    useAnalyticsStream: () => ({
      isLoading: false,
      error: '',
      currentStatus: '',
      statusTimestamp: null,
      setCurrentStatus: setCurrentStatusMock,
      setError: setErrorMock,
      startStream: async (_endpoint: string, onEvent: (data: any) => void) => {
        const events = (globalThis as any).__TEST_EVENTS__ as any[] | undefined;
        if (Array.isArray(events)) {
          for (const e of events) {
            onEvent(e);
          }
        }
      },
      stopStream: stopStreamMock,
      resetState: resetStateMock,
    }),
  };
});

beforeEach(() => {
  setCurrentStatusMock.mockReset();
  setErrorMock.mockReset();
  stopStreamMock.mockReset();
  resetStateMock.mockReset();
  (globalThis as any).__TEST_EVENTS__ = undefined;
});

function HookHarness({ query, flow }: { query: string; flow: 'planner-executor' | 'single-agent' | 'multi-agent' }) {
  const { handleQuery, chatHistory, processSteps, revisionMode, analysisBundle } = useAnalyticsMemoryStream(flow);
  const firstResult = chatHistory.find((m) => m.type === 'result');

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
      <div data-testid="first-result-content">{firstResult?.content ?? ''}</div>
      <ul data-testid="step-ids">
        {processSteps.map((step) => (
          <li key={step.id}>{`${step.id}:${step.status}`}</li>
        ))}
      </ul>
      <div data-testid="first-result-evidence">{firstResult?.analysisOverview ? JSON.stringify(firstResult.analysisOverview.evidence || []) : ''}</div>
      <div data-testid="latency-guardrail-status">{firstResult?.latencyGuardrail?.status ?? ''}</div>
      <div data-testid="analysis-bundle">{analysisBundle ? JSON.stringify(analysisBundle) : ''}</div>
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

  it('dedupes repeated analysis_ready payloads', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      { event: 'analysis_ready', data: { analysis: 'Final NVDA summary.' } },
      { event: 'analysis_ready', data: { analysis: 'Final NVDA summary.' } },
      { event: 'workflow_complete', total_elapsed_ms: 640 },
    ];

    await act(async () => {
      render(<HookHarness query="dedupe analysis" flow="planner-executor" />);
    });

    const resultCount = Number(screen.getByTestId('result-count').textContent);
    expect(resultCount).toBe(1);
  });
  it('parses evidence entries from analysis_overview payloads', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      {
        event: 'analysis_complete',
        analysis: 'Narrative with evidence.',
        analysis_overview: {
          tldr: 'Key takeaway supported by source.',
          evidence: [
            {
              source_url: 'https://example.com/report',
              title: 'Example report',
              snippet: 'The report confirms the growth metric.',
              confidence: 0.6,
            },
          ],
        },
        latency_guardrail: {
          status: 'violation',
          violations: ['p95_ms'],
          thresholds: { p50_ms: 500, p95_ms: 1500 },
        },
      },
    ];

    await act(async () => {
      render(<HookHarness query="evidence check" flow="planner-executor" />);
    });

    const evidenceText = screen.getByTestId('first-result-evidence').textContent || '[]';
    const evidence = JSON.parse(evidenceText);
    expect(evidence).toHaveLength(1);
    expect(evidence[0].sourceUrl).toBe('https://example.com/report');
    expect(evidence[0].title).toBe('Example report');
    expect(evidence[0].confidence).toBe(0.6);
    expect(screen.getByTestId('latency-guardrail-status').textContent).toBe('violation');
  });

  it('emits a single result for cohesive_result followed by workflow_complete', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      {
        event: 'cohesive_result',
        analysis: 'Cohesive final output',
        sql: 'SELECT 1',
        tool_results: [],
        analysis_bundle: {
          sql: { row_count: 4, columns: ['metric', 'value'] },
          stock: { symbols: ['NASDAQ:AMD'] },
        },
      },
      { event: 'workflow_complete' },
    ];

    await act(async () => {
      render(<HookHarness query="another" flow="single-agent" />);
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 75));
    });

    const resultCount = Number(screen.getByTestId('result-count').textContent);
    expect(resultCount).toBe(1);
    const bundleText = screen.getByTestId('analysis-bundle').textContent || '';
    expect(bundleText).toContain('"row_count":4');
  });

  it('merges repeated analysis_ready sources into a single Financial Analysis card', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      {
        event: 'analysis_ready',
        analysis: 'SQL snapshot incoming',
        analysis_sources: {
          sql_lane: { id: 'sql_lane', lane: 'sql', summary: 'Rows fetched: 50', row_count: 50 },
        },
      },
      {
        event: 'analysis_ready',
        analysis: 'SQL snapshot updated',
        analysis_sources: {
          sql_lane: {
            id: 'sql_lane',
            lane: 'sql',
            summary: 'Rows fetched: 60',
            row_count: 60,
            columns: ['ticker', 'avg_return'],
          },
        },
      },
      {
        event: 'analysis_ready',
        analysis: 'Web insights ready',
        analysis_sources: {
          web_lane: {
            id: 'web_lane',
            lane: 'web',
            summary: 'Two corroborating snippets',
            snippet_count: 2,
          },
        },
      },
      {
        event: 'analysis_ready',
        analysis: 'Market snapshot ready',
        analysis_sources: {
          stock_lane: {
            id: 'stock_lane',
            lane: 'stock',
            summary: 'NVDA trending up',
            symbols: ['NVDA'],
            latest_close: 120.34,
            change_percent: 1.23,
          },
        },
      },
      {
        event: 'cohesive_result',
        analysis: 'Final blended narrative',
        sql: 'SELECT * FROM metrics',
        analysis_sources: {
          sql_lane: {
            id: 'sql_lane',
            lane: 'sql',
            summary: 'Rows fetched: 60',
            row_count: 60,
            columns: ['ticker', 'avg_return'],
          },
          web_lane: {
            id: 'web_lane',
            lane: 'web',
            summary: 'Two corroborating snippets',
            snippet_count: 2,
          },
          stock_lane: {
            id: 'stock_lane',
            lane: 'stock',
            summary: 'NVDA trending up',
            symbols: ['NVDA'],
            latest_close: 120.34,
            change_percent: 1.23,
          },
        },
      },
      { event: 'workflow_complete' },
    ];

    const { result } = renderHook(() => useAnalyticsMemoryStream('single-agent'));

    await act(async () => {
      await result.current.handleQuery('merge sources check');
    });

    const resultMessages = result.current.chatHistory.filter((message) => message.type === 'result');
    expect(resultMessages).toHaveLength(1);

    const sources = resultMessages[0].analysisSources;
    expect(sources).toBeTruthy();
    if (!sources) {
      return;
    }

    expect(Object.keys(sources)).toHaveLength(3);
    expect(sources.sql_lane?.rowCount).toBe(60);
    expect(sources.sql_lane?.columns).toEqual(['ticker', 'avg_return']);
    expect(sources.web_lane?.snippetCount).toBe(2);
    expect(sources.stock_lane?.symbols).toEqual(['NVDA']);
    expect(sources.stock_lane?.latestClose).toBeCloseTo(120.34);
    expect(sources.stock_lane?.changePercent).toBeCloseTo(1.23);

    (globalThis as any).__TEST_EVENTS__ = undefined;
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

  it('replaces duplicate revision payloads instead of appending new messages', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      { event: 'chart_patch', data: { ops: [{ op: 'set_chart_type', value: 'line' }], status: 'applied' } },
      { event: 'chart_patch', data: { ops: [{ op: 'set_chart_type', value: 'line' }], status: 'applied' } },
    ];

    await act(async () => {
      render(<HookHarness query="revise chart twice" flow="single-agent" />);
    });

    const resultCount = Number(screen.getByTestId('result-count').textContent);
    expect(resultCount).toBe(2);
    expect(screen.getByTestId('revision-mode').textContent).toBe('chart');
  });
});

describe('useAnalyticsMemoryStream guardrail finalization', () => {
  it('keeps decline copy visible and clears Output ready status', async () => {
    const declineCopy = 'I can\'t help with casual chat, but happy to dig into financial questions.';
    (globalThis as any).__TEST_EVENTS__ = [
      {
        event: 'finalization',
        banner: {
          title: 'Final Answer Ready',
          message: declineCopy,
          route: 'full_pipeline',
        },
        details: {
          banner: {
            message: declineCopy,
            route: 'full_pipeline',
          },
        },
      },
      { event: 'workflow_complete' },
    ];

    await act(async () => {
      render(<HookHarness query="how are you" flow="single-agent" />);
    });

    const content = screen.getByTestId('first-result-content').textContent || '';
    expect(content).toBe(declineCopy);
    expect(setCurrentStatusMock).toHaveBeenCalled();
    const lastCall = setCurrentStatusMock.mock.calls.at(-1);
    expect(lastCall?.[0]).toBe('');
  });
});

describe('useAnalyticsMemoryStream clarifications', () => {
  it('echoes timeframe clarification responses as chat messages', async () => {
    const request = {
      request_id: 'req-timeframe',
      session_id: 'session-clarify',
      slot: 'timeframe',
      question: 'Select a value for timeframe',
      type: 'single' as const,
      options: ['last 5 years', 'last 2 years', 'last 8 quarters', 'year to date'],
      default: null,
      reason: 'Additional context requested to tailor the analysis.',
      required: true,
      mode: 'single_agent',
    };

    const { result } = renderHook(() => useAnalyticsMemoryStream('single-agent'));

    await act(async () => {
      await result.current.submitClarification('last 8 quarters ', request as any);
    });

    const userMessages = result.current.chatHistory.filter((msg) => msg.type === 'user');
    expect(userMessages.at(-1)?.content).toBe('Timeframe: last 8 quarters');
    expect(apiService.post).toHaveBeenCalledWith(
      '/api/analytics/memory/clarify',
      expect.objectContaining({
        slot: 'timeframe',
        value: 'last 8 quarters',
      }),
    );
  });

  it('echoes free-text timeframe clarifications when custom value is provided', async () => {
    const request = {
      request_id: 'req-timeframe-custom',
      session_id: 'session-clarify',
      slot: 'timeframe',
      question: 'Select a value for timeframe',
      type: 'single' as const,
      options: ['last 5 years', 'last 2 years'],
      default: null,
      reason: 'Additional context requested to tailor the analysis.',
      required: true,
      mode: 'single_agent',
    };

    const { result } = renderHook(() => useAnalyticsMemoryStream('single-agent'));

    await act(async () => {
      await result.current.submitClarification('custom trailing 18 months', request as any);
    });

    const userMessages = result.current.chatHistory.filter((msg) => msg.type === 'user');
    expect(userMessages.at(-1)?.content).toBe('Timeframe: custom trailing 18 months');
    expect(apiService.post).toHaveBeenCalledWith(
      '/api/analytics/memory/clarify',
      expect.objectContaining({
        slot: 'timeframe',
        value: 'custom trailing 18 months',
      }),
    );
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

describe('useAnalyticsMemoryStream follow-up guidance', () => {
  it('tracks follow-up route stage and banner metadata', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      { event: 'follow_up_route', data: { route: 'reuse_sql', flow: 'planner-executor' } },
      {
        event: 'progress',
        data: {
          step: 'follow_up_route',
          banner: {
            title: 'Reusing Validated SQL',
            message: 'Keeping the last dataset so revisions publish faster without full regeneration.',
            route: 'reuse_sql',
          },
        },
      },
    ];

    await act(async () => {
      render(<HookHarness query="follow up summary" flow="planner-executor" />);
    });

    const stepIds = Array.from(screen.getByTestId('step-ids').querySelectorAll('li')).map((li) => li.textContent || '');
    expect(stepIds).toContain('follow_up_route:completed');
  });
});
