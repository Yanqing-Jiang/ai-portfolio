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
import { motion, AnimatePresence, MotionConfig } from 'framer-motion';
import { configService } from '../../services/config';
import { authService } from '../../services/auth';
import { useA2UIStream } from './a2ui/useA2UIStream';
import { A2UISurfaceLoading } from './renderer/A2UISurface';
import { ClarificationOverlay } from './ClarificationOverlay';
import { InspectorModeProvider } from './InspectorModeContext';
import { BirthdayScrollPicker } from './BirthdayScrollPicker';
import { MingResultsTabs } from './MingResultsTabs';
import { fortuneClient, FortuneApiError } from './lib/fortuneClient';
import { useFortuneStore } from './stores/fortuneStore';
import { hydrateDataModelFromSnapshot } from './hooks/useFortuneStream';
import type { FortuneFunctionId } from './lib/fortuneTypes';
import { ActivityRail, type ActivityRailStep, type ActivityRailSummary } from './ActivityRail';
import { GlassBoxDrawer } from './GlassBoxDrawer';

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

const GENDER_OPTIONS = [
    { id: 'male', label: 'Male', icon: '♂' },
    { id: 'female', label: 'Female', icon: '♀' },
    { id: 'unknown', label: 'Prefer not to say', icon: '—' },
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
    const [gender, setGender] = useState<string>('unknown');
    const [focus, setFocus] = useState<string | null>(null);
    const [question, setQuestion] = useState('');
    const [showQuestion, setShowQuestion] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const canSubmit = birthDate && (selectedTime || birthTimeUnknown) && focus !== null;

    const setFortune = useFortuneStore((s) => s.setFortune);

    const handleSubmit = async () => {
        if (!canSubmit || isSubmitting) return;
        setIsSubmitting(true);
        setError(null);

        try {
            const birthIso = birthTimeUnknown
                ? `${birthDate}T12:00:00`
                : `${birthDate}T${selectedTime}:00`;

            const data = await fortuneClient.createFortune({
                birth_iso: birthIso,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                focus: focus || undefined,
                question: question || undefined,
                birth_time_unknown: birthTimeUnknown,
                gender: gender || undefined,
            });

            setFortune(data.fortune_id, data.run_id, {
                persistenceDegraded: data.persistenceDegraded,
            });
            onSubmit(data.fortune_id);
        } catch (err) {
            const msg =
                err instanceof FortuneApiError
                    ? err.message
                    : err instanceof Error
                    ? err.message
                    : 'Failed to create reading';
            setError(msg);
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
                <BirthdayScrollPicker
                    value={birthDate}
                    onChange={setBirthDate}
                />
            </div>

            {/* Birth time */}
            <div>
                <label className="mb-1 block text-sm font-medium text-slate-300">
                    Birth Time
                </label>
                <div className="grid grid-cols-4 sm:grid-cols-6 gap-1.5">
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

            {/* Gender (needed for luck pillar direction) */}
            <div>
                <label className="mb-1 block text-sm font-medium text-slate-300">
                    Gender <span className="text-slate-500 font-normal">(for luck cycle calculation)</span>
                </label>
                <div className="grid grid-cols-3 gap-2">
                    {GENDER_OPTIONS.map((opt) => (
                        <button
                            key={opt.id}
                            className="flex min-h-[44px] items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm transition-colors"
                            style={{
                                background:
                                    gender === opt.id
                                        ? 'rgba(148, 163, 184, 0.15)'
                                        : 'rgba(148, 163, 184, 0.06)',
                                border:
                                    gender === opt.id
                                        ? '1.5px solid rgba(148, 163, 184, 0.4)'
                                        : '1px solid rgba(148, 163, 184, 0.12)',
                                color: gender === opt.id ? '#e2e8f0' : '#94a3b8',
                            }}
                            onClick={() => setGender(opt.id)}
                        >
                            <span className="text-base">{opt.icon}</span>
                            <span className="font-medium">{opt.label}</span>
                        </button>
                    ))}
                </div>
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
    inspectorMode?: boolean;
}

function StreamingPhase({ fortuneId, inspectorMode = false }: StreamingPhaseProps) {
    const backendUrl = configService.getBackendUrl();
    const [authToken, setAuthToken] = useState<string | null>(null);
    const [tokenResolved, setTokenResolved] = useState(false);
    const activeRunId = useFortuneStore((s) => s.runId);
    const setRunId = useFortuneStore((s) => s.setRunId);
    const functionId = useFortuneStore((s) => s.functionId);
    const hydrateFromReplay = useFortuneStore((s) => s.hydrateFromReplay);

    // Resolve auth token once before connecting — prevents double-connect flicker
    useEffect(() => {
        authService.getAccessToken().then((token) => {
            setAuthToken(token);
            setTokenResolved(true);
        });
    }, []);

    // Only build streamUrl after token is resolved (or confirmed absent)
    // This prevents: null→connect→token arrives→new URL→reconnect→surface flash
    const streamUrl = useMemo(() => {
        if (!tokenResolved) return null; // Don't connect yet
        const base = `${backendUrl}/api/fortune/${fortuneId}/stream`;
        const params = new URLSearchParams();
        if (authToken) params.set('token', authToken);
        if (activeRunId) params.set('run_id', activeRunId);
        const query = params.toString();
        return query ? `${base}?${query}` : base;
    }, [backendUrl, fortuneId, authToken, activeRunId, tokenResolved]);

    const handleResyncRequired = useCallback(async (detail: Record<string, unknown>) => {
        const snapshot = await fortuneClient.getFortune(fortuneId);
        if (snapshot === null) {
            const replacementRunId = typeof detail.run_id === 'string' ? detail.run_id : null;
            if (replacementRunId && replacementRunId !== activeRunId) setRunId(replacementRunId);
            return;
        }
        const resolvedFunction = (
            snapshot.metadata?.function_id as FortuneFunctionId | undefined
        ) || functionId || 'wish';
        const status = snapshot.status === 'complete'
            ? 'complete'
            : snapshot.status === 'error' || snapshot.status === 'failed_guardrail'
                ? 'error'
                : 'streaming';
        hydrateFromReplay({
            fortune_id: snapshot.fortune_id,
            run_id: typeof detail.run_id === 'string' ? detail.run_id : (activeRunId || ''),
            function_id: resolvedFunction,
            status,
            last_seq: 0,
            metadata: {
                created_at: snapshot.metadata?.created_at || '',
                persistence_degraded: snapshot.metadata?.persistence_degraded,
                birth_time_unknown: snapshot.metadata?.birth_time_unknown,
            },
            data_model: hydrateDataModelFromSnapshot(snapshot, resolvedFunction),
            ask_history: [],
        });
    }, [activeRunId, fortuneId, functionId, hydrateFromReplay, setRunId]);

    const [streamState, streamActions] = useA2UIStream(streamUrl, {
        autoConnect: true,
        apiBaseUrl: `${backendUrl}/api/fortune`,
        onResyncRequired: handleResyncRequired,
    });

    const handleAction = useCallback(
        async (actionName: string, context: Record<string, unknown>) => {
            if (actionName === 'userAction' && context.actionId) {
                try {
                    const res = await fortuneClient.submitAction(
                        fortuneId,
                        context.actionId as string,
                    );
                    setRunId(res.run_id);
                } catch (err) {
                    console.error('[MingEngine] Action failed:', err);
                }
            }
        },
        [fortuneId, streamActions, setRunId]
    );

    const handleClarification = useCallback(
        async (
            _requestId: string,
            responses: Record<string, string | string[]>,
            skipped: boolean
        ) => {
            streamActions.clearClarification();
            if (skipped) return;

            const focusValue = responses.focus;
            if (focusValue) {
                try {
                    const res = await fortuneClient.submitAction(fortuneId, focusValue as string);
                    setRunId(res.run_id);
                } catch (err) {
                    console.error('[MingEngine] Clarification action failed:', err);
                }
            }
        },
        [fortuneId, streamActions, setRunId]
    );

    // Get the first surface and data model
    const surfaceEntry = streamState.surfaces.entries().next().value as
        | [string, any]
        | undefined;
    const surface = surfaceEntry?.[1];
    const dataModel = surfaceEntry
        ? streamState.dataModels.get(surfaceEntry[0]) || {}
        : {};

    // Track whether we've ever seen a surface — prevents flicker on reconnect
    const hasEverHadSurface = useRef(false);
    if (surface) hasEverHadSurface.current = true;

    // Auto-scroll: sentinel at bottom, scroll into view when new content arrives
    const scrollSentinelRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);
    const scrollContainerRef = useRef<HTMLElement | null>(null);
    const userScrolledUp = useRef(false);

    useEffect(() => {
        const findScrollContainer = () => {
            let node = contentRef.current?.parentElement ?? null;
            while (node) {
                const { overflowY } = window.getComputedStyle(node);
                if (/(auto|scroll|overlay)/.test(overflowY) && node.scrollHeight > node.clientHeight) {
                    return node;
                }
                node = node.parentElement;
            }
            return null;
        };

        const scrollTarget = findScrollContainer();
        scrollContainerRef.current = scrollTarget;

        const handleScroll = () => {
            if (scrollTarget) {
                const atBottom = scrollTarget.scrollHeight - scrollTarget.scrollTop - scrollTarget.clientHeight < 120;
                userScrolledUp.current = !atBottom;
                return;
            }
            const el = document.documentElement;
            const scrollTop = window.scrollY || el.scrollTop;
            const atBottom = el.scrollHeight - scrollTop - window.innerHeight < 120;
            userScrolledUp.current = !atBottom;
        };

        handleScroll();
        const target = scrollTarget ?? window;
        target.addEventListener('scroll', handleScroll, { passive: true });
        return () => target.removeEventListener('scroll', handleScroll);
    }, []);

    useEffect(() => {
        if (streamState.isDone || userScrolledUp.current) return;

        const frame = window.requestAnimationFrame(() => {
            const scrollTarget = scrollContainerRef.current;
            if (scrollTarget) {
                scrollTarget.scrollTo({ top: scrollTarget.scrollHeight, behavior: 'auto' });
                return;
            }
            scrollSentinelRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' });
        });

        return () => window.cancelAnimationFrame(frame);
    }, [surface, dataModel, streamState.isDone]);

    // Show loading only when we've never had content yet
    const showLoading = !hasEverHadSurface.current && (streamState.isLoading || !tokenResolved);

    // ---- Glass Box / Activity Rail ---------------------------------------
    // Trace data rides on the A2UI data model at /data/trace/steps and
    // /data/trace/summary — we just reshape it for the rail/drawer.
    const traceFromModel = (dataModel as any)?.trace as
        | { steps?: { items?: any[] } | any[]; summary?: any }
        | undefined;
    const traceSteps: ActivityRailStep[] = useMemo(() => {
        const raw = traceFromModel?.steps;
        // Stream bridge emits either an array (batch) or a keyed map of { stepId: {step} }.
        if (!raw) return [];
        if (Array.isArray(raw)) return raw as ActivityRailStep[];
        if (typeof raw === 'object') {
            const items = (raw as { items?: any[] }).items;
            if (Array.isArray(items)) return items as ActivityRailStep[];
            // Fall back to a map of stepId → { step } entries.
            return Object.values(raw)
                .map((v: any) => v?.step ?? v)
                .filter(Boolean) as ActivityRailStep[];
        }
        return [];
    }, [traceFromModel?.steps]);
    const traceSummary: ActivityRailSummary | null = traceFromModel?.summary ?? null;
    const [glassOpen, setGlassOpen] = useState(false);
    // Close when a fresh run kicks off so the user re-opens intentionally for the new data.
    useEffect(() => {
        if (streamState.isLoading) setGlassOpen(false);
    }, [streamState.isLoading]);

    const storeRunId = useFortuneStore((s) => s.runId);
    const glassContext = storeRunId ? `Run ${storeRunId.slice(0, 8)}` : undefined;

    return (
        <div ref={contentRef} className="mx-auto w-full max-w-6xl px-4 py-6">
            {/* Tab-based results view — routes widgets to tabs */}
            {surface && (
                <InspectorModeProvider inspectorMode={inspectorMode}>
                    <MotionConfig transition={{ layout: { duration: 0 } }}>
                        <div style={{ contain: 'layout paint', willChange: 'transform' }}>
                            <MingResultsTabs
                                surface={surface}
                                dataModel={dataModel}
                                onAction={handleAction}
                            />
                        </div>
                    </MotionConfig>
                </InspectorModeProvider>
            )}

            {/* Loading skeleton — only before any content has appeared */}
            {showLoading && <A2UISurfaceLoading />}

            {/* Progress indicator — show current pipeline phase */}
            {!streamState.isDone && !streamState.error && (dataModel as any)?.meta?.progress && (
                <div className="mt-3 flex items-center justify-center gap-2 text-sm text-slate-400">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--ming-accent)]" />
                    {(dataModel as any).meta.progress.message}
                </div>
            )}

            {/* Error state — only when no surface was ever rendered */}
            {!surface && !showLoading && streamState.error && (
                <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-center text-sm text-red-300">
                    {streamState.error.message}
                </div>
            )}

            {/* Status indicator — only before surface appears */}
            {!hasEverHadSurface.current && !streamState.isDone && !streamState.error && !showLoading && (
                <div className="mt-4 flex items-center justify-center gap-2 text-sm text-slate-500">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--ming-accent)]" />
                    Reading in progress...
                </div>
            )}

            {/* Auto-scroll sentinel */}
            <div ref={scrollSentinelRef} className="h-1" />

            {/* Glass Box bottom drawer — agent trace inspection */}
            <GlassBoxDrawer
                open={glassOpen}
                onClose={() => setGlassOpen(false)}
                steps={traceSteps}
                summary={traceSummary}
                contextLabel={glassContext}
            />
            <ActivityRail
                steps={traceSteps}
                summary={traceSummary}
                isStreaming={!streamState.isDone}
                isOpen={glassOpen}
                onToggle={() => setGlassOpen((v) => !v)}
            />

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
    const [inspectorMode, setInspectorMode] = useState(false);

    return (
        <div
            className={`min-h-screen ${inspectorMode ? 'ming-inspector-mode' : 'ming-reading-mode'}`}
            style={{ background: 'var(--ming-bg, #0c0a14)', overscrollBehavior: 'none' }}
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
                        <StreamingPhase fortuneId={fortuneId} inspectorMode={inspectorMode} />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Truth Toggle — floating button to switch Reading/Inspector mode */}
            {fortuneId && (
                <motion.button
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 1, type: 'spring', stiffness: 200 }}
                    onClick={() => setInspectorMode(!inspectorMode)}
                    className="fixed bottom-6 right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full shadow-lg transition-colors"
                    style={{
                        background: inspectorMode
                            ? 'linear-gradient(135deg, #6366f1, #4f46e5)'
                            : 'rgba(30, 30, 50, 0.9)',
                        border: inspectorMode
                            ? '2px solid #818cf8'
                            : '1px solid rgba(148, 163, 184, 0.2)',
                    }}
                    title={inspectorMode ? 'Switch to Reading Mode' : 'Switch to Inspector Mode'}
                >
                    <span className="text-lg">
                        {inspectorMode ? '\uD83D\uDD0D' : '\uD83D\uDD0E'}
                    </span>
                </motion.button>
            )}

            {/* Inject CSS for mode switching — works with tab system */}
            <style>{`
                /* Inspector Mode: show trace sidebar + all components */
                .ming-inspector-mode [data-component-id="fortune_trace_card"] {
                    display: block !important;
                    min-width: 280px;
                    max-width: 320px;
                    border-left: 1px solid rgba(148, 163, 184, 0.1);
                }
            `}</style>
        </div>
    );
}
