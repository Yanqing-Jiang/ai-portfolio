-- Durable acknowledgement for interrupted-run Redis reconciliation.
-- SQL is authoritative; Redis is only considered repaired after both the
-- terminal stream pair and run hash have been written successfully.
ALTER TABLE fortune_run
    ADD COLUMN IF NOT EXISTS recovery_published_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_fortune_run_recovery_pending
    ON fortune_run (finished_at, created_at)
    WHERE status = 'interrupted' AND recovery_published_at IS NULL;
