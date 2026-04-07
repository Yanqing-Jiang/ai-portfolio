/**
 * SpookyAccuracyCard -- "Predictions about the past" based on annual pillar
 * interactions. Shows retrodictions with year, interaction type, and a
 * templated prediction. The "spooky" part is that it appears to know
 * what happened without being told.
 *
 * Data path: /data/retrodictions
 */

import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';

interface Retrodiction {
    year: number;
    prediction: string;
    interactionType: string;
    interactionDescription: string;
    affectedPillar: string;
    confidence: number;
}

const TYPE_STYLES: Record<string, { color: string; icon: string }> = {
    clash: { color: '#ef4444', icon: '\u26A1' },
    combination: { color: '#22c55e', icon: '\uD83E\uDD1D' },
    harm: { color: '#eab308', icon: '\u26A0\uFE0F' },
};

function RetrodictionCard({ item, index }: { item: Retrodiction; index: number }) {
    const [confirmed, setConfirmed] = useState<boolean | null>(null);
    const style = TYPE_STYLES[item.interactionType] || TYPE_STYLES.clash;

    return (
        <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.15, duration: 0.3 }}
            className="rounded-lg border p-3 space-y-2"
            style={{
                borderColor: `${style.color}25`,
                background: `${style.color}08`,
            }}
        >
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="text-lg">{style.icon}</span>
                    <span className="text-sm font-bold text-slate-200">{item.year}</span>
                    <span
                        className="rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                        style={{ color: style.color, backgroundColor: `${style.color}15` }}
                    >
                        {item.interactionType}
                    </span>
                </div>
                <span className="text-[10px] text-slate-500 font-mono">
                    {(item.confidence * 100).toFixed(0)}% match
                </span>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed">
                {item.prediction}
            </p>

            <p className="text-[10px] text-slate-500 font-mono">
                Source: {item.interactionDescription} ({item.affectedPillar} pillar)
            </p>

            {/* Feedback buttons */}
            {confirmed === null ? (
                <div className="flex gap-2">
                    <button
                        onClick={() => setConfirmed(true)}
                        className="rounded-md px-2.5 py-1 text-xs font-medium transition-colors hover:bg-emerald-900/30"
                        style={{ color: '#4ade80', border: '1px solid rgba(74, 222, 128, 0.2)' }}
                    >
                        This happened
                    </button>
                    <button
                        onClick={() => setConfirmed(false)}
                        className="rounded-md px-2.5 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-800/50"
                        style={{ border: '1px solid rgba(148, 163, 184, 0.15)' }}
                    >
                        Not quite
                    </button>
                </div>
            ) : (
                <p className="text-xs" style={{ color: confirmed ? '#4ade80' : '#94a3b8' }}>
                    {confirmed ? 'Confirmed' : 'Noted — chart interactions can manifest differently'}
                </p>
            )}
        </motion.div>
    );
}

export function SpookyAccuracyCard({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement | null {
    const retroPath = props.retrodictionsPath as BoundValue | undefined;
    const raw = retroPath ? resolveBoundValue(retroPath, dataModel) : null;

    const retrodictions = useMemo<Retrodiction[]>(() => {
        if (!raw) return [];
        const items = (raw as any)?.items ?? raw;
        return Array.isArray(items) ? items : [];
    }, [raw]);

    if (retrodictions.length === 0) return null;

    return (
        <div data-component-id={componentId} className="space-y-3">
            <div className="flex items-center gap-2">
                <span className="text-lg">\uD83D\uDD2E</span>
                <span className="text-base font-semibold text-slate-200">
                    Does This Sound Familiar?
                </span>
            </div>
            <p className="text-xs text-slate-500">
                Based on your chart's past interactions, here's what the pillars suggest happened:
            </p>

            <div className="space-y-2">
                {retrodictions.map((item, i) => (
                    <RetrodictionCard key={item.year} item={item} index={i} />
                ))}
            </div>
        </div>
    );
}
