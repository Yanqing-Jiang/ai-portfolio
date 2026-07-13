/**
 * useFortuneStore — Zustand+Immer store for cross-component Ming Engine state.
 *
 * Why a store:
 * - The BaZi result page has several sibling tabs (Narrative, Mechanics,
 *   Sources, Ask) that all need to know the current fortune_id + run_id.
 *   Prop-drilling through `MingResultsTabs` → every tab component is noisy.
 * - The Ask tab's conversation thread must survive tab switches: users
 *   navigate Narrative → Ask → Narrative and expect prior Q&A still visible.
 *   Local component state resets on unmount; the store keeps it alive.
 * - The Activity Rail / Glass Box drawer (Task #13) will also listen to the
 *   same state to show "Run {run_id} — triage → career_focus" breadcrumbs.
 *
 * Kept intentionally small. SSE event state stays inside `useA2UIStream`'s
 * own reducer (it's event-sourced and bulky). This store only holds what is
 * durable across tab lifecycles.
 *
 * Immer middleware lets reducers mutate `draft` directly without spread
 * ceremony; Zustand applies the produced next-state immutably.
 */

import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type {
    FortuneFunctionId,
    FortuneDataModel,
    FortuneReplayResponse,
    FortuneStatus,
    AskContext,
    AskTurn,
} from '../lib/fortuneTypes';

export interface TraceEvent {
    id?: string;
    run_id?: string;
    fortune_id?: string;
    payload: Record<string, unknown>;
    receivedAt: string;
}

/** Allowlisted Glass Box projection — matches live payload.trace / GET /trace. */
export interface TraceProjection {
    eventId: string;
    runId?: string;
    spanId?: string;
    phase?: string;
    parentSpanId?: string | null;
    spanType?: string | null;
    agentName?: string | null;
    toolName?: string | null;
    model?: string | null;
    durationMs?: number | null;
    status?: string | null;
    argSummary?: string | null;
    resultSummary?: string | null;
    startedAt?: string | null;
    endedAt?: string | null;
}

export type { AskTurn } from '../lib/fortuneTypes';

interface FortuneStateShape {
    fortuneId: string | null;
    /** Monotonic navigation token; changes even when navigation returns A→B→A. */
    fortuneGeneration: number;
    /** Most recent run_id — rotates on /action and /ask. */
    runId: string | null;
    /** True when backend reported X-Fortune-Persistence: degraded. */
    persistenceDegraded: boolean;

    // Fortune data (new — streaming + replay)
    functionId: FortuneFunctionId | null;
    dataModel: FortuneDataModel | null;
    lastSeq: number;
    status: FortuneStatus;
    /** True once the narrative has finished streaming (the reading is
     * renderable) but the guardrail safety check is still in flight. PR5
     * of the latency refactor surfaces this as a "Verifying safety…"
     * banner in ThinkingPanel so users see the reading 3.5–4.5s sooner.
     * Resets on every new fortune via ``setFortune``/``reset``. */
    narrativeReady: boolean;

    // Ask tab
    askInput: string;
    askLoading: boolean;
    askHistory: AskTurn[];
    /** Sticky flag: once an ask turn returned without memory, we surface a hint. */
    askMemoryEverDegraded: boolean;

    /** Live Glass Box trace envelopes (payload.kind==='trace'); Phase 4 renders. */
    traceEvents: TraceEvent[];
    /** True when the reading was created without a known birth hour. */
    birthTimeUnknown: boolean;

    // Actions
    setFortune: (fortuneId: string, runId: string, opts?: { persistenceDegraded?: boolean; functionId?: FortuneFunctionId; birthTimeUnknown?: boolean }) => void;
    setBirthTimeUnknown: (value: boolean) => void;
    /** Replace traceEvents from GET /trace replay projections. */
    hydrateTraceProjections: (projections: TraceProjection[]) => void;
    setRunId: (runId: string) => void;
    setStatus: (status: FortuneStatus) => void;
    /** Mark the narrative as renderable (guardrail still in flight).
     * Called by ``useFortuneStream`` when ``/data/narrative`` arrives with
     * ``isComplete: true``. Idempotent — safe to call repeatedly. */
    setNarrativeReady: (ready: boolean) => void;
    /** Apply a streamed data update at a JSON-pointer path within dataModel. */
    applyPatch: (path: string, value: unknown) => void;
    /** Hydrate the full data model from a replay snapshot. */
    hydrateFromReplay: (replay: FortuneReplayResponse) => void;
    appendTraceEvent: (event: TraceEvent) => void;
    setAskInput: (v: string) => void;
    beginAsk: (userTurn: AskTurn) => void;
    finishAsk: (agentTurn: AskTurn) => void;
    failAsk: (errorMessage: string, retryQuestion: string, askContext: AskContext | undefined, clientRequestId: string, retryable: boolean) => void;
    retryAsk: (clientRequestId?: string) => void;
    hydrateAskHistory: (turns: AskTurn[]) => void;
    clearAskHistory: () => void;
    reset: () => void;
}

type ActionKeys = 'setFortune' | 'setRunId' | 'setStatus' | 'setNarrativeReady' | 'applyPatch' | 'hydrateFromReplay' | 'appendTraceEvent' | 'hydrateTraceProjections' | 'setBirthTimeUnknown' | 'setAskInput' | 'beginAsk' | 'finishAsk' | 'failAsk' | 'retryAsk' | 'hydrateAskHistory' | 'clearAskHistory' | 'reset';

const INITIAL: Omit<FortuneStateShape, ActionKeys> = {
    fortuneId: null,
    fortuneGeneration: 0,
    runId: null,
    persistenceDegraded: false,
    functionId: null,
    dataModel: null,
    lastSeq: 0,
    status: 'idle',
    narrativeReady: false,
    askInput: '',
    askLoading: false,
    askHistory: [],
    askMemoryEverDegraded: false,
    traceEvents: [],
    birthTimeUnknown: false,
};

export const useFortuneStore = create<FortuneStateShape>()(
    immer((set) => ({
        ...INITIAL,

        setFortune: (fortuneId, runId, opts) =>
            set((s) => {
                if (s.fortuneId !== fortuneId) {
                    s.fortuneGeneration += 1;
                }
                if (s.fortuneId && s.fortuneId !== fortuneId) {
                    s.askHistory = [];
                    s.askInput = '';
                    s.askLoading = false;
                    s.askMemoryEverDegraded = false;
                    s.dataModel = null;
                    s.lastSeq = 0;
                    // Clear narrativeReady on fortune change so the
                    // "Verifying safety…" banner doesn't bleed across
                    // sessions during a same-tab create→create flow.
                    s.narrativeReady = false;
                    s.traceEvents = [];
                    s.birthTimeUnknown = false;
                }
                s.fortuneId = fortuneId;
                s.runId = runId;
                s.persistenceDegraded = !!opts?.persistenceDegraded;
                if (opts?.functionId) s.functionId = opts.functionId;
                if (typeof opts?.birthTimeUnknown === 'boolean') {
                    s.birthTimeUnknown = opts.birthTimeUnknown;
                }
            }),

        setRunId: (runId) =>
            set((s) => {
                s.runId = runId;
            }),

        setStatus: (status) =>
            set((s) => {
                s.status = status;
            }),

        setNarrativeReady: (ready) =>
            set((s) => {
                s.narrativeReady = ready;
            }),

        applyPatch: (path, value) =>
            set((s) => {
                if (!s.dataModel) s.dataModel = {};
                // Strip /data/ prefix
                let clean = path;
                if (clean.startsWith('/data/')) clean = clean.slice(6);
                else if (clean.startsWith('/data')) clean = clean.slice(5);
                if (clean.startsWith('/')) clean = clean.slice(1);

                if (!clean) {
                    // Root merge
                    Object.assign(s.dataModel, value);
                    return;
                }

                const segments = clean.split('/');
                let current: Record<string, unknown> = s.dataModel as Record<string, unknown>;
                for (let i = 0; i < segments.length - 1; i++) {
                    const seg = segments[i];
                    if (!current[seg] || typeof current[seg] !== 'object') {
                        current[seg] = {};
                    }
                    current = current[seg] as Record<string, unknown>;
                }
                const last = segments[segments.length - 1];
                const existing = current[last];
                if (existing && typeof existing === 'object' && typeof value === 'object' && value && !Array.isArray(existing)) {
                    Object.assign(existing as Record<string, unknown>, value as Record<string, unknown>);
                } else {
                    current[last] = value;
                }
            }),

        hydrateFromReplay: (replay) =>
            set((s) => {
                const fortuneChanged = s.fortuneId !== replay.fortune_id;
                if (fortuneChanged) {
                    s.fortuneGeneration += 1;
                }
                s.fortuneId = replay.fortune_id;
                s.runId = replay.run_id;
                s.functionId = replay.function_id;
                s.lastSeq = replay.last_seq;
                s.status = replay.status === 'complete' ? 'complete' : replay.status === 'error' ? 'error' : 'loading';
                s.persistenceDegraded = !!replay.metadata?.persistence_degraded;
                s.birthTimeUnknown = !!replay.metadata?.birth_time_unknown;
                s.dataModel = replay.data_model;
                if (fortuneChanged || (replay.ask_history?.length ?? 0) > 0) {
                    s.askHistory = replay.ask_history || [];
                }
                if (fortuneChanged) {
                    s.askInput = '';
                    s.askLoading = false;
                    s.askMemoryEverDegraded = false;
                }
                // A replay snapshot whose narrative already streamed has
                // ``narrative.isComplete = true`` baked into ``data_model``.
                // Pre-set the flag so the page header doesn't briefly flash
                // the "Verifying safety…" banner during hydration.
                const narrativeBlock = (replay.data_model as { narrative?: { isComplete?: boolean } } | null)?.narrative;
                s.narrativeReady = !!narrativeBlock?.isComplete;
            }),

        appendTraceEvent: (event) =>
            set((s) => {
                s.traceEvents.push(event);
                if (s.traceEvents.length > 500) {
                    s.traceEvents.splice(0, s.traceEvents.length - 500);
                }
            }),

        hydrateTraceProjections: (projections) =>
            set((s) => {
                const now = new Date().toISOString();
                s.traceEvents = projections.map((trace) => ({
                    id: trace.eventId,
                    run_id: trace.runId,
                    payload: { kind: 'trace', trace },
                    receivedAt: now,
                }));
            }),

        setBirthTimeUnknown: (value) =>
            set((s) => {
                s.birthTimeUnknown = value;
            }),

        setAskInput: (v) =>
            set((s) => {
                s.askInput = v;
            }),

        beginAsk: (turn) =>
            set((s) => {
                s.askHistory.push({ ...turn, pending: true });
                s.askLoading = true;
                s.askInput = '';
            }),

        finishAsk: (turn) =>
            set((s) => {
                const pending = s.askHistory.find(
                    (item) => item.pending && item.clientRequestId === turn.clientRequestId,
                );
                if (pending) pending.pending = false;
                s.askHistory.push(turn);
                s.askLoading = false;
                if (turn.degradedMemory) s.askMemoryEverDegraded = true;
            }),

        failAsk: (errorMessage, retryQuestion, askContext, clientRequestId, retryable) =>
            set((s) => {
                const pending = s.askHistory.find(
                    (item) => item.pending && item.clientRequestId === clientRequestId,
                );
                if (pending) pending.pending = false;
                s.askHistory.push({
                    id: `err-${Date.now()}`,
                    role: 'agent',
                    content: errorMessage,
                    timestampISO: new Date().toISOString(),
                    error: true,
                    retryable,
                    retryQuestion,
                    askContext,
                    clientRequestId,
                });
                s.askLoading = false;
            }),

        retryAsk: (clientRequestId) =>
            set((s) => {
                s.askHistory = s.askHistory.filter(
                    (turn) => !(turn.error && turn.clientRequestId === clientRequestId),
                );
                const retryingQuestion = s.askHistory.find(
                    (turn) => turn.role === 'user' && turn.clientRequestId === clientRequestId,
                );
                if (retryingQuestion) retryingQuestion.pending = true;
                s.askLoading = true;
            }),

        hydrateAskHistory: (turns) =>
            set((s) => {
                if (!turns.length) return;
                // Durable history is authoritative. Preserve only an explicitly
                // pending optimistic question or a retryable failed exchange;
                // role/content multiset matching cannot correctly pair
                // intentionally repeated questions.
                const recoveryIds = new Set(
                    s.askHistory
                        .filter((turn) => turn.error && turn.retryable && turn.clientRequestId)
                        .map((turn) => turn.clientRequestId as string),
                );
                const durableIds = new Set(
                    turns
                        .filter((turn) => turn.clientRequestId)
                        .map((turn) => turn.clientRequestId as string),
                );
                const recoverableLocal = s.askHistory.filter((turn) => (
                    !turn.clientRequestId || !durableIds.has(turn.clientRequestId)
                ) && (
                    turn.pending || recoveryIds.has(turn.clientRequestId as string)
                ));
                s.askHistory = [...turns, ...recoverableLocal];
            }),

        clearAskHistory: () =>
            set((s) => {
                s.askHistory = [];
                s.askMemoryEverDegraded = false;
            }),

        reset: () =>
            set((s) => {
                Object.assign(s, INITIAL);
                // Object.assign copies the keys we wrote, but
                // ``narrativeReady`` is a primitive so it's already
                // covered. Defensive belt-and-braces in case INITIAL grows
                // additional nested defaults later.
                s.narrativeReady = false;
            }),
    })),
);
