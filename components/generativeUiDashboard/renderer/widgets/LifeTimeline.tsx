/**
 * LifeTimeline -- Vertical year-by-year timeline with luck pillar decade
 * markers, expandable year cards, prediction text, and user corrections.
 *
 * Data paths:
 *   /data/luckPillars    - decade-level pillars
 *   /data/annualPillars  - per-year stem/branch + interactions
 *   /data/narrative       - yearPredictions from LLM
 *   /data/corrections     - user corrections
 *
 * Built with React + framer-motion (not ECharts) for rich expand/collapse
 * interaction with inline forms.
 */

import React, { useState, useMemo, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';
import { configService } from '../../../../services/config';
import { authService } from '../../../../services/auth';

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

interface Correction {
    user_note: string;
    corrected_at: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ELEMENT_COLORS: Record<string, string> = {
    wood: '#22c55e',
    fire: '#ef4444',
    earth: '#d97706',
    metal: '#a1a1aa',
    water: '#3b82f6',
};

const INTERACTION_DOTS: Record<string, { color: string; label: string }> = {
    clash: { color: '#ef4444', label: '\u51b2' },
    combination: { color: '#22c55e', label: '\u5408' },
    harm: { color: '#eab308', label: '\u5bb3' },
    punishment: { color: '#f97316', label: '\u5211' },
};

function getYearColor(interactions: AnnualInteraction[]): string {
    if (interactions.length === 0) return '#334155'; // neutral gray
    const hasClash = interactions.some((i) => i.type === 'clash');
    const hasCombine = interactions.some((i) => i.type === 'combination');
    if (hasClash && hasCombine) return '#d97706'; // amber
    if (hasClash) return '#ef4444'; // red
    if (hasCombine) return '#22c55e'; // green
    return '#eab308'; // yellow for harm/punishment
}

// ---------------------------------------------------------------------------
// Year Card (expandable)
// ---------------------------------------------------------------------------

interface YearCardProps {
    ap: AnnualPillar;
    prediction?: YearPrediction;
    correction?: Correction;
    isCurrentYear: boolean;
    fortuneId?: string;
    onCorrectionSubmit?: (year: number, note: string) => void;
}

function YearCard({
    ap,
    prediction,
    correction,
    isCurrentYear,
    onCorrectionSubmit,
}: YearCardProps) {
    const [expanded, setExpanded] = useState(false);
    const [correcting, setCorrecting] = useState(false);
    const [correctionText, setCorrectionText] = useState('');

    const yearColor = getYearColor(ap.interactions);
    const hasPrediction = prediction && prediction.prediction;

    return (
        <div className="relative flex gap-3">
            {/* Timeline dot */}
            <div className="flex flex-col items-center">
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full border-2 text-xs font-bold transition-all hover:scale-110"
                    style={{
                        borderColor: yearColor,
                        backgroundColor: expanded ? yearColor : 'transparent',
                        color: expanded ? '#fff' : yearColor,
                    }}
                >
                    {ap.interactions.length > 0
                        ? ap.interactions.map((ix) => INTERACTION_DOTS[ix.type]?.label || '').join('')
                        : '\u00B7'}
                </button>
                {isCurrentYear && (
                    <span className="mt-0.5 h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--ming-accent)]" />
                )}
            </div>

            {/* Year label + content */}
            <div className="flex-1 pb-4">
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="flex items-center gap-2 text-left"
                >
                    <span
                        className="text-sm font-semibold"
                        style={{ color: isCurrentYear ? 'var(--ming-gold)' : '#e2e8f0' }}
                    >
                        {ap.year}
                    </span>
                    <span
                        className="text-base"
                        style={{ fontFamily: 'var(--ming-font-chinese)', color: ELEMENT_COLORS[ap.stemElement] || '#94a3b8' }}
                    >
                        {ap.stem}{ap.branch}
                    </span>
                    {ap.interactions.length > 0 && (
                        <span className="flex gap-0.5">
                            {ap.interactions.map((ix, i) => (
                                <span
                                    key={i}
                                    className="rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                                    style={{
                                        backgroundColor: `${INTERACTION_DOTS[ix.type]?.color || '#64748b'}20`,
                                        color: INTERACTION_DOTS[ix.type]?.color || '#64748b',
                                    }}
                                >
                                    {ix.type}
                                </span>
                            ))}
                        </span>
                    )}
                    <span className="text-xs text-slate-600">
                        {expanded ? '\u25B2' : '\u25BC'}
                    </span>
                </button>

                <AnimatePresence>
                    {expanded && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.2 }}
                            className="mt-2 overflow-hidden"
                        >
                            <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-3 space-y-2">
                                {/* Pillar details */}
                                <div className="flex items-center gap-3 text-xs text-slate-400">
                                    <span>
                                        Stem: <span style={{ color: ELEMENT_COLORS[ap.stemElement] }}>{ap.stem} ({ap.stemElement})</span>
                                    </span>
                                    <span>
                                        Branch: <span style={{ color: ELEMENT_COLORS[ap.branchElement] }}>{ap.branch} ({ap.branchElement})</span>
                                    </span>
                                </div>

                                {/* Interactions */}
                                {ap.interactions.length > 0 && (
                                    <div className="space-y-1">
                                        {ap.interactions.map((ix, i) => (
                                            <p key={i} className="text-xs" style={{ color: INTERACTION_DOTS[ix.type]?.color || '#94a3b8' }}>
                                                {ix.description}
                                            </p>
                                        ))}
                                    </div>
                                )}

                                {/* Prediction */}
                                {hasPrediction && (
                                    <div className="rounded-md bg-slate-700/30 p-2">
                                        <p className="text-sm text-slate-200">
                                            {correction ? (
                                                <span className="line-through opacity-50">{prediction!.prediction}</span>
                                            ) : (
                                                prediction!.prediction
                                            )}
                                        </p>
                                        {prediction!.confidence > 0 && (
                                            <span className="mt-1 inline-block rounded-full bg-slate-700/50 px-2 py-0.5 text-[10px] text-slate-400">
                                                confidence: {(prediction!.confidence * 100).toFixed(0)}%
                                            </span>
                                        )}
                                    </div>
                                )}

                                {/* User correction */}
                                {correction && (
                                    <div className="rounded-md border border-amber-800/30 bg-amber-950/20 p-2">
                                        <p className="text-xs font-medium text-amber-400">Your correction:</p>
                                        <p className="text-sm text-amber-200">{correction.user_note}</p>
                                    </div>
                                )}

                                {/* Correct button / form */}
                                {!correction && !correcting && (
                                    <button
                                        onClick={() => setCorrecting(true)}
                                        className="text-xs text-slate-500 hover:text-slate-400 transition-colors"
                                    >
                                        Correct this prediction
                                    </button>
                                )}

                                {correcting && (
                                    <div className="space-y-2">
                                        <textarea
                                            value={correctionText}
                                            onChange={(e) => setCorrectionText(e.target.value)}
                                            placeholder="What actually happened this year?"
                                            rows={2}
                                            className="w-full rounded-md border border-slate-700 bg-slate-800/50 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-amber-600 focus:outline-none"
                                        />
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => {
                                                    if (correctionText.trim() && onCorrectionSubmit) {
                                                        onCorrectionSubmit(ap.year, correctionText.trim());
                                                        setCorrecting(false);
                                                        setCorrectionText('');
                                                    }
                                                }}
                                                disabled={!correctionText.trim()}
                                                className="rounded-md bg-amber-700/80 px-3 py-1 text-xs font-medium text-white disabled:opacity-40"
                                            >
                                                Submit
                                            </button>
                                            <button
                                                onClick={() => { setCorrecting(false); setCorrectionText(''); }}
                                                className="rounded-md px-3 py-1 text-xs text-slate-400 hover:text-slate-300"
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Timeline Component
// ---------------------------------------------------------------------------

export function LifeTimeline({
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement | null {
    const luckPillarsPath = props.luckPillarsPath as BoundValue | undefined;
    const annualPillarsPath = props.annualPillarsPath as BoundValue | undefined;
    const narrativePath = props.narrativePath as BoundValue | undefined;
    const correctionsPath = props.correctionsPath as BoundValue | undefined;

    const rawLP = luckPillarsPath ? resolveBoundValue(luckPillarsPath, dataModel) : null;
    const rawAP = annualPillarsPath ? resolveBoundValue(annualPillarsPath, dataModel) : null;
    const rawNarrative = narrativePath ? resolveBoundValue(narrativePath, dataModel) : null;
    const rawCorrections = correctionsPath ? resolveBoundValue(correctionsPath, dataModel) : null;

    const luckPillars = useMemo<LuckPillar[]>(() => {
        if (!rawLP) return [];
        const items = (rawLP as any)?.items ?? rawLP;
        return Array.isArray(items) ? items : [];
    }, [rawLP]);

    const annualPillars = useMemo<AnnualPillar[]>(() => {
        if (!rawAP) return [];
        const items = (rawAP as any)?.items ?? rawAP;
        return Array.isArray(items) ? items : [];
    }, [rawAP]);

    const predictions = useMemo<Map<number, YearPrediction>>(() => {
        const map = new Map<number, YearPrediction>();
        const yps = (rawNarrative as any)?.yearPredictions ?? (rawNarrative as any)?.year_predictions;
        if (Array.isArray(yps)) {
            for (const yp of yps) map.set(yp.year, yp);
        }
        return map;
    }, [rawNarrative]);

    const [localCorrections, setLocalCorrections] = useState<Record<number, Correction>>({});

    const corrections = useMemo<Record<number, Correction>>(() => {
        const base = (rawCorrections && typeof rawCorrections === 'object')
            ? rawCorrections as Record<number, Correction>
            : {};
        return { ...base, ...localCorrections };
    }, [rawCorrections, localCorrections]);

    // Fortune ID from URL (simplified extraction)
    const fortuneIdRef = useRef<string | null>(null);

    const handleCorrectionSubmit = useCallback(async (year: number, note: string) => {
        // Optimistically update local state
        setLocalCorrections((prev) => ({
            ...prev,
            [year]: { user_note: note, corrected_at: new Date().toISOString() },
        }));

        // Fire-and-forget API call
        try {
            const backendUrl = configService.getBackendUrl();
            const authHeaders = await authService.getAuthHeaders();
            // Extract fortune ID from the page URL
            const fortuneId = fortuneIdRef.current || window.location.pathname.split('/').pop();
            await fetch(`${backendUrl}/api/fortune/${fortuneId}/correction`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeaders },
                body: JSON.stringify({ year, user_note: note }),
            });
        } catch {
            // Correction is already saved locally
        }
    }, []);

    const currentYear = new Date().getFullYear();

    // Show recent + upcoming years (past 10 to future 20)
    const visiblePillars = useMemo(() => {
        return annualPillars.filter(
            (ap) => ap.year >= currentYear - 10 && ap.year <= currentYear + 20,
        );
    }, [annualPillars, currentYear]);

    // Group by luck pillar decade
    const decades = useMemo(() => {
        const map = new Map<number, { lp: LuckPillar | null; years: AnnualPillar[] }>();
        for (const ap of visiblePillars) {
            const lpIdx = ap.luckPillarIndex;
            if (!map.has(lpIdx)) {
                const lp = luckPillars.find((l) => l.index === lpIdx) ?? null;
                map.set(lpIdx, { lp, years: [] });
            }
            map.get(lpIdx)!.years.push(ap);
        }
        return Array.from(map.values());
    }, [visiblePillars, luckPillars]);

    if (annualPillars.length === 0) {
        return (
            <div className="h-32 animate-pulse rounded-lg bg-slate-800/30" />
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-2">
                <span className="text-base font-semibold text-slate-200">
                    Life Timeline
                </span>
                <span className="text-xs text-slate-500">
                    ({visiblePillars.length} years | click to expand)
                </span>
            </div>

            <div className="space-y-6">
                {decades.map((decade, dIdx) => (
                    <div key={dIdx} className="relative">
                        {/* Luck pillar decade header */}
                        {decade.lp && (
                            <div className="mb-3 flex items-center gap-2">
                                <div
                                    className="rounded-md px-2.5 py-1 text-sm font-semibold"
                                    style={{
                                        backgroundColor: `${ELEMENT_COLORS[decade.lp.stemElement]}15`,
                                        color: ELEMENT_COLORS[decade.lp.stemElement],
                                        border: `1px solid ${ELEMENT_COLORS[decade.lp.stemElement]}30`,
                                        fontFamily: 'var(--ming-font-chinese)',
                                    }}
                                >
                                    {decade.lp.stem}{decade.lp.branch}
                                </div>
                                <span className="text-xs text-slate-500">
                                    Age {decade.lp.startAge}-{decade.lp.endAge} | {decade.lp.startYear}-{decade.lp.endYear}
                                </span>
                            </div>
                        )}

                        {/* Vertical line */}
                        <div className="absolute left-[15px] top-10 bottom-0 w-px bg-slate-700/40" />

                        {/* Year cards */}
                        <div className="space-y-0">
                            {decade.years.map((ap) => (
                                <YearCard
                                    key={ap.year}
                                    ap={ap}
                                    prediction={predictions.get(ap.year)}
                                    correction={corrections[ap.year]}
                                    isCurrentYear={ap.year === currentYear}
                                    onCorrectionSubmit={handleCorrectionSubmit}
                                />
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
