// Variant: MINIMAL BOLD.
// Geometric, type-driven viz — almost zero icons, big serif headline italics,
// rail of mono labels on the left.
// Source: ~/homer/output/gemini/architecture-redesign-minimal-bold-2026-05-03-1700.md.
//
// Fidelity fixes vs. raw extract:
//   - MCP `label: 'MCP'` → `label: 'MCP Server'` (locked label).
//   - Receipts restored to ground-truth verbatim:
//       '12,481 Claims' → '12,481 claims stored'
//       '90 Day Retention' → '90 days retention'
//       '47 Active Jobs' → '47 active jobs'
//       '46K Traces' → '46K+ traced executions'
//       '6 Engines' → '6 supported engines'
//       '99.4% Success' → '99.4% success rate'
//       '~40 Unified Tools' → '~40 unified tools'
//       '100% Parity' → '100% capability parity'
//       '380ms Latency' → '380ms first audio out'
//       'Full Duplex' → 'Full-duplex barge-in'
//       'JWT Auth' → 'JWT authenticated'
//       'Cloudflare Tunneled' → 'Cloudflare tunneled'
//   - Voice P2 bullet: 'Zero-latency barge-in' → 'Capture nuance, no laptop.'
//     (P2 of ground truth = "captures nuance of a spoken idea without ever
//     opening a laptop"; barge-in is a receipt, not a phase-2 bullet).

import React, { useState, useEffect, useMemo } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  Brain, Calendar, Cpu, Plug, Phone, Globe,
  ArrowRight, CheckCircle2,
} from 'lucide-react';
import SectionShell from '../../SectionShell';
import { HOMER_THEME } from '../../theme';

export const META = {
  slug: 'minimal-bold',
  name: 'Minimal Bold',
  philosophy:
    'Geometric, type-driven viz — italic serif headline, mono rail, almost no icons.',
  riskLevel: 'medium' as const,
  layoutChange: 'major' as const,
  distinctiveAnimation:
    'Each viz is pure geometry — orbiting dots, rotating spokes, scaling rings — not literal telemetry.',
};

function usePhase(activeId: string) {
  const [phase, setPhase] = useState(0);
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    if (shouldReduceMotion) {
      setPhase(0);
      return;
    }
    setPhase(0);
    const interval = setInterval(() => {
      setPhase(p => (p + 1) % 3);
    }, 4000);
    return () => clearInterval(interval);
  }, [activeId, shouldReduceMotion]);

  return phase;
}

const VizFrame = ({ children }: { children: React.ReactNode }) => (
  <div
    className="relative w-full h-56 md:h-72 rounded-xl overflow-hidden flex items-center justify-center border"
    style={{ backgroundColor: HOMER_THEME.bgSoft, borderColor: HOMER_THEME.divider }}
  >
    {children}
  </div>
);

const MemoryViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="relative flex items-center justify-center w-full h-full">
      <motion.div
        animate={{
          x: phase === 0 ? 0 : phase === 1 ? -40 : -60,
          scale: phase === 2 ? 0.8 : 1
        }}
        className="w-12 h-12 rounded-full border-2"
        style={{ borderColor: HOMER_THEME.accent, boxShadow: `0 0 20px ${HOMER_THEME.accentGlow}` }}
      />
      <AnimatePresence>
        {phase > 0 && (
          <>
            <motion.div
              initial={{ opacity: 0, x: 0 }}
              animate={{ opacity: 1, x: 40 }}
              exit={{ opacity: 0 }}
              className="absolute w-8 h-8 rounded-full border border-white/20"
            />
            <motion.div
              initial={{ opacity: 0, x: 0 }}
              animate={{
                opacity: phase === 2 ? 1 : 0.4,
                x: phase === 2 ? 80 : 40,
                scale: phase === 2 ? [1, 1.2, 1] : 1
              }}
              transition={phase === 2 ? { repeat: Infinity, duration: 2 } : {}}
              className="absolute w-8 h-8 rounded-full border"
              style={{ borderColor: phase === 2 ? HOMER_THEME.accent : 'white' }}
            />
          </>
        )}
      </AnimatePresence>
      {phase === 2 && (
        <motion.span
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 40 }}
          className="absolute text-[10px] uppercase tracking-tighter font-mono"
          style={{ color: HOMER_THEME.accent }}
        >
          6 weeks ago
        </motion.span>
      )}
    </div>
  </VizFrame>
);

const SchedulerViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="relative w-32 h-32 rounded-full border-2 border-white/5 flex items-center justify-center">
      <motion.div
        animate={{ rotate: phase === 0 ? 0 : phase === 1 ? 90 : 90 }}
        transition={{ type: 'spring', stiffness: 50 }}
        className="absolute w-1 h-14 origin-bottom -translate-y-7 rounded-full"
        style={{ backgroundColor: phase > 0 ? HOMER_THEME.accent : 'white' }}
      />
      <motion.div
        animate={{ opacity: phase === 2 ? [0.2, 1, 0.2] : 0 }}
        transition={{ repeat: Infinity, duration: 1.5 }}
        className="absolute inset-0 rounded-full border-2"
        style={{ borderColor: HOMER_THEME.accent, boxShadow: `inset 0 0 20px ${HOMER_THEME.accentGlow}` }}
      />
      <div className="absolute top-2 font-mono text-[10px] text-white/20">12</div>
      <div className="absolute right-2 font-mono text-[10px] text-white/20">3</div>
    </div>
  </VizFrame>
);

const ExecutorViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="flex flex-col items-center gap-6">
      <motion.div
        animate={{ rotate: phase * 120 }}
        className="w-24 h-24 border-4 border-dashed rounded-full border-white/10 flex items-center justify-center"
      >
        <div className="w-4 h-4 rounded-full bg-white" />
      </motion.div>
      <div className="flex gap-4 font-mono text-[10px] uppercase">
        {/* Generic engine slots — minimal-bold's geometric vibe avoids vendor names. */}
        {['ENGINE A', 'ENGINE B', 'ENGINE C'].map((m, i) => (
          <span key={m} style={{ color: phase === i ? HOMER_THEME.accent : HOMER_THEME.textMuted }}>
            {m}
          </span>
        ))}
      </div>
    </div>
  </VizFrame>
);

const MCPViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="relative flex items-center justify-center">
      <div className="w-4 h-4 bg-white rounded-full z-10" />
      {[0, 1, 2, 3].map((i) => (
        <motion.div
          key={i}
          animate={{
            height: phase > 0 ? 60 : 0,
            rotate: i * 90,
            opacity: phase === 2 ? [0.3, 1, 0.3] : 1
          }}
          className="absolute w-[1px] origin-bottom bottom-1/2"
          style={{ backgroundColor: phase === 2 ? HOMER_THEME.accent : 'white' }}
        />
      ))}
    </div>
  </VizFrame>
);

const VoiceViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="relative flex items-center justify-center">
      {[1, 2, 3].map((i) => (
        <motion.div
          key={i}
          animate={{
            scale: phase === 0 ? [1, 1.2, 1] : 1,
            borderRadius: phase === 2 ? '4px' : '999px',
            opacity: phase === 2 && i > 1 ? 0 : 1,
            width: phase === 2 ? 60 : i * 40,
            height: phase === 2 ? 40 : i * 40,
          }}
          transition={{ duration: 0.8, delay: phase === 0 ? i * 0.1 : 0 }}
          className="absolute border border-white/20"
          style={{ borderColor: phase === 2 ? HOMER_THEME.accent : 'white' }}
        />
      ))}
    </div>
  </VizFrame>
);

const WebViz = ({ phase }: { phase: number }) => (
  <VizFrame>
    <div className="w-32 h-56 border-2 border-white/10 rounded-2xl p-2 relative overflow-hidden">
      <motion.div
        animate={{ y: phase === 0 ? 0 : phase === 1 ? -60 : -120 }}
        className="flex flex-col gap-4"
      >
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="w-full h-12 bg-white/5 rounded-md flex items-center px-2">
            <div className="w-full h-2 bg-white/10 rounded" />
          </div>
        ))}
      </motion.div>
      <div className="absolute inset-x-0 top-0 h-4 bg-gradient-to-b from-[#141210] to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-4 bg-gradient-to-t from-[#141210] to-transparent" />
    </div>
  </VizFrame>
);

type Subsystem = {
  id: string;
  label: string;
  icon: React.ElementType;
  headline: string;
  built: string[];
  team: string[];
  receipts: string[];
  Viz: React.FC<{ phase: number }>;
};

const SUBSYSTEMS: Subsystem[] = [
  {
    id: 'memory',
    label: 'Memory',
    icon: Brain,
    headline: 'Perfect recall.',
    built: ['Skip re-explaining the stack.', 'Cross-surface state.', 'Recall a 6-week-old config.'],
    team: ['Customer-history recall.', 'Zero re-pasting.', 'Immutable audit trail.'],
    receipts: ['12,481 claims stored', '90 days retention'],
    Viz: MemoryViz
  },
  {
    id: 'scheduler',
    label: 'Scheduler',
    icon: Calendar,
    headline: 'Wakes at three.',
    built: ['3 AM batch consolidate.', 'Survives sleep / wake.', 'Loud failure → page me.'],
    team: ['Hands-off nightly jobs.', 'Succeed or escalate.', 'Kill fragile loops.'],
    receipts: ['47 active jobs', '46K+ traced executions'],
    Viz: SchedulerViz
  },
  {
    id: 'executors',
    label: 'Executors',
    icon: Cpu,
    headline: 'Optimal routing.',
    built: ['Cycle keys past quotas.', 'Cheap fast vs deep slow.', 'Reroute on provider hang.'],
    team: ['Cheapest capable model.', 'No vendor lock-in.', 'Survive provider outages.'],
    receipts: ['6 supported engines', '99.4% success rate'],
    Viz: ExecutorViz
  },
  {
    id: 'mcp',
    // FIXED: 'MCP' → 'MCP Server'.
    label: 'MCP Server',
    icon: Plug,
    headline: 'One toolkit.',
    built: ['Write once, used everywhere.', 'Centralized perms + logs.', 'Upgrade once, every CLI gains.'],
    team: ['Secure data gateway.', 'Stop rewriting integrations.', 'Centralized rate limit + auth.'],
    receipts: ['~40 unified tools', '100% capability parity'],
    Viz: MCPViz
  },
  {
    id: 'voice',
    label: 'Voice',
    icon: Phone,
    headline: 'Talk to it.',
    // FIXED: P2 was 'Zero-latency barge-in' (a receipt). Restored to ground
    // truth P2 = "captures nuance of a spoken idea without ever opening a
    // laptop."
    built: ['Drive-time dictation.', 'Proactive failure calls.', 'Capture nuance, no laptop.'],
    team: ['Hands-free field tech.', 'On-call calls with context.', 'Replace IVR trees.'],
    receipts: ['380ms first audio out', 'Full-duplex barge-in'],
    Viz: VoiceViz
  },
  {
    id: 'web',
    label: 'Web UI',
    icon: Globe,
    headline: 'Glass dashboard.',
    built: ['Watch from a phone.', 'Renders PDFs cleanly.', 'Lockstep with the CLI.'],
    team: ['Stakeholder visibility.', 'Visual prototyping.', 'Secure Cloudflare tunnel.'],
    receipts: ['JWT authenticated', 'Cloudflare tunneled'],
    Viz: WebViz
  }
];

export const Architecture: React.FC = () => {
  const [activeId, setActiveId] = useState(SUBSYSTEMS[0].id);
  const phase = usePhase(activeId);
  const active = useMemo(() => SUBSYSTEMS.find(s => s.id === activeId)!, [activeId]);

  return (
    <SectionShell
      id="architecture"
      eyebrow="architecture"
      title="Six subsystems, one loop."
      subtitle="Each panel is a real subsystem in production."
    >
      <div className="flex flex-col md:flex-row gap-12 mt-12">
        {/* Left: Rail */}
        <div className="w-full md:w-[260px] flex md:flex-col gap-2 overflow-x-auto pb-4 md:pb-0 scrollbar-hide">
          {SUBSYSTEMS.map((s) => {
            const Icon = s.icon;
            const isActive = activeId === s.id;
            return (
              <button
                key={s.id}
                onClick={() => setActiveId(s.id)}
                className="group flex items-center gap-4 p-3 rounded-lg transition-all text-left flex-shrink-0"
                style={{
                  backgroundColor: isActive ? HOMER_THEME.bgSoft : 'transparent',
                  border: `1px solid ${isActive ? HOMER_THEME.divider : 'transparent'}`
                }}
              >
                <Icon
                  size={18}
                  style={{ color: isActive ? HOMER_THEME.accent : HOMER_THEME.textMuted }}
                />
                <span
                  className="font-mono text-xs uppercase tracking-widest transition-colors"
                  style={{ color: isActive ? HOMER_THEME.text : HOMER_THEME.textMuted }}
                >
                  {s.label}
                </span>
              </button>
            );
          })}
        </div>

        {/* Right: Detail */}
        <div className="flex-1 space-y-8 min-w-0">
          <div className="space-y-4">
            <active.Viz phase={phase} />

            <h3
              className="text-3xl md:text-4xl italic"
              style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
            >
              {active.headline}
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Built for Me */}
            <div className="space-y-4">
              <span className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: HOMER_THEME.textMuted }}>Built for me</span>
              <ul className="space-y-3">
                {active.built.map((b, i) => (
                  <li
                    key={i}
                    className="flex items-center gap-3 transition-opacity duration-500"
                    style={{ opacity: phase === i ? 1 : 0.3, color: HOMER_THEME.text }}
                  >
                    <ArrowRight size={12} style={{ color: HOMER_THEME.accent }} />
                    <span className="text-sm font-medium">{b}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Deployed for Team */}
            <div className="space-y-4">
              <span className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: HOMER_THEME.textMuted }}>For your team</span>
              <ul className="space-y-3">
                {active.team.map((t, i) => (
                  <li
                    key={i}
                    className="flex items-center gap-3 transition-opacity duration-500"
                    style={{ opacity: phase === i ? 1 : 0.3, color: HOMER_THEME.text }}
                  >
                    <CheckCircle2 size={12} style={{ color: HOMER_THEME.textMuted }} />
                    <span className="text-sm font-medium">{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Receipts */}
          <div className="pt-8 border-t flex flex-wrap gap-x-12 gap-y-4" style={{ borderColor: HOMER_THEME.divider }}>
            {active.receipts.map((r, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-1 h-1 rounded-full" style={{ backgroundColor: HOMER_THEME.accent }} />
                <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: HOMER_THEME.textMuted }}>{r}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </SectionShell>
  );
};

export default Architecture;
