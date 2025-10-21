// @vitest-environment jsdom
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ChatMessage } from '../types';
import MemoryAnalyticsPage from './Page';

const mockUseAnalyticsMemoryStream = vi.fn();

vi.mock('../hooks', () => ({
  useAnalyticsMemoryStream: (...args: unknown[]) => mockUseAnalyticsMemoryStream(...args),
}));

vi.mock('../common', () => ({
  AnalysisCard: () => <div data-testid="analysis-card" />,
  ProcessPanel: () => <div data-testid="process-panel" />,
}));

vi.mock('./', () => ({
  ChatHistory: () => <div data-testid="chat-history" />,
}));

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  },
}));

const buildChatMessage = (overrides: Partial<ChatMessage> = {}): ChatMessage => ({
  id: overrides.id ?? 'msg-1',
  type: overrides.type ?? 'user',
  content: overrides.content ?? 'Hello world',
  timestamp: overrides.timestamp ?? new Date().toISOString(),
  flowMode: overrides.flowMode,
  clarifications: overrides.clarifications,
  answers: overrides.answers,
  analysis: overrides.analysis,
  progressiveAnalysis: overrides.progressiveAnalysis,
  progressiveText: overrides.progressiveText,
  chartSpec: overrides.chartSpec,
  sqlQuery: overrides.sqlQuery,
  dataSample: overrides.dataSample,
  stockWidgetConfig: overrides.stockWidgetConfig ?? null,
  toolFanoutManifest: overrides.toolFanoutManifest,
  toolFanoutResults: overrides.toolFanoutResults,
  webSearch: overrides.webSearch ?? null,
  analysisOverview: overrides.analysisOverview ?? null,
  analysisSources: overrides.analysisSources ?? null,
  banner: overrides.banner ?? null,
  specialistCards: overrides.specialistCards ?? [],
  latencyGuardrail: overrides.latencyGuardrail ?? null,
});

const buildBaseStreamState = () => ({
  chatHistory: [] as ChatMessage[],
  chartSpec: null,
  analysis: '',
  analysisOverview: null,
  analysisSources: null,
  sqlQuery: '',
  dataSample: null,
  streamingText: '',
  webSearch: null,
  stockWidget: null,
  progressiveAnalysis: '',
  progressiveText: '',
  singleAgentFanout: null,
  followUpBanner: null,
  slotStatuses: {},
  slotFollowups: [],
  snapshotReuse: null,
  specialistCards: [],
  latencyGuardrail: null,
  isLoading: false,
  currentStatus: '',
  statusTimestamp: null,
  processSteps: [],
  revisionMode: 'none' as const,
  handleQuery: vi.fn(),
  submitClarification: vi.fn(),
  stopAnalysis: vi.fn(),
});

type StreamState = ReturnType<typeof buildBaseStreamState>;

const buildStreamState = (overrides: Partial<StreamState> = {}): StreamState => ({
  ...buildBaseStreamState(),
  ...overrides,
});

describe('MemoryAnalyticsPage flow selector locking', () => {
  beforeEach(() => {
    mockUseAnalyticsMemoryStream.mockReset();
  });

  it('keeps the flow selector enabled before the first query', () => {
    mockUseAnalyticsMemoryStream.mockReturnValue(buildBaseStreamState());

    render(<MemoryAnalyticsPage />);

    const select = screen.getByRole('combobox');
    expect(select).not.toBeDisabled();
  });

  it('locks the flow selector when chat history already contains messages', async () => {
    mockUseAnalyticsMemoryStream.mockReturnValue(
      buildStreamState({
        chatHistory: [buildChatMessage()],
      }),
    );

    render(<MemoryAnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByRole('combobox')).toBeDisabled();
    });

    expect(screen.getByRole('combobox').getAttribute('title')).toMatch(/locked/i);
  });

  it('locks the flow selector when streaming text is present', async () => {
    mockUseAnalyticsMemoryStream.mockReturnValue(
      buildStreamState({
        streamingText: 'Drafting response...',
      }),
    );

    render(<MemoryAnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByRole('combobox')).toBeDisabled();
    });
  });
});
