/**
 * Design tokens for the fortune agent result pages.
 *
 * FLOW_ACCENTS: per-function accent colors (wish=teal, compat=rose, luck=indigo, occasion=amber).
 * ELEMENT_COLORS: Five Elements palette with Tailwind classes + hex.
 * BASE_THEME: dark navy foundation shared across all functions.
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
// Glassmorphism helper
// ---------------------------------------------------------------------------

export const GLASS = 'bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl';

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
