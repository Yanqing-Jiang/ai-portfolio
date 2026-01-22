/**
 * KPI Card Widget
 *
 * Single metric display with optional delta indicator.
 *
 * Component: KpiCard — displays a key performance indicator.
 * Called from: ComponentRenderer via Registry
 * Invokes: DataBinder.resolveString, DataBinder.resolveNumber, useAnimatedNumber
 * Why: Provides at-a-glance metrics in A2UI dashboards.
 *
 * Accessibility: Implements optimization #15 with ARIA labels,
 * keyboard navigation, and screen reader support.
 *
 * Animation: Uses useAnimatedNumber for smooth value transitions.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import { resolveString, resolveNumber } from '../../a2ui/DataBinder';
import type { KpiCardProps } from '../../a2ui/types';
import { useAnimatedNumber } from '../../hooks/useAnimatedNumber';

export function KpiCard({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const kpiProps = props as unknown as KpiCardProps;

    const label = resolveString(kpiProps.label, dataModel, 'Value');
    const rawValue = resolveNumber(kpiProps.value, dataModel, 0);
    const unit = resolveString(kpiProps.unit, dataModel, '');
    const rawDelta = kpiProps.delta ? resolveNumber(kpiProps.delta, dataModel, 0) : null;
    const deltaType = resolveString(kpiProps.deltaType, dataModel, 'absolute');

    // Animate the numeric values
    const value = useAnimatedNumber(rawValue, {
        duration: 800,
        easing: 'easeOutExpo',
        animateOnMount: true,
    });
    // FIX: Always call hook unconditionally (React rules of hooks)
    // Pass 0 as fallback when rawDelta is null to maintain consistent hook count
    const animatedDelta = useAnimatedNumber(rawDelta ?? 0, { duration: 600, easing: 'easeOut' });
    const delta = rawDelta !== null ? animatedDelta : null;

    // Only show N/A when value is explicitly null/undefined, not when 0
    // (0% margin is a valid value, different from "no data")
    const shouldShowNA = rawValue === null || rawValue === undefined;

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

    // Delta color (based on raw value for consistency)
    const deltaColor = rawDelta !== null ? (rawDelta >= 0 ? '#22c55e' : '#ef4444') : '#94a3b8';
    const deltaIcon = rawDelta !== null ? (rawDelta >= 0 ? '↑' : '↓') : '';

    // Accessibility: Build descriptive labels
    const formattedValue = shouldShowNA ? 'N/A' : formatValue(value, unit);
    const ariaLabel = `${label}: ${formattedValue}`;
    const deltaId = `${componentId}-delta`;
    const deltaAriaLabel = rawDelta !== null
        ? `Change: ${rawDelta >= 0 ? 'up' : 'down'} ${formatDelta(Math.abs(rawDelta), deltaType)}`
        : undefined;

    return (
        <div
            className="a2ui-kpi-card"
            data-component-id={componentId}
            // Accessibility: Role and labels (Optimization #15)
            role="figure"
            aria-label={ariaLabel}
            aria-describedby={delta !== null ? deltaId : undefined}
            tabIndex={0}
            style={{
                padding: 'clamp(0.75rem, 3vw, 1rem)', // Responsive padding
                backgroundColor: 'rgba(30, 41, 59, 0.5)',
                borderRadius: '8px',
                textAlign: 'center',
                minWidth: '120px', // Ensure minimum readable width
            }}
        >
            <div
                className="a2ui-kpi-card__label"
                // Accessibility: Label is decorative, main info in aria-label
                aria-hidden="true"
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
                // Accessibility: Announce value changes
                aria-live="polite"
                aria-atomic="true"
                style={{
                    fontSize: 'clamp(1.25rem, 4vw, 1.75rem)', // Responsive font size
                    fontWeight: 700,
                    color: '#f8fafc',
                    marginBottom: delta !== null ? '0.5rem' : 0,
                    wordBreak: 'break-word', // Prevent overflow on very long values
                }}
            >
                {formattedValue}
            </div>

            {delta !== null && !shouldShowNA && (
                <div
                    id={deltaId}
                    className="a2ui-kpi-card__delta"
                    // Accessibility: Describe the change direction and amount
                    role="status"
                    aria-label={deltaAriaLabel}
                    style={{
                        fontSize: '0.875rem',
                        color: deltaColor,
                        fontWeight: 500,
                    }}
                >
                    <span style={{ marginRight: '0.25rem' }} aria-hidden="true">
                        {deltaIcon}
                    </span>
                    {formatDelta(delta, deltaType)}
                </div>
            )}
        </div>
    );
}

