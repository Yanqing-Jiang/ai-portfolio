/**
 * MingEnginePage — BaZi Fortune Reading 3-phase page.
 *
 * Phase 1: Zero-keyboard input (date picker, time pills, focus cards)
 * Phase 2: SSE streaming with A2UI widget rendering
 * Phase 3: Result with follow-up action buttons
 *
 * Called from: App.tsx route /project/ming-engine
 * Invokes: useA2UIStream, A2UISurface, ClarificationOverlay, ProcessPanel
 */

import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { configService } from '../../services/config';
import { authService } from '../../services/auth';
import { useA2UIStream } from './a2ui/useA2UIStream';
import { A2UISurface, A2UISurfaceLoading } from './renderer/A2UISurface';
import { ClarificationOverlay } from './ClarificationOverlay';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EARTHLY_BRANCHES = [
    { branch: '子', time: '23-01', hour: '23:00' },
    { branch: '丑', time: '01-03', hour: '01:00' },
    { branch: '寅', time: '03-05', hour: '03:00' },
    { branch: '卯', time: '05-07', hour: '05:00' },
    { branch: '辰', time: '07-09', hour: '07:00' },
    { branch: '巳', time: '09-11', hour: '09:00' },
    { branch: '午', time: '11-13', hour: '11:00' },
    { branch: '未', time: '13-15', hour: '13:00' },
    { branch: '申', time: '15-17', hour: '15:00' },
    { branch: '酉', time: '17-19', hour: '17:00' },
    { branch: '戌', time: '19-21', hour: '19:00' },
    { branch: '亥', time: '21-23', hour: '21:00' },
] as const;

const FOCUS_OPTIONS = [
    { id: 'career', label: 'Career Deep Dive', icon: '📐' },
    { id: 'relationship', label: 'Compatibility Check', icon: '🤝' },
    { id: 'year', label: 'This Year\'s Luck', icon: '📅' },
    { id: 'general', label: 'General Reading', icon: '🔮' },
] as const;

// ---------------------------------------------------------------------------
// Input Phase
// ---------------------------------------------------------------------------

interface InputPhaseProps {
    onSubmit: (fortuneId: string) => void;
}

function InputPhase({ onSubmit }: InputPhaseProps) {
    const [birthDate, setBirthDate] = useState('');
    const [selectedTime, setSelectedTime] = useState<string | null>(null);
    const [birthTimeUnknown, setBirthTimeUnknown] = useState(false);
    const [focus, setFocus] = useState<string | null>(null);
    const [question, setQuestion] = useState('');
    const [showQuestion, setShowQuestion] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const canSubmit = birthDate && (selectedTime || birthTimeUnknown) && focus !== null;

    const handleSubmit = async () => {
        if (!canSubmit || isSubmitting) return;
        setIsSubmitting(true);
        setError(null);

        try {
            const backendUrl = configService.getBackendUrl();
            const birthIso = birthTimeUnknown
                ? `${birthDate}T12:00:00`
                : `${birthDate}T${selectedTime}:00`;

            const authHeaders = await authService.getAuthHeaders();
            const res = await fetch(`${backendUrl}/api/fortune/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeaders },
                body: JSON.stringify({
                    birth_iso: birthIso,
                    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                    focus: focus || undefined,
                    question: question || undefined,
                    birth_time_unknown: birthTimeUnknown,
                }),
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `Server error ${res.status}`);
            }

            const data = await res.json();
            onSubmit(data.fortune_id);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to create reading');
            setIsSubmitting(false);
        }
    };

    return (
        <motion.div
            className="mx-auto flex w-full max-w-lg flex-col gap-6 px-4 py-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 200, damping: 25 }}
        >
            {/* Header */}
            <div className="text-center">
                <h1
                    className="text-3xl font-bold text-slate-100"
                    style={{ fontFamily: 'var(--ming-font-chinese)' }}
                >
                    命 Engine
                </h1>
                <p className="mt-1 text-sm text-slate-400">
                    BaZi Four Pillars Fortune Reading
                </p>
            </div>

            {/* Birthday */}
            <div>
                <label className="mb-1 block text-sm font-medium text-slate-300">
                    Birthday
                </label>
                <input
                    type="date"
                    value={birthDate}
                    onChange={(e) => setBirthDate(e.target.value)}
                    className="w-full rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 text-slate-200 focus:border-[var(--ming-accent)] focus:outline-none"
                />
            </div>

            {/* Birth time */}
            <div>
                <label className="mb-1 block text-sm font-medium text-slate-300">
                    Birth Time
                </label>
                <div className="grid grid-cols-6 gap-1.5">
                    {EARTHLY_BRANCHES.map((eb) => (
                        <button
                            key={eb.branch}
                            className="flex min-h-[44px] flex-col items-center justify-center rounded-lg px-1 py-1.5 text-center transition-colors"
                            style={{
                                background:
                                    selectedTime === eb.hour && !birthTimeUnknown
                                        ? 'var(--ming-accent)'
                                        : 'rgba(148, 163, 184, 0.08)',
                                border:
                                    selectedTime === eb.hour && !birthTimeUnknown
                                        ? '1px solid var(--ming-accent)'
                                        : '1px solid rgba(148, 163, 184, 0.15)',
                                color:
                                    selectedTime === eb.hour && !birthTimeUnknown
                                        ? '#fff'
                                        : '#cbd5e1',
                            }}
                            onClick={() => {
                                setSelectedTime(eb.hour);
                                setBirthTimeUnknown(false);
                            }}
                        >
                            <span
                                className="text-base leading-none"
                                style={{ fontFamily: 'var(--ming-font-chinese)' }}
                            >
                                {eb.branch}
                            </span>
                            <span className="mt-0.5 text-[10px] opacity-60">
                                {eb.time}
                            </span>
                        </button>
                    ))}
                </div>
                <button
                    className="mt-1.5 w-full min-h-[44px] rounded-lg px-3 py-2 text-sm transition-colors"
                    style={{
                        background: birthTimeUnknown
                            ? 'rgba(148, 163, 184, 0.2)'
                            : 'rgba(148, 163, 184, 0.06)',
                        border: birthTimeUnknown
                            ? '1px solid rgba(148, 163, 184, 0.4)'
                            : '1px solid rgba(148, 163, 184, 0.1)',
                        color: '#94a3b8',
                    }}
                    onClick={() => {
                        setBirthTimeUnknown(true);
                        setSelectedTime(null);
                    }}
                >
                    I don't know my birth time
                </button>
            </div>

            {/* Focus */}
            <div>
                <label className="mb-1 block text-sm font-medium text-slate-300">
                    Reading Focus
                </label>
                <div className="grid grid-cols-2 gap-2">
                    {FOCUS_OPTIONS.map((opt) => (
                        <button
                            key={opt.id}
                            className="flex min-h-[56px] items-center gap-2 rounded-lg px-3 py-3 text-left text-sm transition-colors"
                            style={{
                                background:
                                    focus === opt.id
                                        ? 'rgba(234, 179, 8, 0.12)'
                                        : 'rgba(148, 163, 184, 0.06)',
                                border:
                                    focus === opt.id
                                        ? '1.5px solid var(--ming-gold)'
                                        : '1px solid rgba(148, 163, 184, 0.12)',
                                color: focus === opt.id ? '#eab308' : '#cbd5e1',
                            }}
                            onClick={() => setFocus(opt.id)}
                        >
                            <span className="text-lg">{opt.icon}</span>
                            <span className="font-medium">{opt.label}</span>
                        </button>
                    ))}
                </div>
            </div>

            {/* Optional question */}
            <div>
                <button
                    className="text-xs text-slate-500 hover:text-slate-400"
                    onClick={() => setShowQuestion(!showQuestion)}
                >
                    {showQuestion ? '▲ Hide' : '▼ Add a specific question (optional)'}
                </button>
                <AnimatePresence>
                    {showQuestion && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                        >
                            <textarea
                                value={question}
                                onChange={(e) => setQuestion(e.target.value)}
                                placeholder="e.g., Should I change careers this year?"
                                rows={2}
                                className="mt-1.5 w-full rounded-lg border border-slate-700 bg-slate-800/50 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-[var(--ming-accent)] focus:outline-none"
                            />
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Error */}
            {error && (
                <p className="text-center text-sm text-red-400">{error}</p>
            )}

            {/* Submit */}
            <button
                disabled={!canSubmit || isSubmitting}
                onClick={handleSubmit}
                className="w-full rounded-lg py-3 text-base font-semibold transition-opacity disabled:opacity-40"
                style={{
                    background: 'linear-gradient(135deg, var(--ming-accent), #991b1b)',
                    color: '#fff',
                }}
            >
                {isSubmitting ? 'Computing Chart...' : 'Begin Reading'}
            </button>
        </motion.div>
    );
}

// ---------------------------------------------------------------------------
// Streaming + Result Phases
// ---------------------------------------------------------------------------

interface StreamingPhaseProps {
    fortuneId: string;
}

function StreamingPhase({ fortuneId }: StreamingPhaseProps) {
    const backendUrl = configService.getBackendUrl();
    const [authToken, setAuthToken] = useState<string | null>(null);

    // Keep auth token in sync for SSE streams (EventSource doesn't support headers)
    useEffect(() => {
        authService.getAccessToken().then(setAuthToken);
    }, []);

    const streamUrl = useMemo(() => {
        const base = `${backendUrl}/api/fortune/${fortuneId}/stream`;
        return authToken ? `${base}?token=${encodeURIComponent(authToken)}` : base;
    }, [backendUrl, fortuneId, authToken]);

    const [streamState, streamActions] = useA2UIStream(streamUrl, {
        autoConnect: true,
        apiBaseUrl: `${backendUrl}/api/fortune`,
    });

    const handleAction = useCallback(
        async (actionName: string, context: Record<string, unknown>) => {
            if (actionName === 'userAction' && context.actionId) {
                try {
                    const authHeaders = await authService.getAuthHeaders();
                    await fetch(
                        `${backendUrl}/api/fortune/${fortuneId}/action`,
                        {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', ...authHeaders },
                            body: JSON.stringify({
                                action_id: context.actionId,
                                payload: {},
                            }),
                        }
                    );
                    // Reconnect stream for follow-up
                    streamActions.reconnect();
                } catch (err) {
                    console.error('[MingEngine] Action failed:', err);
                }
            }
        },
        [backendUrl, fortuneId, streamActions]
    );

    const handleClarification = useCallback(
        async (
            _requestId: string,
            responses: Record<string, string | string[]>,
            skipped: boolean
        ) => {
            streamActions.clearClarification();
            if (skipped) return;

            // The focus value is in responses.focus
            const focusValue = responses.focus;
            if (focusValue) {
                try {
                    const authHeaders = await authService.getAuthHeaders();
                    await fetch(
                        `${backendUrl}/api/fortune/${fortuneId}/action`,
                        {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', ...authHeaders },
                            body: JSON.stringify({
                                action_id: focusValue as string,
                                payload: {},
                            }),
                        }
                    );
                    streamActions.reconnect();
                } catch (err) {
                    console.error('[MingEngine] Clarification action failed:', err);
                }
            }
        },
        [backendUrl, fortuneId, streamActions]
    );

    // Get the first surface and data model
    const surfaceEntry = streamState.surfaces.entries().next().value as
        | [string, any]
        | undefined;
    const surface = surfaceEntry?.[1];
    const dataModel = surfaceEntry
        ? streamState.dataModels.get(surfaceEntry[0]) || {}
        : {};

    // Auto-scroll: sentinel at bottom, scroll into view when new content arrives
    const scrollSentinelRef = useRef<HTMLDivElement>(null);
    const userScrolledUp = useRef(false);

    useEffect(() => {
        const handleScroll = () => {
            const el = document.documentElement;
            const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
            userScrolledUp.current = !atBottom;
        };
        window.addEventListener('scroll', handleScroll, { passive: true });
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    useEffect(() => {
        if (streamState.isDone || userScrolledUp.current) return;
        scrollSentinelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, [surface, dataModel, streamState.isDone]);

    return (
        <div className="mx-auto w-full max-w-2xl px-4 py-6">
            {/* Surface rendering */}
            {surface ? (
                <A2UISurface
                    surface={surface}
                    dataModel={dataModel}
                    onAction={handleAction}
                />
            ) : streamState.isLoading ? (
                <A2UISurfaceLoading />
            ) : streamState.error ? (
                <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-center text-sm text-red-300">
                    {streamState.error.message}
                </div>
            ) : null}

            {/* Status indicator */}
            {!streamState.isDone && !streamState.error && (
                <div className="mt-4 flex items-center justify-center gap-2 text-sm text-slate-500">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--ming-accent)]" />
                    Reading in progress...
                </div>
            )}

            {/* Auto-scroll sentinel */}
            <div ref={scrollSentinelRef} className="h-1" />

            {/* Clarification overlay */}
            {streamState.pendingClarification && (
                <ClarificationOverlay
                    request={{
                        id: streamState.pendingClarification.request_id,
                        title: streamState.pendingClarification.title,
                        subtitle: streamState.pendingClarification.subtitle,
                        fields: streamState.pendingClarification.fields.map(
                            (f: any) => ({
                                id: f.field_id,
                                type: f.input_type,
                                prompt: f.label,
                                options: f.options?.map((o: any) => ({
                                    id: o.id,
                                    label: o.label,
                                })),
                            })
                        ),
                    }}
                    onSubmit={handleClarification}
                    onDismiss={() => streamActions.clearClarification()}
                />
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function MingEnginePage(): React.ReactElement {
    const [fortuneId, setFortuneId] = useState<string | null>(null);

    return (
        <div
            className="min-h-screen"
            style={{ background: 'var(--ming-bg, #0c0a14)' }}
        >
            <AnimatePresence mode="wait">
                {!fortuneId ? (
                    <InputPhase
                        key="input"
                        onSubmit={(id) => setFortuneId(id)}
                    />
                ) : (
                    <motion.div
                        key="streaming"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.3 }}
                    >
                        <StreamingPhase fortuneId={fortuneId} />
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
