/**
 * Per-function result-page config keyed by canonical ids from lib/fortuneRoutes.ts.
 * Phase 5: Observatory chrome metadata + KPI extractors (no new backend fields).
 */
import {
  CalendarDays,
  CalendarRange,
  Compass,
  Gauge,
  HeartHandshake,
  Layers,
  MessageCircle,
  Microscope,
  Sparkles,
  Star,
} from 'lucide-react';
import type { CanonicalFortuneFunction } from '../../../../lib/fortuneRoutes';
import { fortuneIntakeRoute } from '../../../../lib/fortuneRoutes';
import type { FortunePurposeId } from '../../fortuneAgentTheme';
import type {
  FortuneDataModel,
  FortuneFunctionId,
  LuckPillar,
  OccasionPick,
} from '../../lib/fortuneTypes';
import type { FortuneTab } from '../../FortuneAgentResultShell';
import { FORTUNE_THEMES } from '../../fortuneAgentTheme';

export interface FortuneResultConfig {
  canonicalId: CanonicalFortuneFunction;
  /** Theme purpose id (legacy slug-shaped). */
  purpose: FortunePurposeId;
  /** Session / create API function id (legacy). */
  sessionFunctionId: FortuneFunctionId;
  baseRoute: string;
  eyebrow: string;
  /** Static subtitle; wish overrides via location.state.question. */
  subtitle?: string;
  /** CJK glyph watermark / kicker prefix (from FORTUNE_THEMES). */
  glyph: string;
  /** CJK title used in kicker, e.g. 擇日. */
  cjkTitle: string;
  /** English function label in kicker. */
  functionLabel: string;
  tabs: FortuneTab[];
  defaultTab: string;
  loadingMessage: string;
  spinnerClass: string;
}

export interface ResultKpi {
  value: string;
  label: string;
}

export const FORTUNE_RESULT_CONFIG: Record<
  CanonicalFortuneFunction,
  FortuneResultConfig
> = {
  wish: {
    canonicalId: 'wish',
    purpose: 'custom-wish',
    sessionFunctionId: 'wish',
    baseRoute: fortuneIntakeRoute('wish'),
    eyebrow: 'Custom Wish',
    glyph: FORTUNE_THEMES['custom-wish'].glyph,
    cjkTitle: '問卜',
    functionLabel: 'Custom Wish',
    tabs: [
      { id: 'Verdict', label: 'Outlook', icon: Compass },
      { id: 'Anchor', label: 'Chart', icon: Sparkles },
      { id: 'Why', label: 'Why', icon: Microscope },
      { id: 'Ask', label: 'Ask', icon: MessageCircle },
    ],
    defaultTab: 'Verdict',
    loadingMessage: 'Preparing your reading...',
    spinnerClass: 'border-teal-500/30 border-t-teal-500',
  },
  cycle: {
    canonicalId: 'cycle',
    purpose: 'luck-draw',
    sessionFunctionId: 'luck-cycle',
    baseRoute: fortuneIntakeRoute('cycle'),
    eyebrow: 'Cycle Reading',
    subtitle: '運勢 · Year & Month',
    glyph: FORTUNE_THEMES['luck-draw'].glyph,
    cjkTitle: '運勢',
    functionLabel: 'Cycle Reading',
    tabs: [
      { id: 'Now', label: 'Now', icon: Gauge },
      { id: 'Timeline', label: 'Years', icon: CalendarRange },
      { id: 'Why', label: 'Why', icon: Microscope },
      { id: 'Ask', label: 'Ask', icon: MessageCircle },
    ],
    defaultTab: 'Now',
    loadingMessage: 'Calculating your cycles...',
    spinnerClass: 'border-indigo-500/30 border-t-indigo-500',
  },
  compatibility: {
    canonicalId: 'compatibility',
    purpose: 'compatibility',
    sessionFunctionId: 'compatibility',
    baseRoute: fortuneIntakeRoute('compatibility'),
    eyebrow: 'Compatibility',
    subtitle: '兩命 · Two Charts',
    glyph: FORTUNE_THEMES.compatibility.glyph,
    cjkTitle: '兩命',
    functionLabel: 'Compatibility',
    tabs: [
      { id: 'Overview', label: 'Match', icon: HeartHandshake },
      { id: 'Pillars', label: 'Charts', icon: Layers },
      { id: 'Why', label: 'Why', icon: Microscope },
      { id: 'Ask', label: 'Ask', icon: MessageCircle },
    ],
    defaultTab: 'Overview',
    loadingMessage: 'Comparing your charts...',
    spinnerClass: 'border-rose-500/30 border-t-rose-500',
  },
  occasion: {
    canonicalId: 'occasion',
    purpose: 'lucky-day',
    sessionFunctionId: 'lucky-day',
    baseRoute: fortuneIntakeRoute('occasion'),
    eyebrow: 'Occasion',
    subtitle: '擇日 · Auspicious Date',
    glyph: FORTUNE_THEMES['lucky-day'].glyph,
    cjkTitle: '擇日',
    functionLabel: 'Auspicious Date',
    tabs: [
      { id: 'TopPicks', label: 'Best days', icon: Star },
      { id: 'Calendar', label: 'Calendar', icon: CalendarDays },
      { id: 'Why', label: 'Why', icon: Microscope },
      { id: 'Ask', label: 'Ask', icon: MessageCircle },
    ],
    defaultTab: 'TopPicks',
    loadingMessage: 'Finding auspicious dates...',
    spinnerClass: 'border-amber-500/30 border-t-amber-500',
  },
};

function dash(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—';
  return String(v);
}

function asKpi(model: FortuneDataModel | null | undefined): Record<string, unknown> {
  return (model?.kpi as Record<string, unknown> | undefined) || {};
}

function birthElementLabel(model: FortuneDataModel | null | undefined): string {
  return dash(asKpi(model).dayMasterElement);
}

function formatHours(hours?: string[]): string {
  if (!hours || hours.length === 0) return '—';
  return hours.slice(0, 2).join(' · ');
}

function spotlightYear(model: FortuneDataModel | null | undefined): string {
  const years =
    model?.narrative?.yearPredictions ||
    model?.luckCycle?.timeline?.years ||
    model?.annualPillars?.items ||
    [];
  const now = new Date().getFullYear();
  let best: { year: number; score: number } | null = null;
  for (const y of years) {
    const year = typeof (y as { year?: number }).year === 'number' ? (y as { year: number }).year : NaN;
    if (!Number.isFinite(year) || year < now) continue;
    const score =
      typeof (y as { confidence?: number }).confidence === 'number'
        ? (y as { confidence: number }).confidence
        : typeof (y as { score?: number }).score === 'number'
          ? (y as { score: number }).score
          : 0;
    if (!best || score > best.score) best = { year, score };
  }
  return best ? String(best.year) : '—';
}

/**
 * Interpretive support for the dated guidance — how much chart evidence backs
 * it, on a 0–100 scale. Deliberately not a percentage or a likelihood.
 */
function wishSupportScore(model: FortuneDataModel | null | undefined): string {
  const preds = model?.narrative?.yearPredictions;
  if (preds && preds.length > 0) {
    const avg =
      preds.reduce((s, p) => s + (typeof p.confidence === 'number' ? p.confidence : 0), 0) /
      preds.length;
    if (avg > 0) return `${Math.round(avg * 100)}/100`;
  }
  const seasonal = asKpi(model).seasonalScore;
  if (typeof seasonal === 'number') return `${Math.round(seasonal)}/100`;
  const score = model?.wish?.verdict?.score ?? asKpi(model).harmonyScore;
  if (typeof score === 'number') return `${Math.round(score)}/100`;
  return '—';
}

/** 4 KPI cards per function — values already present on dataModel only. */
export function buildResultKpis(
  canonicalId: CanonicalFortuneFunction,
  dataModel: FortuneDataModel | null | undefined,
): ResultKpi[] {
  const kpi = asKpi(dataModel);

  if (canonicalId === 'occasion') {
    const picks = (dataModel?.occasion?.topPicks || []) as OccasionPick[];
    const windowDays = dataModel?.occasion?.calendar?.days?.length;
    const top = picks[0];
    return [
      { value: dash(top?.score), label: 'Top score' },
      { value: birthElementLabel(dataModel), label: 'Birth element' },
      {
        value:
          windowDays && picks.length
            ? `${picks.length} / ${windowDays}`
            : dash(picks.length || undefined),
        label: 'Days qualified',
      },
      { value: formatHours(top?.bestHours), label: 'Prime hours' },
    ];
  }

  if (canonicalId === 'cycle') {
    const window = dataModel?.luckCycle?.currentWindow;
    const decades = (dataModel?.luckPillars?.items ||
      dataModel?.luckCycle?.timeline?.decades ||
      []) as LuckPillar[];
    const current =
      window?.decade ||
      decades.find((d) => d.isCurrent)?.stem ||
      (kpi.currentCycle as string | undefined);
    return [
      {
        value: dash(window?.score ?? kpi.harmonyScore),
        label: 'Vitality score',
      },
      { value: birthElementLabel(dataModel), label: 'Birth element' },
      { value: dash(current), label: 'Current decade' },
      { value: spotlightYear(dataModel), label: 'Year spotlight' },
    ];
  }

  if (canonicalId === 'compatibility') {
    const overview = dataModel?.compatibility?.overview;
    return [
      { value: dash(overview?.score ?? kpi.harmonyScore), label: 'Harmony score' },
      { value: dash(overview?.relationship), label: 'Relationship' },
      { value: dash(overview?.strengths?.length), label: 'Strengths' },
      { value: dash(overview?.frictions?.length), label: 'Frictions' },
    ];
  }

  // wish
  const themes =
    dataModel?.narrative?.insights?.length ??
    dataModel?.wish?.anchors?.length ??
    dataModel?.wish?.mechanisms?.length ??
    0;
  return [
    {
      value: dash(dataModel?.wish?.verdict?.score ?? kpi.harmonyScore),
      label: 'Harmony score',
    },
    { value: birthElementLabel(dataModel), label: 'Birth element' },
    { value: dash(themes || undefined), label: 'Themes found' },
    { value: wishSupportScore(dataModel), label: 'Support score' },
  ];
}

/** Display headline: narrative tldr, else function-specific title fallback. */
export function buildResultHeadline(
  canonicalId: CanonicalFortuneFunction,
  dataModel: FortuneDataModel | null | undefined,
  fallbackTitle?: string,
): string {
  const tldr = dataModel?.narrative?.tldr?.trim();
  if (tldr) return tldr;

  if (canonicalId === 'occasion') {
    const top = dataModel?.occasion?.topPicks?.[0];
    if (top?.oneLineReason) return top.oneLineReason;
  }
  if (canonicalId === 'cycle') {
    const summary = dataModel?.luckCycle?.currentWindow?.summary?.trim();
    if (summary) return summary;
  }
  if (canonicalId === 'compatibility') {
    const summary = dataModel?.compatibility?.overview?.summary?.trim();
    if (summary) return summary;
  }
  if (canonicalId === 'wish') {
    const title = dataModel?.wish?.verdict?.title?.trim();
    if (title) return title;
    const summary = dataModel?.wish?.verdict?.summary?.trim();
    if (summary) return summary;
  }

  return fallbackTitle || 'Reading in progress…';
}

/** Model id from dataModel.meta when present (omit otherwise). */
export function readModelId(dataModel: FortuneDataModel | null | undefined): string | undefined {
  const meta = dataModel?.meta as Record<string, unknown> | undefined;
  if (!meta) return undefined;
  for (const key of ['modelId', 'model', 'narrativeModel', 'narrative_model'] as const) {
    const v = meta[key];
    if (typeof v === 'string' && v.trim()) return v.trim();
  }
  return undefined;
}

export function shortFortuneId(fortuneId: string | null | undefined): string {
  if (!fortuneId) return '--------';
  return fortuneId.replace(/-/g, '').slice(0, 8);
}
