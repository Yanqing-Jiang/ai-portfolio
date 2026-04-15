/**
 * Fortune Agent — per-purpose theme tokens.
 *
 * Each function (Compatibility / Occasion / Cycle Reading / Custom Wish) gets
 * a distinct accent color + background gradient that extends the palette
 * already used in the hub's per-section gradients. Gold `#eab308` remains the
 * shared "classical" anchor (citations, serif glyphs) on every page, so the
 * brand stays coherent while each function has its own mood.
 *
 * The gradient values here are the EXACT same pairs used in
 * `FortuneAgentHub.tsx > SECTIONS`, so clicking a tile visually continues
 * the same colored section into the input page and then into the result tabs.
 */

export type FortunePurposeId =
  | 'compatibility'
  | 'lucky-day'
  | 'luck-draw'
  | 'custom-wish';

export interface FortuneTheme {
  id: FortunePurposeId;
  label: string;             // "Compatibility"
  subtitle: string;          // used under the title on result/input pages
  glyph: string;             // CJK ideograph: 緣 / 擇 / 運 / 問
  /** Background gradient [top, bottom] — matches the hub SECTIONS entry. */
  gradient: [string, string];
  /** Primary accent (tab underline, buttons, chips, score rings). */
  accent: string;
  /** Soft border + hover bg — use with rgba. */
  accentSoft: string;
  /** Outer glow color for cards / buttons. */
  accentGlow: string;
  /** Very-low-opacity wash for card backgrounds under this theme. */
  accentWash: string;
}

export const FORTUNE_THEMES: Record<FortunePurposeId, FortuneTheme> = {
  compatibility: {
    id: 'compatibility',
    label: 'Compatibility',
    subtitle: '兩命 · Two Charts',
    glyph: '緣',
    gradient: ['#1a0a10', '#3a0f14'],
    accent: '#f43f5e',                       // rose 500 — intimacy, pull
    accentSoft: 'rgba(244, 63, 94, 0.28)',
    accentGlow: 'rgba(244, 63, 94, 0.35)',
    accentWash: 'rgba(244, 63, 94, 0.06)',
  },
  'lucky-day': {
    id: 'lucky-day',
    label: 'Occasion',
    subtitle: '擇日 · Auspicious Date',
    glyph: '擇',
    gradient: ['#1a1304', '#3a2a08'],
    accent: '#eab308',                       // gold — flagship auspicious warmth
    accentSoft: 'rgba(234, 179, 8, 0.28)',
    accentGlow: 'rgba(234, 179, 8, 0.35)',
    accentWash: 'rgba(234, 179, 8, 0.06)',
  },
  'luck-draw': {
    id: 'luck-draw',
    label: 'Cycle Reading',
    subtitle: '運勢 · Year & Month',
    glyph: '運',
    gradient: ['#200a06', '#4a1608'],
    accent: '#f97316',                       // orange 500 — ember, cyclical fire
    accentSoft: 'rgba(249, 115, 22, 0.28)',
    accentGlow: 'rgba(249, 115, 22, 0.35)',
    accentWash: 'rgba(249, 115, 22, 0.06)',
  },
  'custom-wish': {
    id: 'custom-wish',
    label: 'Custom Wish',
    subtitle: '問卜 · Your Question',
    glyph: '問',
    gradient: ['#0a0c14', '#161a2a'],
    accent: '#60a5fa',                       // blue 400 — oracle, midnight clarity
    accentSoft: 'rgba(96, 165, 250, 0.28)',
    accentGlow: 'rgba(96, 165, 250, 0.35)',
    accentWash: 'rgba(96, 165, 250, 0.06)',
  },
};

/** Gold is shared across all purposes for classical citations + brand anchor. */
export const FORTUNE_GOLD = '#eab308';
export const FORTUNE_GOLD_SOFT = 'rgba(234, 179, 8, 0.28)';
export const FORTUNE_INK = '#0c0a14';
export const FORTUNE_IVORY = '#f8fafc';
export const FORTUNE_CHINESE_FONT =
  "'Noto Serif SC', 'Songti SC', 'Songti TC', Georgia, serif";
