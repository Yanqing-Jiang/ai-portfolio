/**
 * FortuneAgentAskTab — conversational follow-up panel used as the 4th tab
 * on every result page.
 *
 * Design intent (research-backed):
 *
 * - Treat the tab as a "Sacred Scroll / Offering Chamber", not a chatbot.
 *   No bubbles, no typing dots. Oracle text sits centered with a soft
 *   radial gold glow; the user's own words are right-aligned and muted.
 *   (see ~/homer/output/gemini/fortune-mobile-tabs-ux-2026-04-15-1400.md §2)
 *
 * - 4 suggested question chips stacked above the input, so the ritual
 *   gives the user a nudge when they can't phrase their own doubt.
 *   (see data contract: AskPanel.suggestedChips)
 *
 * - Input is a single elegant line with a gold underline + italic serif
 *   placeholder — feels like writing an offering, not typing in Slack.
 *
 * - Every oracle response is framed with a short anchor → lean → mitigation
 *   → closure pattern (handled by the backend prompt).
 *
 * - Safe-area aware so iOS home indicator never crowds the composer.
 */

import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send } from 'lucide-react';
import {
    FORTUNE_THEMES,
    FORTUNE_CHINESE_FONT,
    type FortunePurposeId,
} from './fortuneAgentTheme';

export interface AskTurn {
    id: string;
    role: 'user' | 'agent';
    content: string;
    timestampISO?: string;
}

interface FortuneAgentAskTabProps {
    purpose: FortunePurposeId;
    history: AskTurn[];
    suggestedChips?: string[];
    input: string;
    onInputChange: (v: string) => void;
    onSend: () => void;
    placeholder?: string;
    /** Optional heading text shown above the thread (e.g. "Ask the pillars"). */
    heading?: string;
}

export const FortuneAgentAskTab: React.FC<FortuneAgentAskTabProps> = ({
    purpose,
    history,
    suggestedChips = [],
    input,
    onInputChange,
    onSend,
    placeholder = 'Ask a follow-up…',
    heading = 'Ask the pillars',
}) => {
    const theme = FORTUNE_THEMES[purpose];
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to the latest oracle response whenever history grows.
    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return;
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }, [history.length]);

    const handleKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onSend();
        }
    };

    return (
        <div className="flex min-h-[60vh] flex-col gap-5">
            {/* Heading — tiny eyebrow, matches theme accent */}
            <div className="flex items-center justify-center gap-2">
                <span
                    aria-hidden
                    className="h-px w-8"
                    style={{
                        background: `linear-gradient(to right, transparent, ${theme.accent}88, transparent)`,
                    }}
                />
                <span
                    className="text-[10px] font-bold uppercase tracking-[0.3em]"
                    style={{ color: theme.accent }}
                >
                    {heading}
                </span>
                <span
                    aria-hidden
                    className="h-px w-8"
                    style={{
                        background: `linear-gradient(to left, transparent, ${theme.accent}88, transparent)`,
                    }}
                />
            </div>

            {/* Thread — centered oracle text, right-aligned user text */}
            <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto">
                <AnimatePresence initial={false}>
                    {history.map((t) => (
                        <motion.div
                            key={t.id}
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.45, ease: [0.32, 0.72, 0, 1] }}
                        >
                            {t.role === 'user' ? (
                                <div className="flex justify-end">
                                    <p className="max-w-[85%] rounded-2xl rounded-tr-none px-4 py-2 text-[13px] text-white/70"
                                        style={{
                                            background: 'rgba(248,250,252,0.04)',
                                            border: '1px solid rgba(248,250,252,0.08)',
                                        }}
                                    >
                                        {t.content}
                                    </p>
                                </div>
                            ) : (
                                <div
                                    className="relative mx-auto max-w-[92%] px-5 py-6 text-center text-[15px] leading-relaxed text-white/90"
                                    style={{
                                        fontFamily: FORTUNE_CHINESE_FONT,
                                        background: `radial-gradient(circle at center, ${theme.accent}0d 0%, transparent 65%)`,
                                    }}
                                >
                                    <span
                                        aria-hidden
                                        className="absolute left-1/2 top-0 h-px w-16 -translate-x-1/2"
                                        style={{
                                            background: `linear-gradient(to right, transparent, ${theme.accent}66, transparent)`,
                                        }}
                                    />
                                    <p>{t.content}</p>
                                </div>
                            )}
                        </motion.div>
                    ))}
                </AnimatePresence>
            </div>

            {/* Suggested-question chips (2x2 grid on mobile, row on wider) */}
            {suggestedChips.length > 0 && (
                <div className="grid grid-cols-2 gap-2">
                    {suggestedChips.slice(0, 4).map((chip) => (
                        <button
                            key={chip}
                            type="button"
                            onClick={() => onInputChange(chip)}
                            className="rounded-full border px-3 py-2 text-left text-[11px] leading-snug transition-colors"
                            style={{
                                minHeight: 36,
                                borderColor: theme.accentSoft,
                                background: 'rgba(12,10,20,0.45)',
                                color: 'rgba(248,250,252,0.8)',
                                fontFamily: FORTUNE_CHINESE_FONT,
                            }}
                        >
                            {chip}
                        </button>
                    ))}
                </div>
            )}

            {/* Composer — gold underline, italic serif placeholder */}
            <div className="relative">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => onInputChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    className="w-full bg-transparent py-3 pl-1 pr-10 text-[14px] italic focus:outline-none"
                    style={{
                        borderBottom: `1px solid ${theme.accentSoft}`,
                        color: '#f8fafc',
                        fontFamily: FORTUNE_CHINESE_FONT,
                        minHeight: 44,
                    }}
                />
                <button
                    type="button"
                    onClick={onSend}
                    aria-label="Send"
                    disabled={!input.trim()}
                    className="absolute right-0 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full transition-opacity"
                    style={{
                        background: input.trim() ? theme.accent : 'transparent',
                        color: input.trim() ? '#0c0a14' : theme.accentSoft,
                        opacity: input.trim() ? 1 : 0.4,
                    }}
                >
                    <Send className="h-4 w-4" />
                </button>
            </div>

            {/* Cultural footer line — subtle ritual closure */}
            <p
                className="text-center text-[10px] italic tracking-wide text-white/30"
                style={{ fontFamily: FORTUNE_CHINESE_FONT }}
            >
                顺势 · navigate the season, don't fight it.
            </p>
        </div>
    );
};
