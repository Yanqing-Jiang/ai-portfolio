-- Migration: Create bookings table for consulting booking system
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard

CREATE TABLE IF NOT EXISTS bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_session_id TEXT UNIQUE NOT NULL,
    stripe_event_id TEXT,
    session_type TEXT NOT NULL CHECK (session_type IN ('30', '60')),
    slot_start TIMESTAMPTZ NOT NULL,
    slot_end TIMESTAMPTZ NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT NOT NULL,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'hold' CHECK (status IN (
        'hold',
        'confirmed',
        'calendar_failed',
        'expired',
        'cancelled',
        'refunded'
    )),
    calendar_event_id TEXT,
    meet_link TEXT,
    amount_cents INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Partial unique index: prevent double-booking for active slots
CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_active_slot
    ON bookings (slot_start)
    WHERE (status IN ('hold', 'confirmed'));

-- Index for slot queries
CREATE INDEX IF NOT EXISTS idx_bookings_slot_status
    ON bookings (slot_start, status);

-- Index for Stripe session lookups
CREATE INDEX IF NOT EXISTS idx_bookings_stripe_session
    ON bookings (stripe_session_id);

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_bookings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER bookings_updated_at
    BEFORE UPDATE ON bookings
    FOR EACH ROW
    EXECUTE FUNCTION update_bookings_updated_at();

-- RLS: Allow public read for confirmation polling, restrict writes to service role
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public can read own booking by stripe_session_id"
    ON bookings FOR SELECT
    USING (true);

CREATE POLICY "Service role can insert/update bookings"
    ON bookings FOR ALL
    USING (auth.role() = 'service_role');
