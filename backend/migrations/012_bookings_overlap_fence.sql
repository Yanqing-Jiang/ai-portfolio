-- 002 — the bookings table becomes the single authoritative availability ledger.
--
-- Two things happen here:
--   1. Owner busy-time becomes a row ('blocked' / session_type 'block') instead of
--      a second table, so availability stays ONE query over ONE ledger.
--   2. A range-exclusion constraint replaces the identical-start unique index.
--
-- Why the constraint matters more than the index it replaces: the old index only
-- caught two rows with the *same* slot_start. A 60-minute booking at 13:00 and a
-- 30-minute one at 13:30 have different starts, so nothing stopped them — and the
-- paid checkout path had no application-level overlap guard at all. This fence is
-- enforced by the database on INSERT and UPDATE, so it holds even for a writer
-- that forgets to check.
--
-- No extension is required: a pure range && constraint uses the built-in gist
-- range_ops opclass. (btree_gist would only be needed to mix in scalar equality,
-- e.g. `WITH =` on a column.)

-- Every statement is drop-then-add so the file is safe to re-run: the container
-- applies migrations on boot, and a non-idempotent one that has already been
-- applied by hand takes the whole backend down on "already exists".

ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_status_check;
ALTER TABLE bookings ADD CONSTRAINT bookings_status_check CHECK (status IN (
    'hold', 'confirmed', 'calendar_failed', 'expired', 'cancelled',
    'refunded', 'rescheduled', 'blocked'
));

ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_session_type_check;
ALTER TABLE bookings ADD CONSTRAINT bookings_session_type_check CHECK (
    session_type IN ('30', '60', 'block')
);

ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_no_overlap;
ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap
    EXCLUDE USING gist (tstzrange(slot_start, slot_end, '[)') WITH &&)
    WHERE (status IN ('hold', 'confirmed', 'calendar_failed', 'blocked'));

DROP INDEX IF EXISTS idx_bookings_slot_unique;
