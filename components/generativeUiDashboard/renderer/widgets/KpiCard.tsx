/**
 * KPI Card Widget
 *
 * Single metric display with optional delta indicator.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import { resolveString, resolveNumber } from '../../a2ui/DataBinder';
import type { KpiCardProps } from '../../a2ui/types';

export function KpiCard({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const kpiProps = props as unknown as KpiCardProps;

    const label = resolveString(kpiProps.label, dataModel, 'Value');
    const value = resolveNumber(kpiProps.value, dataModel, 0);
    const unit = resolveString(kpiProps.unit, dataModel, '');
    const delta = kpiProps.delta ? resolveNumber(kpiProps.delta, dataModel, 0) : null;
    const deltaType = resolveString(kpiProps.deltaType, dataModel, 'absolute');

    // Format value
    const formatValue = (val: number, u: string): string => {
        if (u === '$') {
            return `$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }
        if (u === '%') {
            return `${val.toFixed(2)}%`;
        }
        if (u === 'M') {
            return `${(val / 1_000_000).toFixed(2)}M`;
        }
        if (u === 'B') {
            return `${(val / 1_000_000_000).toFixed(2)}B`;
        }
        return val.toLocaleString();
    };

    // Format delta
    const formatDelta = (d: number, type: string): string => {
        const prefix = d > 0 ? '+' : '';
        if (type === 'percentage') {
            return `${prefix}${d.toFixed(2)}%`;
        }
        return `${prefix}${d.toFixed(2)}`;
    };

    // Delta color
    const deltaColor = delta !== null ? (delta >= 0 ? '#22c55e' : '#ef4444') : '#94a3b8';
    const deltaIcon = delta !== null ? (delta >= 0 ? '↑' : '↓') : '';

    return (
        <div
            className="a2ui-kpi-card"
            data-component-id={componentId}
            style={{
                padding: '1rem',
                backgroundColor: 'rgba(30, 41, 59, 0.5)',
                borderRadius: '8px',
                textAlign: 'center',
            }}
        >
            <div
                className="a2ui-kpi-card__label"
                style={{
                    fontSize: '0.75rem',
                    color: '#94a3b8',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    marginBottom: '0.5rem',
                }}
            >
                {label}
            </div>

            <div
                className="a2ui-kpi-card__value"
                style={{
                    fontSize: '1.75rem',
                    fontWeight: 700,
                    color: '#f8fafc',
                    marginBottom: delta !== null ? '0.5rem' : 0,
                }}
            >
                {formatValue(value, unit)}
            </div>

            {delta !== null && (
                <div
                    className="a2ui-kpi-card__delta"
                    style={{
                        fontSize: '0.875rem',
                        color: deltaColor,
                        fontWeight: 500,
                    }}
                >
                    <span style={{ marginRight: '0.25rem' }}>{deltaIcon}</span>
                    {formatDelta(delta, deltaType)}
                </div>
            )}
        </div>
    );
}
