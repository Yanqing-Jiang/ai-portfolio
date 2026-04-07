/**
 * InteractionGraph -- ECharts network graph showing stems/branches as nodes
 * with clash/combine/harm relationships as colored edges.
 *
 * Data paths: /data/interactions, /data/pillars
 */

import React, { useMemo, useRef } from 'react';
import { useInView } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';
import LazyECharts from '../../../shared/LazyECharts';

const INTERACTION_COLORS: Record<string, string> = {
    clash: '#ef4444',
    combination: '#22c55e',
    harm: '#eab308',
    punishment: '#f97316',
    destruction: '#a855f7',
};

const INTERACTION_LABELS: Record<string, string> = {
    clash: '\u51b2 Clash',
    combination: '\u5408 Combine',
    harm: '\u5bb3 Harm',
    punishment: '\u5211 Punish',
    destruction: '\u7834 Destroy',
};

const ELEMENT_NODE_COLORS: Record<string, string> = {
    wood: '#22c55e',
    fire: '#ef4444',
    earth: '#d97706',
    metal: '#a1a1aa',
    water: '#3b82f6',
};

interface InteractionItem {
    type: string;
    between: string[];
    pillars: string[];
    resultElement?: string | null;
    description: string;
}

interface PillarData {
    stem: string;
    branch: string;
    stemElement: string;
    branchElement: string;
}

export function InteractionGraph({
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement | null {
    const ref = useRef<HTMLDivElement>(null);
    const isInView = useInView(ref, { once: true, margin: '-50px' });

    const interactionsPath = props.interactionsPath as BoundValue | undefined;
    const pillarsPath = props.pillarsPath as BoundValue | undefined;

    const rawInteractions = interactionsPath
        ? resolveBoundValue(interactionsPath, dataModel)
        : null;
    const rawPillars = pillarsPath
        ? resolveBoundValue(pillarsPath, dataModel)
        : null;

    const interactions = useMemo<InteractionItem[]>(() => {
        if (!rawInteractions) return [];
        const items = (rawInteractions as any)?.items ?? rawInteractions;
        return Array.isArray(items) ? items : [];
    }, [rawInteractions]);

    const pillars = useMemo<Record<string, PillarData>>(() => {
        if (!rawPillars || typeof rawPillars !== 'object') return {};
        const result: Record<string, PillarData> = {};
        for (const key of ['year', 'month', 'day', 'hour']) {
            const p = (rawPillars as any)[key];
            if (p) result[key] = p;
        }
        return result;
    }, [rawPillars]);

    const chartOptions = useMemo(() => {
        if (Object.keys(pillars).length === 0) return null;

        // Build nodes from pillar branches
        const nodeMap = new Map<string, { name: string; pillar: string; element: string }>();
        const pillarOrder = ['year', 'month', 'day', 'hour'];
        for (const pName of pillarOrder) {
            const p = pillars[pName];
            if (!p) continue;
            const key = `${pName}_${p.branch}`;
            nodeMap.set(key, {
                name: `${p.branch}\n(${pName})`,
                pillar: pName,
                element: p.branchElement,
            });
        }

        // Deterministic grid layout (no Math.random — prevents jitter on re-render)
        const nodes = Array.from(nodeMap.values()).map((n, i) => ({
            name: n.name,
            symbolSize: 45,
            x: (i % 2) * 200 + 80,
            y: Math.floor(i / 2) * 150 + 60,
            itemStyle: {
                color: ELEMENT_NODE_COLORS[n.element] || '#64748b',
                borderColor: 'rgba(255,255,255,0.15)',
                borderWidth: 2,
            },
            label: {
                show: true,
                color: '#e2e8f0',
                fontSize: 12,
                fontFamily: 'var(--ming-font-chinese), sans-serif',
            },
        }));

        // Build edges from interactions
        const edges = interactions
            .filter((ix) => ix.between.length >= 2)
            .map((ix) => {
                // Find source and target nodes by branch character
                const sourceNode = nodes.find((n) => n.name.startsWith(ix.between[0]));
                const targetNode = nodes.find((n) => n.name.startsWith(ix.between[1]));
                if (!sourceNode || !targetNode) return null;

                return {
                    source: sourceNode.name,
                    target: targetNode.name,
                    lineStyle: {
                        color: INTERACTION_COLORS[ix.type] || '#64748b',
                        width: ix.type === 'clash' ? 3 : 2,
                        type: ix.type === 'harm' ? ('dashed' as const) : ('solid' as const),
                        curveness: 0.2,
                    },
                    label: {
                        show: true,
                        formatter: ix.type === 'clash' ? '\u51b2' : ix.type === 'combination' ? '\u5408' : ix.between.join(''),
                        color: INTERACTION_COLORS[ix.type] || '#94a3b8',
                        fontSize: 11,
                    },
                };
            })
            .filter(Boolean);

        return {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'item' as const,
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                borderColor: 'rgba(148, 163, 184, 0.2)',
                textStyle: { color: '#e2e8f0', fontSize: 12 },
            },
            series: [
                {
                    type: 'graph' as const,
                    layout: 'none' as const,
                    roam: false,
                    data: nodes,
                    links: edges,
                    lineStyle: { opacity: 0.8 },
                    emphasis: {
                        focus: 'adjacency' as const,
                        lineStyle: { width: 4 },
                    },
                },
            ],
        };
    }, [pillars, interactions]);

    if (interactions.length === 0) {
        return (
            <div ref={ref} className="rounded-lg bg-slate-800/20 p-4">
                <span className="text-base font-semibold text-slate-200">
                    Interactions
                </span>
                <p className="mt-2 text-sm text-slate-500">
                    No clashes or combinations found in natal chart.
                </p>
            </div>
        );
    }

    return (
        <div ref={ref} className="space-y-3">
            <span className="text-base font-semibold text-slate-200">
                Interactions
            </span>

            {/* Graph */}
            {isInView && chartOptions && (
                <div className="rounded-lg bg-slate-800/20 p-2">
                    <LazyECharts
                        option={chartOptions}
                        style={{ height: 220, width: '100%' }}
                        opts={{ renderer: 'canvas' }}
                    />
                </div>
            )}

            {/* Legend + list */}
            <div className="flex flex-wrap gap-2">
                {interactions.map((ix, i) => (
                    <span
                        key={i}
                        className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium"
                        style={{
                            backgroundColor: `${INTERACTION_COLORS[ix.type]}15`,
                            color: INTERACTION_COLORS[ix.type],
                            border: `1px solid ${INTERACTION_COLORS[ix.type]}30`,
                        }}
                    >
                        {INTERACTION_LABELS[ix.type] || ix.type}: {ix.description}
                    </span>
                ))}
            </div>
        </div>
    );
}
