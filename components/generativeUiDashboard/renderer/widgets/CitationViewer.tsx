/**
 * CitationViewer -- Dual-pane classical text viewer.
 *
 * Shows clickable citation chips [1][2] and when clicked, expands a
 * bottom panel showing: original Chinese text, English translation,
 * source book, and relevance score.
 *
 * Data path: /data/classics (references array)
 * Used alongside InsightAccordion to make citations interactive.
 */

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';

interface ClassicalRef {
    id: string;
    passage: string;
    translation: string;
    source: string;
    relevance: string;
}

function ReferencePanel({ reference, onClose }: { reference: ClassicalRef; onClose: () => void }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.2 }}
            className="rounded-lg border border-indigo-800/30 bg-slate-800/90 backdrop-blur-sm p-4 space-y-3"
        >
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="text-sm">{'\uD83D\uDCDC'}</span>
                    <span className="text-sm font-semibold text-slate-200">{reference.source}</span>
                </div>
                <button
                    onClick={onClose}
                    className="text-slate-500 hover:text-slate-300 text-sm"
                >
                    {'\u2715'}
                </button>
            </div>

            {/* Dual pane */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Original Chinese */}
                <div className="rounded-md bg-slate-900/50 p-3">
                    <p className="text-[10px] text-slate-500 mb-1 uppercase tracking-wide">Original</p>
                    <p
                        className="text-base text-slate-200 leading-relaxed"
                        style={{ fontFamily: 'var(--ming-font-chinese), serif' }}
                    >
                        {reference.passage}
                    </p>
                </div>

                {/* Translation */}
                <div className="rounded-md bg-slate-900/50 p-3">
                    <p className="text-[10px] text-slate-500 mb-1 uppercase tracking-wide">Translation</p>
                    <p className="text-sm text-slate-300 leading-relaxed italic">
                        {reference.translation}
                    </p>
                </div>
            </div>

            {/* Relevance score */}
            <div className="flex items-center gap-2 text-[10px] text-slate-500">
                <span className="font-mono">{reference.relevance}</span>
                <span>|</span>
                <span>ID: {reference.id}</span>
            </div>
        </motion.div>
    );
}

export function CitationViewer({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement | null {
    const refsPath = props.referencesPath as BoundValue | undefined;
    const raw = refsPath ? resolveBoundValue(refsPath, dataModel) : null;

    const references = useMemo<ClassicalRef[]>(() => {
        if (!raw || typeof raw !== 'object') return [];
        const refs = (raw as any)?.references ?? raw;
        return Array.isArray(refs) ? refs : [];
    }, [raw]);

    const [activeRefId, setActiveRefId] = useState<string | null>(null);
    const activeRef = references.find((r) => r.id === activeRefId);

    if (references.length === 0) return null;

    return (
        <div data-component-id={componentId} className="space-y-3">
            <div className="flex items-center gap-2">
                <span className="text-base font-semibold text-slate-200">
                    Classical Sources
                </span>
                <span className="text-xs text-slate-500">
                    {references.length} passages
                </span>
            </div>

            {/* Citation chips */}
            <div className="flex flex-wrap gap-1.5">
                {references.map((ref, i) => (
                    <button
                        key={ref.id}
                        onClick={() => setActiveRefId(activeRefId === ref.id ? null : ref.id)}
                        className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all"
                        style={{
                            backgroundColor: activeRefId === ref.id
                                ? 'rgba(99, 102, 241, 0.15)'
                                : 'rgba(148, 163, 184, 0.06)',
                            border: activeRefId === ref.id
                                ? '1.5px solid rgba(99, 102, 241, 0.4)'
                                : '1px solid rgba(148, 163, 184, 0.12)',
                            color: activeRefId === ref.id ? '#a5b4fc' : '#94a3b8',
                        }}
                    >
                        <span className="font-mono text-[10px] opacity-60">[{i + 1}]</span>
                        <span className="truncate max-w-[140px]">{ref.source}</span>
                    </button>
                ))}
            </div>

            {/* Expanded reference panel */}
            <AnimatePresence>
                {activeRef && (
                    <ReferencePanel
                        reference={activeRef}
                        onClose={() => setActiveRefId(null)}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}
