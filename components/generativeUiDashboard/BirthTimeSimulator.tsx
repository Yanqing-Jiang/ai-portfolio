/**
 * BirthTimeSimulator — "What if my birth time were different?" modal.
 *
 * Triggers on demand (a button on the result page, most useful when
 * `birth_time_unknown=true`). Hits POST /api/fortune/:id/simulate which
 * returns the deterministic BaZi foundation for all 12 Earthly Branch hour
 * hypotheses plus an aggregate stability report.
 *
 * Rendering strategy:
 *
 * 1. Top banner: stability headline. Shows "Day master stable (11/12)" or
 *    "Dominant element wavers: metal 8 / fire 2 / earth 2". This is the
 *    actual payoff of the simulator — confidence signals on the claims
 *    the narrative made.
 *
 * 2. Grid of 12 branch cards. Each card shows the hour-pillar stems, the
 *    dominant element for that hypothesis, and a mini element-bar. Cards
 *    for branches that *match the aggregate modal* are highlighted so the
 *    user can quickly see which hours produce "the typical" reading.
 *
 * No action/commit affordance yet — the user picks their birth time in the
 * initial form. The simulator is inspection-only for v1.
 */

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    fortuneClient,
    FortuneApiError,
    type SimulatorResponse,
    type SimulatorBranch,
    type SimulatorStability,
} from './lib/fortuneClient';

const ELEMENT_COLORS: Record<string, string> = {
    wood: '#22c55e',
    fire: '#ef4444',
    earth: '#f59e0b',
    metal: '#94a3b8',
    water: '#38bdf8',
};

interface Props {
    open: boolean;
    fortuneId: string | null;
    onClose: () => void;
}

export const BirthTimeSimulator: React.FC<Props> = ({ open, fortuneId, onClose }) => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<SimulatorResponse | null>(null);
    const closeBtnRef = useRef<HTMLButtonElement>(null);
    // Remember what had focus when the modal opened, restore on close.
    const opener = useRef<HTMLElement | null>(null);

    useEffect(() => {
        if (!open || !fortuneId) return;
        let cancelled = false;
        const controller = new AbortController();
        setLoading(true);
        setError(null);
        setData(null);
        fortuneClient
            .simulateBirthTime(fortuneId, { signal: controller.signal })
            .then((res) => {
                if (!cancelled) setData(res);
            })
            .catch((err) => {
                if (cancelled || controller.signal.aborted) return;
                setError(
                    err instanceof FortuneApiError
                        ? err.message
                        : 'Simulation failed. Try again.',
                );
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
            controller.abort();
        };
    }, [open, fortuneId]);

    // Focus management: remember opener, move focus into dialog, restore on close.
    useEffect(() => {
        if (open) {
            opener.current = (document.activeElement as HTMLElement) ?? null;
            // Wait for the dialog to mount before moving focus.
            const id = window.requestAnimationFrame(() => closeBtnRef.current?.focus());
            return () => window.cancelAnimationFrame(id);
        }
        // On close: restore focus if it's still reachable in the DOM.
        opener.current?.focus?.();
    }, [open]);

    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [open, onClose]);

    return (
        <AnimatePresence>
            {open && (
                <>
                    <motion.div
                        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
                        onClick={onClose}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                    />
                    <motion.div
                        role="dialog"
                        aria-modal="true"
                        aria-label="Birth-time uncertainty simulator"
                        className="fixed inset-0 z-50 flex items-center justify-center p-4"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                    >
                        <motion.div
                            className="relative max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 text-slate-200 shadow-2xl"
                            initial={{ scale: 0.96, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            exit={{ scale: 0.96, y: 20 }}
                            transition={{ type: 'spring', stiffness: 260, damping: 28 }}
                            onClick={(e) => e.stopPropagation()}
                        >
                            <header className="flex items-start justify-between border-b border-slate-800 px-5 py-4">
                                <div>
                                    <h2 className="text-lg font-semibold text-amber-300">
                                        Birth-Time Uncertainty
                                    </h2>
                                    <p className="mt-0.5 text-xs text-slate-400">
                                        Same date, 12 candidate hour pillars. Which claims are
                                        robust, and which flip with the birth hour?
                                    </p>
                                </div>
                                <button
                                    ref={closeBtnRef}
                                    type="button"
                                    onClick={onClose}
                                    className="rounded px-2 py-1 text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/40"
                                    aria-label="Close simulator"
                                >
                                    ✕
                                </button>
                            </header>

                            <div className="max-h-[calc(90vh-64px)] overflow-y-auto p-5">
                                {loading && (
                                    <div className="py-12 text-center text-sm text-slate-400">
                                        Running 12 foundation computations…
                                    </div>
                                )}
                                {error && !loading && (
                                    <div className="rounded border border-rose-900/60 bg-rose-950/30 p-4 text-sm text-rose-200">
                                        {error}
                                    </div>
                                )}
                                {data && !loading && !error && (
                                    <SimulatorBody data={data} />
                                )}
                            </div>
                        </motion.div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
};

// ---------------------------------------------------------------------------
// Body
// ---------------------------------------------------------------------------

function SimulatorBody({ data }: { data: SimulatorResponse }) {
    const { branches, stability } = data;

    return (
        <div className="space-y-5">
            {data.partial && (
                <div
                    role="status"
                    className="rounded border border-amber-800/60 bg-amber-950/20 px-3 py-2 text-xs text-amber-200"
                >
                    Partial simulation: {data.completedBranches} of{' '}
                    {data.expectedBranches} branches completed.
                    {data.failedBranches.length > 0 && (
                        <> Failed: {data.failedBranches.join(' · ')}.</>
                    )}{' '}
                    Stability below is computed over the completed set only.
                </div>
            )}
            {stability && <StabilityHeader stability={stability} />}

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                {branches.map((b) => (
                    <BranchCard
                        key={b.branch}
                        branch={b}
                        modalElement={stability?.dominantElement.value}
                    />
                ))}
            </div>
        </div>
    );
}

function StabilityHeader({ stability }: { stability: SimulatorStability }) {
    const confidencePct = (x: { count: number; total: number }) =>
        x.total > 0 ? Math.round((x.count / x.total) * 100) : 0;

    return (
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Stability across 12 hour hypotheses
            </h3>
            <div className="grid gap-3 sm:grid-cols-3">
                <StabilityRow
                    label="Day master"
                    value={stability.dayMaster.value}
                    confidence={confidencePct(stability.dayMaster)}
                    counts={stability.dayMaster}
                />
                <StabilityRow
                    label="Dominant element"
                    value={stability.dominantElement.value}
                    confidence={confidencePct(stability.dominantElement)}
                    counts={stability.dominantElement}
                    elementTint
                />
                <StabilityRow
                    label="Seasonal strength"
                    value={stability.seasonalStrength.value}
                    confidence={confidencePct(stability.seasonalStrength)}
                    counts={stability.seasonalStrength}
                />
            </div>
        </div>
    );
}

function StabilityRow({
    label,
    value,
    confidence,
    counts,
    elementTint = false,
}: {
    label: string;
    value: string;
    confidence: number;
    counts: { count: number; total: number; distribution: Record<string, number> };
    elementTint?: boolean;
}) {
    const barColor =
        confidence >= 85
            ? 'bg-emerald-400'
            : confidence >= 60
            ? 'bg-amber-400'
            : 'bg-rose-400';
    const tint = elementTint ? ELEMENT_COLORS[value] : undefined;

    return (
        <div>
            <div className="flex items-baseline justify-between gap-2">
                <span className="text-[11px] uppercase tracking-wide text-slate-500">
                    {label}
                </span>
                <span className="text-[11px] text-slate-400">
                    {counts.count}/{counts.total}
                </span>
            </div>
            <div
                className="mt-1 truncate text-sm font-medium"
                style={{ color: tint ?? '#e2e8f0' }}
            >
                {value}
            </div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-800">
                <div
                    className={`h-full ${barColor}`}
                    style={{ width: `${confidence}%` }}
                    aria-label={`${confidence}% confidence`}
                />
            </div>
            {Object.keys(counts.distribution).length > 1 && (
                <div className="mt-1 text-[10px] text-slate-500">
                    {Object.entries(counts.distribution)
                        .map(([k, v]) => `${k} ${v}`)
                        .join(' · ')}
                </div>
            )}
        </div>
    );
}

function BranchCard({
    branch,
    modalElement,
}: {
    branch: SimulatorBranch;
    modalElement?: string;
}) {
    const isModal = branch.dominantElement === modalElement;
    const elementColor = ELEMENT_COLORS[branch.dominantElement] ?? '#94a3b8';
    const total = Object.values(branch.enhancedElementCounts).reduce(
        (a, b) => a + b,
        0,
    );

    return (
        <div
            className={`rounded-lg border p-3 transition-colors ${
                isModal
                    ? 'border-emerald-800/60 bg-emerald-950/20'
                    : 'border-slate-800 bg-slate-900/40'
            }`}
        >
            <div className="flex items-baseline justify-between">
                <div className="flex items-baseline gap-1">
                    <span className="text-lg leading-none" style={{ fontFamily: 'serif' }}>
                        {branch.branch}
                    </span>
                    <span className="text-[11px] text-slate-500">{branch.window}</span>
                </div>
                {isModal && (
                    <span className="text-[10px] uppercase tracking-wide text-emerald-400">
                        typical
                    </span>
                )}
            </div>

            {branch.hourPillarStem && (
                <div className="mt-1 font-mono text-xs text-slate-400">
                    {branch.hourPillarStem}
                    {branch.hourPillarBranch}
                </div>
            )}

            <div className="mt-2 flex items-baseline gap-1">
                <span
                    className="text-sm font-semibold capitalize"
                    style={{ color: elementColor }}
                >
                    {branch.dominantElement}
                </span>
                <span className="text-[10px] text-slate-500">
                    · {branch.seasonalStrength}
                </span>
            </div>

            {/* Mini element bar */}
            <div className="mt-2 flex h-1.5 overflow-hidden rounded-full bg-slate-800">
                {(['wood', 'fire', 'earth', 'metal', 'water'] as const).map((el) => {
                    const val = branch.enhancedElementCounts[el] ?? 0;
                    const pct = total > 0 ? (val / total) * 100 : 0;
                    return (
                        <div
                            key={el}
                            style={{
                                width: `${pct}%`,
                                background: ELEMENT_COLORS[el],
                            }}
                            title={`${el}: ${val.toFixed(1)}`}
                        />
                    );
                })}
            </div>
        </div>
    );
}
