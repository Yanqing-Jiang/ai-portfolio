/**
 * Per-function result-page config keyed by canonical ids from lib/fortuneRoutes.ts.
 */
import type { CanonicalFortuneFunction } from '../../../../lib/fortuneRoutes';
import { fortuneIntakeRoute } from '../../../../lib/fortuneRoutes';
import type { FortunePurposeId } from '../../fortuneAgentTheme';
import type { FortuneFunctionId } from '../../lib/fortuneTypes';
import type { FortuneTab } from '../../FortuneAgentResultShell';

export interface FortuneResultConfig {
  canonicalId: CanonicalFortuneFunction;
  /** Theme / ThinkingPanel purpose id (legacy slug-shaped). */
  purpose: FortunePurposeId;
  /** Session / create API function id (legacy). */
  sessionFunctionId: FortuneFunctionId;
  baseRoute: string;
  eyebrow: string;
  /** Static subtitle; wish overrides via location.state.question. */
  subtitle?: string;
  tabs: FortuneTab[];
  defaultTab: string;
  loadingMessage: string;
  spinnerClass: string;
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
    tabs: [
      { id: 'Verdict', label: 'Verdict' },
      { id: 'Anchor', label: 'Anchor' },
      { id: 'Why', label: 'Why' },
      { id: 'Ask', label: 'Ask' },
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
    tabs: [
      { id: 'Now', label: 'Now' },
      { id: 'Timeline', label: 'Timeline' },
      { id: 'Why', label: 'Why' },
      { id: 'Ask', label: 'Ask' },
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
    tabs: [
      { id: 'Overview', label: 'Overview' },
      { id: 'Pillars', label: 'Pillars' },
      { id: 'Why', label: 'Why' },
      { id: 'Ask', label: 'Ask' },
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
    tabs: [
      { id: 'TopPicks', label: 'Top Picks' },
      { id: 'Calendar', label: 'Calendar' },
      { id: 'Why', label: 'Why' },
      { id: 'Ask', label: 'Ask' },
    ],
    defaultTab: 'TopPicks',
    loadingMessage: 'Finding auspicious dates...',
    spinnerClass: 'border-amber-500/30 border-t-amber-500',
  },
};
