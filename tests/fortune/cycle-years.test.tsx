import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TimelineTab, filterAnnualYearsForDecade, getDecadeScores } from '../../components/generativeUiDashboard/fortune/luck/TimelineTab';
import { YearCard } from '../../components/generativeUiDashboard/fortune/shared/YearCard';
import { useFortuneStore } from '../../components/generativeUiDashboard/stores/fortuneStore';
import type { AnnualPillar, LuckPillar } from '../../components/generativeUiDashboard/lib/fortuneTypes';

const DECADE: LuckPillar = {
  startAge: 30,
  endAge: 39,
  startYear: 2017,
  endYear: 2026,
  stem: 'Ren',
  branch: 'Zi',
  isCurrent: true,
};

const YEARS = [
  { year: 2017, stem: 'Ding', branch: 'You' },
  { year: 2018, stem: 'Wu', branch: 'Xu' },
] as AnnualPillar[];

describe('cycle Years rendering', () => {
  const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
  const originalScrollTo = HTMLElement.prototype.scrollTo;

  beforeEach(() => {
    HTMLElement.prototype.scrollIntoView = vi.fn();
    HTMLElement.prototype.scrollTo = vi.fn();
    useFortuneStore.getState().reset();
  });

  afterEach(() => {
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      writable: true,
      value: originalScrollIntoView,
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      configurable: true,
      writable: true,
      value: originalScrollTo,
    });
    useFortuneStore.getState().reset();
  });

  it('renders supplied stem and branch elements without Wood or score 50 defaults', () => {
    const item = {
      year: 2017,
      stem: 'Ding',
      branch: 'You',
      stemElement: 'Fire',
      branchElement: 'Metal',
    } as unknown as AnnualPillar;

    render(<YearCard item={item} />);

    expect(screen.getByText('Fire · Metal')).toBeInTheDocument();
    expect(screen.queryByText('Wood')).not.toBeInTheDocument();
    expect(screen.queryByText('50')).not.toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('uses an annual score only when the backend supplies one', () => {
    const item = {
      year: 2018,
      stem: 'Wu',
      branch: 'Xu',
      stemElement: 'Earth',
      branchElement: 'Earth',
      score: 73,
    } as unknown as AnnualPillar;

    render(<YearCard item={item} />);

    expect(screen.getByText('Earth · Earth')).toBeInTheDocument();
    expect(screen.getByText('73')).toBeInTheDocument();
  });

  it('does not fall back to all years when a decade has no matches', () => {
    const unmatched: LuckPillar = {
      ...DECADE,
      isCurrent: false,
      startYear: 2030,
      endYear: 2036,
    };

    expect(filterAnnualYearsForDecade(unmatched, YEARS)).toEqual([]);
  });

  it('shows an empty state after selecting a decade with no annual records', async () => {
    useFortuneStore.getState().setFortune('cycle-id', 'run-id', { functionId: 'luck-cycle' });
    useFortuneStore.getState().applyPatch('/data/luckPillars', {
      items: [DECADE, { ...DECADE, isCurrent: false, startYear: 2030, endYear: 2036 }],
    });
    useFortuneStore.getState().applyPatch('/data/annualPillars', { items: YEARS });
    useFortuneStore.getState().setStatus('complete');

    render(<TimelineTab />);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /2030-2036/ }));
    });

    await waitFor(() => {
      expect(screen.getByText('No annual pillars are available for this decade.')).toBeInTheDocument();
      expect(screen.queryByText('2017')).not.toBeInTheDocument();
    });
  });

  it('keeps trend data empty when decades do not contain numeric scores', () => {
    expect(getDecadeScores([DECADE, { ...DECADE, score: undefined }])).toEqual([]);
    expect(getDecadeScores([{ ...DECADE, score: 68 }, DECADE])).toEqual([68]);
  });
});
