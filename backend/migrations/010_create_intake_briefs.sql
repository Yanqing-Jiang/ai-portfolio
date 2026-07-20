-- Migration: Create intake_briefs table for the AI Brief Agent (Phase 2).
-- Stores the completed, prospect-approved structured brief produced by the
-- /consult intake chat before it routes into the booking flow.
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard

CREATE TABLE IF NOT EXISTS intake_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    path TEXT NOT NULL CHECK (path IN ('business', 'individual', 'unknown')),
    -- The structured brief the prospect reviewed/approved (JSON).
    brief JSONB NOT NULL,
    -- Optional contact info, if the prospect provided it in-chat.
    client_name TEXT,
    client_email TEXT,
    -- The next step the agent recommended: 'fit' (free call), '30' or '60' (paid).
    recommended_next_step TEXT,
    -- Loose link to a resulting booking, set when the prospect books.
    booking_id UUID,
    -- Coarse provenance for rate-limit / abuse review (hashed IP, not raw).
    source_ip_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_intake_briefs_created ON intake_briefs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intake_briefs_email ON intake_briefs (client_email);
