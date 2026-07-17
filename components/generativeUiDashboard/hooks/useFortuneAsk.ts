/** Wire the Ask composer to durable conversation state and POST /ask. */

import { useCallback, useEffect, useRef } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { fortuneClient, FortuneApiError } from '../lib/fortuneClient';
import type { AskContext } from '../lib/fortuneTypes';
import { useFortuneStore } from '../stores/fortuneStore';

const ASK_TIMEOUT_MS = 120_000;
const activeRequests = new Map<string, string>();

function errorDetail(error: FortuneApiError): string {
    if (error.body && typeof error.body === 'object') {
        const body = error.body as { detail?: unknown; message?: unknown };
        if (typeof body.detail === 'string') return body.detail;
        if (typeof body.message === 'string') return body.message;
    }
    return error.message;
}

export function isFortuneAskErrorRetryable(error: unknown, timedOut = false): boolean {
    if (timedOut || !(error instanceof FortuneApiError)) return true;
    return error.status === 409 || error.status === 429 || error.status >= 500;
}

export function getFortuneAskErrorMessage(error: unknown, timedOut = false): string {
    if (timedOut) {
        return 'This answer took longer than two minutes. You can retry without retyping your question.';
    }
    if (error instanceof FortuneApiError) {
        const detail = errorDetail(error).toLowerCase();
        if (error.status === 409) {
            return detail.includes('not ready') || detail.includes('initial') || detail.includes('complete')
                ? 'Your reading is still being prepared. Ask will unlock when it is complete.'
                : 'Another answer is already being prepared. Try again in a few seconds.';
        }
        if (error.status === 429) {
            return 'Too many questions were sent too quickly. Wait a moment, then retry.';
        }
        if (error.status === 422) {
            return 'Keep your question between 1 and 500 characters, then try again.';
        }
        if (error.status >= 500) {
            return 'The fortune service is temporarily unavailable. Your question is saved here—please retry.';
        }
        return error.message;
    }
    return 'Something went wrong preparing this answer. Your question is saved here—please retry.';
}

export function useConversationHydration(fortuneId: string | null) {
    const loadedConversationFor = useRef<string | null>(null);
    const hydrateAskHistory = useFortuneStore((s) => s.hydrateAskHistory);

    useEffect(() => {
        if (!fortuneId || loadedConversationFor.current === fortuneId) return;
        loadedConversationFor.current = fortuneId;
        let ignore = false;

        void fortuneClient.getConversation(fortuneId).then(({ turns }) => {
            if (ignore || useFortuneStore.getState().fortuneId !== fortuneId) return;
            hydrateAskHistory(turns.map((turn, index) => ({
                id: `remote-${fortuneId}-${index}-${turn.at}`,
                role: turn.role === 'assistant' ? 'agent' : 'user',
                content: turn.text,
                timestampISO: turn.at || new Date(0).toISOString(),
                clientRequestId: turn.client_request_id,
            })));
        }).catch(() => {
            // Conversation hydration is additive; a transient failure should not
            // block a new question or replace the reading with an error state.
        });

        return () => { ignore = true; };
    }, [fortuneId, hydrateAskHistory]);
}

export function useFortuneAsk(context?: AskContext) {
    const {
        fortuneId,
        fortuneGeneration,
        askInput,
        askHistory,
        askLoading,
        askMemoryEverDegraded,
        setAskInput,
        beginAsk,
        finishAsk,
        failAsk,
        retryAsk,
        setRunId,
    } = useFortuneStore(
        useShallow((s) => ({
            fortuneId: s.fortuneId,
            fortuneGeneration: s.fortuneGeneration,
            askInput: s.askInput,
            askHistory: s.askHistory,
            askLoading: s.askLoading,
            askMemoryEverDegraded: s.askMemoryEverDegraded,
            setAskInput: s.setAskInput,
            beginAsk: s.beginAsk,
            finishAsk: s.finishAsk,
            failAsk: s.failAsk,
            retryAsk: s.retryAsk,
            setRunId: s.setRunId,
        })),
    );

    const requestAnswer = useCallback(async (
        question: string,
        askContext: AskContext | undefined,
        isRetry: boolean,
        priorClientRequestId?: string,
    ) => {
        if (!question || !fortuneId || askLoading || activeRequests.has(fortuneId)) return;

        const originFortuneId = fortuneId;
        const originGeneration = fortuneGeneration;
        const clientRequestId = priorClientRequestId ?? crypto.randomUUID();
        activeRequests.set(originFortuneId, clientRequestId);

        if (isRetry) {
            retryAsk(clientRequestId);
        } else {
            beginAsk({
                id: `u-${Date.now()}`,
                role: 'user',
                content: question,
                timestampISO: new Date().toISOString(),
                askContext,
                clientRequestId,
            });
        }

        const controller = new AbortController();
        let timedOut = false;
        const timeout = window.setTimeout(() => {
            timedOut = true;
            controller.abort();
        }, ASK_TIMEOUT_MS);

        try {
            const res = await fortuneClient.askFollowUp(
                originFortuneId,
                question,
                clientRequestId,
                askContext,
                { signal: controller.signal },
            );
            const current = useFortuneStore.getState();
            if (
                current.fortuneId !== originFortuneId
                || current.fortuneGeneration !== originGeneration
            ) return;
            const narrative = res.narrative as { tldr?: string };
            finishAsk({
                id: `a-${res.run_id}`,
                role: 'agent',
                content: narrative?.tldr ?? '(no response)',
                timestampISO: new Date().toISOString(),
                runId: res.run_id,
                narrative: res.narrative,
                degradedMemory: res.degraded_memory,
                askContext,
                clientRequestId,
            });
            setRunId(res.run_id);
        } catch (error) {
            const current = useFortuneStore.getState();
            if (
                current.fortuneId !== originFortuneId
                || current.fortuneGeneration !== originGeneration
            ) return;
            failAsk(
                getFortuneAskErrorMessage(error, timedOut),
                question,
                askContext,
                clientRequestId,
                isFortuneAskErrorRetryable(error, timedOut),
            );
        } finally {
            window.clearTimeout(timeout);
            if (activeRequests.get(originFortuneId) === clientRequestId) {
                activeRequests.delete(originFortuneId);
            }
        }
    }, [fortuneId, fortuneGeneration, askLoading, beginAsk, finishAsk, failAsk, retryAsk, setRunId]);

    const send = useCallback((suggestedQuestion?: string) => {
        const question = (suggestedQuestion ?? askInput).trim();
        if (!question) return;
        void requestAnswer(question, context, false);
    }, [askInput, context, requestAnswer]);

    const retry = useCallback((turn: { retryQuestion?: string; askContext?: AskContext; clientRequestId?: string }) => {
        if (!turn.retryQuestion) return;
        void requestAnswer(turn.retryQuestion, turn.askContext ?? context, true, turn.clientRequestId);
    }, [context, requestAnswer]);

    return {
        fortuneId,
        input: askInput,
        setInput: setAskInput,
        history: askHistory,
        loading: askLoading,
        memoryDegraded: askMemoryEverDegraded,
        send,
        retry,
    };
}
