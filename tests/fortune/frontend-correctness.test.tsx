import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  normalizeWindowBoundary,
  quickWindowRange,
  summarizeWindow,
  summerChipLabel,
  WindowStep,
} from '../../components/generativeUiDashboard/fortune/intake/WindowStep';
import {
  calendarDayDistance,
  formatDateOnly,
  parseDateOnly,
} from '../../components/generativeUiDashboard/fortune/shared/dateOnly';
import { BirthdayScrollPicker } from '../../components/generativeUiDashboard/BirthdayScrollPicker';
import { CalendarTab } from '../../components/generativeUiDashboard/fortune/occasion/CalendarTab';
import { useFortuneStore } from '../../components/generativeUiDashboard/stores/fortuneStore';

describe('fortune frontend date handling', () => {
  it('navigates across months and opens a scored date in the next month', () => {
    useFortuneStore.getState().reset();
    useFortuneStore.getState().applyPatch('/data/occasion', {
      calendar: { month: '09', year: 2026, days: [
        { date: '2026-09-24', score: 82 }, { date: '2026-10-01', score: 80 },
      ] },
    });
    const view = render(<CalendarTab isReplay />);
    expect(screen.getByText('September 2026')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next month' }));
    expect(screen.getByText('October 2026')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '1' }));
    expect(screen.getByRole('button', { name: 'Close day details' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close day details' }));
    fireEvent.click(screen.getByRole('button', { name: 'Previous month' }));
    expect(screen.getByText('September 2026')).toBeInTheDocument();
    view.unmount();
    useFortuneStore.getState().reset();
  });
  it('keeps the next-30-days promise at exact local calendar boundaries', () => {
    const range = quickWindowRange('next30', new Date(2026, 8, 5, 23, 45));

    expect(range).toEqual({ start: '2026-09-05', end: '2026-10-04' });
    expect(range.start >= '2026-09-05').toBe(true);
  });

  it('moves an elapsed summer shortcut to the next summer', () => {
    expect(quickWindowRange('summer', new Date(2026, 8, 5))).toEqual({
      start: '2027-06-01',
      end: '2027-08-31',
    });
    expect(summerChipLabel(new Date(2026, 8, 5))).toBe('Next summer');
    expect(summerChipLabel(new Date(2026, 5, 1))).toBe('This summer');
  });

  it('starts before-year-end at today so it cannot include elapsed days', () => {
    expect(quickWindowRange('eoy', new Date(2026, 8, 5))).toEqual({
      start: '2026-09-05',
      end: '2026-12-31',
    });
  });

  it('clamps a September 5 current-month selection and preserves future month starts', () => {
    const sep5 = new Date(2026, 8, 5, 12);
    expect(normalizeWindowBoundary('2026-09', 'start', sep5)).toBe('2026-09-05');
    expect(normalizeWindowBoundary('2026-10', 'start', sep5)).toBe('2026-10-01');
    expect(normalizeWindowBoundary('2026-09', 'end', sep5)).toBe('2026-09-30');
    expect(summarizeWindow('2026-09', '2026-09', sep5)).toContain('Sep 5');
    expect(summarizeWindow('2026-09-05', '2026-10-04')).toContain('Sep 5');
  });

  it('shows the effective September 5 start after a month-strip selection', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 8, 5, 12));
    try {
      const onChange = vi.fn();
      const view = render(<WindowStep windowStart={null} windowEnd={null} onChange={onChange} />);
      const currentMonth = screen.getAllByRole('button').find(
        (button) => button.textContent?.includes('2026') && button.textContent?.includes('Sep'),
      );

      expect(currentMonth).toBeDefined();
      fireEvent.click(currentMonth!);
      expect(onChange).toHaveBeenCalledWith('2026-09', null);

      view.rerender(<WindowStep windowStart="2026-09" windowEnd={null} onChange={onChange} />);
      expect(screen.getByText('Sep 5, 2026')).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('formats API date-only values without UTC rollover in Los Angeles', () => {
    expect(formatDateOnly('2026-09-15', { month: 'long', day: 'numeric' })).toBe('September 15');
    expect(calendarDayDistance('2026-09-15', new Date(2026, 8, 5, 23, 59))).toBe(10);
    expect(parseDateOnly('2026-02-30')).toBeNull();
  });

  it('exposes picker rows as keyboard controls', () => {
    const onChange = vi.fn();
    render(<BirthdayScrollPicker value="1990-01-15" onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: /1990/ }));
    const yearGroup = screen.getByRole('group', { name: 'year of birth' });
    const selectedYear = within(yearGroup).getByRole('button', { name: /1990/ });

    fireEvent.keyDown(selectedYear, { key: 'ArrowDown' });

    expect(onChange).toHaveBeenCalledWith('1989-01-15');
  });
});
