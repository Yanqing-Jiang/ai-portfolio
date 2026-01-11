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
    /** Suggested peer ticker for comparison (defaults to deriving from anomaly or generic 'peers') */
    suggestedPeer?: string;
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
    suggestedPeer,
}: AnomalyAlertProps) {
    const styles = IMPORTANCE_STYLES[anomaly.importance];
    const isPositive = anomaly.comparison.percentageDiff > 0;

    // Derive peer ticker: use prop, or extract from comparison if peer type, or fallback
    const peerTicker = suggestedPeer
        || (anomaly.comparison.type === 'peer'
            ? (anomaly.comparison as unknown as { peerTicker?: string }).peerTicker
            : undefined)
        || 'peers';  // Generic fallback instead of hard-coded AMD

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
                relative rounded-lg border ${styles.border} ${styles.bg}
                shadow-md ${styles.glow} p-3
            `}
            role="alert"
            aria-live="polite"
        >
            {/* Header - Compact */}
            <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-1.5">
                    <span className="text-base">{styles.icon}</span>
                    <div>
                        <h4 className="text-xs font-semibold text-white">
                            AI Noticed Something
                        </h4>
                        <span className={`text-[9px] px-1 py-0.5 rounded ${styles.badge} uppercase tracking-wide`}>
                            {anomaly.importance}
                        </span>
                    </div>
                </div>
                <button
                    onClick={onDismiss}
                    className="text-slate-500 hover:text-white transition-colors p-0.5 rounded hover:bg-slate-700/50 text-xs"
                    aria-label="Dismiss alert"
                >
                    ✕
                </button>
            </div>

            {/* Main insight - Compact */}
            <div className="mb-2">
                <p className="text-slate-200 text-xs leading-snug">
                    <strong className="text-white">{anomaly.ticker}'s {anomaly.metric}</strong>{' '}
                    hit <strong className={isPositive ? 'text-emerald-400' : 'text-rose-400'}>
                        {formattedValue}
                    </strong>{' '}
                    — {anomaly.comparison.description}
                </p>

                {/* Comparison detail */}
                <div className="flex items-center gap-1.5 mt-1.5">
                    <span className={`
                        text-[10px] px-1.5 py-0.5 rounded
                        ${isPositive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}
                    `}>
                        {formattedDiff} from {anomaly.comparison.type} avg
                    </span>
                </div>

                {/* Optional explanation - hidden for compact view */}
            </div>

            {/* Action buttons - Compact */}
            <div className="flex items-center gap-1.5 flex-wrap">
                <button
                    onClick={onInvestigate}
                    className="px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-white text-[10px] font-medium transition-colors flex items-center gap-1"
                >
                    <span>🔍</span>
                    <span>Investigate</span>
                </button>

                {onCompare && (
                    <button
                        onClick={() => onCompare(peerTicker)}
                        className="px-2 py-1 rounded bg-slate-700/50 hover:bg-slate-600/50 text-slate-300 text-[10px] font-medium transition-colors flex items-center gap-1"
                    >
                        <span>📊</span>
                        <span>Compare</span>
                    </button>
                )}
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
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
