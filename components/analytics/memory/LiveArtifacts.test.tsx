import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import { LiveArtifacts } from './LiveArtifacts';

vi.mock('../common/ChartCard', () => ({
  ChartCard: () => <div data-testid="chart-card">Mock Chart</div>,
}));

const baseProps = {
  chartSpec: null,
  dataSample: null,
  sqlQuery: '',
  analysis: '',
  progressiveAnalysis: '',
  progressiveText: '',
  webSearch: null,
  stockWidget: null,
  isLoading: false,
  flowMode: 'multi-agent' as const,
  latencyGuardrail: null,
};

describe('LiveArtifacts', () => {
  it('renders nothing when no live data', () => {
    const { container } = render(<LiveArtifacts {...baseProps} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders sql and analysis sections while streaming', () => {
    render(
      <LiveArtifacts
        {...baseProps}
        sqlQuery="SELECT 1"
        progressiveAnalysis="Draft narrative"
        chartSpec={{ series: [{ data: [1, 2, 3] }] }}
        isLoading={true}
      />,
    );
    expect(screen.getByText(/Supervisor Narrative Draft/i)).toBeInTheDocument();
    expect(screen.getByTestId('chart-card')).toBeInTheDocument();
    expect(screen.getByText(/Generated SQL Query/i)).toBeInTheDocument();
    expect(screen.getByText(/Multi-Agent Supervisor Flow/i)).toBeInTheDocument();
  });

  it('shows final analysis overview when persisted', () => {
    render(
      <LiveArtifacts
        {...baseProps}
        analysis="Deep dive narrative"
        analysisOverview={{
          tldr: 'Quarterly beat on revenue.',
          highlights: ['Revenue up 12% y/y'],
          keyNumbers: ['Operating margin expanded 210 bps'],
          riskWatch: ['FX volatility remains a headwind'],
          nextSteps: ['Monitor Q4 demand mix'],
          evidence: [
            {
              sourceUrl: 'https://example.com/nvda',
              title: 'NVIDIA Q2 2025 earnings beat',
              snippet: 'Revenue up 12% with margin expansion.',
              confidence: 0.82,
            },
          ],
        }}
        latencyGuardrail={{
          status: 'violation',
          violations: ['p50_ms'],
          thresholds: { p50_ms: 500, p95_ms: 1500 },
        }}
        webSearch={{ summary: 'Guardrail check', snippets: [{ snippet: 'Sample snippet' }], latencyStats: { p50_ms: 620, total_ms: 900 } } as any}
        persistOnComplete={true}
        isLoading={false}
      />,
    );
    expect(screen.getAllByText(/Financial Analysis/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Quick Take/i)).toBeInTheDocument();
    expect(screen.getByText(/Quarterly beat on revenue/i)).toBeInTheDocument();
    expect(screen.getByText(/Key Numbers/i)).toBeInTheDocument();
    expect(screen.getByText(/Risk Watch/i)).toBeInTheDocument();
    expect(screen.getByText(/Next Steps/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /NVIDIA Q2 2025 earnings beat/i })).toHaveAttribute('href', 'https://example.com/nvda');
    expect(screen.getByText(/Guardrail: Exceeded/i)).toBeInTheDocument();
    expect(screen.getByText(/Confidence: 82%/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Supervisor Narrative/i).length).toBeGreaterThan(0);
  });

  it('hides when analysis is finalized and not loading', () => {
    const { container } = render(
      <LiveArtifacts
        {...baseProps}
        chartSpec={{ series: [] }}
        analysis="Final analysis ready"
        isLoading={false}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders supplemental specialist cards when provided', () => {
    render(
      <LiveArtifacts
        {...baseProps}
        isLoading={true}
        specialistCards={[
          {
            type: 'news_brief',
            summary: 'New accessory signal',
            topic: 'Earnings follow-up',
            snippets: [{ title: 'First snippet' }],
          },
        ]}
      />,
    );
    expect(screen.getByText(/Specialist Spotlight/i)).toBeInTheDocument();
    expect(screen.getByText(/New accessory signal/i)).toBeInTheDocument();
  });

  it('shows fallback message when no evidence provided', () => {
    render(
      <LiveArtifacts
        {...baseProps}
        analysis="Narrative"
        analysisOverview={{
          tldr: 'Summary with no sources.',
        }}
        persistOnComplete={true}
      />,
    );
    expect(
      screen.getByText(/No grounded sources returned. Consider re-running web research/i),
    ).toBeInTheDocument();
  });
});
