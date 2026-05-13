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
//   - SectionShell title "Six subsystems, one loop." stays canonical.
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
import { Brain, Calendar, Cpu, Plug, Phone, Globe, Database, Terminal, MessageSquare, Zap, AlertCircle, RefreshCw, Shield, Mic, FileText, Smartphone, Lock } from 'lucide-react';
import { SectionShell } from '../SectionShell';
import { HOMER_THEME } from '../theme';

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

const ExecutorsViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="flex items-center gap-8">
      <motion.div animate={{ x: phase === 0 ? 0 : phase === 1 ? 10 : 20 }} className="p-4 rounded-xl border z-10" style={{ borderColor: HOMER_THEME.divider, backgroundColor: HOMER_THEME.bg }}>
        <Cpu size={32} style={{ color: HOMER_THEME.text }} />
      </motion.div>
      <div className="flex flex-col gap-4">
        <motion.div animate={{ opacity: phase === 0 ? 1 : 0.2, borderColor: phase === 0 ? HOMER_THEME.accent : HOMER_THEME.divider }} className="px-4 md:px-6 py-2 border rounded font-mono text-sm flex items-center gap-2">
          Fast <Zap size={14} style={{ color: HOMER_THEME.accent }}/>
        </motion.div>
        <motion.div animate={{ opacity: phase === 1 ? 1 : 0.2, borderColor: phase === 1 ? '#ef4444' : HOMER_THEME.divider }} className="px-4 md:px-6 py-2 border rounded font-mono text-sm flex items-center gap-2">
          Primary <AlertCircle size={14} style={{ color: '#ef4444' }}/>
        </motion.div>
        <motion.div animate={{ opacity: phase === 2 ? 1 : 0.2, borderColor: phase === 2 ? HOMER_THEME.accent : HOMER_THEME.divider }} className="px-4 md:px-6 py-2 border rounded font-mono text-sm flex items-center gap-2">
          Fallback <RefreshCw size={14} style={{ color: HOMER_THEME.accent }}/>
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

// --- SUBSYSTEM DATA ---
const SUBSYSTEMS = [
  {
    id: 'memory',
    label: 'Memory',
    icon: Brain,
    headline: 'Perfect recall.',
    viz: MemoryViz,
    me: ["Skip re-explaining the stack.", "Shared state across surfaces.", "Recall a 6-week-old decision."],
    team: ["Perfect customer-history recall.", "End re-pasting context.", "Immutable AI audit trail."],
    receipts: ['12,481 claims stored', '90 days retention']
  },
  {
    id: 'scheduler',
    label: 'Scheduler',
    icon: Calendar,
    headline: 'Works while you sleep.',
    viz: SchedulerViz,
    // FIXED: original drifted ("intelligence briefs / retry APIs / Slack triggers")
    // — restored to ground-truth phase mapping.
    me: ['3 AM memory consolidate.', 'Survives sleep / wake.', 'Loud failure → page me.'],
    team: ["Run nightly jobs without DevOps.", "Succeed or escalate to a human.", "Kill fragile single-process loops."],
    receipts: ['47 active jobs', '46K+ traced executions']
  },
  {
    id: 'executors',
    label: 'Executors',
    icon: Cpu,
    headline: 'Right model. Every time.',
    viz: ExecutorsViz,
    // FIXED: original P0/P1/P2 drifted; restored ground-truth order
    // (cycle keys / cheap-fast vs deep / reroute on hang).
    me: ['Cycle keys past quotas.', 'Cheap fast vs deep slow.', 'Reroute on provider hang.'],
    team: ["Cheapest capable model, automatic.", "No vendor lock-in.", "Survive provider outages."],
    receipts: ['6 supported engines', '99.4% success rate']
  },
  {
    id: 'mcp',
    label: 'MCP Server',
    icon: Plug,
    headline: 'One toolkit. Every agent.',
    viz: McpViz,
    // FIXED: original P1 was "Native filesystem access" (fabricated capability,
    // not in ground truth) — restored to centralized perms/logs.
    me: ['Write tool once, used everywhere.', 'Centralized perms + logs.', 'Upgrade once, every CLI gains.'],
    team: ["Secure gateway for scattered prototypes.", "Stop rewriting integrations.", "Centralized rate limit + auth."],
    receipts: ['~40 unified tools', '100% capability parity']
  },
  {
    id: 'voice',
    label: 'Voice',
    icon: Phone,
    headline: 'A phone for your agents.',
    viz: VoiceViz,
    // FIXED: original P1/P2 drifted; restored ground-truth phase mapping
    // (dictate while driving / proactive call on critical fail / spoken nuance).
    me: ['Dictate while driving.', 'Calls me on critical fail.', 'Capture nuance, no laptop.'],
    team: ["Hands-free field tech access.", "On-call calls with full context.", "Replace IVR with memory-backed agents."],
    receipts: ['380ms first audio out', 'Full-duplex barge-in']
  },
  {
    id: 'web',
    label: 'Web UI',
    icon: Globe,
    headline: 'Window into the mind.',
    viz: WebUiViz,
    // FIXED: original P2 was "Rich Markdown and PDF views" — that's P1 in
    // ground truth. Restored P0=phone watch, P1=render PDFs, P2=CLI sync.
    me: ['Watch agents from a phone.', 'Render PDFs and transcripts.', 'Same backend as the CLI.'],
    team: ["Visual prototyping, no backend build.", "Stakeholder visibility into agent decisions.", "Secure global memory dashboard."],
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
export const Architecture: React.FC = () => {
  const [activeId, setActiveId] = useState<string>(SUBSYSTEMS[0].id);
  const phase = usePhase(2000);
  const chipStripRef = useRef<HTMLDivElement>(null);
  const shouldReduceMotion = useReducedMotion();

  const activeSub = SUBSYSTEMS.find(s => s.id === activeId) || SUBSYSTEMS[0];
  const ActiveViz = activeSub.viz;
  const ActiveIcon = activeSub.icon;

  // Auto-center the active chip in the horizontal strip when activeId changes.
  // Mirrors the concept-B prototype detail (`scrollIntoView` on tap) but driven
  // by state so programmatic activations work too. inline:'center' keeps the
  // chip visually centered without disturbing vertical page scroll.
  useEffect(() => {
    const strip = chipStripRef.current;
    if (!strip) return;
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
      title="Six subsystems, one loop."
      subtitle="Each panel is a real subsystem in production. Tap a chip to see its actual telemetry."
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
          {SUBSYSTEMS.map((sub) => {
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
        <div className="md:w-2/5 md:border-r" style={{ borderColor: HOMER_THEME.divider }}>
          <ActiveViz phase={phase} />
        </div>

        <div className="md:w-3/5 p-6 md:p-8 flex flex-col gap-6">
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

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <h4
                className="font-mono text-[10px] tracking-[0.18em] uppercase mb-3 pb-2 border-b"
                style={{ color: HOMER_THEME.textMuted, borderColor: HOMER_THEME.divider }}
              >
                Built for me
              </h4>
              <ul className="space-y-2.5">
                {activeSub.me.map((b, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm transition-opacity duration-300"
                    style={{ color: HOMER_THEME.text, opacity: phase === i ? 1 : 0.45 }}
                  >
                    <span
                      className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ backgroundColor: phase === i ? HOMER_THEME.accent : HOMER_THEME.divider }}
                    />
                    {b}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4
                className="font-mono text-[10px] tracking-[0.18em] uppercase mb-3 pb-2 border-b"
                style={{ color: HOMER_THEME.textMuted, borderColor: HOMER_THEME.divider }}
              >
                Deployed for your team
              </h4>
              <ul className="space-y-2.5">
                {activeSub.team.map((b, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm transition-opacity duration-300"
                    style={{ color: HOMER_THEME.text, opacity: phase === i ? 1 : 0.45 }}
                  >
                    <span
                      className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ backgroundColor: phase === i ? HOMER_THEME.accent : HOMER_THEME.divider }}
                    />
                    {b}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div
            className="flex flex-wrap gap-2 pt-4 mt-auto border-t"
            style={{ borderColor: HOMER_THEME.divider }}
          >
            {activeSub.receipts.map((r, i) => (
              <div
                key={i}
                className="px-2.5 py-1 rounded text-[11px] font-mono whitespace-nowrap"
                style={{
                  background: HOMER_THEME.bgSoft,
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
      </motion.div>
    </SectionShell>
  );
};

export default Architecture;
