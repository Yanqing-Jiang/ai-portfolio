import React, { useEffect, useRef, useState } from 'react';
import Lenis from 'lenis';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import { HOMER_THEME } from './theme';
import Hero from './sections/Hero';
import Why from './sections/Why';
import Architecture from './sections/Architecture';
import TryHomer from './sections/TryHomer';
import MorningRoutineVideo from './sections/MorningRoutineVideo';
import Lessons from './sections/Lessons';
import Roadmap from './sections/Roadmap';
import CTA from './sections/CTA';

// Function: HomerLitePage — entry point for the /homer route.
// Section flow (live-product framing, not case study):
//   Hero (LIVE badge + terminal status block) →
//   Why (five Before/After couplets) →
//   Architecture (interactive — Memory schema lives inside) →
//   TryHomer (telemetry trace) → MorningRoutineVideo →
//   Lessons → Roadmap → CTA (consulting)
//
// Metrics section removed 2026-05-13 — placeholder tiles were never wired to
// real ECharts panels and the page reads cleaner without them. File kept at
// sections/Metrics.tsx in case we revive it.
//
// ProofStrip retired 2026-05-13 — its four credibility one-liners were folded
// into the Hero terminal block as `#` mono comments on each `homer --status`
// row. File kept at sections/ProofStrip.tsx for easy revert.
//
// Provides Lenis smooth-scroll over the inherited <main> scroller (mirrors
// LandingPageFlow), Helmet meta block, and a top progress bar.

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
          content="Homer is my live personal AI operating system. SQLite-backed memory, multi-CLI executors, scheduled jobs, MCP tools — running autonomously on a Mac Mini. Try it from the public console."
        />
        <meta property="og:title" content="Homer — Personal AI Operating System" />
        <meta
          property="og:description"
          content="A live personal AI OS. Multi-CLI orchestration, hybrid memory, scheduled agents. Try a few real commands from the public console."
        />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://yanqing.app/homer" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="theme-color" content={HOMER_THEME.bg} />
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
        <div
          aria-hidden
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: 'url("https://grainy-gradients.vercel.app/noise.svg")',
            opacity: 0.06,
          }}
        />

        <div className="relative z-10">
          <Hero />
          <Why />
          <Architecture />
          <TryHomer />
          <MorningRoutineVideo />
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
