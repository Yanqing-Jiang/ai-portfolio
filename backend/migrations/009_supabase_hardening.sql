-- 009: Harden public-schema grants, RLS, privileged functions, and extensions.
--
-- This migration records the final database state after the corresponding
-- manual production hardening. It is safe to run both on that converged state
-- and on a clean database bootstrapped through migrations 001-008.

-- Prevent future objects created by postgres from being exposed implicitly.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE EXECUTE ON FUNCTIONS FROM anon, authenticated;

-- Remove all Data API privileges from the private fortune domain.
REVOKE ALL PRIVILEGES ON TABLE
    public.fortune,
    public.fortune_ask_request,
    public.fortune_event,
    public.fortune_message,
    public.fortune_public_share,
    public.fortune_run,
    public.fortune_snapshot,
    public.fortune_trace
FROM anon, authenticated;

-- The sequences exist on a normal bootstrap, but guard their generated names.
DO $do$
BEGIN
    IF to_regclass('public.fortune_event_id_seq') IS NOT NULL THEN
        EXECUTE
            'REVOKE ALL PRIVILEGES ON SEQUENCE public.fortune_event_id_seq '
            'FROM anon, authenticated';
    END IF;

    IF to_regclass('public.fortune_trace_id_seq') IS NOT NULL THEN
        EXECUTE
            'REVOKE ALL PRIVILEGES ON SEQUENCE public.fortune_trace_id_seq '
            'FROM anon, authenticated';
    END IF;

    -- This legacy dataset is provisioned outside the checked-in migrations.
    IF to_regclass('public.comp_financials') IS NOT NULL THEN
        EXECUTE
            'REVOKE ALL PRIVILEGES ON TABLE public.comp_financials '
            'FROM anon, authenticated';
    END IF;
END
$do$;

-- Preserve the anonymous keepalive contract while making every row invisible.
DROP POLICY IF EXISTS "Public can read own booking by stripe_session_id"
    ON public.bookings;
DROP POLICY IF EXISTS "Service role can insert/update bookings"
    ON public.bookings;
DROP POLICY IF EXISTS bookings_anon_keepalive_deny
    ON public.bookings;

ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE public.bookings FROM anon, authenticated;
GRANT SELECT ON TABLE public.bookings TO anon;

CREATE POLICY bookings_anon_keepalive_deny
    ON public.bookings
    AS RESTRICTIVE
    FOR SELECT
    TO anon
    USING (false);

-- Retire the orphaned memory experiment without cascading through dependencies.
-- The vector type may already have moved from public to extensions.
DO $do$
DECLARE
    function_signature TEXT;
    target_function REGPROCEDURE;
BEGIN
    FOREACH function_signature IN ARRAY ARRAY[
        'public.match_memory_documents(public.vector,double precision,integer)',
        'public.match_memory_documents(extensions.vector,double precision,integer)'
    ]
    LOOP
        target_function := NULL;
        BEGIN
            target_function := to_regprocedure(function_signature);
        EXCEPTION
            WHEN undefined_object OR invalid_schema_name THEN
                NULL;
        END;
        IF target_function IS NOT NULL THEN
            EXECUTE format('DROP FUNCTION %s RESTRICT', target_function);
        END IF;
    END LOOP;
END
$do$;

DROP FUNCTION IF EXISTS public.search_memory_fulltext(text, integer);
DROP TABLE IF EXISTS public.memory_documents RESTRICT;

-- Restrict retained SECURITY DEFINER RPCs to trusted roles only.
DO $do$
DECLARE
    function_signature TEXT;
    target_function REGPROCEDURE;
BEGIN
    FOREACH function_signature IN ARRAY ARRAY[
        'public.get_similar_queries(public.vector,double precision,integer,uuid)',
        'public.get_similar_queries(extensions.vector,double precision,integer,uuid)'
    ]
    LOOP
        target_function := NULL;
        BEGIN
            target_function := to_regprocedure(function_signature);
        EXCEPTION
            WHEN undefined_object OR invalid_schema_name THEN
                NULL;
        END;
        EXIT WHEN target_function IS NOT NULL;
    END LOOP;

    IF target_function IS NOT NULL THEN
        EXECUTE format(
            'REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC, anon, authenticated',
            target_function
        );
        EXECUTE format(
            'GRANT EXECUTE ON FUNCTION %s TO postgres, service_role',
            target_function
        );
    END IF;

    target_function := to_regprocedure(
        'public.increment_analytics_metrics(uuid,integer,integer,integer,bigint,bigint)'
    );
    IF target_function IS NOT NULL THEN
        EXECUTE format(
            'REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC, anon, authenticated',
            target_function
        );
        EXECUTE format(
            'GRANT EXECUTE ON FUNCTION %s TO postgres, service_role',
            target_function
        );
    END IF;
END
$do$;

-- Pin every retained function to the narrowest trusted search path its body uses.
DO $do$
DECLARE
    function_signature TEXT;
    safe_search_path TEXT;
    target_function REGPROCEDURE;
BEGIN
    FOR function_signature, safe_search_path IN
        SELECT *
        FROM (VALUES
            ('public.update_updated_at()',
             'pg_catalog, pg_temp'),
            ('public.set_updated_at_now()',
             'pg_catalog, pg_temp'),
            ('public.update_analytics_updated_at()',
             'pg_catalog, pg_temp'),
            ('public.update_bookings_updated_at()',
             'pg_catalog, pg_temp'),
            ('public.update_session_activity()',
             'pg_catalog, public, pg_temp'),
            ('public.cleanup_expired_artifacts()',
             'pg_catalog, public, pg_temp'),
            ('public.get_user_cache_stats(uuid)',
             'pg_catalog, public, pg_temp'),
            ('public.cleanup_expired_analytics_sessions()',
             'pg_catalog, public, pg_temp'),
            ('public.increment_analytics_metrics(uuid,integer,integer,integer,bigint,bigint)',
             'pg_catalog, public, pg_temp')
        ) AS function_config(signature, search_path)
    LOOP
        target_function := to_regprocedure(function_signature);
        IF target_function IS NOT NULL THEN
            EXECUTE format(
                'ALTER FUNCTION %s SET search_path = %s',
                target_function,
                safe_search_path
            );
        END IF;
    END LOOP;

    FOREACH function_signature IN ARRAY ARRAY[
        'public.get_similar_queries(public.vector,double precision,integer,uuid)',
        'public.get_similar_queries(extensions.vector,double precision,integer,uuid)'
    ]
    LOOP
        target_function := NULL;
        BEGIN
            target_function := to_regprocedure(function_signature);
        EXCEPTION
            WHEN undefined_object OR invalid_schema_name THEN
                NULL;
        END;
        EXIT WHEN target_function IS NOT NULL;
    END LOOP;

    IF target_function IS NOT NULL THEN
        EXECUTE format(
            'ALTER FUNCTION %s '
            'SET search_path = pg_catalog, public, extensions, pg_temp',
            target_function
        );
    END IF;
END
$do$;

-- Remove pg_trgm only when RESTRICT proves that no outside dependency remains.
DO $do$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_extension
        WHERE extname = 'pg_trgm'
    ) THEN
        BEGIN
            EXECUTE 'DROP EXTENSION IF EXISTS pg_trgm RESTRICT';
        EXCEPTION
            WHEN dependent_objects_still_exist THEN
                RAISE NOTICE
                    'pg_trgm retained because dependent objects still exist';
        END;
    END IF;
END
$do$;

-- Keep vector, but move its objects out of public after vector functions are pinned.
DO $do$
DECLARE
    vector_schema NAME;
BEGIN
    SELECT namespace.nspname
    INTO vector_schema
    FROM pg_catalog.pg_extension AS extension
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = extension.extnamespace
    WHERE extension.extname = 'vector';

    IF vector_schema IS NOT NULL AND vector_schema <> 'extensions' THEN
        EXECUTE 'ALTER EXTENSION vector SET SCHEMA extensions';
    END IF;
END
$do$;

NOTIFY pgrst, 'reload schema';
