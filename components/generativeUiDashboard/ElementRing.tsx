/**
 * ElementRing — Donut chart showing five-element balance.
 *
 * Replaces the radar pentagon with a more immediately readable
 * proportional arc visualization. Dominant element name in center.
 *
 * Data: reads from dataModel at /data/elementBySource
 */

import { useMemo } from 'react';
import { motion } from 'framer-motion';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ELEMENT_COLORS: Record<string, string> = {
    wood: '#22c55e',
    fire: '#ef4444',
    earth: '#d97706',
    metal: '#d4d4d8',
    water: '#3b82f6',
};

const ELEMENT_LABELS: Record<string, string> = {
    wood: '\u6728', fire: '\u706B', earth: '\u571F',
    metal: '\u91D1', water: '\u6C34',
};

const ELEMENT_ORDER = ['wood', 'fire', 'earth', 'metal', 'water'];

const SIZE = 200;
const STROKE_WIDTH = 24;
const RADIUS = (SIZE - STROKE_WIDTH) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const CENTER = SIZE / 2;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface ElementRingProps {
    dataModel: Record<string, unknown>;
}

export function ElementRing({ dataModel }: ElementRingProps) {
    const { segments, dominant } = useMemo(() => {
        const elementBySource = dataModel.elementBySource as Record<string, Record<string, number>> | undefined;

        if (!elementBySource) return { segments: [], dominant: null, total: 0 };

        // Aggregate scores per element across all sources (year, month, day, hour, hidden)
        const totals: Record<string, number> = {};
        for (const element of ELEMENT_ORDER) {
            let sum = 0;
            for (const source of Object.values(elementBySource)) {
                sum += source[element] || 0;
            }
            totals[element] = sum;
        }

        const grandTotal = Object.values(totals).reduce((a, b) => a + b, 0) || 1;

        // Build arc segments
        let offset = 0;
        const segs = ELEMENT_ORDER.map((el) => {
            const ratio = totals[el] / grandTotal;
            const dashLength = ratio * CIRCUMFERENCE;
            const seg = { element: el, ratio, dashLength, offset, score: totals[el] };
            offset += dashLength;
            return seg;
        });

        const dom = ELEMENT_ORDER.reduce((a, b) => (totals[a] >= totals[b] ? a : b));

        return { segments: segs, dominant: dom };
    }, [dataModel]);

    if (segments.length === 0) return null;

    const dominantColor = dominant ? ELEMENT_COLORS[dominant] : '#94a3b8';

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 22 }}
            className="flex flex-col items-center"
        >
            <div className="relative" style={{ width: SIZE, height: SIZE }}>
                <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
                    {/* Background ring */}
                    <circle
                        cx={CENTER}
                        cy={CENTER}
                        r={RADIUS}
                        fill="none"
                        stroke="rgba(148, 163, 184, 0.08)"
                        strokeWidth={STROKE_WIDTH}
                    />

                    {/* Element arcs */}
                    {segments.map((seg, i) => (
                        <motion.circle
                            key={seg.element}
                            cx={CENTER}
                            cy={CENTER}
                            r={RADIUS}
                            fill="none"
                            stroke={ELEMENT_COLORS[seg.element]}
                            strokeWidth={STROKE_WIDTH}
                            strokeDasharray={`${seg.dashLength} ${CIRCUMFERENCE - seg.dashLength}`}
                            strokeDashoffset={-seg.offset}
                            strokeLinecap="round"
                            transform={`rotate(-90 ${CENTER} ${CENTER})`}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 0.85 }}
                            transition={{ delay: i * 0.1 + 0.2, duration: 0.4 }}
                            style={{ filter: `drop-shadow(0 0 4px ${ELEMENT_COLORS[seg.element]}30)` }}
                        />
                    ))}
                </svg>

                {/* Center label — dominant element */}
                {dominant && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span
                            className="text-3xl leading-none"
                            style={{
                                fontFamily: 'var(--ming-font-chinese)',
                                color: dominantColor,
                                textShadow: `0 0 20px ${dominantColor}25`,
                            }}
                        >
                            {ELEMENT_LABELS[dominant]}
                        </span>
                        <span className="mt-1 text-[10px] uppercase tracking-wider text-slate-500">
                            dominant
                        </span>
                    </div>
                )}
            </div>

            {/* Legend */}
            <div className="mt-3 flex flex-wrap justify-center gap-x-4 gap-y-1">
                {segments.map((seg) => (
                    <div key={seg.element} className="flex items-center gap-1.5">
                        <div
                            className="h-2 w-2 rounded-full"
                            style={{ backgroundColor: ELEMENT_COLORS[seg.element] }}
                        />
                        <span className="text-[11px] text-slate-400">
                            {seg.element.charAt(0).toUpperCase() + seg.element.slice(1)}
                        </span>
                        <span className="text-[11px] font-mono text-slate-500">
                            {seg.score.toFixed(1)}
                        </span>
                    </div>
                ))}
            </div>
        </motion.div>
    );
}
