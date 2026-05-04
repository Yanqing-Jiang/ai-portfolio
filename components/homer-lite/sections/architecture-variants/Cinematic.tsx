// Variant: CINEMATIC TAB CANVAS (Pro Direction B).
// Horizontal tab strip + full-width hero visualization + 3-column prose grid below.
// Source: ~/homer/output/gemini/architecture-redesign-pro-B-2026-05-03-1700.md.
//
// Fidelity fixes vs. raw extract:
//   - MCP `title: 'MCP'` → `title: 'MCP Server'` (label is locked).
//   - Web `title: 'Web'` → `title: 'Web UI'` (label is locked).
//   - Scheduler "built" P0/P1/P2 rewritten to ground-truth phase order
//     (3 AM consolidate / sleep-wake survival / loud failure paging).
//   - Executors "built" P0/P1/P2 reordered to ground-truth phase order
//     (cycle keys / cheap-fast vs deep / reroute on hang).
//   - Voice "built" P0/P1/P2 fixed (drive dictation / proactive call / capture
//     spoken nuance).
//   - MCP "built" P2 fixed: from "Total capability parity" (which is a
//     receipt) to "Upgrade once, every CLI gains" (matches phase 2 of
//     ground truth).
//   - Memory P2 bullet expanded from "Recall a 6-week decision" → "Recall a
//     6-week-old decision" for parallel structure.
//   - SectionShell now passes eyebrow/title/subtitle so the variant page is
//     recognizable.

import { useState, useEffect } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  Brain, Calendar, Cpu, Plug, Phone, Globe,
  CheckCircle2, AlertCircle, Terminal, FileCode, Zap, Network
} from 'lucide-react';
import { SectionShell } from '../../SectionShell';
import { HOMER_THEME } from '../../theme';

export const META = {
  slug: 'cinematic',
  name: 'Cinematic',
  philosophy:
    'Horizontal tab strip with a full-bleed hero viz; prose moved below into a 3-column grid.',
  riskLevel: 'medium' as const,
  layoutChange: 'major' as const,
  distinctiveAnimation:
    'Hero viz reads like a premium product feature; bullets dim/brighten in lockstep with phase 0/1/2.',
};

export function usePhase() {
  const [phase, setPhase] = useState(0);
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    if (prefersReducedMotion) return;
    const interval = setInterval(() => {
      setPhase((p) => (p + 1) % 3);
    }, 4000);
    return () => clearInterval(interval);
  }, [prefersReducedMotion]);

  return phase;
}

const MemoryViz = ({ phase }: { phase: number }) => (
  <div className="w-full h-full relative flex items-center justify-center overflow-hidden">
    <div className="absolute inset-0 grid grid-cols-8 md:grid-cols-12 grid-rows-4 md:grid-rows-6 gap-4 p-8 opacity-20">
      {Array.from({ length: 72 }).map((_, i) => (
        <motion.div
          key={i}
          className="w-1.5 h-1.5 rounded-full mx-auto"
          initial={{ backgroundColor: HOMER_THEME.textMuted }}
          animate={{
            backgroundColor: phase === 2 && i % 7 === 0 ? HOMER_THEME.accent : HOMER_THEME.textMuted,
            scale: phase === 2 && i % 7 === 0 ? 2 : 1,
            boxShadow: phase === 2 && i % 7 === 0 ? `0 0 10px ${HOMER_THEME.accent}` : 'none'
          }}
          transition={{ duration: 0.5 }}
        />
      ))}
    </div>
    <motion.div
      className="absolute top-0 bottom-0 w-48 blur-2xl z-0"
      style={{ background: `linear-gradient(90deg, transparent, ${HOMER_THEME.accentGlow}, transparent)` }}
      animate={{ left: phase === 0 ? '-20%' : phase === 1 ? '50%' : '120%', opacity: phase === 2 ? 0 : 0.6 }}
      transition={{ duration: 2, ease: 'easeInOut' }}
    />
    <motion.div
      className="z-10 p-6 rounded-3xl backdrop-blur-md border"
      style={{ backgroundColor: HOMER_THEME.bgSoft, borderColor: HOMER_THEME.divider }}
      animate={{ scale: phase === 2 ? 1.1 : 1, borderColor: phase === 2 ? HOMER_THEME.accent : HOMER_THEME.divider }}
    >
      <Brain size={64} color={phase === 2 ? HOMER_THEME.accent : HOMER_THEME.text} />
    </motion.div>
  </div>
);

const SchedulerViz = ({ phase }: { phase: number }) => (
  <div className="w-full h-full relative flex items-center justify-center overflow-hidden">
    <motion.div
      className="absolute rounded-full border border-dashed"
      style={{ borderColor: HOMER_THEME.divider, width: '200px', height: '200px' }}
      animate={{ rotate: phase === 0 ? 0 : 180, scale: phase === 1 ? 1.2 : 1 }}
      transition={{ duration: 2 }}
    />
    <div className="z-10 p-6 rounded-full" style={{ backgroundColor: HOMER_THEME.bgSoft }}>
      <Calendar size={48} color={phase === 0 ? HOMER_THEME.text : HOMER_THEME.accent} />
    </div>
    <motion.div
      className="absolute top-1/4 right-1/4 p-3 rounded-xl border flex items-center gap-2"
      style={{ backgroundColor: HOMER_THEME.bgSoft, borderColor: phase === 2 ? '#ef4444' : HOMER_THEME.divider }}
      animate={{ y: phase === 1 ? 0 : 20, opacity: phase > 0 ? 1 : 0 }}
    >
      {phase === 2 ? <AlertCircle size={24} color="#ef4444" /> : <CheckCircle2 size={24} color={HOMER_THEME.accent} />}
      <span style={{ color: HOMER_THEME.text, fontFamily: HOMER_THEME.fontMono }} className="text-xs">
        {phase === 2 ? 'Job Failed' : 'Job Executed'}
      </span>
    </motion.div>
  </div>
);

const ExecutorsViz = ({ phase }: { phase: number }) => (
  <div className="w-full h-full relative flex flex-col md:flex-row items-center justify-center gap-8 md:gap-24 overflow-hidden">
    <motion.div
      className="p-6 rounded-2xl border z-10"
      style={{ backgroundColor: HOMER_THEME.bgSoft, borderColor: phase === 0 ? HOMER_THEME.accent : HOMER_THEME.divider }}
    >
      <Cpu size={48} color={phase === 0 ? HOMER_THEME.accent : HOMER_THEME.text} />
    </motion.div>

    <div className="flex flex-row md:flex-col gap-6 z-10">
      <motion.div
        className="px-6 py-4 rounded-xl border flex items-center gap-3"
        style={{ backgroundColor: HOMER_THEME.bgSoft, borderColor: phase === 1 ? HOMER_THEME.accent : HOMER_THEME.divider }}
        animate={{ opacity: phase === 1 ? 1 : 0.4 }}
      >
        <Network size={20} color={phase === 1 ? HOMER_THEME.accent : HOMER_THEME.textMuted} />
        <span style={{ color: HOMER_THEME.text, fontFamily: HOMER_THEME.fontMono }}>Primary route</span>
      </motion.div>
      <motion.div
        className="px-6 py-4 rounded-xl border flex items-center gap-3"
        style={{ backgroundColor: HOMER_THEME.bgSoft, borderColor: phase === 2 ? HOMER_THEME.accent : HOMER_THEME.divider }}
        animate={{ opacity: phase === 2 ? 1 : 0.4 }}
      >
        <Zap size={20} color={phase === 2 ? HOMER_THEME.accent : HOMER_THEME.textMuted} />
        <span style={{ color: HOMER_THEME.text, fontFamily: HOMER_THEME.fontMono }}>Fallback route</span>
      </motion.div>
    </div>
  </div>
);

const McpViz = ({ phase }: { phase: number }) => {
  // FIXED: list of connected agents must be the canonical 4 CLI clients
  // (Claude, Codex, Gemini, Kimi) per ground truth. Original variant used
  // {GitHub, Files, Terminal, Browser} which doesn't reflect Homer's actual
  // MCP fan-out.
  const tools = ['Claude', 'Codex', 'Gemini', 'Kimi'];
  return (
    <div className="w-full h-full relative flex items-center justify-center overflow-hidden">
      <motion.div
        className="p-6 rounded-full border z-20"
        style={{ backgroundColor: HOMER_THEME.bgSoft, borderColor: HOMER_THEME.accent }}
        animate={{ scale: phase === 0 ? 1 : 1.1 }}
      >
        <Plug size={48} color={HOMER_THEME.accent} />
      </motion.div>

      {tools.map((tool, i) => {
        const angle = (i * Math.PI * 2) / tools.length;
        const radius = 120;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;
        const isActive = phase === 1 || (phase === 2 && i % 2 === 0);

        return (
          <motion.div
            key={tool}
            className="absolute p-3 rounded-lg border z-10"
            style={{
              backgroundColor: HOMER_THEME.bgSoft,
              borderColor: isActive ? HOMER_THEME.accent : HOMER_THEME.divider,
              x, y
            }}
            animate={{ opacity: isActive ? 1 : 0.3 }}
          >
            <span style={{ color: HOMER_THEME.text, fontFamily: HOMER_THEME.fontMono, fontSize: '0.75rem' }}>{tool}</span>
          </motion.div>
        );
      })}
    </div>
  );
};

const VoiceViz = ({ phase }: { phase: number }) => (
  <div className="w-full h-full relative flex flex-col items-center justify-center gap-8 overflow-hidden">
    <div className="flex gap-2 items-center h-16">
      {Array.from({ length: 15 }).map((_, i) => (
        <motion.div
          key={i}
          className="w-2 rounded-full"
          style={{ backgroundColor: phase === 0 ? HOMER_THEME.accent : HOMER_THEME.textMuted }}
          animate={{
            height: phase === 0 ? Math.random() * 48 + 16 : 8,
            opacity: phase === 0 ? 1 : 0.3
          }}
          transition={{
            repeat: phase === 0 ? Infinity : 0,
            repeatType: 'mirror',
            duration: 0.4,
            delay: i * 0.05
          }}
        />
      ))}
    </div>
    <motion.div
      className="p-4 rounded-xl border flex items-center gap-4"
      style={{ backgroundColor: HOMER_THEME.bgSoft, borderColor: phase > 0 ? HOMER_THEME.accent : HOMER_THEME.divider }}
      animate={{ y: phase > 0 ? 0 : 20, opacity: phase > 0 ? 1 : 0 }}
    >
      <FileCode size={24} color={phase === 2 ? HOMER_THEME.accent : HOMER_THEME.text } />
      <span style={{ color: HOMER_THEME.text, fontFamily: HOMER_THEME.fontMono }} className="text-sm">
        {phase === 2 ? '{ "type": "decision", "topic": "..." }' : 'Transcribing audio...'}
      </span>
    </motion.div>
  </div>
);

const WebViz = ({ phase }: { phase: number }) => (
  <div className="w-full h-full relative flex items-center justify-center gap-4 md:gap-16 overflow-hidden p-8">
    <motion.div
      className="w-48 h-64 rounded-xl border p-4 flex flex-col gap-2 relative z-10"
      style={{ backgroundColor: HOMER_THEME.bgSoft, borderColor: phase === 0 || phase === 2 ? HOMER_THEME.accent : HOMER_THEME.divider }}
    >
      <div className="flex gap-1 mb-2">
        <div className="w-2 h-2 rounded-full bg-red-500" />
        <div className="w-2 h-2 rounded-full bg-yellow-500" />
        <div className="w-2 h-2 rounded-full bg-green-500" />
      </div>
      <div className="w-3/4 h-2 rounded bg-white/10" />
      <div className="w-1/2 h-2 rounded bg-white/10" />
      <motion.div className="w-full h-2 rounded mt-4" style={{ backgroundColor: HOMER_THEME.accentGlow }} animate={{ opacity: phase === 0 ? 1 : 0.3 }} />
    </motion.div>

    <motion.div
      className="absolute h-1 hidden md:block"
      style={{ width: '100px', backgroundColor: HOMER_THEME.accent, opacity: phase === 1 ? 1 : 0 }}
    />

    <motion.div
      className="w-48 h-64 rounded-xl border p-4 flex flex-col gap-2 relative z-10"
      style={{ backgroundColor: HOMER_THEME.bgSoft, borderColor: phase === 2 ? HOMER_THEME.accent : HOMER_THEME.divider }}
      animate={{ x: phase === 2 ? 0 : 20, opacity: phase === 2 ? 1 : 0.5 }}
    >
      <Globe size={24} color={phase === 2 ? HOMER_THEME.accent : HOMER_THEME.textMuted} className="mb-2" />
      <div className="w-full h-24 rounded border border-white/5 bg-white/5" />
      <div className="w-3/4 h-2 rounded bg-white/10 mt-2" />
    </motion.div>
  </div>
);

const SUBSYSTEMS = [
  {
    id: 'memory',
    icon: Brain,
    title: 'Memory',
    headline: 'Perfect recall.',
    viz: MemoryViz,
    receipts: ['12,481 claims stored', '90 days retention'],
    built: ['Skip re-explaining the stack.', 'Shared state across surfaces.', 'Recall a 6-week-old decision.'],
    team: ['Perfect customer-history recall.', 'No more re-pasted context.', 'Immutable AI audit trail.']
  },
  {
    id: 'scheduler',
    icon: Calendar,
    title: 'Scheduler',
    headline: 'Works while you sleep.',
    viz: SchedulerViz,
    receipts: ['47 active jobs', '46K+ traced executions'],
    // FIXED: map to ground-truth phase order.
    built: ['3 AM memory consolidate.', 'Survives sleep / wake.', 'Failures page me, loudly.'],
    team: ['Run nightly jobs without DevOps.', 'Succeed or escalate to a human.', 'Replace fragile single-process loops.']
  },
  {
    id: 'executors',
    icon: Cpu,
    title: 'Executors',
    headline: 'Right model. Every time.',
    viz: ExecutorsViz,
    receipts: ['6 supported engines', '99.4% success rate'],
    // FIXED: ground-truth phase order is cycle-keys / cheap-fast-vs-deep / reroute-on-hang.
    built: ['Cycle keys past quotas.', 'Cheap fast vs deep slow.', 'Reroute on provider hang.'],
    team: ['Cheapest capable model, automatic.', 'No vendor lock-in.', 'Survive provider outages.']
  },
  {
    id: 'mcp',
    icon: Plug,
    // FIXED: label was 'MCP' — locked label is 'MCP Server'.
    title: 'MCP Server',
    headline: 'One toolkit. Every agent.',
    viz: McpViz,
    receipts: ['~40 unified tools', '100% capability parity'],
    // FIXED: P2 was "Total capability parity" (a receipt, not a built-for-me bullet);
    // restored to ground-truth P2 = upgrade once → every CLI gains.
    built: ['Wrote a tool once — 4 CLIs use it.', 'Centralized perms + execution logs.', 'Upgrade once, every CLI gains.'],
    team: ['One secure data gateway.', 'Stop rewriting integrations.', 'Centralized rate limiting + auth.']
  },
  {
    id: 'voice',
    icon: Phone,
    title: 'Voice',
    headline: 'Talk to your agents.',
    viz: VoiceViz,
    receipts: ['380ms first audio out', 'Full-duplex barge-in'],
    // FIXED: ground-truth phase order is dictate-while-driving / proactive-call /
    // capture-nuance.
    built: ['Dictate while driving.', 'Proactive call on critical fail.', 'Capture nuance, no laptop.'],
    team: ['Hands-free field tech access.', 'On-call calls with full context.', 'Replace IVR with memory-backed agents.']
  },
  {
    id: 'web',
    icon: Globe,
    // FIXED: label was 'Web' — locked label is 'Web UI'.
    title: 'Web UI',
    headline: 'Window into the mind.',
    viz: WebViz,
    receipts: ['JWT authenticated', 'Cloudflare tunneled'],
    built: ['Watch agents from a phone.', 'Renders PDFs cleanly.', 'Lockstep with the CLI.'],
    team: ['Visual prototyping, no backend build.', 'Stakeholder visibility.', 'Secure global memory dashboard.']
  }
];

export default function Architecture() {
  const [activeIdx, setActiveIdx] = useState(0);
  const active = SUBSYSTEMS[activeIdx];
  const phase = usePhase();

  return (
    <SectionShell
      id="architecture"
      eyebrow="architecture"
      title="Six subsystems, one loop."
      subtitle="Each panel is a real subsystem in production. Tap a tab to watch it run."
    >
      <div className="flex flex-col gap-8 w-full max-w-6xl mx-auto">

        {/* Tab Strip */}
        <div className="flex gap-2 md:gap-4 overflow-x-auto pb-4 scrollbar-hide border-b" style={{ borderColor: HOMER_THEME.divider }}>
          {SUBSYSTEMS.map((sys, idx) => {
            const isActive = activeIdx === idx;
            return (
              <button
                key={sys.id}
                onClick={() => setActiveIdx(idx)}
                className="flex items-center gap-2 px-4 py-3 rounded-t-xl transition-all whitespace-nowrap"
                style={{
                  backgroundColor: isActive ? HOMER_THEME.bgSoft : 'transparent',
                  color: isActive ? HOMER_THEME.text : HOMER_THEME.textMuted,
                  borderBottom: `2px solid ${isActive ? HOMER_THEME.accent : 'transparent'}`
                }}
              >
                <sys.icon size={18} color={isActive ? HOMER_THEME.accent : HOMER_THEME.textMuted} />
                <span style={{ fontFamily: HOMER_THEME.fontMono }} className="text-sm font-medium tracking-wide">
                  {sys.title.toUpperCase()}
                </span>
              </button>
            );
          })}
        </div>

        {/* Content Canvas */}
        <AnimatePresence mode="wait">
          <motion.div
            key={active.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
            className="flex flex-col gap-12"
          >
            {/* Hero Viz */}
            <div
              className="w-full h-64 md:h-96 rounded-3xl border relative overflow-hidden shadow-2xl"
              style={{ backgroundColor: HOMER_THEME.bg, borderColor: HOMER_THEME.divider }}
            >
              <active.viz phase={phase} />
            </div>

            {/* Prose Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12">

              {/* Column 1: Headline & Receipts */}
              <div className="flex flex-col gap-6">
                <h3
                  style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
                  className="text-4xl md:text-5xl font-light leading-tight"
                >
                  {active.headline}
                </h3>
                <div className="flex flex-col gap-3">
                  {active.receipts.map((receipt, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: HOMER_THEME.accent }} />
                      <span style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }} className="text-sm">
                        {receipt}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Column 2: Built for me */}
              <div className="flex flex-col gap-6">
                <h4 style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }} className="text-xs tracking-widest uppercase">
                  Built for me
                </h4>
                <ul className="flex flex-col gap-4">
                  {active.built.map((bullet, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-3 transition-opacity duration-300"
                      style={{ opacity: phase === i ? 1 : 0.4 }}
                    >
                      <Terminal size={16} className="mt-1 flex-shrink-0" color={phase === i ? HOMER_THEME.accent : HOMER_THEME.textMuted} />
                      <span style={{ color: HOMER_THEME.text }} className="text-base leading-snug">
                        {bullet}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Column 3: Deployed for team */}
              <div className="flex flex-col gap-6">
                <h4 style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }} className="text-xs tracking-widest uppercase">
                  Deployed for your team
                </h4>
                <ul className="flex flex-col gap-4">
                  {active.team.map((bullet, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-3 transition-opacity duration-300"
                      style={{ opacity: phase === i ? 1 : 0.4 }}
                    >
                      <CheckCircle2 size={16} className="mt-1 flex-shrink-0" color={phase === i ? HOMER_THEME.accent : HOMER_THEME.textMuted} />
                      <span style={{ color: HOMER_THEME.text }} className="text-base leading-snug">
                        {bullet}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

            </div>
          </motion.div>
        </AnimatePresence>

      </div>
    </SectionShell>
  );
}
