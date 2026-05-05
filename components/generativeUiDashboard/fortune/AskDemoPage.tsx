/**
 * AskDemoPage — three live mockups of the redesigned Ask-the-Oracle tab.
 *
 * Routes:
 *   /project/fortune-agent/ask-demo        index with concept summaries + links
 *   /project/fortune-agent/ask-demo/a      Concept A — Streaming Oracle
 *   /project/fortune-agent/ask-demo/b      Concept B — Context Anchored
 *   /project/fortune-agent/ask-demo/c      Concept C — Progressive Disclosure
 *
 * No backend wiring. A single shared `useFakeStream` hook simulates the SSE
 * event sequence (routing → reasoning → verdict → narrative → citations →
 * follow-up pills → done) on setTimeout, so the user can FEEL the
 * perceived-latency curve of each concept side-by-side. A "Demo speed"
 * toggle compresses the realistic ~45s timeline into ~15s for fast review.
 *
 * Called from: App.tsx routes. Forwards: nothing (presentational only).
 * Exists because: before committing to the SSE backend (see the redesign
 * spec at ~/homer/output/gemini/fortune-ask-redesign-spec-2026-05-04-1240.md)
 * we want the user to compare A / B / C visually with the same mock answer.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
    BookOpen,
    Brain,
    ChevronDown,
    ChevronLeft,
    Compass,
    Layers,
    Loader2,
    Send,
    Sparkles,
    Target,
    Wand2,
    Zap,
} from 'lucide-react';

import { CITATION_GOLD, FLOW_ACCENTS, GLASS } from './designTokens';

// ---------------------------------------------------------------------------
// Mock answer — same data feeds all three variants so they're comparable.
// English-only by construction (no Chinese characters anywhere).
// ---------------------------------------------------------------------------

interface ReasoningStep { id: string; label: string }
interface CitationItem {
    id: string;
    label: string;
    detail: string;
    kind: 'pillar' | 'insight' | 'classical';
}
interface NarrativeBullet { icon: string; text: string }
interface NarrativeSection {
    id: string;
    icon: string;
    heading: string;
    tagline: string;
    bullets: NarrativeBullet[];
}
interface YearPrediction { year: number; prediction: string; confidence: number }
interface FollowUpPills { deepen: string; action: string; recap: string }

interface MockAnswer {
    question: string;
    specialist: 'career' | 'wealth' | 'relationship' | 'timing' | 'general';
    reasoning: ReasoningStep[];
    verdict: string;
    sections: NarrativeSection[];
    citations: CitationItem[];
    yearPredictions: YearPrediction[];
    followUp: FollowUpPills;
}

const MOCK: MockAnswer = {
    question: 'Should I switch jobs in 2026?',
    specialist: 'career',
    reasoning: [
        { id: 's1', label: 'Mapping the Four Pillars' },
        { id: 's2', label: 'Reading the 2026 Fire Horse year' },
        { id: 's3', label: 'Locating your Direct Wealth star' },
        { id: 's4', label: 'Synthesizing the decision' },
    ],
    verdict:
        'Yes — but only if the new role activates your Direct Wealth star and gives you cleaner scope.',
    sections: [
        {
            id: 'timing_window',
            icon: '🕐',
            heading: 'Timing window',
            tagline: 'When the chart lets you move and when it tells you to wait.',
            bullets: [
                { icon: '🟢', text: 'Promotion offers cluster Mar–May 2026 as Fire Horse warms your Wood Day Master.' },
                { icon: '🟡', text: 'Sign before late August — there is a clash month that muddies negotiations.' },
                { icon: '🔄', text: 'A second window opens Nov 2026 if the spring deal does not land.' },
            ],
        },
        {
            id: 'what_to_screen_for',
            icon: '🎯',
            heading: 'What to screen for',
            tagline: 'Three filters for whether the offer is actually worth it.',
            bullets: [
                { icon: '📈', text: 'Title growth, not just pay — your chart rewards structural elevation.' },
                { icon: '🤝', text: 'A manager who values output stars — Hurt Officer needs room to ship.' },
                { icon: '🧭', text: 'Clear cross-functional scope; ambiguous remits cost you the year.' },
            ],
        },
    ],
    citations: [
        { id: 'c1', label: 'Year Pillar 2026', detail: 'Fire Horse — heat lifts your Wood Day Master', kind: 'pillar' },
        { id: 'c2', label: 'Day Pillar', detail: 'Wood Tiger — initiative + visibility', kind: 'pillar' },
        { id: 'c3', label: 'Insight #2 (Why tab)', detail: 'Direct Wealth in month stem signals salary leverage', kind: 'insight' },
        { id: 'c4', label: 'Zi Ping Zhen Quan · Ch. 4', detail: 'Classical reading on Direct Wealth conditions', kind: 'classical' },
    ],
    yearPredictions: [
        { year: 2026, prediction: 'Direct Wealth peaks; new role lands.', confidence: 0.82 },
        { year: 2027, prediction: 'Operational consolidation — protect scope.', confidence: 0.7 },
        { year: 2028, prediction: 'Metal-element challenge; mind politics.', confidence: 0.6 },
    ],
    followUp: {
        deepen: 'Tell me more about my Direct Wealth star',
        action: 'What should I look for in the offer?',
        recap: 'Summarize this in one sentence',
    },
};

// ---------------------------------------------------------------------------
// Fake-stream simulator — emits a sequence of phases on setTimeout.
// Returns the *current* phase + which reasoning steps + how much of the
// verdict has streamed + which sections / citations / pills have arrived.
// ---------------------------------------------------------------------------

type Phase =
    | 'idle'
    | 'submitted'
    | 'routing'
    | 'streaming-verdict'
    | 'streaming-body'
    | 'complete';

interface StreamState {
    phase: Phase;
    reasoning: ReasoningStep[];
    verdictPartial: string;
    sectionsRevealed: number;
    bulletsRevealed: number;
    citationsRevealed: number;
    pillsVisible: boolean;
    elapsedMs: number;
}

const INITIAL_STATE: StreamState = {
    phase: 'idle',
    reasoning: [],
    verdictPartial: '',
    sectionsRevealed: 0,
    bulletsRevealed: 0,
    citationsRevealed: 0,
    pillsVisible: false,
    elapsedMs: 0,
};

interface UseFakeStreamReturn {
    state: StreamState;
    start: () => void;
    reset: () => void;
    isRunning: boolean;
}

function useFakeStream(answer: MockAnswer, speed: 1 | 3): UseFakeStreamReturn {
    const [state, setState] = useState<StreamState>(INITIAL_STATE);
    const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
    const startTimeRef = useRef<number | null>(null);

    const clearAll = useCallback(() => {
        timersRef.current.forEach((t) => clearTimeout(t));
        timersRef.current = [];
        startTimeRef.current = null;
    }, []);

    const reset = useCallback(() => {
        clearAll();
        setState(INITIAL_STATE);
    }, [clearAll]);

    useEffect(() => () => clearAll(), [clearAll]);

    const start = useCallback(() => {
        clearAll();
        startTimeRef.current = Date.now();
        const tick = () => {
            const elapsed = startTimeRef.current ? Date.now() - startTimeRef.current : 0;
            setState((s) => ({ ...s, elapsedMs: elapsed }));
        };
        // Soft tick for the elapsed counter — every 200ms.
        const tickInterval = setInterval(tick, 200);
        timersRef.current.push(tickInterval as unknown as ReturnType<typeof setTimeout>);

        // Schedule a list of (delayMs, partialState) updates. delays scale with speed.
        const schedule = (atMs: number, mutate: (s: StreamState) => StreamState) => {
            const t = setTimeout(() => {
                setState((s) => mutate(s));
            }, atMs / speed);
            timersRef.current.push(t);
        };

        // submitted → routing
        schedule(0, (s) => ({ ...s, phase: 'submitted' }));
        schedule(400, (s) => ({ ...s, phase: 'routing' }));

        // reasoning steps
        answer.reasoning.forEach((step, i) => {
            schedule(900 + i * 1500, (s) => ({
                ...s,
                phase: i === 0 ? 'streaming-verdict' : s.phase,
                reasoning: [...s.reasoning, step],
            }));
        });

        // verdict streams token by token
        const verdictTokens = answer.verdict.split(' ');
        const verdictStartMs = 900 + answer.reasoning.length * 1500 + 600;
        verdictTokens.forEach((_tok, i) => {
            schedule(verdictStartMs + i * 70, (s) => ({
                ...s,
                phase: 'streaming-verdict',
                verdictPartial: verdictTokens.slice(0, i + 1).join(' '),
            }));
        });
        const verdictEndMs = verdictStartMs + verdictTokens.length * 70;

        // body streams: section by section, bullet by bullet
        let bodyCursor = verdictEndMs + 600;
        schedule(bodyCursor, (s) => ({ ...s, phase: 'streaming-body' }));
        let totalBullets = 0;
        answer.sections.forEach((section, i) => {
            bodyCursor += 600;
            schedule(bodyCursor, (s) => ({ ...s, sectionsRevealed: i + 1 }));
            section.bullets.forEach(() => {
                bodyCursor += 350;
                totalBullets += 1;
                const at = totalBullets;
                schedule(bodyCursor, (s) => ({ ...s, bulletsRevealed: at }));
            });
        });

        // citations roll in
        answer.citations.forEach((_, i) => {
            bodyCursor += 250;
            schedule(bodyCursor, (s) => ({ ...s, citationsRevealed: i + 1 }));
        });

        // follow-up pills + done
        bodyCursor += 600;
        schedule(bodyCursor, (s) => ({ ...s, pillsVisible: true }));
        schedule(bodyCursor + 200, (s) => ({ ...s, phase: 'complete' }));
        // Freeze the elapsed-time ticker once done. Use a raw setTimeout
        // (not `schedule`) because we don't want to mutate state here —
        // returning anything other than a valid StreamState would crash
        // the next render.
        timersRef.current.push(
            setTimeout(() => clearInterval(tickInterval), (bodyCursor + 400) / speed),
        );
    }, [answer, clearAll, speed]);

    const isRunning = state.phase !== 'idle' && state.phase !== 'complete';
    return { state, start, reset, isRunning };
}

// ---------------------------------------------------------------------------
// Shared UI atoms
// ---------------------------------------------------------------------------

const ACCENT = FLOW_ACCENTS.wish; // teal — neutral demo accent
const FORTUNE_SERIF = "'Cormorant Garamond', 'Playfair Display', Georgia, serif";

interface UserBubbleProps { text: string }
const UserBubble: React.FC<UserBubbleProps> = ({ text }) => (
    <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-end"
    >
        <div className="max-w-[80%] rounded-2xl bg-white/10 px-4 py-3 text-sm text-slate-100">
            {text}
        </div>
    </motion.div>
);

interface DemoChromeProps {
    title: string;
    blurb: string;
    state: StreamState;
    onReplay: () => void;
    speed: 1 | 3;
    onSpeedChange: (s: 1 | 3) => void;
    children: React.ReactNode;
}
const DemoChrome: React.FC<DemoChromeProps> = ({
    title,
    blurb,
    state,
    onReplay,
    speed,
    onSpeedChange,
    children,
}) => (
    <div className="min-h-screen bg-[#0B1120] text-slate-200">
        <div className="mx-auto max-w-[640px] px-5 pt-10 pb-32">
            <div className="flex items-center justify-between mb-8">
                <Link
                    to="/project/fortune-agent/ask-demo"
                    className="flex items-center gap-1 text-[11px] uppercase tracking-widest text-slate-500 hover:text-slate-300"
                >
                    <ChevronLeft className="h-3 w-3" /> Back to overview
                </Link>
                <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase tracking-widest text-slate-500">Demo speed</span>
                    <div className="flex rounded-full border border-white/10 bg-white/5 p-0.5 text-[10px]">
                        {([1, 3] as const).map((s) => (
                            <button
                                key={s}
                                type="button"
                                onClick={() => onSpeedChange(s)}
                                className={`px-2 py-0.5 rounded-full transition-colors ${
                                    speed === s
                                        ? 'bg-white/10 text-slate-100'
                                        : 'text-slate-500 hover:text-slate-300'
                                }`}
                            >
                                {s}×
                            </button>
                        ))}
                    </div>
                    <button
                        type="button"
                        onClick={onReplay}
                        className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[11px] text-slate-300 hover:bg-white/[0.08]"
                    >
                        Replay
                    </button>
                </div>
            </div>

            <div className="mb-8">
                <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">Concept</div>
                <h1
                    className="mt-1 text-3xl text-slate-100"
                    style={{ fontFamily: FORTUNE_SERIF, fontStyle: 'italic' }}
                >
                    {title}
                </h1>
                <p className="mt-2 text-sm text-slate-400 leading-relaxed">{blurb}</p>
                <div className="mt-3 text-[10px] uppercase tracking-widest text-slate-500">
                    Elapsed {(state.elapsedMs / 1000).toFixed(1)}s · phase {state.phase}
                </div>
            </div>

            <div className={`${GLASS} p-5`}>
                <div className="space-y-4">
                    <UserBubble text={MOCK.question} />
                    {children}
                </div>

                <div className="mt-8 flex items-end gap-2 border-t border-white/5 pt-4">
                    <textarea
                        disabled
                        rows={1}
                        placeholder="Ask the oracle…"
                        className="flex-1 resize-none rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5 text-xs text-slate-200 placeholder-slate-600"
                        style={{ minHeight: 38 }}
                    />
                    <button
                        type="button"
                        disabled
                        className="flex h-[38px] w-[38px] items-center justify-center rounded-xl border border-teal-500/30 text-slate-600"
                    >
                        <Send className="h-4 w-4" />
                    </button>
                </div>
            </div>
        </div>
    </div>
);

// ---------------------------------------------------------------------------
// Concept A — Streaming Oracle
// Reasoning breadcrumb chips animate in, then verdict streams word-by-word,
// then a 3-line skeleton shows under it while the body finalizes.
// ---------------------------------------------------------------------------

const SpecialistChip: React.FC<{ label: string; color: string }> = ({ label, color }) => (
    <motion.span
        layout
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.25 }}
        className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-widest"
        style={{
            borderColor: `${color}55`,
            background: `${color}1A`,
            color,
        }}
    >
        <Compass className="h-2.5 w-2.5" />
        {label}
    </motion.span>
);

const ReasoningBreadcrumbs: React.FC<{ steps: ReasoningStep[] }> = ({ steps }) => (
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
                    <Loader2 className="h-2.5 w-2.5 animate-spin text-teal-400" />
                    {step.label}
                </motion.span>
            ))}
        </AnimatePresence>
    </div>
);

const SkeletonReveal: React.FC<{ active: boolean; lines?: number }> = ({ active, lines = 3 }) => (
    <AnimatePresence>
        {active && (
            <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="space-y-2 overflow-hidden"
            >
                {Array.from({ length: lines }).map((_, i) => (
                    <motion.div
                        key={i}
                        animate={{ opacity: [0.25, 0.55, 0.25] }}
                        transition={{ duration: 1.6, repeat: Infinity, delay: i * 0.2 }}
                        className="h-3 rounded bg-white/5"
                        style={{ width: `${85 - i * 12}%` }}
                    />
                ))}
            </motion.div>
        )}
    </AnimatePresence>
);

const ConceptA: React.FC = () => {
    const [speed, setSpeed] = useState<1 | 3>(3);
    const stream = useFakeStream(MOCK, speed);

    useEffect(() => {
        // Auto-start on mount.
        stream.start();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [speed]);

    const { state } = stream;
    const showSkeleton =
        state.phase === 'streaming-body' && state.bulletsRevealed < 3;

    return (
        <DemoChrome
            title="Streaming Oracle"
            blurb="Reasoning breadcrumbs + token-by-token verdict + skeleton-while-body-cooks. Maximum perceived speed; the wait is filled with visible work."
            state={state}
            onReplay={stream.start}
            speed={speed}
            onSpeedChange={setSpeed}
        >
            {state.phase !== 'idle' && (
                <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className="rounded-2xl border-l-2 border-teal-500/40 bg-white/[0.02] p-4 space-y-3"
                >
                    {state.phase === 'routing' || state.reasoning.length > 0 ? (
                        <div className="flex items-center gap-2 flex-wrap">
                            <SpecialistChip label="Career specialist" color={ACCENT.primary} />
                            <ReasoningBreadcrumbs steps={state.reasoning} />
                        </div>
                    ) : null}

                    {state.verdictPartial && (
                        <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="text-base leading-relaxed text-slate-100"
                        >
                            {state.verdictPartial}
                            {state.phase === 'streaming-verdict' && (
                                <motion.span
                                    animate={{ opacity: [0.3, 1, 0.3] }}
                                    transition={{ duration: 1, repeat: Infinity }}
                                    className="ml-1 inline-block h-3 w-1.5 bg-teal-400 align-middle"
                                />
                            )}
                        </motion.p>
                    )}

                    <SkeletonReveal active={showSkeleton} />

                    {state.bulletsRevealed > 0 && (
                        <div className="space-y-3 pt-1">
                            {MOCK.sections.map((section, sIdx) => {
                                const visibleBullets = section.bullets.slice(
                                    0,
                                    Math.max(
                                        0,
                                        state.bulletsRevealed -
                                            MOCK.sections.slice(0, sIdx).reduce((a, s) => a + s.bullets.length, 0),
                                    ),
                                );
                                if (state.sectionsRevealed <= sIdx) return null;
                                return (
                                    <motion.div
                                        key={section.id}
                                        initial={{ opacity: 0, y: 4 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="space-y-1.5"
                                    >
                                        <div className="flex items-center gap-2 text-[11px] uppercase tracking-widest text-slate-400">
                                            <span>{section.icon}</span>
                                            <span>{section.heading}</span>
                                        </div>
                                        <ul className="space-y-1.5 pl-1">
                                            {visibleBullets.map((b, i) => (
                                                <motion.li
                                                    key={i}
                                                    initial={{ opacity: 0, x: -4 }}
                                                    animate={{ opacity: 1, x: 0 }}
                                                    className="flex items-start gap-2 text-[13px] leading-relaxed text-slate-200"
                                                >
                                                    <span>{b.icon}</span>
                                                    <span>{b.text}</span>
                                                </motion.li>
                                            ))}
                                        </ul>
                                    </motion.div>
                                );
                            })}
                        </div>
                    )}

                    {state.pillsVisible && (
                        <FollowUpRow follow={MOCK.followUp} />
                    )}
                </motion.div>
            )}
        </DemoChrome>
    );
};

// ---------------------------------------------------------------------------
// Concept B — Context Anchored
// Same chat layout, but each claim is anchored to a clickable source chip.
// Hover any chip to see what data it points to (no actual scroll-cite, just
// a tooltip card to convey the interaction).
// ---------------------------------------------------------------------------

const SourceChip: React.FC<{ citation: CitationItem; onActivate: (c: CitationItem) => void }> = ({
    citation,
    onActivate,
}) => {
    const styles = useMemo(() => {
        if (citation.kind === 'classical') {
            return {
                color: CITATION_GOLD,
                bg: `${CITATION_GOLD}1A`,
                border: `${CITATION_GOLD}55`,
            };
        }
        if (citation.kind === 'pillar') {
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
    }, [citation.kind]);

    return (
        <button
            type="button"
            onClick={() => onActivate(citation)}
            className="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] uppercase tracking-wide transition-transform hover:scale-105"
            style={{ borderColor: styles.border, background: styles.bg, color: styles.color }}
        >
            <BookOpen className="h-2.5 w-2.5" />
            {citation.label}
        </button>
    );
};

const ConceptB: React.FC = () => {
    const [speed, setSpeed] = useState<1 | 3>(3);
    const stream = useFakeStream(MOCK, speed);
    const [hovered, setHovered] = useState<CitationItem | null>(null);

    useEffect(() => {
        stream.start();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [speed]);

    const { state } = stream;

    // Map citations into specific anchors inside the verdict + sections.
    const visibleCites = MOCK.citations.slice(0, state.citationsRevealed);
    const citeByLabel = (label: string) => visibleCites.find((c) => c.label === label);

    return (
        <DemoChrome
            title="Context Anchored"
            blurb="Every claim links back to a chart pillar, a Why-tab insight, or a classical citation. Hover any chip to preview the source — turns the chat into a browser of your own reading."
            state={state}
            onReplay={stream.start}
            speed={speed}
            onSpeedChange={setSpeed}
        >
            {state.phase !== 'idle' && (
                <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-2xl border-l-2 border-rose-500/30 bg-white/[0.02] p-4 space-y-3"
                >
                    {state.reasoning.length > 0 && state.phase !== 'complete' && (
                        <div className="text-[10px] uppercase tracking-widest text-slate-500">
                            {state.reasoning[state.reasoning.length - 1].label}…
                        </div>
                    )}

                    {state.verdictPartial && (
                        <p className="text-base leading-relaxed text-slate-100">
                            {state.verdictPartial}
                            {state.phase === 'streaming-verdict' && (
                                <motion.span
                                    animate={{ opacity: [0.3, 1, 0.3] }}
                                    transition={{ duration: 1, repeat: Infinity }}
                                    className="ml-1 inline-block h-3 w-1.5 bg-rose-400 align-middle"
                                />
                            )}
                            {citeByLabel('Year Pillar 2026') && (
                                <span className="ml-1 inline-flex align-middle">
                                    <SourceChip
                                        citation={citeByLabel('Year Pillar 2026')!}
                                        onActivate={setHovered}
                                    />
                                </span>
                            )}
                        </p>
                    )}

                    {state.bulletsRevealed > 0 && (
                        <div className="space-y-3 pt-1">
                            {MOCK.sections.map((section, sIdx) => {
                                const visible = section.bullets.slice(
                                    0,
                                    Math.max(
                                        0,
                                        state.bulletsRevealed -
                                            MOCK.sections.slice(0, sIdx).reduce((a, s) => a + s.bullets.length, 0),
                                    ),
                                );
                                if (state.sectionsRevealed <= sIdx) return null;
                                const sectionCite = sIdx === 0
                                    ? citeByLabel('Day Pillar')
                                    : citeByLabel('Insight #2 (Why tab)');
                                return (
                                    <div key={section.id} className="space-y-1.5">
                                        <div className="flex items-center justify-between gap-2 text-[11px] uppercase tracking-widest text-slate-400">
                                            <span className="flex items-center gap-2">
                                                <span>{section.icon}</span>
                                                <span>{section.heading}</span>
                                            </span>
                                            {sectionCite && (
                                                <SourceChip citation={sectionCite} onActivate={setHovered} />
                                            )}
                                        </div>
                                        <ul className="space-y-1.5 pl-1">
                                            {visible.map((b, i) => (
                                                <li
                                                    key={i}
                                                    className="flex items-start gap-2 text-[13px] leading-relaxed text-slate-200"
                                                >
                                                    <span>{b.icon}</span>
                                                    <span>{b.text}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {state.citationsRevealed > 0 && (
                        <div className="border-t border-white/5 pt-3 space-y-2">
                            <div className="text-[10px] uppercase tracking-widest text-slate-500">Sources</div>
                            <div className="flex flex-wrap gap-1.5">
                                {visibleCites.map((c) => (
                                    <SourceChip key={c.id} citation={c} onActivate={setHovered} />
                                ))}
                            </div>
                        </div>
                    )}

                    <AnimatePresence>
                        {hovered && (
                            <motion.div
                                initial={{ opacity: 0, y: 4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="rounded-xl border border-white/10 bg-black/40 p-3 text-[12px] text-slate-300"
                            >
                                <div
                                    className="text-[10px] uppercase tracking-widest mb-1"
                                    style={{
                                        color:
                                            hovered.kind === 'classical'
                                                ? CITATION_GOLD
                                                : hovered.kind === 'pillar'
                                                ? '#5eead4'
                                                : '#a5b4fc',
                                    }}
                                >
                                    {hovered.label}
                                </div>
                                <div>{hovered.detail}</div>
                                <button
                                    type="button"
                                    onClick={() => setHovered(null)}
                                    className="mt-2 text-[10px] uppercase tracking-widest text-slate-500 hover:text-slate-300"
                                >
                                    Dismiss
                                </button>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {state.pillsVisible && (
                        <FollowUpRow follow={MOCK.followUp} />
                    )}
                </motion.div>
            )}
        </DemoChrome>
    );
};

// ---------------------------------------------------------------------------
// Concept C — Progressive Disclosure
// Verdict header in serif italic, single "Go deeper" accordion that opens
// the structured analysis (sections, citations, year predictions).
// ---------------------------------------------------------------------------

const DisclosureAccordion: React.FC<{
    title: string;
    defaultExpanded?: boolean;
    children: React.ReactNode;
}> = ({ title, defaultExpanded = false, children }) => {
    const [open, setOpen] = useState(defaultExpanded);
    return (
        <div className="rounded-xl border border-white/5 bg-white/[0.02]">
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                className="flex w-full items-center justify-between px-4 py-3 text-[11px] uppercase tracking-widest text-slate-300 hover:text-slate-100"
            >
                <span className="flex items-center gap-2">
                    <Layers className="h-3 w-3" />
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

const ConceptC: React.FC = () => {
    const [speed, setSpeed] = useState<1 | 3>(3);
    const stream = useFakeStream(MOCK, speed);

    useEffect(() => {
        stream.start();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [speed]);

    const { state } = stream;
    const verdictDone = state.phase === 'streaming-body' || state.phase === 'complete';

    return (
        <DemoChrome
            title="Progressive Disclosure"
            blurb="Verdict-first oracle quote. Detail lives in a single 'Go deeper' fold that maps 1:1 to the EnrichedNarrativeOutput shape — minimal noise, maximum impact, and a clean trust hierarchy."
            state={state}
            onReplay={stream.start}
            speed={speed}
            onSpeedChange={setSpeed}
        >
            {state.phase !== 'idle' && (
                <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-2xl border-l-2 border-indigo-500/30 bg-white/[0.02] p-5 space-y-4"
                >
                    {state.reasoning.length > 0 && !verdictDone && (
                        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-500">
                            <Loader2 className="h-3 w-3 animate-spin text-indigo-300" />
                            {state.reasoning[state.reasoning.length - 1].label}
                        </div>
                    )}

                    {state.verdictPartial && (
                        <div className="border-b border-white/5 pb-4">
                            <div className="text-[9px] uppercase tracking-[0.3em] text-indigo-300/80 mb-1.5">
                                Verdict
                            </div>
                            <p
                                className="text-xl leading-snug text-slate-100"
                                style={{ fontFamily: FORTUNE_SERIF, fontStyle: 'italic' }}
                            >
                                {state.verdictPartial}
                                {state.phase === 'streaming-verdict' && (
                                    <motion.span
                                        animate={{ opacity: [0.3, 1, 0.3] }}
                                        transition={{ duration: 1, repeat: Infinity }}
                                        className="ml-1 inline-block h-4 w-1.5 bg-indigo-300 align-middle"
                                    />
                                )}
                            </p>
                        </div>
                    )}

                    {verdictDone && (
                        <DisclosureAccordion title="Go deeper" defaultExpanded={false}>
                            <div className="space-y-3">
                                {MOCK.sections.slice(0, state.sectionsRevealed).map((section) => (
                                    <div key={section.id} className="space-y-1.5">
                                        <div className="text-[11px] uppercase tracking-widest text-slate-400">
                                            <span className="mr-2">{section.icon}</span>
                                            {section.heading}
                                        </div>
                                        <p className="text-[12px] text-slate-500">{section.tagline}</p>
                                        <ul className="space-y-1.5 pl-1">
                                            {section.bullets.map((b, i) => (
                                                <li
                                                    key={i}
                                                    className="flex items-start gap-2 text-[13px] leading-relaxed text-slate-200"
                                                >
                                                    <span>{b.icon}</span>
                                                    <span>{b.text}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                ))}
                            </div>

                            {state.citationsRevealed > 0 && (
                                <div className="space-y-2 pt-2">
                                    <div className="text-[10px] uppercase tracking-widest text-slate-500">
                                        Citations
                                    </div>
                                    {MOCK.citations.slice(0, state.citationsRevealed).map((c) => (
                                        <div
                                            key={c.id}
                                            className="rounded-lg border-l-2 px-3 py-2 text-[12px]"
                                            style={{
                                                borderColor:
                                                    c.kind === 'classical'
                                                        ? `${CITATION_GOLD}88`
                                                        : 'rgba(99,102,241,0.4)',
                                                background:
                                                    c.kind === 'classical'
                                                        ? `${CITATION_GOLD}0A`
                                                        : 'rgba(99,102,241,0.05)',
                                            }}
                                        >
                                            <div
                                                className="text-[10px] uppercase tracking-widest"
                                                style={{
                                                    color:
                                                        c.kind === 'classical'
                                                            ? CITATION_GOLD
                                                            : '#a5b4fc',
                                                }}
                                            >
                                                {c.label}
                                            </div>
                                            <div className="text-slate-300 mt-0.5">{c.detail}</div>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {state.phase === 'complete' && MOCK.yearPredictions.length > 0 && (
                                <div className="space-y-2 pt-2">
                                    <div className="text-[10px] uppercase tracking-widest text-slate-500">
                                        Timeline
                                    </div>
                                    <div className="space-y-1.5">
                                        {MOCK.yearPredictions.map((yp) => (
                                            <div
                                                key={yp.year}
                                                className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-1.5"
                                            >
                                                <span
                                                    className="text-[12px] font-medium tabular-nums"
                                                    style={{ color: ACCENT.primary }}
                                                >
                                                    {yp.year}
                                                </span>
                                                <span className="text-[12px] text-slate-300 flex-1">
                                                    {yp.prediction}
                                                </span>
                                                <span className="text-[10px] text-slate-500">
                                                    {Math.round(yp.confidence * 100)}%
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </DisclosureAccordion>
                    )}

                    {state.pillsVisible && (
                        <FollowUpRow follow={MOCK.followUp} />
                    )}
                </motion.div>
            )}
        </DemoChrome>
    );
};

// ---------------------------------------------------------------------------
// Concept D — Verdict-First Hybrid (the recommended one)
//
// Pre-verdict phase   : breadcrumbs from A (specialist chip + animated steps)
//                       so the wait is filled with visible work.
// Verdict phase       : large serif italic from C — the calm "oracle" beat.
// Post-verdict phase  : single "Go deeper" accordion from C, but each section
//                       header carries B's source chip and a Sources strip
//                       sits at the bottom — every claim is anchored.
// Always              : reasoning strip collapses into a single muted "trail"
//                       chip after verdict so the breadcrumbs don't compete
//                       with the verdict for attention. Click it to re-expand.
// ---------------------------------------------------------------------------

const ReasoningTrailChip: React.FC<{ steps: ReasoningStep[]; defaultOpen?: boolean }> = ({
    steps,
    defaultOpen = false,
}) => {
    const [open, setOpen] = useState(defaultOpen);
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

const ConceptD: React.FC = () => {
    const [speed, setSpeed] = useState<1 | 3>(3);
    const stream = useFakeStream(MOCK, speed);
    const [hovered, setHovered] = useState<CitationItem | null>(null);

    useEffect(() => {
        stream.start();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [speed]);

    const { state } = stream;
    const verdictDone = state.phase === 'streaming-body' || state.phase === 'complete';
    const visibleCites = MOCK.citations.slice(0, state.citationsRevealed);
    const citeByLabel = (label: string) => visibleCites.find((c) => c.label === label);

    // Pre-verdict accent uses the function color; verdict uses indigo (oracle).
    const oracleAccent = '#a5b4fc';

    return (
        <DemoChrome
            title="Hybrid (recommended)"
            blurb="The build target. Pre-verdict: A's reasoning breadcrumbs fill the wait. Verdict lands big in serif italic — C's calm oracle beat. Post-verdict: detail collapses into a single 'Go deeper' fold whose claims are anchored to source chips (B). Breadcrumbs collapse into a muted trail chip so they never fight the verdict for attention."
            state={state}
            onReplay={stream.start}
            speed={speed}
            onSpeedChange={setSpeed}
        >
            {state.phase !== 'idle' && (
                <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-2xl border-l-2 border-indigo-500/30 bg-white/[0.02] p-5 space-y-4"
                >
                    {/* Pre-verdict: breadcrumbs (A's pattern). Once verdict lands they
                        collapse into a single muted trail chip the user can re-expand. */}
                    {!verdictDone ? (
                        <div className="flex flex-col gap-2">
                            <div className="flex items-center gap-2 flex-wrap">
                                <SpecialistChip label="Career specialist" color={ACCENT.primary} />
                                {state.reasoning.length === 0 && (
                                    <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-widest text-slate-500">
                                        <Loader2 className="h-3 w-3 animate-spin text-indigo-300" />
                                        Routing
                                    </span>
                                )}
                            </div>
                            {state.reasoning.length > 0 && (
                                <ReasoningBreadcrumbs steps={state.reasoning} />
                            )}
                        </div>
                    ) : (
                        <ReasoningTrailChip steps={state.reasoning} />
                    )}

                    {/* Verdict (C's pattern) */}
                    {state.verdictPartial && (
                        <div className="border-b border-white/5 pb-4">
                            <div className="text-[9px] uppercase tracking-[0.3em] text-indigo-300/80 mb-1.5">
                                Verdict
                            </div>
                            <p
                                className="text-xl leading-snug text-slate-100"
                                style={{ fontFamily: FORTUNE_SERIF, fontStyle: 'italic' }}
                            >
                                {state.verdictPartial}
                                {state.phase === 'streaming-verdict' && (
                                    <motion.span
                                        animate={{ opacity: [0.3, 1, 0.3] }}
                                        transition={{ duration: 1, repeat: Infinity }}
                                        className="ml-1 inline-block h-4 w-1.5 bg-indigo-300 align-middle"
                                    />
                                )}
                            </p>
                            {/* Verdict-level source chip — anchors the headline. */}
                            {citeByLabel('Year Pillar 2026') && (
                                <div className="mt-2">
                                    <SourceChip
                                        citation={citeByLabel('Year Pillar 2026')!}
                                        onActivate={setHovered}
                                    />
                                </div>
                            )}
                        </div>
                    )}

                    {/* Detail (C's accordion + B's source chips inside) */}
                    {verdictDone && (
                        <DisclosureAccordion title="Go deeper" defaultExpanded={false}>
                            <div className="space-y-3">
                                {MOCK.sections.slice(0, state.sectionsRevealed).map((section, sIdx) => {
                                    const sectionCite =
                                        sIdx === 0
                                            ? citeByLabel('Day Pillar')
                                            : citeByLabel('Insight #2 (Why tab)');
                                    return (
                                        <div key={section.id} className="space-y-1.5">
                                            <div className="flex items-center justify-between gap-2">
                                                <div className="text-[11px] uppercase tracking-widest text-slate-400 flex items-center gap-2">
                                                    <span>{section.icon}</span>
                                                    <span>{section.heading}</span>
                                                </div>
                                                {sectionCite && (
                                                    <SourceChip
                                                        citation={sectionCite}
                                                        onActivate={setHovered}
                                                    />
                                                )}
                                            </div>
                                            <p className="text-[12px] text-slate-500">
                                                {section.tagline}
                                            </p>
                                            <ul className="space-y-1.5 pl-1">
                                                {section.bullets.map((b, i) => (
                                                    <li
                                                        key={i}
                                                        className="flex items-start gap-2 text-[13px] leading-relaxed text-slate-200"
                                                    >
                                                        <span>{b.icon}</span>
                                                        <span>{b.text}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    );
                                })}
                            </div>

                            {state.citationsRevealed > 0 && (
                                <div className="space-y-2 pt-2">
                                    <div className="text-[10px] uppercase tracking-widest text-slate-500">
                                        Sources
                                    </div>
                                    <div className="flex flex-wrap gap-1.5">
                                        {visibleCites.map((c) => (
                                            <SourceChip
                                                key={c.id}
                                                citation={c}
                                                onActivate={setHovered}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {state.phase === 'complete' && MOCK.yearPredictions.length > 0 && (
                                <div className="space-y-2 pt-2">
                                    <div className="text-[10px] uppercase tracking-widest text-slate-500">
                                        Timeline
                                    </div>
                                    <div className="space-y-1.5">
                                        {MOCK.yearPredictions.map((yp) => (
                                            <div
                                                key={yp.year}
                                                className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-1.5"
                                            >
                                                <span
                                                    className="text-[12px] font-medium tabular-nums"
                                                    style={{ color: oracleAccent }}
                                                >
                                                    {yp.year}
                                                </span>
                                                <span className="text-[12px] text-slate-300 flex-1">
                                                    {yp.prediction}
                                                </span>
                                                <span className="text-[10px] text-slate-500">
                                                    {Math.round(yp.confidence * 100)}%
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </DisclosureAccordion>
                    )}

                    {/* Source preview tooltip card (B's interaction model) */}
                    <AnimatePresence>
                        {hovered && (
                            <motion.div
                                initial={{ opacity: 0, y: 4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="rounded-xl border border-white/10 bg-black/40 p-3 text-[12px] text-slate-300"
                            >
                                <div
                                    className="text-[10px] uppercase tracking-widest mb-1"
                                    style={{
                                        color:
                                            hovered.kind === 'classical'
                                                ? CITATION_GOLD
                                                : hovered.kind === 'pillar'
                                                ? '#5eead4'
                                                : '#a5b4fc',
                                    }}
                                >
                                    {hovered.label}
                                </div>
                                <div>{hovered.detail}</div>
                                <button
                                    type="button"
                                    onClick={() => setHovered(null)}
                                    className="mt-2 text-[10px] uppercase tracking-widest text-slate-500 hover:text-slate-300"
                                >
                                    Dismiss
                                </button>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {state.pillsVisible && <FollowUpRow follow={MOCK.followUp} />}
                </motion.div>
            )}
        </DemoChrome>
    );
};

// ---------------------------------------------------------------------------
// Shared follow-up pill row (used by all 4 variants on `complete`)
// ---------------------------------------------------------------------------

const FollowUpRow: React.FC<{ follow: FollowUpPills }> = ({ follow }) => (
    <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="border-t border-white/5 pt-3 flex flex-wrap gap-1.5"
    >
        {[
            { kind: 'Deepen', text: follow.deepen, icon: <Sparkles className="h-2.5 w-2.5" /> },
            { kind: 'Action', text: follow.action, icon: <Target className="h-2.5 w-2.5" /> },
            { kind: 'Recap', text: follow.recap, icon: <Brain className="h-2.5 w-2.5" /> },
        ].map((p) => (
            <button
                key={p.kind}
                type="button"
                className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/[0.07]"
            >
                <span className="text-slate-500">{p.icon}</span>
                <span className="text-[10px] uppercase tracking-widest text-slate-500">{p.kind}</span>
                <span>{p.text}</span>
            </button>
        ))}
    </motion.div>
);

// ---------------------------------------------------------------------------
// Index — landing page that links to A / B / C with a 1-line summary each
// ---------------------------------------------------------------------------

interface ConceptCardProps {
    slug: 'a' | 'b' | 'c' | 'd';
    title: string;
    subtitle: string;
    blurb: string;
    icon: React.ReactNode;
    accent: string;
    recommended?: boolean;
}
const ConceptCard: React.FC<ConceptCardProps> = ({
    slug,
    title,
    subtitle,
    blurb,
    icon,
    accent,
    recommended,
}) => (
    <Link
        to={`/project/fortune-agent/ask-demo/${slug}`}
        className={`group relative block overflow-hidden rounded-2xl border p-6 transition-colors ${
            recommended
                ? 'border-indigo-400/40 bg-indigo-500/[0.04] hover:bg-indigo-500/[0.08]'
                : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.05]'
        }`}
    >
        <div
            className="absolute inset-x-0 top-0 h-px"
            style={{ background: `linear-gradient(90deg, transparent, ${accent}, transparent)` }}
        />
        {recommended && (
            <div
                className="absolute right-3 top-3 rounded-full border px-2 py-0.5 text-[9px] uppercase tracking-widest"
                style={{
                    borderColor: `${accent}66`,
                    background: `${accent}1A`,
                    color: accent,
                }}
            >
                Build target
            </div>
        )}
        <div className="flex items-center gap-3 mb-3">
            <div
                className="flex h-10 w-10 items-center justify-center rounded-xl"
                style={{ background: `${accent}1A`, color: accent }}
            >
                {icon}
            </div>
            <div>
                <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">
                    Concept {slug.toUpperCase()}
                </div>
                <div
                    className="text-lg text-slate-100"
                    style={{ fontFamily: FORTUNE_SERIF, fontStyle: 'italic' }}
                >
                    {title}
                </div>
            </div>
        </div>
        <p className="text-[11px] uppercase tracking-widest text-slate-500 mb-2">{subtitle}</p>
        <p className="text-sm text-slate-300 leading-relaxed">{blurb}</p>
        <div className="mt-4 inline-flex items-center gap-1 text-[11px] uppercase tracking-widest text-slate-400 group-hover:text-slate-200">
            View live demo →
        </div>
    </Link>
);

const AskDemoIndex: React.FC = () => {
    const navigate = useNavigate();
    return (
        <div className="min-h-screen bg-[#0B1120] text-slate-200">
            <div className="mx-auto max-w-4xl px-5 py-12">
                <button
                    type="button"
                    onClick={() => navigate('/project/fortune-agent/explore')}
                    className="flex items-center gap-1 text-[11px] uppercase tracking-widest text-slate-500 hover:text-slate-300 mb-8"
                >
                    <ChevronLeft className="h-3 w-3" /> Back to fortune-agent
                </button>

                <div className="mb-10">
                    <div className="text-[10px] uppercase tracking-[0.3em] text-slate-500 mb-2">
                        Ask the Oracle — redesign experiments
                    </div>
                    <h1
                        className="text-4xl text-slate-100"
                        style={{ fontFamily: FORTUNE_SERIF, fontStyle: 'italic' }}
                    >
                        Four takes on the same answer.
                    </h1>
                    <p className="mt-3 text-sm text-slate-400 leading-relaxed max-w-2xl">
                        Same mock question, same payload, four different ways of presenting the agent's
                        thinking and the verdict. All four are fully simulated client-side — no backend
                        wiring yet — so you can compare the perceived-latency curve and the information
                        hierarchy of each. Concept D is the build target: it grafts A's pre-verdict
                        breadcrumbs onto C's calm verdict-first layout and pulls B's source chips inside
                        the accordion. Use the speed toggle on each demo to switch between realistic
                        (1×) and fast-review (3×) playback.
                    </p>
                </div>

                <div className="mb-4">
                    <ConceptCard
                        slug="d"
                        title="Hybrid"
                        subtitle="The build target — A pre-verdict + C verdict + B citations"
                        blurb="Reasoning breadcrumbs fill the wait. The verdict lands big in serif italic. Detail collapses into a single 'Go deeper' fold whose claims are anchored to source chips. After verdict, breadcrumbs collapse into a muted trail chip — visible work, calm result."
                        icon={<Sparkles className="h-5 w-5" />}
                        accent="#a5b4fc"
                        recommended
                    />
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                    <ConceptCard
                        slug="a"
                        title="Streaming Oracle"
                        subtitle="Maximum perceived speed"
                        blurb="Reasoning breadcrumbs animate in within 1.5s, the verdict streams token-by-token, and a 3-line skeleton fills the wait while the body finalizes."
                        icon={<Zap className="h-5 w-5" />}
                        accent="#2dd4bf"
                    />
                    <ConceptCard
                        slug="b"
                        title="Context Anchored"
                        subtitle="Trust + chart continuity"
                        blurb="Every claim is tied to a clickable source chip — pillar, prior insight, or classical citation. Hover to preview, click to scroll-cite."
                        icon={<BookOpen className="h-5 w-5" />}
                        accent="#fb7185"
                    />
                    <ConceptCard
                        slug="c"
                        title="Progressive Disclosure"
                        subtitle="Verdict-first oracle"
                        blurb="A serif italic verdict lands first; technical detail (sections, citations, timeline) lives in a single 'Go deeper' fold. Minimum noise, maximum impact."
                        icon={<Wand2 className="h-5 w-5" />}
                        accent="#818cf8"
                    />
                </div>

                <div className="mt-12 grid gap-3 text-[12px] text-slate-400 max-w-2xl">
                    <div className="flex gap-3">
                        <span className="text-slate-500 w-24 uppercase tracking-widest text-[10px] mt-0.5">
                            Question
                        </span>
                        <span>{MOCK.question}</span>
                    </div>
                    <div className="flex gap-3">
                        <span className="text-slate-500 w-24 uppercase tracking-widest text-[10px] mt-0.5">
                            Verdict
                        </span>
                        <span className="italic" style={{ fontFamily: FORTUNE_SERIF }}>
                            {MOCK.verdict}
                        </span>
                    </div>
                    <div className="flex gap-3">
                        <span className="text-slate-500 w-24 uppercase tracking-widest text-[10px] mt-0.5">
                            Reasoning
                        </span>
                        <span>{MOCK.reasoning.map((s) => s.label).join(' · ')}</span>
                    </div>
                    <div className="flex gap-3">
                        <span className="text-slate-500 w-24 uppercase tracking-widest text-[10px] mt-0.5">
                            Citations
                        </span>
                        <span>{MOCK.citations.map((c) => c.label).join(' · ')}</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

// ---------------------------------------------------------------------------
// Router shim — picks the variant from the URL param
// ---------------------------------------------------------------------------

export const AskDemoPage: React.FC = () => {
    const { variant } = useParams<{ variant?: string }>();
    if (variant === 'a') return <ConceptA />;
    if (variant === 'b') return <ConceptB />;
    if (variant === 'c') return <ConceptC />;
    if (variant === 'd') return <ConceptD />;
    return <AskDemoIndex />;
};

export default AskDemoPage;
