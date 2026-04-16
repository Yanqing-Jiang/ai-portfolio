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

    // Ask tab
    askInput: string;
    askLoading: boolean;
    askHistory: AskTurn[];
    /** Sticky flag: once an ask turn returned without memory, we surface a hint. */
    askMemoryEverDegraded: boolean;

    // Actions
    setFortune: (fortuneId: string, runId: string, opts?: { persistenceDegraded?: boolean }) => void;
    setRunId: (runId: string) => void;
    setAskInput: (v: string) => void;
    beginAsk: (userTurn: AskTurn) => void;
    finishAsk: (agentTurn: AskTurn) => void;
    failAsk: (errorMessage: string) => void;
    clearAskHistory: () => void;
    reset: () => void;
}

const INITIAL: Omit<
    FortuneStateShape,
    'setFortune' | 'setRunId' | 'setAskInput' | 'beginAsk' | 'finishAsk' | 'failAsk' | 'clearAskHistory' | 'reset'
> = {
    fortuneId: null,
    runId: null,
    persistenceDegraded: false,
    askInput: '',
    askLoading: false,
    askHistory: [],
    askMemoryEverDegraded: false,
};

export const useFortuneStore = create<FortuneStateShape>()(
    immer((set) => ({
        ...INITIAL,

        setFortune: (fortuneId, runId, opts) =>
            set((s) => {
                // New fortune wipes prior Ask thread — the store-bound session is
                // keyed by fortune_id on the backend, so cross-fortune bleed would
                // look wrong even if the /ask endpoint would technically handle it.
                if (s.fortuneId && s.fortuneId !== fortuneId) {
                    s.askHistory = [];
                    s.askMemoryEverDegraded = false;
                }
                s.fortuneId = fortuneId;
                s.runId = runId;
                s.persistenceDegraded = !!opts?.persistenceDegraded;
            }),

        setRunId: (runId) =>
            set((s) => {
                s.runId = runId;
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
            }),
    })),
);
