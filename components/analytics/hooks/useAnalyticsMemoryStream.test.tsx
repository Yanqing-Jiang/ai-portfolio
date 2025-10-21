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
  const { handleQuery, chatHistory, processSteps, revisionMode, analysisBundle, specialistCards } = useAnalyticsMemoryStream(flow);
  const firstResult = chatHistory.find((m) => m.type === 'result');
  const resultMessages = chatHistory.filter((m) => m.type === 'result');
  const latestResult = resultMessages[resultMessages.length - 1];

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
      <div data-testid="first-result-has-chart">{firstResult?.chartSpec ? 'yes' : 'no'}</div>
      <div data-testid="latest-result-has-chart">{latestResult?.chartSpec ? 'yes' : 'no'}</div>
      <ul data-testid="step-ids">
        {processSteps.map((step) => (
          <li key={step.id}>{`${step.id}:${step.status}`}</li>
        ))}
      </ul>
      <div data-testid="first-result-evidence">{firstResult?.analysisOverview ? JSON.stringify(firstResult.analysisOverview.evidence || []) : ''}</div>
      <div data-testid="latency-guardrail-status">{firstResult?.latencyGuardrail?.status ?? ''}</div>
      <div data-testid="analysis-bundle">{analysisBundle ? JSON.stringify(analysisBundle) : ''}</div>
      <div data-testid="specialist-card-count">{specialistCards.length}</div>
      <div data-testid="specialist-card-order">
        {specialistCards.map((card) => `${card.type ?? 'unknown'}:${card.revision ? 'rev' : 'base'}`).join('|')}
      </div>
      <div data-testid="specialist-card-revision-ids">
        {specialistCards.map((card) => card.revisionId ?? '').join('|')}
      </div>
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


  it('prioritises accessory specialist cards and suppresses duplicate payloads', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      {
        event: 'tool_parallel_result',
        data: {
          specialist_card: {
            type: 'stock_widget',
            lane: 'market',
            title: 'Market Snapshot',
            summary: 'Realtime prices',
            payload_hash: 'stock-hash-1',
          },
          lane: 'market',
        },
      },
      {
        event: 'tool_parallel_result',
        data: {
          specialist_card: {
            type: 'web_context',
            lane: 'web',
            title: 'Web Research',
            summary: 'Breaking headlines',
            payload_hash: 'web-hash-1',
          },
          lane: 'web',
        },
      },
      {
        event: 'tool_parallel_result',
        data: {
          specialist_card: {
            type: 'stock_widget',
            lane: 'market',
            title: 'Market Snapshot',
            summary: 'Realtime prices',
            payload_hash: 'stock-hash-1',
          },
          lane: 'market',
        },
      },
      { event: 'sql_ready', data: { sql: 'select 1' } },
    ];

    await act(async () => {
      render(<HookHarness query="prioritize accessories" flow="planner-executor" />);
    });

    const cardCount = Number(screen.getByTestId('specialist-card-count').textContent);
    expect(cardCount).toBe(2);
    const order = screen.getByTestId('specialist-card-order').textContent;
    expect(order?.startsWith('stock_widget')).toBe(true);
    expect(order).toContain('web_context');
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
      {
        event: 'chart_generated',
        data: {
          chart_spec: {
            series: [{ type: 'line', data: [1, 2, 3] }],
            meta: { chartDesign: { chart_type: 'line' } },
          },
        },
      },
      { event: 'chart_patch', data: { ops: [{ op: 'set_chart_type', value: 'bar' }], status: 'applied' } },
    ];

    await act(async () => {
      render(<HookHarness query="revise chart" flow="single-agent" />);
    });

    const stepIds = Array.from(screen.getByTestId('step-ids').querySelectorAll('li')).map((li) => li.textContent || '');
    expect(stepIds).toContain('chart_revision:completed');

    const resultCount = Number(screen.getByTestId('result-count').textContent);
    expect(resultCount).toBe(2);
    expect(screen.getByTestId('first-result-has-chart').textContent).toBe('no');
    expect(screen.getByTestId('latest-result-has-chart').textContent).toBe('yes');

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
      {
        event: 'chart_generated',
        data: {
          chart_spec: {
            series: [{ type: 'line', data: [3, 2, 1] }],
            meta: { chartDesign: { chart_type: 'line' } },
          },
        },
      },
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
      { event: 'follow_up_route', route: 'full_pipeline' },
      { event: 'done' },
      { event: 'workflow_complete' },
    ];

    await act(async () => {
      render(<HookHarness query="how are you" flow="single-agent" />);
    });

    const content = screen.getByTestId('first-result-content').textContent || '';
    expect(content).toBe(declineCopy);
    expect(setCurrentStatusMock).toHaveBeenCalled();
      const statusCalls = setCurrentStatusMock.mock.calls.map((call) => call[0]);
      expect(statusCalls.at(-1)).toBe('');
  });

  it('preserves guardrail finalization when workflow completes before done', async () => {
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
      { event: 'follow_up_route', route: 'full_pipeline' },
      { event: 'workflow_complete' },
      { event: 'done' },
    ];

    await act(async () => {
      render(<HookHarness query="guardrail order" flow="single-agent" />);
    });

    const content = screen.getByTestId('first-result-content').textContent || '';
    expect(content).toBe(declineCopy);
    const statusCalls = setCurrentStatusMock.mock.calls.map((call) => call[0]);
    expect(statusCalls.at(-1)).toBe('');
    expect(statusCalls).not.toContain('Output ready');
  });

  it('renders decline message when final_answer arrives without prior results', async () => {
    const declineCopy = 'Please ask about a company, ticker, or financial metric so I can help.';
    (globalThis as any).__TEST_EVENTS__ = [
      {
        event: 'classification_started',
        model: 'gpt-5-nano-2025-08-07',
        ts: new Date().toISOString(),
      },
      {
        event: 'classification_complete',
        is_financial: false,
        category: 'general_conversation',
        confidence: 0.95,
        ts: new Date().toISOString(),
      },
      {
        event: 'final_answer',
        message: declineCopy,
        follow_up_route: 'full_pipeline',
      },
      {
        event: 'workflow_complete',
        total_elapsed_ms: 120,
      },
      { event: 'done' },
    ];

    await act(async () => {
      render(<HookHarness query="how are you" flow="single-agent" />);
    });

    const content = screen.getByTestId('first-result-content').textContent || '';
    expect(content).toBe(declineCopy);
    const statusCalls = setCurrentStatusMock.mock.calls.map((call) => call[0]);
    expect(statusCalls.at(-1)).toBe('');
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

describe('useAnalyticsMemoryStream card ordering', () => {
  it('reorders specialist cards when accessories finish before sql and chart lanes', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      {
        event: 'stock_ready',
        data: {
          ts: '2025-10-21T00:00:01.000Z',
          lane: 'market',
          specialist_card: {
            type: 'stock_widget',
            lane: 'market',
            title: 'Stock Chart',
            summary: 'Latest price action',
            state: 'ready',
            ready: true,
            ts: '2025-10-21T00:00:01.000Z',
          },
        },
      },
      {
        event: 'web_ready',
        data: {
          ts: '2025-10-21T00:00:02.000Z',
          lane: 'web',
          specialist_card: {
            type: 'web_context',
            lane: 'web',
            title: 'Market Research',
            summary: 'Peer commentary',
            state: 'ready',
            ready: true,
            ts: '2025-10-21T00:00:02.000Z',
          },
        },
      },
      {
        event: 'chart_ready',
        data: {
          ts: '2025-10-21T00:00:03.000Z',
          lane: 'chart',
          specialist_card: {
            type: 'chart_builder',
            lane: 'chart',
            title: 'SQL Chart',
            summary: 'Revenue vs. growth',
            state: 'ready',
            ready: true,
            ts: '2025-10-21T00:00:03.000Z',
          },
        },
      },
      {
        event: 'analysis_ready',
        data: {
          ts: '2025-10-21T00:00:04.000Z',
          lane: 'analysis',
          specialist_card: {
            type: 'analysis_summary',
            lane: 'analysis',
            title: 'Financial Analysis',
            summary: 'Highlights from the three data sources',
            state: 'ready',
            ready: true,
            ts: '2025-10-21T00:00:04.000Z',
          },
        },
      },
      {
        event: 'sql_ready',
        data: {
          ts: '2025-10-21T00:00:05.000Z',
          lane: 'sql',
          specialist_card: {
            type: 'sql_executor',
            lane: 'sql',
            title: 'Generated SQL Query',
            summary: 'Inspect or reuse the dataset',
            state: 'ready',
            ready: true,
            ts: '2025-10-21T00:00:05.000Z',
          },
        },
      },
      { event: 'workflow_complete', total_elapsed_ms: 320 },
    ];

    await act(async () => {
      render(<HookHarness query="priority ordering" flow="planner-executor" />);
    });

    const order = screen.getByTestId('specialist-card-order').textContent ?? '';
    const tokens = order.split('|').filter(Boolean);
    expect(tokens).toHaveLength(5);
    expect(tokens[0]).toContain('chart_builder');
    expect(tokens[1]).toContain('analysis_summary');
    expect(tokens[2]).toContain('stock_widget');
    expect(tokens[3]).toContain('web_context');
    expect(tokens[4]).toContain('sql_executor');
  });
});

describe('useAnalyticsMemoryStream revisions', () => {
  it('streams stock revision cards ahead of sql revisions', async () => {
    (globalThis as any).__TEST_EVENTS__ = [
      { event: 'revision_request', data: { revision_id: 'rev-1', lanes: ['stock'] } },
      {
        event: 'stock_revision_ready',
        data: {
          revision_id: 'rev-1',
          lane: 'market',
          stock_widget: { symbols: ['NVDA'], ready: true },
          specialist_card: {
            type: 'stock_widget',
            lane: 'market',
            title: 'Stock Chart',
            summary: 'Updated NVDA trend',
          },
        },
      },
      {
        event: 'sql_revision_ready',
        data: {
          revision_id: 'rev-1',
          lane: 'sql',
          sql: 'SELECT 1',
          specialist_card: {
            type: 'sql_executor',
            lane: 'sql',
            title: 'SQL Ready',
            summary: 'Rows: 10',
          },
        },
      },
      { event: 'workflow_complete', total_elapsed_ms: 120 },
    ];

    await act(async () => {
      render(<HookHarness query="targeted stock revision" flow="planner-executor" />);
    });

    const count = screen.getByTestId('specialist-card-count').textContent ?? '0';
    expect(count).toBe('2');
    const order = screen.getByTestId('specialist-card-order').textContent ?? '';
    expect(order.split('|')[0]).toContain('stock_widget');
    const revisions = screen.getByTestId('specialist-card-revision-ids').textContent ?? '';
    expect(revisions.split('|')[0]).toBe('rev-1');
  });

  it('dedupes identical stock revision payloads', async () => {
    const stockEvent = {
      revision_id: 'rev-2',
      lane: 'market',
      stock_widget: { symbols: ['AAPL'], ready: true },
      specialist_card: {
        type: 'stock_widget',
        lane: 'market',
        title: 'Stock Chart',
        summary: 'Updated Apple snapshot',
      },
    };
    (globalThis as any).__TEST_EVENTS__ = [
      { event: 'revision_request', data: { revision_id: 'rev-2', lanes: ['stock'] } },
      { event: 'stock_revision_ready', data: stockEvent },
      { event: 'stock_revision_ready', data: stockEvent },
      { event: 'workflow_complete', total_elapsed_ms: 90 },
    ];

    await act(async () => {
      render(<HookHarness query="dedupe stock revision" flow="planner-executor" />);
    });

    expect(screen.getByTestId('specialist-card-count').textContent).toBe('1');
    const order = screen.getByTestId('specialist-card-order').textContent ?? '';
    expect(order).toContain('stock_widget:rev');
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
