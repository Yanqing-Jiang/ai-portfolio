/**
 * Date-only values from the fortune API represent calendar days, not UTC
 * instants. Parse them with numeric Date arguments so a date such as
 * 2026-09-15 stays September 15 in the user's local timezone.
 */

const DATE_ONLY_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function parseDateOnly(value: string): Date | null {
  const match = DATE_ONLY_RE.exec(value);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day);

  // Date normalizes invalid inputs (e.g. April 31), so reject those rather
  // than rendering a neighboring calendar day.
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return null;
  }
  return date;
}

export function formatDateOnly(
  value: string,
  options: Intl.DateTimeFormatOptions,
): string {
  const date = parseDateOnly(value);
  return date
    ? date.toLocaleDateString('en-US', options)
    : 'Date pending';
}

/** Difference between two local calendar dates, independent of time of day. */
export function calendarDayDistance(value: string, now = new Date()): number | null {
  const date = parseDateOnly(value);
  if (!date) return null;

  const targetDay = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  const todayDay = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((targetDay - todayDay) / (24 * 60 * 60 * 1000));
}
