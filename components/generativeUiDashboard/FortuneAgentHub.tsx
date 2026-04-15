/**
 * FortuneAgentHub — Cinematic snap-scroll landing for the reimagined
 * fortune-agent project (prev. ming-engine).
 *
 * One full-viewport section at a time. Mobile-first (390px).
 * Hero has three artistic wordmark variants selectable via `?v=a|b|c`
 * (default a): Vermillion Seal, Gilded Pillar, Calligraphic Void.
 *
 * Tiles on the hero scroll down to the corresponding in-page section.
 * Each section has a gold chevron that jumps to the next; the closing
 * section has an up-chevron that returns to the hero.
 */

import React, {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
} from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type FortunePurposeId =
    | 'compatibility'
    | 'lucky-day'
    | 'luck-draw'
    | 'custom-wish';

export interface FortuneAgentHubProps {
    onSelect?: (purposeId: FortunePurposeId) => void;
}

type HeroVariant = 'a' | 'b' | 'c';

// ---------------------------------------------------------------------------
// Tokens
// ---------------------------------------------------------------------------

const TOKEN = {
    bg: 'var(--ming-bg, #0c0a14)',
    accent: 'var(--ming-accent, #dc2626)',
    gold: 'var(--ming-gold, #eab308)',
    chinese: "var(--ming-font-chinese, 'Noto Serif SC', 'Songti SC', serif)",
};

const HEX = {
    gold: '#eab308',
    bg: '#0c0a14',
    accent: '#dc2626',
    ivory: '#f8fafc',
};

// ---------------------------------------------------------------------------
// Section metadata
// ---------------------------------------------------------------------------

type SectionId =
    | 'hero'
    | 'compat'
    | 'lucky-day'
    | 'luck-draw'
    | 'custom-wish'
    | 'closing';

interface SectionMeta {
    id: SectionId;
    label: string;
    gradient: [string, string];
}

const SECTIONS: SectionMeta[] = [
    { id: 'hero',        label: 'Welcome',        gradient: ['#0c0a14', '#141028'] },
    { id: 'compat',      label: 'Compatibility',  gradient: ['#1a0a10', '#3a0f14'] },
    { id: 'lucky-day',   label: 'Occasion',       gradient: ['#1a1304', '#3a2a08'] },
    { id: 'luck-draw',   label: 'Cycle Reading',  gradient: ['#200a06', '#4a1608'] },
    { id: 'custom-wish', label: 'Custom Wish',    gradient: ['#0a0c14', '#161a2a'] },
    { id: 'closing',     label: 'More',           gradient: ['#0c0a14', '#0c0a14'] },
];

// ---------------------------------------------------------------------------
// SVG Motifs
// ---------------------------------------------------------------------------

function PillarPair({ className = '' }: { className?: string }) {
    return (
        <svg viewBox="0 0 240 260" className={className} aria-hidden="true">
            <defs>
                <linearGradient id="fa-pg-l" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#7a1f1f" stopOpacity="0.9" />
                    <stop offset="100%" stopColor="#2a0707" stopOpacity="0.6" />
                </linearGradient>
                <linearGradient id="fa-pg-r" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8a2727" stopOpacity="0.9" />
                    <stop offset="100%" stopColor="#2a0707" stopOpacity="0.6" />
                </linearGradient>
            </defs>
            <g transform="translate(40 30) rotate(6 40 110)">
                <rect x="0" y="0" width="60" height="220" rx="4" fill="url(#fa-pg-l)" stroke={HEX.gold} strokeOpacity="0.25" />
                <text x="30" y="60"  textAnchor="middle" fill={HEX.gold} fillOpacity="0.7" fontFamily={TOKEN.chinese} fontSize="28">年</text>
                <text x="30" y="110" textAnchor="middle" fill={HEX.gold} fillOpacity="0.7" fontFamily={TOKEN.chinese} fontSize="28">月</text>
                <text x="30" y="160" textAnchor="middle" fill={HEX.gold} fillOpacity="0.7" fontFamily={TOKEN.chinese} fontSize="28">日</text>
                <text x="30" y="210" textAnchor="middle" fill={HEX.gold} fillOpacity="0.7" fontFamily={TOKEN.chinese} fontSize="28">時</text>
            </g>
            <g transform="translate(140 30) rotate(-6 40 110)">
                <rect x="0" y="0" width="60" height="220" rx="4" fill="url(#fa-pg-r)" stroke={HEX.gold} strokeOpacity="0.25" />
                <text x="30" y="60"  textAnchor="middle" fill={HEX.gold} fillOpacity="0.7" fontFamily={TOKEN.chinese} fontSize="28">年</text>
                <text x="30" y="110" textAnchor="middle" fill={HEX.gold} fillOpacity="0.7" fontFamily={TOKEN.chinese} fontSize="28">月</text>
                <text x="30" y="160" textAnchor="middle" fill={HEX.gold} fillOpacity="0.7" fontFamily={TOKEN.chinese} fontSize="28">日</text>
                <text x="30" y="210" textAnchor="middle" fill={HEX.gold} fillOpacity="0.7" fontFamily={TOKEN.chinese} fontSize="28">時</text>
            </g>
            <motion.path
                d="M 86 140 Q 120 110 154 140"
                stroke={HEX.gold}
                strokeWidth="1.2"
                fill="none"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 0.85 }}
                transition={{ duration: 1.6, ease: 'easeInOut', delay: 0.3 }}
            />
            <circle cx="120" cy="125" r="2.5" fill={HEX.gold} />
        </svg>
    );
}

function LunarWheel({ className = '' }: { className?: string }) {
    const phases = 12;
    return (
        <svg viewBox="0 0 240 240" className={className} aria-hidden="true">
            <defs>
                <radialGradient id="fa-lw-core" cx="0.5" cy="0.5" r="0.5">
                    <stop offset="0%" stopColor={HEX.gold} stopOpacity="0.25" />
                    <stop offset="100%" stopColor={HEX.gold} stopOpacity="0" />
                </radialGradient>
            </defs>
            <circle cx="120" cy="120" r="100" fill="url(#fa-lw-core)" />
            <motion.g
                animate={{ rotate: 360 }}
                transition={{ duration: 120, ease: 'linear', repeat: Infinity }}
                style={{ originX: '120px', originY: '120px' }}
            >
                {Array.from({ length: phases }).map((_, i) => {
                    const a = (i / phases) * Math.PI * 2;
                    const cx = 120 + Math.cos(a) * 90;
                    const cy = 120 + Math.sin(a) * 90;
                    const full = i % 4 === 0;
                    return (
                        <g key={i}>
                            <circle cx={cx} cy={cy} r="8" fill={HEX.bg} stroke={HEX.gold} strokeOpacity="0.55" />
                            {full && <circle cx={cx} cy={cy} r="5" fill={HEX.gold} fillOpacity="0.85" />}
                            {!full && (
                                <path
                                    d={`M ${cx - 3} ${cy - 4} A 5 5 0 0 1 ${cx - 3} ${cy + 4}`}
                                    fill={HEX.gold}
                                    fillOpacity="0.55"
                                />
                            )}
                        </g>
                    );
                })}
            </motion.g>
            {Array.from({ length: 30 }).map((_, i) => {
                const a = (i / 30) * Math.PI * 2;
                const x1 = 120 + Math.cos(a) * 68;
                const y1 = 120 + Math.sin(a) * 68;
                const x2 = 120 + Math.cos(a) * 74;
                const y2 = 120 + Math.sin(a) * 74;
                return (
                    <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={HEX.gold} strokeOpacity="0.3" strokeWidth="1" />
                );
            })}
            <text x="120" y="132" textAnchor="middle" fill={HEX.gold} fillOpacity="0.9" fontFamily={TOKEN.chinese} fontSize="44">吉</text>
        </svg>
    );
}

function EmberRing({ className = '' }: { className?: string }) {
    return (
        <svg viewBox="0 0 240 240" className={className} aria-hidden="true">
            <defs>
                <radialGradient id="fa-er-glow" cx="0.5" cy="0.5" r="0.5">
                    <stop offset="0%" stopColor="#ff7a2a" stopOpacity="0.9" />
                    <stop offset="60%" stopColor={HEX.accent} stopOpacity="0.4" />
                    <stop offset="100%" stopColor={HEX.accent} stopOpacity="0" />
                </radialGradient>
            </defs>
            <circle cx="120" cy="120" r="90" fill="none" stroke={HEX.accent} strokeOpacity="0.25" strokeWidth="1.5" strokeDasharray="2 6" />
            <circle cx="120" cy="120" r="70" fill="none" stroke={HEX.gold} strokeOpacity="0.25" strokeWidth="1" />
            <motion.g
                animate={{ rotate: 360 }}
                transition={{ duration: 10, ease: 'linear', repeat: Infinity }}
                style={{ originX: '120px', originY: '120px' }}
            >
                <circle cx="210" cy="120" r="22" fill="url(#fa-er-glow)" />
                <circle cx="210" cy="120" r="4.5" fill="#ffcf7a" />
            </motion.g>
            <text x="120" y="136" textAnchor="middle" fill={HEX.gold} fillOpacity="0.9" fontFamily={TOKEN.chinese} fontSize="52">運</text>
        </svg>
    );
}

function InkPool({ className = '' }: { className?: string }) {
    return (
        <svg viewBox="0 0 240 200" className={className} aria-hidden="true">
            <defs>
                <radialGradient id="fa-ip-pool" cx="0.5" cy="0.5" r="0.5">
                    <stop offset="0%" stopColor="#0a0a14" stopOpacity="1" />
                    <stop offset="100%" stopColor="#0a0a14" stopOpacity="0.3" />
                </radialGradient>
            </defs>
            <ellipse cx="120" cy="120" rx="90" ry="24" fill="none" stroke={HEX.gold} strokeOpacity="0.5" strokeWidth="1" />
            <ellipse cx="120" cy="120" rx="86" ry="22" fill="url(#fa-ip-pool)" />
            {[0, 1, 2].map((i) => (
                <motion.ellipse
                    key={i}
                    cx="120"
                    cy="120"
                    fill="none"
                    stroke={HEX.gold}
                    strokeOpacity="0.35"
                    initial={{ rx: 10, ry: 2.5, opacity: 0 }}
                    animate={{ rx: 72, ry: 18, opacity: [0, 0.4, 0] }}
                    transition={{ duration: 4.5, delay: i * 1.5, repeat: Infinity, ease: 'easeOut' }}
                />
            ))}
            <motion.circle
                cx="120"
                r="3"
                fill={HEX.gold}
                animate={{ cy: [60, 118, 60], opacity: [0, 1, 0] }}
                transition={{ duration: 4.5, repeat: Infinity, ease: 'easeIn' }}
            />
        </svg>
    );
}

// ---------------------------------------------------------------------------
// Progress rail
// ---------------------------------------------------------------------------

interface ProgressRailProps {
    activeIndex: number;
    onJump: (i: number) => void;
}

function ProgressRail({ activeIndex, onJump }: ProgressRailProps) {
    return (
        <nav
            aria-label="Section progress"
            className="pointer-events-none fixed right-0 top-1/2 z-40 -translate-y-1/2 pr-2"
        >
            <ul className="pointer-events-auto flex flex-col items-center gap-2">
                {SECTIONS.map((s, i) => {
                    const active = i === activeIndex;
                    return (
                        <li key={s.id}>
                            <button
                                type="button"
                                onClick={() => onJump(i)}
                                aria-label={`Jump to ${s.label}`}
                                aria-current={active ? 'true' : undefined}
                                className="group relative flex h-11 w-11 items-center justify-center"
                            >
                                <span
                                    className="block rounded-full transition-all duration-500"
                                    style={{
                                        width: active ? 3 : 2,
                                        height: active ? 26 : 14,
                                        background: active ? TOKEN.gold : 'rgba(234,179,8,0.28)',
                                        boxShadow: active ? `0 0 8px ${HEX.gold}` : 'none',
                                    }}
                                />
                            </button>
                        </li>
                    );
                })}
            </ul>
        </nav>
    );
}

// ---------------------------------------------------------------------------
// Section chevron (down for mid sections, up on closing)
// ---------------------------------------------------------------------------

interface SectionNavButtonProps {
    direction: 'down' | 'up';
    onClick: () => void;
    label: string;
}

function SectionNavButton({ direction, onClick, label }: SectionNavButtonProps) {
    const reduce = useReducedMotion();
    return (
        <button
            type="button"
            onClick={onClick}
            aria-label={label}
            className="absolute inset-x-0 bottom-5 z-30 flex justify-center md:bottom-8"
        >
            <motion.span
                initial={{ opacity: 0, y: direction === 'down' ? -4 : 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
                whileHover={reduce ? undefined : { scale: 1.08 }}
                whileTap={reduce ? undefined : { scale: 0.94 }}
                className="relative inline-flex h-11 w-11 items-center justify-center rounded-full"
                style={{
                    border: `1px solid ${HEX.gold}`,
                    background: 'rgba(12,10,20,0.55)',
                    color: HEX.gold,
                    backdropFilter: 'blur(6px)',
                    WebkitBackdropFilter: 'blur(6px)',
                    boxShadow: `0 0 18px -6px ${HEX.gold}`,
                }}
            >
                {!reduce && (
                    <motion.span
                        aria-hidden
                        className="absolute inset-0 rounded-full"
                        style={{ boxShadow: `0 0 0 1px ${HEX.gold}` }}
                        animate={{ opacity: [0.2, 0.7, 0.2], scale: [1, 1.14, 1] }}
                        transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
                    />
                )}
                <motion.svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    animate={reduce ? undefined : { y: direction === 'down' ? [0, 4, 0] : [0, -4, 0] }}
                    transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                >
                    {direction === 'down' ? (
                        <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    ) : (
                        <path d="M6 15l6-6 6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    )}
                </motion.svg>
            </motion.span>
        </button>
    );
}

// ---------------------------------------------------------------------------
// Section shell
// ---------------------------------------------------------------------------

interface SectionShellProps {
    sectionId: SectionId;
    gradient: [string, string];
    children: React.ReactNode;
    nav?: { direction: 'down' | 'up'; onClick: () => void; label: string };
}

const SectionShell = React.forwardRef<HTMLElement, SectionShellProps>(
    function SectionShell({ sectionId, gradient, children, nav }, ref) {
        return (
            <section
                ref={ref}
                id={`section-${sectionId}`}
                data-section-id={sectionId}
                className="relative flex h-[100svh] w-full flex-none snap-start items-center justify-center overflow-hidden px-6"
                style={{
                    background: `linear-gradient(180deg, ${gradient[0]} 0%, ${gradient[1]} 100%)`,
                    scrollSnapAlign: 'start',
                }}
            >
                {children}
                {nav && <SectionNavButton direction={nav.direction} onClick={nav.onClick} label={nav.label} />}
            </section>
        );
    },
);

// ---------------------------------------------------------------------------
// Hero variants — artistic fortune-agent wordmark
// ---------------------------------------------------------------------------

function VermillionSealVariant({ reduce }: { reduce: boolean }) {
    // Big off-center ivory 命 ink-wash, diagonal gold "fortune-agent" wordmark,
    // red seal with carved 命 stamped at the tail.
    return (
        <div className="relative flex h-[240px] w-full items-center justify-center sm:h-[280px]">
            <motion.span
                aria-hidden
                initial={{ opacity: 0, scale: 1.1 }}
                animate={{ opacity: 0.14, scale: 1 }}
                transition={{ duration: 1.4, ease: 'easeOut' }}
                className="pointer-events-none absolute select-none leading-none"
                style={{
                    fontFamily: TOKEN.chinese,
                    color: HEX.ivory,
                    fontSize: 'clamp(220px, 60vw, 360px)',
                    left: '50%',
                    top: '50%',
                    transform: 'translate(-50%, -50%)',
                    textShadow: `0 0 80px ${HEX.accent}33`,
                }}
            >
                命
            </motion.span>

            <div className="relative" style={{ transform: 'rotate(-8deg)' }}>
                <motion.h1
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.9, ease: [0.22, 0.61, 0.36, 1], delay: 0.3 }}
                    className="flex items-baseline tracking-tight"
                    style={{
                        fontFamily: "'Bodoni Moda', 'Playfair Display', Georgia, serif",
                        color: HEX.gold,
                        fontWeight: 300,
                        fontSize: 'clamp(54px, 15vw, 96px)',
                        lineHeight: 0.9,
                        letterSpacing: '-0.03em',
                    }}
                >
                    {'fortune-agent'.split('').map((ch, i) => (
                        <motion.span
                            key={`${ch}-${i}`}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.4 + i * 0.04, duration: 0.6 }}
                        >
                            {ch === '-' ? <span style={{ opacity: 0.5, margin: '0 0.05em' }}>–</span> : ch}
                        </motion.span>
                    ))}
                </motion.h1>

                <motion.span
                    aria-hidden
                    initial={{ scale: 2.4, opacity: 0, rotate: -6 }}
                    animate={reduce ? { scale: 1, opacity: 1, rotate: -6 } : { scale: [2.4, 0.9, 1], opacity: [0, 1, 1], rotate: [-12, -6, -6] }}
                    transition={{ duration: 0.9, delay: 1.25, ease: [0.5, 0, 0.75, 0] }}
                    className="absolute flex items-center justify-center"
                    style={{
                        right: '-18px',
                        bottom: '-22px',
                        width: 56,
                        height: 56,
                        background: HEX.accent,
                        color: HEX.ivory,
                        fontFamily: TOKEN.chinese,
                        fontSize: 34,
                        lineHeight: 1,
                        letterSpacing: 0,
                        boxShadow: `0 6px 22px -8px ${HEX.accent}`,
                        borderRadius: 4,
                    }}
                >
                    命
                </motion.span>
            </div>
        </div>
    );
}

function GildedPillarVariant({ reduce }: { reduce: boolean }) {
    // Three vertical gold lines form a pillar. Vertical 命 + 運 on the left,
    // stacked FORTUNE / AGENT on the right.
    return (
        <div className="relative flex h-[260px] w-full items-center justify-center sm:h-[300px]">
            <div className="pointer-events-none absolute inset-y-2 left-1/2 flex -translate-x-1/2 gap-[4px]">
                {[0, 1, 2].map((i) => (
                    <motion.span
                        key={i}
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: '100%', opacity: i === 1 ? 0.7 : 0.35 }}
                        transition={{ duration: 0.9, delay: 0.15 + i * 0.1, ease: 'easeOut' }}
                        className="block w-px"
                        style={{ background: HEX.gold }}
                    />
                ))}
            </div>

            <div className="relative z-10 flex items-stretch gap-5">
                <motion.div
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.8, delay: 0.55 }}
                    className="flex flex-col items-center justify-center gap-1"
                    style={{ fontFamily: TOKEN.chinese, color: HEX.ivory }}
                >
                    {['命', '運'].map((ch, i) => (
                        <motion.span
                            key={ch}
                            initial={{ opacity: 0, y: -8 }}
                            animate={{ opacity: i === 0 ? 0.95 : 0.6, y: 0 }}
                            transition={{ duration: 0.6, delay: 0.7 + i * 0.15 }}
                            style={{ fontSize: 'clamp(44px, 11vw, 62px)', lineHeight: 1 }}
                        >
                            {ch}
                        </motion.span>
                    ))}
                </motion.div>

                <div className="flex flex-col items-start justify-center">
                    <motion.span
                        initial={{ x: -18, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        transition={{ duration: 0.8, delay: 0.85 }}
                        className="block"
                        style={{
                            fontFamily: "'Inter', 'Helvetica Neue', sans-serif",
                            fontWeight: 900,
                            color: HEX.gold,
                            fontSize: 'clamp(32px, 9vw, 54px)',
                            letterSpacing: '0.14em',
                            lineHeight: 0.95,
                        }}
                    >
                        FORTUNE
                    </motion.span>
                    <motion.span
                        initial={{ x: -28, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        transition={{ duration: 0.8, delay: 1.0 }}
                        className="mt-1 block"
                        style={{
                            fontFamily: "'Inter', 'Helvetica Neue', sans-serif",
                            fontWeight: 200,
                            color: HEX.ivory,
                            fontSize: 'clamp(22px, 6.5vw, 36px)',
                            letterSpacing: '0.38em',
                            lineHeight: 1,
                        }}
                    >
                        AGENT
                    </motion.span>
                    {!reduce && (
                        <motion.span
                            aria-hidden
                            initial={{ opacity: 0, width: 0 }}
                            animate={{ opacity: 0.6, width: 64 }}
                            transition={{ duration: 0.8, delay: 1.2 }}
                            className="mt-2 block h-px"
                            style={{ background: HEX.gold }}
                        />
                    )}
                </div>
            </div>
        </div>
    );
}

function CalligraphicVoidVariant({ reduce }: { reduce: boolean }) {
    // Massive ivory 命 with "fortune-agent" carved out of its horizontal
    // stroke via SVG mask — the indigo bg shows through as the letters.
    return (
        <div className="relative flex h-[260px] w-full items-center justify-center sm:h-[300px]">
            <svg
                viewBox="0 0 360 260"
                className="h-full w-auto"
                aria-hidden
                style={{ maxWidth: '100%' }}
            >
                <defs>
                    <mask id="fa-void-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="360" height="260">
                        <rect x="0" y="0" width="360" height="260" fill="white" />
                        <text
                            x="180"
                            y="152"
                            textAnchor="middle"
                            fontFamily="'Inter', 'Helvetica Neue', sans-serif"
                            fontSize="22"
                            fontWeight={700}
                            letterSpacing="2"
                            fill="black"
                        >
                            fortune-agent
                        </text>
                    </mask>
                </defs>
                <motion.text
                    x="180"
                    y="205"
                    textAnchor="middle"
                    fontFamily={TOKEN.chinese}
                    fontSize="240"
                    fontWeight={500}
                    fill={HEX.ivory}
                    mask="url(#fa-void-mask)"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: reduce ? 0.3 : 1.4, ease: 'easeOut' }}
                >
                    命
                </motion.text>
                <motion.circle
                    cx="298"
                    cy="58"
                    r="4"
                    fill={HEX.gold}
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.6, delay: 1.2 }}
                />
                <motion.circle
                    cx="62"
                    cy="202"
                    r="3"
                    fill={HEX.accent}
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 0.85, scale: 1 }}
                    transition={{ duration: 0.6, delay: 1.35 }}
                />
            </svg>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

interface HeroProps {
    variant: HeroVariant;
    sectionRef: React.RefObject<HTMLElement>;
    onScrollNext: () => void;
    onJumpToSection: (sectionIndex: number) => void;
}

const TILE_TO_SECTION: Record<FortunePurposeId, number> = {
    'compatibility': 1,
    'lucky-day': 2,
    'luck-draw': 3,
    'custom-wish': 4,
};

function HeroSection({ variant, sectionRef, onScrollNext, onJumpToSection }: HeroProps) {
    const contentRef = useRef<HTMLDivElement>(null!);
    const reduce = useReducedMotion() ?? false;
    const inView = useInView(contentRef, { amount: 0.5 });

    const anim = {
        initial: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 },
        animate: inView ? { opacity: 1, y: 0 } : { opacity: 0.35, y: 12 },
        transition: { duration: 0.9, ease: [0.22, 0.61, 0.36, 1] as [number, number, number, number] },
    };

    const tiles: {
        id: FortunePurposeId;
        glyph: string;
        label: string;
    }[] = [
        { id: 'compatibility', glyph: '緣', label: 'Compatibility' },
        { id: 'lucky-day', glyph: '擇', label: 'Occasion' },
        { id: 'luck-draw', glyph: '運', label: 'Cycle Reading' },
        { id: 'custom-wish', glyph: '問', label: 'Ask Anything' },
    ];

    let artwork: React.ReactNode;
    if (variant === 'b') artwork = <GildedPillarVariant reduce={reduce} />;
    else if (variant === 'c') artwork = <CalligraphicVoidVariant reduce={reduce} />;
    else artwork = <VermillionSealVariant reduce={reduce} />;

    return (
        <SectionShell
            ref={sectionRef}
            sectionId="hero"
            gradient={SECTIONS[0].gradient}
            nav={{ direction: 'down', onClick: onScrollNext, label: 'Continue to Compatibility' }}
        >
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0 opacity-60"
                style={{
                    background:
                        'radial-gradient(60% 50% at 50% 35%, rgba(234,179,8,0.08) 0%, rgba(12,10,20,0) 60%)',
                }}
            />
            <motion.div
                ref={contentRef}
                {...anim}
                className="relative z-10 flex h-full w-full max-w-xl flex-col items-center justify-center gap-8 py-14 text-center sm:gap-10"
            >
                {/* Artistic wordmark — THE centerpiece */}
                <div className="w-full">{artwork}</div>

                {/* "Pick a subject" label, above the tiles */}
                <div className="flex flex-col items-center gap-5 w-full">
                    <p
                        className="text-[12px] uppercase tracking-[0.38em] text-white/60 sm:text-[13px]"
                        style={{ fontFamily: TOKEN.chinese }}
                    >
                        Pick a subject
                    </p>

                    {/* 4 bigger tiles — each scrolls to its section */}
                    <div className="grid w-full max-w-[520px] grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-3">
                        {tiles.map((t, i) => (
                            <motion.button
                                key={t.id}
                                type="button"
                                onClick={() => onJumpToSection(TILE_TO_SECTION[t.id])}
                                aria-label={`Jump to ${t.label} section`}
                                initial={{
                                    opacity: 0,
                                    y: 12,
                                    borderColor: 'rgba(234,179,8,0.22)',
                                    backgroundColor: 'rgba(12,10,20,0.4)',
                                }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.3 + i * 0.08, duration: 0.6, ease: 'easeOut' }}
                                whileHover={
                                    reduce
                                        ? undefined
                                        : {
                                              y: -3,
                                              borderColor: 'rgba(234,179,8,0.85)',
                                              backgroundColor: 'rgba(234,179,8,0.14)',
                                          }
                                }
                                whileTap={reduce ? undefined : { scale: 0.97 }}
                                className="flex min-h-[96px] flex-col items-center justify-center gap-2 rounded-2xl border px-3 py-4 text-center sm:min-h-[108px]"
                            >
                                <span
                                    className="block text-[15px] font-medium leading-tight text-white/95 sm:text-[16px]"
                                    style={{ letterSpacing: '-0.005em' }}
                                >
                                    {t.label}
                                </span>
                                <span
                                    className="block"
                                    style={{
                                        fontFamily: TOKEN.chinese,
                                        color: TOKEN.gold,
                                        fontSize: 30,
                                        lineHeight: 1,
                                        opacity: 0.85,
                                    }}
                                >
                                    {t.glyph}
                                </span>
                            </motion.button>
                        ))}
                    </div>
                </div>
            </motion.div>
        </SectionShell>
    );
}

// ---------------------------------------------------------------------------
// Purpose section
// ---------------------------------------------------------------------------

interface PurposeSectionProps {
    id: SectionId;
    gradient: [string, string];
    eyebrow: string;
    glyph: string;
    headline: string;
    subline: string;
    cta: string;
    onCta: () => void;
    motif: React.ReactNode;
    sectionRef: React.RefObject<HTMLElement>;
    nav: { direction: 'down' | 'up'; onClick: () => void; label: string };
}

function PurposeSection({
    id,
    gradient,
    eyebrow,
    glyph,
    headline,
    subline,
    cta,
    onCta,
    motif,
    sectionRef,
    nav,
}: PurposeSectionProps) {
    const contentRef = useRef<HTMLDivElement>(null!);
    const reduce = useReducedMotion();
    const inView = useInView(contentRef, { amount: 0.5 });
    const anim = {
        initial: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 },
        animate: inView ? { opacity: 1, y: 0 } : { opacity: 0.35, y: 12 },
        transition: { duration: 0.9, ease: [0.22, 0.61, 0.36, 1] as [number, number, number, number] },
    };

    return (
        <SectionShell ref={sectionRef} sectionId={id} gradient={gradient} nav={nav}>
            <motion.div
                ref={contentRef}
                {...anim}
                className="relative z-10 flex w-full max-w-md flex-col items-center text-center"
            >
                <div className="mb-6 h-[220px] w-[220px] sm:h-[240px] sm:w-[240px]">
                    {motif}
                </div>

                <span
                    className="mb-3 text-[11px] uppercase tracking-[0.28em]"
                    style={{ color: 'rgba(234,179,8,0.85)' }}
                >
                    {eyebrow}
                </span>

                <h2 className="mb-2 text-[40px] leading-none text-white" style={{ fontFamily: TOKEN.chinese }}>
                    {glyph}
                </h2>

                <p className="mt-2 text-balance text-lg font-medium leading-snug text-white">{headline}</p>
                <p className="mt-2 max-w-xs text-balance text-sm leading-relaxed text-white/65">{subline}</p>

                <button
                    type="button"
                    onClick={onCta}
                    className="mt-8 inline-flex min-h-[44px] items-center gap-2 rounded-full px-6 py-3 text-sm font-medium text-white transition active:scale-[0.98]"
                    style={{
                        background: 'rgba(255,255,255,0.06)',
                        border: `1px solid ${TOKEN.gold}`,
                        boxShadow: `0 0 24px -10px ${HEX.gold}`,
                    }}
                >
                    {cta}
                    <span aria-hidden>→</span>
                </button>
            </motion.div>
        </SectionShell>
    );
}

// ---------------------------------------------------------------------------
// Custom wish (with input teaser)
// ---------------------------------------------------------------------------

interface CustomWishProps {
    onCta: () => void;
    sectionRef: React.RefObject<HTMLElement>;
    nav: { direction: 'down' | 'up'; onClick: () => void; label: string };
}

function CustomWishSection({ onCta, sectionRef, nav }: CustomWishProps) {
    const contentRef = useRef<HTMLDivElement>(null!);
    const reduce = useReducedMotion();
    const inView = useInView(contentRef, { amount: 0.5 });
    const anim = {
        initial: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 },
        animate: inView ? { opacity: 1, y: 0 } : { opacity: 0.35, y: 12 },
        transition: { duration: 0.9, ease: [0.22, 0.61, 0.36, 1] as [number, number, number, number] },
    };
    const [draft, setDraft] = useState('');

    return (
        <SectionShell ref={sectionRef} sectionId="custom-wish" gradient={SECTIONS[4].gradient} nav={nav}>
            <motion.div
                ref={contentRef}
                {...anim}
                className="relative z-10 flex w-full max-w-md flex-col items-center text-center"
            >
                <div className="mb-6 h-[180px] w-[220px]">
                    <InkPool className="h-full w-full" />
                </div>

                <span className="mb-3 text-[11px] uppercase tracking-[0.28em]" style={{ color: 'rgba(234,179,8,0.85)' }}>
                    Custom Wish
                </span>

                <h2 className="mb-2 text-[40px] leading-none text-white" style={{ fontFamily: TOKEN.chinese }}>
                    願
                </h2>

                <p className="mt-2 text-balance text-lg font-medium leading-snug text-white">
                    Ask anything the old heaven knows.
                </p>
                <p className="mt-2 max-w-xs text-balance text-sm leading-relaxed text-white/65">
                    Career windows. A name. A quiet fear. Phrase it plainly.
                </p>

                <label htmlFor="fa-wish-teaser" className="sr-only">Your question</label>
                <input
                    id="fa-wish-teaser"
                    type="text"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder="Should I take the offer?"
                    className="mt-6 w-full max-w-sm rounded-full border bg-transparent px-5 py-3 text-[15px] text-white placeholder:text-white/35 focus:outline-none"
                    style={{ borderColor: 'rgba(234,179,8,0.35)', minHeight: 44 }}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') onCta();
                    }}
                />

                <button
                    type="button"
                    onClick={onCta}
                    className="mt-5 inline-flex min-h-[44px] items-center gap-2 rounded-full px-6 py-3 text-sm font-medium text-white transition active:scale-[0.98]"
                    style={{
                        background: 'rgba(255,255,255,0.06)',
                        border: `1px solid ${TOKEN.gold}`,
                        boxShadow: `0 0 24px -10px ${HEX.gold}`,
                    }}
                >
                    Begin the question
                    <span aria-hidden>→</span>
                </button>
            </motion.div>
        </SectionShell>
    );
}

// ---------------------------------------------------------------------------
// Closing
// ---------------------------------------------------------------------------

interface ClosingProps {
    sectionRef: React.RefObject<HTMLElement>;
    onBackToTop: () => void;
}

function ClosingSection({ sectionRef, onBackToTop }: ClosingProps) {
    const contentRef = useRef<HTMLDivElement>(null!);
    const reduce = useReducedMotion();
    const inView = useInView(contentRef, { amount: 0.5 });
    const anim = {
        initial: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 },
        animate: inView ? { opacity: 1, y: 0 } : { opacity: 0.35, y: 12 },
        transition: { duration: 0.9, ease: [0.22, 0.61, 0.36, 1] as [number, number, number, number] },
    };
    return (
        <SectionShell
            ref={sectionRef}
            sectionId="closing"
            gradient={SECTIONS[5].gradient}
            nav={{ direction: 'up', onClick: onBackToTop, label: 'Back to top' }}
        >
            <motion.div
                ref={contentRef}
                {...anim}
                className="relative z-10 flex w-full max-w-md flex-col items-center text-center"
            >
                <div className="mb-8 text-[64px] leading-none" style={{ color: TOKEN.gold, fontFamily: TOKEN.chinese }}>
                    續
                </div>
                <p className="text-base leading-relaxed text-white/75">More coming —</p>
                <ul className="mt-3 flex flex-col gap-1 text-[15px] text-white/60">
                    <li>baby naming</li>
                    <li>career windows</li>
                    <li>feng shui dates</li>
                </ul>

                <div aria-hidden className="mt-16 h-px w-16" style={{ background: 'rgba(234,179,8,0.35)' }} />

                <p className="mt-6 text-[11px] uppercase tracking-[0.28em] text-white/45">
                    Running on my handcrafted agent harness
                </p>
            </motion.div>
        </SectionShell>
    );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function readVariantFromURL(): HeroVariant {
    if (typeof window === 'undefined') return 'b';
    const params = new URLSearchParams(window.location.search);
    const v = (params.get('v') || '').toLowerCase();
    if (v === 'a' || v === 'c') return v;
    return 'b';
}

export const FortuneAgentHub: React.FC<FortuneAgentHubProps> = ({
    onSelect = (id) => {
        // eslint-disable-next-line no-console
        console.log('[FortuneAgentHub] onSelect', id);
    },
}) => {
    const scrollerRef = useRef<HTMLDivElement>(null!);

    const heroRef       = useRef<HTMLElement>(null!);
    const compatRef     = useRef<HTMLElement>(null!);
    const luckyDayRef   = useRef<HTMLElement>(null!);
    const luckDrawRef   = useRef<HTMLElement>(null!);
    const customWishRef = useRef<HTMLElement>(null!);
    const closingRef    = useRef<HTMLElement>(null!);

    const sectionRefs = useMemo(
        () => [heroRef, compatRef, luckyDayRef, luckDrawRef, customWishRef, closingRef],
        [],
    );

    const [activeIndex, setActiveIndex] = useState(0);
    const [variant, setVariant] = useState<HeroVariant>('b');

    useEffect(() => {
        setVariant(readVariantFromURL());
    }, []);

    useEffect(() => {
        const scroller = scrollerRef.current;
        if (!scroller) return;

        const io = new IntersectionObserver(
            (entries) => {
                const visible = entries
                    .filter((e) => e.isIntersecting)
                    .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
                if (!visible) return;
                const idx = sectionRefs.findIndex((r) => r.current === visible.target);
                if (idx >= 0) setActiveIndex(idx);
            },
            { root: scroller, threshold: [0.5, 0.75] },
        );

        sectionRefs.forEach((r) => {
            if (r.current) io.observe(r.current);
        });

        return () => io.disconnect();
    }, [sectionRefs]);

    const jumpTo = useCallback(
        (i: number) => {
            const el = sectionRefs[i]?.current;
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        },
        [sectionRefs],
    );

    const handleSelect = useCallback(
        (purposeId: FortunePurposeId) => {
            try {
                onSelect(purposeId);
            } catch (err) {
                // eslint-disable-next-line no-console
                console.error('[FortuneAgentHub] onSelect threw', err);
            }
        },
        [onSelect],
    );

    return (
        <div className="relative w-full" style={{ background: TOKEN.bg, color: '#fff' }}>
            <ProgressRail activeIndex={activeIndex} onJump={jumpTo} />

            <div
                ref={scrollerRef}
                className="h-[100svh] w-full overflow-y-auto overflow-x-hidden"
                style={{
                    scrollSnapType: 'y mandatory',
                    WebkitOverflowScrolling: 'touch',
                    overscrollBehaviorY: 'contain',
                    touchAction: 'pan-y',
                }}
            >
                <HeroSection
                    variant={variant}
                    sectionRef={heroRef}
                    onScrollNext={() => jumpTo(1)}
                    onJumpToSection={(idx) => jumpTo(idx)}
                />

                <PurposeSection
                    sectionRef={compatRef}
                    id="compat"
                    gradient={SECTIONS[1].gradient}
                    eyebrow="Compatibility"
                    glyph="緣"
                    headline="See two charts sing."
                    subline="Two pillars leaning across a gold thread. Where they meet, fate hums."
                    cta="See two charts sing"
                    onCta={() => handleSelect('compatibility')}
                    motif={<PillarPair className="h-full w-full" />}
                    nav={{ direction: 'down', onClick: () => jumpTo(2), label: 'Continue to Occasion' }}
                />

                <PurposeSection
                    sectionRef={luckyDayRef}
                    id="lucky-day"
                    gradient={SECTIONS[2].gradient}
                    eyebrow="Occasion"
                    glyph="擇"
                    headline="Pick a day the sky agrees with."
                    subline="Weddings, signings, first days. Let the calendar lean your way."
                    cta="Find an auspicious date"
                    onCta={() => handleSelect('lucky-day')}
                    motif={<LunarWheel className="h-full w-full" />}
                    nav={{ direction: 'down', onClick: () => jumpTo(3), label: 'Continue to Cycle Reading' }}
                />

                <PurposeSection
                    sectionRef={luckDrawRef}
                    id="luck-draw"
                    gradient={SECTIONS[3].gradient}
                    eyebrow="Cycle Reading"
                    glyph="運"
                    headline="Where are you in the cycle?"
                    subline="An ember circles the ring. Some months glow; some are for rest."
                    cta="Draw this year's luck"
                    onCta={() => handleSelect('luck-draw')}
                    motif={<EmberRing className="h-full w-full" />}
                    nav={{ direction: 'down', onClick: () => jumpTo(4), label: 'Continue to Custom Wish' }}
                />

                <CustomWishSection
                    sectionRef={customWishRef}
                    onCta={() => handleSelect('custom-wish')}
                    nav={{ direction: 'down', onClick: () => jumpTo(5), label: 'Continue' }}
                />

                <ClosingSection sectionRef={closingRef} onBackToTop={() => jumpTo(0)} />
            </div>
        </div>
    );
};

export default FortuneAgentHub;
