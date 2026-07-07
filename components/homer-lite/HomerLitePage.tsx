import React, { useEffect, useRef, useState } from 'react';
import Lenis from 'lenis';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import { HOMER_THEME } from './theme';
import Hero from './sections/Hero';
import Why from './sections/Why';
import Architecture from './sections/Architecture';
import TryHomer from './sections/TryHomer';
import MemorySearchDemo from './sections/MemorySearchDemo';
import MemoryLifecycleDemo from './sections/MemoryLifecycleDemo';
import MorningRoutineCast from './sections/MorningRoutineCast';
import Lessons from './sections/Lessons';
import Roadmap from './sections/Roadmap';
import CTA from './sections/CTA';

// Function: HomerLitePage — entry point for the /homer route.
// Section flow (live-product framing, not case study):
//   Hero (typewriter boot sequence + fixed LIVE pill) →
//   TryHomer (telemetry trace) → MemorySearchDemo → MorningRoutineCast →
//   Architecture (interactive — Memory schema lives inside) →
//   Why (three Before/After couplets) → Lessons → Roadmap → CTA (consulting)
//
// Metrics section removed 2026-05-13 — placeholder tiles were never wired to
// real ECharts panels and the page reads cleaner without them. File kept at
// sections/Metrics.tsx in case we revive it.
//
// ProofStrip retired 2026-05-13 — its four credibility one-liners were
// expressed in the Hero terminal boot block itself (memory layer, token
// usage, scheduler, executors, voice, mcp). File kept at sections/ProofStrip.tsx
// for easy revert.
//
// MorningRoutineVideo retired 2026-07-06 — the missing WebM probe could be
// answered by the SPA fallback as 200-with-HTML, producing an empty video box
// in production. File kept at sections/MorningRoutineVideo.tsx for easy revert.
//
// Hero redesigned 2026-05-13 — replaced the static `$ homer --status` block
// with a character-by-character typewriter boot sequence (ported from
// pro-C-typewriter.html). LIVE badge moved to a fixed top-right pill.
//
// Provides Lenis smooth-scroll over the inherited <main> scroller (mirrors
// LandingPageFlow), Helmet meta block, and a top progress bar.

const HOMER_URL = 'https://yanqing.app/homer';
const HOMER_DESCRIPTION =
  'Homer is my live personal AI operating system. SQLite-backed memory, five executors, 48 scheduled jobs, MCP tools — running autonomously on a Mac Mini.';

const homerSoftwareSchema = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'Homer',
  applicationCategory: 'ProductivityApplication',
  operatingSystem: 'macOS',
  url: HOMER_URL,
  description: HOMER_DESCRIPTION,
  creator: {
    '@type': 'Person',
    name: 'Yanqing Jiang',
    url: 'https://yanqing.app',
  },
  featureList: [
    'SQLite-backed memory with FTS5 and vector retrieval',
    'Five CLI executors: claude, codex, gemini, kimi, opencode',
    '48 scheduled daily tasks',
    'Telegram and voice escalation loops',
  ],
};

const homerPersonSchema = {
  '@context': 'https://schema.org',
  '@type': 'Person',
  name: 'Yanqing Jiang',
  url: 'https://yanqing.app',
  sameAs: [
    'https://www.linkedin.com/in/yanqing-jiang/',
    'https://github.com/Yanqing-Jiang',
    'https://medium.com/@yanqing_j',
  ],
};

const homerBreadcrumbSchema = {
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: [
    {
      '@type': 'ListItem',
      position: 1,
      name: 'Home',
      item: 'https://yanqing.app/',
    },
    {
      '@type': 'ListItem',
      position: 2,
      name: 'Homer',
      item: HOMER_URL,
    },
  ],
};

const HomerLitePage: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const lenisRef = useRef<Lenis | null>(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const mainEl = document.querySelector('main');
    if (!mainEl) return;

    const lenis = new Lenis({
      wrapper: mainEl as HTMLElement,
      content: mainEl as HTMLElement,
      duration: 0.85,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      touchMultiplier: 1.5,
      infinite: false,
    });
    lenisRef.current = lenis;

    let rafId = 0;
    const raf = (time: number) => {
      lenis.raf(time);
      rafId = requestAnimationFrame(raf);
    };
    rafId = requestAnimationFrame(raf);

    const onScroll = () => {
      const max = (mainEl as HTMLElement).scrollHeight - (mainEl as HTMLElement).clientHeight;
      if (max <= 0) return;
      setProgress(Math.min(1, (mainEl as HTMLElement).scrollTop / max));
    };
    lenis.on('scroll', onScroll);
    onScroll();

    return () => {
      cancelAnimationFrame(rafId);
      lenis.destroy();
      lenisRef.current = null;
    };
  }, []);

  return (
    <>
      <Helmet>
        <title>Homer — Personal AI Operating System · Yanqing Jiang</title>
        <meta
          name="description"
          content={HOMER_DESCRIPTION}
        />
        <meta property="og:title" content="Homer — Personal AI Operating System" />
        <meta
          property="og:description"
          content="A live personal AI OS. Multi-CLI orchestration, hybrid memory, scheduled agents. Try a few real commands from the public console."
        />
        <meta property="og:type" content="website" />
        <meta property="og:url" content={HOMER_URL} />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="theme-color" content={HOMER_THEME.bg} />
        <link rel="canonical" href={HOMER_URL} />
        <script type="application/ld+json">{JSON.stringify(homerSoftwareSchema)}</script>
        <script type="application/ld+json">{JSON.stringify(homerPersonSchema)}</script>
        <script type="application/ld+json">{JSON.stringify(homerBreadcrumbSchema)}</script>
      </Helmet>

      {/* Top reading-progress bar */}
      <div
        className="fixed top-[env(safe-area-inset-top)] left-0 right-0 h-px z-[60] origin-left"
        style={{
          background: HOMER_THEME.accent,
          transform: `scaleX(${progress})`,
          transformOrigin: '0 0',
          transition: 'transform 80ms linear',
          opacity: progress > 0.005 ? 0.9 : 0,
          pointerEvents: 'none',
        }}
      />

      <div
        ref={containerRef}
        className="relative w-full overflow-x-hidden"
        style={{
          background: HOMER_THEME.bg,
          color: HOMER_THEME.text,
          minHeight: '100vh',
        }}
      >
        <div className="relative z-10">
          <Hero />
          <TryHomer />
          <MemorySearchDemo />
          <MemoryLifecycleDemo />
          <MorningRoutineCast />
          <Architecture />
          <Why />
          <Lessons />
          <Roadmap />
          <CTA />

          <footer
            className="border-t mt-12 py-12 px-4 md:px-6 text-center"
            style={{ borderColor: HOMER_THEME.divider }}
          >
            <div
              className="text-xs"
              style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
            >
              homer · live · &copy; {new Date().getFullYear()} yanqing jiang
            </div>
          </footer>
        </div>
      </div>
    </>
  );
};

export default HomerLitePage;
