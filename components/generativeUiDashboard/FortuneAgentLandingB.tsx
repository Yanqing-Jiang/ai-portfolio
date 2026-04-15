/**
 * FortuneAgentLandingB — "Tactile Bento" landing page for fortune-agent.
 *
 * Mobile-first bento grid of 5 primary entry points + 2 compact extras.
 * Design direction: iOS / Apple Vision Pro — glassmorphism with restraint,
 * tactile press animations, Chinese flourish (命 / 吉), premium not tacky.
 *
 * Drop-in replacement candidate for MingEnginePage's entry surface.
 * No backend calls — onSelect(id) prop or console.log fallback.
 */

import React, { useCallback, useMemo, useState } from 'react';
import { motion, MotionConfig, AnimatePresence } from 'framer-motion';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type FortuneAgentEntryId =
    | 'synastry'
    | 'lucky-day'
    | 'yearly-luck'
    | 'custom-wish'
    | 'baby-naming'
    | 'career-window';

export interface FortuneAgentLandingBProps {
    onSelect?: (id: FortuneAgentEntryId, payload?: Record<string, unknown>) => void;
    className?: string;
}

// ---------------------------------------------------------------------------
// Constants — occasions, toggles, motifs
// ---------------------------------------------------------------------------

const OCCASIONS = [
    { id: 'business', label: 'Business Opening', glyph: '開' },
    { id: 'wedding', label: 'Wedding', glyph: '囍' },
    { id: 'engagement', label: 'Engagement', glyph: '訂' },
    { id: 'moving', label: 'Moving', glyph: '遷' },
    { id: 'contract', label: 'Signing Contract', glyph: '約' },
    { id: 'travel', label: 'Travel', glyph: '行' },
] as const;

// ---------------------------------------------------------------------------
// Subtle SVG motifs — abstract, one per card, no emoji
// ---------------------------------------------------------------------------

const MotifRings: React.FC<{ className?: string }> = ({ className }) => (
    <svg viewBox="0 0 140 140" className={className} fill="none" aria-hidden>
        <circle cx="70" cy="70" r="54" stroke="currentColor" strokeOpacity="0.25" />
        <circle cx="70" cy="70" r="38" stroke="currentColor" strokeOpacity="0.45" />
        <circle cx="70" cy="70" r="22" stroke="currentColor" strokeOpacity="0.65" />
        <circle cx="70" cy="70" r="3" fill="currentColor" />
    </svg>
);

const MotifOrbit: React.FC<{ className?: string }> = ({ className }) => (
    <svg viewBox="0 0 160 120" className={className} fill="none" aria-hidden>
        <ellipse cx="80" cy="60" rx="62" ry="22" stroke="currentColor" strokeOpacity="0.4" />
        <ellipse cx="80" cy="60" rx="62" ry="22" stroke="currentColor" strokeOpacity="0.3" transform="rotate(55 80 60)" />
        <circle cx="40" cy="60" r="5" fill="currentColor" />
        <circle cx="120" cy="60" r="5" fill="currentColor" opacity="0.6" />
    </svg>
);

const MotifArc: React.FC<{ className?: string }> = ({ className }) => (
    <svg viewBox="0 0 120 120" className={className} fill="none" aria-hidden>
        <path d="M10 90 Q 60 10 110 90" stroke="currentColor" strokeOpacity="0.55" strokeWidth="1.5" />
        <circle cx="60" cy="42" r="3" fill="currentColor" />
        <path d="M10 90 L 110 90" stroke="currentColor" strokeOpacity="0.2" strokeDasharray="3 4" />
    </svg>
);

const MotifSpark: React.FC<{ className?: string }> = ({ className }) => (
    <svg viewBox="0 0 100 100" className={className} fill="none" aria-hidden>
        <path d="M50 8 L 54 46 L 92 50 L 54 54 L 50 92 L 46 54 L 8 50 L 46 46 Z" fill="currentColor" fillOpacity="0.55" />
    </svg>
);

const MotifGrid: React.FC<{ className?: string }> = ({ className }) => (
    <svg viewBox="0 0 120 120" className={className} fill="none" aria-hidden>
        {[0, 1, 2, 3].map((r) =>
            [0, 1, 2, 3].map((c) => (
                <circle
                    key={`${r}-${c}`}
                    cx={20 + c * 27}
                    cy={20 + r * 27}
                    r={1.5 + ((r + c) % 2)}
                    fill="currentColor"
                    fillOpacity={0.15 + ((r + c) % 3) * 0.15}
                />
            ))
        )}
    </svg>
);

const MotifWave: React.FC<{ className?: string }> = ({ className }) => (
    <svg viewBox="0 0 140 80" className={className} fill="none" aria-hidden>
        <path d="M0 40 Q 20 10 40 40 T 80 40 T 120 40 T 160 40" stroke="currentColor" strokeOpacity="0.55" />
        <path d="M0 55 Q 20 25 40 55 T 80 55 T 120 55 T 160 55" stroke="currentColor" strokeOpacity="0.3" />
    </svg>
);

// ---------------------------------------------------------------------------
// BentoCard — the core tile primitive
// ---------------------------------------------------------------------------

interface BentoCardProps {
    id: FortuneAgentEntryId;
    title: string;
    chinese?: string;
    hint: string;
    cta?: string;
    accent: 'gold' | 'crimson' | 'jade' | 'ink';
    span: 'hero' | 'wide' | 'square' | 'compact';
    motif: React.ReactNode;
    children?: React.ReactNode;
    onTap: (id: FortuneAgentEntryId) => void;
}

const ACCENT_TOKENS: Record<
    BentoCardProps['accent'],
    { ring: string; glyph: string; cta: string; glow: string }
> = {
    gold:    { ring: 'ring-amber-300/15',  glyph: 'text-amber-200/85',  cta: 'bg-amber-300/10 text-amber-100 border-amber-200/25', glow: 'from-amber-300/10' },
    crimson: { ring: 'ring-rose-400/15',   glyph: 'text-rose-300/90',   cta: 'bg-rose-400/10 text-rose-100 border-rose-300/25',    glow: 'from-rose-400/10' },
    jade:    { ring: 'ring-emerald-300/15',glyph: 'text-emerald-200/85',cta: 'bg-emerald-300/10 text-emerald-100 border-emerald-200/25', glow: 'from-emerald-300/10' },
    ink:     { ring: 'ring-slate-300/10',  glyph: 'text-slate-200/80',  cta: 'bg-white/5 text-slate-100 border-white/15',          glow: 'from-white/5' },
};

const SPAN_CLASSES: Record<BentoCardProps['span'], string> = {
    // mobile: 2-col grid. desktop >=md: 4-col grid.
    hero:    'col-span-2 md:col-span-4 row-span-2 min-h-[240px] md:min-h-[280px]',
    wide:    'col-span-2 md:col-span-2 min-h-[180px]',
    square:  'col-span-1 md:col-span-2 min-h-[180px]',
    compact: 'col-span-1 md:col-span-1 min-h-[140px]',
};

const cardMotion = {
    hidden: { opacity: 0, y: 14, scale: 0.98 },
    show:   { opacity: 1, y: 0,  scale: 1 },
};

function BentoCard({
    id,
    title,
    chinese,
    hint,
    cta = 'Begin',
    accent,
    span,
    motif,
    children,
    onTap,
}: BentoCardProps) {
    const tokens = ACCENT_TOKENS[accent];

    return (
        <motion.button
            type="button"
            variants={cardMotion}
            whileTap={{ scale: 0.97 }}
            whileHover={{ y: -2 }}
            transition={{ type: 'spring', stiffness: 380, damping: 28 }}
            onClick={() => onTap(id)}
            className={[
                'group relative text-left overflow-hidden',
                'rounded-3xl p-5 md:p-6',
                'bg-white/[0.035] backdrop-blur-xl',
                'border border-white/10',
                'ring-1', tokens.ring,
                'shadow-[0_1px_0_0_rgba(255,255,255,0.05)_inset,0_12px_40px_-20px_rgba(0,0,0,0.8)]',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-white/30',
                'transition-colors hover:bg-white/[0.06]',
                SPAN_CLASSES[span],
            ].join(' ')}
            aria-label={title}
        >
            {/* soft accent wash */}
            <div
                className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${tokens.glow} via-transparent to-transparent opacity-80`}
                aria-hidden
            />

            {/* motif */}
            <div
                className={`pointer-events-none absolute -right-6 -bottom-6 w-36 h-36 md:w-44 md:h-44 ${tokens.glyph}`}
                aria-hidden
            >
                {motif}
            </div>

            {/* content */}
            <div className="relative flex h-full flex-col justify-between gap-4">
                <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                        <div className="flex items-center gap-2">
                            <h3 className="text-[15px] md:text-base font-semibold tracking-tight text-white/95 truncate">
                                {title}
                            </h3>
                            {chinese && (
                                <span
                                    className={`text-sm md:text-base ${tokens.glyph}`}
                                    style={{ fontFamily: "var(--ming-font-chinese, 'Noto Serif SC', 'Songti SC', serif)" }}
                                >
                                    {chinese}
                                </span>
                            )}
                        </div>
                        <p className="mt-1 text-[12.5px] md:text-[13px] leading-snug text-white/55 line-clamp-3">
                            {hint}
                        </p>
                    </div>
                </div>

                {children && <div className="relative">{children}</div>}

                <div className="flex items-center justify-between">
                    <span
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${tokens.cta}`}
                    >
                        {cta}
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden>
                            <path d="M2 5h6M5 2l3 3-3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </span>
                    <span className="text-[10px] uppercase tracking-[0.18em] text-white/30">
                        {span === 'hero' ? 'featured' : span === 'compact' ? 'quick' : ''}
                    </span>
                </div>
            </div>
        </motion.button>
    );
}

// ---------------------------------------------------------------------------
// Embedded interactive teases (visual only — no backend)
// ---------------------------------------------------------------------------

function SynastryTease() {
    return (
        <div className="flex items-center gap-3">
            {(['A', 'B'] as const).map((p, i) => (
                <div
                    key={p}
                    className="flex items-center gap-2 rounded-2xl border border-white/10 bg-black/25 px-3 py-2 flex-1 min-w-0"
                >
                    <div
                        className={`h-7 w-7 rounded-xl grid place-items-center text-[11px] font-semibold ${
                            i === 0 ? 'bg-rose-400/20 text-rose-100' : 'bg-amber-300/20 text-amber-100'
                        }`}
                        style={{ fontFamily: "var(--ming-font-chinese, 'Noto Serif SC', serif)" }}
                    >
                        {i === 0 ? '陽' : '陰'}
                    </div>
                    <div className="min-w-0">
                        <div className="text-[11px] uppercase tracking-widest text-white/40">Person {p}</div>
                        <div className="text-[12.5px] text-white/80 truncate">Add birth profile</div>
                    </div>
                </div>
            ))}
            <div className="hidden md:flex h-10 w-8 items-center justify-center text-white/40">↔</div>
        </div>
    );
}

function LuckyDayTease() {
    return (
        <div className="flex flex-wrap gap-1.5">
            {OCCASIONS.slice(0, 6).map((o) => (
                <span
                    key={o.id}
                    className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] text-white/75"
                >
                    <span
                        className="text-amber-200/80"
                        style={{ fontFamily: "var(--ming-font-chinese, 'Noto Serif SC', serif)" }}
                    >
                        {o.glyph}
                    </span>
                    {o.label}
                </span>
            ))}
        </div>
    );
}

function YearlyLuckTease() {
    const [mode, setMode] = useState<'year' | 'month'>('year');
    return (
        <div className="flex items-center gap-2">
            <div
                className="relative inline-flex rounded-full border border-white/10 bg-black/30 p-0.5 text-[11px]"
                onClick={(e) => e.stopPropagation()}
            >
                {(['year', 'month'] as const).map((m) => (
                    <button
                        key={m}
                        type="button"
                        onClick={(e) => {
                            e.stopPropagation();
                            setMode(m);
                        }}
                        className={`relative z-10 min-w-[56px] px-3 py-1.5 rounded-full transition-colors ${
                            mode === m ? 'text-slate-900' : 'text-white/65'
                        }`}
                    >
                        {m === 'year' ? 'Year' : 'Month'}
                    </button>
                ))}
                <motion.span
                    layout
                    className="absolute inset-y-0.5 w-[56px] rounded-full bg-emerald-200/90"
                    initial={false}
                    animate={{ x: mode === 'year' ? 2 : 58 }}
                    transition={{ type: 'spring', stiffness: 420, damping: 30 }}
                />
            </div>
            <div className="text-[11px] text-white/45">2026 · 丙午</div>
        </div>
    );
}

function CustomWishTease() {
    return (
        <div className="rounded-2xl border border-white/10 bg-black/30 px-3 py-2.5 text-[12.5px] text-white/50">
            <span className="select-none">Ask anything the old heaven knows…</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function FortuneAgentLandingB({ onSelect, className }: FortuneAgentLandingBProps) {
    const handleSelect = useCallback(
        (id: FortuneAgentEntryId, payload?: Record<string, unknown>) => {
            if (onSelect) {
                onSelect(id, payload);
                return;
            }
            // eslint-disable-next-line no-console
            console.log('[fortune-agent] select', id, payload ?? {});
        },
        [onSelect]
    );

    const gridVariants = useMemo(
        () => ({
            hidden: {},
            show: {
                transition: { staggerChildren: 0.055, delayChildren: 0.08 },
            },
        }),
        []
    );

    const bgStyle: React.CSSProperties = {
        background:
            'radial-gradient(1200px 600px at 50% -10%, rgba(234,179,8,0.08), transparent 60%),' +
            'radial-gradient(900px 500px at 90% 110%, rgba(220,38,38,0.06), transparent 60%),' +
            'var(--ming-bg, #0c0a14)',
    };

    return (
        <MotionConfig reducedMotion="user">
            <div
                className={['min-h-screen w-full text-white antialiased', className ?? ''].join(' ')}
                style={bgStyle}
            >
                <div className="mx-auto w-full max-w-[1120px] px-4 pt-8 pb-16 md:px-8 md:pt-14">
                    {/* Hero */}
                    <motion.header
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, ease: [0.2, 0.7, 0.2, 1] }}
                        className="relative mb-6 md:mb-10"
                    >
                        <div className="flex items-center gap-2">
                            <span
                                className="inline-flex items-center gap-1.5 rounded-full border border-white/12 bg-white/[0.04] px-2.5 py-1 text-[10.5px] uppercase tracking-[0.18em] text-white/70"
                                title="Agent Harness Master"
                            >
                                <span className="h-1.5 w-1.5 rounded-full bg-amber-300/90 shadow-[0_0_6px_rgba(252,211,77,0.9)]" />
                                Agent Harness Master
                            </span>
                            <span className="text-[10.5px] uppercase tracking-[0.18em] text-white/30">
                                v0.2 · bento
                            </span>
                        </div>

                        <div className="mt-4 flex items-end gap-3">
                            <h1 className="text-[34px] leading-none md:text-[56px] font-semibold tracking-tight text-white">
                                fortune<span className="text-white/40">-</span>agent
                            </h1>
                            <span
                                aria-hidden
                                className="text-[30px] md:text-[48px] leading-none -translate-y-[2px] bg-gradient-to-br from-amber-200 via-amber-300 to-rose-300 bg-clip-text text-transparent"
                                style={{ fontFamily: "var(--ming-font-chinese, 'Noto Serif SC', 'Songti SC', serif)" }}
                            >
                                命
                            </span>
                            <span
                                aria-hidden
                                className="hidden md:inline text-[30px] md:text-[40px] leading-none -translate-y-[2px] text-white/25"
                                style={{ fontFamily: "var(--ming-font-chinese, 'Noto Serif SC', 'Songti SC', serif)" }}
                            >
                                吉
                            </span>
                        </div>

                        <p className="mt-3 max-w-xl text-[13.5px] md:text-[15px] leading-relaxed text-white/55">
                            A tactile entry point to BaZi fortune, auspicious dates, and yearly luck —
                            one agent, five gates.
                        </p>
                    </motion.header>

                    {/* Bento Grid */}
                    <motion.section
                        variants={gridVariants}
                        initial="hidden"
                        animate="show"
                        aria-label="Fortune entry points"
                        className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 auto-rows-[minmax(0,auto)]"
                    >
                        {/* 1. Compatibility Check — HERO */}
                        <BentoCard
                            id="synastry"
                            title="Compatibility Check"
                            chinese="合婚"
                            hint="See how two BaZi charts sing (or clash) together. A duet of pillars, elements, and timing."
                            cta="Start synastry"
                            accent="crimson"
                            span="hero"
                            motif={<MotifOrbit className="w-full h-full" />}
                            onTap={handleSelect}
                        >
                            <SynastryTease />
                        </BentoCard>

                        {/* 2. Lucky Day Picker — WIDE */}
                        <BentoCard
                            id="lucky-day"
                            title="Lucky Day Picker"
                            chinese="擇日"
                            hint="Pick an auspicious date for the moments that matter."
                            cta="Pick occasion"
                            accent="gold"
                            span="wide"
                            motif={<MotifRings className="w-full h-full" />}
                            onTap={handleSelect}
                        >
                            <LuckyDayTease />
                        </BentoCard>

                        {/* 3. Yearly / Monthly Luck — SQUARE (2-col on desktop) */}
                        <BentoCard
                            id="yearly-luck"
                            title="Yearly & Monthly Luck"
                            chinese="流年"
                            hint="Is this year lucky for you? Drill from year into month."
                            cta="See my luck"
                            accent="jade"
                            span="square"
                            motif={<MotifWave className="w-full h-full" />}
                            onTap={handleSelect}
                        >
                            <YearlyLuckTease />
                        </BentoCard>

                        {/* 4. Custom Wish — SQUARE */}
                        <BentoCard
                            id="custom-wish"
                            title="Custom Wish"
                            chinese="問天"
                            hint="A free-text fortune question, answered in the old idiom."
                            cta="Ask"
                            accent="ink"
                            span="square"
                            motif={<MotifSpark className="w-full h-full" />}
                            onTap={handleSelect}
                        >
                            <CustomWishTease />
                        </BentoCard>

                        {/* 5. Baby Naming — COMPACT */}
                        <BentoCard
                            id="baby-naming"
                            title="Baby Naming"
                            chinese="取名"
                            hint="Names tuned to the pillars of a newborn."
                            cta="Suggest names"
                            accent="gold"
                            span="compact"
                            motif={<MotifGrid className="w-full h-full" />}
                            onTap={handleSelect}
                        />

                        {/* 6. Career Window — COMPACT */}
                        <BentoCard
                            id="career-window"
                            title="Career Window"
                            chinese="事業"
                            hint="Timing windows for moves, launches, and pivots."
                            cta="Find window"
                            accent="jade"
                            span="compact"
                            motif={<MotifArc className="w-full h-full" />}
                            onTap={handleSelect}
                        />
                    </motion.section>

                    {/* Footer whisper */}
                    <AnimatePresence>
                        <motion.div
                            key="whisper"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.4, duration: 0.5 }}
                            className="mt-8 md:mt-12 flex items-center justify-between text-[11px] text-white/35"
                        >
                            <span>Built on the ming-engine · No data leaves the device in this preview.</span>
                            <span
                                className="tracking-[0.2em] text-white/30"
                                style={{ fontFamily: "var(--ming-font-chinese, 'Noto Serif SC', serif)" }}
                            >
                                順 · 天 · 應 · 人
                            </span>
                        </motion.div>
                    </AnimatePresence>
                </div>
            </div>
        </MotionConfig>
    );
}

export default FortuneAgentLandingB;
