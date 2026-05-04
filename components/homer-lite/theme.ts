// Homer Lite — shared theme tokens
//
// Locked decisions (per ~/homer/output/claude/homer-lite-buildout-plan-2026-05-02.md):
//   - Accent: warm gold (#d4a056) to echo Homer's classical/editorial theme
//   - Headline: Fraunces (editorial serif)
//   - Mono / terminal proof: JetBrains Mono
//
// Used by every section under components/homer-lite/sections/* so the page reads
// as a coherent "Director-voice" essay rather than a generic project page.

export const HOMER_THEME = {
  accent: '#d4a056',
  accentSoft: 'rgba(212, 160, 86, 0.18)',
  accentGlow: 'rgba(212, 160, 86, 0.35)',
  bg: '#0b0a08',
  bgSoft: '#141210',
  text: '#e8e4dc',
  textMuted: '#9a9489',
  divider: 'rgba(232, 228, 220, 0.08)',
  // Inline font-family strings — kept here so sections don't need a global Tailwind extend.
  fontSerif: '"Fraunces", "Source Serif Pro", Georgia, serif',
  fontMono: '"JetBrains Mono", "Geist Mono", ui-monospace, SFMono-Regular, monospace',
} as const;

export type HomerTheme = typeof HOMER_THEME;
