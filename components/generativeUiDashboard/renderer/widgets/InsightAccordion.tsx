/**
 * InsightAccordion — Interactive insight cards with accordion expand/collapse.
 *
 * Renders the fortune reading as compact, themed insight cards:
 * - TL;DR banner at the top
 * - 3-4 accordion sections, each with icon + heading + tagline + bullet list
 * - First section auto-expanded, rest collapsed
 * - Staggered framer-motion entrance animation
 * - Streaming: shows shimmer skeleton until isComplete
 *
 * Called from: ComponentRenderer.tsx via Registry
 * Data path: /data/narrative (emitted by stream_bridge.emit_narrative_complete)
 */

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';
import { useInspectorMode } from '../../InspectorModeContext';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface InsightBullet {
    icon: string;
    text: string;
}

interface InsightSection {
    id: string;
    icon: string;
    heading: string;
    tagline: string;
    bullets: InsightBullet[];
    citations: string[];
}

interface NarrativeData {
    tldr?: string;
    insights?: InsightSection[];
    isComplete: boolean;
    streamingText?: string;
}

/* ------------------------------------------------------------------ */
/* Animation variants                                                  */
/* ------------------------------------------------------------------ */

const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.12 } },
};

const cardVariants = {
    hidden: { opacity: 0, y: 16, scale: 0.97 },
    visible: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: { type: 'spring', stiffness: 260, damping: 24, mass: 0.8 },
    },
};

const expandVariants = {
    collapsed: { height: 0, opacity: 0 },
    expanded: { height: 'auto', opacity: 1, transition: { duration: 0.25, ease: 'easeOut' } },
};

/* ------------------------------------------------------------------ */
/* Shimmer skeleton (shown during streaming)                           */
/* ------------------------------------------------------------------ */

function StreamingSkeleton({ text }: { text?: string }) {
    return (
        <div className="flex w-full flex-col gap-3 p-1">
            {/* TL;DR placeholder */}
            <div
                className="h-5 w-3/4 rounded"
                style={{
                    background:
                        'linear-gradient(90deg, rgba(148,163,184,0.06) 0%, rgba(148,163,184,0.14) 50%, rgba(148,163,184,0.06) 100%)',
                    backgroundSize: '200% 100%',
                    animation: 'insightShimmer 1.6s ease-in-out infinite',
                }}
            />
            {/* Card placeholders */}
            {[1, 2, 3].map((i) => (
                <div
                    key={i}
                    className="rounded-lg p-4"
                    style={{
                        background: 'rgba(148, 163, 184, 0.04)',
                        border: '1px solid rgba(148, 163, 184, 0.1)',
                    }}
                >
                    <div className="flex items-center gap-2">
                        <div
                            className="h-6 w-6 rounded"
                            style={{
                                background: 'rgba(148,163,184,0.1)',
                                animation: `insightShimmer 1.6s ease-in-out infinite ${i * 0.15}s`,
                            }}
                        />
                        <div
                            className="h-4 rounded"
                            style={{
                                width: `${40 + i * 12}%`,
                                background:
                                    'linear-gradient(90deg, rgba(148,163,184,0.06) 0%, rgba(148,163,184,0.14) 50%, rgba(148,163,184,0.06) 100%)',
                                backgroundSize: '200% 100%',
                                animation: `insightShimmer 1.6s ease-in-out infinite ${i * 0.15}s`,
                            }}
                        />
                    </div>
                </div>
            ))}
            {text && (
                <p className="mt-1 text-xs text-slate-500 italic truncate">
                    {text}…
                </p>
            )}
            <style>{`@keyframes insightShimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
        </div>
    );
}

/* ------------------------------------------------------------------ */
/* Single accordion card                                               */
/* ------------------------------------------------------------------ */

const ACCENT_COLORS: Record<string, string> = {
    '🎯': '#f43f5e',
    '⚡': '#f59e0b',
    '✨': '#a78bfa',
    '🕐': '#38bdf8',
    '⚠️': '#fb923c',
    '💡': '#34d399',
    '🔥': '#ef4444',
    '🌊': '#06b6d4',
};

const EVIDENCE_BADGE_STYLES: Record<string, { label: string; color: string; icon: string }> = {
    computation: { label: 'Computed', color: '#6366f1', icon: '\u2699\uFE0F' },
    classical: { label: 'Classical', color: '#a855f7', icon: '\uD83D\uDCDC' },
    interpretation: { label: 'Interpreted', color: '#64748b', icon: '\uD83D\uDCA1' },
};

function EvidenceBadge({ type, receipt }: { type?: string; receipt?: string }) {
    const [showReceipt, setShowReceipt] = useState(false);
    const style = EVIDENCE_BADGE_STYLES[type || 'interpretation'] || EVIDENCE_BADGE_STYLES.interpretation;
    return (
        <span className="relative inline-flex">
            <button
                onClick={(e) => { e.stopPropagation(); setShowReceipt(!showReceipt); }}
                className="inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[9px] font-medium transition-opacity hover:opacity-100"
                style={{
                    backgroundColor: `${style.color}15`,
                    color: style.color,
                    border: `1px solid ${style.color}30`,
                    opacity: 0.8,
                }}
                title={`Evidence: ${style.label}`}
            >
                {style.icon} {style.label}
            </button>
            <AnimatePresence>
                {showReceipt && receipt && (
                    <motion.div
                        initial={{ opacity: 0, y: -4, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -4, scale: 0.95 }}
                        transition={{ duration: 0.12 }}
                        className="absolute left-0 top-full z-50 mt-1 w-56 rounded-lg border border-slate-700 bg-slate-800 p-2 shadow-xl"
                        style={{ fontFamily: 'ui-monospace, monospace' }}
                    >
                        <p className="text-[10px] text-slate-400 mb-1">Computation Receipt</p>
                        <p className="text-[11px] text-slate-200 whitespace-pre-wrap">{receipt}</p>
                    </motion.div>
                )}
            </AnimatePresence>
        </span>
    );
}

function AccordionCard({
    section,
    isOpen,
    onToggle,
    inspectorMode,
}: {
    section: InsightSection;
    isOpen: boolean;
    onToggle: () => void;
    inspectorMode: boolean;
}) {
    const accent = ACCENT_COLORS[section.icon] || '#6366f1';

    return (
        <motion.div
            variants={cardVariants}
            className="rounded-lg overflow-hidden"
            style={{
                background: 'rgba(148, 163, 184, 0.04)',
                border: `1px solid ${isOpen ? accent + '40' : 'rgba(148, 163, 184, 0.12)'}`,
                borderLeft: `3px solid ${accent}`,
                transition: 'border-color 0.2s ease',
            }}
        >
            {/* Header — always visible, clickable */}
            <button
                onClick={onToggle}
                className="flex w-full items-center justify-between p-3 sm:p-4 text-left"
                style={{ minHeight: '52px', background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit' }}
            >
                <div className="flex items-center gap-2 min-w-0">
                    <span className="text-lg flex-shrink-0">{section.icon}</span>
                    <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-slate-200 truncate">
                            {section.heading}
                        </h3>
                        {!isOpen && (
                            <p className="text-xs text-slate-400 truncate mt-0.5">
                                {section.tagline}
                            </p>
                        )}
                    </div>
                </div>
                <motion.span
                    animate={{ rotate: isOpen ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-slate-500 flex-shrink-0 ml-2"
                    style={{ fontSize: '0.7rem' }}
                >
                    ▼
                </motion.span>
            </button>

            {/* Expanded content */}
            <AnimatePresence initial={false}>
                {isOpen && (
                    <motion.div
                        key="content"
                        variants={expandVariants}
                        initial="collapsed"
                        animate="expanded"
                        exit="collapsed"
                        className="overflow-hidden"
                    >
                        <div className="px-3 sm:px-4 pb-3 sm:pb-4">
                            {/* Tagline */}
                            <p className="text-xs text-slate-400 mb-2 leading-relaxed">
                                {section.tagline}
                            </p>

                            {/* Bullet list */}
                            <ul className="space-y-1.5">
                                {section.bullets.map((bullet, i) => (
                                    <li key={i} className="flex items-start gap-2">
                                        <span className="text-sm flex-shrink-0 mt-0.5 leading-none">{bullet.icon}</span>
                                        <span className="text-sm text-slate-300 leading-snug">
                                            {bullet.text}
                                        </span>
                                        {inspectorMode && (
                                            <EvidenceBadge
                                                type={(bullet as any).evidence_type || (bullet as any).evidenceType}
                                                receipt={(bullet as any).tool_receipt || (bullet as any).toolReceipt}
                                            />
                                        )}
                                    </li>
                                ))}
                            </ul>

                            {/* Citation pills */}
                            {section.citations.length > 0 && (
                                <div className="mt-2.5 flex flex-wrap gap-1">
                                    {section.citations.map((cite, i) => (
                                        <span
                                            key={i}
                                            className="rounded-full px-2 py-0.5 text-[10px] text-slate-500"
                                            style={{
                                                background: 'rgba(148, 163, 184, 0.08)',
                                                border: '1px solid rgba(148, 163, 184, 0.15)',
                                            }}
                                        >
                                            {cite}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */

/**
 * InsightAccordion — renders fortune reading as interactive insight cards.
 * Called from: ComponentRenderer.tsx via Registry.
 * Data source: /data/narrative (emitted by stream_bridge).
 * Why: Replaces the wall-of-text FortuneReadingPanel with scannable,
 *      interactive cards that encourage user exploration.
 */
export function InsightAccordion({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const data = resolveBoundValue(
        props.insightsPath as BoundValue | undefined,
        dataModel,
    ) as NarrativeData | undefined;

    const insights = useMemo(() => data?.insights || [], [data?.insights]);
    const isComplete = data?.isComplete ?? false;
    const tldr = data?.tldr || '';
    const isInspector = useInspectorMode();

    // Track which sections are open. Default: first section expanded.
    const [openSections, setOpenSections] = useState<Set<string>>(new Set());

    // Auto-expand the first section when data arrives
    const firstId = insights[0]?.id;
    const effectiveOpen = useMemo(() => {
        if (openSections.size > 0) return openSections;
        if (firstId) return new Set([firstId]);
        return new Set<string>();
    }, [openSections, firstId]);

    const toggleSection = (id: string) => {
        setOpenSections((prev) => {
            const next = new Set(prev);
            // If nothing was explicitly toggled yet, start from the default
            if (prev.size === 0 && firstId) next.add(firstId);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    };

    // Streaming state: show skeleton
    if (!isComplete || !insights.length) {
        return (
            <div data-component-id={componentId}>
                <StreamingSkeleton text={data?.streamingText} />
            </div>
        );
    }

    // Complete: render TL;DR + accordion cards
    return (
        <motion.div
            data-component-id={componentId}
            className="flex w-full flex-col gap-3"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
        >
            {/* TL;DR banner */}
            {tldr && (
                <motion.div
                    variants={cardVariants}
                    className="rounded-lg px-3 py-2.5 sm:px-4 sm:py-3"
                    style={{
                        background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(168, 85, 247, 0.06) 100%)',
                        border: '1px solid rgba(99, 102, 241, 0.15)',
                    }}
                >
                    <p className="text-sm font-medium text-slate-200 leading-snug">
                        💎 {tldr}
                    </p>
                </motion.div>
            )}

            {/* Insight cards */}
            {insights.map((section) => (
                <AccordionCard
                    key={section.id}
                    section={section}
                    isOpen={effectiveOpen.has(section.id)}
                    onToggle={() => toggleSection(section.id)}
                    inspectorMode={isInspector}
                />
            ))}
        </motion.div>
    );
}
