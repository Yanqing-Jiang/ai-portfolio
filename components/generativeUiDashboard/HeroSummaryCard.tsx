/**
 * HeroSummaryCard — "Character card" showing day master archetype.
 *
 * First thing users see on the "Your Story" tab. Translates raw BaZi
 * stem data into an emotionally engaging identity card.
 *
 * Data: reads from the shared dataModel (same paths as A2UI widgets)
 *   - /data/pillars  → day master stem + element
 *   - /data/narrative → tldr
 *   - /data/kpi      → seasonal strength
 */

import { useMemo, useEffect, useState } from 'react';
import { motion } from 'framer-motion';

// ---------------------------------------------------------------------------
// Archetype lookup — 10 Heavenly Stems → personality archetypes
// ---------------------------------------------------------------------------

const ARCHETYPES: Record<string, { name: string; nameZh: string; tagline: string }> = {
    '\u7532': { name: 'The Towering Pine', nameZh: '\u53C2\u5929\u677E', tagline: 'A natural leader who grows through adversity' },
    '\u4E59': { name: 'The Winding Vine', nameZh: '\u7F20\u7ED5\u85E4', tagline: 'Adaptable and resilient, finding strength in flexibility' },
    '\u4E19': { name: 'The Blazing Sun', nameZh: '\u70C8\u65E5', tagline: 'Radiant and generous, illuminating everything you touch' },
    '\u4E01': { name: 'The Candlelight', nameZh: '\u70DB\u5149', tagline: 'Warm and perceptive, seeing what others miss' },
    '\u620A': { name: 'The Mountain', nameZh: '\u9AD8\u5C71', tagline: 'Steady and dependable, the ground others build on' },
    '\u5DF1': { name: 'The Fertile Field', nameZh: '\u6C83\u571F', tagline: 'Nurturing and patient, cultivating lasting value' },
    '\u5E9A': { name: 'The Blade', nameZh: '\u5229\u5203', tagline: 'Sharp and decisive, cutting through complexity' },
    '\u8F9B': { name: 'The Gem', nameZh: '\u5B9D\u77F3', tagline: 'Refined and discerning, finding beauty in precision' },
    '\u58EC': { name: 'The Ocean', nameZh: '\u5927\u6D77', tagline: 'Deep and powerful, moving with unstoppable momentum' },
    '\u7678': { name: 'The Morning Dew', nameZh: '\u671D\u9732', tagline: 'Gentle and intuitive, nourishing everything subtly' },
};

const ELEMENT_COLORS: Record<string, string> = {
    wood: '#22c55e',
    fire: '#ef4444',
    earth: '#d97706',
    metal: '#d4d4d8',
    water: '#3b82f6',
};

const POLARITY: Record<string, string> = {
    '\u7532': 'Yang Wood', '\u4E59': 'Yin Wood',
    '\u4E19': 'Yang Fire', '\u4E01': 'Yin Fire',
    '\u620A': 'Yang Earth', '\u5DF1': 'Yin Earth',
    '\u5E9A': 'Yang Metal', '\u8F9B': 'Yin Metal',
    '\u58EC': 'Yang Water', '\u7678': 'Yin Water',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface HeroSummaryCardProps {
    dataModel: Record<string, unknown>;
}

export function HeroSummaryCard({ dataModel }: HeroSummaryCardProps) {
    const pillars = dataModel.pillars as Record<string, unknown> | undefined;
    const narrative = dataModel.narrative as Record<string, unknown> | undefined;
    const kpi = dataModel.kpi as Record<string, unknown> | undefined;

    const stem = useMemo(() => {
        if (!pillars) return null;
        const day = pillars.day as Record<string, unknown> | undefined;
        return (day?.stem as string) || (pillars.day_master as string) || null;
    }, [pillars]);

    const element = useMemo(() => {
        if (!pillars) return null;
        return (pillars.day_master_element as string) || null;
    }, [pillars]);

    const archetype = stem ? ARCHETYPES[stem] : null;
    const color = element ? ELEMENT_COLORS[element.toLowerCase()] : '#94a3b8';
    const tldr = narrative?.tldr as string | undefined;
    const strength = kpi?.seasonalStrength as string | undefined;
    const polarity = stem ? POLARITY[stem] : null;

    // Respect prefers-reduced-motion
    const [reduceMotion, setReduceMotion] = useState(false);
    useEffect(() => {
        const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
        setReduceMotion(mq.matches);
        const handler = (e: MediaQueryListEvent) => setReduceMotion(e.matches);
        mq.addEventListener('change', handler);
        return () => mq.removeEventListener('change', handler);
    }, []);

    // Don't render until we have at least the stem
    if (!stem) return null;

    return (
        <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 200, damping: 22 }}
            className="relative overflow-hidden rounded-2xl border p-5 sm:p-6"
            style={{
                background: `radial-gradient(ellipse at 30% 40%, ${color}0a 0%, transparent 70%), rgba(148, 163, 184, 0.04)`,
                borderColor: `${color}30`,
            }}
        >
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4 sm:gap-6">
                {/* Day master character with glow */}
                <motion.div
                    initial={{ scale: 0.3, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ type: 'spring', stiffness: 200, damping: 18, delay: 0.2 }}
                    className="relative flex-shrink-0"
                >
                    <span
                        className="block text-center leading-none select-none"
                        style={{
                            fontSize: 'clamp(4rem, 12vw, 6rem)',
                            color,
                            fontFamily: 'var(--ming-font-chinese)',
                            textShadow: `0 0 40px ${color}30, 0 0 80px ${color}15`,
                            letterSpacing: '0.05em',
                        }}
                    >
                        {stem}
                    </span>
                    {/* Breathing glow behind character */}
                    <motion.div
                        animate={reduceMotion ? { opacity: 0.2 } : { opacity: [0.15, 0.25, 0.15] }}
                        transition={reduceMotion ? {} : { duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                        className="absolute inset-0 -z-10 rounded-full blur-2xl"
                        style={{ background: color }}
                    />
                </motion.div>

                {/* Identity text */}
                <div className="flex-1 text-center sm:text-left">
                    {archetype && (
                        <motion.h2
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.35 }}
                            className="text-2xl sm:text-3xl font-extrabold"
                            style={{ color: 'var(--ming-gold, #eab308)' }}
                        >
                            {archetype.name}
                        </motion.h2>
                    )}
                    {archetype && (
                        <p
                            className="mt-0.5 text-xs text-slate-500"
                            style={{ fontFamily: 'var(--ming-font-chinese)', letterSpacing: '0.1em' }}
                        >
                            {archetype.nameZh}
                        </p>
                    )}

                    {/* TL;DR or archetype tagline */}
                    <motion.p
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.5 }}
                        className="mt-3 text-sm leading-relaxed text-slate-300"
                    >
                        {tldr || archetype?.tagline || ''}
                    </motion.p>

                    {/* Badges */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.65 }}
                        className="mt-4 flex flex-wrap justify-center sm:justify-start gap-2"
                    >
                        {polarity && (
                            <Badge label={polarity} color={color} />
                        )}
                        {strength && (
                            <Badge
                                label={strength}
                                color={
                                    strength.toLowerCase().includes('strong') ? '#22c55e'
                                    : strength.toLowerCase().includes('weak') ? '#ef4444'
                                    : '#d97706'
                                }
                            />
                        )}
                        {element && (
                            <Badge label={element.charAt(0).toUpperCase() + element.slice(1)} color={color} />
                        )}
                    </motion.div>
                </div>
            </div>
        </motion.div>
    );
}

function Badge({ label, color }: { label: string; color: string }) {
    return (
        <span
            className="inline-block rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider"
            style={{
                color,
                backgroundColor: `${color}15`,
                border: `1px solid ${color}20`,
            }}
        >
            {label}
        </span>
    );
}
