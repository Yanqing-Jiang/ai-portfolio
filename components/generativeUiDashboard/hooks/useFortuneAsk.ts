/**
 * useFortuneAsk — hook wiring the Ask tab input to POST /api/fortune/:id/ask.
 *
 * Responsibilities:
 * - Append the user's question to `askHistory` as a local turn (optimistic).
 * - Call `fortuneClient.askFollowUp`.
 * - On success: push the agent turn, rotate `runId`, flag `degraded_memory`.
 * - On failure: push an error turn so the user sees something went wrong.
 *
 * Not in scope:
 * - Streaming. /ask is a synchronous JSON endpoint for now; if we later SSE
 *   it, this hook will grow an EventSource branch (mirroring useFortuneStream).
 * - Retry logic. A single failure surfaces immediately; the user can retype.
 */

import { useCallback } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { fortuneClient, FortuneApiError } from '../lib/fortuneClient';
import { useFortuneStore, type AskTurn } from '../stores/fortuneStore';

export function useFortuneAsk() {
    const {
        fortuneId,
        askInput,
        askHistory,
        askLoading,
        askMemoryEverDegraded,
        setAskInput,
        beginAsk,
        finishAsk,
        failAsk,
        setRunId,
    } = useFortuneStore(
        useShallow((s) => ({
            fortuneId: s.fortuneId,
            askInput: s.askInput,
            askHistory: s.askHistory,
            askLoading: s.askLoading,
            askMemoryEverDegraded: s.askMemoryEverDegraded,
            setAskInput: s.setAskInput,
            beginAsk: s.beginAsk,
            finishAsk: s.finishAsk,
            failAsk: s.failAsk,
            setRunId: s.setRunId,
        })),
    );

    const send = useCallback(async () => {
        const question = askInput.trim();
        if (!question || !fortuneId || askLoading) return;

        const userTurn: AskTurn = {
            id: `u-${Date.now()}`,
            role: 'user',
            content: question,
            timestampISO: new Date().toISOString(),
        };
        beginAsk(userTurn);

        try {
            const res = await fortuneClient.askFollowUp(fortuneId, question);
            const narrative = res.narrative as { tldr?: string };
            const agentTurn: AskTurn = {
                id: `a-${res.run_id}`,
                role: 'agent',
                content: narrative?.tldr ?? '(no response)',
                timestampISO: new Date().toISOString(),
                runId: res.run_id,
                narrative: res.narrative,
                degradedMemory: res.degraded_memory,
            };
            finishAsk(agentTurn);
            setRunId(res.run_id);
        } catch (err) {
            const msg =
                err instanceof FortuneApiError
                    ? err.status === 409
                        ? 'Initial reading is still preparing — try again in a moment.'
                        : err.status === 429
                        ? 'Easy there — too many questions too fast. Try again shortly.'
                        : err.message
                    : 'Something went wrong asking the pillars. Please try again.';
            failAsk(msg);
        }
    }, [askInput, fortuneId, askLoading, beginAsk, finishAsk, failAsk, setRunId]);

    return {
        fortuneId,
        input: askInput,
        setInput: setAskInput,
        history: askHistory,
        loading: askLoading,
        memoryDegraded: askMemoryEverDegraded,
        send,
    };
}
