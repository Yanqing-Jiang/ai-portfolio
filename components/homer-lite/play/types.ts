// Contract for POST /api/homer/play — mirrors §3 of
// ~/homer/output/codex/homer-playable-architecture-backend-2026-08-29-1922.md.
// Keep in sync with backend/homer_play/ Pydantic models.

export type PlayTab = 'memory' | 'scheduler' | 'executors' | 'mcp' | 'voice' | 'web';

export interface PlayRequest {
  version: '1';
  tab: PlayTab;
  action: string;
  message: string;
  input?: Record<string, unknown>;
  client_turn_id?: string;
}

export interface PlayDegraded {
  active: boolean;
  reason: string;
  replay_id?: string;
  captured_at?: string;
  live_data_age_seconds?: number | null;
}

export interface PlayEnvelope<T = unknown> {
  ok: true;
  version: string;
  request_id: string;
  tab: PlayTab;
  action: string;
  mode: 'live' | 'degraded';
  reply: string;
  data: T;
  receipt?: { source: string; observed_at: string; read_only: boolean; persisted: boolean };
  limits?: { remaining_this_hour: number; reset_at: string };
  spend?: { reserved_usd: number; charged_usd: number; daily_cap_usd: number };
  degraded: PlayDegraded | null;
}

export interface PlayError {
  ok: false;
  request_id?: string;
  error: { code: string; message: string; retryable?: boolean; fields?: Record<string, string> };
}

// --- Memory ---------------------------------------------------------------
export interface SearchTrace {
  bm25_rank: number | null;
  bm25_score: number | null;
  vector_rank: number | null;
  cosine: number | null;
  rrf_score: number;
  tier_multiplier: number;
  recency_multiplier: number;
  final_score: number;
}
export interface SearchHit {
  id: string;
  content: string;
  claim_type: string;
  target: string;
  status: string;
  created_at: string;
  trace: SearchTrace;
}
export interface MemorySearchData {
  query: string;
  vector_leg: string;
  results: SearchHit[];
  meta: { legs_used: string[]; corpus_size: number; fused_candidates: number; query_embedding_ms: number | null };
}
export interface ExtractMatch { public_claim_id: string; content: string; cosine: number; relation: string }
export interface ExtractCandidate {
  candidate_id: string;
  content: string;
  claim_type: string;
  confidence: number;
  provenance: string;
  route: { tier: string; decision: string; reason: string; would_persist: boolean };
  matches: ExtractMatch[];
}
export interface MemoryExtractData {
  extractor: { name: string; version: string };
  candidates: ExtractCandidate[];
  policy: { corpus: string; conflict_threshold: number; writes_attempted: number };
}

// --- Scheduler ------------------------------------------------------------
export interface SchedulerRun { started_at: string; outcome: string; duration_ms_bucket: string }
export interface SchedulerJob {
  id: string;
  name: string;
  kind: string;
  cadence: string;
  enabled: boolean;
  running: boolean;
  next_run_at: string | null;
  last_success_at: string | null;
  consecutive_failures_bucket: string;
  recent_runs: SchedulerRun[];
}
export interface SchedulerData {
  interpreted_query: { status: string; since_hours: number; job_ids: string[]; include_next_run: boolean };
  jobs: SchedulerJob[];
  meta: { public_jobs_scanned: number; runs_scanned: number };
}

// --- Web ------------------------------------------------------------------
export interface WebActivityData {
  window: string;
  as_of: string;
  threads: { active_bucket: string; created: number; messages: number; providers: { family: string; share_bucket: string }[] };
  activity: {
    cli_runs: { completed: number; failed: number; running: number };
    scheduled_runs: { completed: number; failed: number; running: number };
    events_by_kind: { kind: string; count: number }[];
  };
  freshness: { db_observed_at: string; cache_age_seconds: number };
}

// --- MCP ------------------------------------------------------------------
export interface McpTool {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  data_source: string;
  side_effect_class: string;
}
export interface McpListData { protocol: string; tools: McpTool[]; hidden_tool_count: number }
export interface McpCallData {
  protocol: string;
  tool: string;
  content: { type: string; text?: string }[];
  structured_content: Record<string, unknown> | null;
  is_error: boolean;
  trace: { allowlist_match: boolean; handler: string };
}

// --- Voice ----------------------------------------------------------------
export interface VoiceData {
  text: string;
  audio: { mime_type: string; encoding: string; data: string; bytes: number; duration_ms: number | null };
  voice: { provider: string; class: string; model: string };
  characters_billed: number;
}
export interface VoiceRecording { id: string; text: string; file: string; bytes?: number; duration_ms?: number }
