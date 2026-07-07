import React, { useMemo, useRef, useState } from 'react';
import { AlertTriangle, ChevronDown, Loader2, Search, Terminal } from 'lucide-react';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';
import { configService } from '../../../services/config';

type Trace = {
  bm25_rank: number | null;
  bm25_score: number | null;
  vector_rank: number | null;
  cosine: number | null;
  rrf_score: number;
  tier_multiplier: number;
  recency_multiplier: number;
  final_score: number;
};

type Hit = {
  id: string;
  content: string;
  claim_type: string;
  target: string;
  status: 'approved' | 'candidate' | 'archived' | string;
  created_at: string;
  trace: Trace;
};

type MemorySearchResponse = {
  query: string;
  vector_leg: 'available' | 'unavailable' | string;
  results: Hit[];
  meta: {
    query_embedding_ms: number | null;
    legs_used: string[];
    corpus_size: number;
    fused_candidates: number;
  };
};

type SearchError = {
  message: string;
  rateLimited?: boolean;
  retryAfter?: number;
};

const SUGGESTED_QUERIES = [
  'why sqlite instead of a vector db',
  'what happens when two memories conflict',
  'which model runs the morning brief',
  'why did the voice stack end up on elevenlabs',
] as const;

const getApiBase = () => {
  if (typeof window === 'undefined') return configService.getBackendUrl();
  const host = window.location.hostname;
  const bffHosted =
    host === 'yanqing.app' ||
    host.endsWith('.yanqing.app') ||
    host.endsWith('.pages.dev');
  return bffHosted ? '' : configService.getBackendUrl();
};

const formatRank = (rank: number | null) => (rank ? `#${rank}` : '—');
const formatScore = (value: number | null | undefined, digits = 4) =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';
const formatDate = (value: string) => {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric', timeZone: 'UTC' });
};
const formatRetry = (seconds?: number) => {
  if (!seconds || seconds < 1) return 'soon';
  const minutes = Math.ceil(seconds / 60);
  return minutes <= 1 ? 'about 1 minute' : `about ${minutes} minutes`;
};

const statusColor = (status: Hit['status']) => {
  if (status === 'candidate') return '#f5cf94';
  if (status === 'archived') return '#c4b5fd';
  return '#86efac';
};

const metaLine = (data: MemorySearchResponse | null) => {
  if (!data) return 'ready · public corpus · BM25 + vector + RRF trace';
  const legs = data.meta.legs_used.join('+');
  const embed = data.meta.query_embedding_ms == null ? 'embed unavailable' : `embed ${data.meta.query_embedding_ms}ms`;
  return `${legs} · ${data.meta.corpus_size} claims · ${data.meta.fused_candidates} fused · ${embed}`;
};

const TraceMetric: React.FC<{ label: string; value: string; accent?: boolean }> = ({ label, value, accent }) => (
  <div className="min-w-0">
    <div
      className="text-[9px] uppercase tracking-[0.18em] mb-1"
      style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
    >
      {label}
    </div>
    <div
      className="text-[12px] md:text-[13px] tabular-nums truncate"
      style={{ color: accent ? HOMER_THEME.accent : HOMER_THEME.text, fontFamily: HOMER_THEME.fontMono }}
    >
      {value}
    </div>
  </div>
);

const ResultCard: React.FC<{
  hit: Hit;
  open: boolean;
  onToggle: () => void;
}> = ({ hit, open, onToggle }) => {
  const compactTrace =
    `bm25 ${formatRank(hit.trace.bm25_rank)} / ${formatScore(hit.trace.bm25_score, 3)} · ` +
    `cos ${formatScore(hit.trace.cosine, 3)} · ` +
    `rrf ${formatScore(hit.trace.rrf_score, 4)} → ` +
    `×${formatScore(hit.trace.tier_multiplier, 2)} ×${formatScore(hit.trace.recency_multiplier, 2)} → ` +
    `${formatScore(hit.trace.final_score, 5)}`;

  return (
    <article
      className="rounded-md border overflow-hidden"
      style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bg }}
    >
      <div className="p-4 md:p-5">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span
            className="text-[10px] uppercase tracking-[0.18em] rounded border px-2 py-1"
            style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.accent, fontFamily: HOMER_THEME.fontMono }}
          >
            {hit.claim_type}
          </span>
          <span
            className="text-[10px] uppercase tracking-[0.18em] rounded border px-2 py-1"
            style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
          >
            {hit.target}
          </span>
          <span
            className="text-[10px] uppercase tracking-[0.18em] rounded border px-2 py-1"
            style={{ borderColor: 'rgba(255,255,255,0.08)', color: statusColor(hit.status), fontFamily: HOMER_THEME.fontMono }}
          >
            {hit.status}
          </span>
          <span
            className="ml-auto text-[10px] tabular-nums"
            style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
          >
            {hit.id} · {formatDate(hit.created_at)}
          </span>
        </div>

        <p className="text-sm md:text-base leading-relaxed" style={{ color: HOMER_THEME.text }}>
          {hit.content}
        </p>
      </div>

      <button
        type="button"
        onClick={onToggle}
        className="w-full min-h-[44px] border-t px-4 py-3 text-left flex items-center gap-3 transition-colors hover:bg-white/[0.03]"
        style={{ borderColor: HOMER_THEME.divider }}
        aria-expanded={open}
      >
        <span
          className="min-w-0 flex-1 text-[11px] leading-relaxed tabular-nums [overflow-wrap:anywhere]"
          style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
        >
          {compactTrace}
        </span>
        <ChevronDown
          size={15}
          className="shrink-0 transition-transform"
          style={{ color: HOMER_THEME.accent, transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
        />
      </button>

      {open && (
        <div
          className="border-t p-4 grid grid-cols-2 md:grid-cols-8 gap-4"
          style={{ borderColor: HOMER_THEME.divider, background: '#08070a' }}
        >
          <TraceMetric label="bm25 rank" value={formatRank(hit.trace.bm25_rank)} />
          <TraceMetric label="bm25 score" value={formatScore(hit.trace.bm25_score, 4)} />
          <TraceMetric label="vector rank" value={formatRank(hit.trace.vector_rank)} />
          <TraceMetric label="cosine" value={formatScore(hit.trace.cosine, 4)} />
          <TraceMetric label="rrf" value={formatScore(hit.trace.rrf_score, 5)} />
          <TraceMetric label="tier" value={`×${formatScore(hit.trace.tier_multiplier, 2)}`} />
          <TraceMetric label="recency" value={`×${formatScore(hit.trace.recency_multiplier, 2)}`} />
          <TraceMetric label="final" value={formatScore(hit.trace.final_score, 6)} accent />
        </div>
      )}
    </article>
  );
};

export const MemorySearchDemo: React.FC = () => {
  const [query, setQuery] = useState<string>(SUGGESTED_QUERIES[0]);
  const [data, setData] = useState<MemorySearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<SearchError | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const degraded = data?.vector_leg === 'unavailable';
  const emptyState = !data && !loading && !error;
  const summary = useMemo(() => metaLine(data), [data]);

  const runSearch = async (nextQuery: string = query) => {
    const trimmed = nextQuery.trim();
    if (!trimmed) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${getApiBase()}/api/homer/memory-search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: trimmed }),
        signal: controller.signal,
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = body?.detail;
        const message =
          typeof detail === 'string'
            ? detail
            : typeof detail?.message === 'string'
              ? detail.message
              : `Search failed with HTTP ${response.status}`;
        setError({
          message,
          rateLimited: response.status === 429,
          retryAfter: Number(response.headers.get('retry-after')) || undefined,
        });
        return;
      }
      const payload = body as MemorySearchResponse;
      setData(payload);
      setOpenId(payload.results[0]?.id ?? null);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setError({ message: err instanceof Error ? err.message : 'Search failed.' });
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setLoading(false);
      }
    }
  };

  return (
    <SectionShell
      id="memory-search"
      eyebrow="LIVE RETRIEVAL"
      title="Interrogate Homer's memory."
      subtitle="This box runs Homer's actual hybrid retrieval stack — FTS + vector + RRF + tier/recency scoring — over a public-safe corpus of claims about Homer itself. Same math, sanitized data."
    >
      <div
        className="rounded-lg border overflow-hidden"
        style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bgSoft }}
      >
        <div
          className="flex flex-wrap items-center gap-2 px-4 py-2.5 border-b"
          style={{ borderColor: HOMER_THEME.divider, background: 'rgba(0,0,0,0.25)' }}
        >
          <Terminal size={13} style={{ color: HOMER_THEME.accent }} />
          <span
            className="text-[10px] tracking-[0.24em] uppercase"
            style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
          >
            memory_search.trace
          </span>
          <span
            className="ml-auto text-[10px] tabular-nums"
            style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
          >
            {summary}
          </span>
        </div>

        <div className="p-4 md:p-5 border-b" style={{ borderColor: HOMER_THEME.divider }}>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void runSearch();
            }}
            className="flex flex-col gap-3 md:flex-row"
          >
            <label className="sr-only" htmlFor="homer-memory-query">
              Search Homer's public memory corpus
            </label>
            <div
              className="flex-1 rounded-md border flex items-center gap-3 px-3 min-h-[48px]"
              style={{ borderColor: HOMER_THEME.divider, background: '#08070a' }}
            >
              <Search size={15} style={{ color: HOMER_THEME.accent }} />
              <input
                id="homer-memory-query"
                value={query}
                maxLength={200}
                onChange={(event) => setQuery(event.target.value)}
                className="w-full bg-transparent outline-none text-sm md:text-base"
                style={{ color: HOMER_THEME.text, fontFamily: HOMER_THEME.fontMono }}
                placeholder="Ask about Homer's memory architecture..."
              />
            </div>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-md border px-5 text-[11px] uppercase tracking-[0.18em] transition-colors disabled:opacity-50"
              style={{
                borderColor: HOMER_THEME.accentSoft,
                background: HOMER_THEME.accentSoft,
                color: HOMER_THEME.accent,
                fontFamily: HOMER_THEME.fontMono,
              }}
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              search
            </button>
          </form>

          <div className="mt-3 flex flex-wrap gap-2">
            {SUGGESTED_QUERIES.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => {
                  setQuery(item);
                  void runSearch(item);
                }}
                disabled={loading}
                className="min-h-[34px] rounded border px-3 text-[10px] md:text-[11px] transition-colors hover:bg-white/[0.03] disabled:opacity-50"
                style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="relative min-h-[360px] p-4 md:p-5">
          {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center" style={{ background: 'rgba(8,7,10,0.72)' }}>
              <div
                className="relative overflow-hidden rounded-md border px-5 py-4"
                style={{ borderColor: HOMER_THEME.divider, background: '#08070a', fontFamily: HOMER_THEME.fontMono }}
              >
                <style>{`
                  @keyframes homer-search-scan { 0% { transform: translateY(-100%); } 100% { transform: translateY(280%); } }
                  .homer-search-scanline::after {
                    content: '';
                    position: absolute;
                    left: 0;
                    right: 0;
                    top: 0;
                    height: 42%;
                    background: linear-gradient(transparent, rgba(212,160,86,0.16), transparent);
                    animation: homer-search-scan 1.25s linear infinite;
                  }
                `}</style>
                <div className="homer-search-scanline absolute inset-0 pointer-events-none" />
                <div className="relative text-[11px] tracking-[0.2em] uppercase" style={{ color: HOMER_THEME.accent }}>
                  embedding query · running BM25 · fusing ranks
                </div>
              </div>
            </div>
          )}

          {error && (
            <div
              className="rounded-md border p-4 flex gap-3"
              style={{ borderColor: error.rateLimited ? HOMER_THEME.accentSoft : 'rgba(248,113,113,0.35)', background: '#08070a' }}
            >
              <AlertTriangle size={16} className="mt-0.5 shrink-0" style={{ color: error.rateLimited ? HOMER_THEME.accent : '#f87171' }} />
              <div>
                <div
                  className="text-[11px] uppercase tracking-[0.18em] mb-2"
                  style={{ color: error.rateLimited ? HOMER_THEME.accent : '#f87171', fontFamily: HOMER_THEME.fontMono }}
                >
                  {error.rateLimited ? 'rate limited' : 'search error'}
                </div>
                <p className="text-sm leading-relaxed" style={{ color: HOMER_THEME.textMuted }}>
                  {error.message}
                  {error.rateLimited ? ` Reset in ${formatRetry(error.retryAfter)}.` : ''}
                </p>
              </div>
            </div>
          )}

          {degraded && !error && (
            <div
              className="mb-4 rounded-md border px-4 py-3 text-[11px] leading-relaxed"
              style={{ borderColor: HOMER_THEME.accentSoft, color: HOMER_THEME.accent, background: 'rgba(212,160,86,0.08)', fontFamily: HOMER_THEME.fontMono }}
            >
              vector_leg=unavailable · showing lexical BM25 + RRF trace only
            </div>
          )}

          {emptyState && (
            <div
              className="rounded-md border p-5 md:p-6 min-h-[240px] flex flex-col justify-center"
              style={{ borderColor: HOMER_THEME.divider, background: '#08070a' }}
            >
              <div
                className="text-[11px] uppercase tracking-[0.22em] mb-4"
                style={{ color: HOMER_THEME.accent, fontFamily: HOMER_THEME.fontMono }}
              >
                awaiting query
              </div>
              <p className="max-w-2xl text-sm md:text-base leading-relaxed" style={{ color: HOMER_THEME.textMuted }}>
                Ask about SQLite vs vector databases, memory conflicts, scheduler routing, executors, voice architecture, or operational safety. Results return ranked claims plus the scoring trace that produced them.
              </p>
            </div>
          )}

          {data && !error && (
            <div className="space-y-3">
              {data.results.map((hit) => (
                <ResultCard
                  key={hit.id}
                  hit={hit}
                  open={openId === hit.id}
                  onToggle={() => setOpenId((current) => (current === hit.id ? null : hit.id))}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </SectionShell>
  );
};

export default MemorySearchDemo;
