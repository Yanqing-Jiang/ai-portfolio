/**
 * CurrentCycleBanner — Prominent display of current luck pillar + annual pillar.
 *
 * Shows at the top of the Life Map tab: "Where am I now?" before
 * the user scrolls through the full timeline.
 *
 * Data: reads from dataModel at /data/luckPillars and /data/annualPillars
 */

import { useMemo } from 'react';
import { motion } from 'framer-motion';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LuckPillar {
    index: number;
    startAge: number;
    endAge: number;
    stem: string;
    branch: string;
    stemElement: string;
    branchElement: string;
    startYear: number;
    endYear: number;
}

interface AnnualPillar {
    year: number;
    stem: string;
    branch: string;
    stemElement: string;
    branchElement: string;
    interactions: { type: string; between: string[]; description: string }[];
    luckPillarIndex: number;
}

const ELEMENT_COLORS: Record<string, string> = {
    wood: '#22c55e', fire: '#ef4444', earth: '#d97706',
    metal: '#d4d4d8', water: '#3b82f6',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface CurrentCycleBannerProps {
    dataModel: Record<string, unknown>;
}

export function CurrentCycleBanner({ dataModel }: CurrentCycleBannerProps) {
    const currentYear = new Date().getFullYear();

    const { currentLuckPillar, currentAnnualPillar, yearInCycle, cycleLength } = useMemo(() => {
        const luckPillars = dataModel.luckPillars as { items?: LuckPillar[] } | undefined;
        const annualPillars = dataModel.annualPillars as { items?: AnnualPillar[] } | undefined;

        const lp = luckPillars?.items?.find(
            (p) => p.startYear <= currentYear && p.endYear >= currentYear
        ) || null;

        const ap = annualPillars?.items?.find((p) => p.year === currentYear) || null;

        const yearInCy = lp ? currentYear - lp.startYear + 1 : 0;
        const cycleLen = lp ? lp.endYear - lp.startYear + 1 : 10;

        return { currentLuckPillar: lp, currentAnnualPillar: ap, yearInCycle: yearInCy, cycleLength: cycleLen };
    }, [dataModel, currentYear]);

    if (!currentLuckPillar && !currentAnnualPillar) return null;

    const lpColor = currentLuckPillar
        ? ELEMENT_COLORS[currentLuckPillar.stemElement?.toLowerCase()] || '#94a3b8'
        : '#94a3b8';
    const apColor = currentAnnualPillar
        ? ELEMENT_COLORS[currentAnnualPillar.stemElement?.toLowerCase()] || '#94a3b8'
        : '#94a3b8';

    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 200, damping: 22 }}
            className="rounded-xl border p-4 mb-4"
            style={{
                background: 'rgba(148, 163, 184, 0.04)',
                borderColor: 'rgba(148, 163, 184, 0.12)',
            }}
        >
            <div className="flex items-center gap-4 sm:gap-6">
                {/* Luck Pillar (Decade) */}
                {currentLuckPillar && (
                    <div className="flex-1 text-center">
                        <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
                            Current Cycle
                        </div>
                        <div
                            className="text-2xl font-bold"
                            style={{ fontFamily: 'var(--ming-font-chinese)', color: lpColor }}
                        >
                            {currentLuckPillar.stem}{currentLuckPillar.branch}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                            {currentLuckPillar.startYear}–{currentLuckPillar.endYear}
                        </div>
                        {/* Progress bar */}
                        <div className="mt-2 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${(yearInCycle / cycleLength) * 100}%` }}
                                transition={{ duration: 0.8, ease: 'easeOut' }}
                                className="h-full rounded-full"
                                style={{ backgroundColor: lpColor }}
                            />
                        </div>
                        <div className="text-[10px] text-slate-600 mt-1">
                            Year {yearInCycle} of {cycleLength}
                        </div>
                    </div>
                )}

                {/* Divider */}
                {currentLuckPillar && currentAnnualPillar && (
                    <div className="h-12 w-px bg-slate-700/50" />
                )}

                {/* Annual Pillar (This Year) */}
                {currentAnnualPillar && (
                    <div className="flex-1 text-center">
                        <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
                            This Year
                        </div>
                        <div
                            className="text-2xl font-bold"
                            style={{ fontFamily: 'var(--ming-font-chinese)', color: apColor }}
                        >
                            {currentAnnualPillar.stem}{currentAnnualPillar.branch}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                            {currentYear}
                        </div>
                        {/* Interaction count */}
                        {currentAnnualPillar.interactions.length > 0 && (
                            <div className="mt-2 text-[10px] font-medium" style={{ color: apColor }}>
                                {currentAnnualPillar.interactions.length} interaction{currentAnnualPillar.interactions.length > 1 ? 's' : ''} with your chart
                            </div>
                        )}
                    </div>
                )}
            </div>
        </motion.div>
    );
}
