/**
 * TenGodsTable -- Compact table showing each position's 10 God classification
 * with favorability badges.
 *
 * Data path: /data/tenGods
 */

import React, { useMemo } from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';

interface TenGodItem {
    stem: string;
    god: string;
    english: string;
    pillar: string;
    position: string;
}

// 10 Gods favorability classification
// Favorable: Companion, Direct Seal, Indirect Seal, Direct Officer, Eating God
// Unfavorable: Rob Wealth, Seven Killings, Hurting Officer
// Neutral: Direct Wealth, Indirect Wealth
const FAVORABILITY: Record<string, 'favorable' | 'unfavorable' | 'neutral'> = {
    '\u6bd4\u80a9': 'favorable',      // Companion
    '\u52ab\u8d22': 'unfavorable',    // Rob Wealth
    '\u98df\u795e': 'favorable',      // Eating God
    '\u4f24\u5b98': 'unfavorable',    // Hurting Officer
    '\u504f\u8d22': 'neutral',        // Indirect Wealth
    '\u6b63\u8d22': 'neutral',        // Direct Wealth
    '\u4e03\u6740': 'unfavorable',    // Seven Killings
    '\u6b63\u5b98': 'favorable',      // Direct Officer
    '\u504f\u5370': 'favorable',      // Indirect Seal
    '\u6b63\u5370': 'favorable',      // Direct Seal
};

const FAVORABILITY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
    favorable: { bg: 'rgba(34, 197, 94, 0.1)', text: '#4ade80', border: 'rgba(34, 197, 94, 0.2)' },
    unfavorable: { bg: 'rgba(239, 68, 68, 0.1)', text: '#f87171', border: 'rgba(239, 68, 68, 0.2)' },
    neutral: { bg: 'rgba(148, 163, 184, 0.08)', text: '#94a3b8', border: 'rgba(148, 163, 184, 0.15)' },
};

const POSITION_LABELS: Record<string, string> = {
    stem: 'Stem',
    hidden_main: 'Main Qi',
    hidden_middle: 'Mid Qi',
    hidden_residual: 'Res Qi',
};

const PILLAR_ORDER = ['year', 'month', 'day', 'hour'];

export function TenGodsTable({
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement | null {
    const godsPath = props.godsPath as BoundValue | undefined;
    const raw = godsPath ? resolveBoundValue(godsPath, dataModel) : null;

    const gods = useMemo<TenGodItem[]>(() => {
        if (!raw) return [];
        const items = (raw as any)?.items ?? raw;
        return Array.isArray(items) ? items : [];
    }, [raw]);

    if (gods.length === 0) {
        return (
            <div className="h-32 animate-pulse rounded-lg bg-slate-800/30" />
        );
    }

    // Group by pillar for organized display
    const grouped = useMemo(() => {
        const map = new Map<string, TenGodItem[]>();
        for (const pillar of PILLAR_ORDER) {
            const items = gods.filter((g) => g.pillar === pillar);
            if (items.length > 0) map.set(pillar, items);
        }
        return map;
    }, [gods]);

    return (
        <div className="space-y-3">
            <span className="text-base font-semibold text-slate-200">
                Ten Gods <span className="text-xs text-slate-500 font-normal">\u5341\u795e</span>
            </span>

            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-slate-700/50">
                            <th className="pb-2 pr-3 text-left text-xs font-medium text-slate-500">
                                Pillar
                            </th>
                            <th className="pb-2 px-2 text-left text-xs font-medium text-slate-500">
                                Pos
                            </th>
                            <th className="pb-2 px-2 text-center text-xs font-medium text-slate-500"
                                style={{ fontFamily: 'var(--ming-font-chinese)' }}
                            >
                                Stem
                            </th>
                            <th className="pb-2 px-2 text-left text-xs font-medium text-slate-500">
                                God
                            </th>
                            <th className="pb-2 pl-2 text-left text-xs font-medium text-slate-500">
                                English
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {PILLAR_ORDER.map((pillar) => {
                            const items = grouped.get(pillar);
                            if (!items) return null;
                            return items.map((item, idx) => {
                                const fav = FAVORABILITY[item.god] || 'neutral';
                                const colors = FAVORABILITY_COLORS[fav];
                                return (
                                    <tr
                                        key={`${pillar}-${idx}`}
                                        className="border-b border-slate-800/30"
                                    >
                                        {idx === 0 && (
                                            <td
                                                className="py-1.5 pr-3 text-xs font-medium text-slate-400 capitalize align-top"
                                                rowSpan={items.length}
                                            >
                                                {pillar}
                                            </td>
                                        )}
                                        <td className="py-1.5 px-2 text-xs text-slate-500">
                                            {POSITION_LABELS[item.position] || item.position}
                                        </td>
                                        <td
                                            className="py-1.5 px-2 text-center text-base"
                                            style={{ fontFamily: 'var(--ming-font-chinese)' }}
                                        >
                                            {item.stem}
                                        </td>
                                        <td className="py-1.5 px-2">
                                            <span
                                                className="inline-block rounded-md px-1.5 py-0.5 text-xs font-medium"
                                                style={{
                                                    backgroundColor: colors.bg,
                                                    color: colors.text,
                                                    border: `1px solid ${colors.border}`,
                                                    fontFamily: 'var(--ming-font-chinese)',
                                                }}
                                            >
                                                {item.god}
                                            </span>
                                        </td>
                                        <td className="py-1.5 pl-2 text-xs text-slate-400">
                                            {item.english}
                                        </td>
                                    </tr>
                                );
                            });
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
