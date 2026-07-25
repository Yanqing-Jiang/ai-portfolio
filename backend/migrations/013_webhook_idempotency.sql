-- 013 — make Stripe webhook idempotency enforceable instead of advisory.
--
-- The handler does `SELECT ... WHERE stripe_event_id = $1` and returns early if a
-- row is found. That is a read-then-act with no lock and, until now, no index at
-- all on the column: two concurrent deliveries of the SAME event both saw "not
-- processed" and both ran, so a payment could produce two calendar events and two
-- confirmation emails. Stripe retries on any non-2xx, so concurrent redelivery is
-- a normal occurrence, not a rare one.
--
-- A partial UNIQUE index makes the second writer fail at the UPDATE instead, which
-- the handler turns into an idempotent no-op. Partial because most rows have a NULL
-- stripe_event_id (free bookings, and paid holds before their webhook lands) and
-- NULLs must stay unconstrained.
--
-- Idempotent: drop-then-create, because the container applies migrations on boot.

DROP INDEX IF EXISTS idx_bookings_stripe_event_unique;
CREATE UNIQUE INDEX idx_bookings_stripe_event_unique
    ON bookings (stripe_event_id)
    WHERE stripe_event_id IS NOT NULL;

-- 'cancelling' is a claim marker: cancel flips 'confirmed' -> 'cancelling' before
-- issuing the Stripe refund, so two concurrent cancellations cannot both refund.
-- It is deliberately NOT an occupying status — a cancellation in progress has
-- already released its slot.
--
-- DEBT: a crash between the claim and the final 'cancelled'/'refunded' write
-- leaves the row stuck in 'cancelling', and nothing sweeps it back. Upgrade to a
-- timestamped claim + sweep when cancellations become routine, or on the first
-- stuck row observed.
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_status_check;
ALTER TABLE bookings ADD CONSTRAINT bookings_status_check CHECK (status IN (
    'hold', 'confirmed', 'calendar_failed', 'expired', 'cancelled',
    'refunded', 'rescheduled', 'blocked', 'cancelling'
));
