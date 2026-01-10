/**
 * AnomalyAlert - Proactive insight notification in follow-up section.
 *
 * Component: AnomalyAlert
 * Appears in: "Continue your analysis" section
 * Triggered by: Background anomaly detection on dashboard data
 * Why: Surfaces insights users would otherwise miss.
 */

import { motion, AnimatePresence } from 'framer-motion';

// ============================================================================
// Types
// ============================================================================

export interface AnomalyData {
    /** Primary ticker symbol */
    ticker: string;
    /** Metric name that has the anomaly */
    metric: string;
    /** Current value of the metric */
    value: number;
    /** Unit of measure (%, $, etc.) */
    unit?: string;
    /** Comparison details */
    comparison: {
        /** Type of comparison */
        type: 'historical' | 'sector' | 'peer';
        /** Baseline value for comparison */
        baseline: number;
        /** Percentage difference from baseline */
        percentageDiff: number;
        /** Human-readable description */
        description: string;
    };
    /** Importance level for styling */
    importance: 'high' | 'medium' | 'low';
    /** Optional explanation text */
    explanation?: string;
}

export interface AnomalyAlertProps {
    /** Anomaly data to display */
    anomaly: AnomalyData;
    /** Called when user clicks "Investigate" */
    onInvestigate: () => void;
    /** Called when user wants to compare to a peer */
    onCompare?: (peerTicker: string) => void;
    /** Called when user dismisses the alert */
    onDismiss: () => void;
}

// ============================================================================
// Styling helpers
// ============================================================================

const IMPORTANCE_STYLES = {
    high: {
        border: 'border-rose-500/40',
        bg: 'bg-rose-500/10',
        glow: 'shadow-rose-500/20',
        icon: '🔥',
        badge: 'bg-rose-500/20 text-rose-400',
    },
    medium: {
        border: 'border-amber-500/40',
        bg: 'bg-amber-500/10',
        glow: 'shadow-amber-500/20',
        icon: '💡',
        badge: 'bg-amber-500/20 text-amber-400',
    },
    low: {
        border: 'border-blue-500/40',
        bg: 'bg-blue-500/10',
        glow: 'shadow-blue-500/20',
        icon: '📊',
        badge: 'bg-blue-500/20 text-blue-400',
    },
};

// ============================================================================
// Component
// ============================================================================

export function AnomalyAlert({
    anomaly,
    onInvestigate,
    onCompare,
    onDismiss,
}: AnomalyAlertProps) {
    const styles = IMPORTANCE_STYLES[anomaly.importance];
    const isPositive = anomaly.comparison.percentageDiff > 0;

    // Format the value with unit
    const formattedValue = anomaly.unit === '%'
        ? `${anomaly.value.toFixed(1)}%`
        : anomaly.unit === '$'
            ? `$${anomaly.value.toLocaleString()}`
            : anomaly.value.toLocaleString();

    // Format the percentage difference
    const diffSign = isPositive ? '+' : '';
    const formattedDiff = `${diffSign}${anomaly.comparison.percentageDiff.toFixed(1)}%`;

    return (
        <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className={`
                relative rounded-xl border ${styles.border} ${styles.bg}
                shadow-lg ${styles.glow} p-4 mb-4
            `}
            role="alert"
            aria-live="polite"
        >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                    <span className="text-xl">{styles.icon}</span>
                    <div>
                        <h4 className="text-sm font-semibold text-white">
                            AI Noticed Something
                        </h4>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${styles.badge} uppercase tracking-wide`}>
                            {anomaly.importance} priority
                        </span>
                    </div>
                </div>
                <button
                    onClick={onDismiss}
                    className="text-slate-500 hover:text-white transition-colors p-1 rounded hover:bg-slate-700/50"
                    aria-label="Dismiss alert"
                >
                    ✕
                </button>
            </div>

            {/* Main insight */}
            <div className="mb-3">
                <p className="text-slate-200 text-sm leading-relaxed">
                    <strong className="text-white">{anomaly.ticker}'s {anomaly.metric}</strong>{' '}
                    hit <strong className={isPositive ? 'text-emerald-400' : 'text-rose-400'}>
                        {formattedValue}
                    </strong>{' '}
                    — {anomaly.comparison.description}
                </p>

                {/* Comparison detail */}
                <div className="flex items-center gap-2 mt-2">
                    <span className={`
                        text-xs px-2 py-1 rounded-lg
                        ${isPositive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}
                    `}>
                        {formattedDiff} from {anomaly.comparison.type} average
                    </span>
                </div>

                {/* Optional explanation */}
                {anomaly.explanation && (
                    <p className="text-xs text-slate-400 mt-2 italic">
                        {anomaly.explanation}
                    </p>
                )}
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-2 flex-wrap">
                <button
                    onClick={onInvestigate}
                    className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white text-xs font-medium transition-colors flex items-center gap-1.5"
                >
                    <span>🔍</span>
                    <span>Investigate</span>
                </button>

                {onCompare && (
                    <button
                        onClick={() => onCompare('AMD')} // Default peer, could be dynamic
                        className="px-3 py-1.5 rounded-lg bg-slate-700/50 hover:bg-slate-600/50 text-slate-300 text-xs font-medium transition-colors flex items-center gap-1.5"
                    >
                        <span>📊</span>
                        <span>Compare to peers</span>
                    </button>
                )}

                <button
                    onClick={onDismiss}
                    className="px-3 py-1.5 rounded-lg text-slate-500 hover:text-slate-300 text-xs font-medium transition-colors ml-auto"
                >
                    Dismiss
                </button>
            </div>
        </motion.div>
    );
}

// ============================================================================
// Container for multiple anomalies
// ============================================================================

export interface AnomalyAlertListProps {
    anomalies: AnomalyData[];
    onInvestigate: (anomaly: AnomalyData) => void;
    onCompare?: (anomaly: AnomalyData, peerTicker: string) => void;
    onDismiss: (anomaly: AnomalyData) => void;
}

export function AnomalyAlertList({
    anomalies,
    onInvestigate,
    onCompare,
    onDismiss,
}: AnomalyAlertListProps) {
    if (anomalies.length === 0) return null;

    return (
        <div className="space-y-2">
            <AnimatePresence mode="popLayout">
                {anomalies.map((anomaly, index) => (
                    <AnomalyAlert
                        key={`${anomaly.ticker}-${anomaly.metric}-${index}`}
                        anomaly={anomaly}
                        onInvestigate={() => onInvestigate(anomaly)}
                        onCompare={onCompare ? (peer) => onCompare(anomaly, peer) : undefined}
                        onDismiss={() => onDismiss(anomaly)}
                    />
                ))}
            </AnimatePresence>
        </div>
    );
}

export default AnomalyAlert;
