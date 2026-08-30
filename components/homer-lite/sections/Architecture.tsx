// Variant: OPERATOR CONSOLE (Pro Direction B) — mobile-first port.
// Sticky chip strip (thumb-reachable) + animated card. Replaces the previous
// 2-column "list-left / sticky-panel-right" layout, which stacked badly on
// mobile (tap → no scroll-into-view; sticky doesn't stick once columns collapse).
// Source: ~/homer/output/gemini/homer-architecture-mobile-pro-2026-05-13/concept-B.html.
//
// Carryover from the prior Safe Winner port (kept on purpose):
//   - SUBSYSTEMS data + the six Framer Motion vizzes are unchanged.
//   - Scheduler / Executors / MCP / Voice / Web UI bullets stay locked to the
//     ground-truth phase mapping (don't let copy drift re-introduce the old
//     "intelligence briefs / Slack triggers / native FS access" variants).
//   - SectionShell title "Five subsystems, one loop." (Executors tab removed 2026-08-29 per Yanqing).
//
// What changed vs. concept-B.html:
//   - Mobile-first sticky position lives inside the section (not page-global),
//     so it doesn't fight other sections on the long scroll.
//   - Bullet phase-cycling highlight from the prior implementation is preserved
//     (concept B's static bullets dropped this; it's a defining touch of the
//     live-telemetry feel).
//   - Receipts kept as mono chips; icons removed from chips (cleaner), kept
//     inside the card next to the headline for a small visual anchor.

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { Brain, Calendar, Plug, Phone, Globe, Database, Terminal, MessageSquare, Zap, AlertCircle, RefreshCw, Shield, Mic, FileText, Smartphone, Lock } from 'lucide-react';
import { SectionShell } from '../SectionShell';
import { HOMER_THEME } from '../theme';
import { PlayConsole } from '../play/PlayConsole';
import { renderMemory, renderMcp, renderScheduler, renderVoice, renderWeb } from '../play/renderers';
import type { PlayEnvelope, PlayTab } from '../play/types';

export const META = {
  slug: 'operator-console',
  name: 'Operator Console',
  philosophy:
    'Mobile-first sticky chip strip + animated card. Thumb-reachable navigation, app-like telemetry feel, identical content density on mobile and desktop.',
  riskLevel: 'low' as const,
  layoutChange: 'shell' as const,
  distinctiveAnimation:
    'Pulsing live-telemetry dot above chips + per-subsystem 3-phase viz (2s loop) — same vizzes as the prior variant.',
};

const usePhase = (intervalMs = 2000) => {
  const [phase, setPhase] = useState(0);
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    if (shouldReduceMotion) return;
    const timer = setInterval(() => {
      setPhase((p) => (p + 1) % 3);
    }, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs, shouldReduceMotion]);

  return shouldReduceMotion ? 0 : phase;
};

const VizFrame = ({ children, className = '' }: { children: React.ReactNode, className?: string }) => (
  <div
    className={`relative w-full h-48 md:h-64 rounded-lg border overflow-hidden flex items-center justify-center ${className}`}
    style={{ backgroundColor: HOMER_THEME.bgSoft, borderColor: HOMER_THEME.divider }}
  >
    {children}
  </div>
);

// --- VIZ COMPONENTS ---
const MemoryViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="flex flex-col items-center gap-6 w-full max-w-sm px-4 md:px-8">
      <div className="flex justify-between w-full text-sm font-mono" style={{ color: HOMER_THEME.textMuted }}>
        <motion.div animate={{ opacity: phase === 0 ? 1 : 0.3 }} className="flex items-center gap-2"><Terminal size={16}/> CLI</motion.div>
        <motion.div animate={{ opacity: phase === 1 ? 1 : 0.3 }} className="flex items-center gap-2"><MessageSquare size={16}/> Slack</motion.div>
        <motion.div animate={{ opacity: phase === 2 ? 1 : 0.3, color: phase === 2 ? HOMER_THEME.accent : HOMER_THEME.textMuted }} className="flex items-center gap-2"><Zap size={16}/> Search</motion.div>
      </div>
      <div className="w-full space-y-2 relative">
        <motion.div
          animate={{ backgroundColor: phase === 0 ? HOMER_THEME.accentSoft : HOMER_THEME.bg, borderColor: phase === 0 ? HOMER_THEME.accent : HOMER_THEME.divider }}
          className="h-8 border rounded flex items-center px-4 transition-colors"
        >
          <div className="h-2 w-1/3 rounded bg-current opacity-50" />
        </motion.div>
        <motion.div
          animate={{ backgroundColor: phase === 1 ? HOMER_THEME.accentSoft : HOMER_THEME.bg, borderColor: phase === 1 ? HOMER_THEME.accent : HOMER_THEME.divider }}
          className="h-8 border rounded flex items-center px-4 transition-colors"
        >
          <div className="h-2 w-1/2 rounded bg-current opacity-50" />
        </motion.div>
        <motion.div
          animate={{
            backgroundColor: phase === 2 ? HOMER_THEME.accentSoft : HOMER_THEME.bg,
            borderColor: phase === 2 ? HOMER_THEME.accent : HOMER_THEME.divider,
            scale: phase === 2 ? 1.05 : 1
          }}
          className="h-8 border rounded flex items-center px-4 transition-all z-10"
        >
          <div className="h-2 w-2/3 rounded bg-current opacity-50" />
          {phase === 2 && <motion.div layoutId="beam-safe" className="absolute -left-4 w-2 h-8 rounded" style={{ backgroundColor: HOMER_THEME.accent }} />}
        </motion.div>
      </div>
    </div>
  </VizFrame>
);

const SchedulerViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="flex flex-col items-center gap-8">
      <div className="text-4xl font-mono tracking-widest" style={{ color: phase === 2 ? '#ef4444' : HOMER_THEME.text }}>
        {phase === 0 ? "03:00:00" : phase === 1 ? "ZZZ..." : "ERR:500"}
      </div>
      <div className="flex gap-4">
        <motion.div animate={{ scale: phase === 0 ? 1.2 : 1, opacity: phase === 0 ? 1 : 0.4 }} className="p-3 rounded-full border" style={{ borderColor: HOMER_THEME.divider, backgroundColor: HOMER_THEME.bg }}>
          <RefreshCw size={24} style={{ color: HOMER_THEME.accent }} />
        </motion.div>
        <motion.div animate={{ scale: phase === 1 ? 1.2 : 1, opacity: phase === 1 ? 1 : 0.4 }} className="p-3 rounded-full border" style={{ borderColor: HOMER_THEME.divider, backgroundColor: HOMER_THEME.bg }}>
          <Database size={24} style={{ color: HOMER_THEME.textMuted }} />
        </motion.div>
        <motion.div animate={{ scale: phase === 2 ? 1.2 : 1, opacity: phase === 2 ? 1 : 0.4 }} className="p-3 rounded-full border" style={{ borderColor: phase === 2 ? '#ef4444' : HOMER_THEME.divider, backgroundColor: HOMER_THEME.bg }}>
          <AlertCircle size={24} style={{ color: phase === 2 ? '#ef4444' : HOMER_THEME.textMuted }} />
        </motion.div>
      </div>
    </div>
  </VizFrame>
);

const McpViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="relative flex items-center justify-center w-full h-full">
      <motion.div className="absolute z-30 p-4 rounded-full border bg-opacity-90" style={{ borderColor: HOMER_THEME.divider, backgroundColor: HOMER_THEME.bg }}>
        <Plug size={32} style={{ color: phase === 2 ? HOMER_THEME.accent : HOMER_THEME.text }} />
      </motion.div>
      <div className="absolute flex w-48 justify-between z-10">
        <motion.div animate={{ scale: phase === 0 ? 1 : 0.8, opacity: phase === 0 ? 1 : 0.3 }}><Terminal size={24}/></motion.div>
        <motion.div animate={{ scale: phase === 0 ? 1 : 0.8, opacity: phase === 0 ? 1 : 0.3 }}><MessageSquare size={24}/></motion.div>
      </div>
      <AnimatePresence>
        {phase === 1 && (
          <motion.div initial={{ opacity: 0, scale: 0 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="absolute z-40">
            <Shield size={64} style={{ color: '#ef4444' }} strokeWidth={1} />
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {phase === 2 && (
          <motion.div initial={{ scale: 0.5, opacity: 1 }} animate={{ scale: 3, opacity: 0 }} transition={{ duration: 1 }} className="absolute rounded-full border-2 z-20" style={{ borderColor: HOMER_THEME.accent, width: 64, height: 64 }} />
        )}
      </AnimatePresence>
    </div>
  </VizFrame>
);

const VoiceViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="flex flex-col items-center gap-6">
      <motion.div animate={{ scale: phase === 0 ? 1.2 : 1, color: phase === 0 ? HOMER_THEME.accent : HOMER_THEME.text }} className="p-4 rounded-full border" style={{ borderColor: HOMER_THEME.divider, backgroundColor: HOMER_THEME.bg }}>
        <Mic size={32} />
      </motion.div>
      <div className="flex gap-2 h-8 items-end">
        {[...Array(5)].map((_, i) => (
          <motion.div key={i} animate={{ height: phase === 1 ? Math.random() * 24 + 8 : 4 }} className="w-2 rounded-t transition-all" style={{ backgroundColor: HOMER_THEME.accent }} />
        ))}
      </div>
      <motion.div animate={{ opacity: phase === 2 ? 1 : 0, y: phase === 2 ? 0 : 10 }} className="px-4 py-2 border rounded font-mono text-xs flex items-center gap-2" style={{ borderColor: HOMER_THEME.accent, backgroundColor: HOMER_THEME.accentSoft, color: HOMER_THEME.accent }}>
        <FileText size={14}/> Extracted Data
      </motion.div>
    </div>
  </VizFrame>
);

const WebUiViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="flex items-center gap-4 md:gap-8 w-full max-w-sm px-4 md:px-8">
      <motion.div animate={{ opacity: phase === 0 ? 1 : 0.4 }} className="flex flex-col items-center gap-2">
        <Smartphone size={24} style={{ color: HOMER_THEME.textMuted }} />
        <div className="w-12 h-2 rounded bg-current opacity-20" />
      </motion.div>
      <div className="flex-1 flex flex-col items-center relative">
        <div className="w-full h-px border-t border-dashed" style={{ borderColor: HOMER_THEME.divider }} />
        <motion.div animate={{ x: phase === 2 ? '100%' : '-100%', opacity: phase === 2 ? 1 : 0 }} className="absolute -top-3 p-1 rounded-full bg-black border" style={{ borderColor: HOMER_THEME.accent }}>
          <Lock size={14} style={{ color: HOMER_THEME.accent }} />
        </motion.div>
        {phase === 1 && (
           <motion.div className="absolute -top-4 px-2 py-1 rounded text-xs font-mono" style={{ backgroundColor: HOMER_THEME.accentSoft, color: HOMER_THEME.accent, borderColor: HOMER_THEME.accent, borderWidth: 1 }}>
             JSON
           </motion.div>
        )}
      </div>
      <motion.div animate={{ opacity: phase === 2 ? 1 : 0.4, scale: phase === 2 ? 1.05 : 1 }} className="flex flex-col gap-2 p-3 border rounded shadow-lg" style={{ borderColor: HOMER_THEME.divider, backgroundColor: HOMER_THEME.bg }}>
        <div className="w-16 h-2 rounded" style={{ backgroundColor: HOMER_THEME.accent }} />
        <div className="w-24 h-2 rounded bg-current opacity-20" />
        <div className="w-20 h-2 rounded bg-current opacity-20" />
      </motion.div>
    </div>
  </VizFrame>
);

// --- PLAY CONFIG (2026-08-29) ---
// Each live subsystem embeds a PlayConsole wired to POST /api/homer/play.
// Phase 1 = memory / scheduler / web. Chips for subsystems without a `play`
// entry are hidden until their phase ships (Yanqing: "hide those chips until
// live") — the headline stays; the subtitle says how many
// are live.
//
// The old "Built for me / Deployed for your team" bullets were removed — they
// didn't explain anything; the console does the explaining now.
interface PlayConfig {
  label: string;
  placeholder: string;
  suggestions: readonly string[];
  route: (message: string) => { action: string; input?: Record<string, unknown> };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  render: (env: PlayEnvelope<any>) => React.ReactNode;
  maxLength?: number;
  /** Voice only: static pre-recorded lines the visitor can play without spending a try. */
  recordingsManifest?: string;
}

// Memory: a statement (past tense, "prefers", "decided", "moved", …) goes to
// the extractor; anything else is a search. Visitors can force either with a
// leading "search:" / "remember:".
const looksLikeStatement = (m: string) =>
  /\b(moved|prefers?|decided|switched|cancell?ed|will|now|instead|no longer|from now on|changed)\b/i.test(m) ||
  /^[A-Z][^?]*\.$/.test(m.trim());

const PLAY: Partial<Record<PlayTab, PlayConfig>> = {
  memory: {
    label: 'search it, or tell it something and watch the extractor',
    placeholder: 'ask about Homer, or tell it something new…',
    suggestions: [
      'why sqlite instead of a vector db',
      'what happens when two memories conflict',
      'Yanqing moved the weekly review to Friday mornings.',
    ],
    route: (m) => {
      const lower = m.toLowerCase();
      if (lower.startsWith('search:')) return { action: 'search', input: { limit: 4 } };
      if (lower.startsWith('remember:')) return { action: 'extract_dry_run', input: { target: 'architecture' } };
      return looksLikeStatement(m)
        ? { action: 'extract_dry_run', input: { target: 'architecture' } }
        : { action: 'search', input: { limit: 4 } };
    },
    render: renderMemory,
  },
  scheduler: {
    label: 'ask about the job table',
    placeholder: 'e.g. what failed this week? what runs next?',
    suggestions: ['what runs in the next hour', 'anything failed this week?', 'how often does memory reindex run'],
    route: () => ({ action: 'query', input: { max_jobs: 8, max_runs_per_job: 3 } }),
    render: renderScheduler,
  },
  web: {
    label: 'ask what Homer has been doing',
    placeholder: 'what has Homer been doing today?',
    suggestions: ['what has Homer been doing today?', 'how busy was the last 7 days', 'which model did most of the work'],
    route: (m) => ({
      action: 'activity',
      input: { window: /7 ?d|week/i.test(m) ? '7d' : /hour|1h|last 60/i.test(m) ? '1h' : '24h' },
    }),
    render: renderWeb,
  },
  mcp: {
    label: 'list the public tools, then call one',
    placeholder: '/tools   or   /call memory_search {"query":"conflict"}   or just type a question',
    suggestions: ['/tools', '/call memory_search {"query":"memory conflict"}', '/call preference_query {"topic":"sqlite"}', '/call todo_list'],
    route: (m) => {
      const t = m.trim();
      if (/^\/tools\b/i.test(t)) return { action: 'list_tools', input: {} };
      const call = t.match(/^\/call\s+([a-z_]+)\s*(\{[\s\S]*\})?\s*$/i);
      if (call) {
        let args: Record<string, unknown> = {};
        try {
          args = call[2] ? (JSON.parse(call[2]) as Record<string, unknown>) : {};
        } catch {
          args = {};
        }
        return { action: 'call_tool', input: { tool: call[1].toLowerCase(), arguments: args } };
      }
      // Plain text → memory_search, the tool a real agent would reach for first.
      return { action: 'call_tool', input: { tool: 'memory_search', arguments: { query: t, limit: 3 } } };
    },
    render: renderMcp,
  },
  voice: {
    label: 'type a line and Homer says it in the Goggins voice (80 chars max)',
    placeholder: 'something short for Homer to say…',
    suggestions: ['Stay hard. Homer never sleeps.', 'Three jobs failed overnight. Fix them.'],
    route: () => ({ action: 'synthesize', input: { format: 'mp3' } }),
    render: renderVoice,
    maxLength: 80,
    recordingsManifest: '/homer/voice/manifest.json',
  },
};

// --- SUBSYSTEM DATA ---
const SUBSYSTEMS = [
  {
    id: 'memory',
    label: 'Memory',
    icon: Brain,
    headline: 'Perfect recall.',
    viz: MemoryViz,
    receipts: ['12,481 claims stored', '90 days retention']
  },
  {
    id: 'scheduler',
    label: 'Scheduler',
    icon: Calendar,
    headline: 'Works while you sleep.',
    viz: SchedulerViz,
    receipts: ['48 daily tasks', '46K+ traced executions']
  },
  {
    id: 'mcp',
    label: 'MCP Server',
    icon: Plug,
    headline: 'One toolkit. Every agent.',
    viz: McpViz,
    receipts: ['~40 unified tools', '100% capability parity']
  },
  {
    id: 'voice',
    label: 'Voice',
    icon: Phone,
    headline: 'A phone for your agents.',
    viz: VoiceViz,
    receipts: ['380ms first audio out', 'Full-duplex barge-in']
  },
  {
    id: 'web',
    label: 'Web UI',
    icon: Globe,
    headline: 'Window into the mind.',
    viz: WebUiViz,
    receipts: ['JWT authenticated', 'Cloudflare tunneled']
  }
] as const;

// --- MAIN COMPONENT ---
// Layout note: we deliberately do NOT wrap the card in <AnimatePresence mode="wait">.
// usePhase re-renders this tree every 2s; a wait-for-exit cycle on the keyed
// child gets interrupted on each tick and the new card never mounts — leaving
// the panel stuck on whatever was active first. Plain key-based remount on
// <motion.div> is enough: React unmounts the old, mounts the new, and
// `initial → animate` plays the fade-in. (Carried over from the prior variant
// — re-introducing AnimatePresence here will reproduce the freeze bug.)
const LIVE_SUBSYSTEMS = SUBSYSTEMS.filter((s) => PLAY[s.id as PlayTab]);

export const Architecture: React.FC = () => {
  const [activeId, setActiveId] = useState<string>(LIVE_SUBSYSTEMS[0].id);
  const phase = usePhase(2000);
  const chipStripRef = useRef<HTMLDivElement>(null);
  const shouldReduceMotion = useReducedMotion();

  const activeSub = LIVE_SUBSYSTEMS.find((s) => s.id === activeId) || LIVE_SUBSYSTEMS[0];
  const play = PLAY[activeSub.id as PlayTab]!;
  const ActiveViz = activeSub.viz;
  const ActiveIcon = activeSub.icon;

  // Auto-center the active chip in the horizontal strip when activeId changes.
  // Mirrors the concept-B prototype detail (`scrollIntoView` on tap) but driven
  // by state so programmatic activations work too. inline:'center' keeps the
  // chip visually centered horizontally.
  //
  // Two guards added 2026-05-14:
  //   1. Skip the first run. On mount, scrollIntoView({block:'nearest'}) was
  //      bringing the (below-the-fold) chip strip into the viewport — yanking
  //      the page past the Hero. We only want this to fire on real user-driven
  //      activeId changes.
  //   2. Skip when the strip is not currently visible in the viewport.
  //      Prevents future programmatic activations (e.g. deep links) from
  //      forcing a vertical scroll when the user is reading another section.
  //      Horizontal scroll-into-view inside the strip is still safe because
  //      we scroll the chip's nearest scrollable ancestor (the strip itself),
  //      not the page — but only when the strip is on screen.
  const didMountRef = useRef(false);
  useEffect(() => {
    if (!didMountRef.current) {
      didMountRef.current = true;
      return;
    }
    const strip = chipStripRef.current;
    if (!strip) return;
    const stripRect = strip.getBoundingClientRect();
    const stripOnScreen =
      stripRect.bottom > 0 && stripRect.top < window.innerHeight;
    if (!stripOnScreen) return;
    const el = strip.querySelector(`[data-chip-id="${activeId}"]`) as HTMLElement | null;
    el?.scrollIntoView({
      behavior: shouldReduceMotion ? 'auto' : 'smooth',
      block: 'nearest',
      inline: 'center',
    });
  }, [activeId, shouldReduceMotion]);

  return (
    <SectionShell
      id="architecture"
      eyebrow="architecture"
      title="Five subsystems, one loop."
      subtitle={`You can try it out too. Every tab below is a real subsystem in production — tap a chip, then type in the box.${LIVE_SUBSYSTEMS.length < SUBSYSTEMS.length ? ` ${LIVE_SUBSYSTEMS.length} of ${SUBSYSTEMS.length} are live; the rest come online as their sandboxes ship.` : }`}
    >
      {/* Sticky chip strip — thumb-reachable on mobile, horizontal on desktop.
          Sticks within the section (not page-global) so the long scroll past
          this section behaves normally. The `top` offset clears the 1px reading
          progress bar in HomerLitePage. */}
      <div
        className="sticky top-2 z-20 -mx-4 md:-mx-12 px-4 md:px-12 pt-3 pb-3 mb-8 backdrop-blur-md border-b"
        style={{
          background: 'rgba(11, 10, 8, 0.82)',
          borderColor: HOMER_THEME.divider,
        }}
      >
        <div className="flex items-center gap-2 mb-3">
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{
              background: HOMER_THEME.accent,
              animation: shouldReduceMotion ? 'none' : 'homer-pulse 1.6s ease-in-out infinite',
              boxShadow: `0 0 8px ${HOMER_THEME.accentGlow}`,
            }}
          />
          <span
            className="text-[10px] tracking-[0.32em] uppercase"
            style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
          >
            live telemetry / architecture
          </span>
        </div>

        <div
          ref={chipStripRef}
          className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
          // Inline keyframes for the pulse — keeps this section self-contained
          // without touching globals.css (which is governed by the Tailwind
          // build). One <style> tag inside the section is cheaper than a new
          // global rule for a single animation used only here.
        >
          <style>{`@keyframes homer-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
          {LIVE_SUBSYSTEMS.map((sub) => {
            const isActive = sub.id === activeId;
            return (
              <button
                key={sub.id}
                data-chip-id={sub.id}
                onClick={() => setActiveId(sub.id)}
                className="flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 border whitespace-nowrap"
                style={{
                  background: isActive ? HOMER_THEME.accentSoft : HOMER_THEME.bgSoft,
                  color: isActive ? HOMER_THEME.accent : HOMER_THEME.textMuted,
                  borderColor: isActive ? HOMER_THEME.accent : HOMER_THEME.divider,
                  fontFamily: HOMER_THEME.fontMono,
                  fontSize: '0.78rem',
                  letterSpacing: '0.02em',
                }}
              >
                {sub.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Card — viz on top (mobile), viz-left/content-right (md+). Re-mounts on
          activeId change to play the fade-in via key + initial/animate. */}
      <motion.div
        key={activeSub.id}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="rounded-2xl border overflow-hidden flex flex-col md:flex-row"
        style={{ background: HOMER_THEME.bgSoft, borderColor: HOMER_THEME.divider }}
      >
        {/* Left: identity + viz + receipts. Right: the console. */}
        <div className="md:w-[38%] md:border-r p-6 md:p-7 flex flex-col gap-4" style={{ borderColor: HOMER_THEME.divider }}>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div
                className="p-2 rounded-lg"
                style={{ background: HOMER_THEME.accentSoft, color: HOMER_THEME.accent }}
              >
                <ActiveIcon size={18} />
              </div>
              <h3
                className="text-2xl md:text-3xl"
                style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
              >
                {activeSub.label}
              </h3>
            </div>
            <p
              className="text-lg italic mt-1 ml-12"
              style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.accent }}
            >
              {activeSub.headline}
            </p>
          </div>

          <ActiveViz phase={phase} />

          <div className="flex flex-wrap gap-2 mt-auto">
            {activeSub.receipts.map((r, i) => (
              <div
                key={i}
                className="px-2.5 py-1 rounded text-[11px] whitespace-nowrap"
                style={{
                  background: HOMER_THEME.bg,
                  color: HOMER_THEME.accent,
                  border: `1px solid ${HOMER_THEME.accentSoft}`,
                  fontFamily: HOMER_THEME.fontMono,
                }}
              >
                {r}
              </div>
            ))}
          </div>
        </div>

        <div
          className="md:w-[62%] p-6 md:p-7"
          style={{ background: 'linear-gradient(180deg, rgba(212,160,86,0.05), transparent 40%)' }}
        >
          <PlayConsole
            key={activeSub.id}
            tab={activeSub.id as PlayTab}
            label={play.label}
            placeholder={play.placeholder}
            suggestions={play.suggestions}
            route={play.route}
            render={play.render}
            maxLength={play.maxLength}
            recordingsManifest={play.recordingsManifest}
          />
        </div>
      </motion.div>
    </SectionShell>
  );
};

export default Architecture;
