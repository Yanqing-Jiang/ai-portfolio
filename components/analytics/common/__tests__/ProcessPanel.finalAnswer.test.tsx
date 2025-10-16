import { render, screen } from '@testing-library/react';

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
  });
});
