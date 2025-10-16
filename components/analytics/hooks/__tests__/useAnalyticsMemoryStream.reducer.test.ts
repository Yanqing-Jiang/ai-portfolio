import React from 'react';
import { act, renderHook, waitFor, render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { useAnalyticsMemoryStream } from '../useAnalyticsMemoryStream';
import { useAnalyticsStream } from '../useAnalyticsStream';
import { ProcessPanel } from '../../common/ProcessPanel';

vi.mock('../useAnalyticsStream', () => ({
  useAnalyticsStream: vi.fn(),
}));

describe('useAnalyticsMemoryStream metadata wiring', () => {
  let latestStreamCallback: ((payload: any) => void) | undefined;
  const startStreamMock = vi.fn();

  beforeEach(() => {
    latestStreamCallback = undefined;
    startStreamMock.mockImplementation(async (_endpoint: string, callback: (payload: any) => void) => {
      latestStreamCallback = callback;
    });
    vi.mocked(useAnalyticsStream).mockReturnValue({
      startStream: startStreamMock,
      resetState: vi.fn(),
      stopStream: vi.fn(),
      setError: vi.fn(),
      setCurrentStatus: vi.fn(),
      isLoading: false,
      error: null,
      currentStatus: '',
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('records lane reuse metadata and final-answer guidance', async () => {
    const { result } = renderHook(() => useAnalyticsMemoryStream());

    await act(async () => {
      await result.current.handleQuery('market outlook');
    });

    expect(startStreamMock).toHaveBeenCalled();
    expect(latestStreamCallback).toBeDefined();

    const ts = new Date().toISOString();
    act(() => {
      latestStreamCallback?.({
        event: 'status',
        step: 'market_phase',
        data: {
          step: 'market_phase',
          message: 'Reusing market context',
          lane: 'market',
          parallel_group: 'tool_fanout',
          reused: true,
          ts,
        },
      });
    });

    await waitFor(() => {
      const marketStep = result.current.processSteps.find((step) => step.id === 'market_phase');
      expect(marketStep).toBeDefined();
      expect(marketStep?.lane).toBe('market');
      expect(marketStep?.reused).toBe(true);
    });

    act(() => {
      latestStreamCallback?.({
        event: 'final_answer',
        data: {
          message: 'Final answer requires rerun.',
          final_answer_only: true,
          missing_components: ['sql', 'web'],
          follow_up_route: 'full_pipeline',
          analysis_available: false,
          flow_mode: 'planner-executor',
          ts,
        },
      });
    });

    await waitFor(() => {
      const finalStep = result.current.processSteps.find((step) => step.id === 'finalization');
      expect(finalStep?.finalAnswerOnly).toBe(true);
      expect(finalStep?.missingComponents).toEqual(['sql', 'web']);
      expect(finalStep?.followUpRoute).toBe('full_pipeline');
    });

    expect(result.current.followUpBanner?.finalAnswerOnly).toBe(true);
    expect(result.current.followUpBanner?.missingComponents).toEqual(['sql', 'web']);
    expect(result.current.followUpBanner?.analysisAvailable).toBe(false);
  });

  it('tracks market and web cached lanes and surfaces cached ledger labels', async () => {
    const { result } = renderHook(() => useAnalyticsMemoryStream());

    await act(async () => {
      await result.current.handleQuery('cached lane demo');
    });

    expect(startStreamMock).toHaveBeenCalled();
    expect(latestStreamCallback).toBeDefined();

    const ts = new Date().toISOString();

    act(() => {
      latestStreamCallback?.({
        event: 'status',
        step: 'market_agent',
        data: {
          step: 'market_agent',
          message: 'Reusing market receipts',
          lane: 'market',
          parallel_group: 'tool_fanout',
          reused: true,
          ts,
        },
      });
    });

    act(() => {
      latestStreamCallback?.({
        event: 'status',
        step: 'web_research_agent',
        data: {
          step: 'web_research_agent',
          message: 'Reusing web insights',
          lane: 'web',
          parallel_group: 'tool_fanout',
          reused: true,
          ts,
        },
      });
    });

    await waitFor(() => {
      const marketStep = result.current.processSteps.find((step) => step.id === 'market_agent');
      const webStep = result.current.processSteps.find((step) => step.id === 'web_research_agent');
      expect(marketStep?.lane).toBe('market');
      expect(marketStep?.reused).toBe(true);
      expect(webStep?.lane).toBe('web');
      expect(webStep?.reused).toBe(true);
    });

    const cachedSteps = result.current.processSteps
      .filter((step) => step.id === 'market_agent' || step.id === 'web_research_agent')
      .map((step) => ({
        ...step,
        status: 'completed',
      }));

    const panel = render(
      React.createElement(ProcessPanel, {
        steps: cachedSteps,
        flowMode: 'planner-executor',
        show: true,
        onClose: () => {},
        showVisualization: false,
      }),
    );

    expect(screen.getByText(/Market Insights \(cached\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Web Insights \(cached\)/i)).toBeInTheDocument();
    panel.unmount();
  });
});
