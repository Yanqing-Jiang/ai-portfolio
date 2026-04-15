/**
 * FortuneAgentLandingA — "Celestial Scroll" landing for fortune-agent.
 *
 * An ink-wash, zen, oracle-card-reveal aesthetic. Mobile-first (390px primary).
 * Presentational only — no backend. Tapping a card calls onSelect(id) if
 * provided, otherwise console.log.
 *
 * Design direction: Chinese classical calligraphy meets modern minimalism.
 * Vertical scroll as a ritual. One breath per block. Dark ambient background
 * with gold/ember accents. Single glyph per card, generous whitespace.
 */

import React, { useState, useCallback } from 'react';
import { motion, useReducedMotion, type Variants } from 'framer-motion';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type FortuneUseCaseId =
    | 'compatibility'
    | 'lucky-day'
    | 'yearly-monthly'
    | 'custom-wish'
    | 'naming-timing'
    | 'career-window';

export interface FortuneAgentLandingAProps {
    onSelect?: (id: FortuneUseCaseId, meta?: Record<string, unknown>) => void;
}

// ---------------------------------------------------------------------------
// Tokens — fall back gracefully if CSS vars aren't defined
// ---------------------------------------------------------------------------

const BG = 'var(--ming-bg, #0c0a14)';
const ACCENT = 'var(--ming-accent, #dc2626)';
const GOLD = 'var(--ming-gold, #eab308)';
const FONT_CN = "var(--ming-font-chinese, 'Noto Serif SC', 'Songti SC', serif)";

// ---------------------------------------------------------------------------
// Motion primitives
// ---------------------------------------------------------------------------

const fadeUp: Variants = {
    hidden: { opacity: 0, y: 18 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.9, ease: [0.22, 0.61, 0.36, 1] },
    },
};

const stagger: Variants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.12, delayChildren: 0.05 } },
};

// ---------------------------------------------------------------------------
// Content — every word intentional
// ---------------------------------------------------------------------------

const OCCASION_CHIPS: Array<{ id: string; label: string; cn: string }> = [
    { id: 'opening', label: 'Business Opening', cn: '开张' },
    { id: 'wedding', label: 'Wedding', cn: '婚礼' },
    { id: 'moving', label: 'Moving Home', cn: '搬家' },
    { id: 'contract', label: 'Signing Contract', cn: '签约' },
    { id: 'travel', label: 'Travel', cn: '出行' },
];

interface UseCase {
    id: FortuneUseCaseId;
    glyph: string;       // Chinese character flourish
    title: string;       // 2-5 words
    hint: string;        // one line
    more?: boolean;
}

const CORE_USE_CASES: UseCase[] = [
    {
        id: 'compatibility',
        glyph: '合',
        title: 'Compatibility Check',
        hint: 'Two birth profiles. One honest reading.',
    },
    {
        id: 'lucky-day',
        glyph: '择',
        title: 'Lucky Day Picker',
        hint: 'Choose an auspicious date for what matters.',
    },
    {
        id: 'yearly-monthly',
        glyph: '运',
        title: 'Fortune This Year',
        hint: 'Is the current cycle kind to you?',
    },
    {
        id: 'custom-wish',
        glyph: '问',
        title: 'Ask Freely',
        hint: 'A single question, answered with care.',
    },
];

const MORE_USE_CASES: UseCase[] = [
    {
        id: 'naming-timing',
        glyph: '名',
        title: 'Baby Naming Window',
        hint: 'Timing a name the old way.',
        more: true,
    },
    {
        id: 'career-window',
        glyph: '迁',
        title: 'Career Pivot Window',
        hint: 'When the door opens, and when it doesn\u2019t.',
        more: true,
    },
];

// ---------------------------------------------------------------------------
// Atoms
// ---------------------------------------------------------------------------

function InkDivider({ className = '' }: { className?: string }) {
    return (
        <div className={`flex items-center justify-center gap-3 ${className}`} aria-hidden>
            <span
                className="h-px w-16"
                style={{
                    background: `linear-gradient(to right, transparent, ${GOLD}55, transparent)`,
                }}
            />
            <span className="text-[10px] tracking-[0.4em]" style={{ color: `${GOLD}99` }}>
                ◦
            </span>
            <span
                className="h-px w-16"
                style={{
                    background: `linear-gradient(to right, transparent, ${GOLD}55, transparent)`,
                }}
            />
        </div>
    );
}

function SectionLabel({ cn, en }: { cn: string; en: string }) {
    return (
        <motion.div variants={fadeUp} className="mb-5 flex items-baseline gap-3">
            <span
                className="text-2xl leading-none"
                style={{ fontFamily: FONT_CN, color: GOLD }}
            >
                {cn}
            </span>
            <span
                className="text-[11px] uppercase tracking-[0.35em]"
                style={{ color: '#ffffff66' }}
            >
                {en}
            </span>
        </motion.div>
    );
}

interface CardProps {
    useCase: UseCase;
    onTap: (id: FortuneUseCaseId) => void;
    children?: React.ReactNode;
}

function UseCaseCard({ useCase, onTap, children }: CardProps) {
    const reduce = useReducedMotion();
    return (
        <motion.button
            type="button"
            variants={fadeUp}
            whileTap={reduce ? undefined : { scale: 0.985 }}
            onClick={() => onTap(useCase.id)}
            className="group relative block w-full overflow-hidden rounded-2xl px-5 py-6 text-left transition-colors"
            style={{
                minHeight: 96,
                background: 'linear-gradient(180deg, #15121d 0%, #0f0d16 100%)',
                border: `1px solid ${useCase.more ? '#ffffff14' : '#ffffff1f'}`,
                boxShadow:
                    '0 1px 0 rgba(255,255,255,0.03) inset, 0 10px 30px -20px rgba(0,0,0,0.8)',
            }}
        >
            {/* soft ember glow on the right, gold seal */}
            <span
                aria-hidden
                className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full opacity-0 transition-opacity duration-700 group-hover:opacity-100"
                style={{
                    background: `radial-gradient(closest-side, ${ACCENT}22, transparent 70%)`,
                }}
            />

            <div className="flex items-start gap-4">
                <span
                    className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md"
                    style={{
                        fontFamily: FONT_CN,
                        fontSize: 26,
                        color: GOLD,
                        background: '#0b0913',
                        border: `1px solid ${GOLD}33`,
                        letterSpacing: 0,
                    }}
                    aria-hidden
                >
                    {useCase.glyph}
                </span>
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <h3 className="text-[17px] font-medium leading-tight text-white">
                            {useCase.title}
                        </h3>
                        {useCase.more && (
                            <span
                                className="rounded-full px-2 py-[2px] text-[9px] uppercase tracking-[0.2em]"
                                style={{
                                    color: '#ffffff88',
                                    border: '1px solid #ffffff1f',
                                }}
                            >
                                more
                            </span>
                        )}
                    </div>
                    <p className="mt-1.5 text-[13.5px] leading-relaxed" style={{ color: '#ffffffb0' }}>
                        {useCase.hint}
                    </p>
                    {children}
                </div>
                <span
                    className="mt-1 text-[18px] leading-none transition-transform group-hover:translate-x-0.5"
                    style={{ color: `${GOLD}bb` }}
                    aria-hidden
                >
                    →
                </span>
            </div>
        </motion.button>
    );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FortuneAgentLandingA({ onSelect }: FortuneAgentLandingAProps) {
    const [fortuneScope, setFortuneScope] = useState<'year' | 'month'>('year');
    const [wish, setWish] = useState('');

    const handleSelect = useCallback(
        (id: FortuneUseCaseId, meta?: Record<string, unknown>) => {
            if (onSelect) onSelect(id, meta);
            else {
                // presentational stub
                // eslint-disable-next-line no-console
                console.log('[fortune-agent] select', id, meta ?? {});
            }
        },
        [onSelect]
    );

    const viewportOnce = { once: true, amount: 0.25 } as const;

    return (
        <div
            className="relative min-h-screen w-full overflow-x-hidden"
            style={{
                background: BG,
                color: '#f5efe6',
            }}
        >
            {/* Ambient ink-wash backdrop */}
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0"
                style={{
                    background: `
                        radial-gradient(60% 40% at 50% 8%, ${ACCENT}22 0%, transparent 60%),
                        radial-gradient(40% 30% at 85% 30%, ${GOLD}14 0%, transparent 70%),
                        radial-gradient(50% 35% at 15% 75%, ${ACCENT}14 0%, transparent 70%)
                    `,
                }}
            />
            {/* Faint grain */}
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0 opacity-[0.04] mix-blend-overlay"
                style={{
                    backgroundImage:
                        'radial-gradient(rgba(255,255,255,0.6) 1px, transparent 1px)',
                    backgroundSize: '3px 3px',
                }}
            />

            <main className="relative mx-auto flex w-full max-w-[440px] flex-col px-5 pb-16 pt-12">
                {/* =========================== HERO =========================== */}
                <motion.section
                    initial="hidden"
                    animate="visible"
                    variants={stagger}
                    className="pt-6"
                >
                    <motion.div variants={fadeUp} className="mb-7 flex justify-center">
                        <span
                            className="inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[10.5px] uppercase tracking-[0.28em]"
                            style={{
                                color: `${GOLD}d0`,
                                border: `1px solid ${GOLD}33`,
                                background: '#ffffff05',
                            }}
                        >
                            <span
                                className="inline-block h-1.5 w-1.5 rounded-full"
                                style={{ background: GOLD }}
                                aria-hidden
                            />
                            Agent Harness Master
                        </span>
                    </motion.div>

                    <motion.h1
                        variants={fadeUp}
                        className="text-center leading-none"
                        style={{
                            fontFamily: FONT_CN,
                            fontSize: 92,
                            color: '#fbf5e8',
                            textShadow: `0 0 40px ${ACCENT}33`,
                            letterSpacing: '0.04em',
                        }}
                    >
                        命
                    </motion.h1>

                    <motion.div
                        variants={fadeUp}
                        className="mt-3 text-center text-[22px] font-light tracking-[0.22em]"
                        style={{ color: '#f5efe6' }}
                    >
                        fortune-agent
                    </motion.div>

                    <motion.p
                        variants={fadeUp}
                        className="mx-auto mt-5 max-w-[320px] text-center text-[14.5px] leading-relaxed"
                        style={{ color: '#ffffffa8' }}
                    >
                        An oracle in quiet conversation. Bring a date, a question, a decision —
                        receive a reading drawn from classical BaZi, rendered plainly.
                    </motion.p>

                    <motion.div variants={fadeUp}>
                        <InkDivider className="mt-10" />
                    </motion.div>
                </motion.section>

                {/* =========================== CORE USE CASES =========================== */}
                <motion.section
                    initial="hidden"
                    whileInView="visible"
                    viewport={viewportOnce}
                    variants={stagger}
                    className="mt-12"
                >
                    <SectionLabel cn="四问" en="Four Questions" />

                    <div className="flex flex-col gap-3.5">
                        {/* 1. Compatibility */}
                        <UseCaseCard useCase={CORE_USE_CASES[0]} onTap={handleSelect}>
                            <div
                                className="mt-3 flex items-center gap-2 text-[11.5px]"
                                style={{ color: '#ffffff80' }}
                            >
                                <span
                                    className="rounded-sm px-1.5 py-0.5"
                                    style={{ border: '1px solid #ffffff1a', fontFamily: FONT_CN }}
                                >
                                    你
                                </span>
                                <span style={{ color: `${GOLD}80` }}>&</span>
                                <span
                                    className="rounded-sm px-1.5 py-0.5"
                                    style={{ border: '1px solid #ffffff1a', fontFamily: FONT_CN }}
                                >
                                    他/她
                                </span>
                                <span className="ml-1">· romance, partnership, co-founders</span>
                            </div>
                        </UseCaseCard>

                        {/* 2. Lucky Day Picker */}
                        <UseCaseCard useCase={CORE_USE_CASES[1]} onTap={handleSelect}>
                            <div className="mt-3 flex flex-wrap gap-1.5">
                                {OCCASION_CHIPS.map((c) => (
                                    <button
                                        key={c.id}
                                        type="button"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleSelect('lucky-day', { occasion: c.id });
                                        }}
                                        className="rounded-full px-2.5 py-1 text-[11px] transition-colors"
                                        style={{
                                            color: '#ffffffb5',
                                            border: '1px solid #ffffff1f',
                                            background: '#ffffff04',
                                            minHeight: 28,
                                        }}
                                    >
                                        <span style={{ fontFamily: FONT_CN, color: `${GOLD}b0` }}>
                                            {c.cn}
                                        </span>
                                        <span className="mx-1.5" style={{ color: '#ffffff30' }}>·</span>
                                        {c.label}
                                    </button>
                                ))}
                            </div>
                        </UseCaseCard>

                        {/* 3. Yearly / Monthly toggle */}
                        <UseCaseCard useCase={CORE_USE_CASES[2]} onTap={handleSelect}>
                            <div
                                className="mt-3 inline-flex rounded-full p-0.5"
                                style={{
                                    border: '1px solid #ffffff1f',
                                    background: '#0a0812',
                                }}
                                role="tablist"
                                onClick={(e) => e.stopPropagation()}
                            >
                                {(['year', 'month'] as const).map((scope) => {
                                    const active = fortuneScope === scope;
                                    return (
                                        <button
                                            key={scope}
                                            type="button"
                                            role="tab"
                                            aria-selected={active}
                                            onClick={() => {
                                                setFortuneScope(scope);
                                                handleSelect('yearly-monthly', { scope });
                                            }}
                                            className="rounded-full px-4 py-1.5 text-[12px] uppercase tracking-[0.2em] transition-all"
                                            style={{
                                                minHeight: 32,
                                                color: active ? '#0b0913' : '#ffffffa0',
                                                background: active ? GOLD : 'transparent',
                                                fontWeight: active ? 600 : 400,
                                            }}
                                        >
                                            {scope === 'year' ? 'Year · 年' : 'Month · 月'}
                                        </button>
                                    );
                                })}
                            </div>
                        </UseCaseCard>

                        {/* 4. Custom Wish */}
                        <motion.div
                            variants={fadeUp}
                            className="relative overflow-hidden rounded-2xl px-5 py-6"
                            style={{
                                background: 'linear-gradient(180deg, #15121d 0%, #0f0d16 100%)',
                                border: `1px solid ${ACCENT}33`,
                            }}
                        >
                            <span
                                aria-hidden
                                className="pointer-events-none absolute -left-12 -bottom-12 h-40 w-40 rounded-full"
                                style={{
                                    background: `radial-gradient(closest-side, ${ACCENT}1a, transparent 70%)`,
                                }}
                            />
                            <div className="relative flex items-start gap-4">
                                <span
                                    className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md"
                                    style={{
                                        fontFamily: FONT_CN,
                                        fontSize: 26,
                                        color: GOLD,
                                        background: '#0b0913',
                                        border: `1px solid ${GOLD}33`,
                                    }}
                                    aria-hidden
                                >
                                    问
                                </span>
                                <div className="min-w-0 flex-1">
                                    <h3 className="text-[17px] font-medium leading-tight text-white">
                                        Ask Freely
                                    </h3>
                                    <p
                                        className="mt-1.5 text-[13.5px] leading-relaxed"
                                        style={{ color: '#ffffffb0' }}
                                    >
                                        Ask the engine anything.
                                    </p>
                                </div>
                            </div>

                            <div className="relative mt-4">
                                <textarea
                                    value={wish}
                                    onChange={(e) => setWish(e.target.value)}
                                    placeholder="Should I take the offer? Is this the year to move?"
                                    rows={2}
                                    className="w-full resize-none rounded-lg px-3.5 py-3 text-[14px] leading-relaxed outline-none transition-colors placeholder:text-[#ffffff55]"
                                    style={{
                                        minHeight: 72,
                                        color: '#f5efe6',
                                        background: '#0a0812',
                                        border: '1px solid #ffffff14',
                                        fontFamily: 'inherit',
                                    }}
                                />
                                <button
                                    type="button"
                                    onClick={() => handleSelect('custom-wish', { wish })}
                                    className="mt-3 inline-flex w-full items-center justify-center rounded-lg px-4 text-[13px] font-medium uppercase tracking-[0.28em] transition-all active:scale-[0.99]"
                                    style={{
                                        minHeight: 46,
                                        color: '#0b0913',
                                        background: GOLD,
                                        boxShadow: `0 10px 30px -12px ${GOLD}55`,
                                    }}
                                >
                                    Draw a reading
                                </button>
                            </div>
                        </motion.div>
                    </div>
                </motion.section>

                {/* =========================== MORE =========================== */}
                <motion.section
                    initial="hidden"
                    whileInView="visible"
                    viewport={viewportOnce}
                    variants={stagger}
                    className="mt-14"
                >
                    <motion.div variants={fadeUp}>
                        <InkDivider />
                    </motion.div>
                    <div className="mt-10">
                        <SectionLabel cn="更问" en="Further Readings" />
                        <div className="flex flex-col gap-3.5">
                            {MORE_USE_CASES.map((uc) => (
                                <UseCaseCard key={uc.id} useCase={uc} onTap={handleSelect} />
                            ))}
                        </div>
                    </div>
                </motion.section>

                {/* =========================== FOOTER =========================== */}
                <motion.footer
                    initial="hidden"
                    whileInView="visible"
                    viewport={viewportOnce}
                    variants={stagger}
                    className="mt-20"
                >
                    <motion.div variants={fadeUp}>
                        <InkDivider />
                    </motion.div>

                    <motion.div variants={fadeUp} className="mt-8 text-center">
                        <div
                            className="text-[24px] leading-none"
                            style={{ fontFamily: FONT_CN, color: `${GOLD}aa` }}
                        >
                            知命者不怨天
                        </div>
                        <div
                            className="mt-2 text-[11px] italic"
                            style={{ color: '#ffffff66' }}
                        >
                            Those who understand fate do not blame the sky.
                        </div>
                    </motion.div>

                    <motion.p
                        variants={fadeUp}
                        className="mt-8 text-center text-[11px] leading-relaxed"
                        style={{ color: '#ffffff55' }}
                    >
                        Powered by an agent harness I\u2019m learning to build.
                        <br />
                        Readings are offered as reflection, not prescription.
                    </motion.p>
                </motion.footer>
            </main>
        </div>
    );
}

export default FortuneAgentLandingA;
