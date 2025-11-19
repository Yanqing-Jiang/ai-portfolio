import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { ProcessStep, FollowUpBanner } from '../../types';
import { ProcessPanel } from '../ProcessPanel';

const baseStep: ProcessStep = {
  id: 'market_phase',
  name: 'Market Phase',
  status: 'completed',
  thinking: [],
  details: {},
};

describe('ProcessPanel cached and final-answer presentation', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('surfaces cached badges and guided rerun messaging', () => {
    const steps: ProcessStep[] = [
      {
        ...baseStep,
        lane: 'market',
        parallelGroup: 'market',
        reused: true,
      },
      {
        id: 'finalization',
        name: 'Finalization',
        status: 'completed',
        thinking: [],
        finalAnswerOnly: true,
        missingComponents: ['sql'],
        analysisAvailable: false,
        details: {
          banner: {
            title: 'Guided Final Answer',
            message: 'Final answer requires rerun.',
            route: 'full_pipeline',
            finalAnswerOnly: true,
            missingComponents: ['sql'],
            analysisAvailable: false,
          } satisfies FollowUpBanner,
          final_answer_only: true,
          missing_components: ['sql'],
          analysis_available: false,
        },
      },
    ];

    const followUpBanner: FollowUpBanner = {
      title: 'Guided Final Answer',
      message: 'Final answer requires rerun.',
      route: 'full_pipeline',
      finalAnswerOnly: true,
      missingComponents: ['sql'],
      analysisAvailable: false,
    };

    render(
      <ProcessPanel
        steps={steps}
        flowMode="planner-executor"
        show
        onClose={() => {}}
        showVisualization={false}
        followUpBanner={followUpBanner}
      />,
    );

    expect(screen.getAllByText(/Cached/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Final Answer Only/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Missing: Sql/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Analysis Pending/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Guided Final Answer/i).length).toBeGreaterThan(0);
    expect(screen.getByTestId('final-answer-banner-dismiss')).toBeInTheDocument();
  });

  it('persists final-answer banner dismissal across remounts', async () => {
    const user = userEvent.setup();
    const steps: ProcessStep[] = [
      {
        ...baseStep,
        lane: 'market',
        parallelGroup: 'market',
        reused: true,
      },
    ];

    const followUpBanner: FollowUpBanner = {
      title: 'Guided Final Answer',
      message: 'Final answer requires rerun.',
      route: 'full_pipeline',
      finalAnswerOnly: true,
      missingComponents: ['sql'],
      analysisAvailable: false,
    };

    const { unmount } = render(
      <ProcessPanel
        steps={steps}
        flowMode="planner-executor"
        show
        onClose={() => {}}
        showVisualization={false}
        followUpBanner={followUpBanner}
      />,
    );

    const dismissButton = screen.getByTestId('final-answer-banner-dismiss');
    await user.click(dismissButton);

    await waitFor(() => {
      expect(screen.queryByText(/Guided Final Answer/i)).not.toBeInTheDocument();
    });

    expect(window.localStorage.getItem('aa.finalAnswerOnlyDismissed')).toBeTruthy();

    unmount();

    render(
      <ProcessPanel
        steps={steps}
        flowMode="planner-executor"
        show
        onClose={() => {}}
        showVisualization={false}
        followUpBanner={followUpBanner}
      />,
    );

    expect(screen.queryByText(/Guided Final Answer/i)).not.toBeInTheDocument();
  });

  it('renders agent evidence badges', () => {
    const steps: ProcessStep[] = [
      {
        ...baseStep,
        lane: 'analysis',
        parallelGroup: 'analysis',
        status: 'completed',
      },
    ];
    render(
      <ProcessPanel
        steps={steps}
        flowMode="multi-agent"
        show
        onClose={() => {}}
        showVisualization={false}
        agentEvidence={{ status: 'agent_fallback', reason: 'cached_revision' }}
      />,
    );
    expect(screen.getByText(/Agent Fallback/i)).toBeInTheDocument();
  });
});
