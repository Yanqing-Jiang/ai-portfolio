-- Snapshot v2 dual-write columns (Phase 3A).
-- Already applied to live Supabase; this file documents the ALTER for fresh installs.
--
-- schema_version: 1 = legacy latest_* only; 2 = also carries data_model JSONB
--   (accumulated A2UI FortuneDataModel). Distinct from snapshot_version (ETag
--   revision counter bumped on every upsert).
-- data_model: camelCase FortuneDataModel blob mirroring the frontend Zustand store.

BEGIN;

ALTER TABLE public.fortune_snapshot
    ADD COLUMN IF NOT EXISTS schema_version integer NOT NULL DEFAULT 1;

ALTER TABLE public.fortune_snapshot
    ADD COLUMN IF NOT EXISTS data_model jsonb;

COMMIT;
