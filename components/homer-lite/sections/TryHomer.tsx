import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity,
  Brain,
  Database,
  ChevronRight,
  Terminal,
  Scissors,
  Clock,
  Phone,
  PhoneOutgoing,
  GitMerge,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

// Function: TryHomer — "The Telemetry Trace" (Gemini 3.1 Pro spec, 2026-05-03).
// Two-pane interface for hiring managers / recruiters:
//   • Left:  always-on telemetry stream — proves the daemon is alive while they read.
//   • Right: archived operations they can drill into to see Homer's actual orchestration
//            traces. Each trace expands into a step-by-step timeline with the executor,
//            duration, and raw payload for that step.
//
// Design rationale (from gemini-3.1-pro-preview redesign brief):
//   Senior engineering leaders have buzzword fatigue and zero patience for chat UIs.
//   They care about observability + multi-step reasoning + production maturity.
//   The telemetry stream signals "this thing is running RIGHT NOW," and the traces
//   prove the candidate thinks in systems, not features.
//
// Reference: ~/homer/output/gemini/try-homer-redesign-2026-05-03.md

interface LogEntry { id: string; time: string; process: string; message: string; tone: 'info' | 'ok' | 'work'; }
interface TraceStep { title: string; agent: string; duration: string; detail: string; payload?: string; icon: React.ReactNode; }
interface Trace { id: string; title: string; description: string; impact: string; steps: TraceStep[]; }

// --- Archived operations ----------------------------------------------------
// Three traces chosen to span the system's range: self-maintenance,
// data pipeline, applied automation. Each step is plausible and
// reads like a real run log.
const TRACES: Trace[] = [
  {
    id: 'prune',
    title: 'Self-pruning · removed an unused skill',
    description:
      "Homer noticed a skill it had stopped invoking and proposed deletion. Approved via Telegram, executed in 3 steps.",
    impact: 'context window saved · 1.2k tokens / call',
    steps: [
      {
        title: 'cron · weekly_skill_audit',
        agent: 'homer.core',
        duration: '45ms',
        detail:
          'Scanned skill_invocations table for trailing 30 days. Skill `legacy_yt_scraper` had 0 fires; flagged as candidate for deletion.',
        payload:
          '{"skill":"legacy_yt_scraper","invocations_30d":0,"last_seen":"2026-04-02","superseded_by":"yt_dlp_extractor"}',
        icon: <Database size={14} />,
      },
      {
        title: 'reasoning · should_we_delete',
        agent: 'codex (gpt-5.5 · medium)',
        duration: '2.1s',
        detail:
          'Compared usage signal vs. retention cost. Found `yt_dlp_extractor` already covers all known invocation patterns. Proposed deletion + Telegram approval request.',
        icon: <Brain size={14} />,
      },
      {
        title: 'execution · fs_remove + index_update',
        agent: 'homer.core',
        duration: '12ms',
        detail:
          'Removed ~/.claude/skills/legacy_yt_scraper/. Updated skills_index. Logged audit row. Notified user via Telegram with diff.',
        icon: <Scissors size={14} />,
      },
    ],
  },
  {
    id: 'memory',
    title: 'Nightly memory consolidation · 12k claims',
    description:
      'The 23:00 batch job that compresses ephemeral session context into durable claims and rebuilds the FTS5 + vector indices.',
    impact: 'recall latency · -38% · Sundays',
    steps: [
      {
        title: 'fetch · session_fragments',
        agent: 'sqlite.fts5',
        duration: '110ms',
        detail:
          'Pulled 142 session fragments from the trailing 24h. Filtered by token-count > 60 to drop trivial chatter.',
        icon: <Database size={14} />,
      },
      {
        title: 'extract · durable_claims',
        agent: 'gemini-3-flash',
        duration: '4.5s',
        detail:
          'Extracted 12 high-confidence claims (e.g. "Yanqing prefers Framer Motion springs over CSS transitions for hero animations").',
        payload:
          '{"new_claims":12,"superseded":3,"conflicts":1,"avg_confidence":0.84}',
        icon: <Sparkles size={14} />,
      },
      {
        title: 'merge · vector_upsert',
        agent: 'embedding.local',
        duration: '820ms',
        detail:
          'Generated 1024-dim embeddings for new claims. Upserted to vss0. Fired conflict-guard on 1 row; demoted confidence and routed to HITL.',
        icon: <Activity size={14} />,
      },
      {
        title: 'archive · daily_log',
        agent: 'homer.core',
        duration: '38ms',
        detail:
          'Wrote ~/memory/daily/2026-05-02.md. Pushed to Azure Blob. Cleared session_fragments older than 7 days.',
        icon: <Clock size={14} />,
      },
    ],
  },
  {
    id: 'voice-hitl',
    title: 'Voice HITL · Homer rang me to resolve a memory conflict',
    description:
      'Nightly consolidation found two contradicting claims about my coffee preference. Confidence delta crossed the HITL threshold, and the policy escalated to voice. Homer dialed me, asked one question, persisted the answer.',
    impact: 'one ring · 8.4s call · conflict resolved',
    steps: [
      {
        title: 'detect · conflict_guard',
        agent: 'sqlite + memory.consolidator',
        duration: '24ms',
        detail:
          'Two claims about the same predicate disagreed. Confidence delta = 0.41 (threshold 0.30). Older claim cited from chat (conf 0.62), newer one from a calendar event description (conf 0.81). Tie too close to auto-supersede.',
        payload:
          '{"predicate":"prefers.coffee.style","claim_a":"cl_61204","claim_b":"cl_84119","delta":0.41,"action":"escalate.hitl"}',
        icon: <GitMerge size={14} />,
      },
      {
        title: 'route · notification_policy',
        agent: 'homer.core',
        duration: '6ms',
        detail:
          'Notification router applied policy: severity = blocking, hours = 22:00–07:00, channels = [voice, telegram]. Telegram suppressed by quiet-hours rule. Voice promoted to primary channel.',
        icon: <ShieldCheck size={14} />,
      },
      {
        title: 'dial · outbound_call',
        agent: 'twilio + elevenlabs.managed_agent',
        duration: '1.1s',
        detail:
          'Twilio outbound to caller_id_owner. ElevenLabs Managed Agent attached as SIP participant; STT + TTS streamed full-duplex over WebSocket. Pre-roll TTS: "One question, then I\'ll let you sleep."',
        icon: <PhoneOutgoing size={14} />,
      },
      {
        title: 'turn · clarify',
        agent: 'managed_agent (single-turn policy)',
        duration: '8.4s',
        detail:
          'Read both candidate claims aloud as A/B. Listener said "the second one." Confidence post-disambiguation: 0.97. Hung up after one confirmation token. Total wall time on the line: 8.4s.',
        icon: <Phone size={14} />,
      },
      {
        title: 'persist · supersede + reindex',
        agent: 'homer.core',
        duration: '92ms',
        detail:
          'Updated knowledge_claims: cl_61204.superseded_by = cl_84119. Re-embedded both rows. Wrote audit row to call_summaries with a short transcript reference.',
        icon: <Database size={14} />,
      },
    ],
  },
];

// --- Telemetry generator ---------------------------------------------------
// Generates a steady drip of plausible log lines. Lines are sampled from a
// small vocabulary so the stream never repeats too obviously, and the rate
// is jittered so it doesn't feel like a metronome.
const PROCS = [
  { name: 'mem_gc', tone: 'info' as const, msgs: ['compacted vss0', 'evicted 14 stale rows', 'idle', 'scheduled'] },
  { name: 'inbox_scan', tone: 'work' as const, msgs: ['2 new urls queued', 'youtube/3 medium/1', 'paywall_bypass ok'] },
  { name: 'sched_tick', tone: 'info' as const, msgs: ['next: portfolio_health (+4m)', 'next: news_brief (+27m)', '47 jobs active'] },
  { name: 'tg_relay', tone: 'ok' as const, msgs: ['1 outbound', 'hitl approved', 'idle'] },
  { name: 'mcp.bridge', tone: 'info' as const, msgs: ['memory_search · 12 hits', 'memory_context · 4ms', 'idle'] },
  { name: 'voice.eleven', tone: 'work' as const, msgs: ['ws warm', 'turn_complete', 'idle'] },
  { name: 'health_chk', tone: 'ok' as const, msgs: ['portfolio-api 200', 'tunnel ok', 'mac_mini cpu 4%'] },
  { name: 'cli_runner', tone: 'work' as const, msgs: ['claude · pending(1)', 'codex · running(2.1s)', 'gemini · ok'] },
];

const makeLog = (): LogEntry => {
  const proc = PROCS[Math.floor(Math.random() * PROCS.length)];
  const msg = proc.msgs[Math.floor(Math.random() * proc.msgs.length)];
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    time: new Date().toLocaleTimeString('en-US', { hour12: false }),
    process: proc.name,
    message: msg,
    tone: proc.tone,
  };
};

const TONE_COLOR: Record<LogEntry['tone'], string> = {
  info: HOMER_THEME.textMuted,
  ok: '#86efac',
  work: HOMER_THEME.accent,
};

// --- Inner step row --------------------------------------------------------
const StepRow: React.FC<{ step: TraceStep; idx: number; total: number; expanded: boolean; onToggle: () => void }> = ({
  step,
  idx,
  total,
  expanded,
  onToggle,
}) => (
  <div className="flex gap-3 md:gap-4">
    {/* Timeline rail */}
    <div className="flex flex-col items-center mt-1 shrink-0">
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center border transition-colors"
        style={{
          borderColor: expanded ? HOMER_THEME.accent : HOMER_THEME.divider,
          background: HOMER_THEME.bg,
          color: expanded ? HOMER_THEME.accent : HOMER_THEME.textMuted,
        }}
      >
        {step.icon}
      </div>
      {idx !== total - 1 && (
        <div className="w-px flex-1 my-1.5 min-h-[28px]" style={{ background: HOMER_THEME.divider }} />
      )}
    </div>

    {/* Step body */}
    <div className="flex-1 min-w-0 pb-4">
      <button
        onClick={onToggle}
        className="w-full min-h-[44px] text-left flex items-center justify-between gap-2 md:gap-3 p-2 rounded"
      >
        <span
          className="text-[13px] leading-snug min-w-0 flex-1 break-words"
          style={{
            fontFamily: HOMER_THEME.fontMono,
            color: expanded ? HOMER_THEME.text : HOMER_THEME.textMuted,
          }}
        >
          {step.title}
        </span>
        <span
          className="text-[10px] tabular-nums shrink-0"
          style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
        >
          {step.duration}
        </span>
      </button>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="detail"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div
              className="mt-2 rounded border p-3 space-y-2"
              style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bg }}
            >
              <div className="flex justify-between items-center">
                <span
                  className="text-[9px] tracking-[0.24em] uppercase leading-snug break-words [overflow-wrap:anywhere]"
                  style={{ color: HOMER_THEME.accent, fontFamily: HOMER_THEME.fontMono }}
                >
                  executor · {step.agent}
                </span>
              </div>
              <div className="text-sm leading-relaxed" style={{ color: HOMER_THEME.textMuted }}>
                {step.detail}
              </div>
              {step.payload && (
                <pre
                  className="mt-1 p-2 text-[10.5px] leading-relaxed overflow-x-auto rounded border"
                  style={{
                    background: '#08070a',
                    borderColor: HOMER_THEME.divider,
                    color: HOMER_THEME.text,
                    fontFamily: HOMER_THEME.fontMono,
                  }}
                >
                  {step.payload}
                </pre>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  </div>
);

// --- Main section ----------------------------------------------------------
export const TryHomer: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [expandedStep, setExpandedStep] = useState<number | null>(0);
  const [paused, setPaused] = useState(false);

  const active = useMemo(() => TRACES.find((t) => t.id === activeId) ?? null, [activeId]);
  const tickerRef = useRef<HTMLDivElement>(null);

  // Boot the telemetry ticker
  useEffect(() => {
    setLogs(Array.from({ length: 6 }, makeLog));
  }, []);

  useEffect(() => {
    if (paused) return;
    let cancel = false;
    const tick = () => {
      if (cancel) return;
      setLogs((prev) => {
        const next = [...prev, makeLog()];
        return next.length > 14 ? next.slice(next.length - 14) : next;
      });
      // Jitter the cadence so it doesn't feel like a metronome
      const next = 1700 + Math.random() * 1800;
      timer = setTimeout(tick, next);
    };
    let timer = setTimeout(tick, 1400);
    return () => {
      cancel = true;
      clearTimeout(timer);
    };
  }, [paused]);

  // Keep ticker scrolled to bottom
  useEffect(() => {
    const el = tickerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [logs]);

  const openTrace = (id: string) => {
    setActiveId(id);
    setExpandedStep(0);
  };

  return (
    <SectionShell
      id="try"
      eyebrow="production system"
      title="Not a chat interface."
      subtitle="Homer is a headless daemon running on a Mac Mini. Five executors, one memory layer, ~50 scheduled jobs. Below is a live telemetry slice and three real archived operations you can step through."
    >
      <div
        className="grid grid-cols-1 md:grid-cols-[minmax(0,_1fr)_minmax(0,_1.7fr)] gap-4 md:gap-5 mt-2"
        style={{ minHeight: '0' }}
      >
        {/* --- Left pane: live telemetry --- */}
        <div
          className="rounded-lg border overflow-hidden flex flex-col"
          style={{
            borderColor: HOMER_THEME.divider,
            background: HOMER_THEME.bgSoft,
            // Mobile clamp so the ticker doesn't dominate; desktop matches the right pane
            height: 'clamp(220px, 36vh, 600px)',
          }}
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
        >
          {/* header */}
          <div
            className="flex items-center justify-between gap-2 px-4 py-2.5 border-b"
            style={{ borderColor: HOMER_THEME.divider, background: 'rgba(0,0,0,0.25)' }}
          >
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-green-400" />
              </span>
              <span
                className="text-[10px] tracking-[0.24em] uppercase"
                style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
              >
                telemetry · live
              </span>
            </div>
            <span
              className="text-[10px]"
              style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
            >
              {paused ? 'paused' : 'streaming'}
            </span>
          </div>

          {/* ticker */}
          <div
            ref={tickerRef}
            className="flex-1 overflow-y-auto px-4 py-3 relative"
            style={{ scrollbarWidth: 'thin' }}
          >
            <div
              className="absolute top-0 left-0 right-0 h-8 pointer-events-none z-10"
              style={{ background: `linear-gradient(${HOMER_THEME.bgSoft}, transparent)` }}
            />
            <AnimatePresence initial={false}>
              {logs.map((log) => (
                <motion.div
                  key={log.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                  transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                  className="text-[11px] leading-[1.7] mb-0.5"
                  style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
                >
                  <span style={{ opacity: 0.55 }}>[{log.time}]</span>{' '}
                  <span style={{ color: TONE_COLOR[log.tone] }}>{log.process}</span>
                  <span style={{ opacity: 0.55 }}> :: </span>
                  <span style={{ color: HOMER_THEME.text }}>{log.message}</span>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          <div
            className="px-4 py-2 border-t text-[10px] flex items-center justify-between"
            style={{
              borderColor: HOMER_THEME.divider,
              fontFamily: HOMER_THEME.fontMono,
              color: HOMER_THEME.textMuted,
            }}
          >
            <span>hover to pause</span>
            <span>{logs.length} / 14 lines</span>
          </div>
        </div>

        {/* --- Right pane: archived operations / trace timeline --- */}
        <div
          className="rounded-lg border overflow-hidden flex flex-col"
          style={{
            borderColor: HOMER_THEME.divider,
            background: HOMER_THEME.bgSoft,
            // Match left pane on mobile but allow growth on desktop
            minHeight: 'clamp(420px, 60vh, 600px)',
          }}
        >
          {/* header */}
          <div
            className="flex flex-wrap items-center gap-x-2 gap-y-1 px-4 md:px-5 py-2.5 border-b"
            style={{ borderColor: HOMER_THEME.divider, background: 'rgba(0,0,0,0.25)' }}
          >
            <Terminal size={13} style={{ color: HOMER_THEME.accent }} />
            <span
              className="text-[10px] tracking-[0.24em] uppercase"
              style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
            >
              archived operations
            </span>
            <span
              className="ml-0 sm:ml-auto text-[10px]"
              style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
            >
              {active ? '1 trace open' : `${TRACES.length} traces · click to inspect`}
            </span>
          </div>

          <div className="flex-1 p-4 md:p-6 overflow-y-auto">
            <AnimatePresence mode="wait">
              {!active ? (
                <motion.div
                  key="index"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="flex flex-col gap-3"
                >
                  <p
                    className="text-sm leading-relaxed mb-2 max-w-xl"
                    style={{ color: HOMER_THEME.textMuted }}
                  >
                    Pick a recent autonomous operation. Each step expands into the executor it ran on,
                    the duration, and the raw payload it emitted.
                  </p>

                  {TRACES.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => openTrace(t.id)}
                      className="group text-left p-4 rounded-md border transition-all hover:bg-white/[0.02] min-h-[44px]"
                      style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bg }}
                    >
                      <div className="flex items-start justify-between gap-3 mb-1.5">
                        <div
                          className="text-sm leading-snug min-w-0"
                          style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
                        >
                          {t.title}
                        </div>
                        <ChevronRight
                          size={14}
                          className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                          style={{ color: HOMER_THEME.accent }}
                        />
                      </div>
                      <div
                        className="text-sm leading-snug mb-2"
                        style={{ color: HOMER_THEME.textMuted }}
                      >
                        {t.description}
                      </div>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px]" style={{ fontFamily: HOMER_THEME.fontMono }}>
                        <span style={{ color: HOMER_THEME.accent }}>{t.steps.length} steps</span>
                        <span style={{ color: HOMER_THEME.textMuted }}>·</span>
                        <span style={{ color: HOMER_THEME.textMuted }}>{t.impact}</span>
                      </div>
                    </button>
                  ))}
                </motion.div>
              ) : (
                <motion.div
                  key={active.id}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
                  className="flex flex-col h-full"
                >
                  <button
                    onClick={() => setActiveId(null)}
                    className="text-[11px] mb-5 inline-flex min-h-[44px] items-center gap-1 self-start p-2 -ml-2 rounded hover:underline"
                    style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
                  >
                    ← back to index
                  </button>
                  <h3
                    className="text-xl md:text-2xl mb-2 leading-tight"
                    style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
                  >
                    {active.title}
                  </h3>
                  <p
                    className="text-sm leading-relaxed pb-4 mb-5 border-b"
                    style={{ color: HOMER_THEME.textMuted, borderColor: HOMER_THEME.divider }}
                  >
                    {active.description}
                  </p>

                  <div>
                    {active.steps.map((step, idx) => (
                      <StepRow
                        key={idx}
                        step={step}
                        idx={idx}
                        total={active.steps.length}
                        expanded={expandedStep === idx}
                        onToggle={() => setExpandedStep(expandedStep === idx ? null : idx)}
                      />
                    ))}
                  </div>

                  <div
                    className="mt-4 pt-4 border-t flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between text-[10px]"
                    style={{
                      borderColor: HOMER_THEME.divider,
                      fontFamily: HOMER_THEME.fontMono,
                      color: HOMER_THEME.textMuted,
                    }}
                  >
                    <span>impact · {active.impact}</span>
                    <span>{active.steps.length} steps · click to expand</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      <p
        className="mt-5 text-[11px]"
        style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
      >
        public-safe slice · payloads are real shape, content is sanitized for portfolio view.
      </p>
    </SectionShell>
  );
};

export default TryHomer;
