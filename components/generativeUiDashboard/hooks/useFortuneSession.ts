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
  /** True while a pause request is in flight. */
  pausing: boolean;
  /** POST /{fortuneId}/cancel — gracefully aborts the narrative agent. */
  cancel: () => Promise<void>;
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
    if (yearText && Number.isFinite(monthNumber)) return `${yearText}-${String(monthNumber).padStart(2, '0')}`;
    if (yearText) return yearText;
  }
  return 'this-year';
}

type AnyRecord = Record<string, any>;

const ELEMENT_BY_LOWER: Record<string, string> = {
  wood: 'Wood',
  fire: 'Fire',
  earth: 'Earth',
  metal: 'Metal',
  water: 'Water',
};

function asRecord(value: unknown): AnyRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as AnyRecord : {};
}

function asArray(value: unknown): any[] {
  if (Array.isArray(value)) return value;
  const record = asRecord(value);
  if (Array.isArray(record.items)) return record.items;
  if (Array.isArray(record.references)) return record.references;
  return [];
}

function pickValue(record: AnyRecord, ...keys: string[]) {
  for (const key of keys) {
    if (record[key] !== undefined && record[key] !== null) return record[key];
  }
  return undefined;
}

function normalizeElementName(value: unknown) {
  if (typeof value !== 'string') return value;
  return ELEMENT_BY_LOWER[value.trim().toLowerCase()] || value;
}

function normalizeElementMap(value: unknown) {
  const raw = asRecord(value);
  if ('Wood' in raw || 'Fire' in raw) return raw;
  return {
    Wood: Number(raw.wood ?? 0),
    Fire: Number(raw.fire ?? 0),
    Earth: Number(raw.earth ?? 0),
    Metal: Number(raw.metal ?? 0),
    Water: Number(raw.water ?? 0),
  };
}

function normalizePillar(value: unknown) {
  const raw = asRecord(value);
  if (!raw.stem && !raw.branch) return undefined;
  return {
    ...raw,
    stem: raw.stem || '',
    branch: raw.branch || '',
    stemElement: normalizeElementName(pickValue(raw, 'stemElement', 'stem_element', 'element')),
    branchElement: normalizeElementName(pickValue(raw, 'branchElement', 'branch_element')),
  };
}

function normalizePillarSet(value: unknown) {
  const raw = asRecord(value);
  return {
    year: normalizePillar(raw.year),
    month: normalizePillar(raw.month),
    day: normalizePillar(raw.day),
    hour: raw.hour ? normalizePillar(raw.hour) : undefined,
    dayMaster: pickValue(raw, 'dayMaster', 'day_master'),
    dayMasterElement: normalizeElementName(pickValue(raw, 'dayMasterElement', 'day_master_element')),
    birthTimeUnknown: pickValue(raw, 'birthTimeUnknown', 'birth_time_unknown') || false,
  };
}

function normalizeHiddenStems(value: unknown) {
  const raw = asRecord(value);
  return Object.fromEntries(Object.entries(raw).map(([pillar, stems]) => [
    pillar,
    asArray(stems).map((stem) => {
      const item = asRecord(stem);
      return {
        stem: item.stem || '',
        element: normalizeElementName(item.element) || '',
        strength: item.strength || 'trace',
      };
    }),
  ]));
}

function normalizeTenGods(value: unknown) {
  return asArray(value).map((god) => {
    const item = asRecord(god);
    return {
      ...item,
      pillar: item.pillar || '',
      position: item.position || '',
      god: item.god || item.name || '',
      description: item.description || item.english,
    };
  });
}

function normalizeInteraction(value: unknown) {
  const item = asRecord(value);
  const between = item.between;
  const parts = Array.isArray(between)
    ? between
    : typeof between === 'string'
      ? between.replace('->', '-').split('-').map((part) => part.trim()).filter(Boolean)
      : [];
  return {
    ...item,
    type: item.type || 'interaction',
    from: item.from || item.from_ || parts[0] || '',
    to: item.to || parts[1] || '',
    effect: item.effect || item.resultElement || item.result_element,
    description: item.description || '',
  };
}

function normalizeSeasonalStrength(value: unknown) {
  const raw = asRecord(value);
  if (!Object.keys(raw).length) return undefined;
  return {
    ...raw,
    dayMasterElement: normalizeElementName(pickValue(raw, 'dayMasterElement', 'day_master_element')),
    monthBranch: pickValue(raw, 'monthBranch', 'month_branch'),
    strength: raw.strength || raw.label || 'moderate',
    score: Number(raw.score ?? 0),
    description: raw.description || raw.label,
  };
}

function normalizeLuckPillar(value: unknown) {
  const raw = asRecord(value);
  return {
    ...raw,
    startAge: Number(pickValue(raw, 'startAge', 'start_age') ?? 0),
    endAge: Number(pickValue(raw, 'endAge', 'end_age') ?? 0),
    startYear: Number(pickValue(raw, 'startYear', 'start_year') ?? 0),
    endYear: Number(pickValue(raw, 'endYear', 'end_year') ?? 0),
    stem: raw.stem || '',
    branch: raw.branch || '',
    stemElement: normalizeElementName(pickValue(raw, 'stemElement', 'stem_element')),
    branchElement: normalizeElementName(pickValue(raw, 'branchElement', 'branch_element')),
  };
}

function normalizeAnnualPillar(value: unknown) {
  const raw = asRecord(value);
  return {
    ...raw,
    year: Number(raw.year ?? 0),
    stem: raw.stem || '',
    branch: raw.branch || '',
    stemElement: normalizeElementName(pickValue(raw, 'stemElement', 'stem_element')),
    branchElement: normalizeElementName(pickValue(raw, 'branchElement', 'branch_element')),
    luckPillarIndex: pickValue(raw, 'luckPillarIndex', 'luck_pillar_index'),
    interactions: asArray(pickValue(raw, 'interactions', 'interactions_with_chart')).map(normalizeInteraction),
  };
}

function inferMechanismType(scope: string, item: AnyRecord) {
  const explicit = typeof item.type === 'string' && item.type.trim() ? item.type.trim() : '';
  if (explicit) return explicit;
  const text = `${item.title || ''} ${asArray(item.bullets).join(' ')}`.toLowerCase();
  if (scope === 'compatibility') {
    if (text.includes('clash')) return 'clash';
    if (text.includes('harm')) return 'harm';
    if (text.includes('punish')) return 'punishment';
    if (text.includes('combine')) return 'combination';
    return 'support';
  }
  if (scope === 'occasion') {
    if (text.includes('avoid') || text.includes('clash')) return 'Caution';
    if (text.includes('element') || ['wood', 'fire', 'earth', 'metal', 'water'].some((e) => text.includes(e))) return 'Element';
    return 'Timing';
  }
  if (scope === 'wish') {
    if (text.includes('luck') || text.includes('cycle')) return 'luck';
    if (text.includes('clash') || text.includes('combine') || text.includes('interaction')) return 'interaction';
    return 'chart';
  }
  return 'support';
}

function normalizeMechanism(value: unknown, scope: string) {
  const raw = asRecord(value);
  return {
    id: raw.id,
    title: raw.title || 'Why this matters',
    type: inferMechanismType(scope, raw),
    icon: raw.icon,
    bullets: asArray(raw.bullets).map(String),
    citationIds: pickValue(raw, 'citationIds', 'citation_ids') || [],
  };
}

function normalizePick(value: unknown) {
  const raw = asRecord(value);
  const pillar = asRecord(raw.dayPillar);
  return {
    rank: Number(raw.rank ?? 0),
    date: raw.date || '',
    dayPillar: {
      stem: raw.day_pillar_stem || raw.dayPillarStem || pillar.stem || '',
      branch: raw.day_pillar_branch || raw.dayPillarBranch || pillar.branch || '',
    },
    score: Number(raw.score ?? 0),
    oneLineReason: raw.one_line_reason || raw.oneLineReason || '',
    bestHours: pickValue(raw, 'bestHours', 'best_hours') || [],
    mechanisms: asArray(raw.mechanisms).map((item) => normalizeMechanism(item, 'occasion')),
  };
}

function buildCalendarFromPicks(picks: ReturnType<typeof normalizePick>[]) {
  const first = picks.find((pick) => /^\d{4}-\d{2}-\d{2}/.test(pick.date));
  if (!first) return undefined;
  const date = new Date(`${first.date.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return undefined;
  return {
    month: String(date.getMonth() + 1).padStart(2, '0'),
    year: date.getFullYear(),
    days: picks.map((pick) => ({
      date: pick.date.slice(0, 10),
      pillar: pick.dayPillar,
      score: pick.score,
    })),
  };
}

function normalizeOccasion(value: unknown) {
  const raw = asRecord(value);
  const topPicks = asArray(pickValue(raw, 'topPicks', 'top_picks')).map(normalizePick);
  const calendarRaw = asRecord(raw.calendar);
  const analysisRaw = asRecord(raw.analysis);
  return {
    topPicks,
    calendar: calendarRaw.days ? {
      month: String(calendarRaw.month || '').padStart(2, '0'),
      year: Number(calendarRaw.year || 0),
      days: asArray(calendarRaw.days),
    } : buildCalendarFromPicks(topPicks),
    analysis: Object.keys(analysisRaw).length ? {
      occasionType: pickValue(analysisRaw, 'occasionType', 'occasion_type') || '',
      keyElements: asArray(pickValue(analysisRaw, 'keyElements', 'key_elements')).map((item) => String(item).trim()).filter(Boolean),
      avoidElements: asArray(pickValue(analysisRaw, 'avoidElements', 'avoid_elements')).map((item) => String(item).trim()).filter(Boolean),
      description: analysisRaw.description || '',
    } : undefined,
    mechanisms: asArray(raw.mechanisms).map((item) => normalizeMechanism(item, 'occasion')),
  };
}

function normalizeWish(value: unknown) {
  const raw = asRecord(value);
  const verdict = asRecord(raw.verdict);
  return {
    verdict: Object.keys(verdict).length ? {
      title: verdict.title || '',
      score: verdict.score,
      summary: verdict.summary || '',
      caution: verdict.caution,
      conditions: asArray(verdict.conditions).map((condition) => {
        const item = asRecord(condition);
        const text = typeof condition === 'string' ? condition : item.text || item.label || item.description || '';
        return { type: item.type || 'warn', text };
      }).filter((condition) => condition.text),
    } : undefined,
    anchors: asArray(raw.anchors).map((anchor) => {
      const item = asRecord(anchor);
      return {
        id: item.id,
        label: item.label || '',
        symbol: item.symbol || '',
        element: item.element,
        relevance: Number(item.relevance ?? 0.5),
        bullets: asArray(item.bullets).map(String),
      };
    }),
    mechanisms: asArray(raw.mechanisms).map((item) => normalizeMechanism(item, 'wish')),
  };
}

function normalizeLuckCycle(value: unknown, mechanics: AnyRecord) {
  const raw = asRecord(value);
  const rawTimeline = asRecord(raw.timeline);
  const decades = asArray(rawTimeline.decades).length
    ? asArray(rawTimeline.decades).map(normalizeLuckPillar)
    : asArray(mechanics.luck_pillars).map(normalizeLuckPillar);
  const years = asArray(rawTimeline.years).length
    ? asArray(rawTimeline.years).map(normalizeAnnualPillar)
    : asArray(mechanics.annual_pillars).map(normalizeAnnualPillar);
  const rawWindow = asRecord(pickValue(raw, 'currentWindow', 'current_window'));
  const currentYear = new Date().getFullYear();
  const active = decades.find((pillar) => pillar.startYear <= currentYear && currentYear <= pillar.endYear) || decades[0];
  return {
    currentWindow: Object.keys(rawWindow).length ? {
      decade: rawWindow.decade || '',
      score: Number(rawWindow.score ?? 0),
      summary: rawWindow.summary || '',
      element: rawWindow.element,
    } : active ? {
      decade: `${active.startYear}-${active.endYear}`,
      score: Number(mechanics.harmony_score ?? 0),
      summary: `Active decade ${active.stem}${active.branch} is shaping this timing window.`,
      element: active.stemElement || active.branchElement,
    } : undefined,
    timeline: { decades, years, months: asArray(rawTimeline.months) },
    mechanisms: asArray(raw.mechanisms).map((item) => normalizeMechanism(item, 'luck_cycle')),
  };
}

function normalizePersonChart(value: unknown, fallbackPillars: unknown, fallbackMechanics: AnyRecord, fallbackElements: unknown) {
  const raw = asRecord(value);
  const mechanics = { ...fallbackMechanics, ...asRecord(raw.mechanics) };
  return {
    name: raw.name,
    dayMaster: pickValue(raw, 'dayMaster', 'day_master') || pickValue(asRecord(fallbackPillars), 'dayMaster', 'day_master'),
    dayMasterElement: normalizeElementName(pickValue(raw, 'dayMasterElement', 'day_master_element') || pickValue(asRecord(fallbackPillars), 'dayMasterElement', 'day_master_element')),
    pillars: normalizePillarSet(raw.pillars || fallbackPillars),
    elements: normalizeElementMap(raw.elements || fallbackElements),
    tenGods: normalizeTenGods(raw.tenGods || mechanics.ten_gods),
    hiddenStems: normalizeHiddenStems(raw.hiddenStems || mechanics.hidden_stems),
  };
}

function normalizeCompatibility(value: unknown, pillarsSnapshot: AnyRecord, mechanics: AnyRecord) {
  const raw = asRecord(value);
  const overview = asRecord(raw.overview);
  const personB = asRecord(pillarsSnapshot.person_b);
  return {
    overview: Object.keys(overview).length ? {
      score: Number(overview.score ?? 0),
      summary: overview.summary || '',
      relationship: overview.relationship || '',
      strengths: asArray(overview.strengths).map(String),
      frictions: asArray(overview.frictions).map(String),
    } : undefined,
    personA: normalizePersonChart(raw.personA, pillarsSnapshot.pillars, mechanics, pillarsSnapshot.elements),
    personB: Object.keys(personB).length
      ? normalizePersonChart(raw.personB || personB, personB.pillars, asRecord(personB.mechanics), personB.elements)
      : raw.personB
        ? normalizePersonChart(raw.personB, undefined, {}, undefined)
        : undefined,
    pairInteractions: asArray(pickValue(raw, 'pairInteractions', 'pair_interactions')).map((item) => {
      const ix = normalizeInteraction(item);
      return {
        ...ix,
        personA: pickValue(asRecord(item), 'personA', 'person_a') || 'Person A',
        personB: pickValue(asRecord(item), 'personB', 'person_b') || 'Person B',
      };
    }),
    mechanisms: asArray(raw.mechanisms).map((item) => normalizeMechanism(item, 'compatibility')),
  };
}

function normalizeNarrative(value: unknown) {
  const raw = asRecord(value);
  return {
    tldr: raw.tldr || '',
    insights: asArray(raw.insights).map((insight) => {
      const item = asRecord(insight);
      return {
        id: item.id || item.heading || 'insight',
        icon: item.icon || 'sparkles',
        heading: item.heading || '',
        tagline: item.tagline || '',
        bullets: asArray(item.bullets).map((bullet) => {
          const b = asRecord(bullet);
          return { icon: b.icon || 'check', text: b.text || String(bullet || '') };
        }),
        citations: asArray(item.citations).map(String),
      };
    }),
    yearPredictions: asArray(pickValue(raw, 'yearPredictions', 'year_predictions')).map((prediction) => {
      const item = asRecord(prediction);
      return {
        year: Number(item.year || 0),
        prediction: item.prediction || '',
        confidence: Number(item.confidence || 0),
        evidenceRefs: pickValue(item, 'evidenceRefs', 'evidence_refs') || [],
      };
    }),
    isComplete: true,
  };
}

function normalizeReferences(value: unknown) {
  return asArray(value).map((reference) => {
    const item = asRecord(reference);
    return {
      id: item.id || `${item.source || 'ref'}-${String(item.passage || item.quote || '').slice(0, 24)}`,
      source: item.source || '',
      quote: item.quote || item.passage || '',
      passage: item.passage || item.quote || '',
      translation: item.translation || '',
      rationale: item.rationale || item.relevance || '',
    };
  });
}

export function buildReplayDataModel(snapshot: Awaited<ReturnType<typeof fortuneClient.getFortune>>, functionId: FortuneFunctionId): FortuneDataModel {
  const data = asRecord(snapshot?.data);
  const overview = asRecord(data.overview);
  const pillarsSnapshot = asRecord(data.pillars);
  const mechanics = asRecord(data.mechanics);
  const narrative = asRecord(data.narrative);
  const pillarsRaw = pillarsSnapshot.pillars || mechanics.pillars || pillarsSnapshot;
  const luckCycle = normalizeLuckCycle(narrative.luck_cycle, mechanics);
  const occasion = normalizeOccasion(narrative.occasion);
  const compatibility = normalizeCompatibility(narrative.compatibility, pillarsSnapshot, mechanics);
  const wish = normalizeWish(narrative.wish);

  return {
    ...overview,
    kpi: {
      ...(asRecord(overview.kpi)),
      dayMaster: pickValue(asRecord(pillarsRaw), 'dayMaster', 'day_master') || asRecord(asRecord(pillarsRaw).day).stem,
      dayMasterElement: normalizeElementName(pickValue(asRecord(pillarsRaw), 'dayMasterElement', 'day_master_element')),
      harmonyScore: mechanics.harmony_score,
      currentCycle: luckCycle.currentWindow?.decade,
      seasonalStrength: normalizeSeasonalStrength(mechanics.seasonal_strength)?.strength,
      seasonalScore: normalizeSeasonalStrength(mechanics.seasonal_strength)?.score,
    },
    pillars: normalizePillarSet(pillarsRaw) as any,
    elements: normalizeElementMap(pillarsSnapshot.elements || mechanics.enhanced_element_counts),
    hiddenStems: normalizeHiddenStems(mechanics.hidden_stems),
    tenGods: { items: normalizeTenGods(mechanics.ten_gods) },
    interactions: { items: asArray(mechanics.interactions).map(normalizeInteraction) },
    seasonalStrength: normalizeSeasonalStrength(mechanics.seasonal_strength) as any,
    elementBySource: mechanics.element_by_source,
    luckPillars: { items: asArray(mechanics.luck_pillars).map(normalizeLuckPillar) },
    annualPillars: { items: asArray(mechanics.annual_pillars).map(normalizeAnnualPillar) },
    narrative: normalizeNarrative(narrative) as any,
    classics: { references: normalizeReferences(data.references) as any },
    trace: data.trace as any,
    retrodictions: data.retrodictions
      ? { items: asArray(data.retrodictions) as any }
      : undefined,
    ...(data.corrections ? { corrections: data.corrections } : {}),
    ...(functionId === 'wish' || Object.keys(asRecord(narrative.wish)).length ? { wish: wish as any } : {}),
    ...(functionId === 'luck-cycle' || Object.keys(asRecord(narrative.luck_cycle)).length ? { luckCycle: luckCycle as any } : {}),
    ...(functionId === 'compatibility' || Object.keys(asRecord(narrative.compatibility)).length ? { compatibility: compatibility as any } : {}),
    ...(functionId === 'lucky-day' || Object.keys(asRecord(narrative.occasion)).length ? { occasion: occasion as any } : {}),
  } as FortuneDataModel;
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
  const streamStartedForRef = useRef<string | null>(null);

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

  const startStreamForFortune = useCallback(async (id: string) => {
    if (streamStartedForRef.current === id) {
      setStatus('streaming');
      return;
    }
    streamStartedForRef.current = id;
    const token = await authService.getAccessToken();
    setStreamUrl(fortuneClient.buildStreamUrl(id, token));
    setStatus('streaming');
  }, [setStatus]);

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
    if (
      fortuneId === urlFortuneId
      && (dataModel || streamStartedForRef.current === urlFortuneId || status === 'streaming')
    ) {
      return;
    }

    let cancelled = false;
    setStatus('loading');

    (async () => {
      try {
        const snapshot = await fortuneClient.getFortune(urlFortuneId);

        if (cancelled) return;

        if (snapshot === null) {
          // 202 — still pending, open stream
          setFortune(urlFortuneId, '', { functionId });
          await startStreamForFortune(urlFortuneId);
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
          await startStreamForFortune(urlFortuneId);
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
          data_model: buildReplayDataModel(snapshot, functionId),
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
      await startStreamForFortune(resp.fortune_id);

      // Navigate to the fortuneId URL (replace to prevent back-to-creating)
      navigate(`${baseRoute}/${resp.fortune_id}`, { replace: true });
    } catch (err) {
      setError(err instanceof FortuneApiError ? err.message : 'Failed to create fortune reading.');
      setStatus('error');
      createCalledRef.current = false;
    }
  }, [functionId, baseRoute, navigate, setFortune, setStatus, startStreamForFortune]);

  // Auto-create from location.state if no fortuneId in URL
  useEffect(() => {
    if (urlFortuneId) return; // have an ID — replay path
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
      // Best-effort — the backend will also cancel on client disconnect.
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
    ask,
    create,
    pausing,
    cancel,
  };
}
