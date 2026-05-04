import React from 'react';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

// Function: ProofStrip — 4 credibility one-liners under the hero.
// Plan §1.5: "runs 24/7, books dinner, etc." — signals the system is alive,
// not a slide deck. Static text in MVP; can swap to live values from metrics.json
// in Sprint 3.

const PROOF_LINES: { kpi: string; label: string }[] = [
  { kpi: '24/7', label: 'runs autonomously on a Mac Mini' },
  { kpi: '8', label: 'agents share one memory layer' },
  { kpi: '5 CLIs', label: 'orchestrated under one runtime' },
  { kpi: '6mo', label: 'continuous uptime in production' },
];

export const ProofStrip: React.FC = () => (
  <SectionShell id="proof-strip" className="!py-12 md:!py-16">
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-8 md:gap-x-12">
      {PROOF_LINES.map((p) => (
        <div key={p.kpi} className="border-l pl-4" style={{ borderColor: HOMER_THEME.accent }}>
          <div
            className="text-2xl md:text-3xl"
            style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
          >
            {p.kpi}
          </div>
          <div
            className="text-xs md:text-sm mt-2 leading-snug"
            style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
          >
            {p.label}
          </div>
        </div>
      ))}
    </div>
  </SectionShell>
);

export default ProofStrip;
