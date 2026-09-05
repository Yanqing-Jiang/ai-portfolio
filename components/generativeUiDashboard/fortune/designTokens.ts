/**
 * Design tokens for the fortune agent result pages.
 *
 * FLOW_ACCENTS: per-function accent colors (wish=teal, compat=rose, luck=indigo, occasion=amber).
 * ELEMENT_COLORS: Five Elements palette with Tailwind classes + hex.
 * BASE_THEME: dark navy foundation shared across all functions.
 * OBSERVATORY_*: Phase 5 shared visual tokens (Observatory + trace ledger).
 *
 * Gold (#eab308) is RESERVED for classical citations — never used for buttons or accents.
 */

import type { FortuneFunctionId, ElementType } from '../lib/fortuneTypes';

// ---------------------------------------------------------------------------
// Flow accents — per fortune function
// ---------------------------------------------------------------------------

export interface FlowAccent {
  primary: string;
  light: string;
  dark: string;
  bg: string;
  border: string;
  glow: string;
}

export const FLOW_ACCENTS: Record<FortuneFunctionId, FlowAccent> = {
  wish:          { primary: '#14b8a6', light: '#5eead4', dark: '#0d9488', bg: 'rgba(20,184,166,0.08)', border: 'rgba(20,184,166,0.2)', glow: '0 0 20px rgba(20,184,166,0.3)' },
  compatibility: { primary: '#f43f5e', light: '#fb7185', dark: '#e11d48', bg: 'rgba(244,63,94,0.08)', border: 'rgba(244,63,94,0.2)', glow: '0 0 20px rgba(244,63,94,0.3)' },
  'luck-cycle':  { primary: '#6366f1', light: '#818cf8', dark: '#4f46e5', bg: 'rgba(99,102,241,0.08)', border: 'rgba(99,102,241,0.2)', glow: '0 0 20px rgba(99,102,241,0.3)' },
  'lucky-day':   { primary: '#f59e0b', light: '#fbbf24', dark: '#d97706', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)', glow: '0 0 20px rgba(245,158,11,0.3)' },
} as const;

/** Gold — RESERVED for classical book citations only. */
export const CITATION_GOLD = '#eab308';

// ---------------------------------------------------------------------------
// Five Elements colors
// ---------------------------------------------------------------------------

export interface ElementColor {
  text: string;
  bg: string;
  border: string;
  hex: string;
}

export const ELEMENT_COLORS: Record<ElementType, ElementColor> = {
  Wood:  { text: 'text-green-400',  bg: 'bg-green-500/10',  border: 'border-green-500/30',  hex: '#4ade80' },
  Fire:  { text: 'text-red-400',    bg: 'bg-red-500/10',    border: 'border-red-500/30',    hex: '#f87171' },
  Earth: { text: 'text-yellow-500', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', hex: '#eab308' },
  Metal: { text: 'text-slate-300',  bg: 'bg-slate-400/10',  border: 'border-slate-400/30',  hex: '#cbd5e1' },
  Water: { text: 'text-blue-400',   bg: 'bg-blue-500/10',   border: 'border-blue-500/30',   hex: '#60a5fa' },
} as const;

// ---------------------------------------------------------------------------
// Base theme — dark navy foundation
// ---------------------------------------------------------------------------

export const BASE_THEME = {
  bg: '#0B1120',
  surface: 'rgba(15,23,42,0.8)',
  card: 'rgba(30,41,59,0.5)',
  border: 'rgba(51,65,85,0.5)',
  text: '#f1f5f9',
  textSecondary: '#94a3b8',
  textMuted: '#64748b',
} as const;

// ---------------------------------------------------------------------------
// Glassmorphism helper (legacy surfaces still used by Why/Calendar/etc.)
// ---------------------------------------------------------------------------

export const GLASS = 'bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl';

// ---------------------------------------------------------------------------
// Observatory (Phase 5) — shared style tokens
// Define once; consume from shell / panels / hero cards. No per-function copies.
// ---------------------------------------------------------------------------

export const OBSERVATORY_SERIF =
  "'Songti SC', 'Noto Serif SC', Georgia, serif";

export const OBSERVATORY_MONO =
  "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace";

/** Parse #rgb / #rrggbb into rgba() string. */
export function accentAlpha(hex: string, alpha: number): string {
  const raw = hex.replace('#', '');
  const full =
    raw.length === 3
      ? raw
          .split('')
          .map((c) => c + c)
          .join('')
      : raw.padEnd(6, '0').slice(0, 6);
  const n = Number.parseInt(full, 16);
  if (!Number.isFinite(n)) return `rgba(212,175,55,${alpha})`;
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

export interface ObservatoryAccentStyles {
  primary: string;
  softBorder: string;
  wash: string;
  tabBg: string;
  tabBorder: string;
  focusRing: string;
  pulse: string;
  heroBorder: string;
  heroWash: string;
  score: string;
}

/** Map a FLOW_ACCENTS primary (or any hex) into Observatory surface tokens. */
export function observatoryAccent(primary: string): ObservatoryAccentStyles {
  return {
    primary,
    softBorder: accentAlpha(primary, 0.28),
    wash: accentAlpha(primary, 0.07),
    tabBg: accentAlpha(primary, 0.06),
    tabBorder: accentAlpha(primary, 0.3),
    focusRing: accentAlpha(primary, 0.45),
    pulse: primary,
    heroBorder: accentAlpha(primary, 0.25),
    heroWash: `linear-gradient(120deg, ${accentAlpha(primary, 0.08)}, ${accentAlpha(primary, 0.02)})`,
    score: primary,
  };
}

/** KPI band card — mock A `.kpi` */
export const OBS_KPI_CARD =
  'rounded-xl border border-white/[0.07] bg-white/[0.02] p-3.5 sm:p-3.5';

export const OBS_KPI_VALUE =
  'block text-[20px] sm:text-[22px] font-semibold leading-none text-[#f4e9c8]';

export const OBS_KPI_LABEL =
  'mt-2 block font-mono text-[9px] font-semibold uppercase tracking-[0.2em] text-[#7a7f88]';

/** Quiet / secondary pick card — mock A `.pick.minor` */
export const OBS_QUIET_CARD =
  'flex items-center gap-4 rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4';

/**
 * Tab base — icon-led 44px segment on mobile, mock A `.tab` pill from sm up.
 * Padding lives here so callers never have to override a conflicting utility.
 */
export const OBS_TAB =
  'relative flex min-h-11 flex-col items-center justify-center gap-1 rounded-xl border border-transparent px-1.5 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[#8a8f98] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40 sm:flex-row sm:gap-2 sm:rounded-full sm:px-4 sm:py-2.5 sm:text-[11px] sm:tracking-[0.15em]';

/** Ledger / execution-trace mono strip */
export const OBS_LEDGER =
  'rounded-xl border border-white/[0.06] bg-[#070808]/80 font-mono';

export const OBS_LEDGER_HEADER =
  'px-4 py-3 text-[9px] font-semibold uppercase tracking-[0.2em]';

export const OBS_LEDGER_ROW =
  'flex items-baseline justify-between gap-3 px-4 py-1 text-[10.5px] leading-[1.9] text-[#5c6963]';

/** Compact session-memory strip */
export const OBS_MEMORY_STRIP =
  'overflow-hidden rounded-xl border border-white/[0.06] bg-white/[0.02] font-mono';

// ---------------------------------------------------------------------------
// Score thresholds — color by score value
// ---------------------------------------------------------------------------

export function scoreColor(score: number): string {
  if (score >= 75) return 'text-green-400';
  if (score >= 50) return 'text-yellow-400';
  return 'text-red-400';
}

export function scoreBg(score: number): string {
  if (score >= 80) return 'bg-green-500/70';
  if (score >= 65) return 'bg-green-500/40';
  if (score >= 50) return 'bg-yellow-500/40';
  if (score >= 35) return 'bg-orange-500/40';
  return 'bg-red-500/40';
}
