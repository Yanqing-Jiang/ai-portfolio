// Index page for /homer/architecture — lists all 5 variants as cards.
//
// Each card: name, philosophy, risk badge (green/amber/red), layout-change
// badge, distinctive animation note, "Open →" link to the variant page.
// Title uses HOMER_THEME.fontSerif and the page sits on HOMER_THEME.bg so it
// blends visually with the rest of /homer.

import React from 'react';
import { Link } from 'react-router-dom';
import { HOMER_THEME } from '../theme';
import { VARIANTS, type RiskLevel, type LayoutChange } from './variants';

const RISK_COLORS: Record<RiskLevel, { bg: string; fg: string; label: string }> = {
  low: { bg: 'rgba(34, 197, 94, 0.12)', fg: '#22c55e', label: 'risk: low' },
  medium: { bg: 'rgba(212, 160, 86, 0.18)', fg: HOMER_THEME.accent, label: 'risk: medium' },
  high: { bg: 'rgba(239, 68, 68, 0.14)', fg: '#ef4444', label: 'risk: high' },
};

const LAYOUT_LABELS: Record<LayoutChange, string> = {
  none: 'layout: same',
  major: 'layout: major',
  total: 'layout: total',
};

const ArchitectureCompareIndex: React.FC = () => {
  return (
    <div
      className="min-h-screen w-full"
      style={{ backgroundColor: HOMER_THEME.bg, color: HOMER_THEME.text }}
    >
      <div className="max-w-5xl mx-auto px-6 md:px-12 py-20 md:py-28">
        <div
          className="text-[11px] tracking-[0.32em] uppercase mb-5"
          style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
        >
          architecture · redesign comparison
        </div>
        <h1
          className="text-3xl md:text-5xl leading-[1.1] tracking-tight font-medium"
          style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
        >
          Architecture redesign — 5 variants
        </h1>
        <p
          className="mt-5 max-w-3xl text-base md:text-lg leading-relaxed"
          style={{ color: HOMER_THEME.textMuted }}
        >
          Five takes on the Architecture section. Same six subsystems, same
          locked receipts; different layouts and animation metaphors. Open
          each, then pick the winner.
        </p>

        <div className="mt-12 grid grid-cols-1 md:grid-cols-2 gap-5">
          {VARIANTS.map((v, i) => {
            const risk = RISK_COLORS[v.riskLevel];
            return (
              <Link
                key={v.slug}
                to={`/homer/architecture/${v.slug}`}
                className="group block rounded-xl border p-6 transition-all hover:-translate-y-0.5"
                style={{
                  backgroundColor: HOMER_THEME.bgSoft,
                  borderColor: HOMER_THEME.divider,
                }}
              >
                <div className="flex items-center justify-between gap-4 mb-4">
                  <span
                    className="text-[10px] tracking-[0.32em] uppercase"
                    style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
                  >
                    variant {String(i + 1).padStart(2, '0')}
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className="px-2 py-0.5 rounded-full text-[10px] tracking-widest uppercase"
                      style={{
                        fontFamily: HOMER_THEME.fontMono,
                        backgroundColor: risk.bg,
                        color: risk.fg,
                      }}
                    >
                      {risk.label}
                    </span>
                    <span
                      className="px-2 py-0.5 rounded-full text-[10px] tracking-widest uppercase border"
                      style={{
                        fontFamily: HOMER_THEME.fontMono,
                        borderColor: HOMER_THEME.divider,
                        color: HOMER_THEME.textMuted,
                      }}
                    >
                      {LAYOUT_LABELS[v.layoutChange]}
                    </span>
                  </div>
                </div>

                <h2
                  className="text-2xl md:text-3xl leading-tight"
                  style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
                >
                  {v.name}
                </h2>
                <p
                  className="mt-3 text-sm leading-relaxed"
                  style={{ color: HOMER_THEME.textMuted }}
                >
                  {v.philosophy}
                </p>

                <div
                  className="mt-4 pt-4 border-t text-xs leading-relaxed"
                  style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted }}
                >
                  <span
                    className="block text-[10px] tracking-[0.24em] uppercase mb-1"
                    style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
                  >
                    distinctive animation
                  </span>
                  {v.distinctiveAnimation}
                </div>

                <div
                  className="mt-5 inline-flex items-center gap-2 text-xs tracking-[0.24em] uppercase transition-colors"
                  style={{
                    fontFamily: HOMER_THEME.fontMono,
                    color: HOMER_THEME.accent,
                  }}
                >
                  open
                  <span aria-hidden className="transition-transform group-hover:translate-x-1">→</span>
                </div>
              </Link>
            );
          })}
        </div>

        <div className="mt-16 text-xs" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>
          <Link
            to="/homer"
            className="hover:underline"
            style={{ color: HOMER_THEME.accent }}
          >
            ← back to /homer
          </Link>
        </div>
      </div>
    </div>
  );
};

export default ArchitectureCompareIndex;
