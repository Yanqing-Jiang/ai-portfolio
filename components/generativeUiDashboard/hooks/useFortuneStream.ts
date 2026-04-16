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

    // Pre-flight check: detect 409 conflict before opening EventSource
    // (EventSource doesn't expose HTTP status codes on error)
    fetch(streamUrl, { method: 'HEAD' }).then((res) => {
      if (res.status === 409) {
        setPhase('error');
        setStatus('error');
        // Store a conflict indicator so the UI can show a specific message
        applyPatch('/data/meta', { status: 'error', error_message: 'Another tab is already streaming this reading. Close it and try again.' });
        return;
      }
    }).catch(() => { /* ignore — EventSource will handle real connection errors */ });

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

        // Store run_id on first message
        if (run_id && !runId) {
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
      if (retryCountRef.current < MAX_RETRIES) {
        const delay = INITIAL_BACKOFF_MS * Math.pow(2, retryCountRef.current);
        retryCountRef.current++;
        setPhase('connecting');
        retryTimerRef.current = setTimeout(connect, Math.min(delay, 30000));
      } else {
        setPhase('error');
        setStatus('error');
      }
    };
  }, [streamUrl, enabled, close, applyPatch, setStatus, setStoreRunId, runId]);

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
  if (!Array.isArray(contents)) {
    // Sometimes payload is already a plain object
    if (contents && typeof contents === 'object') return contents as Record<string, unknown>;
    return {};
  }
  const result: Record<string, unknown> = {};
  for (const entry of contents) {
    if (!entry || typeof entry !== 'object' || !('key' in entry)) continue;
    const e = entry as Record<string, unknown>;
    if (e.valueString !== undefined) result[e.key as string] = e.valueString;
    else if (e.valueNumber !== undefined) result[e.key as string] = e.valueNumber;
    else if (e.valueBoolean !== undefined) result[e.key as string] = e.valueBoolean;
    else if (e.valueArray !== undefined) result[e.key as string] = normalizeArray(e.valueArray);
    else if (e.valueMap !== undefined) result[e.key as string] = processContents(e.valueMap);
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
    return item;
  });
}
