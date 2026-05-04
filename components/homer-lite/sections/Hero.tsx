import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { HOMER_THEME } from '../theme';

// Function: Hero — Homer landing hero.
// Production-product framing (NOT a case study, NOT an essay):
//   • LIVE status badge with pulsing green dot (the system is actually running right now)
//   • Tagline emphasizing autonomous + live
//   • Terminal proof block fed by metrics.json when available
//   • Two CTAs: scroll to "Try Homer" (primary) + scroll to roadmap (secondary)

interface HomerStats {
  uptimeDays: number;
  claims: number;
  agents: number;
  executors: string[];
  scheduledRuns?: number;
}

const DEFAULT_STATS: HomerStats = {
  uptimeDays: 186,
  claims: 12481,
  agents: 8,
  executors: ['claude', 'codex', 'gemini', 'kimi', 'opencode'],
  scheduledRuns: 46307,
};

// Function: useCountUp — drives the animated counter on stat values.
const useCountUp = (target: number, durationMs = 1200) => {
  const [value, setValue] = useState(0);
  useEffect(() => {
    const startTs = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - startTs) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(eased * target));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs]);
  return value;
};

// Function: useHomerStats — pulls live aggregates from /homer/metrics.json on mount.
// Falls back to DEFAULT_STATS if the file is missing or malformed.
const useHomerStats = (): HomerStats => {
  const [stats, setStats] = useState<HomerStats>(DEFAULT_STATS);
  useEffect(() => {
    fetch('/homer/metrics.json')
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (!j?.hero) return;
        setStats({
          uptimeDays: Number(j.hero.uptimeDays) || DEFAULT_STATS.uptimeDays,
          claims: Number(j.hero.claims) || DEFAULT_STATS.claims,
          agents: Number(j.hero.executorCount) || DEFAULT_STATS.agents,
          executors: Array.isArray(j.hero.executors) ? j.hero.executors : DEFAULT_STATS.executors,
          scheduledRuns: Number(j.hero.scheduledRuns) || DEFAULT_STATS.scheduledRuns,
        });
      })
      .catch(() => {});
  }, []);
  return stats;
};

export const Hero: React.FC = () => {
  const stats = useHomerStats();
  const uptime = useCountUp(stats.uptimeDays);
  const claims = useCountUp(stats.claims);
  const scheduled = useCountUp(stats.scheduledRuns ?? 0);

  return (
    <section
      className="relative min-h-[100svh] md:min-h-[100vh] flex flex-col items-center justify-center px-4 md:px-12 py-20 md:py-24"
      style={{ background: HOMER_THEME.bg }}
    >
      {/* Soft gold ambient glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `radial-gradient(900px 600px at 50% 30%, ${HOMER_THEME.accentSoft}, transparent 70%)`,
        }}
      />

      <div className="relative max-w-3xl w-full text-center md:text-left">
        {/* LIVE status badge — pulsing green dot signals the system is actually running */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          className="inline-flex items-center gap-2.5 mb-8 px-3 py-1.5 rounded-full border max-w-full"
          style={{
            background: 'rgba(34, 197, 94, 0.08)',
            borderColor: 'rgba(34, 197, 94, 0.35)',
          }}
        >
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-green-400" />
          </span>
          <span
            className="text-[11px] tracking-[0.32em] uppercase"
            style={{ fontFamily: HOMER_THEME.fontMono, color: '#86efac' }}
          >
            Live · in production
          </span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="text-4xl sm:text-5xl md:text-7xl leading-[1.05] tracking-tight font-normal"
          style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
        >
          Homer.
          <br />
          My personal AI&nbsp;OS.
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 0.4 }}
          className="mt-6 text-lg md:text-xl max-w-2xl"
          style={{ color: HOMER_THEME.textMuted }}
        >
          Runs autonomously on a Mac Mini. Eight agents share one memory layer.
          Five CLIs orchestrated under one runtime. It picks up the phone, books
          dinner, drafts posts, monitors my portfolio — all while I&rsquo;m asleep.
        </motion.p>

        {/* Divider */}
        <motion.div
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 1, delay: 0.6 }}
          className="origin-left h-px w-32 mt-12 mb-8"
          style={{ background: HOMER_THEME.accent }}
        />

        {/* Terminal proof block — fed by /homer/metrics.json */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.7 }}
          className="rounded-md p-4 md:p-8 border"
          style={{
            background: 'rgba(20, 18, 16, 0.85)',
            borderColor: HOMER_THEME.divider,
            fontFamily: HOMER_THEME.fontMono,
          }}
        >
          <div className="text-sm md:text-base" style={{ color: HOMER_THEME.text }}>
            <div style={{ color: HOMER_THEME.accent }}>$ homer --status</div>
            <div
              className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 md:gap-x-6 gap-y-1.5 text-[13px] md:text-sm break-words [overflow-wrap:anywhere]"
              style={{ color: HOMER_THEME.textMuted }}
            >
              <span>uptime:</span>
              <span style={{ color: HOMER_THEME.text }}>{uptime}d</span>
              <span>claims:</span>
              <span style={{ color: HOMER_THEME.text }}>{claims.toLocaleString()}</span>
              <span>scheduled runs:</span>
              <span style={{ color: HOMER_THEME.text }}>{scheduled.toLocaleString()}</span>
              <span>executors:</span>
              <span style={{ color: HOMER_THEME.text }}>{stats.executors.join(' · ')}</span>
            </div>
          </div>
        </motion.div>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.7, delay: 1 }}
          className="mt-10 flex flex-col sm:flex-row gap-3 sm:gap-4"
        >
          <a
            href="#try"
            className="inline-flex min-h-[44px] items-center justify-center px-6 py-3 rounded-full text-sm font-medium transition-transform hover:-translate-y-0.5"
            style={{
              background: HOMER_THEME.accent,
              color: '#1a160f',
              fontFamily: HOMER_THEME.fontMono,
              letterSpacing: '0.05em',
            }}
          >
            Try Homer →
          </a>
          <a
            href="#roadmap"
            className="inline-flex min-h-[44px] items-center justify-center px-6 py-3 rounded-full text-sm font-medium border transition-colors hover:bg-white/5"
            style={{
              color: HOMER_THEME.text,
              borderColor: HOMER_THEME.divider,
              fontFamily: HOMER_THEME.fontMono,
              letterSpacing: '0.05em',
            }}
          >
            What&rsquo;s next ↓
          </a>
        </motion.div>
      </div>
    </section>
  );
};

export default Hero;
