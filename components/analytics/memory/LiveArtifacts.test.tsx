import React from 'react';
import { render, screen } from '@testing-library/react';
import { LiveArtifacts } from './LiveArtifacts';

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
};

describe('LiveArtifacts', () => {
  it('renders nothing when no live data', () => {
    const { queryByText } = render(<LiveArtifacts {...baseProps} />);
    expect(queryByText(/Live Specialist Outputs/i)).toBeNull();
  });

  it('renders sql and analysis sections while streaming', () => {
    render(
      <LiveArtifacts
        {...baseProps}
        sqlQuery="SELECT 1"
        progressiveAnalysis="Draft narrative"
        isLoading={true}
      />,
    );
    expect(screen.getByText(/Live Specialist Outputs/i)).toBeInTheDocument();
    expect(screen.getByText(/Analysis Draft/i)).toBeInTheDocument();
    expect(screen.getByText(/SQL Snapshot/i)).toBeInTheDocument();
  });

  it('hides when analysis is finalized and not loading', () => {
    const { queryByText } = render(
      <LiveArtifacts
        {...baseProps}
        chartSpec={{ series: [] }}
        analysis="Final analysis ready"
        isLoading={false}
      />,
    );
    expect(queryByText(/Live Specialist Outputs/i)).toBeNull();
  });
});
