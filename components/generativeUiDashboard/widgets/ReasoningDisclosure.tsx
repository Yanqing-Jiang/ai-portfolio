/**
 * ReasoningDisclosure - Collapsible panel showing AI reasoning steps.
 *
 * Component: ReasoningDisclosure
 * Called from: ExplainMovePanel, PeerComparePanel
 * Invokes: Framer Motion AnimatePresence
 * Why: Shows AI's thought process with expandable reasoning steps.
 *      Increases transparency and trust in AI-generated insights.
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// ============================================================================
// Types
// ============================================================================

export interface ReasoningStep {
    /** Short description of what this step analyzed */
    step: string;
    /** Detailed explanation of the reasoning */
    reasoning: string;
    /** Optional confidence score (0-1) */
    confidence?: number;
}

export interface ReasoningDisclosureProps {
    /** Array of reasoning steps */
    steps: ReasoningStep[];
    /** Label for the disclosure button */
    label?: string;
    /** Initially expanded? */
    defaultExpanded?: boolean;
    /** Additional class names */
    className?: string;
}

// ============================================================================
// Component
// ============================================================================

export function ReasoningDisclosure({
    steps,
    label = 'Why this insight?',
    defaultExpanded = false,
    className = '',
}: ReasoningDisclosureProps) {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);

    // Don't render if no steps
    if (!steps || steps.length === 0) return null;

    // Check for reduced motion preference
    const prefersReducedMotion = typeof window !== 'undefined'
        && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    const animationProps = prefersReducedMotion ? {} : {
        initial: { opacity: 0, height: 0 },
        animate: { opacity: 1, height: 'auto' },
        exit: { opacity: 0, height: 0 },
        transition: { duration: 0.2, ease: 'easeInOut' },
    };

    return (
        <div className={`reasoning-disclosure ${className}`}>
            {/* Toggle button */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-800/50 hover:bg-slate-700/50 border border-slate-700/50 hover:border-slate-600 transition-all duration-200 text-left"
                aria-expanded={isExpanded}
                aria-controls="reasoning-content"
            >
                <span className="flex items-center gap-2 text-sm text-slate-300">
                    <span className="text-amber-400">💡</span>
                    <span>{label}</span>
                </span>
                <motion.span
                    animate={{ rotate: isExpanded ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-slate-400"
                >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                    </svg>
                </motion.span>
            </button>

            {/* Expandable content */}
            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        id="reasoning-content"
                        {...animationProps}
                        className="overflow-hidden"
                    >
                        <div className="mt-2 space-y-2">
                            {steps.map((step, index) => (
                                <ReasoningStepCard
                                    key={index}
                                    step={step}
                                    stepNumber={index + 1}
                                    totalSteps={steps.length}
                                />
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

/**
 * Individual reasoning step card.
 */
function ReasoningStepCard({
    step,
    stepNumber,
    totalSteps,
}: {
    step: ReasoningStep;
    stepNumber: number;
    totalSteps: number;
}) {
    return (
        <div className="reasoning-step p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
            {/* Step header */}
            <div className="flex items-start justify-between mb-1">
                <div className="flex items-center gap-2">
                    <span className="flex-shrink-0 w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 text-xs font-medium flex items-center justify-center">
                        {stepNumber}
                    </span>
                    <span className="text-sm font-medium text-slate-200">
                        {step.step}
                    </span>
                </div>
                {step.confidence !== undefined && (
                    <ConfidenceBadge confidence={step.confidence} />
                )}
            </div>

            {/* Step reasoning */}
            <p className="text-sm text-slate-400 pl-7 leading-relaxed">
                {step.reasoning}
            </p>

            {/* Progress indicator */}
            {totalSteps > 1 && (
                <div className="mt-2 pl-7">
                    <div className="flex gap-1">
                        {Array.from({ length: totalSteps }).map((_, i) => (
                            <div
                                key={i}
                                className={`h-1 flex-1 rounded-full transition-colors ${
                                    i < stepNumber ? 'bg-rose-500/50' : 'bg-slate-700'
                                }`}
                            />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

/**
 * Confidence score badge.
 */
function ConfidenceBadge({ confidence }: { confidence: number }) {
    // Determine color based on confidence level
    const getColorClass = () => {
        if (confidence >= 0.8) return 'text-emerald-400 bg-emerald-500/20';
        if (confidence >= 0.6) return 'text-amber-400 bg-amber-500/20';
        return 'text-rose-400 bg-rose-500/20';
    };

    const percentage = Math.round(confidence * 100);

    return (
        <span
            className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${getColorClass()}`}
            title={`${percentage}% confidence`}
        >
            {percentage}%
        </span>
    );
}

export default ReasoningDisclosure;
