-- 011: permit the training intake path in persisted briefs.

ALTER TABLE public.intake_briefs
    DROP CONSTRAINT IF EXISTS intake_briefs_path_check;

ALTER TABLE public.intake_briefs
    ADD CONSTRAINT intake_briefs_path_check
    CHECK (path IN ('business', 'individual', 'training', 'unknown'));

NOTIFY pgrst, 'reload schema';
