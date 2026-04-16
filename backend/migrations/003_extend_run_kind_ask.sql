-- 003_extend_run_kind_ask.sql
--
-- Extend fortune_run.run_kind to include 'ask' for free-form follow-up questions
-- routed through the triage agent with SQLAlchemySession memory.
--
-- Prior state (from 002_create_fortune_schema.sql):
--   run_kind CHECK (run_kind IN ('initial', 'action'))
--   consistency CHECK: 'initial' => action_type NULL, 'action' => action_type NOT NULL
--
-- New state:
--   run_kind CHECK (run_kind IN ('initial', 'action', 'ask'))
--   consistency CHECK: 'ask' rows also require action_type NULL
--
-- Idempotent: drops and recreates both CHECK constraints so reruns converge.

BEGIN;

-- Extend the run_kind enum-via-check to include 'ask'.
ALTER TABLE public.fortune_run
    DROP CONSTRAINT IF EXISTS fortune_run_run_kind_check;
ALTER TABLE public.fortune_run
    ADD CONSTRAINT fortune_run_run_kind_check
    CHECK (run_kind IN ('initial', 'action', 'ask'));

-- Relax the kind/action_type consistency constraint to permit 'ask' rows
-- (which, like 'initial', have no action_type).
ALTER TABLE public.fortune_run
    DROP CONSTRAINT IF EXISTS fortune_run_kind_action_type_consistency;
ALTER TABLE public.fortune_run
    ADD CONSTRAINT fortune_run_kind_action_type_consistency
    CHECK (
        (run_kind = 'initial' AND action_type IS NULL)
        OR
        (run_kind = 'action' AND action_type IS NOT NULL)
        OR
        (run_kind = 'ask' AND action_type IS NULL)
    );

COMMIT;
