-- Durable Ask idempotency: an ambiguous client/BFF timeout may be retried with
-- the same UUID without creating a second model run or conversation turn.

BEGIN;

-- The live Redis projection intentionally omits heavyweight analysis objects.
-- Keep the original reading intent (including compatibility Person B) beside
-- the durable mechanics so a cold/restarted Ask can reconstruct the same
-- specialist context as the initial run.
ALTER TABLE public.fortune_snapshot
    ADD COLUMN IF NOT EXISTS request_context JSONB;

-- Preserve all reconstructable primary-chart intent on upgrades. Compatibility
-- Person B is recovered from its stored chart mechanics when old rows predate
-- request_context.
UPDATE public.fortune_snapshot AS snapshot
SET request_context = jsonb_strip_nulls(jsonb_build_object(
    'birth_iso', fortune.birth_iso,
    'timezone', fortune.timezone,
    'gender', fortune.gender,
    'birth_time_unknown', fortune.birth_time_unknown,
    'focus', fortune.focus,
    'original_question', fortune.question,
    'tone', fortune.tone
))
FROM public.fortune AS fortune
WHERE snapshot.fortune_id = fortune.id
  AND snapshot.request_context IS NULL;

-- Ask turns are first-class runs in the activity rail. Migration 002's
-- original checks only admitted initial/action, causing the route's Ask run
-- insert to fail and silently fall back to an untracked random UUID.
ALTER TABLE public.fortune_run
    DROP CONSTRAINT IF EXISTS fortune_run_run_kind_check;
ALTER TABLE public.fortune_run
    ADD CONSTRAINT fortune_run_run_kind_check
    CHECK (run_kind IN ('initial', 'action', 'ask'));
ALTER TABLE public.fortune_run
    DROP CONSTRAINT IF EXISTS fortune_run_kind_action_type_consistency;
ALTER TABLE public.fortune_run
    ADD CONSTRAINT fortune_run_kind_action_type_consistency
    CHECK (
        (run_kind = 'initial' AND action_type IS NULL)
        OR (run_kind = 'action' AND action_type IS NOT NULL)
        OR (run_kind = 'ask' AND action_type IS NULL)
    );

CREATE TABLE IF NOT EXISTS public.fortune_ask_request (
    fortune_id UUID NOT NULL REFERENCES public.fortune(id) ON DELETE CASCADE,
    client_request_id UUID NOT NULL,
    payload_hash TEXT NOT NULL,
    lease_token UUID NOT NULL,
    delivery_id UUID NOT NULL,
    run_id UUID REFERENCES public.fortune_run(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'done', 'error')),
    response_json JSONB,
    session_items JSONB,
    conversation_committed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fortune_id, client_request_id),
    CHECK ((status = 'done') = (response_json IS NOT NULL)),
    CHECK (conversation_committed = FALSE OR status = 'done')
);

-- Safe if an early build created the table before delivery fencing existed.
ALTER TABLE public.fortune_ask_request
    ADD COLUMN IF NOT EXISTS delivery_id UUID;
ALTER TABLE public.fortune_ask_request
    ADD COLUMN IF NOT EXISTS run_id UUID REFERENCES public.fortune_run(id) ON DELETE SET NULL;
UPDATE public.fortune_ask_request
    SET delivery_id = gen_random_uuid() WHERE delivery_id IS NULL;
ALTER TABLE public.fortune_ask_request
    ALTER COLUMN delivery_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fortune_ask_request_updated
    ON public.fortune_ask_request (updated_at DESC);

-- The SDK owns these tables, so the delivery columns stay nullable for its
-- ordinary writes. Ask outbox writes supply both values and are uniquely
-- identified independently of message content or the configured history
-- window. This is what makes crash repair exactly-once.
ALTER TABLE public.agent_messages
    ADD COLUMN IF NOT EXISTS ask_delivery_id UUID,
    ADD COLUMN IF NOT EXISTS ask_delivery_index INTEGER;

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_messages_ask_delivery
    ON public.agent_messages (session_id, ask_delivery_id, ask_delivery_index)
    WHERE ask_delivery_id IS NOT NULL;

ALTER TABLE public.fortune_ask_request ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all_fortune_ask_request
    ON public.fortune_ask_request;
CREATE POLICY service_role_all_fortune_ask_request
    ON public.fortune_ask_request
    FOR ALL TO service_role USING (true) WITH CHECK (true);

COMMIT;
