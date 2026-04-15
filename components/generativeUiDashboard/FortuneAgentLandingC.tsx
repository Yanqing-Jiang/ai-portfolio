/**
 * FortuneAgentLandingC — "Conversational Oracle"
 *
 * A mobile-first, chat-led landing for fortune-agent (formerly ming-engine).
 * The page IS the conversation: agent greets, user taps quick-reply chips
 * or types free-text. Every use case is a natural-language turn, reinforcing
 * the "agent harness" positioning — the UI is a tiny stage for the agent.
 *
 * Drop-in presentational mockup. No backend. Picking a chip or sending text
 * calls the `onSelect(id, payload?)` prop (or console.log by default).
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type FortuneIntentId =
    | 'compatibility'
    | 'lucky_day'
    | 'period_luck'
    | 'custom'
    | 'baby_naming'
    | 'career_pivot'
    | 'home_date';

type OccasionId =
    | 'business_opening'
    | 'wedding'
    | 'engagement'
    | 'moving'
    | 'contract'
    | 'travel';

interface FortuneAgentLandingCProps {
    onSelect?: (id: FortuneIntentId, payload?: Record<string, unknown>) => void;
}

type TurnRole = 'agent' | 'user';

interface BaseTurn {
    id: string;
    role: TurnRole;
}

interface TextTurn extends BaseTurn {
    kind: 'text';
    text: string;
}

interface PreviewTurn extends BaseTurn {
    kind: 'preview';
    title: string;
    body: string;
    intentId: FortuneIntentId;
    cta: string;
    inline?: 'occasion' | 'period';
}

type Turn = TextTurn | PreviewTurn;

// ---------------------------------------------------------------------------
// Chip catalog
// ---------------------------------------------------------------------------

interface Chip {
    id: FortuneIntentId;
    label: string;
    glyph: string;
    userEcho: string;
    preview: { title: string; body: string; cta: string };
    inline?: 'occasion' | 'period';
}

const CHIPS: Chip[] = [
    {
        id: 'compatibility',
        label: 'Compatibility Check',
        glyph: '合',
        userEcho: 'Check compatibility between two people.',
        preview: {
            title: 'Two charts, one reading',
            body: 'Share both birth moments — I will compare Four Pillars and read the resonance.',
            cta: 'Begin compatibility',
        },
    },
    {
        id: 'lucky_day',
        label: 'Lucky Day',
        glyph: '吉',
        userEcho: 'Find a lucky day for me.',
        preview: {
            title: 'Pick the occasion',
            body: 'The right date depends on the event. Choose one and I will scan the calendar.',
            cta: 'Pick a date window',
        },
        inline: 'occasion',
    },
    {
        id: 'period_luck',
        label: "This Year / Month's Luck",
        glyph: '運',
        userEcho: "Read this period's luck for me.",
        preview: {
            title: 'Year or month view?',
            body: 'I can read the full year arc or zoom into a single month. Toggle below.',
            cta: 'Read my period',
        },
        inline: 'period',
    },
    {
        id: 'baby_naming',
        label: 'Baby Naming',
        glyph: '名',
        userEcho: 'Help me choose a name for a new baby.',
        preview: {
            title: 'Name the Five Elements',
            body: 'I will weigh the chart and suggest names that balance what is missing.',
            cta: 'Start naming',
        },
    },
    {
        id: 'career_pivot',
        label: 'Career Pivot Window',
        glyph: '業',
        userEcho: 'When should I make my career move?',
        preview: {
            title: 'Timing the pivot',
            body: 'I will map favorable windows in the next 12 months against your pillars.',
            cta: 'Scan windows',
        },
    },
    {
        id: 'home_date',
        label: 'Home / Feng Shui Date',
        glyph: '宅',
        userEcho: 'Find an auspicious date to move or renovate.',
        preview: {
            title: 'Home direction & date',
            body: 'Tell me the address; I will read direction, element and date alignment.',
            cta: 'Choose a date',
        },
    },
];

const OCCASIONS: { id: OccasionId; label: string; glyph: string }[] = [
    { id: 'business_opening', label: 'Business Opening', glyph: '開' },
    { id: 'wedding', label: 'Wedding', glyph: '婚' },
    { id: 'engagement', label: 'Engagement', glyph: '訂' },
    { id: 'moving', label: 'Moving', glyph: '遷' },
    { id: 'contract', label: 'Contract Signing', glyph: '約' },
    { id: 'travel', label: 'Travel', glyph: '行' },
];

// ---------------------------------------------------------------------------
// Default handler (if prop not provided)
// ---------------------------------------------------------------------------

const defaultOnSelect: NonNullable<FortuneAgentLandingCProps['onSelect']> = (id, payload) => {
    // eslint-disable-next-line no-console
    console.log('[fortune-agent] onSelect', id, payload ?? {});
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TypingDots() {
    return (
        <div className="flex items-center gap-1 px-4 py-3">
            {[0, 1, 2].map((i) => (
                <motion.span
                    key={i}
                    className="inline-block w-1.5 h-1.5 rounded-full"
                    style={{ background: 'var(--ming-gold, #eab308)' }}
                    animate={{ opacity: [0.3, 1, 0.3], y: [0, -2, 0] }}
                    transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.15 }}
                />
            ))}
        </div>
    );
}

function AgentAvatar() {
    return (
        <div
            className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm"
            style={{
                background:
                    'radial-gradient(circle at 30% 30%, rgba(234,179,8,0.35), rgba(220,38,38,0.25) 60%, rgba(12,10,20,0.9))',
                border: '1px solid rgba(234,179,8,0.35)',
                color: 'var(--ming-gold, #eab308)',
                fontFamily: 'var(--ming-font-chinese, "Noto Serif SC", serif)',
            }}
            aria-hidden
        >
            命
        </div>
    );
}

function AgentBubble({ children }: { children: React.ReactNode }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            className="flex items-end gap-2 pr-10"
        >
            <AgentAvatar />
            <div
                className="rounded-2xl rounded-bl-sm px-4 py-3 text-[15px] leading-relaxed"
                style={{
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(234,179,8,0.18)',
                    color: 'rgba(245,240,225,0.95)',
                    maxWidth: '86%',
                }}
            >
                {children}
            </div>
        </motion.div>
    );
}

function UserBubble({ children }: { children: React.ReactNode }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="flex justify-end pl-10"
        >
            <div
                className="rounded-2xl rounded-br-sm px-4 py-2.5 text-[15px] leading-relaxed"
                style={{
                    background:
                        'linear-gradient(135deg, rgba(220,38,38,0.92), rgba(153,27,27,0.92))',
                    color: '#fff7ed',
                    maxWidth: '84%',
                    boxShadow: '0 4px 18px -6px rgba(220,38,38,0.55)',
                }}
            >
                {children}
            </div>
        </motion.div>
    );
}

function PreviewCard({
    turn,
    onContinue,
    onInlinePick,
}: {
    turn: PreviewTurn;
    onContinue: () => void;
    onInlinePick: (payload: Record<string, unknown>) => void;
}) {
    const [periodMode, setPeriodMode] = useState<'year' | 'month'>('year');

    return (
        <AgentBubble>
            <div className="flex flex-col gap-3 min-w-[220px]">
                <div>
                    <div
                        className="text-xs uppercase tracking-[0.18em] mb-1"
                        style={{ color: 'var(--ming-gold, #eab308)', opacity: 0.85 }}
                    >
                        Preview
                    </div>
                    <div className="font-medium text-[15px]" style={{ color: '#fef3c7' }}>
                        {turn.title}
                    </div>
                    <div className="text-[13.5px] mt-1" style={{ color: 'rgba(245,240,225,0.75)' }}>
                        {turn.body}
                    </div>
                </div>

                {turn.inline === 'occasion' && (
                    <div className="grid grid-cols-2 gap-1.5">
                        {OCCASIONS.map((o) => (
                            <button
                                key={o.id}
                                type="button"
                                onClick={() =>
                                    onInlinePick({ occasion: o.id, occasion_label: o.label })
                                }
                                className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-[12.5px] text-left active:scale-[0.97] transition"
                                style={{
                                    background: 'rgba(234,179,8,0.06)',
                                    border: '1px solid rgba(234,179,8,0.2)',
                                    color: 'rgba(245,240,225,0.88)',
                                    minHeight: '44px',
                                }}
                            >
                                <span
                                    style={{
                                        fontFamily:
                                            'var(--ming-font-chinese, "Noto Serif SC", serif)',
                                        color: 'var(--ming-gold, #eab308)',
                                    }}
                                >
                                    {o.glyph}
                                </span>
                                <span>{o.label}</span>
                            </button>
                        ))}
                    </div>
                )}

                {turn.inline === 'period' && (
                    <div
                        className="flex rounded-lg p-1 gap-1"
                        style={{
                            background: 'rgba(0,0,0,0.35)',
                            border: '1px solid rgba(234,179,8,0.18)',
                        }}
                    >
                        {(['year', 'month'] as const).map((m) => {
                            const active = periodMode === m;
                            return (
                                <button
                                    key={m}
                                    type="button"
                                    onClick={() => setPeriodMode(m)}
                                    className="flex-1 text-[13px] py-2 rounded-md transition active:scale-[0.98]"
                                    style={{
                                        background: active
                                            ? 'linear-gradient(135deg, rgba(220,38,38,0.85), rgba(153,27,27,0.85))'
                                            : 'transparent',
                                        color: active ? '#fff7ed' : 'rgba(245,240,225,0.7)',
                                        fontWeight: active ? 600 : 400,
                                        minHeight: '40px',
                                    }}
                                >
                                    {m === 'year' ? 'This Year' : 'This Month'}
                                </button>
                            );
                        })}
                    </div>
                )}

                <button
                    type="button"
                    onClick={() => {
                        if (turn.inline === 'period') {
                            onInlinePick({ period: periodMode });
                        }
                        onContinue();
                    }}
                    className="w-full flex items-center justify-center gap-2 rounded-lg py-2.5 text-[14px] font-medium active:scale-[0.98] transition"
                    style={{
                        background:
                            'linear-gradient(135deg, var(--ming-gold, #eab308), #b8860b)',
                        color: '#1a1405',
                        minHeight: '44px',
                        boxShadow: '0 4px 14px -4px rgba(234,179,8,0.5)',
                    }}
                >
                    <span>{turn.cta}</span>
                    <span aria-hidden>→</span>
                </button>
            </div>
        </AgentBubble>
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function FortuneAgentLandingC({ onSelect }: FortuneAgentLandingCProps = {}) {
    const handler = onSelect ?? defaultOnSelect;

    const [greetingReady, setGreetingReady] = useState(false);
    const [chipsReady, setChipsReady] = useState(false);
    const [turns, setTurns] = useState<Turn[]>([]);
    const [selectedIntent, setSelectedIntent] = useState<FortuneIntentId | null>(null);
    const [composerText, setComposerText] = useState('');
    const [composerFocused, setComposerFocused] = useState(false);

    const scrollRef = useRef<HTMLDivElement>(null);

    // Greeting typing tease
    useEffect(() => {
        const t1 = setTimeout(() => setGreetingReady(true), 900);
        const t2 = setTimeout(() => setChipsReady(true), 1500);
        return () => {
            clearTimeout(t1);
            clearTimeout(t2);
        };
    }, []);

    // Auto-scroll on new turns
    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return;
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }, [turns.length, greetingReady]);

    const handleChip = useCallback(
        (chip: Chip) => {
            setSelectedIntent(chip.id);
            const stamp = Date.now();
            setTurns((prev) => [
                ...prev,
                { id: `u-${stamp}`, role: 'user', kind: 'text', text: chip.userEcho },
            ]);
            // Agent reply after a brief beat
            setTimeout(() => {
                setTurns((prev) => [
                    ...prev,
                    {
                        id: `a-${stamp}`,
                        role: 'agent',
                        kind: 'preview',
                        title: chip.preview.title,
                        body: chip.preview.body,
                        cta: chip.preview.cta,
                        intentId: chip.id,
                        inline: chip.inline,
                    },
                ]);
            }, 420);
        },
        [],
    );

    const handleSend = useCallback(() => {
        const text = composerText.trim();
        if (!text) return;
        const stamp = Date.now();
        setTurns((prev) => [
            ...prev,
            { id: `u-${stamp}`, role: 'user', kind: 'text', text },
        ]);
        setComposerText('');
        setTimeout(() => {
            setTurns((prev) => [
                ...prev,
                {
                    id: `a-${stamp}`,
                    role: 'agent',
                    kind: 'text',
                    text: 'Received. I will thread this through the Four Pillars and return a reading.',
                },
            ]);
        }, 350);
        handler('custom', { text });
    }, [composerText, handler]);

    const handleComposerKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div
            className="relative min-h-screen w-full flex flex-col"
            style={{
                background:
                    'radial-gradient(1200px 600px at 50% -10%, rgba(234,179,8,0.08), transparent 60%), radial-gradient(900px 500px at 50% 110%, rgba(220,38,38,0.08), transparent 60%), var(--ming-bg, #0c0a14)',
                color: 'rgba(245,240,225,0.92)',
                fontFamily:
                    '"Inter", ui-sans-serif, system-ui, -apple-system, "Helvetica Neue", sans-serif',
            }}
        >
            {/* Top bar */}
            <header
                className="sticky top-0 z-20 flex items-center justify-between px-4 py-3"
                style={{
                    backdropFilter: 'blur(14px)',
                    background: 'rgba(12,10,20,0.7)',
                    borderBottom: '1px solid rgba(234,179,8,0.12)',
                }}
            >
                <div className="flex items-center gap-2">
                    <span
                        aria-hidden
                        className="w-7 h-7 rounded-full flex items-center justify-center text-[13px]"
                        style={{
                            background:
                                'conic-gradient(from 200deg, rgba(234,179,8,0.9), rgba(220,38,38,0.9), rgba(234,179,8,0.9))',
                            color: '#1a1405',
                            fontFamily:
                                'var(--ming-font-chinese, "Noto Serif SC", serif)',
                            fontWeight: 600,
                        }}
                    >
                        命
                    </span>
                    <div className="flex flex-col leading-tight">
                        <span className="text-[15px] font-medium tracking-tight">
                            fortune-agent
                        </span>
                        <span
                            className="text-[10.5px] uppercase tracking-[0.18em]"
                            style={{ color: 'var(--ming-gold, #eab308)', opacity: 0.8 }}
                        >
                            Four Pillars · Agentic
                        </span>
                    </div>
                </div>

                <div
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10.5px] uppercase tracking-[0.14em]"
                    style={{
                        background: 'rgba(234,179,8,0.08)',
                        border: '1px solid rgba(234,179,8,0.3)',
                        color: 'var(--ming-gold, #eab308)',
                    }}
                    title="I'm learning about agent harness"
                >
                    <motion.span
                        className="inline-block w-1.5 h-1.5 rounded-full"
                        style={{ background: 'var(--ming-gold, #eab308)' }}
                        animate={{ opacity: [0.4, 1, 0.4] }}
                        transition={{ duration: 2, repeat: Infinity }}
                    />
                    Agent Harness
                </div>
            </header>

            {/* Chat transcript */}
            <main
                ref={scrollRef}
                className="flex-1 overflow-y-auto px-4 pt-5 pb-4"
                style={{ scrollBehavior: 'smooth' }}
            >
                <div className="max-w-md mx-auto flex flex-col gap-4">
                    {/* Greeting */}
                    {!greetingReady ? (
                        <div className="flex items-end gap-2">
                            <AgentAvatar />
                            <div
                                className="rounded-2xl rounded-bl-sm"
                                style={{
                                    background: 'rgba(255,255,255,0.04)',
                                    border: '1px solid rgba(234,179,8,0.18)',
                                }}
                            >
                                <TypingDots />
                            </div>
                        </div>
                    ) : (
                        <AgentBubble>
                            <div>
                                <div
                                    className="mb-1 text-[13px]"
                                    style={{
                                        fontFamily:
                                            'var(--ming-font-chinese, "Noto Serif SC", serif)',
                                        color: 'var(--ming-gold, #eab308)',
                                        letterSpacing: '0.08em',
                                    }}
                                >
                                    天機在此
                                </div>
                                <div>
                                    What would you like to ask the heavens?
                                </div>
                                <div
                                    className="mt-1.5 text-[12.5px]"
                                    style={{ color: 'rgba(245,240,225,0.62)' }}
                                >
                                    Tap a thread below, or type anything in your own words.
                                </div>
                            </div>
                        </AgentBubble>
                    )}

                    {/* Quick-reply chips — pulse in on mount */}
                    <AnimatePresence>
                        {chipsReady && (
                            <motion.div
                                key="chips"
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.3 }}
                                className="pl-10 flex flex-wrap gap-2"
                                role="group"
                                aria-label="Quick replies"
                            >
                                {CHIPS.map((chip, i) => {
                                    const dim = selectedIntent && selectedIntent !== chip.id;
                                    return (
                                        <motion.button
                                            key={chip.id}
                                            type="button"
                                            onClick={() => handleChip(chip)}
                                            initial={{ opacity: 0, y: 6, scale: 0.96 }}
                                            animate={{
                                                opacity: dim ? 0.45 : 1,
                                                y: 0,
                                                scale: 1,
                                            }}
                                            transition={{
                                                delay: 0.05 * i,
                                                type: 'spring',
                                                stiffness: 320,
                                                damping: 22,
                                            }}
                                            whileTap={{ scale: 0.96 }}
                                            className="group flex items-center gap-2 px-3.5 py-2.5 rounded-full text-[13.5px] transition"
                                            style={{
                                                background:
                                                    'linear-gradient(180deg, rgba(234,179,8,0.10), rgba(234,179,8,0.04))',
                                                border: '1px solid rgba(234,179,8,0.35)',
                                                color: 'rgba(250,245,230,0.94)',
                                                minHeight: '44px',
                                                boxShadow:
                                                    '0 1px 0 rgba(255,255,255,0.04) inset',
                                            }}
                                        >
                                            <span
                                                aria-hidden
                                                style={{
                                                    fontFamily:
                                                        'var(--ming-font-chinese, "Noto Serif SC", serif)',
                                                    color: 'var(--ming-gold, #eab308)',
                                                    fontSize: '15px',
                                                    lineHeight: 1,
                                                }}
                                            >
                                                {chip.glyph}
                                            </span>
                                            <span>{chip.label}</span>
                                        </motion.button>
                                    );
                                })}
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Conversation turns */}
                    <AnimatePresence initial={false}>
                        {turns.map((t) => {
                            if (t.role === 'user' && t.kind === 'text') {
                                return (
                                    <UserBubble key={t.id}>
                                        <span>{t.text}</span>
                                    </UserBubble>
                                );
                            }
                            if (t.role === 'agent' && t.kind === 'text') {
                                return (
                                    <AgentBubble key={t.id}>
                                        <span>{t.text}</span>
                                    </AgentBubble>
                                );
                            }
                            if (t.role === 'agent' && t.kind === 'preview') {
                                return (
                                    <PreviewCard
                                        key={t.id}
                                        turn={t}
                                        onContinue={() => handler(t.intentId)}
                                        onInlinePick={(payload) =>
                                            handler(t.intentId, payload)
                                        }
                                    />
                                );
                            }
                            return null;
                        })}
                    </AnimatePresence>

                    {/* Trust cue / how it works — subtle */}
                    <div
                        className="mt-2 pl-10 flex items-center gap-2 text-[11.5px]"
                        style={{ color: 'rgba(245,240,225,0.45)' }}
                        aria-label="How this works"
                    >
                        <span
                            aria-hidden
                            className="inline-flex items-center gap-1"
                            style={{ color: 'var(--ming-gold, #eab308)', opacity: 0.75 }}
                        >
                            <span
                                className="inline-block w-1 h-1 rounded-full"
                                style={{ background: 'currentColor' }}
                            />
                        </span>
                        <span>Four Pillars</span>
                        <span style={{ opacity: 0.4 }}>→</span>
                        <span>agent reasoning</span>
                        <span style={{ opacity: 0.4 }}>→</span>
                        <span>your reading</span>
                    </div>

                    {/* bottom spacer so composer never covers last turn */}
                    <div className="h-24" aria-hidden />
                </div>
            </main>

            {/* Sticky composer */}
            <div
                className="sticky bottom-0 z-20"
                style={{
                    paddingBottom: 'env(safe-area-inset-bottom, 0px)',
                    background:
                        'linear-gradient(180deg, rgba(12,10,20,0) 0%, rgba(12,10,20,0.85) 30%, rgba(12,10,20,0.95) 100%)',
                }}
            >
                <div className="max-w-md mx-auto px-4 pt-3 pb-3">
                    <div
                        className="flex items-center gap-2 rounded-2xl pl-4 pr-2 py-1.5 transition"
                        style={{
                            background: 'rgba(255,255,255,0.04)',
                            border: `1px solid ${
                                composerFocused
                                    ? 'rgba(234,179,8,0.55)'
                                    : 'rgba(234,179,8,0.22)'
                            }`,
                            boxShadow: composerFocused
                                ? '0 0 0 4px rgba(234,179,8,0.10), 0 10px 30px -12px rgba(220,38,38,0.25)'
                                : '0 6px 20px -10px rgba(0,0,0,0.5)',
                        }}
                    >
                        <input
                            value={composerText}
                            onChange={(e) => setComposerText(e.target.value)}
                            onFocus={() => setComposerFocused(true)}
                            onBlur={() => setComposerFocused(false)}
                            onKeyDown={handleComposerKey}
                            placeholder="Ask in your own words…"
                            className="flex-1 bg-transparent outline-none text-[15px] py-2.5"
                            style={{
                                color: 'rgba(250,245,230,0.95)',
                                minHeight: '44px',
                            }}
                            aria-label="Ask the fortune agent"
                        />
                        <button
                            type="button"
                            onClick={handleSend}
                            disabled={!composerText.trim()}
                            className="flex items-center justify-center rounded-xl transition active:scale-[0.94] disabled:opacity-40"
                            style={{
                                width: '44px',
                                height: '44px',
                                background: composerText.trim()
                                    ? 'linear-gradient(135deg, var(--ming-accent, #dc2626), #7f1d1d)'
                                    : 'rgba(255,255,255,0.05)',
                                border: '1px solid rgba(234,179,8,0.35)',
                                color: composerText.trim()
                                    ? '#fff7ed'
                                    : 'rgba(245,240,225,0.55)',
                                fontFamily:
                                    'var(--ming-font-chinese, "Noto Serif SC", serif)',
                                fontSize: '17px',
                                boxShadow: composerText.trim()
                                    ? '0 6px 18px -6px rgba(220,38,38,0.6)'
                                    : 'none',
                            }}
                            aria-label="Send message"
                        >
                            送
                        </button>
                    </div>

                    {/* Handcrafted cue */}
                    <div
                        className="mt-2 text-center text-[10.5px] tracking-[0.12em] uppercase"
                        style={{ color: 'rgba(245,240,225,0.35)' }}
                    >
                        Running on a handcrafted agent harness
                    </div>
                </div>
            </div>
        </div>
    );
}

export default FortuneAgentLandingC;
