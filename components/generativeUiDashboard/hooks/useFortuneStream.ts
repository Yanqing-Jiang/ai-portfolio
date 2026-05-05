/**
 * useFortuneStream — SSE envelope adapter for fortune readings.
 *
 * The fortune backend wraps every event as:
 *   { run_id, fortune_id, seq, payload: <A2UI dataModelUpdate or done sentinel> }
 *
 * This hook:
 * 1. Opens an EventSource to the fortune stream URL
 * 2. Unwraps each envelope and deduplicates on `seq`
 * 3. Extracts the A2UI dataModelUpdate path+contents from `payload`
 * 4. Applies the update to the Zustand store's `dataModel`
 * 5. Detects the done sentinel and completion/error status
 * 6. Handles reconnection with exponential backoff
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useFortuneStore } from '../stores/fortuneStore';

interface UseFortuneStreamOptions {
  fortuneId: string | null;
  streamUrl: string | null;
  enabled?: boolean;
}

interface UseFortuneStreamReturn {
  phase: 'idle' | 'connecting' | 'streaming' | 'complete' | 'error';
  lastSeq: number;
  runId: string | null;
  reconnect: () => void;
}

const MAX_RETRIES = 5;
const INITIAL_BACKOFF_MS = 1000;

export function useFortuneStream(options: UseFortuneStreamOptions): UseFortuneStreamReturn {
  const { fortuneId, streamUrl, enabled = true } = options;
  const [phase, setPhase] = useState<UseFortuneStreamReturn['phase']>('idle');
  const [lastSeq, setLastSeq] = useState(0);
  const [runId, setRunId] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const maxSeqRef = useRef(0);
  const runIdRef = useRef<string | null>(null);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const applyPatch = useFortuneStore((s) => s.applyPatch);
  const setStatus = useFortuneStore((s) => s.setStatus);
  const setStoreRunId = useFortuneStore((s) => s.setRunId);

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

  const connect = useCallback(() => {
    if (!streamUrl || !enabled) return;

    close();
    setPhase('connecting');
    setStatus('streaming');

    const es = new EventSource(streamUrl);
    eventSourceRef.current = es;

    es.onopen = () => {
      setPhase('streaming');
      retryCountRef.current = 0;
    };

    es.onmessage = (event) => {
      try {
        const envelope = JSON.parse(event.data);

        // Done sentinel — backend wraps it inside payload: { done: true }
        // Also handle top-level { done: true } for robustness
        if (envelope.done === true || (envelope.payload && envelope.payload.done === true)) {
          setPhase('complete');
          setStatus('complete');
          es.close();
          return;
        }

        const { run_id, seq, payload } = envelope;

        if (typeof seq === 'number') {
          retryCountRef.current = 0;
        }

        // Store run_id on first message
        if (run_id && runIdRef.current !== run_id) {
          runIdRef.current = run_id;
          setRunId(run_id);
          setStoreRunId(run_id);
        }

        // Deduplicate on seq
        if (typeof seq === 'number' && seq <= maxSeqRef.current) return;
        if (typeof seq === 'number') {
          maxSeqRef.current = seq;
          setLastSeq(seq);
        }

        // Process the A2UI payload
        if (payload && typeof payload === 'object') {
          // dataModelUpdate shape: { dataModelUpdate: { surfaceId, path, contents } }
          if (payload.dataModelUpdate) {
            const { path, contents } = payload.dataModelUpdate;
            // Convert A2UI DataEntry format to plain object
            const data = processContents(contents);
            applyPatch(path, data);
          }
          // Check for meta status
          if (payload.dataModelUpdate?.path === '/data/meta') {
            const contents = processContents(payload.dataModelUpdate.contents);
            if (contents.status === 'complete') {
              setPhase('complete');
              setStatus('complete');
            } else if (contents.status === 'error') {
              setPhase('error');
              setStatus('error');
            }
          }
        }
      } catch (err) {
        console.error('[useFortuneStream] Failed to parse SSE message:', err);
      }
    };

    es.onerror = () => {
      es.close();
      eventSourceRef.current = null;

      // Retrying after the backend has already emitted data starts a second
      // long-running agent call for the same fortune if the browser drops the
      // connection mid-narrative. Let replay/resume handle recovery instead.
      if (maxSeqRef.current === 0 && retryCountRef.current < MAX_RETRIES) {
        const delay = INITIAL_BACKOFF_MS * Math.pow(2, retryCountRef.current);
        retryCountRef.current++;
        setPhase('connecting');
        retryTimerRef.current = setTimeout(connect, Math.min(delay, 30000));
      } else {
        setPhase('error');
        setStatus('error');
      }
    };
  }, [streamUrl, enabled, close, applyPatch, setStatus, setStoreRunId]);

  // Auto-connect when streamUrl is available
  useEffect(() => {
    if (streamUrl && enabled && fortuneId) {
      connect();
    }
    return close;
  }, [streamUrl, enabled, fortuneId, connect, close]);

  return { phase, lastSeq, runId, reconnect: connect };
}

/**
 * Convert A2UI DataEntry[] contents to a plain JS object.
 * DataEntry: { key, valueString?, valueNumber?, valueBoolean?, valueArray?, valueMap? }
 */
function processContents(contents: unknown): Record<string, unknown> {
  const normalizeEntry = (key: unknown, value: unknown) => normalizeStreamValue(String(key || ''), value);

  if (!Array.isArray(contents)) {
    // Sometimes payload is already a plain object
    if (contents && typeof contents === 'object') return normalizeStreamValue('', contents) as Record<string, unknown>;
    return {};
  }
  const result: Record<string, unknown> = {};
  for (const entry of contents) {
    if (!entry || typeof entry !== 'object' || !('key' in entry)) continue;
    const e = entry as Record<string, unknown>;
    if (e.valueString !== undefined) result[e.key as string] = normalizeEntry(e.key, e.valueString);
    else if (e.valueNumber !== undefined) result[e.key as string] = e.valueNumber;
    else if (e.valueBoolean !== undefined) result[e.key as string] = e.valueBoolean;
    else if (e.valueArray !== undefined) result[e.key as string] = normalizeEntry(e.key, normalizeArray(e.valueArray));
    else if (e.valueMap !== undefined) result[e.key as string] = normalizeEntry(e.key, processContents(e.valueMap));
  }
  return result;
}

/** Recursively normalize array entries that may contain nested DataEntry maps. */
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
