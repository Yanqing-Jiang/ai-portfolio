/**
 * OracleChat — mobile-first Ask-the-Oracle conversation.
 *
 * Messages flow with the page while the safe-area-aware sticky composer stays
 * visible at the viewport edge. A bottom sentinel keeps new turns in view.
 * Each agent turn renders as:
 *   1. Pre-verdict: an honest pending state while Execution Trace surfaces
 *      server-backed reasoning separately.
 *   2. Verdict: italic serif headline (= narrative.tldr).
 *   3. Go-deeper accordion: holds insights → bullets, classical citations,
 *      and year predictions when present. Source chips on each section
 *      header anchor the claim back to a chart pillar / Why-tab insight.
 *   4. Follow-up pills: pulled from the per-tab `suggestions` array.
 *
 * Backward compat: a turn without `narrative` (legacy or error) falls back
 * to the plain-text bubble. The unified fortune/shared/AskTab.tsx stores
 * `narrative` on each turn via `useFortuneAsk`.
 *
 * Called from: fortune/shared/AskTab.tsx.
 * Forwards to: only renders — no fetching. Submit handled by parent.
 *
 * AskDemoPage is an independent visual prototype, not a caller of this layout.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, MotionConfig, useReducedMotion } from 'framer-motion';
import {
    AlertCircle,
    BookOpen,
    Brain,
    ChevronDown,
    Loader2,
    Send,
    Sparkles,
    Target,
} from 'lucide-react';
import { CITATION_GOLD, GLASS } from '../designTokens';
import type { AskContext } from '../../lib/fortuneTypes';

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
    error?: boolean;
    retryable?: boolean;
    retryQuestion?: string;
    clientRequestId?: string;
    askContext?: AskContext;
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
    /** Submit the current composer value, or a predefined question directly. */
    onSend: (question?: string) => void;
    onRetry?: (message: OracleChatMessage) => void;
    suggestions?: string[];
    accentColor?: string;
    isLoading?: boolean;
    memoryDegraded?: boolean;
    disabled?: boolean;
    contextLabel?: string;
    disabledReason?: string;
}

const SERIF = "'Cormorant Garamond', 'Playfair Display', Georgia, serif";

// ---------------------------------------------------------------------------
// Atoms
// ---------------------------------------------------------------------------

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
    isPending?: boolean;
    onRetry?: (message: OracleChatMessage) => void;
}

const AgentBubble: React.FC<AgentBubbleProps> = ({
    msg,
    accentColor,
    isPending,
    onRetry,
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
                    <div role={msg.error ? 'alert' : undefined}>{msg.content}</div>
                    {msg.error && msg.retryable && msg.retryQuestion && onRetry && (
                        <button
                            type="button"
                            onClick={() => onRetry(msg)}
                            className="mt-2 rounded-full border border-white/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-slate-300 hover:bg-white/[0.06]"
                        >
                            Retry
                        </button>
                    )}
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
            {/* Honest pre-verdict state: no simulated backend progress. */}
            {isPending && (
                <div className="flex flex-col gap-2">
                    <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-slate-500">
                        <Loader2 className="h-3 w-3 animate-spin" style={{ color: accentColor }} />
                        Consulting the oracle…
                    </span>
                </div>
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
    onRetry,
    suggestions = [],
    accentColor = '#14b8a6',
    isLoading = false,
    memoryDegraded = false,
    disabled = false,
    contextLabel,
    disabledReason,
}) => {
    const bottomRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const reduceMotion = useReducedMotion();

    useEffect(() => {
        const bottom = bottomRef.current;
        if (!bottom) return;
        const latestIsUser = messages.at(-1)?.role === 'user';
        const nearViewportBottom = typeof window !== 'undefined'
            && bottom.getBoundingClientRect().top <= window.innerHeight + 120;
        if (!latestIsUser && !nearViewportBottom) return;
        bottom.scrollIntoView?.({
            block: 'end',
            behavior: reduceMotion ? 'auto' : 'smooth',
        });
    }, [messages.length, isLoading, reduceMotion]);

    useEffect(() => {
        const textarea = textareaRef.current;
        if (!textarea) return;
        textarea.style.height = 'auto';
        textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }, [input]);

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
        <MotionConfig reducedMotion="user">
        <div>
            {contextLabel && (
                <div className="mb-3 flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-500">
                    <span>Answering about</span>
                    <span
                        className="rounded-full border px-2 py-1 text-slate-300"
                        style={{ borderColor: `${accentColor}44`, background: `${accentColor}12` }}
                    >
                        {contextLabel}
                    </span>
                </div>
            )}
            {memoryDegraded && (
                <div className="flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 p-2 mb-3 text-[11px] text-amber-400">
                    <AlertCircle className="w-3.5 h-3.5 flex-none" />
                    Memory is limited — the oracle may not recall earlier context.
                </div>
            )}

            <div
                role="log"
                aria-live="polite"
                aria-busy={isLoading}
                aria-label="Ask conversation"
                className="mb-3 space-y-4 pr-1"
            >
                <AnimatePresence initial={false}>
                    {messages.map((msg) =>
                        msg.role === 'user' ? (
                            <UserBubble key={msg.id} text={msg.content} />
                        ) : (
                            <AgentBubble
                                key={msg.id}
                                msg={msg}
                                accentColor={accentColor}
                                onRetry={onRetry}
                            />
                        ),
                    )}
                </AnimatePresence>

                {/* In-flight pending bubble — only shown while loading */}
                {isLoading && (
                    <AgentBubble
                        msg={{ id: '__pending', role: 'agent', content: '' }}
                        accentColor={accentColor}
                        isPending
                    />
                )}

                {/* Cold-start quick replies live inside the conversation so
                    the first interaction already feels like a chatbot. */}
                {!isLoading && messages.length === 0 && suggestions.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="max-w-[92%] space-y-3 rounded-2xl border border-white/[0.07] bg-white/[0.03] p-4"
                    >
                        <p className="text-[13px] text-slate-300">
                            Choose a question to start the conversation.
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                            {suggestions.map((s) => (
                                <button
                                    key={s}
                                    type="button"
                                    onClick={() => onSend(s)}
                                    disabled={disabled}
                                    className="min-h-10 rounded-full border border-white/10 bg-white/[0.03] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.12em] text-slate-400 transition-colors hover:bg-white/[0.06] hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    </motion.div>
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
                                    onClick={() => onSend(s)}
                                    className="inline-flex min-h-10 items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.12em] text-slate-300 hover:bg-white/[0.07]"
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
                <div ref={bottomRef} aria-hidden />
            </div>

            <div
                className="sticky bottom-0 z-10 -mx-1 border-t border-white/[0.06] px-1 pt-3 backdrop-blur-md"
                style={{
                    background: 'rgba(10,12,16,0.88)',
                    paddingBottom: 'max(env(safe-area-inset-bottom), 8px)',
                }}
            >
                {disabledReason && disabled && (
                    <p id="fortune-ask-disabled" className="mb-2 text-[11px] text-slate-500">
                        {disabledReason}
                    </p>
                )}
                <div className="flex items-end gap-2">
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => onInputChange(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask the oracle..."
                        disabled={disabled}
                        maxLength={500}
                        aria-label="Ask a question about this reading"
                        aria-describedby={disabledReason && disabled ? 'fortune-ask-disabled fortune-ask-count' : 'fortune-ask-count'}
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
                        onClick={() => onSend()}
                        disabled={disabled || isLoading || !input.trim()}
                        aria-label={isLoading ? 'Waiting for answer' : 'Send question'}
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
                <div id="fortune-ask-count" className="mt-1 text-right font-mono text-[10px] text-slate-600">
                    {input.length}/500
                </div>
            </div>
        </div>
        </MotionConfig>
    );
};
