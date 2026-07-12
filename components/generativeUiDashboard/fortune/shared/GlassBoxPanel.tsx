/**
 * GlassBoxPanel — Execution Trace ledger (Phase 5 / mock B).
 *
 * Live: fortuneStore.traceEvents (SSE payload.kind==='trace').
 * Replay: GET /api/fortune/{id}/trace when live events are empty.
 *
 * variant="inline" (default): collapsible drawer for mobile / Phase-4 placement.
 * variant="rail": always-open sticky side ledger for ≥lg screens.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { useShallow } from 'zustand/react/shallow';
import { fortuneClient } from '../../lib/fortuneClient';
import { useFortuneStore, type TraceProjection } from '../../stores/fortuneStore';
import {
  OBS_LEDGER,
  OBS_LEDGER_HEADER,
  OBS_LEDGER_ROW,
  OBSERVATORY_MONO,
  accentAlpha,
} from '../designTokens';

function asProjection(raw: unknown): TraceProjection | null {
  if (!raw || typeof raw !== 'object') return null;
  const t = raw as Record<string, unknown>;
  const eventId = typeof t.eventId === 'string' ? t.eventId : null;
  if (!eventId) return null;
  return {
    eventId,
    runId: typeof t.runId === 'string' ? t.runId : undefined,
    spanId: typeof t.spanId === 'string' ? t.spanId : undefined,
    phase: typeof t.phase === 'string' ? t.phase : undefined,
    parentSpanId: (t.parentSpanId as string | null | undefined) ?? null,
    spanType: (t.spanType as string | null | undefined) ?? null,
    agentName: (t.agentName as string | null | undefined) ?? null,
    toolName: (t.toolName as string | null | undefined) ?? null,
    model: (t.model as string | null | undefined) ?? null,
    durationMs: typeof t.durationMs === 'number' ? t.durationMs : null,
    status: (t.status as string | null | undefined) ?? null,
    argSummary: (t.argSummary as string | null | undefined) ?? null,
    resultSummary: (t.resultSummary as string | null | undefined) ?? null,
    startedAt: (t.startedAt as string | null | undefined) ?? null,
    endedAt: (t.endedAt as string | null | undefined) ?? null,
  };
}

function spanKey(p: TraceProjection): string {
  // Backend emits one event per span phase: `{run_id}:{span_id}:start|end`.
  if (p.spanId) return `${p.runId || ''}:${p.spanId}`;
  return p.eventId.replace(/:(start|end)$/, '');
}

/** Collapse per-phase events into one ledger row per span. The end event's
 * terminal fields (duration, status, summaries) win; a span with only a
 * start event so far is still running and pulses. */
function coalesceSpans(events: TraceProjection[]): TraceProjection[] {
  const byKey = new Map<string, TraceProjection>();
  for (const ev of events) {
    const key = spanKey(ev);
    const prev = byKey.get(key);
    if (!prev) {
      byKey.set(key, ev);
      continue;
    }
    const [start, end] = ev.phase === 'end' || ev.durationMs != null ? [prev, ev] : [ev, prev];
    byKey.set(key, {
      ...start,
      eventId: key,
      phase: end.phase ?? start.phase,
      spanType: end.spanType ?? start.spanType,
      agentName: end.agentName ?? start.agentName,
      toolName: end.toolName ?? start.toolName,
      model: end.model ?? start.model,
      durationMs: end.durationMs ?? start.durationMs,
      status: end.status ?? start.status,
      argSummary: end.argSummary ?? start.argSummary,
      resultSummary: end.resultSummary ?? start.resultSummary,
      startedAt: start.startedAt ?? end.startedAt,
      endedAt: end.endedAt ?? start.endedAt,
    });
  }
  const spans = [...byKey.values()];
  spans.sort((a, b) => {
    if (a.startedAt && b.startedAt && a.startedAt !== b.startedAt) {
      return a.startedAt < b.startedAt ? -1 : 1;
    }
    return 0;
  });
  return spans;
}

function formatDuration(ms: number | null | undefined): string {
  if (typeof ms !== 'number' || ms <= 0) return '';
  if (ms >= 1000) {
    const s = ms / 1000;
    return s >= 10 ? `${Math.round(s)}s` : `${s.toFixed(1)}s`;
  }
  return `${Math.round(ms)}ms`;
}

function spanLabel(step: TraceProjection): string {
  return step.toolName || step.spanType || step.phase || step.model || 'span';
}

function isActiveStatus(status: string | null | undefined): boolean {
  const s = (status || '').toLowerCase();
  return s === 'running' || s === 'pending' || s === 'streaming';
}

interface GlassBoxPanelProps {
  accent?: string;
  /** inline = collapsible (mobile); rail = always open desktop ledger */
  variant?: 'inline' | 'rail';
}

export const GlassBoxPanel: React.FC<GlassBoxPanelProps> = ({
  accent = '#39d98a',
  variant = 'inline',
}) => {
  const reduceMotion = useReducedMotion();
  const { fortuneId, status, traceEvents, hydrateTraceProjections } = useFortuneStore(
    useShallow((s) => ({
      fortuneId: s.fortuneId,
      status: s.status,
      traceEvents: s.traceEvents,
      hydrateTraceProjections: s.hydrateTraceProjections,
    })),
  );

  const isRail = variant === 'rail';
  const [open, setOpen] = useState(isRail);
  const [loadingReplay, setLoadingReplay] = useState(false);

  useEffect(() => {
    if (isRail) setOpen(true);
  }, [isRail]);

  const projections = useMemo(() => {
    const out: TraceProjection[] = [];
    for (const ev of traceEvents) {
      const trace = asProjection(ev.payload?.trace);
      if (trace) out.push(trace);
    }
    return coalesceSpans(out);
  }, [traceEvents]);

  useEffect(() => {
    if (!fortuneId) return;
    if (projections.length > 0) return;
    if (status === 'streaming' || status === 'loading') return;

    let cancelled = false;
    (async () => {
      setLoadingReplay(true);
      try {
        const res = await fortuneClient.getTrace(fortuneId);
        if (cancelled) return;
        const mapped = (res.events || [])
          .map((e) => asProjection(e))
          .filter((e): e is TraceProjection => !!e);
        if (mapped.length > 0) hydrateTraceProjections(mapped);
      } catch {
        // Replay is best-effort.
      } finally {
        if (!cancelled) setLoadingReplay(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [fortuneId, projections.length, status, hydrateTraceProjections]);

  const isLive = status === 'streaming' || status === 'loading';
  const totalMs = useMemo(
    () =>
      projections.reduce(
        (sum, p) => sum + (typeof p.durationMs === 'number' ? p.durationMs : 0),
        0,
      ),
    [projections],
  );

  const headerText = loadingReplay
    ? 'EXECUTION TRACE · LOADING…'
    : `EXECUTION TRACE · ${projections.length} SPAN${projections.length === 1 ? '' : 'S'}${
        totalMs > 0 ? ` · ${formatDuration(totalMs)}` : ''
      }`;

  const rows = (
    <div
      className={isRail ? 'max-h-[calc(100dvh-120px)] overflow-y-auto pb-3' : 'max-h-72 overflow-y-auto pb-3'}
      style={{ fontFamily: OBSERVATORY_MONO }}
    >
      {projections.length === 0 ? (
        <div className="flex items-center justify-center gap-2 px-4 py-6 text-[10.5px] text-[#5c6963]">
          {loadingReplay || isLive ? (
            <>
              <Loader2 size={12} className="animate-spin" style={{ color: accent }} />
              {isLive ? 'Waiting for spans…' : 'Loading trace…'}
            </>
          ) : (
            'No execution spans recorded.'
          )}
        </div>
      ) : (
        projections.map((step) => {
          const active = isActiveStatus(step.status);
          const ms = formatDuration(step.durationMs);
          return (
            <div
              key={step.eventId}
              className={OBS_LEDGER_ROW}
              style={active ? { color: accent } : undefined}
            >
              <span className="min-w-0 truncate">
                <b
                  className="font-medium"
                  style={{ color: active ? accent : '#9fb3a8' }}
                >
                  {step.agentName || 'pipeline'}
                </b>{' '}
                <span>{spanLabel(step)}</span>
                {active && (
                  <motion.span
                    aria-hidden
                    className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle"
                    style={{ background: accent }}
                    animate={reduceMotion ? undefined : { opacity: [1, 0.25, 1] }}
                    transition={
                      reduceMotion
                        ? undefined
                        : { duration: 1.2, repeat: Infinity, ease: 'easeInOut' }
                    }
                  />
                )}
              </span>
              {ms ? (
                <span
                  className="flex-none"
                  style={{ color: active ? accentAlpha(accent, 0.7) : '#39707f' }}
                >
                  {ms}
                </span>
              ) : (
                <span className="flex-none text-transparent">·</span>
              )}
            </div>
          );
        })
      )}
    </div>
  );

  if (isRail) {
    return (
      <div className={`${OBS_LEDGER} overflow-hidden`} style={{ borderColor: '#1c2420' }}>
        <div className={OBS_LEDGER_HEADER} style={{ color: accent, fontFamily: OBSERVATORY_MONO }}>
          <span className="inline-flex items-center gap-2">
            {isLive && (
              <motion.span
                aria-hidden
                className="inline-block h-1.5 w-1.5 rounded-full"
                style={{ background: accent }}
                animate={reduceMotion ? undefined : { opacity: [1, 0.3, 1] }}
                transition={
                  reduceMotion
                    ? undefined
                    : { duration: 1.4, repeat: Infinity, ease: 'easeInOut' }
                }
              />
            )}
            {headerText}
          </span>
        </div>
        {rows}
      </div>
    );
  }

  return (
    <div className={`${OBS_LEDGER} overflow-hidden`} style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`flex w-full items-center justify-between gap-3 text-left ${OBS_LEDGER_HEADER}`}
        style={{ color: accent, fontFamily: OBSERVATORY_MONO }}
        aria-expanded={open}
      >
        <span className="inline-flex min-w-0 items-center gap-2 truncate">
          {isLive && (
            <motion.span
              aria-hidden
              className="inline-block h-1.5 w-1.5 flex-none rounded-full"
              style={{ background: accent }}
              animate={reduceMotion ? undefined : { opacity: [1, 0.3, 1] }}
              transition={
                reduceMotion
                  ? undefined
                  : { duration: 1.4, repeat: Infinity, ease: 'easeInOut' }
              }
            />
          )}
          <span className="truncate">{headerText}</span>
        </span>
        {open ? (
          <ChevronDown size={14} className="text-[#5c6963]" />
        ) : (
          <ChevronRight size={14} className="text-[#5c6963]" />
        )}
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={reduceMotion ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={reduceMotion ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.2 }}
            className="overflow-hidden border-t border-white/[0.05]"
          >
            {rows}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default GlassBoxPanel;
