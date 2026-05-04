// Variant: SPATIAL FLOW.
// Topology canvas — six subsystems as nodes connected by SVG edges; clicking
// a node opens a detail drawer.
// Source: ~/homer/output/gemini/architecture-redesign-spatial-flow-2026-05-03-1700.md.
//
// Fidelity fixes vs. raw extract:
//   - MCP `label: 'MCP Gateway'` → `label: 'MCP Server'` (locked label).
//   - Web `label: 'Web'` → `label: 'Web UI'` (locked label).
//   - Eyebrow casing kept lower-case ("architecture") for consistency with the
//     other variants and the live page.

import React, { useState, useEffect } from 'react';
import { motion, useReducedMotion, AnimatePresence } from 'framer-motion';
import { Database, Clock, Cpu, Plug, Phone, Globe, ArrowRight } from 'lucide-react';
import { HOMER_THEME } from '../../theme';
import SectionShell from '../../SectionShell';

export const META = {
  slug: 'spatial-flow',
  name: 'Spatial Flow',
  philosophy:
    'Topology canvas — six nodes, ambient edges, click any node to trace its flow.',
  riskLevel: 'high' as const,
  layoutChange: 'total' as const,
  distinctiveAnimation:
    'SVG edges pulse between nodes; selecting a node dims the rest and reveals a side drawer with its 3-phase loop.',
};

interface Subsystem {
  id: string;
  label: string;
  headline: string;
  icon: React.ElementType;
  pos: { x: number; y: number };
  mine: string[];
  team: string[];
  receipts: string[];
}

interface EdgeDef {
  id: string;
  source: string;
  target: string;
  path: string;
}

const SUBSYSTEMS: Subsystem[] = [
  {
    id: 'memory',
    label: 'Memory',
    headline: 'Perfect recall.',
    icon: Database,
    pos: { x: 300, y: 200 },
    mine: ['Skip re-explaining the stack.', 'Cross-surface state sync.', 'Recall a 6-week-old config.'],
    team: ['Perfect customer-history recall.', 'Single source of truth.', 'Immutable AI audit trail.'],
    receipts: ['12,481 claims stored', '90 days retention']
  },
  {
    id: 'scheduler',
    label: 'Scheduler',
    headline: 'While you sleep.',
    icon: Clock,
    pos: { x: 300, y: 50 },
    mine: ['3 AM memory consolidate.', 'Survives sleep / wake.', 'Loud failure → page me.'],
    team: ['Automated nightly reporting.', 'Succeed or escalate.', 'Robust production orchestrator.'],
    receipts: ['47 active jobs', '46K+ traced executions']
  },
  {
    id: 'executors',
    label: 'Executors',
    headline: 'Right model. Always.',
    icon: Cpu,
    pos: { x: 300, y: 350 },
    mine: ['Cycle keys past quotas.', 'Cheap fast vs deep slow.', 'Reroute on provider hang.'],
    team: ['Cheapest capable model.', 'No vendor lock-in.', 'Survive provider outages.'],
    receipts: ['6 supported engines', '99.4% success rate']
  },
  {
    id: 'mcp',
    // FIXED: 'MCP Gateway' → 'MCP Server' (locked label).
    label: 'MCP Server',
    headline: 'One toolkit, everywhere.',
    icon: Plug,
    pos: { x: 480, y: 200 },
    mine: ['Write tool once, used by 4 CLIs.', 'Centralized perms + logs.', 'Upgrade once, every CLI gains.'],
    team: ['Secure internal gateway.', 'Stop rewriting integrations.', 'Centralized rate limit + auth.'],
    receipts: ['~40 unified tools', '100% capability parity']
  },
  {
    id: 'voice',
    label: 'Voice',
    headline: 'Hands-free context.',
    icon: Phone,
    pos: { x: 120, y: 300 },
    mine: ['Dictate while driving.', 'Proactive failure calls.', 'Capture nuance, no laptop.'],
    team: ['Hands-free field tech.', 'On-call calls with full context.', 'Replace IVR with memory-backed agents.'],
    receipts: ['380ms first audio out', 'Full-duplex barge-in']
  },
  {
    id: 'web',
    // FIXED: 'Web' → 'Web UI' (locked label).
    label: 'Web UI',
    headline: 'A window in.',
    icon: Globe,
    pos: { x: 120, y: 100 },
    mine: ['Watch agents from a phone.', 'Renders PDFs cleanly.', 'Lockstep with the CLI.'],
    team: ['Visual prototyping, no backend build.', 'Stakeholder visibility.', 'Secure global memory dashboard.'],
    receipts: ['JWT authenticated', 'Cloudflare tunneled']
  }
];

const EDGES: EdgeDef[] = [
  { id: 'mem-sch', source: 'memory', target: 'scheduler', path: 'M 300 200 L 300 50' },
  { id: 'mem-exe', source: 'memory', target: 'executors', path: 'M 300 200 L 300 350' },
  { id: 'mem-mcp', source: 'memory', target: 'mcp', path: 'M 300 200 L 480 200' },
  { id: 'sch-exe', source: 'scheduler', target: 'executors', path: 'M 300 50 Q 420 200 300 350' },
  { id: 'mcp-exe', source: 'mcp', target: 'executors', path: 'M 480 200 L 300 350' },
  { id: 'mcp-voi', source: 'mcp', target: 'voice', path: 'M 480 200 Q 300 350 120 300' },
  { id: 'mcp-web', source: 'mcp', target: 'web', path: 'M 480 200 Q 300 50 120 100' },
  { id: 'voi-mem', source: 'voice', target: 'memory', path: 'M 120 300 L 300 200' },
  { id: 'web-mem', source: 'web', target: 'memory', path: 'M 120 100 L 300 200' },
];

const usePhaseLoop = (phases: number, durationMs: number) => {
  const [phase, setPhase] = useState(0);
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    if (prefersReducedMotion) {
      setPhase(0);
      return;
    }
    const interval = setInterval(() => {
      setPhase((p) => (p + 1) % phases);
    }, durationMs / phases);
    return () => clearInterval(interval);
  }, [phases, durationMs, prefersReducedMotion]);

  return phase;
};

const MicroViz = ({ phase }: { phase: number }) => {
  return (
    <div className="flex flex-col items-center gap-4 w-full">
      <div
        className="relative w-24 h-24 flex items-center justify-center rounded-full border border-dashed"
        style={{ borderColor: HOMER_THEME.divider }}
      >
        <motion.div
          className="absolute inset-0 rounded-full border-t-2"
          style={{ borderColor: HOMER_THEME.accent }}
          animate={{ rotate: phase === 1 ? 360 : 0 }}
          transition={{ duration: 1.33, ease: 'linear', repeat: phase === 1 ? Infinity : 0 }}
        />
        <div className="w-12 h-12 rounded-full flex items-center justify-center relative overflow-hidden shadow-inner" style={{ backgroundColor: HOMER_THEME.bg }}>
          <motion.div
            className="w-4 h-4 rounded-full z-10"
            animate={{
              scale: phase === 0 ? [1, 1.5, 1] : 1,
              backgroundColor: phase === 2 ? HOMER_THEME.accent : HOMER_THEME.textMuted
            }}
            transition={{ duration: 1.33, repeat: phase === 0 ? Infinity : 0 }}
          />
        </div>
      </div>
      <div className="flex gap-2 mt-2">
        {[0, 1, 2].map(i => (
          <div
            key={i}
            className="w-2 h-2 rounded-full transition-colors duration-300"
            style={{ backgroundColor: phase === i ? HOMER_THEME.accent : HOMER_THEME.divider }}
          />
        ))}
      </div>
      <div className="text-[10px] uppercase tracking-widest mt-2" style={{ color: HOMER_THEME.accent, fontFamily: HOMER_THEME.fontMono }}>
        {phase === 0 && 'INIT'}
        {phase === 1 && 'PROCESS'}
        {phase === 2 && 'SYNCED'}
      </div>
    </div>
  );
};

export const Architecture: React.FC = () => {
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const phase = usePhaseLoop(3, 4000);

  const activeData = SUBSYSTEMS.find(s => s.id === activeNode);

  const isEdgeActive = (edge: EdgeDef) => {
    if (!activeNode) return true; // Ambient flow when nothing is selected
    return edge.source === activeNode || edge.target === activeNode;
  };

  const handleNodeClick = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    setActiveNode(activeNode === id ? null : id);
  };

  return (
    <SectionShell
      id="architecture"
      eyebrow="architecture"
      title="Six subsystems, one loop."
      subtitle="Six specialized subsystems, unified by memory. Select a node to trace the flow."
    >
      <div className="w-full flex flex-col items-center z-10">
        {/* Desktop SVG Topology */}
        <div className="hidden md:block relative w-[600px] h-[400px] mb-8">
          <svg width="600" height="400" className="absolute inset-0 pointer-events-none">
            {EDGES.map(edge => {
              const active = isEdgeActive(edge);
              return (
                <g key={edge.id}>
                  <path
                    d={edge.path}
                    fill="none"
                    stroke={active ? (activeNode ? HOMER_THEME.accent : HOMER_THEME.textMuted) : HOMER_THEME.divider}
                    strokeWidth="1.5"
                    className="transition-colors duration-500"
                  />
                  {active && (
                    <motion.path
                      d={edge.path}
                      fill="none"
                      stroke={HOMER_THEME.accent}
                      strokeWidth="2"
                      strokeDasharray="4 12"
                      initial={{ strokeDashoffset: 16 }}
                      animate={{ strokeDashoffset: 0 }}
                      transition={{ repeat: Infinity, ease: 'linear', duration: 0.6 }}
                      style={{ opacity: activeNode ? 1 : 0.2 }}
                    />
                  )}
                </g>
              );
            })}
          </svg>

          {SUBSYSTEMS.map(s => {
            const isActive = activeNode === s.id;
            const isDimmed = !!activeNode && !isActive;
            const Icon = s.icon;
            return (
              <div
                key={s.id}
                className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-3 cursor-pointer transition-all duration-300"
                style={{
                  left: s.pos.x,
                  top: s.pos.y,
                  opacity: isDimmed ? 0.3 : 1,
                  transform: `translate(-50%, -50%) scale(${isActive ? 1.1 : 1})`,
                }}
                onClick={(e) => handleNodeClick(e, s.id)}
              >
                <div
                  className="w-14 h-14 rounded-full border flex items-center justify-center transition-all duration-300 shadow-2xl"
                  style={{
                    backgroundColor: HOMER_THEME.bgSoft,
                    borderColor: isActive ? HOMER_THEME.accent : HOMER_THEME.divider,
                    boxShadow: isActive ? `0 0 24px -6px ${HOMER_THEME.accent}` : 'none'
                  }}
                >
                  <Icon size={22} color={isActive ? HOMER_THEME.accent : HOMER_THEME.textMuted} />
                </div>
                <span
                  style={{ color: isActive ? HOMER_THEME.accent : HOMER_THEME.text, fontFamily: HOMER_THEME.fontMono }}
                  className="text-[10px] font-semibold tracking-widest uppercase transition-colors"
                >
                  {s.label}
                </span>
              </div>
            );
          })}
        </div>

        {/* Mobile List View */}
        <div className="md:hidden flex flex-col gap-3 w-full max-w-sm mb-8">
          {SUBSYSTEMS.map(s => {
            const isActive = activeNode === s.id;
            const Icon = s.icon;
            return (
              <div
                key={s.id}
                onClick={(e) => handleNodeClick(e, s.id)}
                className="p-4 rounded-xl border flex items-center gap-4 cursor-pointer transition-all duration-300"
                style={{
                  borderColor: isActive ? HOMER_THEME.accent : HOMER_THEME.divider,
                  backgroundColor: HOMER_THEME.bgSoft
                }}
              >
                <Icon size={24} color={isActive ? HOMER_THEME.accent : HOMER_THEME.textMuted} />
                <span className="text-sm uppercase tracking-widest font-semibold" style={{ fontFamily: HOMER_THEME.fontMono, color: isActive ? HOMER_THEME.accent : HOMER_THEME.text }}>
                  {s.label}
                </span>
              </div>
            );
          })}
        </div>

        {/* Detail Panel Drawer */}
        <div className="h-[420px] md:h-[380px] w-full max-w-4xl relative">
          <AnimatePresence mode="wait">
            {activeData ? (
              <motion.div
                key={activeData.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
                className="absolute inset-0 w-full h-full p-6 md:p-10 border rounded-2xl flex flex-col md:flex-row gap-8 shadow-2xl overflow-y-auto overflow-x-hidden"
                style={{ borderColor: HOMER_THEME.divider, backgroundColor: HOMER_THEME.bgSoft }}
              >
                <div className="flex-1 flex flex-col justify-between">
                  <div>
                    <h3 className="text-3xl md:text-4xl mb-8 font-light" style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.accent }}>
                      {activeData.headline}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
                      <div>
                        <h4 className="text-[10px] uppercase tracking-widest mb-4" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>Built for me</h4>
                        <div className="flex flex-col gap-3">
                          {activeData.mine.map((b, i) => (
                            <div key={i} className={`flex items-start gap-2 text-sm transition-opacity duration-300 ${phase === i ? 'opacity-100' : 'opacity-40'}`}>
                              <ArrowRight size={14} className="mt-1 shrink-0" style={{ color: HOMER_THEME.accent }} />
                              <span style={{ color: HOMER_THEME.text }}>{b}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div>
                        <h4 className="text-[10px] uppercase tracking-widest mb-4" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>Deployed for team</h4>
                        <div className="flex flex-col gap-3">
                          {activeData.team.map((b, i) => (
                            <div key={i} className={`flex items-start gap-2 text-sm transition-opacity duration-300 ${phase === i ? 'opacity-100' : 'opacity-40'}`}>
                              <ArrowRight size={14} className="mt-1 shrink-0" style={{ color: HOMER_THEME.accent }} />
                              <span style={{ color: HOMER_THEME.text }}>{b}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="mt-8 flex flex-wrap gap-3">
                    {activeData.receipts.map((r, i) => (
                      <div key={i} className="text-[10px] px-3 py-1 rounded-full border bg-black/20 uppercase tracking-wide" style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>
                        {r}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="w-full md:w-64 flex flex-col justify-center border-t md:border-t-0 md:border-l pt-8 md:pt-0 md:pl-8 mt-4 md:mt-0" style={{ borderColor: HOMER_THEME.divider }}>
                  <h4 className="text-[10px] uppercase tracking-widest mb-8 text-center" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>System State</h4>
                  <MicroViz phase={phase} />
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 w-full h-full border rounded-2xl flex flex-col items-center justify-center border-dashed"
                style={{ borderColor: HOMER_THEME.divider }}
              >
                <Plug size={32} className="mb-4 opacity-20" style={{ color: HOMER_THEME.textMuted }} />
                <span className="text-sm uppercase tracking-widest opacity-50" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>
                  Awaiting subsystem selection
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </SectionShell>
  );
};

export default Architecture;
