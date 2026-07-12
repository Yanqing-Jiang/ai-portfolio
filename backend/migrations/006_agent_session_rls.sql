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

ALTER TABLE public.agent_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_messages ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.agent_sessions FROM anon, authenticated;
REVOKE ALL ON public.agent_messages FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.agent_messages_id_seq FROM anon, authenticated;
