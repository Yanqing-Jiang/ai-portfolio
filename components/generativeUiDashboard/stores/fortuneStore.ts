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
} from '../lib/fortuneTypes';

export interface TraceEvent {
    id?: string;
    run_id?: string;
    fortune_id?: string;
    payload: Record<string, unknown>;
    receivedAt: string;
}

export interface AskTurn {
    id: string;
    role: 'user' | 'agent';
    content: string;
    timestampISO: string;
    /** Present on agent turns sourced from /ask — used by Glass Box drawer. */
    runId?: string;
    /** Narrative payload on agent turns; string `content` is a render fallback. */
    narrative?: unknown;
    /** True when the turn was answered without ask-session memory. */
    degradedMemory?: boolean;
}

interface FortuneStateShape {
    fortuneId: string | null;
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

    // Actions
    setFortune: (fortuneId: string, runId: string, opts?: { persistenceDegraded?: boolean; functionId?: FortuneFunctionId }) => void;
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
    failAsk: (errorMessage: string) => void;
    clearAskHistory: () => void;
    reset: () => void;
}

type ActionKeys = 'setFortune' | 'setRunId' | 'setStatus' | 'setNarrativeReady' | 'applyPatch' | 'hydrateFromReplay' | 'appendTraceEvent' | 'setAskInput' | 'beginAsk' | 'finishAsk' | 'failAsk' | 'clearAskHistory' | 'reset';

const INITIAL: Omit<FortuneStateShape, ActionKeys> = {
    fortuneId: null,
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
};

export const useFortuneStore = create<FortuneStateShape>()(
    immer((set) => ({
        ...INITIAL,

        setFortune: (fortuneId, runId, opts) =>
            set((s) => {
                if (s.fortuneId && s.fortuneId !== fortuneId) {
                    s.askHistory = [];
                    s.askMemoryEverDegraded = false;
                    s.dataModel = null;
                    s.lastSeq = 0;
                    // Clear narrativeReady on fortune change so the
                    // "Verifying safety…" banner doesn't bleed across
                    // sessions during a same-tab create→create flow.
                    s.narrativeReady = false;
                    s.traceEvents = [];
                }
                s.fortuneId = fortuneId;
                s.runId = runId;
                s.persistenceDegraded = !!opts?.persistenceDegraded;
                if (opts?.functionId) s.functionId = opts.functionId;
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
                s.fortuneId = replay.fortune_id;
                s.runId = replay.run_id;
                s.functionId = replay.function_id;
                s.lastSeq = replay.last_seq;
                s.status = replay.status === 'complete' ? 'complete' : replay.status === 'error' ? 'error' : 'loading';
                s.persistenceDegraded = !!replay.metadata?.persistence_degraded;
                s.dataModel = replay.data_model;
                s.askHistory = replay.ask_history || [];
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

        setAskInput: (v) =>
            set((s) => {
                s.askInput = v;
            }),

        beginAsk: (turn) =>
            set((s) => {
                s.askHistory.push(turn);
                s.askLoading = true;
                s.askInput = '';
            }),

        finishAsk: (turn) =>
            set((s) => {
                s.askHistory.push(turn);
                s.askLoading = false;
                if (turn.degradedMemory) s.askMemoryEverDegraded = true;
            }),

        failAsk: (errorMessage) =>
            set((s) => {
                s.askHistory.push({
                    id: `err-${Date.now()}`,
                    role: 'agent',
                    content: errorMessage,
                    timestampISO: new Date().toISOString(),
                });
                s.askLoading = false;
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
