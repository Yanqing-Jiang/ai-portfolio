/**
 * Component: Architecture — rendered from HomerLitePage.tsx as one of the section
 * children inside the dark editorial flow. Wraps its content in SectionShell so the
 * eyebrow / title / subtitle / fade-up reveal stay consistent with every other
 * Homer Lite section.
 *
 * Direction: LIVE DATA / TERMINAL.
 *   The viz reads like real telemetry — SQLite rows, launchd logs, JSON-RPC
 *   frames, transcript streams — not abstract icons. Each of the six subsystems
 *   has a 3-phase animation that steps in lockstep with its 3 "Built for me"
 *   bullets (active bullet brightens, others dim) on a 4 s loop. Loop is
 *   suppressed under prefers-reduced-motion (frozen at phase 0).
 *
 * Animation metaphors (one line each):
 *   - Memory:    INSERT row -> 2-source table -> fts5 MATCH highlight on a 6-wk-old row
 *   - Scheduler: launchd START -> OK -> FAIL ECONNRESET + Telegram "paged @yj" toast
 *   - Executors: routing log w/ token+latency rows -> 429 row -> retry fallback
 *   - MCP:       JSON-RPC tools/call frame -> fan-out to 4 named clients -> auth: deny
 *   - Voice:     mic + first_audio_out 380 ms counter -> typewriter transcript ->
 *                structured claim row { type: "decision", ... }
 *   - Web UI:    phone frame -> desktop dashboard -> PDF render, "tunneled" badge
 *
 * Stack: React + framer-motion + lucide-react + tailwind only. No new deps.
 * Theme: HOMER_THEME tokens (gold + warm dark + Fraunces serif + JetBrains Mono).
 *        Red #ef4444 for error states, green #22c55e for healthy / tunneled —
 *        both already in use elsewhere in this codebase.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Database,
  Calendar,
  Cpu,
  Plug,
  Mic,
  LayoutDashboard,
  ChevronRight,
  RefreshCw,
  Phone,
} from 'lucide-react';
import SectionShell from '../../SectionShell';
import { HOMER_THEME } from '../../theme';

/* -------------------------------------------------------------------------- */
/*                                   TYPES                                    */
/* -------------------------------------------------------------------------- */

type SubsystemId = 'memory' | 'scheduler' | 'executors' | 'mcp' | 'voice' | 'web';

interface Subsystem {
  id: SubsystemId;
  label: string;
  headline: string;
  icon: React.ElementType;
  builtBullets: string[];
  teamBullets: string[];
  receipts: string[];
}

/* -------------------------------------------------------------------------- */
/*                                    DATA                                    */
/* -------------------------------------------------------------------------- */

const SUBSYSTEMS: Subsystem[] = [
  {
    id: 'memory',
    label: 'Memory',
    headline: 'Perfect recall.',
    icon: Database,
    builtBullets: [
      'Never re-explains stack.',
      'CLI + Slack share state.',
      'Recall 6-week-old config.',
    ],
    teamBullets: [
      'Perfect customer-history recall.',
      'Stop re-pasting context.',
      'Immutable AI audit trail.',
    ],
    receipts: ['12,481 claims', 'fts5 + vec0', '90d retention'],
  },
  {
    id: 'scheduler',
    label: 'Scheduler',
    headline: 'Loud failure.',
    icon: Calendar,
    builtBullets: [
      '3am memory consolidate.',
      'Survives sleep / wake.',
      'Failures page me.',
    ],
    teamBullets: [
      'No DevOps for nightly jobs.',
      'Escalate or succeed.',
      'Kill fragile loops.',
    ],
    receipts: ['47 jobs', '46K runs traced', 'launchd'],
  },
  {
    id: 'executors',
    label: 'Executors',
    headline: 'Right model, every time.',
    icon: Cpu,
    builtBullets: [
      'Cycle keys past quotas.',
      'Cheap fast / deep slow.',
      'Auto-fallback on hang.',
    ],
    teamBullets: [
      'Cheapest capable model.',
      'No vendor lock-in.',
      'Survive provider outages.',
    ],
    receipts: ['6 engines', '99.4% success'],
  },
  {
    id: 'mcp',
    label: 'MCP Server',
    headline: 'Write once. Use everywhere.',
    icon: Plug,
    builtBullets: [
      'Write tool once.',
      'Centralized auth + logs.',
      'Upgrade once, used everywhere.',
    ],
    teamBullets: [
      'One secure data gateway.',
      'Stop rewriting integrations.',
      'Centralized rate limiting.',
    ],
    receipts: ['~40 tools', '4 CLI clients'],
  },
  {
    id: 'voice',
    label: 'Voice',
    headline: 'Talk to it.',
    icon: Mic,
    builtBullets: [
      'Dictate while driving.',
      'Calls me on critical fail.',
      'Speech to memory rows.',
    ],
    teamBullets: [
      'Hands-free field ops.',
      'Incident calls with context.',
      'Replace IVR trees.',
    ],
    receipts: ['380ms first audio', 'Full-duplex'],
  },
  {
    id: 'web',
    label: 'Web UI',
    headline: 'Window into the machine.',
    icon: LayoutDashboard,
    builtBullets: [
      'Watch agents from phone.',
      'Renders PDFs cleanly.',
      'Same backend as CLI.',
    ],
    teamBullets: [
      'Visual prototyping, no backend build.',
      'Stakeholder visibility.',
      'Globally accessible dashboard.',
    ],
    receipts: ['JWT auth', 'Cloudflare tunneled'],
  },
];

const RED = '#ef4444';
const GREEN = '#22c55e';

/* -------------------------------------------------------------------------- */
/*                              HOOK: REDUCED MOTION                          */
/* -------------------------------------------------------------------------- */

const useReducedMotion = (): boolean => {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const listener = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener?.('change', listener);
    return () => mq.removeEventListener?.('change', listener);
  }, []);
  return reduced;
};

/* -------------------------------------------------------------------------- */
/*                               TERMINAL CHROME                              */
/* -------------------------------------------------------------------------- */

const TerminalChrome: React.FC<{ title: string }> = ({ title }) => (
  <div
    className="flex items-center justify-between px-3 py-1.5 border-b"
    style={{
      background: HOMER_THEME.bg,
      borderColor: HOMER_THEME.divider,
    }}
  >
    <div className="flex gap-1.5">
      <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(239,68,68,0.6)' }} />
      <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(234,179,8,0.6)' }} />
      <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(34,197,94,0.6)' }} />
    </div>
    <div
      className="text-[10px] uppercase tracking-[0.24em]"
      style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
    >
      {title}
    </div>
    <div className="w-10" />
  </div>
);

/* -------------------------------------------------------------------------- */
/*                               VIZ COMPONENTS                               */
/* -------------------------------------------------------------------------- */

interface VizProps {
  phase: number;
}

// 1) MEMORY — SQLite-style insert -> table -> fts5 MATCH highlight
const MemoryViz: React.FC<VizProps> = ({ phase }) => (
  <div
    className="p-4 text-[11px] space-y-3 h-full overflow-hidden"
    style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.text }}
  >
    <div style={{ color: HOMER_THEME.textMuted }}>-- sqlite3 ~/homer/data/homer.db</div>
    <AnimatePresence mode="wait">
      {phase === 0 && (
        <motion.div
          key="m0"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="space-y-1"
        >
          <div style={{ color: GREEN }}>INSERT INTO claims (ts, source, text)</div>
          <div className="pl-4" style={{ color: GREEN, opacity: 0.85 }}>
            VALUES (1714723200, 'cli', 'use React Query for caching');
          </div>
          <div className="mt-2" style={{ color: HOMER_THEME.textMuted }}>... done. [1 row]</div>
        </motion.div>
      )}
      {phase === 1 && (
        <motion.div
          key="m1"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <table className="w-full border-collapse">
            <thead style={{ color: HOMER_THEME.textMuted }} className="text-left">
              <tr>
                <th className="py-1 font-normal">TS</th>
                <th className="py-1 font-normal">SRC</th>
                <th className="py-1 font-normal">CLAIM</th>
              </tr>
            </thead>
            <tbody style={{ color: HOMER_THEME.text }}>
              <tr style={{ borderTop: `1px solid ${HOMER_THEME.divider}` }}>
                <td className="py-1" style={{ color: HOMER_THEME.textMuted }}>03:14</td>
                <td>cli</td>
                <td>node v20.12</td>
              </tr>
              <motion.tr
                initial={{ background: 'transparent' }}
                animate={{ background: HOMER_THEME.accentSoft }}
                transition={{ duration: 0.6 }}
                style={{ borderTop: `1px solid ${HOMER_THEME.divider}` }}
              >
                <td className="py-1" style={{ color: HOMER_THEME.textMuted }}>03:15</td>
                <td style={{ color: HOMER_THEME.accent }}>slack</td>
                <td>prefer pnpm over npm</td>
              </motion.tr>
              <tr style={{ borderTop: `1px solid ${HOMER_THEME.divider}` }}>
                <td className="py-1" style={{ color: HOMER_THEME.textMuted }}>03:16</td>
                <td>cli</td>
                <td>bg = #0b0a08</td>
              </tr>
            </tbody>
          </table>
        </motion.div>
      )}
      {phase === 2 && (
        <motion.div
          key="m2"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="space-y-3"
        >
          <div style={{ color: HOMER_THEME.accent }}>
            sqlite&gt; SELECT * FROM claims_fts WHERE text MATCH 'react auth';
          </div>
          <div
            className="p-2 rounded border"
            style={{
              borderColor: HOMER_THEME.accent,
              background: HOMER_THEME.accentSoft,
            }}
          >
            <div
              className="flex justify-between text-[9px] mb-1 uppercase tracking-widest"
              style={{ color: HOMER_THEME.textMuted }}
            >
              <span>created · 6 wks ago</span>
              <span>rank · 0.98</span>
            </div>
            <div style={{ color: HOMER_THEME.text }}>
              "use Supabase auth hooks in this project."
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  </div>
);

// 2) SCHEDULER — launchd-style log: START -> OK -> FAIL + Telegram toast
const SchedulerViz: React.FC<VizProps> = ({ phase }) => (
  <div
    className="p-4 text-[11px] space-y-2 h-full overflow-hidden"
    style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.text }}
  >
    <div className="flex items-center gap-2" style={{ color: HOMER_THEME.textMuted }}>
      <RefreshCw size={11} style={{ animation: 'homer-spin 4s linear infinite' }} />
      <span>launchd · com.homer.daemon [active]</span>
    </div>
    <style>{`@keyframes homer-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    <div className="space-y-1 pt-1">
      <div className="flex gap-3">
        <span style={{ color: HOMER_THEME.textMuted }}>[03:00:00]</span>
        <span style={{ color: HOMER_THEME.accent }}>memory-consolidate START</span>
      </div>
      {phase >= 1 && (
        <motion.div
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          className="flex gap-3"
        >
          <span style={{ color: HOMER_THEME.textMuted }}>[03:00:14]</span>
          <span style={{ color: GREEN }}>memory-consolidate OK · 14.2s</span>
        </motion.div>
      )}
      {phase === 2 && (
        <motion.div
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          className="space-y-1"
        >
          <div className="flex gap-3">
            <span style={{ color: HOMER_THEME.textMuted }}>[03:14:02]</span>
            <span style={{ color: RED }}>health-check FAIL · ECONNRESET</span>
          </div>
          <div className="flex gap-3">
            <span style={{ color: HOMER_THEME.textMuted }}>[03:14:03]</span>
            <span style={{ color: RED }}>retry 1/3 ... failing</span>
          </div>
          <motion.div
            initial={{ y: 12, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.25 }}
            className="mt-3 p-2 rounded flex gap-2.5 items-center border"
            style={{
              borderColor: HOMER_THEME.accent,
              background: HOMER_THEME.accentSoft,
            }}
          >
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center"
              style={{ background: HOMER_THEME.accent, color: HOMER_THEME.bg }}
            >
              <Phone size={12} />
            </div>
            <div>
              <div
                className="text-[9px] uppercase tracking-widest"
                style={{ color: HOMER_THEME.accent }}
              >
                Telegram alert
              </div>
              <div style={{ color: HOMER_THEME.text }}>paged @yj</div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  </div>
);

// 3) EXECUTORS — routing log with ticking token counter, 429, fallback retry
const ExecutorsViz: React.FC<VizProps> = ({ phase }) => {
  const reduced = useReducedMotion();
  const [tokens, setTokens] = useState(4231);
  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => {
      setTokens((t) => t + Math.floor(Math.random() * 4) + 1);
    }, 180);
    return () => clearInterval(id);
  }, [reduced]);

  return (
    <div
      className="p-4 text-[11px] h-full space-y-3 overflow-hidden"
      style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.text }}
    >
      <div
        className="flex justify-between text-[9px] uppercase tracking-widest"
        style={{ color: HOMER_THEME.textMuted }}
      >
        <span>routing log</span>
        <span>tok · {tokens.toLocaleString()}</span>
      </div>
      <div className="space-y-2">
        <div className="flex items-center gap-2.5">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: GREEN }} />
          <span style={{ color: HOMER_THEME.text }}>claude-sonnet-4</span>
          <span style={{ color: HOMER_THEME.textMuted }}>·</span>
          <span style={{ color: HOMER_THEME.textMuted }}>4.2K tok</span>
          <span style={{ color: HOMER_THEME.textMuted }}>·</span>
          <span style={{ color: HOMER_THEME.textMuted }}>820ms</span>
          <span className="ml-auto" style={{ color: GREEN }}>200 OK</span>
        </div>
        {phase >= 1 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2.5"
          >
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: GREEN }} />
            <span>gpt-5-mini</span>
            <span style={{ color: HOMER_THEME.textMuted }}>·</span>
            <span style={{ color: HOMER_THEME.textMuted }}>1.1K tok</span>
            <span style={{ color: HOMER_THEME.textMuted }}>·</span>
            <span style={{ color: HOMER_THEME.textMuted }}>450ms</span>
            <span className="ml-auto" style={{ color: GREEN }}>200 OK</span>
          </motion.div>
        )}
        {phase === 2 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-1.5"
          >
            <div className="flex items-center gap-2.5">
              <motion.span
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: RED }}
                animate={reduced ? {} : { opacity: [1, 0.4, 1] }}
                transition={{ duration: 1, repeat: Infinity }}
              />
              <span>claude-sonnet-4</span>
              <span className="ml-auto" style={{ color: RED }}>429 RATE_LIMIT</span>
            </div>
            <div
              className="flex items-center gap-2 pl-4"
              style={{
                color: HOMER_THEME.textMuted,
                borderLeft: `1px solid ${HOMER_THEME.divider}`,
              }}
            >
              <span style={{ color: HOMER_THEME.accent }}>{'↳'}</span>
              <span className="italic">retry → gpt-5</span>
              <span className="ml-auto">980ms</span>
              <span style={{ color: GREEN }}>OK</span>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
};

// 4) MCP — JSON-RPC tools/call frame fanning out to 4 named clients
const McpViz: React.FC<VizProps> = ({ phase }) => (
  <div
    className="p-4 text-[10px] h-full space-y-3 overflow-hidden"
    style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.text }}
  >
    <div
      className="p-2 rounded border"
      style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bg }}
    >
      <div
        className="mb-1 uppercase tracking-widest text-[9px]"
        style={{ color: HOMER_THEME.textMuted }}
      >
        → request
      </div>
      <div style={{ color: GREEN, lineHeight: 1.5 }}>
        {'{'}<br />
        &nbsp;&nbsp;"jsonrpc": "2.0",<br />
        &nbsp;&nbsp;"method": "tools/call",<br />
        &nbsp;&nbsp;"params": {'{ "name": "memory_search", "args": { "q": "pnpm" } }'}<br />
        {'}'}
      </div>
    </div>

    {phase >= 1 && (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="space-y-2"
      >
        <div
          className="text-center text-[9px] uppercase tracking-widest"
          style={{ color: HOMER_THEME.textMuted }}
        >
          ── fan-out · 4 clients ──
        </div>
        <div className="grid grid-cols-4 gap-1.5">
          {(['claude', 'codex', 'gemini', 'kimi'] as const).map((c, i) => {
            const isDenied = phase === 2 && c === 'kimi';
            return (
              <motion.div
                key={c}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08 * i }}
                className="px-1.5 py-1 text-center rounded border text-[9px] uppercase tracking-widest"
                style={{
                  borderColor: isDenied ? RED : HOMER_THEME.accent,
                  color: isDenied ? RED : HOMER_THEME.accent,
                  background: isDenied ? 'rgba(239,68,68,0.08)' : HOMER_THEME.accentSoft,
                }}
              >
                {c}
              </motion.div>
            );
          })}
        </div>
      </motion.div>
    )}

    {phase === 2 && (
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        className="p-2 rounded border"
        style={{ borderColor: RED, background: 'rgba(239,68,68,0.06)' }}
      >
        <div
          className="mb-1 uppercase tracking-widest text-[9px]"
          style={{ color: RED }}
        >
          ← kimi · response
        </div>
        <div style={{ color: RED, lineHeight: 1.5 }}>
          {'{ "error": { "code": -32001, "message": "auth: deny" } }'}
        </div>
      </motion.div>
    )}
  </div>
);

// 5) VOICE — typewriter transcript + first_audio_out latency, structured claim
const VoiceViz: React.FC<VizProps> = ({ phase }) => {
  const reduced = useReducedMotion();
  const fullText = "let's switch the auth layer to Supabase before shipping";
  const [text, setText] = useState(reduced ? fullText : '');
  useEffect(() => {
    if (reduced) {
      setText(fullText);
      return;
    }
    let i = 0;
    setText('');
    const id = setInterval(() => {
      i += 1;
      setText(fullText.slice(0, i));
      if (i >= fullText.length) {
        clearInterval(id);
      }
    }, 45);
    return () => clearInterval(id);
  }, [phase, reduced]);

  return (
    <div
      className="p-4 text-[11px] h-full space-y-4 overflow-hidden"
      style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.text }}
    >
      <div className="flex items-center gap-3">
        <div className="flex gap-1 items-end h-6">
          {[0, 1, 2, 3, 4, 5, 6].map((i) => (
            <motion.div
              key={i}
              animate={reduced ? { height: 10 } : { height: [6, 22, 6] }}
              transition={{ repeat: Infinity, duration: 0.9, delay: i * 0.08 }}
              className="w-[3px] rounded-full"
              style={{ background: HOMER_THEME.accent }}
            />
          ))}
        </div>
        <div className="flex flex-col leading-tight">
          <span
            className="text-[9px] uppercase tracking-widest"
            style={{ color: HOMER_THEME.textMuted }}
          >
            first_audio_out
          </span>
          <span style={{ color: HOMER_THEME.accent }}>
            380<span className="text-[9px] opacity-60"> ms</span>
          </span>
        </div>
      </div>

      <div
        className="p-2.5 rounded border min-h-[50px]"
        style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bg }}
      >
        <span style={{ color: HOMER_THEME.text }}>"{text}"</span>
        <motion.span
          animate={reduced ? {} : { opacity: [1, 0] }}
          transition={{ duration: 0.7, repeat: Infinity }}
          className="inline-block w-[6px] h-[12px] ml-1 align-middle"
          style={{ background: HOMER_THEME.accent }}
        />
      </div>

      {phase === 2 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-2 border-l-2"
          style={{
            borderColor: HOMER_THEME.accent,
            background: HOMER_THEME.accentSoft,
          }}
        >
          <div
            className="text-[9px] uppercase tracking-widest mb-1"
            style={{ color: HOMER_THEME.accent }}
          >
            structured claim
          </div>
          <div className="text-[10px]" style={{ color: HOMER_THEME.text }}>
            {'{ type: "decision", text: "use Supabase auth" }'}
          </div>
        </motion.div>
      )}
    </div>
  );
};

// 6) WEB UI — phone -> desktop -> PDF render w/ "tunneled" status badge
const WebViz: React.FC<VizProps> = ({ phase }) => (
  <div className="p-4 flex flex-col items-center justify-center h-full relative overflow-hidden">
    <div className="absolute top-2 right-3 flex items-center gap-1.5 z-10">
      <motion.span
        animate={{ opacity: [1, 0.45, 1] }}
        transition={{ duration: 1.6, repeat: Infinity }}
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: GREEN }}
      />
      <span
        className="text-[9px] uppercase tracking-widest"
        style={{ fontFamily: HOMER_THEME.fontMono, color: GREEN }}
      >
        tunneled
      </span>
    </div>

    <AnimatePresence mode="wait">
      {phase === 0 && (
        <motion.div
          key="phone"
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.92 }}
          transition={{ duration: 0.35 }}
          className="w-28 h-48 rounded-2xl p-2 border-2"
          style={{
            borderColor: HOMER_THEME.accent,
            background: HOMER_THEME.bgSoft,
          }}
        >
          <div
            className="w-10 h-1 rounded-full mx-auto mb-3"
            style={{ background: HOMER_THEME.divider }}
          />
          <div className="space-y-1.5">
            <div className="h-1.5 w-full rounded" style={{ background: HOMER_THEME.divider }} />
            <div
              className="h-6 w-full rounded flex items-center px-2 gap-1.5"
              style={{ background: HOMER_THEME.accentSoft }}
            >
              <span className="w-1 h-1 rounded-full" style={{ background: GREEN }} />
              <span
                className="block h-1 flex-1 rounded"
                style={{ background: HOMER_THEME.accent, opacity: 0.5 }}
              />
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              <div className="h-7 rounded" style={{ background: HOMER_THEME.divider }} />
              <div className="h-7 rounded" style={{ background: HOMER_THEME.divider }} />
            </div>
            <div className="h-1.5 w-3/4 rounded" style={{ background: HOMER_THEME.divider }} />
          </div>
        </motion.div>
      )}
      {phase === 1 && (
        <motion.div
          key="desktop"
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.92 }}
          transition={{ duration: 0.35 }}
          className="w-56 h-36 rounded-md p-2 border"
          style={{
            borderColor: HOMER_THEME.accent,
            background: HOMER_THEME.bgSoft,
          }}
        >
          <div className="flex gap-1 mb-2">
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'rgba(239,68,68,0.5)' }} />
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'rgba(234,179,8,0.5)' }} />
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'rgba(34,197,94,0.5)' }} />
          </div>
          <div className="flex gap-2 mb-2">
            <div className="w-7 h-7 rounded" style={{ background: HOMER_THEME.accentSoft }} />
            <div className="space-y-1 flex-1">
              <div className="h-1.5 w-1/2 rounded" style={{ background: HOMER_THEME.divider }} />
              <div className="h-1.5 w-1/3 rounded" style={{ background: HOMER_THEME.divider }} />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-1.5">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-10 rounded border"
                style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bg }}
              />
            ))}
          </div>
        </motion.div>
      )}
      {phase === 2 && (
        <motion.div
          key="pdf"
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.92 }}
          transition={{ duration: 0.35 }}
          className="w-32 h-44 rounded p-3 flex flex-col gap-1.5 shadow-lg"
          style={{ background: HOMER_THEME.text }}
        >
          <div className="h-2.5 w-3/4 rounded" style={{ background: 'rgba(11,10,8,0.65)' }} />
          <div className="h-1 w-full rounded" style={{ background: 'rgba(11,10,8,0.18)' }} />
          <div className="h-1 w-full rounded" style={{ background: 'rgba(11,10,8,0.18)' }} />
          <div className="h-1 w-2/3 rounded" style={{ background: 'rgba(11,10,8,0.18)' }} />
          <div
            className="mt-2 h-14 w-full rounded border-2 border-dashed flex items-center justify-center"
            style={{ borderColor: 'rgba(11,10,8,0.18)' }}
          >
            <span
              className="text-[8px] uppercase tracking-widest"
              style={{
                color: 'rgba(11,10,8,0.55)',
                fontFamily: HOMER_THEME.fontMono,
              }}
            >
              chart.pdf
            </span>
          </div>
          <div className="mt-auto flex justify-between">
            <div className="h-1 w-8 rounded" style={{ background: 'rgba(11,10,8,0.18)' }} />
            <div className="h-1 w-8 rounded" style={{ background: 'rgba(11,10,8,0.18)' }} />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  </div>
);

/* -------------------------------------------------------------------------- */
/*                              SHARED PRIMITIVES                             */
/* -------------------------------------------------------------------------- */

interface BulletColumnProps {
  heading: string;
  items: string[];
  activeIndex?: number;
  syncToPhase?: boolean;
}

const BulletColumn: React.FC<BulletColumnProps> = ({
  heading,
  items,
  activeIndex,
  syncToPhase,
}) => (
  <div>
    <div
      className="text-[10px] uppercase tracking-[0.24em] mb-2"
      style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
    >
      {heading}
    </div>
    <ul className="space-y-1.5">
      {items.map((item, i) => {
        const dim = syncToPhase && activeIndex !== undefined && activeIndex !== i;
        return (
          <li
            key={i}
            className="flex gap-2.5 items-start text-[12px] transition-opacity duration-300"
            style={{
              fontFamily: HOMER_THEME.fontMono,
              color: HOMER_THEME.text,
              opacity: dim ? 0.32 : 1,
            }}
          >
            <span
              className="mt-1 shrink-0 w-1 h-1 rounded-full transition-colors duration-300"
              style={{ background: dim ? HOMER_THEME.divider : HOMER_THEME.accent }}
            />
            <span>{item}</span>
          </li>
        );
      })}
    </ul>
  </div>
);

/* -------------------------------------------------------------------------- */
/*                                MAIN SECTION                                */
/* -------------------------------------------------------------------------- */

export const Architecture: React.FC = () => {
  const [activeId, setActiveId] = useState<SubsystemId>('memory');
  const [phase, setPhase] = useState(0);
  const reduced = useReducedMotion();

  // Reset phase whenever the user switches subsystem.
  useEffect(() => {
    setPhase(0);
  }, [activeId]);

  // 4 s phase loop — frozen at phase 0 if user prefers reduced motion.
  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => {
      setPhase((p) => (p + 1) % 3);
    }, 4000);
    return () => clearInterval(id);
  }, [activeId, reduced]);

  const current = useMemo(
    () => SUBSYSTEMS.find((s) => s.id === activeId) ?? SUBSYSTEMS[0],
    [activeId],
  );

  const renderViz = () => {
    switch (activeId) {
      case 'memory':
        return <MemoryViz phase={phase} />;
      case 'scheduler':
        return <SchedulerViz phase={phase} />;
      case 'executors':
        return <ExecutorsViz phase={phase} />;
      case 'mcp':
        return <McpViz phase={phase} />;
      case 'voice':
        return <VoiceViz phase={phase} />;
      case 'web':
        return <WebViz phase={phase} />;
    }
  };

  return (
    <SectionShell
      id="architecture"
      eyebrow="architecture"
      title="Six subsystems, one loop."
      subtitle="Each panel is a real subsystem in production. Click any of them to watch its actual telemetry — logs, SQL, JSON-RPC, transcripts — and read what it does for me, what it could do for your team."
    >
      <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-4 md:gap-6">
        {/* LEFT — vertical card list */}
        <div className="flex flex-col gap-2">
          {SUBSYSTEMS.map((s) => {
            const isActive = s.id === activeId;
            const Icon = s.icon;
            return (
              <button
                key={s.id}
                onClick={() => setActiveId(s.id)}
                className="text-left p-3 rounded-md border transition-all relative flex items-center gap-3"
                style={{
                  borderColor: isActive ? HOMER_THEME.accent : HOMER_THEME.divider,
                  background: isActive ? HOMER_THEME.accentSoft : HOMER_THEME.bgSoft,
                  opacity: isActive ? 1 : 0.78,
                }}
                aria-pressed={isActive}
              >
                <Icon
                  size={16}
                  strokeWidth={1.5}
                  color={isActive ? HOMER_THEME.accent : HOMER_THEME.textMuted}
                />
                <span
                  className="text-[10px] tracking-[0.24em] uppercase"
                  style={{
                    fontFamily: HOMER_THEME.fontMono,
                    color: isActive ? HOMER_THEME.accent : HOMER_THEME.textMuted,
                  }}
                >
                  {s.label}
                </span>
                <ChevronRight
                  size={12}
                  className="ml-auto"
                  style={{
                    color: isActive ? HOMER_THEME.accent : HOMER_THEME.textMuted,
                    transform: isActive ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s',
                  }}
                />
                {isActive && (
                  <motion.span
                    layoutId="arch-active-rail"
                    className="absolute left-0 top-2 bottom-2 w-0.5 rounded-r"
                    style={{ background: HOMER_THEME.accent }}
                    transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                  />
                )}
              </button>
            );
          })}
        </div>

        {/* RIGHT — terminal-styled detail panel */}
        <div
          className="rounded-lg border overflow-hidden md:sticky md:top-6 md:self-start"
          style={{
            borderColor: HOMER_THEME.divider,
            background: HOMER_THEME.bgSoft,
          }}
        >
          <TerminalChrome title={`~/homer/${current.id}.log`} />
          <AnimatePresence mode="wait">
            <motion.div
              key={current.id}
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="grid grid-cols-1 lg:grid-cols-2">
                {/* Viz column — terminal-flavored, dominant */}
                <div
                  className="h-56 md:h-72 lg:h-80 lg:border-r border-b lg:border-b-0"
                  style={{
                    borderColor: HOMER_THEME.divider,
                    background: HOMER_THEME.bg,
                  }}
                >
                  {renderViz()}
                </div>

                {/* Copy column — Built-for-me bullets sync to viz phase */}
                <div className="p-5 md:p-6 space-y-5">
                  <div>
                    <h3
                      className="text-xl md:text-2xl mb-1.5 leading-tight"
                      style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
                    >
                      {current.headline}
                    </h3>
                    <div className="flex gap-x-3 gap-y-1 flex-wrap">
                      {current.receipts.map((r) => (
                        <span
                          key={r}
                          className="text-[10px] uppercase tracking-widest"
                          style={{
                            fontFamily: HOMER_THEME.fontMono,
                            color: HOMER_THEME.accent,
                          }}
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  </div>

                  <BulletColumn
                    heading="Built for me"
                    items={current.builtBullets}
                    activeIndex={phase}
                    syncToPhase
                  />
                  <BulletColumn
                    heading="Deployed for your team"
                    items={current.teamBullets}
                  />
                </div>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </SectionShell>
  );
};

export default Architecture;
