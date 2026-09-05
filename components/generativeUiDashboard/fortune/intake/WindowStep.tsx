/**
 * Shared date-window step (month stripe + quick chips).
 * Used by Occasion / Lucky Day intake; other wizards keep their own horizon UI.
 */
import React, { useMemo } from 'react';
import { parseDateOnly } from '../shared/dateOnly';

const MONTH_NAMES_SHORT = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
] as const;

function buildMonthStrip(from: Date, count: number): { key: string; year: number; month: number }[] {
  const out: { key: string; year: number; month: number }[] = [];
  const d = new Date(from.getFullYear(), from.getMonth(), 1);
  for (let i = 0; i < count; i++) {
    out.push({
      key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`,
      year: d.getFullYear(),
      month: d.getMonth() + 1,
    });
    d.setMonth(d.getMonth() + 1);
  }
  return out;
}

function monthKeyCompare(a: string, b: string): number {
  return a.localeCompare(b);
}

export function firstOfMonthISO(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}-01`;
}

export function lastOfMonthISO(year: number, month: number): string {
  const last = new Date(year, month, 0).getDate();
  return `${year}-${String(month).padStart(2, '0')}-${String(last).padStart(2, '0')}`;
}

export function normalizeWindowBoundary(
  value: string,
  boundary: 'start' | 'end',
  now = new Date(),
): string {
  const [year, month] = value.split('-').map(Number);
  if (
    boundary === 'start' &&
    value.length === 7 &&
    year === now.getFullYear() &&
    month === now.getMonth() + 1
  ) {
    return toDateOnlyISO(new Date(now.getFullYear(), now.getMonth(), now.getDate()));
  }
  if (parseDateOnly(value)) return value;
  if (!year || !month) return value;
  return boundary === 'start'
    ? firstOfMonthISO(year, month)
    : lastOfMonthISO(year, month);
}

function toDateOnlyISO(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate(),
  ).padStart(2, '0')}`;
}

function addCalendarDays(date: Date, days: number): Date {
  const result = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  result.setDate(result.getDate() + days);
  return result;
}

export function quickWindowRange(
  id: 'next30' | 'summer' | 'eoy',
  now = new Date(),
): { start: string; end: string } {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  if (id === 'next30') {
    return {
      start: toDateOnlyISO(today),
      end: toDateOnlyISO(addCalendarDays(today, 29)),
    };
  }

  if (id === 'summer') {
    // Once June–August has passed, use the next occurrence instead of sending
    // a user into an already elapsed window.
    const summerYear = today.getMonth() > 7 ? today.getFullYear() + 1 : today.getFullYear();
    const summerStart = new Date(summerYear, 5, 1);
    const summerEnd = new Date(summerYear, 8, 0);
    return {
      start: toDateOnlyISO(summerStart > today ? summerStart : today),
      end: toDateOnlyISO(summerEnd),
    };
  }

  return {
    start: toDateOnlyISO(today),
    end: toDateOnlyISO(new Date(today.getFullYear(), 11, 31)),
  };
}

export function summerChipLabel(now = new Date()): 'This summer' | 'Next summer' {
  return now.getMonth() > 7 ? 'Next summer' : 'This summer';
}

function monthKey(value: string): string {
  return value.slice(0, 7);
}

export function summarizeWindow(
  startKey: string | null,
  endKey: string | null,
  now = new Date(),
): string {
  if (!startKey) return 'Pick a month or range';
  const effectiveStartKey = normalizeWindowBoundary(startKey, 'start', now);
  const effectiveEndKey = endKey ? normalizeWindowBoundary(endKey, 'end', now) : null;
  const startDate = parseDateOnly(effectiveStartKey);
  const endDate = effectiveEndKey ? parseDateOnly(effectiveEndKey) : null;
  const [sy, sm] = effectiveStartKey.split('-').map(Number);
  const startLabel = startDate && startDate.getDate() !== 1
    ? startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : `${MONTH_NAMES_SHORT[sm - 1]} ${sy}`;
  if (!endKey || endKey === startKey) return startLabel;
  const [ey, em] = effectiveEndKey!.split('-').map(Number);
  const endIsMonthBoundary = endDate
    && endDate.getDate() === new Date(endDate.getFullYear(), endDate.getMonth() + 1, 0).getDate();
  const endLabel = endDate && (!endIsMonthBoundary
    || (startDate
      && startDate.getDate() !== 1
      && startDate.getFullYear() === endDate.getFullYear()
      && startDate.getMonth() === endDate.getMonth()))
    ? endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : `${MONTH_NAMES_SHORT[em - 1]} ${ey}`;
  return `${startLabel} → ${endLabel}`;
}

export interface WindowStepProps {
  windowStart: string | null;
  windowEnd: string | null;
  onChange: (start: string | null, end: string | null) => void;
  accentRgb?: string;
  monthCount?: number;
}

export const WindowStep: React.FC<WindowStepProps> = ({
  windowStart,
  windowEnd,
  onChange,
  accentRgb = '234, 179, 8',
  monthCount = 18,
}) => {
  const monthStrip = useMemo(() => buildMonthStrip(new Date(), monthCount), [monthCount]);

  const handleMonthTap = (key: string) => {
    if (!windowStart) {
      onChange(key, null);
      return;
    }
    const startMonth = monthKey(windowStart);
    if (windowStart && !windowEnd) {
      if (monthKeyCompare(key, startMonth) < 0) {
        onChange(key, null);
      } else if (key === startMonth) {
        onChange(key, key);
      } else {
        onChange(startMonth, key);
      }
      return;
    }
    onChange(key, null);
  };

  const isMonthInRange = (key: string): boolean => {
    if (!windowStart) return false;
    const startMonth = monthKey(windowStart);
    if (!windowEnd) return key === startMonth;
    const endMonth = monthKey(windowEnd);
    return (
      monthKeyCompare(key, startMonth) >= 0 &&
      monthKeyCompare(key, endMonth) <= 0
    );
  };

  const applyQuickChip = (id: 'next30' | 'summer' | 'eoy') => {
    const range = quickWindowRange(id);
    onChange(range.start, range.end);
  };

  return (
    <div>
      <p
        className="mb-3 text-center text-sm font-medium"
        style={{ color: `rgb(${accentRgb})` }}
      >
        {summarizeWindow(windowStart, windowEnd)}
      </p>

      <div className="mb-3 flex flex-wrap gap-1.5">
        {(
          [
            { id: 'next30' as const, label: 'Next 30 days' },
            { id: 'summer' as const, label: summerChipLabel() },
            { id: 'eoy' as const, label: 'Before year-end' },
          ] as const
        ).map((chip) => (
          <button
            key={chip.id}
            type="button"
            onClick={() => applyQuickChip(chip.id)}
            className="min-h-[32px] rounded-full px-3 py-1 text-xs transition-colors"
            style={{
              background: 'rgba(148, 163, 184, 0.08)',
              border: '1px solid rgba(148, 163, 184, 0.18)',
              color: '#cbd5e1',
            }}
          >
            {chip.label}
          </button>
        ))}
      </div>

      <div
        className="relative -mx-4 overflow-x-auto px-4 pb-2"
        style={{
          scrollSnapType: 'x mandatory',
          WebkitOverflowScrolling: 'touch',
        }}
      >
        <div className="flex gap-2">
          {monthStrip.map((m) => {
            const inRange = isMonthInRange(m.key);
            const isAnchor = m.key === (windowStart ? monthKey(windowStart) : null)
              || m.key === (windowEnd ? monthKey(windowEnd) : null);
            return (
              <button
                key={m.key}
                type="button"
                onClick={() => handleMonthTap(m.key)}
                className="flex min-h-[72px] w-[68px] flex-none flex-col items-center justify-center rounded-xl transition-all"
                style={{
                  scrollSnapAlign: 'center',
                  background: inRange
                    ? `rgba(${accentRgb}, 0.18)`
                    : 'rgba(148, 163, 184, 0.06)',
                  border: isAnchor
                    ? '1.5px solid var(--ming-gold, #d4af37)'
                    : inRange
                      ? `1px solid rgba(${accentRgb}, 0.5)`
                      : '1px solid rgba(148, 163, 184, 0.14)',
                  color: inRange ? '#fff' : '#cbd5e1',
                }}
              >
                <span className="text-[10px] uppercase tracking-wider opacity-70">
                  {m.year}
                </span>
                <span className="text-base font-semibold">
                  {MONTH_NAMES_SHORT[m.month - 1]}
                </span>
                {isAnchor && (
                  <span
                    className="mt-0.5 h-1 w-1 rounded-full"
                    style={{ background: 'var(--ming-gold, #d4af37)' }}
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>
      <p className="mt-2 text-center text-[11px] text-slate-500">
        Tap once for a month, twice to set a range
      </p>
    </div>
  );
};
