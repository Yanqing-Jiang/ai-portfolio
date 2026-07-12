BEGIN;

ALTER TABLE public.fortune_run
    DROP CONSTRAINT IF EXISTS fortune_run_status_check;
ALTER TABLE public.fortune_run
    ADD CONSTRAINT fortune_run_status_check CHECK (status IN (
        'queued', 'streaming', 'done', 'failed_guardrail', 'error', 'interrupted'
    ));

ALTER TABLE public.fortune_trace
    ADD COLUMN IF NOT EXISTS phase TEXT NOT NULL DEFAULT 'complete';
DROP INDEX IF EXISTS public.idx_fortune_trace_run_span;
CREATE UNIQUE INDEX IF NOT EXISTS idx_fortune_trace_run_span_phase
    ON public.fortune_trace (run_id, span_id, phase);

COMMIT;
