/**
 * useFortuneSession — lifecycle hook for fortune result pages.
 *
 * Handles the full lifecycle:
 * 1. Read fortuneId from URL params
 * 2. If fortuneId exists → replay (GET snapshot) → hydrate store
 * 3. If no fortuneId → read location.state.inputPayload → create → navigate to /:fortuneId
 * 4. Open SSE stream if status is 'streaming' or 'pending'
 * 5. Expose create/replay/stream state + existing useFortuneAsk
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useShallow } from 'zustand/react/shallow';
import { fortuneClient, FortuneApiError } from '../lib/fortuneClient';
import { authService } from '../../../services/auth';
import { useFortuneStore } from '../stores/fortuneStore';
import { useFortuneStream } from './useFortuneStream';
import { useFortuneAsk } from './useFortuneAsk';
import type { FortuneFunctionId, FortuneDataModel, FortuneStatus } from '../lib/fortuneTypes';

interface UseFortuneSessionOptions {
  functionId: FortuneFunctionId;
  /** Base route for this function, e.g. '/project/fortune-agent/custom-wish' */
  baseRoute: string;
}

interface UseFortuneSessionReturn {
  fortuneId: string | null;
  runId: string | null;
  functionId: FortuneFunctionId;
  status: FortuneStatus;
  dataModel: FortuneDataModel | null;
  persistenceDegraded: boolean;
  isReplay: boolean;
  error: string | null;
  ask: ReturnType<typeof useFortuneAsk>;
  create: (payload: Record<string, unknown>) => Promise<void>;
}

// Per-function payload mapping: input pages emit { birthDate, birthTime, timeUnknown, gender }
// (nested under `profile` / `personA` / `personB`). Backend expects a flat CreateFortuneRequest
// with `birth_iso`. This helper bridges the two shapes.
interface InputProfile {
  birthDate?: string;
  birthTime?: string | null;
  timeUnknown?: boolean;
  gender?: string;
}

function toBirthIso(p: InputProfile | undefined | null): string {
  if (!p?.birthDate) return '';
  const hour = p.timeUnknown ? '12' : (p.birthTime || '12');
  return `${p.birthDate}T${hour.padStart(2, '0')}:00:00`;
}

function buildCreateRequest(functionId: FortuneFunctionId, payload: Record<string, unknown>) {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  switch (functionId) {
    case 'compatibility': {
      const p = payload as { relationship: string; personA: InputProfile; personB: InputProfile; question?: string };
      return fortuneClient.createCompatibility({
        relationship: p.relationship,
        personA: { birth_iso: toBirthIso(p.personA), timezone: tz, gender: p.personA?.gender },
        personB: { birth_iso: toBirthIso(p.personB), timezone: tz, gender: p.personB?.gender },
        question: p.question,
      });
    }
    case 'lucky-day': {
      const p = payload as { occasion: string; profile: InputProfile; windowStart: string; windowEnd: string };
      return fortuneClient.createLuckyDay({
        profile: { birth_iso: toBirthIso(p.profile), timezone: tz, gender: p.profile?.gender },
        occasion: p.occasion,
        windowStartISO: p.windowStart,
        windowEndISO: p.windowEnd,
      });
    }
    case 'luck-cycle': {
      const p = payload as { horizon: string; focus: string; profile: InputProfile };
      return fortuneClient.createLuckCycle({
        profile: {
          birth_iso: toBirthIso(p.profile),
          timezone: tz,
          birth_time_unknown: p.profile?.timeUnknown,
          gender: p.profile?.gender,
        },
        horizon: p.horizon,
        focus: p.focus,
      });
    }
    case 'wish': {
      const p = payload as { question: string; profile: InputProfile; focus?: string; tone?: string };
      return fortuneClient.createWish({
        profile: {
          birth_iso: toBirthIso(p.profile),
          timezone: tz,
          birth_time_unknown: p.profile?.timeUnknown,
          gender: p.profile?.gender,
        },
        question: p.question,
        focus: p.focus,
        tone: p.tone,
      });
    }
  }
}

export function useFortuneSession(options: UseFortuneSessionOptions): UseFortuneSessionReturn {
  const { functionId, baseRoute } = options;
  const { fortuneId: urlFortuneId } = useParams<{ fortuneId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const createCalledRef = useRef(false);

  const {
    fortuneId,
    runId,
    status,
    dataModel,
    persistenceDegraded,
    setFortune,
    hydrateFromReplay,
    setStatus,
  } = useFortuneStore(
    useShallow((s) => ({
      fortuneId: s.fortuneId,
      runId: s.runId,
      status: s.status,
      dataModel: s.dataModel,
      persistenceDegraded: s.persistenceDegraded,
      setFortune: s.setFortune,
      hydrateFromReplay: s.hydrateFromReplay,
      setStatus: s.setStatus,
    })),
  );

  const ask = useFortuneAsk();

  // Is this a replay (arrived via URL with fortuneId and data already loaded)?
  const isReplay = !!urlFortuneId && (status === 'complete' || (status !== 'streaming' && status !== 'loading' && !!dataModel));

  // SSE stream hook
  useFortuneStream({
    fortuneId: fortuneId,
    streamUrl,
    enabled: !!streamUrl,
  });

  // Replay: load snapshot when we have a fortuneId in the URL
  useEffect(() => {
    if (!urlFortuneId) return;
    if (fortuneId === urlFortuneId && dataModel) return; // already loaded

    let cancelled = false;
    setStatus('loading');

    (async () => {
      try {
        const snapshot = await fortuneClient.getFortune(urlFortuneId);

        if (cancelled) return;

        if (snapshot === null) {
          // 202 — still pending, open stream
          const token = await authService.getAccessToken();
          setFortune(urlFortuneId, '', { functionId });
          setStreamUrl(fortuneClient.buildStreamUrl(urlFortuneId, token));
          setStatus('streaming');
          return;
        }

        // Map backend snapshot to FortuneReplayResponse shape.
        // Backend status: 'done' = complete, 'partial' = still building, else error.
        const replayStatus = (snapshot.status === 'done' || snapshot.status === 'complete')
          ? 'complete'
          : snapshot.status === 'partial'
            ? 'streaming'
            : 'error';

        // If partial, open SSE to continue streaming
        if (replayStatus === 'streaming') {
          const token = await authService.getAccessToken();
          setStreamUrl(fortuneClient.buildStreamUrl(urlFortuneId, token));
        }

        hydrateFromReplay({
          fortune_id: snapshot.fortune_id,
          run_id: '',
          function_id: (snapshot.metadata?.function_id as FortuneFunctionId) || functionId,
          status: replayStatus,
          last_seq: 0,
          metadata: {
            created_at: snapshot.metadata?.created_at || '',
            persistence_degraded: snapshot.metadata?.persistence_degraded,
          },
          data_model: {
            // Spread overview fields (kpi, score, etc.) at root
            ...(snapshot.data?.overview as Record<string, unknown> || {}),
            // Core natal data
            pillars: snapshot.data?.pillars as any,
            // Mechanics -> may contain interactions, tenGods, etc.
            ...(snapshot.data?.mechanics as Record<string, unknown> || {}),
            // Narrative
            narrative: snapshot.data?.narrative as any,
            // References -> must go into classics.references wrapper
            classics: snapshot.data?.references
              ? { references: Array.isArray(snapshot.data.references) ? snapshot.data.references : (snapshot.data.references as any)?.references || [] }
              : undefined,
            // Trace
            trace: snapshot.data?.trace as any,
            // Retrodictions -> must preserve { items: [...] } wrapper
            retrodictions: snapshot.data?.retrodictions
              ? { items: Array.isArray(snapshot.data.retrodictions) ? snapshot.data.retrodictions : (snapshot.data.retrodictions as any)?.items || [] }
              : undefined,
            // Corrections -> preserve for correction overlay
            ...(snapshot.data?.corrections ? { corrections: snapshot.data.corrections } : {}),
          } as any,
          ask_history: [],
        });
      } catch (err) {
        if (cancelled) return;
        if (err instanceof FortuneApiError) {
          if (err.status === 404) {
            setError('Fortune reading not found.');
          } else if (err.status === 503) {
            setError('Service temporarily unavailable. Please try again.');
          } else {
            setError(err.message);
          }
        } else {
          setError('Failed to load fortune reading.');
        }
        setStatus('error');
      }
    })();

    return () => { cancelled = true; };
  }, [urlFortuneId]);

  // Create: called from input pages that pass payload via location.state
  const create = useCallback(async (payload: Record<string, unknown>) => {
    if (createCalledRef.current) return;
    createCalledRef.current = true;

    try {
      setStatus('loading');
      const resp = await buildCreateRequest(functionId, payload);

      setFortune(resp.fortune_id, resp.run_id, {
        persistenceDegraded: resp.persistenceDegraded,
        functionId,
      });

      // Open SSE
      const token = await authService.getAccessToken();
      setStreamUrl(fortuneClient.buildStreamUrl(resp.fortune_id, token));
      setStatus('streaming');

      // Navigate to the fortuneId URL (replace to prevent back-to-creating)
      navigate(`${baseRoute}/${resp.fortune_id}`, { replace: true });
    } catch (err) {
      setError(err instanceof FortuneApiError ? err.message : 'Failed to create fortune reading.');
      setStatus('error');
      createCalledRef.current = false;
    }
  }, [functionId, baseRoute, navigate, setFortune, setStatus]);

  // Auto-create from location.state if no fortuneId in URL
  useEffect(() => {
    if (urlFortuneId) return; // have an ID — replay path
    const inputPayload = (location.state as Record<string, unknown>) || null;
    if (inputPayload && !createCalledRef.current) {
      create(inputPayload);
    }
  }, [urlFortuneId, location.state, create]);

  return {
    fortuneId,
    runId,
    functionId,
    status,
    dataModel,
    persistenceDegraded,
    isReplay,
    error,
    ask,
    create,
  };
}
