// Variant registry for the comparison pages.
//
// Each entry holds: the slug we use in URLs, a static META block (name,
// philosophy, risk badge, distinctive animation) for the index card, and a
// React.lazy() loader so each variant page only ships its own viz code.
//
// The full Architecture component lives in
// `components/homer-lite/sections/architecture-variants/{Variant}.tsx`.

import { lazy } from 'react';
import type { ComponentType, LazyExoticComponent } from 'react';

export type VariantSlug =
  | 'safe-winner'
  | 'cinematic'
  | 'minimal-bold'
  | 'live-data'
  | 'spatial-flow';

export type RiskLevel = 'low' | 'medium' | 'high';
export type LayoutChange = 'none' | 'major' | 'total';

export interface VariantEntry {
  slug: VariantSlug;
  name: string;
  philosophy: string;
  riskLevel: RiskLevel;
  layoutChange: LayoutChange;
  distinctiveAnimation: string;
  // `any` for props because each variant declares its own (unrelated) FC
  // signature; they're all rendered with no props from ArchitectureComparePage.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  Component: LazyExoticComponent<ComponentType<any>>;
}

// Order = the order Yanqing wants to flip through (← / → cycles in this order).
export const VARIANTS: VariantEntry[] = [
  {
    slug: 'safe-winner',
    name: 'Safe Winner',
    philosophy:
      'Telegraphic 2-column layout — punchy bullets, bigger viz container, scannable left rail.',
    riskLevel: 'low',
    layoutChange: 'none',
    distinctiveAnimation:
      'Per-subsystem viz cycles 3 phases (2s loop) — DB writes / launchd run / API failover / shield + fan-out / mic + transcript / phone-to-dashboard.',
    Component: lazy(() => import('../sections/architecture-variants/SafeWinner')),
  },
  {
    slug: 'cinematic',
    name: 'Cinematic',
    philosophy:
      'Horizontal tab strip with a full-bleed hero viz; prose moved below into a 3-column grid.',
    riskLevel: 'medium',
    layoutChange: 'major',
    distinctiveAnimation:
      'Hero viz reads like a premium product feature; bullets dim/brighten in lockstep with phase 0/1/2.',
    Component: lazy(() => import('../sections/architecture-variants/Cinematic')),
  },
  {
    slug: 'minimal-bold',
    name: 'Minimal Bold',
    philosophy:
      'Geometric, type-driven viz — italic serif headline, mono rail, almost no icons.',
    riskLevel: 'medium',
    layoutChange: 'major',
    distinctiveAnimation:
      'Each viz is pure geometry — orbiting dots, rotating spokes, scaling rings — not literal telemetry.',
    Component: lazy(() => import('../sections/architecture-variants/MinimalBold')),
  },
  {
    slug: 'live-data',
    name: 'Live Data',
    philosophy:
      'The viz reads like real telemetry — SQLite rows, launchd logs, JSON-RPC frames, transcript streams.',
    riskLevel: 'low',
    layoutChange: 'none',
    distinctiveAnimation:
      'Each subsystem renders as a working terminal: INSERT rows, launchd START/FAIL, 4-CLI fan-out, 380ms first-audio counter.',
    Component: lazy(() => import('../sections/architecture-variants/LiveData')),
  },
  {
    slug: 'spatial-flow',
    name: 'Spatial Flow',
    philosophy:
      'Topology canvas — six nodes, ambient edges, click any node to trace its flow.',
    riskLevel: 'high',
    layoutChange: 'total',
    distinctiveAnimation:
      'SVG edges pulse between nodes; selecting a node dims the rest and reveals a side drawer with its 3-phase loop.',
    Component: lazy(() => import('../sections/architecture-variants/SpatialFlow')),
  },
];

export function findVariant(slug: string | undefined): VariantEntry | undefined {
  return VARIANTS.find((v) => v.slug === slug);
}
