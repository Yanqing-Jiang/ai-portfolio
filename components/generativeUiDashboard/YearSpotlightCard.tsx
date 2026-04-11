/**
 * YearSpotlightCard — Hero card for the current year's annual pillar.
 *
 * Shows this year's BaZi forecast prominently with element colors,
 * interaction badges (clash/combination/harm), LLM prediction text,
 * and a valence indicator (favorable/challenging/neutral).
 *
 * Data: reads from dataModel at /data/annualPillars and /data/narrative
 */

import { useMemo } from 'react';
import { motion } from 'framer-motion';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AnnualInteraction {
    type: string;
    between: string[];
    description: string;
}

interface AnnualPillar {
    year: number;
    stem: string;
    branch: string;
    stemElement: string;
    branchElement: string;
    interactions: AnnualInteraction[];
    luckPillarIndex: number;
}

interface YearPrediction {
    year: number;
    prediction: string;
    confidence: number;
    evidence_refs: string[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ELEMENT_COLORS: Record<string, string> = {
    wood: '#22c55e', fire: '#ef4444', earth: '#d97706',
    metal: '#d4d4d8', water: '#3b82f6',
};

const VALENCE_MAP: Record<string, { label: string; color: string; icon: string }> = {
    clash: { label: 'Tension & Change', color: '#ef4444', icon: '\u26A1' },
    combination: { label: 'Harmonious Alignment', color: '#22c55e', icon: '\uD83E\uDD1D' },
    harm: { label: 'Hidden Challenge', color: '#eab308', icon: '\u26A0\uFE0F' },
    punishment: { label: 'Growth Through Difficulty', color: '#f97316', icon: '\uD83D\uDD25' },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface YearSpotlightCardProps {
    dataModel: Record<string, unknown>;
}

export function YearSpotlightCard({ dataModel }: YearSpotlightCardProps) {
    const currentYear = new Date().getFullYear();

    const { thisYear, prediction, dominantInteraction } = useMemo(() => {
        const annualPillars = dataModel.annualPillars as { items?: AnnualPillar[] } | undefined;
        const narrative = dataModel.narrative as { yearPredictions?: YearPrediction[] } | undefined;

        const ap = annualPillars?.items?.find((p) => p.year === currentYear) || null;
        const pred = narrative?.yearPredictions?.find((p) => p.year === currentYear) || null;

        // Find the most significant interaction for valence
        const dominant = ap?.interactions?.[0] || null;

        return { thisYear: ap, prediction: pred, dominantInteraction: dominant };
    }, [dataModel, currentYear]);

    if (!thisYear) return null;

    const elementColor = ELEMENT_COLORS[thisYear.stemElement?.toLowerCase()] || '#94a3b8';
    const valence = dominantInteraction
        ? VALENCE_MAP[dominantInteraction.type] || VALENCE_MAP.clash
        : null;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 200, damping: 22 }}
            className="rounded-2xl border p-5 sm:p-6"
            style={{
                background: `radial-gradient(ellipse at 50% 0%, ${elementColor}08 0%, transparent 70%), rgba(148, 163, 184, 0.04)`,
                borderColor: `${elementColor}25`,
            }}
        >
            {/* Year header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <span
                        className="text-3xl font-bold"
                        style={{ color: elementColor, fontFamily: 'var(--ming-font-chinese)' }}
                    >
                        {thisYear.stem}{thisYear.branch}
                    </span>
                    <div>
                        <div className="text-lg font-bold text-slate-200">{currentYear}</div>
                        <div className="text-xs text-slate-500">Annual Pillar</div>
                    </div>
                </div>

                {/* Valence badge */}
                {valence && (
                    <span
                        className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold"
                        style={{
                            color: valence.color,
                            backgroundColor: `${valence.color}12`,
                            border: `1px solid ${valence.color}25`,
                        }}
                    >
                        <span>{valence.icon}</span>
                        {valence.label}
                    </span>
                )}
            </div>

            {/* Prediction text */}
            {prediction && (
                <p className="text-sm leading-relaxed text-slate-300 mb-4">
                    {prediction.prediction}
                </p>
            )}

            {/* Interaction details */}
            {thisYear.interactions.length > 0 && (
                <div className="flex flex-wrap gap-2">
                    {thisYear.interactions.map((ix, i) => {
                        const v = VALENCE_MAP[ix.type] || VALENCE_MAP.clash;
                        return (
                            <span
                                key={i}
                                className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-[11px]"
                                style={{
                                    color: v.color,
                                    backgroundColor: `${v.color}0a`,
                                    border: `1px solid ${v.color}15`,
                                }}
                            >
                                <span>{v.icon}</span>
                                {ix.description}
                            </span>
                        );
                    })}
                </div>
            )}

            {/* Confidence meter */}
            {prediction && (
                <div className="mt-4 flex items-center gap-2">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider">Confidence</span>
                    <div className="flex gap-0.5">
                        {[1, 2, 3, 4, 5].map((level) => (
                            <div
                                key={level}
                                className="h-2 w-3 rounded-sm"
                                style={{
                                    backgroundColor: level <= Math.round(prediction.confidence * 5)
                                        ? elementColor
                                        : 'rgba(148, 163, 184, 0.15)',
                                }}
                            />
                        ))}
                    </div>
                </div>
            )}
        </motion.div>
    );
}

// ---------------------------------------------------------------------------
// UpcomingYearsSwim — Horizontal scrollable year forecast cards
// ---------------------------------------------------------------------------

interface UpcomingYearsSwimProps {
    dataModel: Record<string, unknown>;
}

export function UpcomingYearsSwim({ dataModel }: UpcomingYearsSwimProps) {
    const currentYear = new Date().getFullYear();

    const upcomingYears = useMemo(() => {
        const annualPillars = dataModel.annualPillars as { items?: AnnualPillar[] } | undefined;
        const narrative = dataModel.narrative as { yearPredictions?: YearPrediction[] } | undefined;

        if (!annualPillars?.items) return [];

        return annualPillars.items
            .filter((ap) => ap.year > currentYear && ap.year <= currentYear + 5)
            .map((ap) => {
                const pred = narrative?.yearPredictions?.find((p) => p.year === ap.year);
                const dominant = ap.interactions?.[0];
                return { ...ap, prediction: pred, dominantInteraction: dominant };
            });
    }, [dataModel, currentYear]);

    if (upcomingYears.length === 0) return null;

    return (
        <div className="mt-5">
            <h3 className="text-sm font-medium text-slate-400 mb-3">Upcoming Years</h3>
            <div
                className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide"
                style={{ WebkitOverflowScrolling: 'touch', scrollSnapType: 'x mandatory' }}
            >
                {upcomingYears.map((year, i) => {
                    const color = ELEMENT_COLORS[year.stemElement?.toLowerCase()] || '#94a3b8';
                    const valence = year.dominantInteraction
                        ? VALENCE_MAP[year.dominantInteraction.type]
                        : null;

                    return (
                        <motion.div
                            key={year.year}
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.08 }}
                            className="flex-shrink-0 rounded-xl border p-3.5"
                            style={{
                                width: 160,
                                scrollSnapAlign: 'start',
                                background: 'rgba(148, 163, 184, 0.04)',
                                borderColor: valence ? `${valence.color}20` : 'rgba(148, 163, 184, 0.12)',
                            }}
                        >
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-base font-bold text-slate-200">{year.year}</span>
                                <span
                                    className="text-lg"
                                    style={{ fontFamily: 'var(--ming-font-chinese)', color }}
                                >
                                    {year.stem}{year.branch}
                                </span>
                            </div>

                            {valence && (
                                <span
                                    className="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium mb-2"
                                    style={{ color: valence.color, backgroundColor: `${valence.color}12` }}
                                >
                                    {valence.icon} {valence.label}
                                </span>
                            )}

                            {year.prediction && (
                                <p className="text-[11px] leading-relaxed text-slate-400 line-clamp-3">
                                    {year.prediction.prediction}
                                </p>
                            )}

                            {!year.prediction && !valence && (
                                <p className="text-[11px] text-slate-500">Steady year</p>
                            )}
                        </motion.div>
                    );
                })}
            </div>
        </div>
    );
}
