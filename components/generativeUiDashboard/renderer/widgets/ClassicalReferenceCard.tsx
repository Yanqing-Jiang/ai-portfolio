/**
 * ClassicalReferenceCard — Expandable classical BaZi text passages.
 *
 * Renders Chinese passage with toggleable English translation,
 * source citation, and relevance note.
 *
 * Called from: ComponentRenderer.tsx via Registry
 * Data path: /data/classics (emitted by stream_bridge.emit_references)
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';

interface ClassicalReference {
    id: string;
    passage: string;
    translation: string;
    source: string;
    relevance: string;
}

const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.15 } },
};

const cardVariants = {
    hidden: { opacity: 0, x: -12 },
    visible: {
        opacity: 1,
        x: 0,
        transition: { type: 'spring', stiffness: 200, damping: 25, mass: 0.8 },
    },
};

export function ClassicalReferenceCard({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const resolved = resolveBoundValue(
        props.referencesPath as BoundValue | undefined,
        dataModel
    ) as { references: ClassicalReference[] } | ClassicalReference[] | undefined;

    const references = Array.isArray(resolved)
        ? resolved
        : resolved?.references || [];

    const [expandedId, setExpandedId] = useState<string | null>(null);

    if (!references.length) {
        return <div data-component-id={componentId} />;
    }

    return (
        <motion.div
            data-component-id={componentId}
            className="flex w-full flex-col gap-3"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
        >
            {references.map((ref) => {
                const isExpanded = expandedId === ref.id;
                return (
                    <motion.div
                        key={ref.id}
                        variants={cardVariants}
                        className="cursor-pointer rounded-lg p-4"
                        style={{
                            borderLeft: '3px solid #dc2626',
                            background: 'rgba(148, 163, 184, 0.04)',
                            border: '1px solid rgba(148, 163, 184, 0.1)',
                            borderLeftColor: '#dc2626',
                            borderLeftWidth: '3px',
                        }}
                        onClick={() =>
                            setExpandedId(isExpanded ? null : ref.id)
                        }
                    >
                        {/* Chinese passage */}
                        <p
                            className="leading-relaxed text-slate-200"
                            style={{
                                fontFamily:
                                    "var(--ming-font-chinese, 'Noto Serif SC', 'Songti SC', serif)",
                                fontSize: 'clamp(0.95rem, 2.5vw, 1.125rem)',
                            }}
                        >
                            {ref.passage}
                        </p>

                        {/* Translation (toggle) */}
                        <AnimatePresence>
                            {isExpanded && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    transition={{ duration: 0.2 }}
                                    className="overflow-hidden"
                                >
                                    <p className="mt-2 text-sm leading-relaxed text-slate-400">
                                        {ref.translation}
                                    </p>
                                    {ref.relevance && (
                                        <p className="mt-1 text-xs italic text-slate-500">
                                            {ref.relevance}
                                        </p>
                                    )}
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Source + expand hint */}
                        <div className="mt-2 flex items-center justify-between">
                            <span className="text-xs text-slate-500">
                                {isExpanded ? '▲ collapse' : '▼ translation'}
                            </span>
                            <span className="text-xs text-slate-500">
                                {ref.source}
                            </span>
                        </div>
                    </motion.div>
                );
            })}
        </motion.div>
    );
}
