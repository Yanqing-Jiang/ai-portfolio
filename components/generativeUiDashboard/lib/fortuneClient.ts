/**
 * fortuneClient — typed HTTP client for the /api/fortune surface.
 *
 * Centralises every call the frontend makes to the Ming Engine backend so
 * components consume semantic methods (`createFortune`, `submitAction`,
 * `askFollowUp`) instead of raw `fetch` + URL templating. That gives us:
 *
 * - one place to attach auth headers (and future request IDs / tracing)
 * - typed request / response shapes matched to the Python Pydantic models
 * - graceful handling of the backend's `X-Fortune-Persistence: degraded`
 *   and `degraded_memory` signals, so UI can render a soft "offline-ish"
 *   indicator instead of treating it as a hard failure
 *
 * Error policy: every method throws a `FortuneApiError` with `.status` and
 * `.requestId` so callers can branch on transport failures (offline, 5xx)
 * vs business errors (409 waiting for initial read, 429 rate limited).
 *
 * Routing: production calls target the Cloudflare Pages BFF layer
 * (`functions/api/fortune/*`) which sits in front of the Mac Mini backend
 * and injects a request id + CF-trusted client IP. Local dev bypasses the
 * BFF because Pages Functions are only mounted on the deployed origin —
 * see `_apiBase()` below for the switch. `/stream` intentionally stays
 * direct-to-backend even in prod: EventSource through a CF Pages Function
 * loses the backend's heartbeat flush semantics and the BFF adds nothing
 * for an SSE hot path (no body to log, no rate limit benefit at the
 * per-event granularity).
 */

import { configService } from '../../../services/config';
import { authService } from '../../../services/auth';

// ---------------------------------------------------------------------------
// Request / response types — match backend Pydantic shapes in
// backend/fortune/routes.py.
// ---------------------------------------------------------------------------

export interface PersonBirthInfo {
    birth_iso: string;
    timezone?: string;
    gender?: string;
    birth_time_unknown?: boolean;
    name?: string;
}

export interface CreateFortuneRequest {
    birth_iso: string;
    timezone?: string;
    focus?: string;
    question?: string;
    tone?: string;
    birth_time_unknown?: boolean;
    gender?: string;
    /** Second person for compatibility flow. Backend computes a second
     * foundation when this is present and focus starts with "compatibility:". */
    person_b?: PersonBirthInfo;
}

export interface CreateFortuneResponse {
    fortune_id: string;
    run_id: string;
    surface_id: string;
    /** True when Supabase persistence was unavailable — hot path still works. */
    persistenceDegraded: boolean;
}

export interface ActionResponse {
    fortune_id: string;
    run_id: string;
    action_id: string;
    focus: string | null;
    status: string;
    stream_url: string;
}

export interface AskResponse {
    fortune_id: string;
    run_id: string;
    narrative: {
        tldr: string;
        insights: Array<{
            id: string;
            icon: string;
            heading: string;
            tagline: string;
            bullets: Array<{ icon: string; text: string }>;
            citations?: string[];
        }>;
        year_predictions?: Array<{
            year: number;
            prediction: string;
            confidence: number;
            evidence_refs?: string[];
        }>;
    };
    degraded_memory: boolean;
}

export class FortuneApiError extends Error {
    constructor(
        message: string,
        public readonly status: number,
        public readonly requestId: string | null = null,
        public readonly body?: unknown,
    ) {
        super(message);
        this.name = 'FortuneApiError';
    }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Resolve the origin for JSON fortune calls.
 *
 * Deployed origins (yanqing.app / *.pages.dev) host the Pages Function BFF
 * at `/api/fortune/*`, so an empty base string sends the request same-origin
 * and the BFF forwards it. Anywhere else — local dev, preview tunnels — the
 * request goes straight to the Python backend since there is no BFF mounted.
 */
function _apiBase(): string {
    if (typeof window === 'undefined') {
        return configService.getBackendUrl();
    }
    const host = window.location.hostname;
    const bffHosted =
        host === 'yanqing.app' ||
        host.endsWith('.yanqing.app') ||
        host.endsWith('.pages.dev');
    return bffHosted ? '' : configService.getBackendUrl();
}

async function jsonFetch<T>(
    path: string,
    init: RequestInit = {},
): Promise<{ data: T; headers: Headers }> {
    const base = _apiBase();
    const authHeaders = await authService.getAuthHeaders();
    const res = await fetch(`${base}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...authHeaders,
            ...(init.headers as Record<string, string> | undefined),
        },
    });

    const requestId = res.headers.get('x-request-id');
    if (!res.ok) {
        let body: unknown = undefined;
        try { body = await res.json(); } catch { /* non-JSON error — ignore */ }
        const detail =
            (body && typeof body === 'object' && 'detail' in body && typeof (body as { detail?: unknown }).detail === 'string')
                ? (body as { detail: string }).detail
                : `Server error ${res.status}`;
        throw new FortuneApiError(detail, res.status, requestId, body);
    }

    const data = (await res.json()) as T;
    return { data, headers: res.headers };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

// Fortune replay response — matches backend GET /api/fortune/{id}
interface BackendReplaySnapshot {
    fortune_id: string;
    snapshot_version?: number;
    status: string;
    metadata: {
        created_at: string;
        persistence_degraded?: boolean;
        function_id?: string;
    };
    data: {
        overview?: Record<string, unknown>;
        pillars?: Record<string, unknown>;
        mechanics?: Record<string, unknown>;
        narrative?: Record<string, unknown>;
        trace?: Record<string, unknown>;
        references?: Record<string, unknown>;
        retrodictions?: Record<string, unknown>;
        corrections?: Record<string, unknown>;
    };
}

export const fortuneClient = {
    async createFortune(req: CreateFortuneRequest): Promise<CreateFortuneResponse> {
        const { data, headers } = await jsonFetch<Omit<CreateFortuneResponse, 'persistenceDegraded'>>(
            '/api/fortune/create',
            { method: 'POST', body: JSON.stringify(req) },
        );
        return {
            ...data,
            persistenceDegraded: headers.get('x-fortune-persistence') === 'degraded',
        };
    },

    async submitAction(
        fortuneId: string,
        actionId: string,
        payload: Record<string, unknown> = {},
    ): Promise<ActionResponse> {
        const { data } = await jsonFetch<ActionResponse>(
            `/api/fortune/${fortuneId}/action`,
            { method: 'POST', body: JSON.stringify({ action_id: actionId, payload }) },
        );
        return data;
    },

    async askFollowUp(fortuneId: string, question: string): Promise<AskResponse> {
        const { data } = await jsonFetch<AskResponse>(
            `/api/fortune/${fortuneId}/ask`,
            { method: 'POST', body: JSON.stringify({ question }) },
        );
        return data;
    },

    async submitCorrection(
        fortuneId: string,
        year: number,
        userNote: string,
    ): Promise<{ year: number; correction: { user_note: string; corrected_at: string } }> {
        const { data } = await jsonFetch<{ year: number; correction: { user_note: string; corrected_at: string } }>(
            `/api/fortune/${fortuneId}/correction`,
            { method: 'POST', body: JSON.stringify({ year, user_note: userNote }) },
        );
        return data;
    },

    // Typed create methods for each fortune function
    async createWish(req: {
        profile: { birth_iso: string; timezone?: string; birth_time_unknown?: boolean; gender?: string };
        question: string;
        focus?: string;
        tone?: string;
    }): Promise<CreateFortuneResponse> {
        return this.createFortune({
            birth_iso: req.profile.birth_iso,
            timezone: req.profile.timezone,
            birth_time_unknown: req.profile.birth_time_unknown,
            gender: req.profile.gender,
            question: req.question,
            focus: req.focus || 'custom_wish',
            tone: req.tone,
        });
    },

    async createLuckCycle(req: {
        profile: { birth_iso: string; timezone?: string; birth_time_unknown?: boolean; gender?: string };
        horizon: string;
        focus: string;
    }): Promise<CreateFortuneResponse> {
        return this.createFortune({
            birth_iso: req.profile.birth_iso,
            timezone: req.profile.timezone,
            birth_time_unknown: req.profile.birth_time_unknown,
            gender: req.profile.gender,
            focus: `luck_cycle:${req.focus}:${req.horizon}`,
        });
    },

    async createCompatibility(req: {
        relationship: string;
        personA: { birth_iso: string; timezone?: string; gender?: string; birth_time_unknown?: boolean; name?: string };
        personB: { birth_iso: string; timezone?: string; gender?: string; birth_time_unknown?: boolean; name?: string };
        question?: string;
    }): Promise<CreateFortuneResponse> {
        return this.createFortune({
            birth_iso: req.personA.birth_iso,
            timezone: req.personA.timezone,
            gender: req.personA.gender,
            birth_time_unknown: req.personA.birth_time_unknown,
            focus: `compatibility:${req.relationship}`,
            question: req.question,
            person_b: {
                birth_iso: req.personB.birth_iso,
                timezone: req.personB.timezone,
                gender: req.personB.gender,
                birth_time_unknown: req.personB.birth_time_unknown,
                name: req.personB.name,
            },
        });
    },

    async createLuckyDay(req: {
        profile: { birth_iso: string; timezone?: string; gender?: string };
        occasion: string;
        windowStartISO: string;
        windowEndISO: string;
    }): Promise<CreateFortuneResponse> {
        return this.createFortune({
            birth_iso: req.profile.birth_iso,
            timezone: req.profile.timezone,
            gender: req.profile.gender,
            focus: `occasion:${req.occasion}:${req.windowStartISO}:${req.windowEndISO}`,
        });
    },

    /**
     * Fetch a completed fortune snapshot for replay.
     * 200 → mapped response, 202 → null (still pending), 404/503 → throw
     */
    async getFortune(fortuneId: string, opts?: { signal?: AbortSignal }): Promise<BackendReplaySnapshot | null> {
        const base = _apiBase();
        const authHeaders = await authService.getAuthHeaders();
        const res = await fetch(`${base}/api/fortune/${fortuneId}`, {
            headers: { ...authHeaders },
            signal: opts?.signal,
        });

        if (res.status === 202) return null; // still pending
        if (!res.ok) {
            const requestId = res.headers.get('x-request-id');
            let body: unknown;
            try { body = await res.json(); } catch { /* ignore */ }
            throw new FortuneApiError(
                `Fortune ${res.status}`,
                res.status,
                requestId,
                body,
            );
        }

        return (await res.json()) as BackendReplaySnapshot;
    },

    /**
     * Pause / cancel an in-flight reading. Sets ``cancel_requested`` on the
     * backend session; the SSE stream loop sees the flag on its next event
     * boundary, calls the Agents SDK ``stream_result.cancel()`` gracefully,
     * and closes the stream with a ``Reading paused by user`` progress event.
     * Idempotent — safe to call if the reading already completed.
     */
    async cancelFortune(fortuneId: string): Promise<void> {
        const base = _apiBase();
        const authHeaders = await authService.getAuthHeaders();
        await fetch(`${base}/api/fortune/${fortuneId}/cancel`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...authHeaders },
        });
    },

    /**
     * Build the SSE stream URL. Kept as a string builder (not a fetch wrapper)
     * because the browser's EventSource consumes a URL directly.
     *
     * `/stream` is intentionally direct-to-backend in all environments —
     * see the file header for rationale. Auth is forwarded on the query
     * string because EventSource cannot set request headers.
     */
    buildStreamUrl(fortuneId: string, accessToken: string | null): string {
        const base = `${configService.getBackendUrl()}/api/fortune/${fortuneId}/stream`;
        return accessToken ? `${base}?token=${encodeURIComponent(accessToken)}` : base;
    },
};

export type FortuneClient = typeof fortuneClient;
