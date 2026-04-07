/**
 * ElementBalanceRadar — Interactive Five Elements balance radar chart.
 *
 * Features:
 * - ECharts radar pentagon showing element scores (0-10 scale)
 * - Scroll-triggered animation (renders only when visible)
 * - Tappable element chips with detail tooltips
 * - Pulsing dominant element indicator
 * - Mobile-responsive layout
 *
 * Called from: ComponentRenderer.tsx via Registry
 * Data path: /data/elements (emitted by stream_bridge.emit_elements)
 */

import React, { useState, useMemo, useRef } from 'react';
import { motion, AnimatePresence, useInView } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';
import LazyECharts from '../../../shared/LazyECharts';

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

const ELEMENT_DESCRIPTIONS: Record<string, string> = {
    wood: 'Growth, creativity, and benevolence. Associated with spring, the liver, and the color green. Wood people are expansive and visionary.',
    fire: 'Passion, dynamism, and propriety. Associated with summer, the heart, and the color red. Fire people are charismatic and decisive.',
    earth: 'Stability, nourishment, and trust. Associated with late summer, the spleen, and the color yellow. Earth people are reliable and grounded.',
    metal: 'Precision, righteousness, and discipline. Associated with autumn, the lungs, and the color white. Metal people are principled and structured.',
    water: 'Wisdom, adaptability, and flow. Associated with winter, the kidneys, and the color black. Water people are intuitive and resourceful.',
};

interface ElementScore {
    element: string;
    score: number;
}

interface ElementBalanceData {
    scores: ElementScore[];
    dominant: string;
    weakest: string;
    summary: string;
}

export function ElementBalanceRadar({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const containerRef = useRef<HTMLDivElement>(null);
    const isInView = useInView(containerRef, { once: true, margin: '-50px' });
    const [selectedElement, setSelectedElement] = useState<string | null>(null);

    const data = resolveBoundValue(
        props.elementsPath as BoundValue | undefined,
        dataModel
    ) as ElementBalanceData | undefined;

    const option = useMemo(() => {
        if (!data?.scores?.length) return null;

        const dominantColor = ELEMENT_COLORS[data.dominant] || '#3b82f6';

        return {
            backgroundColor: 'transparent',
            radar: {
                indicator: data.scores.map((s) => ({
                    name: s.element.charAt(0).toUpperCase() + s.element.slice(1),
                    max: 10,
                })),
                axisName: {
                    color: '#94a3b8',
                    fontSize: 12,
                },
                splitArea: {
                    areaStyle: {
                        color: [
                            'rgba(148, 163, 184, 0.02)',
                            'rgba(148, 163, 184, 0.04)',
                        ],
                    },
                },
                splitLine: {
                    lineStyle: { color: 'rgba(148, 163, 184, 0.12)' },
                },
                axisLine: {
                    lineStyle: { color: 'rgba(148, 163, 184, 0.12)' },
                },
            },
            series: [
                {
                    type: 'radar',
                    data: [
                        {
                            value: data.scores.map((s) => s.score),
                            areaStyle: {
                                color: {
                                    type: 'radial',
                                    x: 0.5,
                                    y: 0.5,
                                    r: 0.6,
                                    colorStops: [
                                        { offset: 0, color: `${dominantColor}30` },
                                        { offset: 1, color: `${dominantColor}08` },
                                    ],
                                },
                            },
                            lineStyle: {
                                color: dominantColor,
                                width: 2,
                            },
                            itemStyle: {
                                color: dominantColor,
                            },
                            symbol: 'circle',
                            symbolSize: 6,
                        },
                    ],
                    animationEasing: 'elasticOut',
                    animationDuration: 1200,
                },
            ],
            tooltip: {
                trigger: 'item',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderColor: 'rgba(148, 163, 184, 0.2)',
                textStyle: { color: '#f8fafc', fontSize: 12 },
            },
        };
    }, [data]);

    if (!data || !option) {
        return <div data-component-id={componentId} />;
    }

    return (
        <motion.div
            ref={containerRef}
            data-component-id={componentId}
            className="w-full"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={isInView ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 200, damping: 25, mass: 0.8 }}
        >
            {/* Chart — only render when scrolled into view */}
            {isInView && (
                <LazyECharts
                    option={option}
                    theme="dark"
                    style={{ height: 'clamp(200px, 50vw, 320px)', width: '100%' }}
                    opts={{ renderer: 'svg' }}
                />
            )}

            {/* Interactive element chips */}
            <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
                {data.scores.map((s) => {
                    const color = ELEMENT_COLORS[s.element] || '#94a3b8';
                    const isDominant = s.element === data.dominant;
                    const isWeakest = s.element === data.weakest;
                    const isSelected = s.element === selectedElement;

                    return (
                        <motion.button
                            key={s.element}
                            className="relative inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium"
                            style={{
                                minHeight: '36px',
                                backgroundColor: isSelected ? `${color}40` : `${color}20`,
                                color,
                                border: isSelected
                                    ? `2px solid ${color}`
                                    : isDominant
                                        ? `1.5px solid ${color}`
                                        : isWeakest
                                            ? `1px dashed ${color}60`
                                            : `1px solid ${color}30`,
                                touchAction: 'manipulation',
                            }}
                            whileTap={{ scale: 0.9 }}
                            animate={isSelected ? { scale: 1.1 } : { scale: 1 }}
                            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                            onClick={() =>
                                setSelectedElement(
                                    selectedElement === s.element ? null : s.element
                                )
                            }
                        >
                            {/* Pulsing ring on dominant element */}
                            {isDominant && !isSelected && (
                                <motion.div
                                    className="absolute inset-0 rounded-full"
                                    style={{ border: `1.5px solid ${color}`, opacity: 0.5 }}
                                    animate={{
                                        scale: [1, 1.15, 1],
                                        opacity: [0.5, 0, 0.5],
                                    }}
                                    transition={{
                                        duration: 2,
                                        repeat: Infinity,
                                        ease: 'easeInOut',
                                    }}
                                />
                            )}
                            {ELEMENT_EMOJI[s.element] || ''} {s.element}
                            <span className="font-bold">{s.score}</span>
                            {isDominant && (
                                <span className="text-[9px] opacity-70">\u2605</span>
                            )}
                        </motion.button>
                    );
                })}
            </div>

            {/* Detail tooltip for selected element */}
            <AnimatePresence>
                {selectedElement && (
                    <motion.div
                        key={selectedElement}
                        initial={{ opacity: 0, y: -8, height: 0 }}
                        animate={{ opacity: 1, y: 0, height: 'auto' }}
                        exit={{ opacity: 0, y: -8, height: 0 }}
                        transition={{ duration: 0.2, ease: 'easeOut' }}
                        className="mt-2 overflow-hidden rounded-lg p-3 text-sm"
                        style={{
                            background: `${ELEMENT_COLORS[selectedElement]}10`,
                            border: `1px solid ${ELEMENT_COLORS[selectedElement]}30`,
                        }}
                    >
                        <p
                            className="font-medium capitalize"
                            style={{ color: ELEMENT_COLORS[selectedElement] }}
                        >
                            {ELEMENT_EMOJI[selectedElement] || ''}{' '}
                            {selectedElement} Element
                        </p>
                        <p className="mt-1 text-xs leading-relaxed text-slate-400">
                            {ELEMENT_DESCRIPTIONS[selectedElement] ||
                                'One of the five fundamental elements in BaZi astrology.'}
                        </p>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Summary */}
            {data.summary && (
                <p className="mt-2 text-center text-sm leading-relaxed text-slate-400">
                    {data.summary}
                </p>
            )}
        </motion.div>
    );
}
