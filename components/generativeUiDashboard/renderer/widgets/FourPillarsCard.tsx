/**
 * FourPillarsCard — BaZi Four Pillars display widget.
 *
 * Renders Year/Month/Day/Hour pillars in a grid with Chinese characters,
 * element color badges, and day master highlight.
 *
 * Called from: ComponentRenderer.tsx via Registry
 * Data path: /data/pillars (emitted by stream_bridge.emit_pillars)
 */

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
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
    { key: 'year', zh: '年柱', en: 'Year' },
    { key: 'month', zh: '月柱', en: 'Month' },
    { key: 'day', zh: '日柱', en: 'Day' },
    { key: 'hour', zh: '时柱', en: 'Hour' },
] as const;

const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.1 } },
};

const columnVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { type: 'spring', stiffness: 200, damping: 25, mass: 0.8 },
    },
};

function ElementBadge({ element }: { element: string }) {
    const color = ELEMENT_COLORS[element] || '#94a3b8';
    return (
        <span
            className="inline-block rounded-full px-2 py-0.5 text-xs font-medium"
            style={{
                backgroundColor: `${color}20`,
                color,
                border: `1px solid ${color}40`,
            }}
        >
            {element}
        </span>
    );
}

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
            <motion.div
                className="grid gap-3"
                style={{
                    gridTemplateColumns: `repeat(${pillars.length}, 1fr)`,
                }}
                variants={containerVariants}
                initial="hidden"
                animate="visible"
            >
                {pillars.map(({ key, zh, en, pillar }) => {
                    const isDayPillar = key === 'day';
                    return (
                        <motion.div
                            key={key}
                            variants={columnVariants}
                            className="flex flex-col items-center gap-2 rounded-lg p-3"
                            style={{
                                background: isDayPillar
                                    ? `${dayMasterColor}10`
                                    : 'rgba(148, 163, 184, 0.06)',
                                border: isDayPillar
                                    ? `1.5px solid ${dayMasterColor}40`
                                    : '1px solid rgba(148, 163, 184, 0.1)',
                            }}
                        >
                            {/* Header */}
                            <span className="text-xs text-slate-500">
                                {zh} · {en}
                            </span>

                            {/* Stem */}
                            <span
                                className="leading-none"
                                style={{
                                    fontFamily:
                                        "var(--ming-font-chinese, 'Noto Serif SC', 'Songti SC', serif)",
                                    fontSize: 'clamp(1.2rem, 4vw, 2rem)',
                                    color:
                                        ELEMENT_COLORS[pillar.stemElement] ||
                                        '#f8fafc',
                                }}
                            >
                                {pillar.stem}
                            </span>

                            {/* Branch */}
                            <span
                                className="leading-none"
                                style={{
                                    fontFamily:
                                        "var(--ming-font-chinese, 'Noto Serif SC', 'Songti SC', serif)",
                                    fontSize: 'clamp(1.2rem, 4vw, 2rem)',
                                    color:
                                        ELEMENT_COLORS[pillar.branchElement] ||
                                        '#f8fafc',
                                }}
                            >
                                {pillar.branch}
                            </span>

                            {/* Element badges */}
                            <div className="flex flex-col items-center gap-1">
                                <ElementBadge element={pillar.stemElement} />
                                <ElementBadge element={pillar.branchElement} />
                            </div>

                            {/* Day master indicator */}
                            {isDayPillar && (
                                <span
                                    className="mt-1 text-xs font-semibold"
                                    style={{ color: dayMasterColor }}
                                >
                                    Day Master
                                </span>
                            )}
                        </motion.div>
                    );
                })}
            </motion.div>

            {/* Day master summary */}
            <div className="mt-3 text-center text-sm text-slate-400">
                Day Master:{' '}
                <span
                    className="font-semibold"
                    style={{ color: dayMasterColor }}
                >
                    {data.dayMaster}
                </span>
                <span className="mx-1">·</span>
                <ElementBadge element={data.dayMasterElement} />
                {data.birthTimeUnknown && (
                    <span className="ml-2 text-xs text-slate-500">
                        (birth time unknown)
                    </span>
                )}
            </div>
        </div>
    );
}
