import { act, renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

import { useAnalyticsMemoryStream } from '../useAnalyticsMemoryStream';
import { useAnalyticsStream } from '../useAnalyticsStream';

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
});
