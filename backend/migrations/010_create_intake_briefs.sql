-- 010: intake_briefs — completed AI Brief Agent briefs (Phase 2).
--
-- Applied automatically by the migration runner on deploy (scripts/apply_migration.py).
-- Establishes its own table-local security invariant, matching the hardening
-- conventions of migration 009: schema-qualified, RLS on, Data API roles
-- revoked, and an explicit deny policy for the anon keepalive contract.

CREATE TABLE IF NOT EXISTS public.intake_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    path TEXT NOT NULL CHECK (path IN ('business', 'individual', 'unknown')),
    -- The structured brief the prospect reviewed/approved (JSON, server-validated).
    brief JSONB NOT NULL,
    -- Optional contact info, captured at booking time.
    client_name TEXT,
    client_email TEXT,
    -- The next step the agent recommended.
    recommended_next_step TEXT CHECK (
        recommended_next_step IS NULL OR recommended_next_step IN ('fit', '30', '60')
    ),
    -- Link to the resulting booking (set when the prospect books). No hard FK:
    -- a brief may be stored before/independently of a confirmed booking row, and
    -- we never want a brief write to fail because the booking isn't committed yet.
    booking_id UUID,
    -- Coarse provenance for abuse review (hashed visitor IP, never the raw IP).
    source_ip_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_intake_briefs_created ON public.intake_briefs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intake_briefs_email ON public.intake_briefs (client_email);
CREATE INDEX IF NOT EXISTS idx_intake_briefs_booking ON public.intake_briefs (booking_id);

-- Security: only the backend's service role (via the asyncpg pool) reads/writes
-- this table. Make it invisible to the Supabase Data API roles entirely.
ALTER TABLE public.intake_briefs ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE public.intake_briefs FROM anon, authenticated;

-- Preserve the anon keepalive contract used elsewhere while making every row
-- invisible to anon (mirrors migration 009's bookings pattern).
GRANT SELECT ON TABLE public.intake_briefs TO anon;

DROP POLICY IF EXISTS intake_briefs_anon_deny ON public.intake_briefs;
CREATE POLICY intake_briefs_anon_deny
    ON public.intake_briefs
    AS RESTRICTIVE
    FOR SELECT
    TO anon
    USING (false);

NOTIFY pgrst, 'reload schema';
