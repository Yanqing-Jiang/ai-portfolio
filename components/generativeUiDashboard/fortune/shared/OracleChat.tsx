/**
 * OracleChat — production Ask-the-Oracle bubble (Concept D, "Hybrid").
 *
 * Each agent turn renders as:
 *   1. Pre-verdict (during the ~50-70s /ask wait): a Career-style specialist
 *      chip + a stack of animated reasoning breadcrumbs that walk through 4
 *      named phases on a fixed schedule. Backend doesn't stream yet, so the
 *      schedule is client-side; the SSE migration in the redesign spec
 *      replaces this with real `reasoning.step` events.
 *   2. Verdict: italic serif headline (= narrative.tldr).
 *   3. Go-deeper accordion: holds insights → bullets, classical citations,
 *      and year predictions when present. Source chips on each section
 *      header anchor the claim back to a chart pillar / Why-tab insight.
 *   4. Follow-up pills: pulled from the per-tab `suggestions` array.
 *
 * Backward compat: a turn without `narrative` (legacy or error) falls back
 * to the plain-text bubble. The callers (4 per-function AskTab.tsx files)
 * already store `narrative` on each turn via `useFortuneAsk`, so the new
 * layout lights up automatically.
 *
 * Called from: fortune/{compatibility|occasion|luck|wish}/AskTab.tsx.
 * Forwards to: only renders — no fetching. Submit handled by parent.
 *
 * The companion demo at /project/fortune-agent/ask-demo/d simulates the
 * full event flow client-side for visual review of this layout.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
    AlertCircle,
    BookOpen,
    Brain,
    ChevronDown,
    Compass,
    Loader2,
    Send,
    Sparkles,
    Target,
} from 'lucide-react';
import { CITATION_GOLD, GLASS } from '../designTokens';

// ---------------------------------------------------------------------------
// Types — keep the message shape backward compatible. Optional fields light
// up the richer Concept D layout when present.
// ---------------------------------------------------------------------------

export interface OracleChatMessage {
    id: string;
    role: 'user' | 'agent';
    /** Plain text fallback (= narrative.tldr or error string). */
    content: string;
    /** Full structured narrative when the turn came from /ask. */
    narrative?: NarrativePayload;
    runId?: string;
    degradedMemory?: boolean;
}

interface NarrativeBullet { icon?: string; text: string }
interface NarrativeInsight {
    id?: string;
    icon?: string;
    heading?: string;
    tagline?: string;
    bullets?: NarrativeBullet[];
    citations?: string[];
}
interface YearPrediction {
    year: number;
    prediction: string;
    confidence?: number;
}
interface NarrativePayload {
    tldr?: string;
    insights?: NarrativeInsight[];
    year_predictions?: YearPrediction[];
}

interface OracleChatProps {
    messages: OracleChatMessage[];
    input: string;
    onInputChange: (v: string) => void;
    onSend: () => void;
    suggestions?: string[];
    accentColor?: string;
    isLoading?: boolean;
    memoryDegraded?: boolean;
    disabled?: boolean;
    /** Focus string of the parent flow (e.g. "compatibility:romance",
     * "luck_cycle:career:5-year") so the loading chip can name the
     * specialist that's about to run. */
    flowFocus?: string;
}

const SERIF = "'Cormorant Garamond', 'Playfair Display', Georgia, serif";

// Generic reasoning phases shown during the loading wait. Mapped to a fixed
// schedule (in ms) since the JSON /ask endpoint doesn't stream yet. Once the
// backend SSE work lands, this hook is replaced with real event consumption.
const REASONING_PHASES = [
    'Mapping the Four Pillars',
    'Reading the year and luck pillars',
    'Locating the relevant Ten Gods',
    'Synthesizing the answer',
] as const;

const PHASE_SCHEDULE_MS = [400, 8000, 22000, 38000];

// Mirror of backend `infer_specialist_action` so the loading chip can name
// the specialist that's actually about to run (e.g. "Career specialist"
// rather than the generic "Oracle specialist"). Heuristics intentionally
// match — if backend bypasses triage, the label here is correct.
const SPECIALIST_LABELS: Record<string, string> = {
    career_focus: 'Career specialist',
    relationship_focus: 'Relationship specialist',
    year_forecast: 'Year forecast specialist',
    deep_dive_element: 'Element-balance specialist',
    show_sources: 'Sources specialist',
    expand_classics: 'Classics specialist',
};

function inferSpecialistLabel(question: string | undefined, focus: string | undefined): string {
    const q = (question || '').toLowerCase();
    const f = (focus || '').toLowerCase();
    const has = (keys: string[]) => keys.some((k) => q.includes(k));

    // Order mirrors backend `infer_specialist_action` (triage.py:155+):
    // classics is checked BEFORE sources because "explain the classic
    // text" should land on expand_classics, not show_sources. PR4 of the
    // latency refactor surfaced this drift in code review.
    if (has(['classic', 'classical text', 'expand on', 'philosophy', 'tradition', 'scripture', 'deeper meaning', 'more from']))
        return SPECIALIST_LABELS.expand_classics;
    // Sources keys mirror backend `_SOURCES_PHRASES` + `_SOURCES_WORDS`
    // (triage.py:99-104). The two long phrases without a "source" /
    // "reference" / "citation" / "passage" substring — "where does this
    // come from" and "where did you get" — must be enumerated explicitly
    // or the optimistic chat label drifts from the actual specialist.
    if (has(['source', 'reference', 'citation', 'passage', 'where does this come from', 'where did you get']))
        return SPECIALIST_LABELS.show_sources;
    if (has(['career', 'job', 'work', 'promotion', 'boss', 'salary', 'company', 'office', 'raise', 'interview', 'resign', 'quit']))
        return SPECIALIST_LABELS.career_focus;
    if (has(['relationship', 'partner', 'marry', 'marriage', 'love', 'spouse', 'wife', 'husband', 'girlfriend', 'boyfriend', 'us ', 'we ', 'together']))
        return SPECIALIST_LABELS.relationship_focus;
    if (has(['element', 'wood', 'fire', 'earth', 'metal', 'water', 'balance']))
        return SPECIALIST_LABELS.deep_dive_element;
    if (has(['year', 'next year', 'decade', 'luck', 'cycle', 'timing', 'when ', 'forecast', '2025', '2026', '2027', '2028']))
        return SPECIALIST_LABELS.year_forecast;

    if (f.startsWith('compatibility')) return SPECIALIST_LABELS.relationship_focus;
    if (f.startsWith('luck_cycle') || f.startsWith('occasion')) return SPECIALIST_LABELS.year_forecast;
    return 'Oracle specialist';
}

function useSimulatedReasoning(active: boolean) {
    const [revealed, setRevealed] = useState(0);
    const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

    useEffect(() => {
        // Reset and re-arm whenever active flips on.
        timersRef.current.forEach((t) => clearTimeout(t));
        timersRef.current = [];
        if (!active) {
            setRevealed(0);
            return;
        }
        PHASE_SCHEDULE_MS.forEach((delay, i) => {
            const t = setTimeout(() => setRevealed(i + 1), delay);
            timersRef.current.push(t);
        });
        return () => {
            timersRef.current.forEach((t) => clearTimeout(t));
        };
    }, [active]);

    return REASONING_PHASES.slice(0, revealed).map((label, i) => ({
        id: `phase-${i}`,
        label,
    }));
}

// ---------------------------------------------------------------------------
// Atoms
// ---------------------------------------------------------------------------

const SpecialistChip: React.FC<{ label: string; color: string }> = ({ label, color }) => (
    <motion.span
        layout
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.25 }}
        className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-widest"
        style={{ borderColor: `${color}55`, background: `${color}1A`, color }}
    >
        <Compass className="h-2.5 w-2.5" />
        {label}
    </motion.span>
);

const ReasoningBreadcrumbs: React.FC<{
    steps: { id: string; label: string }[];
    accentColor: string;
}> = ({ steps, accentColor }) => (
    <div className="flex flex-wrap items-center gap-1.5">
        <AnimatePresence>
            {steps.map((step) => (
                <motion.span
                    key={step.id}
                    layout
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    className="inline-flex items-center gap-1 rounded-full bg-white/[0.04] px-2 py-1 text-[10px] text-slate-300"
                >
                    <Loader2 className="h-2.5 w-2.5 animate-spin" style={{ color: accentColor }} />
                    {step.label}
                </motion.span>
            ))}
        </AnimatePresence>
    </div>
);

const ReasoningTrailChip: React.FC<{ steps: { id: string; label: string }[] }> = ({ steps }) => {
    const [open, setOpen] = useState(false);
    if (steps.length === 0) return null;
    return (
        <div className="flex flex-col gap-1.5">
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                className="self-start inline-flex items-center gap-1.5 rounded-full border border-white/5 bg-white/[0.02] px-2.5 py-1 text-[10px] uppercase tracking-widest text-slate-500 hover:text-slate-300"
            >
                <Brain className="h-3 w-3" />
                {steps.length} reasoning steps
                <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
                    <ChevronDown className="h-3 w-3" />
                </motion.span>
            </button>
            <AnimatePresence initial={false}>
                {open && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25 }}
                        className="overflow-hidden"
                    >
                        <ul className="space-y-1 pl-1 pt-1">
                            {steps.map((s, i) => (
                                <li
                                    key={s.id}
                                    className="flex items-center gap-2 text-[11px] text-slate-400"
                                >
                                    <span className="text-slate-600 tabular-nums">
                                        {String(i + 1).padStart(2, '0')}
                                    </span>
                                    <span>{s.label}</span>
                                </li>
                            ))}
                        </ul>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

const DisclosureAccordion: React.FC<{
    title: string;
    children: React.ReactNode;
    defaultExpanded?: boolean;
}> = ({ title, children, defaultExpanded = false }) => {
    const [open, setOpen] = useState(defaultExpanded);
    return (
        <div className="rounded-xl border border-white/5 bg-white/[0.02]">
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                className="flex w-full items-center justify-between px-4 py-3 text-[11px] uppercase tracking-widest text-slate-300 hover:text-slate-100"
            >
                <span className="flex items-center gap-2">
                    <BookOpen className="h-3 w-3" />
                    {title}
                </span>
                <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
                    <ChevronDown className="h-3.5 w-3.5" />
                </motion.span>
            </button>
            <AnimatePresence initial={false}>
                {open && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25 }}
                        className="overflow-hidden"
                    >
                        <div className="px-4 pb-4 space-y-3">{children}</div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

const SectionTag: React.FC<{ label: string; tone: 'classical' | 'pillar' | 'insight' }> = ({
    label,
    tone,
}) => {
    const styles = useMemo(() => {
        if (tone === 'classical') {
            return {
                color: CITATION_GOLD,
                bg: `${CITATION_GOLD}1A`,
                border: `${CITATION_GOLD}55`,
            };
        }
        if (tone === 'pillar') {
            return {
                color: '#5eead4',
                bg: 'rgba(20,184,166,0.12)',
                border: 'rgba(20,184,166,0.4)',
            };
        }
        return {
            color: '#a5b4fc',
            bg: 'rgba(99,102,241,0.12)',
            border: 'rgba(99,102,241,0.4)',
        };
    }, [tone]);

    return (
        <span
            className="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] uppercase tracking-wide"
            style={{ borderColor: styles.border, background: styles.bg, color: styles.color }}
        >
            <BookOpen className="h-2.5 w-2.5" />
            {label}
        </span>
    );
};

// ---------------------------------------------------------------------------
// Bubbles
// ---------------------------------------------------------------------------

const UserBubble: React.FC<{ text: string }> = ({ text }) => (
    <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="flex justify-end"
    >
        <div className="max-w-[80%] rounded-2xl bg-white/10 px-4 py-2.5 text-[13px] text-slate-100">
            {text}
        </div>
    </motion.div>
);

interface AgentBubbleProps {
    msg: OracleChatMessage;
    accentColor: string;
    /** Pre-rendered when this is the in-flight loading turn. */
    pendingSteps?: { id: string; label: string }[];
    isPending?: boolean;
    /** Resolved specialist name to show in the pre-verdict chip. */
    specialistLabel?: string;
}

const AgentBubble: React.FC<AgentBubbleProps> = ({
    msg,
    accentColor,
    pendingSteps,
    isPending,
    specialistLabel = 'Oracle specialist',
}) => {
    const narrative = msg.narrative;
    const verdict = narrative?.tldr || msg.content;
    const insights = narrative?.insights || [];
    const yearPredictions = narrative?.year_predictions || [];
    const collectedCitations = useMemo(() => {
        const out: string[] = [];
        for (const ins of insights) {
            for (const c of ins.citations || []) out.push(c);
        }
        return Array.from(new Set(out));
    }, [insights]);

    // No narrative payload → plain bubble (e.g. error turns)
    if (!narrative && !isPending) {
        return (
            <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex justify-start"
            >
                <div
                    className={`${GLASS} max-w-[88%] rounded-2xl px-4 py-3 text-[13px] text-slate-200`}
                    style={{ borderLeft: `2px solid ${accentColor}66` }}
                >
                    {msg.content}
                </div>
            </motion.div>
        );
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border-l-2 bg-white/[0.02] p-4 space-y-3"
            style={{ borderLeftColor: `${accentColor}66` }}
        >
            {/* Pre-verdict: specialist + animated reasoning breadcrumbs */}
            {isPending && (
                <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                        <SpecialistChip label={specialistLabel} color={accentColor} />
                        {(!pendingSteps || pendingSteps.length === 0) && (
                            <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-widest text-slate-500">
                                <Loader2 className="h-3 w-3 animate-spin" style={{ color: accentColor }} />
                                Routing
                            </span>
                        )}
                    </div>
                    {pendingSteps && pendingSteps.length > 0 && (
                        <ReasoningBreadcrumbs steps={pendingSteps} accentColor={accentColor} />
                    )}
                </div>
            )}

            {/* Post-verdict reasoning trail (collapsed) — only when narrative present */}
            {!isPending && narrative && (
                <ReasoningTrailChip
                    steps={REASONING_PHASES.map((label, i) => ({ id: `r-${i}`, label }))}
                />
            )}

            {/* Verdict — italic serif (= narrative.tldr). */}
            {verdict && (
                <div className={`pb-3 ${insights.length ? 'border-b border-white/5' : ''}`}>
                    <div className="text-[9px] uppercase tracking-[0.3em] mb-1.5" style={{ color: `${accentColor}cc` }}>
                        Verdict
                    </div>
                    <p
                        className="text-base leading-snug text-slate-100 sm:text-lg"
                        style={{ fontFamily: SERIF, fontStyle: 'italic' }}
                    >
                        {verdict}
                    </p>
                </div>
            )}

            {/* Skeleton pulse while waiting for the verdict body */}
            {isPending && !narrative && (
                <div className="space-y-2 pt-2">
                    {[0, 1, 2].map((i) => (
                        <motion.div
                            key={i}
                            animate={{ opacity: [0.2, 0.5, 0.2] }}
                            transition={{ duration: 1.6, repeat: Infinity, delay: i * 0.2 }}
                            className="h-3 rounded bg-white/5"
                            style={{ width: `${85 - i * 12}%` }}
                        />
                    ))}
                </div>
            )}

            {/* Go deeper — sections + citations + timeline */}
            {(insights.length > 0 || yearPredictions.length > 0 || collectedCitations.length > 0) && (
                <DisclosureAccordion title="Go deeper">
                    {insights.length > 0 && (
                        <div className="space-y-3">
                            {insights.map((section, sIdx) => (
                                <div key={section.id || sIdx} className="space-y-1.5">
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="text-[11px] uppercase tracking-widest text-slate-400 flex items-center gap-2">
                                            {section.icon && <span>{section.icon}</span>}
                                            {section.heading && <span>{section.heading}</span>}
                                        </div>
                                        {/* Section gets a generic insight chip — backend doesn't yet
                                            split classical vs pillar refs by section. */}
                                        {section.citations && section.citations.length > 0 && (
                                            <SectionTag label={`${section.citations.length} ref${section.citations.length > 1 ? 's' : ''}`} tone="insight" />
                                        )}
                                    </div>
                                    {section.tagline && (
                                        <p className="text-[12px] text-slate-500">{section.tagline}</p>
                                    )}
                                    {section.bullets && section.bullets.length > 0 && (
                                        <ul className="space-y-1.5 pl-1">
                                            {section.bullets.map((b, bi) => (
                                                <li
                                                    key={bi}
                                                    className="flex items-start gap-2 text-[13px] leading-relaxed text-slate-200"
                                                >
                                                    {b.icon && <span>{b.icon}</span>}
                                                    <span>{b.text}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}

                    {collectedCitations.length > 0 && (
                        <div className="space-y-2 pt-2">
                            <div className="text-[10px] uppercase tracking-widest text-slate-500">
                                Sources
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {collectedCitations.map((cid) => (
                                    <SectionTag
                                        key={cid}
                                        label={cid}
                                        tone={
                                            /classic|zhen quan|滴天|子平|三命/i.test(cid)
                                                ? 'classical'
                                                : 'pillar'
                                        }
                                    />
                                ))}
                            </div>
                        </div>
                    )}

                    {yearPredictions.length > 0 && (
                        <div className="space-y-2 pt-2">
                            <div className="text-[10px] uppercase tracking-widest text-slate-500">
                                Timeline
                            </div>
                            <div className="space-y-1.5">
                                {yearPredictions.map((yp) => (
                                    <div
                                        key={yp.year}
                                        className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-1.5"
                                    >
                                        <span
                                            className="text-[12px] font-medium tabular-nums"
                                            style={{ color: accentColor }}
                                        >
                                            {yp.year}
                                        </span>
                                        <span className="text-[12px] text-slate-300 flex-1">
                                            {yp.prediction}
                                        </span>
                                        {typeof yp.confidence === 'number' && (
                                            <span className="text-[10px] text-slate-500">
                                                {Math.round(yp.confidence * 100)}%
                                            </span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </DisclosureAccordion>
            )}
        </motion.div>
    );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const OracleChat: React.FC<OracleChatProps> = ({
    messages,
    input,
    onInputChange,
    onSend,
    suggestions = [],
    accentColor = '#14b8a6',
    isLoading = false,
    memoryDegraded = false,
    disabled = false,
    flowFocus,
}) => {
    const scrollRef = useRef<HTMLDivElement>(null);
    const pendingSteps = useSimulatedReasoning(isLoading);

    // The most recent user turn is what the next /ask call will dispatch on,
    // so use it (plus flowFocus as fallback) to name the specialist chip.
    const lastUserText = useMemo(() => {
        for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].role === 'user') return messages[i].content;
        }
        return '';
    }, [messages]);
    const specialistLabel = useMemo(
        () => inferSpecialistLabel(lastUserText, flowFocus),
        [lastUserText, flowFocus],
    );

    useEffect(() => {
        scrollRef.current?.scrollTo({
            top: scrollRef.current.scrollHeight,
            behavior: 'smooth',
        });
    }, [messages.length, pendingSteps.length]);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onSend();
        }
    };

    // The follow-up pills row replaces the old "suggestions only show on first
    // message" behavior — we now always show 3 pills under the latest agent
    // turn so users have a way back into the conversation. Falls back to the
    // first 3 suggestions from the parent.
    const followUps = suggestions.slice(0, 3);
    const lastAgentIdx = (() => {
        for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].role === 'agent') return i;
        }
        return -1;
    })();

    return (
        <div className="flex flex-col h-[60vh] max-h-[560px]">
            {memoryDegraded && (
                <div className="flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 p-2 mb-3 text-[11px] text-amber-400">
                    <AlertCircle className="w-3.5 h-3.5 flex-none" />
                    Memory is limited — the oracle may not recall earlier context.
                </div>
            )}

            <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-4 mb-3 pr-1 scrollbar-hide">
                <AnimatePresence initial={false}>
                    {messages.map((msg) =>
                        msg.role === 'user' ? (
                            <UserBubble key={msg.id} text={msg.content} />
                        ) : (
                            <AgentBubble
                                key={msg.id}
                                msg={msg}
                                accentColor={accentColor}
                            />
                        ),
                    )}
                </AnimatePresence>

                {/* In-flight pending bubble — only shown while loading */}
                {isLoading && (
                    <AgentBubble
                        msg={{ id: '__pending', role: 'agent', content: '' }}
                        accentColor={accentColor}
                        pendingSteps={pendingSteps}
                        isPending
                        specialistLabel={specialistLabel}
                    />
                )}

                {/* Follow-up pills under the latest agent turn (kept persistent
                    so users always have an on-ramp, not just on first message) */}
                {!isLoading && lastAgentIdx >= 0 && followUps.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex flex-wrap gap-1.5 pt-1"
                    >
                        {followUps.map((s, i) => {
                            const meta = [
                                { kind: 'Deepen', icon: <Sparkles className="h-2.5 w-2.5" /> },
                                { kind: 'Action', icon: <Target className="h-2.5 w-2.5" /> },
                                { kind: 'Recap', icon: <Brain className="h-2.5 w-2.5" /> },
                            ][i] || { kind: 'Ask', icon: <Sparkles className="h-2.5 w-2.5" /> };
                            return (
                                <button
                                    key={s}
                                    type="button"
                                    onClick={() => onInputChange(s)}
                                    className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-slate-300 hover:bg-white/[0.07]"
                                >
                                    <span className="text-slate-500">{meta.icon}</span>
                                    <span className="text-[10px] uppercase tracking-widest text-slate-500">
                                        {meta.kind}
                                    </span>
                                    <span>{s}</span>
                                </button>
                            );
                        })}
                    </motion.div>
                )}
            </div>

            {/* Suggestion chips — pre-conversation only (cold start onboarding) */}
            {suggestions.length > 0 && messages.length === 0 && !isLoading && (
                <div className="flex flex-wrap gap-1.5 mb-3">
                    {suggestions.map((s) => (
                        <button
                            key={s}
                            type="button"
                            onClick={() => onInputChange(s)}
                            className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-slate-400 transition-colors hover:bg-white/[0.06] hover:text-slate-200"
                        >
                            {s}
                        </button>
                    ))}
                </div>
            )}

            <div className="flex items-end gap-2">
                <textarea
                    value={input}
                    onChange={(e) => onInputChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask the oracle..."
                    disabled={disabled || isLoading}
                    rows={1}
                    className="flex-1 resize-none rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
                    style={{ maxHeight: 100, minHeight: 38 }}
                    onFocus={(e) => {
                        e.currentTarget.style.borderColor = `${accentColor}88`;
                        e.currentTarget.style.boxShadow = `0 0 0 2px ${accentColor}33`;
                    }}
                    onBlur={(e) => {
                        e.currentTarget.style.borderColor = '';
                        e.currentTarget.style.boxShadow = '';
                    }}
                />
                <button
                    type="button"
                    onClick={onSend}
                    disabled={disabled || isLoading || !input.trim()}
                    className="flex h-[38px] w-[38px] flex-none items-center justify-center rounded-xl border transition-colors"
                    style={{
                        borderColor: `${accentColor}33`,
                        background: input.trim() ? `${accentColor}1A` : 'transparent',
                        color: input.trim() ? accentColor : '#64748b',
                    }}
                >
                    <Send className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};
