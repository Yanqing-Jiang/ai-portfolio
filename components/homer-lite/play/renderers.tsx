import React from 'react';
import { HOMER_THEME } from '../theme';
import type {
  McpCallData,
  McpListData,
  MemoryExtractData,
  MemorySearchData,
  PlayEnvelope,
  SchedulerData,
  VoiceData,
  WebActivityData,
} from './types';
import { AudioClip } from './AudioClip';

// Result renderers for the phase-1 tabs. Each takes the full envelope so it
// can show receipts (source, observed_at) alongside `data`.

const OK = '#86efac';
const WARN = '#f5cf94';
const BAD = '#ef6f6f';
const PURPLE = '#c4b5fd';

const Row: React.FC<{ pill: React.ReactNode; pillColor: string; right?: React.ReactNode; children: React.ReactNode }> = ({
  pill,
  pillColor,
  right,
  children,
}) => (
  <div
    className="grid items-center gap-2.5 rounded-md px-2.5 py-2 text-[12px]"
    style={{
      gridTemplateColumns: 'auto 1fr auto',
      fontFamily: HOMER_THEME.fontMono,
      background: '#0a0908',
      border: `1px solid ${HOMER_THEME.divider}`,
    }}
  >
    <span
      className="px-1.5 py-0.5 rounded text-[10px] uppercase tracking-[0.12em] whitespace-nowrap"
      style={{ color: pillColor, border: `1px solid ${pillColor}` }}
    >
      {pill}
    </span>
    <span style={{ color: HOMER_THEME.text }}>{children}</span>
    <span className="whitespace-nowrap" style={{ color: HOMER_THEME.textMuted }}>
      {right}
    </span>
  </div>
);

const KV: React.FC<{ items: [string, React.ReactNode][] }> = ({ items }) => (
  <div className="flex flex-wrap gap-x-3.5 gap-y-1 mt-2 text-[11px]" style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}>
    {items.map(([k, v]) => (
      <span key={k}>
        {k} <b className="font-medium tabular-nums" style={{ color: HOMER_THEME.text }}>{v}</b>
      </span>
    ))}
  </div>
);

const Receipt: React.FC<{ items: string[] }> = ({ items }) => (
  <div className="flex flex-wrap gap-x-3.5 gap-y-1 mt-1.5 text-[10.5px]" style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}>
    {items.map((i) => (
      <span key={i}>
        <span style={{ color: OK }}>✓</span> {i}
      </span>
    ))}
  </div>
);

const statusColor = (s: string) => (s === 'candidate' ? WARN : s === 'archived' ? PURPLE : OK);
const fmt = (n: number | null | undefined, d = 4) => (typeof n === 'number' && Number.isFinite(n) ? n.toFixed(d) : '—');
const ago = (iso: string | null | undefined) => {
  if (!iso) return '—';
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms)) return iso;
  const abs = Math.abs(ms);
  const unit = abs < 60_000 ? [Math.round(abs / 1000), 's'] : abs < 3_600_000 ? [Math.round(abs / 60_000), 'm'] : abs < 86_400_000 ? [Math.round(abs / 3_600_000), 'h'] : [Math.round(abs / 86_400_000), 'd'];
  return ms >= 0 ? `${unit[0]}${unit[1]} ago` : `in ${unit[0]}${unit[1]}`;
};

// --- Memory ---------------------------------------------------------------
export const renderMemory = (env: PlayEnvelope<MemorySearchData | MemoryExtractData>) => {
  if (env.action === 'extract_dry_run') {
    const d = env.data as MemoryExtractData;
    return (
      <div>
        <p className="mb-2">
          Extractor dry-run — <span style={{ color: HOMER_THEME.accent }}>{d.candidates.length} candidate{d.candidates.length === 1 ? '' : 's'}</span>, checked against the public corpus.
        </p>
        <div className="grid gap-1.5">
          {d.candidates.map((c) => (
            <React.Fragment key={c.candidate_id}>
              <Row pill={c.claim_type} pillColor={c.route.decision === 'dropped_noise' ? BAD : WARN} right={`conf ${fmt(c.confidence, 2)}`}>
                <span style={{ textDecoration: c.route.decision === 'dropped_noise' ? 'line-through' : undefined, opacity: c.route.decision === 'dropped_noise' ? 0.65 : 1 }}>
                  {c.content}
                </span>
              </Row>
              {c.matches.map((m) => (
                <Row key={m.public_claim_id} pill={`${m.relation.replace(/_/g, ' ')} ${fmt(m.cosine, 2)}`} pillColor={m.relation === 'possible_supersede' ? BAD : WARN} right={c.route.decision.replace(/_/g, ' ')}>
                  <span style={{ color: HOMER_THEME.textMuted }}>↳ existing: “{m.content}”</span>
                </Row>
              ))}
            </React.Fragment>
          ))}
          {d.candidates.length === 0 && <span style={{ color: HOMER_THEME.textMuted }}>Nothing worth remembering in that — the extractor dropped it as noise.</span>}
        </div>
        <KV items={[['tier', 'passive'], ['would_persist', 'false'], ['writes', String(d.policy.writes_attempted)], ['extractor', d.extractor.name]]} />
        <Receipt items={['real extractor prompt', `real conflict guard (cos ≥ ${d.policy.conflict_threshold})`, 'nothing stored']} />
      </div>
    );
  }
  const d = env.data as MemorySearchData;
  return (
    <div>
      <p className="mb-2">Top hits from the hybrid index (FTS + vector, fused with RRF):</p>
      <div className="grid gap-1.5">
        {d.results.map((h) => (
          <Row key={h.id} pill={h.status} pillColor={statusColor(h.status)} right={fmt(h.trace.final_score)}>
            {h.content}
          </Row>
        ))}
        {d.results.length === 0 && <span style={{ color: HOMER_THEME.textMuted }}>No claims matched.</span>}
      </div>
      <KV
        items={[
          ['corpus', d.meta.corpus_size],
          ['legs', d.meta.legs_used.join(' + ')],
          ['embed', d.meta.query_embedding_ms == null ? '—' : `${d.meta.query_embedding_ms} ms`],
          ['fused', d.meta.fused_candidates],
        ]}
      />
      <Receipt items={['same ranking code as production', 'public corpus only']} />
    </div>
  );
};

// --- Scheduler ------------------------------------------------------------
export const renderScheduler = (env: PlayEnvelope<SchedulerData>) => {
  const d = env.data;
  const q = d.interpreted_query;
  const since = q.since_hours === 1 ? 'last hour' : q.since_hours === 24 ? 'last 24 h' : `last ${Math.round(q.since_hours / 24)} days`;
  const failColor = (b: string) => (b === '0' ? OK : b === '1' ? WARN : BAD);
  return (
    <div>
      <p className="mb-2">
        Interpreted as <span style={{ color: HOMER_THEME.accent }}>status = {q.status} · {since}{q.include_next_run ? ' · include next run' : ''}</span>. {d.jobs.length} of {d.meta.public_jobs_scanned} public jobs match.
      </p>
      <div className="grid gap-1.5">
        {d.jobs.map((j) => (
          <Row
            key={j.id}
            pill={j.running ? 'running' : j.consecutive_failures_bucket === '0' ? 'ok' : `${j.consecutive_failures_bucket} fail`}
            pillColor={j.running ? HOMER_THEME.accent : failColor(j.consecutive_failures_bucket)}
            right={j.recent_runs[0]?.duration_ms_bucket ?? ''}
          >
            {j.id} · {j.cadence}
            {j.next_run_at ? ` · next ${ago(j.next_run_at)}` : ''}
            {j.last_success_at ? ` · last ok ${ago(j.last_success_at)}` : ''}
          </Row>
        ))}
        {d.jobs.length === 0 && <span style={{ color: HOMER_THEME.textMuted }}>No public jobs match that filter.</span>}
      </div>
      <KV items={[['scanned', `${d.meta.public_jobs_scanned} jobs · ${d.meta.runs_scanned} runs`], ['source', env.receipt?.source ?? 'live bridge'], ['observed', ago(env.receipt?.observed_at)]]} />
      <Receipt items={['real scheduled_job_state', 'public job allowlist', 'model wrote a filter, not SQL']} />
    </div>
  );
};

// --- Web ------------------------------------------------------------------
export const renderWeb = (env: PlayEnvelope<WebActivityData>) => {
  const d = env.data;
  const label = d.window === '1h' ? 'Last hour' : d.window === '24h' ? 'Last 24 h' : 'Last 7 days';
  return (
    <div>
      <p className="mb-2">{label}, as of {ago(d.as_of)}:</p>
      <div className="grid gap-1.5">
        <Row pill="runs" pillColor={OK} right="live">
          scheduled {d.activity.scheduled_runs.completed} ok · {d.activity.scheduled_runs.failed} failed · {d.activity.scheduled_runs.running} running &nbsp;|&nbsp; CLI {d.activity.cli_runs.completed} ok · {d.activity.cli_runs.failed} failed
        </Row>
        <Row pill="threads" pillColor={HOMER_THEME.accent} right="bucketed">
          {d.threads.active_bucket} active · {d.threads.created} created · {d.threads.messages} messages
          {d.threads.providers[0] ? ` · ${d.threads.providers[0].family} handled ${d.threads.providers[0].share_bucket}` : ''}
        </Row>
        <Row pill="events" pillColor={HOMER_THEME.textMuted} right={d.window}>
          {d.activity.events_by_kind.map((e) => `${e.kind} ${e.count}`).join(' · ') || '—'}
        </Row>
      </div>
      <Receipt items={['aggregate counts only', 'no message content', 'zero cost']} />
    </div>
  );
};

// --- MCP ------------------------------------------------------------------
const Code: React.FC<{ children: string }> = ({ children }) => (
  <pre
    className="mt-2 rounded-md px-3 py-2.5 text-[12px] overflow-x-auto"
    style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.text, background: '#0a0908', border: `1px solid ${HOMER_THEME.divider}` }}
  >
    {children}
  </pre>
);

export const renderMcp = (env: PlayEnvelope<McpListData | McpCallData>) => {
  if (env.action === 'list_tools') {
    const d = env.data as McpListData;
    return (
      <div>
        <p className="mb-2">
          <span style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}>tools/list</span> → {d.tools.length} tools exposed publicly. Call one with{' '}
          <span style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}>/call &lt;name&gt; {'{...}'}</span>.
        </p>
        <div className="grid gap-1.5">
          {d.tools.map((t) => (
            <Row key={t.name} pill={t.side_effect_class === 'none' ? 'read' : t.side_effect_class} pillColor={OK} right={t.data_source.replace(/_/g, ' ')}>
              <b className="font-medium">{t.name}</b> · {t.description}
              {Array.isArray((t.input_schema as { required?: string[] }).required) && (
                <span style={{ color: HOMER_THEME.textMuted }}> · needs {((t.input_schema as { required?: string[] }).required ?? []).join(', ')}</span>
              )}
            </Row>
          ))}
        </div>
        <Receipt items={['same protocol as the private server', 'read-only allowlist', 'no side effects']} />
      </div>
    );
  }
  const d = env.data as McpCallData;
  const text = d.content.map((c) => c.text ?? '').filter(Boolean).join('\n');
  return (
    <div>
      <p className="mb-1">
        <span style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}>tools/call</span> → <b className="font-medium">{d.tool}</b>
        {d.is_error && <span style={{ color: BAD }}> · error</span>}
      </p>
      {text && <div className="text-sm whitespace-pre-wrap" style={{ color: HOMER_THEME.text }}>{text}</div>}
      {d.structured_content && <Code>{JSON.stringify(d.structured_content, null, 2).slice(0, 2400)}</Code>}
      <KV items={[['allowlist', String(d.trace.allowlist_match)], ['handler', d.trace.handler]]} />
      <Receipt items={['real MCP frame', 'allowlisted tool', 'nothing written']} />
    </div>
  );
};

// --- Voice ----------------------------------------------------------------
export const renderVoice = (env: PlayEnvelope<VoiceData>) => {
  const d = env.data;
  const src = `data:${d.audio.mime_type};base64,${d.audio.data}`;
  return (
    <div>
      <p className="mb-2">Synthesised with Homer's real TTS stack — the same cloned voice as Goggins GPT.</p>
      <AudioClip src={src} label={d.text} autoPlay durationMs={d.audio.duration_ms} />
      <KV items={[['chars billed', d.characters_billed], ['bytes', d.audio.bytes], ['voice', d.voice.class.replace(/_/g, ' ')]]} />
      <Receipt items={['no outbound call', 'audio not stored']} />
    </div>
  );
};
