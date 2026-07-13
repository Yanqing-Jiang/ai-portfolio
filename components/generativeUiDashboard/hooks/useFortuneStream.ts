/**
 * useFortuneStream — SSE envelope adapter for fortune readings.
 *
 * Phase 3B: resume via Redis cursor (`?after=`), typed `resync_required`,
 * and trace envelopes (payload.kind==='trace', no seq) into fortuneStore.traceEvents.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useFortuneStore } from '../stores/fortuneStore';
import { fortuneClient } from '../lib/fortuneClient';
import type { FortuneDataModel, FortuneFunctionId } from '../lib/fortuneTypes';

interface UseFortuneStreamOptions {
  fortuneId: string | null;
  streamUrl: string | null;
  enabled?: boolean;
  /** Called when the server emits typed resync_required — parent re-hydrates snapshot. */
  onResyncRequired?: () => void | Promise<void>;
}

interface UseFortuneStreamReturn {
  phase: 'idle' | 'connecting' | 'streaming' | 'complete' | 'error';
  lastSeq: number;
  lastEventId: string | null;
  runId: string | null;
  reconnect: () => void;
}

const MAX_RETRIES = 8;
const INITIAL_BACKOFF_MS = 1000;

export function useFortuneStream(options: UseFortuneStreamOptions): UseFortuneStreamReturn {
  const { fortuneId, streamUrl, enabled = true, onResyncRequired } = options;
  const [phase, setPhase] = useState<UseFortuneStreamReturn['phase']>('idle');
  const [lastSeq, setLastSeq] = useState(0);
  const [lastEventId, setLastEventId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const maxSeqRef = useRef(0);
  const lastEventIdRef = useRef<string | null>(null);
  const runIdRef = useRef<string | null>(null);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const completedRef = useRef(false);
  const erroredRef = useRef(false);
  const baseStreamUrlRef = useRef<string | null>(null);
  const onResyncRef = useRef(onResyncRequired);
  const fortuneIdRef = useRef(fortuneId);
  const connectionEpochRef = useRef(0);
  onResyncRef.current = onResyncRequired;
  // Update during render so callbacks from the previous EventSource are fenced
  // even before React runs the route-change effect.
  fortuneIdRef.current = fortuneId;

  const applyPatch = useFortuneStore((s) => s.applyPatch);
  const setStatus = useFortuneStore((s) => s.setStatus);
  const setStoreRunId = useFortuneStore((s) => s.setRunId);
  const setNarrativeReady = useFortuneStore((s) => s.setNarrativeReady);
  const appendTraceEvent = useFortuneStore((s) => s.appendTraceEvent);

  const close = useCallback(() => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const connect = useCallback((urlOverride?: string | null) => {
    const url = urlOverride ?? baseStreamUrlRef.current ?? streamUrl;
    if (!url || !enabled) return;

    close();
    if (completedRef.current) return;

    setPhase('connecting');
    setStatus('streaming');

    const es = new EventSource(url);
    eventSourceRef.current = es;
    const epoch = connectionEpochRef.current;
    const connectionFortuneId = fortuneId;
    const isCurrentConnection = () => (
      eventSourceRef.current === es
      && connectionEpochRef.current === epoch
      && fortuneIdRef.current === connectionFortuneId
    );

    es.onopen = () => {
      if (!isCurrentConnection()) return;
      setPhase('streaming');
      retryCountRef.current = 0;
    };

    const handleEnvelope = (event: MessageEvent) => {
      try {
        if (!isCurrentConnection()) return;
        const currentFortuneId = useFortuneStore.getState().fortuneId;
        if (currentFortuneId !== fortuneId) return;

        if (event.lastEventId) {
          lastEventIdRef.current = event.lastEventId;
          setLastEventId(event.lastEventId);
        }

        const envelope = JSON.parse(event.data);

        // A delayed EventSource callback must never mutate the newly selected
        // reading after navigation. Older servers may omit fortune_id, but an
        // explicit mismatch is always stale and must be ignored.
        if (envelope.fortune_id && envelope.fortune_id !== fortuneId) {
          return;
        }

        if (envelope.done === true || (envelope.payload && envelope.payload.done === true)) {
          completedRef.current = true;
          if (erroredRef.current) {
            setPhase('error');
            setStatus('error');
          } else {
            setPhase('complete');
            setStatus('complete');
          }
          es.close();
          return;
        }

        const { run_id, seq, payload } = envelope;

        if (run_id && runIdRef.current !== run_id) {
          runIdRef.current = run_id;
          setRunId(run_id);
          setStoreRunId(run_id);
        }

        // Trace envelopes have no seq — store separately, skip deduper.
        if (payload && typeof payload === 'object' && payload.kind === 'trace') {
          appendTraceEvent({
            id: event.lastEventId || undefined,
            run_id,
            fortune_id: envelope.fortune_id,
            payload: payload as Record<string, unknown>,
            receivedAt: new Date().toISOString(),
          });
          return;
        }

        if (typeof seq === 'number') {
          retryCountRef.current = 0;
          if (seq <= maxSeqRef.current) return;
          maxSeqRef.current = seq;
          setLastSeq(seq);
        }

        if (payload && typeof payload === 'object') {
          if (payload.dataModelUpdate) {
            const { path, contents } = payload.dataModelUpdate;
            const data = processContents(contents);
            applyPatch(path, data);

            if (path === '/data/narrative' && data.isComplete === true) {
              setNarrativeReady(true);
            }
          }
          if (payload.dataModelUpdate?.path === '/data/meta') {
            const contents = processContents(payload.dataModelUpdate.contents);
            if (contents.status === 'complete') {
              completedRef.current = true;
              setPhase('complete');
              setStatus('complete');
            } else if (contents.status === 'error') {
              erroredRef.current = true;
              setPhase('error');
              setStatus('error');
            }
          }
        }
      } catch (err) {
        console.error('[useFortuneStream] Failed to parse SSE message:', err);
      }
    };

    es.onmessage = handleEnvelope;

    // Typed events (e.g. event: resync_required)
    es.addEventListener('resync_required', () => {
      if (!isCurrentConnection()) return;
      es.close();
      eventSourceRef.current = null;
      void (async () => {
        try {
          await onResyncRef.current?.();
          if (!isCurrentConnection() && (
            connectionEpochRef.current !== epoch
            || fortuneIdRef.current !== connectionFortuneId
          )) return;
          if (eventSourceRef.current !== null) return;
          // Parent rehydrates + may rebuild streamUrl without after=; reset cursor.
          lastEventIdRef.current = null;
          setLastEventId(null);
          maxSeqRef.current = 0;
          setLastSeq(0);
          retryCountRef.current = 0;
          if (baseStreamUrlRef.current) {
            connect(baseStreamUrlRef.current);
          }
        } catch (err) {
          console.error('[useFortuneStream] resync failed:', err);
          setPhase('error');
          setStatus('error');
        }
      })();
    });

    es.onerror = () => {
      if (!isCurrentConnection()) return;
      es.close();
      eventSourceRef.current = null;
      if (completedRef.current) return;

      if (retryCountRef.current < MAX_RETRIES) {
        const delay = INITIAL_BACKOFF_MS * Math.pow(2, retryCountRef.current);
        retryCountRef.current++;
        setPhase('connecting');

        const after = lastEventIdRef.current;
        let resumeUrl = baseStreamUrlRef.current || streamUrl;
        if (resumeUrl && after && fortuneId) {
          // Rebuild with ?after= — EventSource cannot set Last-Event-ID on manual reconnect.
          try {
            const u = new URL(resumeUrl);
            u.searchParams.set('after', after);
            resumeUrl = u.toString();
          } catch {
            const sep = resumeUrl.includes('?') ? '&' : '?';
            resumeUrl = `${resumeUrl}${sep}after=${encodeURIComponent(after)}`;
          }
        }

        retryTimerRef.current = setTimeout(() => connect(resumeUrl), Math.min(delay, 30000));
      } else {
        setPhase('error');
        setStatus('error');
      }
    };
  }, [
    streamUrl,
    enabled,
    fortuneId,
    close,
    applyPatch,
    setStatus,
    setStoreRunId,
    setNarrativeReady,
    appendTraceEvent,
  ]);

  // A new stream URL is a new run even when it belongs to the same fortune
  // (for example an action run). Sequence numbers and completion are run-local,
  // so fence the old source and reset its cursor for either identity change.
  useEffect(() => {
    connectionEpochRef.current += 1;
    close();
    completedRef.current = false;
    erroredRef.current = false;
    maxSeqRef.current = 0;
    lastEventIdRef.current = null;
    runIdRef.current = null;
    retryCountRef.current = 0;
    baseStreamUrlRef.current = null;
    setLastSeq(0);
    setLastEventId(null);
    setRunId(null);
    setPhase('idle');
  }, [fortuneId, streamUrl, close]);

  useEffect(() => {
    baseStreamUrlRef.current = streamUrl;
    if (streamUrl && enabled && fortuneId) {
      connect(streamUrl);
    }
    return close;
  }, [streamUrl, enabled, fortuneId, connect, close]);

  const reconnect = useCallback(() => {
    // Manual reconnect denotes a new run attempt even when the backend URL is
    // stable for the fortune. Clear every run-local latch before connecting.
    connectionEpochRef.current += 1;
    close();
    completedRef.current = false;
    erroredRef.current = false;
    maxSeqRef.current = 0;
    lastEventIdRef.current = null;
    runIdRef.current = null;
    retryCountRef.current = 0;
    setLastSeq(0);
    setLastEventId(null);
    setRunId(null);
    setPhase('idle');
    connect(streamUrl);
  }, [close, connect, streamUrl]);

  return { phase, lastSeq, lastEventId, runId, reconnect };
}

/** Convert A2UI DataEntry[] contents to a plain JS object. */
function processContents(contents: unknown): Record<string, unknown> {
  const normalizeEntry = (key: unknown, value: unknown) =>
    normalizeStreamValue(String(key || ''), value);

  if (!Array.isArray(contents)) {
    if (contents && typeof contents === 'object') {
      return normalizeStreamValue('', contents) as Record<string, unknown>;
    }
    return {};
  }
  const result: Record<string, unknown> = {};
  for (const entry of contents) {
    if (!entry || typeof entry !== 'object' || !('key' in entry)) continue;
    const e = entry as Record<string, unknown>;
    if (e.valueString !== undefined) result[e.key as string] = normalizeEntry(e.key, e.valueString);
    else if (e.valueNumber !== undefined) result[e.key as string] = e.valueNumber;
    else if (e.valueBoolean !== undefined) result[e.key as string] = e.valueBoolean;
    else if (e.valueBool !== undefined) result[e.key as string] = e.valueBool;
    else if (e.valueArray !== undefined) result[e.key as string] = normalizeEntry(e.key, normalizeArray(e.valueArray));
    else if (e.valueMap !== undefined) result[e.key as string] = normalizeEntry(e.key, processContents(e.valueMap));
    else if (e.valueObject !== undefined) result[e.key as string] = normalizeEntry(e.key, processContents(e.valueObject));
  }
  return result;
}

function normalizeArray(arr: unknown): unknown[] {
  if (!Array.isArray(arr)) return [];
  return arr.map((item) => {
    if (Array.isArray(item) && item.length > 0 && item[0] && typeof item[0] === 'object' && 'key' in item[0]) {
      return processContents(item);
    }
    if (item && typeof item === 'object' && 'valueMap' in (item as Record<string, unknown>)) {
      return processContents((item as Record<string, unknown>).valueMap);
    }
    return normalizeStreamValue('', item);
  });
}

const ELEMENT_BY_LOWER: Record<string, string> = {
  wood: 'Wood',
  fire: 'Fire',
  earth: 'Earth',
  metal: 'Metal',
  water: 'Water',
};

const ELEMENT_VALUE_KEYS = new Set([
  'element',
  'dayMasterElement',
  'day_master_element',
  'stemElement',
  'stem_element',
  'branchElement',
  'branch_element',
]);

function normalizeElementName(value: unknown): unknown {
  if (typeof value !== 'string') return value;
  return ELEMENT_BY_LOWER[value.trim().toLowerCase()] || value;
}

function normalizeStreamValue(key: string, value: unknown): unknown {
  if (ELEMENT_VALUE_KEYS.has(key)) return normalizeElementName(value);
  if (Array.isArray(value)) return value.map((item) => normalizeStreamValue('', item));
  if (!value || typeof value !== 'object') return value;

  const raw = value as Record<string, unknown>;
  const normalizedEntries = Object.entries(raw).map(([entryKey, entryValue]) => {
    const normalizedKey = ELEMENT_BY_LOWER[entryKey.toLowerCase()] || entryKey;
    return [normalizedKey, normalizeStreamValue(entryKey, entryValue)];
  });
  return Object.fromEntries(normalizedEntries);
}

/** Hydrate store from GET /{id} data_model (v2). Overlays corrections from data.*. */
export function hydrateDataModelFromSnapshot(
  snapshot: Awaited<ReturnType<typeof fortuneClient.getFortune>>,
  functionId: FortuneFunctionId,
): FortuneDataModel {
  if (!snapshot) return {} as FortuneDataModel;

  const base = (snapshot.data_model && typeof snapshot.data_model === 'object'
    ? { ...(snapshot.data_model as Record<string, unknown>) }
    : {}) as FortuneDataModel;

  // Post-hoc /correction writes update latest_retrodictions only — overlay from GET data.
  const corrections = snapshot.data?.corrections;
  if (corrections && typeof corrections === 'object') {
    (base as Record<string, unknown>).corrections = corrections;
  }
  const retro = snapshot.data?.retrodictions;
  if (retro && typeof retro === 'object') {
    const existing = (base as Record<string, unknown>).retrodictions as
      | { items?: unknown }
      | undefined;
    if (!existing || !Array.isArray(existing.items) || existing.items.length === 0) {
      const items = Array.isArray((retro as { items?: unknown }).items)
        ? (retro as { items: unknown[] }).items
        : Array.isArray(retro)
          ? retro
          : [];
      if (items.length > 0) {
        (base as Record<string, unknown>).retrodictions = { items };
      }
    }
  }

  // Ensure functionId is recorded on the model meta when present.
  void functionId;
  return base;
}
