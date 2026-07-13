/**
 * useFortuneSession — lifecycle hook for fortune result pages.
 *
 * Phase 3B: replay hydrates Zustand from GET data_model (schema_version=2).
 * Legacy buildReplayDataModel normalizer deleted.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useShallow } from 'zustand/react/shallow';
import { fortuneClient, FortuneApiError } from '../lib/fortuneClient';
import { authService } from '../../../services/auth';
import { useFortuneStore } from '../stores/fortuneStore';
import { useFortuneStream, hydrateDataModelFromSnapshot } from './useFortuneStream';
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
  create: (payload: Record<string, unknown>) => Promise<void>;
  pausing: boolean;
  cancel: () => Promise<void>;
}

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

function normalizeLuckCycleFocus(value: unknown): string {
  if (Array.isArray(value)) {
    return value
      .map((item) => String(item || '').trim())
      .filter(Boolean)
      .join('+') || 'general';
  }
  if (typeof value === 'string' && value.trim()) return value.trim();
  return 'general';
}

function normalizeLuckCycleHorizon(value: unknown): string {
  if (typeof value === 'string' && value.trim()) return value.trim();
  if (typeof value === 'object' && value !== null) {
    const { year, month } = value as { year?: unknown; month?: unknown };
    const yearText = typeof year === 'number' || typeof year === 'string' ? String(year).trim() : '';
    const monthNumber = typeof month === 'number' ? month : Number(month);
    if (yearText && Number.isFinite(monthNumber)) {
      return `${yearText}-${String(monthNumber).padStart(2, '0')}`;
    }
    if (yearText) return yearText;
  }
  return 'this-year';
}

function buildCreateRequest(functionId: FortuneFunctionId, payload: Record<string, unknown>) {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  switch (functionId) {
    case 'compatibility': {
      const p = payload as {
        relationship: string;
        personA: InputProfile;
        personB: InputProfile;
        question?: string;
      };
      return fortuneClient.createCompatibility({
        relationship: p.relationship,
        personA: {
          birth_iso: toBirthIso(p.personA),
          timezone: tz,
          gender: p.personA?.gender,
          birth_time_unknown: p.personA?.timeUnknown,
        },
        personB: {
          birth_iso: toBirthIso(p.personB),
          timezone: tz,
          gender: p.personB?.gender,
          birth_time_unknown: p.personB?.timeUnknown,
        },
        question: p.question,
      });
    }
    case 'lucky-day': {
      const p = payload as {
        occasion: string;
        profile: InputProfile;
        windowStart: string;
        windowEnd: string;
      };
      return fortuneClient.createLuckyDay({
        profile: {
          birth_iso: toBirthIso(p.profile),
          timezone: tz,
          gender: p.profile?.gender,
          birth_time_unknown: p.profile?.timeUnknown,
        },
        occasion: p.occasion,
        windowStartISO: p.windowStart,
        windowEndISO: p.windowEnd,
      });
    }
    case 'luck-cycle': {
      const p = payload as { horizon: unknown; focus: unknown; profile: InputProfile };
      return fortuneClient.createLuckCycle({
        profile: {
          birth_iso: toBirthIso(p.profile),
          timezone: tz,
          birth_time_unknown: p.profile?.timeUnknown,
          gender: p.profile?.gender,
        },
        horizon: normalizeLuckCycleHorizon(p.horizon),
        focus: normalizeLuckCycleFocus(p.focus),
      });
    }
    case 'wish': {
      const p = payload as {
        question: string;
        profile: InputProfile;
        focus?: string;
        tone?: string;
      };
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


function extractBirthTimeUnknown(functionId: FortuneFunctionId, payload: Record<string, unknown>): boolean {
  if (functionId === 'compatibility') {
    const p = payload as { personA?: InputProfile };
    return !!p.personA?.timeUnknown;
  }
  const p = payload as { profile?: InputProfile };
  return !!p.profile?.timeUnknown;
}

function mapReplayStatus(status: string): 'complete' | 'streaming' | 'error' {
  if (status === 'done' || status === 'complete') return 'complete';
  if (status === 'partial') return 'streaming';
  return 'error';
}

export function useFortuneSession(options: UseFortuneSessionOptions): UseFortuneSessionReturn {
  const { functionId, baseRoute } = options;
  const { fortuneId: urlFortuneId } = useParams<{ fortuneId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const createCalledRef = useRef(false);
  const streamStartedForRef = useRef<string | null>(null);
  const hydrationGenerationRef = useRef(0);

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

  const startStreamForFortune = useCallback(async (
    id: string,
    hydrationGeneration?: number,
  ) => {
    if (
      hydrationGeneration !== undefined &&
      hydrationGenerationRef.current !== hydrationGeneration
    ) return false;
    if (streamStartedForRef.current === id && streamUrl) {
      setStatus('streaming');
      return true;
    }
    const token = await authService.getAccessToken();
    if (
      hydrationGeneration !== undefined &&
      hydrationGenerationRef.current !== hydrationGeneration
    ) return false;
    streamStartedForRef.current = id;
    setStreamUrl(fortuneClient.buildStreamUrl(id, token));
    setStatus('streaming');
    return true;
  }, [setStatus, streamUrl]);

  const hydrateSnapshot = useCallback(async (id: string) => {
    const generation = ++hydrationGenerationRef.current;
    const snapshot = await fortuneClient.getFortune(id);
    if (hydrationGenerationRef.current !== generation) return undefined;
    if (snapshot === null) {
      setFortune(id, '', { functionId });
      if (!await startStreamForFortune(id, generation)) return undefined;
      return null;
    }

    const replayStatus = mapReplayStatus(snapshot.status);
    const model = hydrateDataModelFromSnapshot(snapshot, functionId);

    hydrateFromReplay({
      fortune_id: snapshot.fortune_id,
      run_id: '',
      function_id: (snapshot.metadata?.function_id as FortuneFunctionId) || functionId,
      status: replayStatus,
      last_seq: 0,
      metadata: {
        created_at: snapshot.metadata?.created_at || '',
        persistence_degraded: snapshot.metadata?.persistence_degraded,
        birth_time_unknown: snapshot.metadata?.birth_time_unknown,
      },
      data_model: model,
      ask_history: [],
    });

    return { snapshot, replayStatus, generation };
  }, [functionId, hydrateFromReplay, setFortune, startStreamForFortune]);

  const handleResyncRequired = useCallback(async () => {
    const id = fortuneId || urlFortuneId;
    if (!id) return;
    streamStartedForRef.current = null;
    setStreamUrl(null);
    const result = await hydrateSnapshot(id);
    if (result === undefined) return;
    if (result?.replayStatus === 'streaming') {
      await startStreamForFortune(id, result.generation);
    }
  }, [fortuneId, urlFortuneId, hydrateSnapshot, startStreamForFortune]);

  const isReplay =
    !!urlFortuneId &&
    (status === 'complete' ||
      (status !== 'streaming' && status !== 'loading' && !!dataModel));

  useFortuneStream({
    fortuneId,
    streamUrl,
    enabled: !!streamUrl,
    onResyncRequired: handleResyncRequired,
  });

  useEffect(() => {
    if (!urlFortuneId) return;
    if (
      fortuneId === urlFortuneId &&
      (dataModel || streamStartedForRef.current === urlFortuneId || status === 'streaming')
    ) {
      return;
    }

    let cancelled = false;
    setStatus('loading');

    (async () => {
      try {
        const result = await hydrateSnapshot(urlFortuneId);
        if (cancelled || result === undefined) return;
        if (result === null) return; // pending → stream opened
        if (result.replayStatus === 'streaming') {
          await startStreamForFortune(urlFortuneId, result.generation);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof FortuneApiError) {
          if (err.status === 404) setError('Fortune reading not found.');
          else if (err.status === 503) {
            setError('Service temporarily unavailable. Please try again.');
          } else setError(err.message);
        } else {
          setError('Failed to load fortune reading.');
        }
        setStatus('error');
      }
    })();

    return () => {
      cancelled = true;
      // Invalidate the in-flight fetch before its first store mutation. This
      // prevents a delayed response for the old route from replacing the new
      // fortune and clearing its Ask conversation.
      hydrationGenerationRef.current += 1;
    };
  }, [urlFortuneId]);

  const create = useCallback(async (payload: Record<string, unknown>) => {
    if (createCalledRef.current) return;
    createCalledRef.current = true;

    try {
      setStatus('loading');
      const resp = await buildCreateRequest(functionId, payload);

      setFortune(resp.fortune_id, resp.run_id, {
        persistenceDegraded: resp.persistenceDegraded,
        functionId,
        birthTimeUnknown: extractBirthTimeUnknown(functionId, payload),
      });

      await startStreamForFortune(resp.fortune_id);
      navigate(`${baseRoute}/${resp.fortune_id}`, { replace: true });
    } catch (err) {
      setError(err instanceof FortuneApiError ? err.message : 'Failed to create fortune reading.');
      setStatus('error');
      createCalledRef.current = false;
    }
  }, [functionId, baseRoute, navigate, setFortune, setStatus, startStreamForFortune]);

  useEffect(() => {
    if (urlFortuneId) return;
    const inputPayload = (location.state as Record<string, unknown>) || null;
    if (inputPayload && !createCalledRef.current) {
      create(inputPayload);
    }
  }, [urlFortuneId, location.state, create]);

  const [pausing, setPausing] = useState(false);
  const cancel = useCallback(async () => {
    const id = fortuneId || urlFortuneId;
    if (!id) return;
    setPausing(true);
    try {
      await fortuneClient.cancelFortune(id);
    } catch {
      // best-effort
    }
  }, [fortuneId, urlFortuneId]);

  return {
    fortuneId,
    runId,
    functionId,
    status,
    dataModel,
    persistenceDegraded,
    isReplay,
    error,
    create,
    pausing,
    cancel,
  };
}
