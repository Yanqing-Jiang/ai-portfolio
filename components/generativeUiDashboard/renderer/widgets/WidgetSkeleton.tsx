/**
 * WidgetSkeleton Component
 *
 * Provides shimmer loading placeholders for A2UI widgets during data fetching.
 * Called from: ComponentRenderer.tsx when widget data is loading
 * Called from: SwapDeckOverlay.tsx for preview empty state loading
 * Why: Creates premium loading experience with animated placeholders
 *
 * Variants:
 * - card: Generic card placeholder
 * - chart: MetricChart/PriceChart placeholder (16:9 aspect)
 * - table: DataTable placeholder with header + rows
 * - text: Text block placeholder
 * - kpi: Single KPI card placeholder
 * - kpi-grid: Multiple KPI cards in a grid (legacy)
 */

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

// --- Reduced Motion Support ---
function useReducedMotion(): boolean {
    const [prefersReduced, setPrefersReduced] = useState(false);

    useEffect(() => {
        if (typeof window === 'undefined') return;
        const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
        setPrefersReduced(mediaQuery.matches);
        const handler = (e: MediaQueryListEvent) => setPrefersReduced(e.matches);
        mediaQuery.addEventListener('change', handler);
        return () => mediaQuery.removeEventListener('change', handler);
    }, []);

    return prefersReduced;
}

const shimmerKeyframes = {
    initial: { backgroundPosition: '-200% 0' },
    animate: { backgroundPosition: '200% 0' },
};

const shimmerTransition = {
    duration: 1.5,
    repeat: Infinity,
    ease: 'linear' as const,
};

// Static fallback for reduced motion
const staticStyle: React.CSSProperties = {
    background: 'rgba(51, 65, 85, 0.5)',
    borderRadius: '8px',
};

const baseShimmerStyle: React.CSSProperties = {
    background: 'linear-gradient(90deg, rgba(30, 41, 59, 0.6) 25%, rgba(51, 65, 85, 0.8) 50%, rgba(30, 41, 59, 0.6) 75%)',
    backgroundSize: '200% 100%',
    borderRadius: '8px',
};

export type SkeletonVariant = 'card' | 'chart' | 'table' | 'text' | 'kpi' | 'kpi-grid';

interface SkeletonProps {
    variant?: SkeletonVariant;
    className?: string;
    /** Label for screen readers (default: "Loading...") */
    ariaLabel?: string;
}

/** Map component types to skeleton variants */
export const componentTypeToVariant: Record<string, SkeletonVariant> = {
    MetricChart: 'chart',
    PriceChart: 'chart',
    DataTable: 'table',
    KpiCard: 'kpi',
    NewsTimeline: 'card',
    ExplainMovePanel: 'card',
    PeerComparePanel: 'card',
    CorrelationMatrix: 'table',
};

export function WidgetSkeleton({ variant = 'card', className = '', ariaLabel = 'Loading...' }: SkeletonProps): React.ReactElement {
    const prefersReducedMotion = useReducedMotion();
    const shimmerStyle = prefersReducedMotion ? staticStyle : baseShimmerStyle;
    const animateProps = prefersReducedMotion
        ? {}
        : { initial: shimmerKeyframes.initial, animate: shimmerKeyframes.animate, transition: shimmerTransition };

    switch (variant) {
        // Single KPI card skeleton (for preview loading)
        case 'kpi':
            return (
                <motion.div
                    className={`p-4 rounded-xl ${className}`}
                    style={{ backgroundColor: 'rgba(30, 41, 59, 0.5)', border: '1px solid rgba(148, 163, 184, 0.1)' }}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    aria-busy="true"
                    aria-label={ariaLabel}
                    role="status"
                >
                    {/* Label shimmer */}
                    <motion.div
                        style={{ ...shimmerStyle, height: '12px', width: '50%', marginBottom: '12px' }}
                        {...animateProps}
                    />
                    {/* Value shimmer */}
                    <motion.div
                        style={{ ...shimmerStyle, height: '32px', width: '70%', marginBottom: '8px' }}
                        {...(prefersReducedMotion ? {} : { ...animateProps, transition: { ...shimmerTransition, delay: 0.1 } })}
                    />
                    {/* Delta shimmer */}
                    <motion.div
                        style={{ ...shimmerStyle, height: '14px', width: '40%' }}
                        {...(prefersReducedMotion ? {} : { ...animateProps, transition: { ...shimmerTransition, delay: 0.2 } })}
                    />
                </motion.div>
            );

        // Multiple KPI cards in grid (legacy)
        case 'kpi-grid':
            return (
                <div className={`grid grid-cols-2 md:grid-cols-4 gap-4 ${className}`} aria-busy="true" aria-label={ariaLabel} role="status">
                    {[1, 2, 3, 4].map((i) => (
                        <motion.div
                            key={i}
                            className="p-4 rounded-xl"
                            style={{ backgroundColor: 'rgba(30, 41, 59, 0.5)', border: '1px solid rgba(148, 163, 184, 0.1)' }}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.1 }}
                        >
                            <motion.div
                                style={{ ...shimmerStyle, height: '12px', width: '60%', marginBottom: '12px' }}
                                {...animateProps}
                            />
                            <motion.div
                                style={{ ...shimmerStyle, height: '28px', width: '80%' }}
                                {...(prefersReducedMotion ? {} : { ...animateProps, transition: { ...shimmerTransition, delay: 0.2 } })}
                            />
                        </motion.div>
                    ))}
                </div>
            );

        case 'chart':
            return (
                <motion.div
                    className={`rounded-xl overflow-hidden ${className}`}
                    style={{ backgroundColor: 'rgba(30, 41, 59, 0.5)', border: '1px solid rgba(148, 163, 184, 0.1)', aspectRatio: '16/9' }}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    aria-busy="true"
                    aria-label={ariaLabel}
                    role="status"
                >
                    <div className="p-4 h-full flex flex-col">
                        <motion.div
                            style={{ ...shimmerStyle, height: '20px', width: '40%', marginBottom: '16px' }}
                            {...animateProps}
                        />
                        <motion.div
                            className="flex-1"
                            style={{ ...shimmerStyle, borderRadius: '12px' }}
                            {...(prefersReducedMotion ? {} : { ...animateProps, transition: { ...shimmerTransition, delay: 0.3 } })}
                        />
                    </div>
                </motion.div>
            );

        case 'table':
            return (
                <motion.div
                    className={`rounded-xl overflow-hidden ${className}`}
                    style={{ backgroundColor: 'rgba(30, 41, 59, 0.5)', border: '1px solid rgba(148, 163, 184, 0.1)' }}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    aria-busy="true"
                    aria-label={ariaLabel}
                    role="status"
                >
                    <div className="p-4">
                        {/* Header */}
                        <div className="flex gap-4 mb-4 pb-3" style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.1)' }}>
                            {[1, 2, 3, 4].map((i) => (
                                <motion.div
                                    key={i}
                                    style={{ ...shimmerStyle, height: '14px', flex: 1 }}
                                    {...(prefersReducedMotion ? {} : { ...animateProps, transition: { ...shimmerTransition, delay: i * 0.1 } })}
                                />
                            ))}
                        </div>
                        {/* Rows */}
                        {[1, 2, 3, 4, 5].map((row) => (
                            <div key={row} className="flex gap-4 py-3" style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.05)' }}>
                                {[1, 2, 3, 4].map((col) => (
                                    <motion.div
                                        key={col}
                                        style={{ ...shimmerStyle, height: '16px', flex: 1 }}
                                        {...(prefersReducedMotion ? {} : { ...animateProps, transition: { ...shimmerTransition, delay: (row + col) * 0.05 } })}
                                    />
                                ))}
                            </div>
                        ))}
                    </div>
                </motion.div>
            );

        case 'text':
            return (
                <div className={`space-y-3 ${className}`} aria-busy="true" aria-label={ariaLabel} role="status">
                    {[100, 90, 95, 60].map((width, i) => (
                        <motion.div
                            key={i}
                            style={{ ...shimmerStyle, height: '14px', width: `${width}%` }}
                            {...(prefersReducedMotion ? {} : { ...animateProps, transition: { ...shimmerTransition, delay: i * 0.1 } })}
                        />
                    ))}
                </div>
            );

        case 'card':
        default:
            return (
                <motion.div
                    className={`p-6 rounded-xl ${className}`}
                    style={{ backgroundColor: 'rgba(30, 41, 59, 0.5)', border: '1px solid rgba(148, 163, 184, 0.1)' }}
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    aria-busy="true"
                    aria-label={ariaLabel}
                    role="status"
                >
                    <motion.div
                        style={{ ...shimmerStyle, height: '24px', width: '50%', marginBottom: '16px' }}
                        {...animateProps}
                    />
                    <div className="space-y-3">
                        {[1, 2, 3].map((i) => (
                            <motion.div
                                key={i}
                                style={{ ...shimmerStyle, height: '14px', width: `${100 - i * 10}%` }}
                                {...(prefersReducedMotion ? {} : { ...animateProps, transition: { ...shimmerTransition, delay: i * 0.15 } })}
                            />
                        ))}
                    </div>
                </motion.div>
            );
    }
}

/** Full dashboard skeleton for initial load */
export function DashboardSkeleton(): React.ReactElement {
    return (
        <div className="space-y-6 p-4" aria-busy="true" aria-label="Loading dashboard..." role="status">
            <WidgetSkeleton variant="kpi-grid" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <WidgetSkeleton variant="chart" />
                <WidgetSkeleton variant="card" />
            </div>
            <WidgetSkeleton variant="table" />
        </div>
    );
}

export default WidgetSkeleton;
