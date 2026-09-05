import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

import { FortuneResultShell } from '../../components/generativeUiDashboard/FortuneResultShell';
import { GuardrailBanner } from '../../components/generativeUiDashboard/fortune/shared/GuardrailBanner';
import { GlassBoxPanel } from '../../components/generativeUiDashboard/fortune/shared/GlassBoxPanel';
import { HarnessView } from '../../components/generativeUiDashboard/fortune/shared/HarnessView';
import { buildOutlook, supportBand } from '../../components/generativeUiDashboard/fortune/shared/outlook';
import {
  detectReadingFailure,
  friendlyFailureMessage,
  GENERIC_FAILURE_MESSAGE,
} from '../../components/generativeUiDashboard/fortune/shell/readingStatus';
import { fortuneClient } from '../../components/generativeUiDashboard/lib/fortuneClient';
import { useFortuneStore } from '../../components/generativeUiDashboard/stores/fortuneStore';
import type { FortuneDataModel } from '../../components/generativeUiDashboard/lib/fortuneTypes';

const FINDING = {
  topic: '2028–2029: Turn expertise into stronger leverage',
  opportunity: 'Your specialist skills attract better projects. Bargaining power grows.',
  risk: 'Too much independence may weaken cooperation.',
  action: 'Document your methods and negotiate from measurable contributions.',
  alternative: 'Progress may come through a partnership instead.',
  technical_basis: 'Eating God visible; 2028 branch combines with the month branch.',
  evidence_paths: ['/ten_gods/9', '/ziwei/palaces/1'],
  agreement: 'mixed' as const,
  start_year: 2028,
  end_year: 2029,
  age_at_birthday: [38, 39],
};

const COMPLETE_MODEL: FortuneDataModel = {
  meta: { status: 'complete' },
  narrative: {
    tldr: 'Career responsibility rises in 2027.',
    isComplete: true,
    yearPredictions: [
      { year: 2028, prediction: 'Document results and build alliances.', confidence: 0.78 },
      { year: 2029, prediction: 'Negotiate from measurable contributions.', confidence: 0.76 },
      { year: 2030, prediction: 'Redesign career structures carefully.', confidence: 0.82 },
    ],
  },
  wish: { verdict: { title: 'Strong momentum', score: 78, summary: 'Five favourable years.' } },
  harness: { brief: { findings: [FINDING], limitations: ['Not guaranteed events.'] } },
};

function snapshot(status: string, dataModel: FortuneDataModel) {
  return {
    fortune_id: 'fortune-1',
    status,
    metadata: { created_at: '2026-09-05T00:00:00Z', function_id: 'wish' },
    data: {},
    data_model: dataModel as unknown as Record<string, unknown>,
  };
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
}

function renderResult(initialEntry = '/project/fortune-agent/custom-wish/fortune-1') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <LocationProbe />
      <Routes>
        <Route
          path="/project/fortune-agent/custom-wish/:fortuneId"
          element={<FortuneResultShell functionId="wish" />}
        />
        <Route
          path="/project/fortune-agent/custom-wish"
          element={<div>Custom wish intake</div>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('outlook guidance', () => {
  it('groups year predictions into their supporting finding window with server ages', () => {
    const entries = buildOutlook(COMPLETE_MODEL);

    expect(entries).toHaveLength(2);
    expect(entries[0]).toMatchObject({
      yearLabel: '2028–2029',
      ageLabel: 'Age 38–39',
      title: 'Turn expertise into stronger leverage',
      possible: 'Your specialist skills attract better projects.',
      risk: FINDING.risk,
    });
    expect(entries[0].steps.map((step) => step.year)).toEqual([2028, 2029]);
    // 2030 has no matching finding: a year card, but no invented age or event.
    expect(entries[1]).toMatchObject({ yearLabel: '2030', ageLabel: undefined, possible: undefined });
  });

  it('borrows the generated insight icon and tagline for a year without a dated finding', () => {
    const [, standalone] = buildOutlook({
      ...COMPLETE_MODEL,
      narrative: {
        ...COMPLETE_MODEL.narrative,
        yearPredictions: COMPLETE_MODEL.narrative!.yearPredictions!.map((item) =>
          item.year === 2030 ? { ...item, evidenceRefs: ['/notable_annual_pillars/3'] } : item,
        ),
        insights: [{
          id: 'careful_restructuring', icon: '🔄', heading: 'Prepare Flexibly',
          tagline: 'Later changes favor deliberate redesign.',
          bullets: [], citations: ['/notable_annual_pillars/3'],
        }],
      },
    });

    expect(standalone).toMatchObject({
      yearLabel: '2030',
      icon: '🔄',
      title: 'Later changes favor deliberate redesign.',
    });
  });

  it('labels whose birthday ages these are when a second chart is present', () => {
    const [entry] = buildOutlook(COMPLETE_MODEL, { personLabel: 'Person A' });
    expect(entry.ageLabel).toBe('Person A age 38–39');
  });

  it('uses only supplied endpoint ages when guidance covers part of a finding', () => {
    const model = {
      ...COMPLETE_MODEL,
      narrative: { yearPredictions: [{ year: 2029, prediction: 'Negotiate carefully.', confidence: 0.76 }] },
    };
    expect(buildOutlook(model)[0]).toMatchObject({ yearLabel: '2029', ageLabel: 'Age 39' });
    const widerWindow = {
      ...model,
      harness: { brief: { findings: [{ ...FINDING, end_year: 2030, age_at_birthday: [38, 40] }], limitations: [] } },
    };
    expect(buildOutlook(widerWindow)[0].ageLabel).toBeUndefined();
  });

  it('returns nothing for legacy readings without generated year predictions', () => {
    expect(buildOutlook({ retrodictions: { items: [{ year: 1994, prediction: 'x', confidence: 0.85 }] } })).toEqual([]);
  });

  it('describes heuristic support as support, never as a probability', () => {
    expect(supportBand(0.84).label).toBe('Strong support');
    expect(supportBand(0.7).label).toBe('Moderate support');
    expect(supportBand(0.4).label).toBe('Limited support');
  });
});

describe('reading failure detection', () => {
  it('keeps raw pointer and SDK errors out of audience copy', () => {
    expect(friendlyFailureMessage('/data/narrative/insights/0 failed to validate')).toBe(GENERIC_FAILURE_MESSAGE);
    expect(friendlyFailureMessage('/ten_gods/99 failed to validate')).toBe(GENERIC_FAILURE_MESSAGE);
    expect(friendlyFailureMessage('Traceback (most recent call last)')).toBe(GENERIC_FAILURE_MESSAGE);
    expect(friendlyFailureMessage('')).toBe(GENERIC_FAILURE_MESSAGE);
    expect(friendlyFailureMessage('The reading timed out before it finished.'))
      .toBe('The reading timed out before it finished.');
  });

  it('treats an errored meta on a legacy partial snapshot as a stopped run', () => {
    expect(detectReadingFailure({
      status: 'streaming',
      dataModel: { meta: { status: 'error', error_message: 'The reading timed out.' } },
    })).toEqual({ kind: 'failed', message: 'The reading timed out.' });
  });

  it('distinguishes a withheld reading from a stopped one', () => {
    expect(detectReadingFailure({
      status: 'complete',
      dataModel: { guardrail: { message: 'This request cannot be answered.', level: 'error' } },
    })?.kind).toBe('rejected');
    expect(detectReadingFailure({
      status: 'complete', dataModel: { guardrail: { level: 'critical', message: 'Reading withheld.' } },
    })?.kind).toBe('rejected');
    expect(detectReadingFailure({ status: 'complete', dataModel: COMPLETE_MODEL })).toBeNull();
  });
});

it('renders the backend critical guardrail level without a banner crash', () => {
  render(<GuardrailBanner guardrail={{ level: 'critical', message: 'Reading withheld.' }} />);
  expect(screen.getByRole('status')).toHaveTextContent('Reading withheld.');
});

describe('FortuneResultShell terminal states', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useFortuneStore.getState().reset();
    vi.spyOn(fortuneClient, 'getConversation').mockResolvedValue({ fortune_id: 'fortune-1', turns: [] });
    vi.spyOn(fortuneClient, 'getTrace').mockResolvedValue({ fortune_id: 'fortune-1', run_id: null, events: [] });
  });

  it('renders a friendly stopped state with working recovery and no loading affordances', async () => {
    vi.spyOn(fortuneClient, 'getFortune').mockResolvedValue(snapshot('error', {
      meta: { status: 'error', error_message: 'The reading stopped while writing.' },
      harness: { brief: { findings: [FINDING], limitations: [] } },
    }));

    renderResult();

    const alert = await screen.findByRole('alert');
    expect(within(alert).getByText('The reading stopped while writing.')).toBeInTheDocument();
    expect(screen.getByText('Stopped')).toBeInTheDocument();
    expect(screen.queryByText('Reading in progress…')).not.toBeInTheDocument();
    expect(screen.queryByText(/Verdict Finalized|Weighing factor/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Start a new reading/ }));
    await waitFor(() => expect(screen.getByText('Custom wish intake')).toBeInTheDocument());
  });

  it('falls back to generic copy for an empty error message and keeps the explorer reachable', async () => {
    vi.spyOn(fortuneClient, 'getFortune').mockResolvedValue(snapshot('error', {
      meta: { status: 'error', error_message: '' },
      harness: { brief: { findings: [FINDING], limitations: [] } },
    }));

    renderResult();

    const alert = await screen.findByRole('alert');
    expect(within(alert).getByText(GENERIC_FAILURE_MESSAGE)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /Why/ }));
    expect(screen.getByRole('button', { name: 'Explore backend' })).toBeInTheDocument();
  });

  it('disables Ask on a stopped reading with a reason', async () => {
    vi.spyOn(fortuneClient, 'getFortune').mockResolvedValue(snapshot('error', {
      meta: { status: 'error', error_message: 'The reading stopped while writing.' },
    }));

    renderResult('/project/fortune-agent/custom-wish/fortune-1?tab=Ask');

    const composer = await screen.findByLabelText('Ask a question about this reading');
    expect(composer).toBeDisabled();
    expect(
      screen.getByText('This reading did not finish, so follow-up questions are unavailable.'),
    ).toBeInTheDocument();
  });

  it('shows the dated guidance instead of the past-year checks by default', async () => {
    vi.spyOn(fortuneClient, 'getFortune').mockResolvedValue(snapshot('done', {
      ...COMPLETE_MODEL,
      retrodictions: { items: [{ year: 1994, prediction: 'An old pattern.', confidence: 0.85 }] },
    }));

    renderResult();

    expect(await screen.findByText('2028–2029')).toBeInTheDocument();
    expect(screen.getByText(/Age 38–39/)).toBeInTheDocument();
    expect(screen.getByText('Document results and build alliances.')).toBeInTheDocument();
    expect(screen.getByText('Past-year pattern checks (1)')).toBeInTheDocument();
    expect(screen.queryByText('An old pattern.')).not.toBeVisible();
    expect(screen.queryByText('Tap to expand years')).not.toBeInTheDocument();
  });

  it('drops explorer selection from the URL when leaving Why', async () => {
    vi.spyOn(fortuneClient, 'getFortune').mockResolvedValue(snapshot('done', COMPLETE_MODEL));

    renderResult('/project/fortune-agent/custom-wish/fortune-1?tab=Why&view=chart&palace=3&finding=1');

    await screen.findByRole('tab', { name: /Outlook/ });
    fireEvent.click(screen.getByRole('tab', { name: /Outlook/ }));

    await waitFor(() =>
      expect(screen.getByTestId('location').textContent).toBe(
        '/project/fortune-agent/custom-wish/fortune-1',
      ),
    );
  });
});

describe('backend explorer', () => {
  beforeEach(() => {
    useFortuneStore.getState().reset();
  });

  function renderHarness(dataModel: FortuneDataModel, search = '?view=findings') {
    act(() => {
      useFortuneStore.getState().hydrateFromReplay({
        fortune_id: 'fortune-1', run_id: 'run-1', function_id: 'wish', status: 'complete',
        last_seq: 0, metadata: { created_at: '2026-09-05T00:00:00Z' },
        data_model: dataModel, ask_history: [],
      });
    });
    return render(
      <MemoryRouter initialEntries={[`/result${search}`]}>
        <Routes>
          <Route
            path="/result"
            element={<HarnessView accent="#14b8a6"><div>Reading</div></HarnessView>}
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  it('reveals the validated opportunity, risk, action and alternative', () => {
    renderHarness({ harness: { brief: { findings: [FINDING], limitations: ['Not guaranteed events.'] } } });

    expect(screen.getByText(/Opportunity:/)).toBeInTheDocument();
    expect(screen.getByText(/Too much independence/)).toBeInTheDocument();
    expect(screen.getByText(/Document your methods/)).toBeInTheDocument();
    expect(screen.getByText(/Progress may come through a partnership/)).toBeInTheDocument();
    expect(screen.getByText('What this reading cannot tell you')).toBeInTheDocument();
  });

  it('names Person A when two charts are present', () => {
    renderHarness({
      harness: {
        brief: { findings: [FINDING], limitations: [] },
        charts: {
          personA: { status: 'unavailable', engine: 'iztro', version: '2.6.0', conventions: {}, palaces: [] },
          personB: { status: 'unavailable', engine: 'iztro', version: '2.6.0', conventions: {}, palaces: [] },
        },
      },
    });

    expect(screen.getByText(/Person A turning 38–39/)).toBeInTheDocument();
  });

  it('explains a reading saved before briefs existed', () => {
    renderHarness({ narrative: { tldr: 'An older reading.' } });

    expect(screen.getByText(/older reading has no saved findings/)).toBeInTheDocument();
  });
});

describe('execution trace loading', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useFortuneStore.getState().reset();
  });

  it('does not spend replay quota while the drawer is closed', async () => {
    const getTrace = vi.spyOn(fortuneClient, 'getTrace').mockResolvedValue({ fortune_id: 'fortune-a', run_id: null, events: [] });
    act(() => useFortuneStore.getState().setFortune('fortune-a', 'run-a'));
    render(<GlassBoxPanel />);

    await act(async () => { await Promise.resolve(); });
    expect(getTrace).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { expanded: false }));
    await waitFor(() => expect(getTrace).toHaveBeenCalledOnce());
  });
});
