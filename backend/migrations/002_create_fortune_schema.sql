-- Migration: Create fortune (Ming Engine) domain schema
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard
--
-- Tables:
--   fortune                 one row per user session (birth data + initial request)
--   fortune_run             each agent pipeline run (initial + follow-up actions)
--   fortune_event           ordered SSE event log for replay (seq + run_id)
--   fortune_message         Ask-tab chat history (user + assistant)
--   fortune_snapshot        final projection JSON per fortune for CF-cached replay
--   fortune_trace           tracing-processor span projections for Glass Box
--   fortune_public_share    slug -> fortune_id mapping for shareable URLs
--
-- Access control:
-- Primary path: FastAPI asyncpg connection using the Supabase DB role — this path
-- bypasses RLS (direct Postgres role connections are not JWT-scoped), so the real
-- access boundary is the connection string + service_role secret stored in
-- backend/.env.production. RLS policies below are belt-and-suspenders for any
-- future Supabase REST/client calls and deny-by-default to anon.
--
-- This migration is idempotent: safe to rerun after partial failure.

-- ---------------------------------------------------------------------------
-- Helper: updated_at trigger function
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at_now()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- fortune: one row per user session (birth + initial request shape)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fortune (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    birth_iso TEXT NOT NULL,
    timezone TEXT NOT NULL,
    focus TEXT,
    question TEXT,
    tone TEXT,
    birth_time_unknown BOOLEAN NOT NULL DEFAULT FALSE,
    gender TEXT NOT NULL DEFAULT 'unknown',
    locale TEXT NOT NULL DEFAULT 'en',
    surface_id TEXT NOT NULL,
    client_ip TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fortune_created_at ON public.fortune (created_at DESC);

CREATE OR REPLACE TRIGGER fortune_updated_at
    BEFORE UPDATE ON public.fortune
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at_now();

-- ---------------------------------------------------------------------------
-- fortune_run: one row per agent pipeline invocation
-- ---------------------------------------------------------------------------
-- last_emitted_seq: race-free replay sequence allocator. Reserve the next seq
-- atomically with: UPDATE fortune_run SET last_emitted_seq = last_emitted_seq + 1
--   WHERE id = $1 RETURNING last_emitted_seq.
CREATE TABLE IF NOT EXISTS public.fortune_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fortune_id UUID NOT NULL REFERENCES public.fortune(id) ON DELETE CASCADE,
    run_kind TEXT NOT NULL CHECK (run_kind IN ('initial', 'action')),
    action_type TEXT,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'streaming', 'done', 'failed_guardrail', 'error', 'interrupted'
    )),
    agent_session_id TEXT,
    model_used TEXT,
    reasoning_effort TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    reasoning_tokens INTEGER,
    cost_cents NUMERIC(10, 4),
    error_message TEXT,
    trace_id TEXT,
    group_id TEXT,
    request_id TEXT,
    last_emitted_seq INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

-- Converge columns when recovering from an older pre-patch fortune_run table.
ALTER TABLE public.fortune_run
    ADD COLUMN IF NOT EXISTS reasoning_tokens INTEGER;
ALTER TABLE public.fortune_run
    ADD COLUMN IF NOT EXISTS last_emitted_seq INTEGER NOT NULL DEFAULT 0;

-- Composite unique key lets child tables prove run_id belongs to fortune_id.
ALTER TABLE public.fortune_run
    DROP CONSTRAINT IF EXISTS fortune_run_id_fortune_id_key;
ALTER TABLE public.fortune_run
    ADD CONSTRAINT fortune_run_id_fortune_id_key UNIQUE (id, fortune_id);

ALTER TABLE public.fortune_run
    DROP CONSTRAINT IF EXISTS fortune_run_kind_action_type_consistency;
ALTER TABLE public.fortune_run
    ADD CONSTRAINT fortune_run_kind_action_type_consistency
    CHECK (
        (run_kind = 'initial' AND action_type IS NULL)
        OR
        (run_kind = 'action' AND action_type IS NOT NULL)
    );

ALTER TABLE public.fortune_run
    DROP CONSTRAINT IF EXISTS fortune_run_last_emitted_seq_nonnegative;
ALTER TABLE public.fortune_run
    ADD CONSTRAINT fortune_run_last_emitted_seq_nonnegative
    CHECK (last_emitted_seq >= 0);

CREATE INDEX IF NOT EXISTS idx_fortune_run_fortune_id
    ON public.fortune_run (fortune_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fortune_run_active_status_created_at
    ON public.fortune_run (status, created_at)
    WHERE status IN ('queued', 'streaming');
CREATE INDEX IF NOT EXISTS idx_fortune_run_created_at
    ON public.fortune_run (created_at DESC);

-- ---------------------------------------------------------------------------
-- fortune_event: ordered SSE event log for replay + Last-Event-ID reconnect
-- ---------------------------------------------------------------------------
-- Composite FK (run_id, fortune_id) -> fortune_run(id, fortune_id) prevents
-- cross-fortune event misattribution at the database layer.
CREATE TABLE IF NOT EXISTS public.fortune_event (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL,
    fortune_id UUID NOT NULL,
    seq INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    target_tab TEXT,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Drop the old single-column FK if it exists (pre-patch migrations had it).
ALTER TABLE public.fortune_event
    DROP CONSTRAINT IF EXISTS fortune_event_run_id_fkey;
ALTER TABLE public.fortune_event
    DROP CONSTRAINT IF EXISTS fortune_event_run_fortune_fkey;
ALTER TABLE public.fortune_event
    ADD CONSTRAINT fortune_event_run_fortune_fkey
    FOREIGN KEY (run_id, fortune_id)
    REFERENCES public.fortune_run (id, fortune_id)
    ON DELETE CASCADE;

CREATE UNIQUE INDEX IF NOT EXISTS idx_fortune_event_run_seq
    ON public.fortune_event (run_id, seq);
CREATE INDEX IF NOT EXISTS idx_fortune_event_fortune_created
    ON public.fortune_event (fortune_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- fortune_message: Ask-tab chat history (durable Q&A)
-- ---------------------------------------------------------------------------
-- run_id may be NULL for user-side messages queued before their run is created.
-- Composite FK still enforces same-fortune invariant when run_id is present.
CREATE TABLE IF NOT EXISTS public.fortune_message (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fortune_id UUID NOT NULL REFERENCES public.fortune(id) ON DELETE CASCADE,
    run_id UUID,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    action_type TEXT,
    content TEXT NOT NULL,
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    model_used TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Drop the old single-column FK if it exists (pre-patch migrations had it).
ALTER TABLE public.fortune_message
    DROP CONSTRAINT IF EXISTS fortune_message_run_id_fkey;
ALTER TABLE public.fortune_message
    DROP CONSTRAINT IF EXISTS fortune_message_run_fortune_fkey;
ALTER TABLE public.fortune_message
    ADD CONSTRAINT fortune_message_run_fortune_fkey
    FOREIGN KEY (run_id, fortune_id)
    REFERENCES public.fortune_run (id, fortune_id)
    ON DELETE SET NULL (run_id);

CREATE INDEX IF NOT EXISTS idx_fortune_message_fortune_created
    ON public.fortune_message (fortune_id, created_at);

-- ---------------------------------------------------------------------------
-- fortune_snapshot: final projection JSON per fortune (source for replay)
-- ---------------------------------------------------------------------------
-- One row per fortune. Upserted when a run completes. snapshot_version is bumped
-- on every write so CF edge can use it in the ETag for cache invalidation.
CREATE TABLE IF NOT EXISTS public.fortune_snapshot (
    fortune_id UUID PRIMARY KEY REFERENCES public.fortune(id) ON DELETE CASCADE,
    snapshot_version INTEGER NOT NULL DEFAULT 1,
    latest_overview JSONB,
    latest_pillars JSONB,
    latest_mechanics JSONB,
    latest_narrative JSONB,
    latest_trace JSONB,
    latest_references JSONB,
    latest_retrodictions JSONB,
    status TEXT NOT NULL DEFAULT 'partial' CHECK (status IN ('partial', 'done')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fortune_snapshot_updated
    ON public.fortune_snapshot (updated_at DESC);

CREATE OR REPLACE TRIGGER fortune_snapshot_updated_at
    BEFORE UPDATE ON public.fortune_snapshot
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at_now();

-- ---------------------------------------------------------------------------
-- fortune_trace: TracingProcessor span projections for the Glass Box drawer
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fortune_trace (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES public.fortune_run(id) ON DELETE CASCADE,
    span_id TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'complete',
    parent_span_id TEXT,
    span_type TEXT NOT NULL,
    agent_name TEXT,
    tool_name TEXT,
    model TEXT,
    input_json JSONB,
    output_json JSONB,
    error TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    duration_ms INTEGER
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fortune_trace_run_span_phase
    ON public.fortune_trace (run_id, span_id, phase);
CREATE INDEX IF NOT EXISTS idx_fortune_trace_run_started
    ON public.fortune_trace (run_id, started_at);

-- ---------------------------------------------------------------------------
-- fortune_public_share: share slug -> fortune_id for /fortune/:slug
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fortune_public_share (
    share_slug TEXT PRIMARY KEY,
    fortune_id UUID NOT NULL REFERENCES public.fortune(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_fortune_public_share_active_fortune
    ON public.fortune_public_share (fortune_id)
    WHERE revoked_at IS NULL;

-- ---------------------------------------------------------------------------
-- Row Level Security (belt-and-suspenders; primary access is asyncpg)
-- ---------------------------------------------------------------------------

ALTER TABLE public.fortune ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fortune_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fortune_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fortune_message ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fortune_snapshot ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fortune_trace ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fortune_public_share ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS service_role_all_fortune ON public.fortune;
CREATE POLICY service_role_all_fortune ON public.fortune
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_all_fortune_run ON public.fortune_run;
CREATE POLICY service_role_all_fortune_run ON public.fortune_run
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_all_fortune_event ON public.fortune_event;
CREATE POLICY service_role_all_fortune_event ON public.fortune_event
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_all_fortune_message ON public.fortune_message;
CREATE POLICY service_role_all_fortune_message ON public.fortune_message
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_all_fortune_snapshot ON public.fortune_snapshot;
CREATE POLICY service_role_all_fortune_snapshot ON public.fortune_snapshot
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_all_fortune_trace ON public.fortune_trace;
CREATE POLICY service_role_all_fortune_trace ON public.fortune_trace
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_all_fortune_public_share ON public.fortune_public_share;
CREATE POLICY service_role_all_fortune_public_share ON public.fortune_public_share
    FOR ALL TO service_role USING (true) WITH CHECK (true);
