/**
 * WidgetSkeleton Component
 * 
 * Provides shimmer loading placeholders for A2UI widgets during data fetching.
 * Called from: ComponentRenderer.tsx when widget data is loading
 * Why: Creates premium loading experience with animated placeholders
 */

import React from 'react';
import { motion } from 'framer-motion';

const shimmerKeyframes = {
    initial: { backgroundPosition: '-200% 0' },
    animate: { backgroundPosition: '200% 0' },
};

const shimmerTransition = {
    duration: 1.5,
    repeat: Infinity,
    ease: 'linear' as const,
};

const baseShimmerStyle: React.CSSProperties = {
    background: 'linear-gradient(90deg, rgba(30, 41, 59, 0.6) 25%, rgba(51, 65, 85, 0.8) 50%, rgba(30, 41, 59, 0.6) 75%)',
    backgroundSize: '200% 100%',
    borderRadius: '8px',
};

interface SkeletonProps {
    variant?: 'card' | 'chart' | 'table' | 'text' | 'kpi';
    className?: string;
}

export function WidgetSkeleton({ variant = 'card', className = '' }: SkeletonProps): React.ReactElement {
    switch (variant) {
        case 'kpi':
            return (
                <div className={`grid grid-cols-2 md:grid-cols-4 gap-4 ${className}`}>
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
                                style={{ ...baseShimmerStyle, height: '12px', width: '60%', marginBottom: '12px' }}
                                initial={shimmerKeyframes.initial}
                                animate={shimmerKeyframes.animate}
                                transition={shimmerTransition}
                            />
                            <motion.div
                                style={{ ...baseShimmerStyle, height: '28px', width: '80%' }}
                                initial={shimmerKeyframes.initial}
                                animate={shimmerKeyframes.animate}
                                transition={{ ...shimmerTransition, delay: 0.2 }}
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
                >
                    <div className="p-4 h-full flex flex-col">
                        <motion.div
                            style={{ ...baseShimmerStyle, height: '20px', width: '40%', marginBottom: '16px' }}
                            initial={shimmerKeyframes.initial}
                            animate={shimmerKeyframes.animate}
                            transition={shimmerTransition}
                        />
                        <motion.div
                            className="flex-1"
                            style={{ ...baseShimmerStyle, borderRadius: '12px' }}
                            initial={shimmerKeyframes.initial}
                            animate={shimmerKeyframes.animate}
                            transition={{ ...shimmerTransition, delay: 0.3 }}
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
                >
                    <div className="p-4">
                        {/* Header */}
                        <div className="flex gap-4 mb-4 pb-3" style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.1)' }}>
                            {[1, 2, 3, 4].map((i) => (
                                <motion.div
                                    key={i}
                                    style={{ ...baseShimmerStyle, height: '14px', flex: 1 }}
                                    initial={shimmerKeyframes.initial}
                                    animate={shimmerKeyframes.animate}
                                    transition={{ ...shimmerTransition, delay: i * 0.1 }}
                                />
                            ))}
                        </div>
                        {/* Rows */}
                        {[1, 2, 3, 4, 5].map((row) => (
                            <div key={row} className="flex gap-4 py-3" style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.05)' }}>
                                {[1, 2, 3, 4].map((col) => (
                                    <motion.div
                                        key={col}
                                        style={{ ...baseShimmerStyle, height: '16px', flex: 1 }}
                                        initial={shimmerKeyframes.initial}
                                        animate={shimmerKeyframes.animate}
                                        transition={{ ...shimmerTransition, delay: (row + col) * 0.05 }}
                                    />
                                ))}
                            </div>
                        ))}
                    </div>
                </motion.div>
            );

        case 'text':
            return (
                <div className={`space-y-3 ${className}`}>
                    {[100, 90, 95, 60].map((width, i) => (
                        <motion.div
                            key={i}
                            style={{ ...baseShimmerStyle, height: '14px', width: `${width}%` }}
                            initial={shimmerKeyframes.initial}
                            animate={shimmerKeyframes.animate}
                            transition={{ ...shimmerTransition, delay: i * 0.1 }}
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
                >
                    <motion.div
                        style={{ ...baseShimmerStyle, height: '24px', width: '50%', marginBottom: '16px' }}
                        initial={shimmerKeyframes.initial}
                        animate={shimmerKeyframes.animate}
                        transition={shimmerTransition}
                    />
                    <div className="space-y-3">
                        {[1, 2, 3].map((i) => (
                            <motion.div
                                key={i}
                                style={{ ...baseShimmerStyle, height: '14px', width: `${100 - i * 10}%` }}
                                initial={shimmerKeyframes.initial}
                                animate={shimmerKeyframes.animate}
                                transition={{ ...shimmerTransition, delay: i * 0.15 }}
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
        <div className="space-y-6 p-4">
            <WidgetSkeleton variant="kpi" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <WidgetSkeleton variant="chart" />
                <WidgetSkeleton variant="card" />
            </div>
            <WidgetSkeleton variant="table" />
        </div>
    );
}

export default WidgetSkeleton;
