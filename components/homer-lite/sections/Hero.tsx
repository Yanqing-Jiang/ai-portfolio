import React, { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import { HOMER_THEME } from '../theme';

// Hero — Typewriter boot sequence.
//
// Ported from ~/homer/output/gemini/homer-hero-redesign-2026-05-13/pro-C-typewriter.html.
// Each boot line types out character-by-character left→right. A single live
// block cursor (`.homer-type-cursor`) is repositioned after every typed char
// so it visually follows the typing — when one line finishes the cursor
// jumps to the start of the next; after `homer is awake.` it rests there.
//
// Implementation note: we do this imperatively with raw DOM nodes inside a
// `useEffect` rather than React state because there's a single moving DOM
// node (the cursor) tracking ~400 char-by-char updates over ~7 seconds.
// State-driven rendering would re-render the whole tree every char.
//
// Visible boot values (24.7 GB, 1.4B, 48 daily tasks, 18 tools, executors
// list) are presentational and kept static here — they describe the SYSTEM,
// not a snapshot. Only the LIVE badge's day-count is wired to metrics.json,
// since that's the one number that actually grows over time.

const DEFAULT_UPTIME_DAYS = 186;
const EXECUTORS = ['claude', 'codex', 'gemini', 'kimi', 'opencode'];

// Function: useUptimeDays — pulls uptime from /homer/metrics.json on mount.
// Returns the default if metrics.json is missing, malformed, or hasn't loaded
// yet. Intentionally separate from the typewriter effect so the boot anim
// only runs once on mount (not again when metrics arrive a few hundred ms
// later — that would restart the 7-second sequence mid-play).
const useUptimeDays = (): number => {
  const [days, setDays] = useState(DEFAULT_UPTIME_DAYS);
  useEffect(() => {
    fetch('/homer/metrics.json')
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        const d = Number(j?.hero?.uptimeDays);
        if (Number.isFinite(d) && d > 0) setDays(d);
      })
      .catch(() => {});
  }, []);
  return days;
};

interface Segment {
  t: string;
  v?: boolean; // gold (numeric value) vs muted (prose)
}
interface Line {
  ts?: string;
  main: string;
  status?: 'ok';
  detail?: Segment[];
  awake?: boolean; // final "homer is awake." line — green, with top margin
}

// Boot script. Sequence is deliberate: memory first (the most defensible
// claim), then token usage / scheduler / executors / voice / mcp, then the
// awake line in green. Dots are padding to align the `ok` column visually
// like a real systemd boot.
const LINES: Line[] = [
  { ts: '[2026-05-13 09:42:18]', main: 'homer.daemon: booting...' },
  {
    ts: '[2026-05-13 09:42:18]',
    main: 'mounting memory layer ..................',
    status: 'ok',
    detail: [{ t: ' (' }, { t: '24.7 GB', v: true }, { t: ' indexed)' }],
  },
  {
    ts: '[2026-05-13 09:42:19]',
    main: 'loading token usage ......................',
    status: 'ok',
    detail: [{ t: ' (' }, { t: '1.4B', v: true }, { t: '/month)' }],
  },
  {
    ts: '[2026-05-13 09:42:19]',
    main: 'starting scheduler .......................',
    status: 'ok',
    detail: [{ t: ' (' }, { t: '48', v: true }, { t: ' daily tasks)' }],
  },
  {
    ts: '[2026-05-13 09:42:19]',
    main: 'connecting executors .....................',
    status: 'ok',
    detail: [{ t: ` (${EXECUTORS.join(' · ')})` }],
  },
  {
    ts: '[2026-05-13 09:42:19]',
    main: 'voice channel ............................',
    status: 'ok',
  },
  {
    ts: '[2026-05-13 09:42:20]',
    main: 'mcp server bound to socket ...............',
    status: 'ok',
    detail: [{ t: ' (' }, { t: '18', v: true }, { t: ' tools active)' }],
  },
  { main: 'homer is awake.', awake: true },
];

// Type speeds. Lower = faster. Variance adds a subtle natural cadence so it
// doesn't read as a robotic per-char tick.
const BASE_DELAY = 12;
const VARIANCE = 10;
const randDelay = () => BASE_DELAY + Math.random() * VARIANCE;
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export const Hero: React.FC = () => {
  const uptimeDays = useUptimeDays();
  const shouldReduceMotion = useReducedMotion();
  const terminalRef = useRef<HTMLDivElement>(null);
  const [brandVisible, setBrandVisible] = useState(false);
  const [ctaVisible, setCtaVisible] = useState(false);

  useEffect(() => {
    const terminal = terminalRef.current;
    if (!terminal) return;

    // Reset on (re-)mount. React strict-mode double-invoke is fine: cleanup
    // sets cancelled=true and clears the DOM, second invoke starts fresh.
    terminal.innerHTML = '';
    setBrandVisible(false);
    setCtaVisible(false);

    let cancelled = false;

    // The single live cursor that travels with the typing. We re-append it
    // to its parent after each char so it ends up positioned right after
    // the most-recently-typed character.
    const cursor = document.createElement('span');
    cursor.className = 'homer-type-cursor';

    const makeSpan = (cls?: string): HTMLSpanElement => {
      const s = document.createElement('span');
      if (cls) s.className = cls;
      return s;
    };

    const typeInto = async (el: HTMLSpanElement, text: string) => {
      for (const ch of text) {
        if (cancelled) return;
        el.textContent = (el.textContent ?? '') + ch;
        if (cursor.parentNode) cursor.parentNode.appendChild(cursor);
        await sleep(randDelay());
      }
    };

    const typeBoot = async () => {
      for (const line of LINES) {
        if (cancelled) return;
        const lineEl = document.createElement('div');
        lineEl.className = 'homer-line' + (line.awake ? ' homer-awake-line' : '');
        terminal.appendChild(lineEl);
        // Park cursor at the start of this line.
        lineEl.appendChild(cursor);

        if (line.ts) {
          const tsEl = makeSpan('homer-ts');
          lineEl.insertBefore(tsEl, cursor);
          await typeInto(tsEl, line.ts + ' ');
        }

        const mainEl = makeSpan(line.awake ? 'homer-awake' : undefined);
        lineEl.insertBefore(mainEl, cursor);
        await typeInto(mainEl, line.main);

        if (line.status) {
          // System "thinks" briefly before reporting the status — this is
          // the moment that gives each `ok` weight.
          await sleep(180);
          if (cancelled) return;
          const okEl = makeSpan('homer-ok');
          lineEl.insertBefore(okEl, cursor);
          await typeInto(okEl, '  ' + line.status);
        }

        if (line.detail) {
          await sleep(80);
          for (const seg of line.detail) {
            if (cancelled) return;
            const segEl = makeSpan('homer-detail' + (seg.v ? ' homer-v' : ''));
            lineEl.insertBefore(segEl, cursor);
            await typeInto(segEl, seg.t);
          }
        }

        await sleep(130);
      }
    };

    // Reduced-motion fallback — snap the entire boot output instantly,
    // cursor rests at the end of the last line.
    const reducedFallback = () => {
      for (const line of LINES) {
        const lineEl = document.createElement('div');
        lineEl.className = 'homer-line' + (line.awake ? ' homer-awake-line' : '');
        terminal.appendChild(lineEl);

        if (line.ts) {
          const ts = makeSpan('homer-ts');
          ts.textContent = line.ts + ' ';
          lineEl.appendChild(ts);
        }
        const main = makeSpan(line.awake ? 'homer-awake' : undefined);
        main.textContent = line.main;
        lineEl.appendChild(main);
        if (line.status) {
          const ok = makeSpan('homer-ok');
          ok.textContent = '  ' + line.status;
          lineEl.appendChild(ok);
        }
        if (line.detail) {
          for (const seg of line.detail) {
            const segEl = makeSpan('homer-detail' + (seg.v ? ' homer-v' : ''));
            segEl.textContent = seg.t;
            lineEl.appendChild(segEl);
          }
        }
      }
      const last = terminal.lastChild as HTMLElement | null;
      last?.appendChild(cursor);
    };

    (async () => {
      if (shouldReduceMotion) {
        reducedFallback();
      } else {
        await typeBoot();
      }
      if (cancelled) return;
      await sleep(500);
      if (cancelled) return;
      setBrandVisible(true);
      await sleep(700);
      if (cancelled) return;
      setCtaVisible(true);
    })();

    return () => {
      cancelled = true;
    };
  }, [shouldReduceMotion]);

  return (
    <section
      className="relative min-h-[100svh] flex flex-col items-center justify-center px-4 md:px-12 py-20 md:py-24"
      style={{ background: HOMER_THEME.bg }}
    >
      {/* Scoped styles for the typewriter + LIVE-pulse keyframes. Kept inline
          (not in a global stylesheet) because this is the only place these
          rules apply and the class names are namespaced `homer-*`. */}
      <style>{`
        .homer-line {
          display: flex;
          flex-wrap: wrap;
          align-items: baseline;
          white-space: pre-wrap;
          word-break: break-word;
        }
        .homer-awake-line { margin-top: 0.6rem; }
        .homer-ts { color: ${HOMER_THEME.textMuted}; }
        .homer-ok { color: ${HOMER_THEME.accent}; font-weight: 500; }
        .homer-detail { color: ${HOMER_THEME.textMuted}; }
        .homer-detail.homer-v { color: ${HOMER_THEME.accent}; font-weight: 500; }
        .homer-awake { color: #4ade80; font-weight: 500; }
        .homer-type-cursor {
          display: inline-block;
          width: 8px;
          height: 16px;
          background: ${HOMER_THEME.accent};
          margin-left: 2px;
          transform: translateY(2px);
          animation: homer-blink-fast 0.65s step-end infinite;
        }
        @keyframes homer-blink-fast { 50% { opacity: 0; } }
        @keyframes homer-pulse-ring {
          0%   { transform: scale(1);   opacity: 0.55; }
          100% { transform: scale(2.6); opacity: 0;    }
        }
        .homer-pulse-ring {
          animation: homer-pulse-ring 2s cubic-bezier(0, 0, 0.2, 1) infinite;
        }
        @media (prefers-reduced-motion: reduce) {
          .homer-type-cursor { animation: none; }
          .homer-pulse-ring { animation: none; }
        }
      `}</style>

      {/* LIVE server-status badge — fixed to viewport top-right so it reads
          as a persistent "this OS is running right now" signal, mirroring
          the HTML mockup. */}
      <div
        className="fixed top-6 right-6 z-50 flex items-center gap-2 rounded-full border px-3 py-1.5"
        style={{
          background: 'rgba(34, 197, 94, 0.08)',
          borderColor: 'rgba(34, 197, 94, 0.3)',
        }}
      >
        <span className="relative inline-block h-2 w-2">
          <span
            className="homer-pulse-ring absolute inset-0 rounded-full"
            style={{ background: '#22c55e' }}
          />
          <span
            className="absolute inset-0 rounded-full"
            style={{ background: '#22c55e', boxShadow: '0 0 6px rgba(34, 197, 94, 0.6)' }}
          />
        </span>
        <span
          className="text-[10px] uppercase tracking-[0.18em]"
          style={{ fontFamily: HOMER_THEME.fontMono, color: '#4ade80' }}
        >
          Live
        </span>
        <span className="text-[10px] opacity-50" style={{ color: '#4ade80' }}>
          ·
        </span>
        <span
          className="text-[10px] uppercase tracking-[0.18em]"
          style={{ fontFamily: HOMER_THEME.fontMono, color: '#4ade80' }}
        >
          {uptimeDays}d
        </span>
      </div>

      {/* Terminal viewport — DOM nodes injected imperatively by the effect. */}
      <div
        ref={terminalRef}
        className="w-full max-w-[820px] flex flex-col gap-1 text-sm leading-relaxed"
        style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.text }}
      />

      {/* Brand reveal — fades in after the boot completes. Pre-rendered so
          it reserves layout space; only opacity transitions. */}
      <div
        className="mt-10 flex flex-col items-center gap-4 transition-opacity duration-1000"
        style={{ opacity: brandVisible ? 1 : 0 }}
      >
        <pre
          className="m-0 text-[10px] md:text-sm leading-[1.2]"
          style={{
            color: HOMER_THEME.accent,
            fontFamily: HOMER_THEME.fontMono,
            filter: `drop-shadow(0 0 10px ${HOMER_THEME.accentGlow})`,
          }}
        >
{`  ▒▒▒▒▒  ▒▒▒  ▒    ▒  ▒▒▒▒▒  ▒▒▒▒
  ▒   ▒ ▒   ▒ ▒▒▒▒▒▒▒ ▒      ▒   ▒
  ▒   ▒ ▒   ▒ ▒  ▒  ▒ ▒▒▒▒▒  ▒▒▒▒
  ▒   ▒ ▒   ▒ ▒  ▒  ▒ ▒      ▒  ▒
  ▒   ▒  ▒▒▒  ▒     ▒ ▒▒▒▒▒  ▒   ▒`}
        </pre>
        <h1
          className="text-4xl md:text-6xl font-normal leading-none tracking-tight"
          style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
        >
          Homer.
        </h1>
        <p
          className="text-center italic font-light text-base md:text-xl max-w-[24ch] leading-tight"
          style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.textMuted }}
        >
          An OS for one user &mdash; me.
        </p>
      </div>

      {/* Single CTA — `What's next ↓` was removed at user request. */}
      <div
        className="mt-10 flex gap-4 transition-all duration-700"
        style={{
          opacity: ctaVisible ? 1 : 0,
          transform: ctaVisible ? 'translateY(0)' : 'translateY(10px)',
        }}
      >
        <a
          href="#try"
          className="px-8 py-3 rounded-full text-base whitespace-nowrap transition-transform hover:-translate-y-0.5"
          style={{
            background: HOMER_THEME.accent,
            color: HOMER_THEME.bg,
            fontFamily: HOMER_THEME.fontSerif,
            boxShadow: `0 0 20px ${HOMER_THEME.accentSoft}`,
          }}
        >
          Try Homer →
        </a>
      </div>
    </section>
  );
};

export default Hero;
