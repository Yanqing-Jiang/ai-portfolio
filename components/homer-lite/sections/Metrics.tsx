import React from 'react';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

// Function: Metrics — Plan §6.0.
// 4 ECharts panels driven by /homer/metrics.json (anonymized aggregates exported
// nightly by ~/homer/scripts/export-homer-lite-metrics.ts).
//
// Sprint 1 ships a lightweight tile placeholder so the section reserves space
// in the layout. Sprint 3 swaps each tile for a LazyECharts panel matching the
// pattern from components/generativeUiDashboard. Keeping this stub light means
// no ECharts cost on the homepage until the panels are real.

const TILES = [
  { kpi: 'Claims', subtitle: 'over time', range: '186d', value: '12.4k' },
  { kpi: 'Runs by executor', subtitle: 'last 30d', range: '~2.1k', value: '5 CLIs' },
  { kpi: 'Reliability', subtitle: 'success rate by job', range: '24/7', value: '98.2%' },
  { kpi: 'Cost', subtitle: 'inference + infra', range: 'monthly', value: '$42' },
];

export const Metrics: React.FC = () => (
  <SectionShell
    id="metrics"
    eyebrow="Metrics"
    title="What the production system actually does."
    subtitle="Aggregated nightly from homer.db. Tier 1 / Tier 2 are anonymized — counts and timestamps only, no claim text."
  >
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {TILES.map((t) => (
        <div
          key={t.kpi}
          className="p-6 rounded-md border"
          style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bgSoft }}
        >
          <div className="flex items-baseline justify-between">
            <div
              className="text-xs tracking-[0.24em] uppercase"
              style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
            >
              {t.kpi}
            </div>
            <div
              className="text-[11px]"
              style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
            >
              {t.range}
            </div>
          </div>
          <div
            className="mt-4 text-3xl md:text-4xl"
            style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
          >
            {t.value}
          </div>
          <div
            className="mt-1 text-xs"
            style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
          >
            {t.subtitle} · [echarts panel lands in Sprint 3]
          </div>
        </div>
      ))}
    </div>
  </SectionShell>
);

export default Metrics;
