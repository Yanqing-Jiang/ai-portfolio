// Variant: SAFE WINNER (Pro Direction A).
// Two-column scannable layout — list left, sticky detail panel right.
// Source: ~/homer/output/gemini/architecture-redesign-pro-A-2026-05-03-1700.md.
//
// Fidelity fixes vs. raw extract:
//   - Scheduler "Built for me" bullets rewritten to map 1:1 to phases 0/1/2 of
//     ground-truth animation (3 AM consolidate / survives sleep-wake / loud
//     failures via Telegram or voice). Original variant drifted to "intelligence
//     briefs / retry flaky APIs / trigger from Slack" which contradicts ground
//     truth and breaks the bullet↔phase sync.
//   - SectionShell title aligned to canonical "Six subsystems, one loop." with
//     the locked subtitle so the variant page is recognizable.

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { Brain, Calendar, Cpu, Plug, Phone, Globe, Database, Terminal, MessageSquare, Zap, AlertCircle, RefreshCw, Shield, Mic, FileText, Smartphone, Lock } from 'lucide-react';
import { SectionShell } from '../SectionShell';
import { HOMER_THEME } from '../theme';

export const META = {
  slug: 'safe-winner',
  name: 'Safe Winner',
  philosophy:
    'Telegraphic 2-column layout — punchy bullets, bigger viz container, scannable left rail.',
  riskLevel: 'low' as const,
  layoutChange: 'none' as const,
  distinctiveAnimation:
    'Per-subsystem viz cycles 3 phases (2s loop) — DB writes / launchd run / API failover / shield + fan-out / mic + transcript / phone-to-dashboard.',
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
export const Architecture: React.FC = () => {
  const [activeId, setActiveId] = useState<string>(SUBSYSTEMS[0].id);
  const phase = usePhase(2000);

  const activeSub = SUBSYSTEMS.find(s => s.id === activeId) || SUBSYSTEMS[0];
  const ActiveViz = activeSub.viz;

  return (
    <SectionShell
      id="architecture"
      eyebrow="architecture"
      title="Six subsystems, one loop."
      subtitle="Each panel is a real subsystem in production. Click to see its actual telemetry."
    >
      <div className="mt-12 grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-start">
        {/* Left Column: Navigation List */}
        <div className="lg:col-span-5 flex flex-col gap-2">
          {SUBSYSTEMS.map((sub) => {
            const isActive = sub.id === activeId;
            const Icon = sub.icon;
            return (
              <button
                key={sub.id}
                onClick={() => setActiveId(sub.id)}
                className="w-full min-h-[64px] text-left p-4 rounded-xl transition-all duration-300 flex items-center gap-4 group"
                style={{
                  backgroundColor: isActive ? HOMER_THEME.bgSoft : 'transparent',
                  borderColor: isActive ? HOMER_THEME.divider : 'transparent',
                  borderWidth: 1,
                }}
              >
                <div
                  className="p-3 rounded-lg transition-colors"
                  style={{
                    backgroundColor: isActive ? HOMER_THEME.accentSoft : 'transparent',
                    color: isActive ? HOMER_THEME.accent : HOMER_THEME.textMuted
                  }}
                >
                  <Icon size={20} />
                </div>
                <div className="min-w-0">
                  <h3
                    className="font-mono text-lg transition-colors"
                    style={{ color: isActive ? HOMER_THEME.text : HOMER_THEME.textMuted }}
                  >
                    {sub.label}
                  </h3>
                  <p className="text-sm font-serif italic mt-1" style={{ color: isActive ? HOMER_THEME.accent : HOMER_THEME.textMuted }}>
                    {sub.headline}
                  </p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Right Column: Sticky Detail Panel
            NOTE: We deliberately do NOT wrap this in <AnimatePresence mode="wait">.
            With framer-motion 11 + React 19, the parent re-renders every 2s
            (from `usePhase`); a wait-for-exit cycle on the keyed child gets
            interrupted on each tick and the new viz never mounts — leaving the
            right panel stuck on whatever was active first (Memory by default).
            Plain key-based remount on <motion.div> is enough: React unmounts
            the old, mounts the new, and `initial → animate` plays the fade-in. */}
        <div className="lg:col-span-7 lg:sticky lg:top-24 flex flex-col gap-8">
          <motion.div
            key={activeSub.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="flex flex-col gap-8"
          >
              <ActiveViz phase={phase} />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div>
                  <h4 className="font-mono text-sm mb-4" style={{ color: HOMER_THEME.text }}>Built for me</h4>
                  <ul className="space-y-3">
                    {activeSub.me.map((b, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm transition-opacity duration-300" style={{ color: HOMER_THEME.textMuted, opacity: phase === i ? 1 : 0.4 }}>
                        <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: phase === i ? HOMER_THEME.accent : HOMER_THEME.divider }} />
                        {b}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="font-mono text-sm mb-4" style={{ color: HOMER_THEME.text }}>Deployed for your team</h4>
                  <ul className="space-y-3">
                    {activeSub.team.map((b, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm transition-opacity duration-300" style={{ color: HOMER_THEME.textMuted, opacity: phase === i ? 1 : 0.4 }}>
                        <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: phase === i ? HOMER_THEME.accent : HOMER_THEME.divider }} />
                        {b}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="flex flex-wrap gap-4 pt-6 border-t" style={{ borderColor: HOMER_THEME.divider }}>
                {activeSub.receipts.map((r, i) => (
                  <div key={i} className="px-3 py-1.5 rounded text-xs font-mono whitespace-nowrap" style={{ backgroundColor: HOMER_THEME.bgSoft, color: HOMER_THEME.textMuted, border: `1px solid ${HOMER_THEME.divider}` }}>
                    {r}
                  </div>
                ))}
              </div>
          </motion.div>
        </div>
      </div>
    </SectionShell>
  );
};

export default Architecture;
