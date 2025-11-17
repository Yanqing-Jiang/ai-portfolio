// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAnalyticsSqlStream } from '../useAnalyticsSqlStream';

const {
  countUserInputMock,
  startStreamMock,
  setErrorMock,
  setCurrentStatusMock,
} = vi.hoisted(() => ({
  countUserInputMock: vi.fn(async () => ({
    success: true,
    data: {
      success: true,
      scope: 'next-gen-analytics-sql',
      identifier: 'user:test|next-gen-analytics-sql',
      base_identifier: 'user:test',
      current_usage: 1,
      limit: 5,
      remaining: 4,
      user_type: 'member',
    },
  })),
  startStreamMock: vi.fn(),
  setErrorMock: vi.fn(),
  setCurrentStatusMock: vi.fn(),
}));

vi.mock('../../../../services/apiService', () => ({
  apiService: {
    countUserInput: countUserInputMock,
  },
}));

vi.mock('../useAnalyticsStream', () => ({
  useAnalyticsStream: () => ({
    isLoading: false,
    error: '',
    currentStatus: '',
    statusTimestamp: null,
    setCurrentStatus: setCurrentStatusMock,
    setError: setErrorMock,
    startStream: startStreamMock,
    stopStream: vi.fn(),
    resetState: vi.fn(),
  }),
}));

vi.mock('../utils', () => ({
  applyChartOps: (chart: unknown) => chart,
}));

beforeEach(() => {
  countUserInputMock.mockClear();
  startStreamMock.mockReset();
  setErrorMock.mockClear();
  setCurrentStatusMock.mockClear();
});

describe('useAnalyticsSqlStream', () => {
  it('pre-checks the rate limit before starting a stream', async () => {
    const { result } = renderHook(() => useAnalyticsSqlStream());

    await act(async () => {
      await result.current.handleQuery('NVDA revenue 2024');
    });

    expect(countUserInputMock).toHaveBeenCalledWith({ scope: 'next-gen-analytics-sql' });
    expect(startStreamMock).toHaveBeenCalledTimes(1);
    expect(setErrorMock).not.toHaveBeenCalled();
  });

  it('surfaces rate-limit errors and skips the stream', async () => {
    countUserInputMock.mockResolvedValueOnce({
      success: false,
      error: 'Rate limit exceeded.',
    });

    const { result } = renderHook(() => useAnalyticsSqlStream());

    await act(async () => {
      await result.current.handleQuery('AMD vs NVDA market share');
    });

    expect(countUserInputMock).toHaveBeenCalledWith({ scope: 'next-gen-analytics-sql' });
    expect(startStreamMock).not.toHaveBeenCalled();
    expect(setErrorMock).toHaveBeenCalledWith('Rate limit exceeded.');
    expect(setCurrentStatusMock).toHaveBeenCalledWith('Error: Rate limit exceeded.');
  });

  it('updates flow mode when telemetry metadata is streamed', async () => {
    startStreamMock.mockImplementationOnce(async (_endpoint: string, onEvent: (data: any) => void) => {
      onEvent({ event: 'status', data: { message: 'starting', mode: 'multi_agent' } });
      onEvent({ event: 'done', data: {} });
      return 'mock-stream';
    });

    const { result } = renderHook(() => useAnalyticsSqlStream());

    await act(async () => {
      await result.current.handleQuery('Check flow mode');
    });

    expect(result.current.flowMode).toBe('multi-agent');
  });
});
