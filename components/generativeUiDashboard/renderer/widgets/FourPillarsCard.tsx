/**
 * FourPillarsCard — Interactive BaZi Four Pillars display.
 *
 * Each pillar starts face-down and auto-reveals one by one on first load.
 * Tap to flip between Chinese characters (front) and element details (back).
 * Sparkle particles on flip. Day pillar gets a special glow highlight.
 * Mobile-first: 2x2 grid on narrow screens, 4x1 on wider screens.
 *
 * Called from: ComponentRenderer.tsx via Registry
 * Data path: /data/pillars (emitted by stream_bridge.emit_pillars)
 */

import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';

const ELEMENT_COLORS: Record<string, string> = {
    wood: '#22c55e',
    fire: '#ef4444',
    earth: '#d97706',
    metal: '#a1a1aa',
    water: '#3b82f6',
};

const ELEMENT_EMOJI: Record<string, string> = {
    wood: '\u{1F33F}',
    fire: '\u{1F525}',
    earth: '\u{1FAA8}',
    metal: '\u2694\uFE0F',
    water: '\u{1F30A}',
};

interface Pillar {
    raw: string;
    stem: string;
    branch: string;
    stemElement: string;
    branchElement: string;
}

interface PillarsData {
    year: Pillar;
    month: Pillar;
    day: Pillar;
    hour: Pillar | null;
    dayMaster: string;
    dayMasterElement: string;
    birthTimeUnknown: boolean;
}

const PILLAR_LABELS = [
    { key: 'year', zh: '\u5E74', en: 'Year' },
    { key: 'month', zh: '\u6708', en: 'Month' },
    { key: 'day', zh: '\u65E5', en: 'Day' },
    { key: 'hour', zh: '\u65F6', en: 'Hour' },
] as const;

const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.08 } },
};

const cardVariants = {
    hidden: { opacity: 0, y: 24, scale: 0.92 },
    visible: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: { type: 'spring', stiffness: 300, damping: 22, mass: 0.6 },
    },
};

/* ------------------------------------------------------------------ */
/* Sparkle overlay                                                     */
/* ------------------------------------------------------------------ */

function SparkleOverlay({ color }: { color: string }) {
    const particles = useMemo(
        () =>
            Array.from({ length: 6 }, (_, i) => ({
                id: i,
                left: `${20 + Math.random() * 60}%`,
                top: `${20 + Math.random() * 60}%`,
                dx: (Math.random() - 0.5) * 40,
                dy: (Math.random() - 0.5) * 40,
            })),
        []
    );

    return (
        <div className="pointer-events-none absolute inset-0 z-10">
            {particles.map((p) => (
                <motion.div
                    key={p.id}
                    className="absolute h-1.5 w-1.5 rounded-full"
                    style={{ background: color, left: p.left, top: p.top }}
                    initial={{ opacity: 1, scale: 0 }}
                    animate={{ opacity: 0, scale: 2, x: p.dx, y: p.dy }}
                    transition={{ duration: 0.5, ease: 'easeOut' }}
                />
            ))}
        </div>
    );
}

/* ------------------------------------------------------------------ */
/* Single interactive pillar card                                      */
/* ------------------------------------------------------------------ */

function PillarFlipCard({
    pillar,
    label,
    isDayPillar,
    dayMasterColor,
    index,
}: {
    pillar: Pillar;
    label: { key: string; zh: string; en: string };
    isDayPillar: boolean;
    dayMasterColor: string;
    index: number;
}) {
    const [isRevealed, setIsRevealed] = useState(false);
    const [isFlipped, setIsFlipped] = useState(false);
    const [sparkle, setSparkle] = useState(false);

    const stemColor = ELEMENT_COLORS[pillar.stemElement] || '#f8fafc';
    const branchColor = ELEMENT_COLORS[pillar.branchElement] || '#f8fafc';
    const borderColor = isDayPillar ? dayMasterColor : 'rgba(148, 163, 184, 0.15)';

    // Auto-reveal: cards flip from mystery to front one by one
    useEffect(() => {
        const timer = setTimeout(() => {
            setIsRevealed(true);
        }, 600 + index * 500);
        return () => clearTimeout(timer);
    }, [index]);

    const handleFlip = useCallback(() => {
        if (!isRevealed) {
            // Tap to skip waiting — reveal immediately
            setIsRevealed(true);
            return;
        }
        setIsFlipped((f) => !f);
        setSparkle(true);
        setTimeout(() => setSparkle(false), 600);
        // Haptic feedback (Android Chrome)
        if (navigator.vibrate) navigator.vibrate(10);
    }, [isRevealed]);

    // Determine rotation: mystery = 180, front = 0, back (element details) = 180
    const rotateY = !isRevealed ? 180 : isFlipped ? 180 : 0;

    return (
        <motion.div
            variants={cardVariants}
            className="relative cursor-pointer select-none"
            style={{ perspective: 'min(600px, 50vw)', touchAction: 'manipulation' }}
            onClick={handleFlip}
            whileTap={{ scale: 0.95 }}
        >
            {/* Sparkle effect on flip */}
            <AnimatePresence>
                {sparkle && <SparkleOverlay color={stemColor} />}
            </AnimatePresence>

            <motion.div
                className="relative w-full"
                animate={{ rotateY }}
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                style={{ transformStyle: 'preserve-3d' }}
            >
                {/* FRONT — Chinese characters */}
                <div
                    className="flex flex-col items-center gap-1.5 rounded-xl p-3 sm:p-4"
                    style={{
                        backfaceVisibility: 'hidden',
                        background: isDayPillar
                            ? `${dayMasterColor}12`
                            : 'rgba(148, 163, 184, 0.04)',
                        border: `1.5px solid ${borderColor}`,
                        boxShadow: isDayPillar
                            ? `0 0 20px ${dayMasterColor}20, inset 0 1px 0 ${dayMasterColor}15`
                            : 'none',
                    }}
                >
                    {/* Label */}
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        {label.zh} \u00B7 {label.en}
                    </span>

                    {/* Stem character */}
                    <motion.span
                        className="leading-none"
                        style={{
                            fontFamily: "var(--ming-font-chinese, 'Noto Serif SC', 'Songti SC', serif)",
                            fontSize: 'clamp(1.6rem, 5vw, 2.4rem)',
                            color: stemColor,
                            textShadow: `0 0 12px ${stemColor}40`,
                        }}
                        initial={{ opacity: 0, scale: 0.5 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: index * 0.1 + 0.2, type: 'spring', stiffness: 400, damping: 20 }}
                    >
                        {pillar.stem}
                    </motion.span>

                    {/* Divider */}
                    <div
                        className="h-px w-6"
                        style={{ background: `linear-gradient(90deg, transparent, ${stemColor}40, transparent)` }}
                    />

                    {/* Branch character */}
                    <motion.span
                        className="leading-none"
                        style={{
                            fontFamily: "var(--ming-font-chinese, 'Noto Serif SC', 'Songti SC', serif)",
                            fontSize: 'clamp(1.6rem, 5vw, 2.4rem)',
                            color: branchColor,
                            textShadow: `0 0 12px ${branchColor}40`,
                        }}
                        initial={{ opacity: 0, scale: 0.5 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: index * 0.1 + 0.3, type: 'spring', stiffness: 400, damping: 20 }}
                    >
                        {pillar.branch}
                    </motion.span>

                    {/* Day master badge */}
                    {isDayPillar && (
                        <motion.span
                            className="mt-1 rounded-full px-2 py-0.5 text-[10px] font-bold"
                            style={{
                                backgroundColor: `${dayMasterColor}20`,
                                color: dayMasterColor,
                                border: `1px solid ${dayMasterColor}40`,
                            }}
                            animate={{ opacity: [0.6, 1, 0.6] }}
                            transition={{ duration: 2, repeat: Infinity }}
                        >
                            \u2605 Day Master
                        </motion.span>
                    )}

                    {/* Tap hint */}
                    <span className="mt-1 text-[9px] text-slate-600">tap to flip</span>
                </div>

                {/* MYSTERY FACE — shown before reveal */}
                <div
                    className="absolute inset-0 flex flex-col items-center justify-center rounded-xl"
                    style={{
                        backfaceVisibility: 'hidden',
                        transform: 'rotateY(180deg)',
                        background: 'rgba(148, 163, 184, 0.06)',
                        border: '1.5px solid rgba(148, 163, 184, 0.15)',
                    }}
                >
                    <motion.span
                        className="text-2xl"
                        animate={{ scale: [1, 1.1, 1], rotate: [0, 5, -5, 0] }}
                        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                    >
                        \u2728
                    </motion.span>
                    <span className="mt-1.5 text-[10px] text-slate-500">{label.en}</span>
                    <span className="mt-0.5 text-[9px] text-slate-600">tap to reveal</span>
                </div>

                {/* BACK — Element details (shown when user taps revealed card) */}
                {/* This shares the 180deg face with mystery, but mystery is only visible pre-reveal */}
                {isRevealed && (
                    <div
                        className="absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-xl p-3 sm:p-4"
                        style={{
                            backfaceVisibility: 'hidden',
                            transform: 'rotateY(180deg)',
                            background: isDayPillar
                                ? `${dayMasterColor}12`
                                : 'rgba(148, 163, 184, 0.04)',
                            border: `1.5px solid ${borderColor}`,
                        }}
                    >
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                            {label.en} Elements
                        </span>

                        {/* Stem element */}
                        <div className="flex items-center gap-1.5">
                            <span className="text-lg">{ELEMENT_EMOJI[pillar.stemElement] || '\u2726'}</span>
                            <div>
                                <span className="text-xs text-slate-500">Stem</span>
                                <p className="text-sm font-semibold capitalize" style={{ color: stemColor }}>
                                    {pillar.stemElement}
                                </p>
                            </div>
                        </div>

                        {/* Branch element */}
                        <div className="flex items-center gap-1.5">
                            <span className="text-lg">{ELEMENT_EMOJI[pillar.branchElement] || '\u2726'}</span>
                            <div>
                                <span className="text-xs text-slate-500">Branch</span>
                                <p className="text-sm font-semibold capitalize" style={{ color: branchColor }}>
                                    {pillar.branchElement}
                                </p>
                            </div>
                        </div>

                        <span className="mt-1 text-[9px] text-slate-600">tap to flip back</span>
                    </div>
                )}
            </motion.div>
        </motion.div>
    );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */

export function FourPillarsCard({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const data = resolveBoundValue(
        props.pillarsPath as BoundValue | undefined,
        dataModel
    ) as PillarsData | undefined;

    const pillars = useMemo(() => {
        if (!data) return [];
        const entries = PILLAR_LABELS.map(({ key, zh, en }) => {
            const pillar = data[key as keyof PillarsData] as Pillar | null;
            if (!pillar) return null;
            return { key, zh, en, pillar };
        });
        return entries.filter(Boolean) as {
            key: string;
            zh: string;
            en: string;
            pillar: Pillar;
        }[];
    }, [data]);

    if (!data || pillars.length === 0) {
        return <div data-component-id={componentId} />;
    }

    const dayMasterColor = ELEMENT_COLORS[data.dayMasterElement] || '#eab308';

    return (
        <div data-component-id={componentId} className="w-full">
            {/* Responsive grid: 2x2 on mobile, row on wider screens */}
            <motion.div
                className={`grid gap-2.5 ${pillars.length === 4 ? 'grid-cols-2 sm:grid-cols-4' : ''}`}
                style={
                    pillars.length !== 4
                        ? { gridTemplateColumns: `repeat(${pillars.length}, 1fr)` }
                        : undefined
                }
                variants={containerVariants}
                initial="hidden"
                animate="visible"
            >
                {pillars.map(({ key, zh, en, pillar }, index) => (
                    <PillarFlipCard
                        key={key}
                        pillar={pillar}
                        label={{ key, zh, en }}
                        isDayPillar={key === 'day'}
                        dayMasterColor={dayMasterColor}
                        index={index}
                    />
                ))}
            </motion.div>

            {/* Day master summary */}
            <motion.div
                className="mt-3 flex items-center justify-center gap-2 text-sm text-slate-400"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5 }}
            >
                <span>Day Master:</span>
                <span
                    className="rounded-full px-2.5 py-0.5 text-xs font-bold"
                    style={{
                        backgroundColor: `${dayMasterColor}20`,
                        color: dayMasterColor,
                        border: `1px solid ${dayMasterColor}40`,
                    }}
                >
                    {ELEMENT_EMOJI[data.dayMasterElement] || ''} {data.dayMaster} \u00B7 {data.dayMasterElement}
                </span>
                {data.birthTimeUnknown && (
                    <span className="text-xs text-slate-500">(time unknown)</span>
                )}
            </motion.div>
        </div>
    );
}
