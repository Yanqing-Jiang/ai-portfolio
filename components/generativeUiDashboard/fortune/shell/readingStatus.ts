/**
 * Terminal reading state for the result shell.
 *
 * A run can end three ways the audience must be able to tell apart:
 *  - `failed`   — the generation stopped (backend error, expired run, fetch error)
 *  - `rejected` — the safety review withheld the reading
 *  - neither    — live or replay, handled by the normal result surfaces
 *
 * Backend contract: GET /api/fortune/{id} may return status="error" and
 * data_model.meta = { status: "error", error_message }. Stream errors set the
 * same meta fields. Legacy snapshots may report `partial` with an error meta;
 * checking both keeps those readable.
 */

import type { FortuneDataModel } from '../../lib/fortuneTypes';

export type ReadingFailureKind = 'failed' | 'rejected';

export interface ReadingFailure {
  kind: ReadingFailureKind;
  message: string;
}

export const GENERIC_FAILURE_MESSAGE =
  'This reading stopped before it finished. Please start a new reading.';

export const GENERIC_REJECTION_MESSAGE =
  'The safety review withheld this reading, so it was not completed.';

/**
 * Only pass through short, human-readable copy. Raw JSON pointers, stack
 * traces and SDK errors belong in the trace, never in audience text.
 */
export function friendlyFailureMessage(raw: unknown, fallback = GENERIC_FAILURE_MESSAGE): string {
  const text = typeof raw === 'string' ? raw.trim().replace(/^(error|exception)\s*:\s*/i, '') : '';
  if (!text || text.length > 180) return fallback;
  if (!/\s/.test(text)) return fallback;
  if (/\/(?:[a-z_]+\/)+[\w-]+/i.test(text)) return fallback;
  if (/[{}[\]<>\\|]|https?:\/\/|\/data\/|\/#\/|\btraceback\b|\bstatus code\b|\bstack\b|\btypeerror\b|\bkeyerror\b|\bnull\b|\bundefined\b|\bnonetype\b/i.test(text)) {
    return fallback;
  }
  return text;
}

export function detectReadingFailure(input: {
  status: string;
  dataModel: FortuneDataModel | null | undefined;
  sessionError?: string | null;
}): ReadingFailure | null {
  const guardrail = input.dataModel?.guardrail;
  const severity = (guardrail?.severity || guardrail?.level || '').toLowerCase();
  if (severity === 'critical' || severity === 'error' || severity === 'failed' || severity === 'reject' || severity === 'rejected') {
    return {
      kind: 'rejected',
      message: friendlyFailureMessage(guardrail?.message, GENERIC_REJECTION_MESSAGE),
    };
  }

  if (input.sessionError) {
    return { kind: 'failed', message: friendlyFailureMessage(input.sessionError) };
  }

  const meta = input.dataModel?.meta;
  if (input.status === 'error' || meta?.status === 'error') {
    return { kind: 'failed', message: friendlyFailureMessage(meta?.error_message) };
  }

  return null;
}
