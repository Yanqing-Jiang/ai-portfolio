/**
 * GlassBoxPanel — Execution Trace for fortune result pages.
 *
 * Live: fortuneStore.traceEvents (SSE payload.kind==='trace').
 * Replay: GET /api/fortune/{id}/trace when live events are empty.
 *
 * Label is "Execution Trace" (SDK agent/tool/generation/guardrail spans),
 * not "thinking"/"reasoning". Collapsed by default.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Bot,
  ChevronDown,
  ChevronRight,
  Loader2,
  Shield,
  Sparkles,
  Wrench,
  Zap,
} from 'lucide-react';
import { useShallow } from 'zustand/react/shallow';
import { fortuneClient } from '../../lib/fortuneClient';
import { useFortuneStore, type TraceProjection } from '../../stores/fortuneStore';
import { GLASS } from '../designTokens';

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

function spanIcon(spanType: string | null | undefined) {
  const key = (spanType || '').toLowerCase();
  if (key.includes('function') || key.includes('tool')) return Wrench;
  if (key.includes('guard')) return Shield;
  if (key.includes('generation') || key.includes('response')) return Sparkles;
  if (key.includes('agent')) return Bot;
  return Zap;
}

function statusClass(status: string | null | undefined): string {
  switch ((status || '').toLowerCase()) {
    case 'running':
    case 'pending':
      return 'bg-amber-400 animate-pulse';
    case 'error':
    case 'rejected':
      return 'bg-rose-500';
    case 'success':
    case 'done':
      return 'bg-emerald-400';
    default:
      return 'bg-slate-500';
  }
}

interface GlassBoxPanelProps {
  accent?: string;
}

export const GlassBoxPanel: React.FC<GlassBoxPanelProps> = ({
  accent = '#94a3b8',
}) => {
  const { fortuneId, status, traceEvents, hydrateTraceProjections } = useFortuneStore(
    useShallow((s) => ({
      fortuneId: s.fortuneId,
      status: s.status,
      traceEvents: s.traceEvents,
      hydrateTraceProjections: s.hydrateTraceProjections,
    })),
  );

  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [loadingReplay, setLoadingReplay] = useState(false);

  const projections = useMemo(() => {
    const out: TraceProjection[] = [];
    for (const ev of traceEvents) {
      const trace = asProjection(ev.payload?.trace);
      if (trace) out.push(trace);
    }
    return out;
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
        // Replay is best-effort; live stream may still populate later.
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

  const grouped = useMemo(() => {
    const groups: Array<{ agent: string; items: TraceProjection[] }> = [];
    let current: { agent: string; items: TraceProjection[] } | null = null;
    for (const p of projections) {
      const agent = p.agentName || 'pipeline';
      if (!current || current.agent !== agent) {
        current = { agent, items: [p] };
        groups.push(current);
      } else {
        current.items.push(p);
      }
    }
    return groups;
  }, [projections]);

  return (
    <div className={`${GLASS} overflow-hidden border-white/10`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        aria-expanded={open}
      >
        <div className="flex min-w-0 items-center gap-2.5">
          {isLive ? (
            <span
              className="h-1.5 w-1.5 flex-none rounded-full animate-pulse"
              style={{ background: accent }}
              aria-hidden
            />
          ) : (
            <Zap size={13} style={{ color: accent }} className="flex-none" />
          )}
          <div className="min-w-0">
            <div className="text-[11px] font-semibold tracking-wide text-slate-200">
              Execution Trace
              {isLive && (
                <span className="ml-2 text-[10px] font-normal uppercase tracking-wider text-amber-300/80">
                  streaming
                </span>
              )}
            </div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
              {loadingReplay
                ? 'Loading…'
                : `${projections.length} span${projections.length === 1 ? '' : 's'}${
                    totalMs > 0 ? ` · ${Math.round(totalMs)}ms` : ''
                  }`}
            </div>
          </div>
        </div>
        {open ? (
          <ChevronDown size={14} className="text-slate-500" />
        ) : (
          <ChevronRight size={14} className="text-slate-500" />
        )}
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-white/5"
          >
            <div className="max-h-72 space-y-3 overflow-y-auto px-4 py-3">
              {projections.length === 0 ? (
                <div className="flex items-center justify-center gap-2 py-6 text-xs text-slate-500">
                  {loadingReplay || isLive ? (
                    <>
                      <Loader2 size={12} className="animate-spin" />
                      {isLive ? 'Waiting for spans…' : 'Loading trace…'}
                    </>
                  ) : (
                    'No execution spans recorded.'
                  )}
                </div>
              ) : (
                grouped.map((group) => (
                  <div key={group.agent} className="space-y-1">
                    <div className="px-0.5 text-[9px] font-bold uppercase tracking-[0.18em] text-slate-500">
                      {group.agent}
                    </div>
                    {group.items.map((step) => {
                      const Icon = spanIcon(step.spanType);
                      const isOpen = !!expanded[step.eventId];
                      const hasDetail = !!(step.argSummary || step.resultSummary);
                      return (
                        <div key={step.eventId}>
                          <button
                            type="button"
                            onClick={() =>
                              hasDetail &&
                              setExpanded((prev) => ({
                                ...prev,
                                [step.eventId]: !prev[step.eventId],
                              }))
                            }
                            className={`flex w-full items-start gap-2.5 rounded-lg px-1.5 py-1.5 text-left ${
                              hasDetail ? 'hover:bg-white/[0.03]' : 'cursor-default'
                            }`}
                            aria-expanded={hasDetail ? isOpen : undefined}
                          >
                            <span
                              className="mt-0.5 inline-flex h-5 w-5 flex-none items-center justify-center rounded-md"
                              style={{
                                background: `${accent}22`,
                                color: accent,
                              }}
                            >
                              <Icon size={11} />
                            </span>
                            <span
                              className={`mt-1.5 h-1.5 w-1.5 flex-none rounded-full ${statusClass(
                                step.status,
                              )}`}
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex items-baseline justify-between gap-2">
                                <p className="truncate text-[12px] text-slate-100">
                                  {step.toolName || step.spanType || step.phase || 'span'}
                                  {step.phase ? (
                                    <span className="ml-1.5 text-[10px] text-slate-500">
                                      · {step.phase}
                                    </span>
                                  ) : null}
                                </p>
                                {typeof step.durationMs === 'number' && step.durationMs > 0 && (
                                  <span className="flex-none font-mono text-[10px] text-slate-500">
                                    {Math.round(step.durationMs)}ms
                                  </span>
                                )}
                              </div>
                              <div className="text-[10px] text-slate-500">
                                {step.status || 'unknown'}
                                {step.model ? ` · ${step.model}` : ''}
                              </div>
                            </div>
                          </button>
                          <AnimatePresence initial={false}>
                            {isOpen && hasDetail && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="overflow-hidden pl-9 pr-1"
                              >
                                <div className="mb-1 space-y-1 rounded-md border border-white/5 bg-black/20 p-2 font-mono text-[10px] text-slate-400">
                                  {step.argSummary ? (
                                    <div>
                                      <span className="text-slate-600">in </span>
                                      {step.argSummary}
                                    </div>
                                  ) : null}
                                  {step.resultSummary ? (
                                    <div>
                                      <span className="text-slate-600">out </span>
                                      {step.resultSummary}
                                    </div>
                                  ) : null}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      );
                    })}
                  </div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default GlassBoxPanel;
