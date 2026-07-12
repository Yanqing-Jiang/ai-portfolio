/**
 * Shared date-window step (month stripe + quick chips).
 * Used by Occasion / Lucky Day intake; other wizards keep their own horizon UI.
 */
import React, { useMemo } from 'react';

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

export function summarizeWindow(startKey: string | null, endKey: string | null): string {
  if (!startKey) return 'Pick a month or range';
  const [sy, sm] = startKey.split('-').map(Number);
  const startLabel = `${MONTH_NAMES_SHORT[sm - 1]} ${sy}`;
  if (!endKey || endKey === startKey) return startLabel;
  const [ey, em] = endKey.split('-').map(Number);
  return `${startLabel} → ${MONTH_NAMES_SHORT[em - 1]} ${ey}`;
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
    if (windowStart && !windowEnd) {
      if (monthKeyCompare(key, windowStart) < 0) {
        onChange(key, null);
      } else if (key === windowStart) {
        onChange(key, key);
      } else {
        onChange(windowStart, key);
      }
      return;
    }
    onChange(key, null);
  };

  const isMonthInRange = (key: string): boolean => {
    if (!windowStart) return false;
    if (!windowEnd) return key === windowStart;
    return (
      monthKeyCompare(key, windowStart) >= 0 &&
      monthKeyCompare(key, windowEnd) <= 0
    );
  };

  const applyQuickChip = (id: 'next30' | 'summer' | 'eoy') => {
    const now = new Date();
    const yr = now.getFullYear();
    if (id === 'next30') {
      const k = `${yr}-${String(now.getMonth() + 1).padStart(2, '0')}`;
      onChange(k, k);
      return;
    }
    if (id === 'summer') {
      onChange(`${yr}-06`, `${yr}-08`);
      return;
    }
    const sm = String(now.getMonth() + 1).padStart(2, '0');
    onChange(`${yr}-${sm}`, `${yr}-12`);
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
            { id: 'summer' as const, label: 'This summer' },
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
            const isAnchor = m.key === windowStart || m.key === windowEnd;
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
