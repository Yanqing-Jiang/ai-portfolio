/**
 * Comparison KPI Card Widget
 *
 * Displays two values side-by-side with delta for peer comparison.
 * 
 * Component: ComparisonKpiCard — displays a comparative KPI (e.g., QCOM vs AVGO margin).
 * Called from: ComponentRenderer via Registry
 * Invokes: DataBinder.resolveString, DataBinder.resolveNumber
 * Why: Shows peer comparison metrics at a glance in A2UI dashboards.
 * 
 * Accessibility: Implements ARIA labels, keyboard navigation, and screen reader support.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import { resolveString, resolveNumber } from '../../a2ui/DataBinder';

export interface ComparisonKpiCardProps {
    label: { literalString?: string; path?: string };
    primaryLabel: { literalString?: string; path?: string };
    primaryValue: { literalNumber?: number; path?: string };
    secondaryLabel: { literalString?: string; path?: string };
    secondaryValue: { literalNumber?: number; path?: string };
    unit?: { literalString?: string; path?: string };
    delta?: { literalNumber?: number; path?: string };
}

export function ComparisonKpiCard({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const kpiProps = props as unknown as ComparisonKpiCardProps;

    const label = resolveString(kpiProps.label, dataModel, 'Metric');
    const primaryLabel = resolveString(kpiProps.primaryLabel, dataModel, 'Primary');
    const primaryValue = resolveNumber(kpiProps.primaryValue, dataModel, 0);
    const secondaryLabel = resolveString(kpiProps.secondaryLabel, dataModel, 'Secondary');
    const secondaryValue = resolveNumber(kpiProps.secondaryValue, dataModel, 0);
    const unit = resolveString(kpiProps.unit, dataModel, '%');
    const delta = kpiProps.delta ? resolveNumber(kpiProps.delta, dataModel, undefined) : null;

    // Format value with unit
    const formatValue = (val: number, u: string): string => {
        if (u === '$') {
            return `$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }
        if (u === '%') {
            return `${val.toFixed(1)}%`;
        }
        if (u === 'M') {
            return `${(val / 1_000_000).toFixed(2)}M`;
        }
        if (u === 'B') {
            return `${(val / 1_000_000_000).toFixed(2)}B`;
        }
        return val.toLocaleString();
    };

    // Compute delta if not provided
    const computedDelta = delta ?? (primaryValue - secondaryValue);
    const deltaPrefix = computedDelta >= 0 ? '+' : '';
    const deltaColor = computedDelta >= 0 ? '#22c55e' : '#ef4444';
    const deltaIcon = computedDelta >= 0 ? '▲' : '▼';

    // Accessibility
    const formattedPrimary = formatValue(primaryValue, unit);
    const formattedSecondary = formatValue(secondaryValue, unit);
    const ariaLabel = `${label}: ${primaryLabel} ${formattedPrimary} versus ${secondaryLabel} ${formattedSecondary}, difference ${deltaPrefix}${computedDelta.toFixed(1)}${unit === '%' ? ' points' : ''}`;

    return (
        <div
            className="a2ui-comparison-kpi-card"
            data-component-id={componentId}
            role="figure"
            aria-label={ariaLabel}
            tabIndex={0}
            style={{
                padding: '1rem',
                backgroundColor: 'rgba(30, 41, 59, 0.5)',
                borderRadius: '8px',
                textAlign: 'center',
                minWidth: '200px',
            }}
        >
            {/* Label */}
            <div
                className="a2ui-comparison-kpi-card__label"
                aria-hidden="true"
                style={{
                    fontSize: '0.75rem',
                    color: '#94a3b8',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    marginBottom: '0.75rem',
                }}
            >
                {label}
            </div>

            {/* Values row */}
            <div
                className="a2ui-comparison-kpi-card__values"
                style={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    gap: '1rem',
                    marginBottom: '0.5rem',
                }}
            >
                {/* Primary value */}
                <div style={{ textAlign: 'center' }}>
                    <div
                        style={{
                            fontSize: '0.65rem',
                            color: '#64748b',
                            textTransform: 'uppercase',
                            marginBottom: '0.25rem',
                        }}
                    >
                        {primaryLabel}
                    </div>
                    <div
                        style={{
                            fontSize: '1.5rem',
                            fontWeight: 700,
                            color: '#f8fafc',
                        }}
                    >
                        {formattedPrimary}
                    </div>
                </div>

                {/* VS separator */}
                <div
                    style={{
                        fontSize: '0.75rem',
                        color: '#475569',
                        fontWeight: 500,
                    }}
                    aria-hidden="true"
                >
                    vs
                </div>

                {/* Secondary value */}
                <div style={{ textAlign: 'center' }}>
                    <div
                        style={{
                            fontSize: '0.65rem',
                            color: '#64748b',
                            textTransform: 'uppercase',
                            marginBottom: '0.25rem',
                        }}
                    >
                        {secondaryLabel}
                    </div>
                    <div
                        style={{
                            fontSize: '1.5rem',
                            fontWeight: 700,
                            color: '#f8fafc',
                        }}
                    >
                        {formattedSecondary}
                    </div>
                </div>
            </div>

            {/* Delta */}
            <div
                className="a2ui-comparison-kpi-card__delta"
                role="status"
                style={{
                    fontSize: '0.8rem',
                    color: deltaColor,
                    fontWeight: 500,
                }}
            >
                <span style={{ marginRight: '0.25rem' }} aria-hidden="true">
                    {deltaIcon}
                </span>
                {deltaPrefix}{Math.abs(computedDelta).toFixed(1)}{unit === '%' ? ' pts' : ''}
            </div>
        </div>
    );
}
