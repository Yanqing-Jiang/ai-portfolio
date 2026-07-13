-- 006: Lock down SDK session tables (agent_sessions / agent_messages).
--
-- These tables are created at runtime by the Agents SDK's SQLAlchemySession
-- (see backend/fortune/session_store.py) and therefore never went through a
-- reviewed migration. They store raw run inputs/outputs — full prompts,
-- foundation payloads (birth-derived data), and Ask questions — but were
-- created with RLS disabled and default PUBLIC grants, leaving them readable
-- and writable by the `anon` and `authenticated` PostgREST roles.
--
-- The backend connects as the table owner (postgres via SUPABASE_DB_URL),
-- which bypasses non-FORCE RLS, so enabling RLS with no policies blocks all
-- PostgREST access while leaving the backend unaffected. This mirrors the
-- service-role-only posture of the fortune* tables (002).
--
-- Applied to live Supabase 2026-07-12 (fortune v2 final gate, finding B1).

-- Create the SDK-owned tables explicitly so a clean restore can run the
-- migration chain before application code has initialized SQLAlchemySession.
CREATE TABLE IF NOT EXISTS public.agent_sessions (
    session_id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.agent_messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR NOT NULL REFERENCES public.agent_sessions(session_id)
        ON DELETE CASCADE,
    message_data TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_messages_session_time
    ON public.agent_messages (session_id, created_at);

ALTER TABLE public.agent_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_messages ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.agent_sessions FROM anon, authenticated;
REVOKE ALL ON public.agent_messages FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.agent_messages_id_seq FROM anon, authenticated;
