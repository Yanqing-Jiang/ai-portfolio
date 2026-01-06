/**
 * Widget Error Boundary
 *
 * Component: WidgetErrorBoundary — catches render errors in A2UI widgets.
 * Called from: ComponentRenderer.tsx
 * Invokes: React error boundary lifecycle
 * Why: Prevents cascade failures and provides graceful degradation for widget errors.
 *
 * Implements optimization #14 from optimization-recommendations.md
 */

import React, { Component, type ReactNode, type ErrorInfo } from 'react';
import { motion } from 'framer-motion';

export interface WidgetErrorFallbackProps {
    /** The error that was caught */
    error: Error;
    /** The component ID that failed */
    componentId: string;
    /** The component type that failed */
    componentType?: string;
    /** Callback to reset the error state */
    resetError?: () => void;
}

/**
 * Fallback UI when a widget fails to render.
 * Displays error information with option to retry.
 */
export function WidgetErrorFallback({
    error,
    componentId,
    componentType,
    resetError,
}: WidgetErrorFallbackProps): React.ReactElement {
    const [showDetails, setShowDetails] = React.useState(false);

    return (
        <motion.div
            className="a2ui-widget-error"
            data-component-id={componentId}
            data-component-type={componentType}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            role="alert"
            aria-live="polite"
            style={{
                padding: '1rem',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                borderRadius: '8px',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: 'var(--text-secondary, #666)',
                fontSize: '0.875rem',
            }}
        >
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    marginBottom: '0.5rem',
                }}
            >
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                >
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span style={{ fontWeight: 500 }}>Widget failed to render</span>
            </div>

            <button
                onClick={() => setShowDetails((prev) => !prev)}
                style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-tertiary, #888)',
                    cursor: 'pointer',
                    padding: '0.25rem 0',
                    fontSize: '0.75rem',
                    textDecoration: 'underline',
                }}
                aria-expanded={showDetails}
            >
                {showDetails ? 'Hide details' : 'Show details'}
            </button>

            {showDetails && (
                <div
                    style={{
                        marginTop: '0.5rem',
                        padding: '0.5rem',
                        backgroundColor: 'rgba(0, 0, 0, 0.2)',
                        borderRadius: '4px',
                        fontFamily: 'monospace',
                        fontSize: '0.75rem',
                        overflow: 'auto',
                        maxHeight: '150px',
                    }}
                >
                    <div style={{ marginBottom: '0.25rem', color: 'var(--text-tertiary, #888)' }}>
                        Component: {componentType || 'Unknown'} ({componentId})
                    </div>
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {error.message}
                    </pre>
                    {error.stack && (
                        <details style={{ marginTop: '0.5rem' }}>
                            <summary style={{ cursor: 'pointer', color: 'var(--text-tertiary, #888)' }}>
                                Stack trace
                            </summary>
                            <pre
                                style={{
                                    margin: '0.25rem 0 0',
                                    whiteSpace: 'pre-wrap',
                                    wordBreak: 'break-word',
                                    fontSize: '0.6rem',
                                }}
                            >
                                {error.stack}
                            </pre>
                        </details>
                    )}
                </div>
            )}

            {resetError && (
                <button
                    onClick={resetError}
                    style={{
                        marginTop: '0.75rem',
                        padding: '0.375rem 0.75rem',
                        backgroundColor: 'rgba(239, 68, 68, 0.2)',
                        border: '1px solid rgba(239, 68, 68, 0.4)',
                        borderRadius: '4px',
                        color: 'inherit',
                        cursor: 'pointer',
                        fontSize: '0.75rem',
                        fontWeight: 500,
                    }}
                    aria-label="Retry rendering this widget"
                >
                    Retry
                </button>
            )}
        </motion.div>
    );
}

export interface WidgetErrorBoundaryProps {
    /** Children to render */
    children: ReactNode;
    /** Component ID for error reporting */
    componentId: string;
    /** Component type for error reporting */
    componentType?: string;
    /** Optional custom fallback component */
    fallback?: ReactNode;
    /** Callback when an error is caught */
    onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface WidgetErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

/**
 * Error boundary for A2UI widgets.
 *
 * Catches rendering errors in widget components and displays a fallback UI
 * instead of crashing the entire dashboard.
 *
 * Usage:
 * ```tsx
 * <WidgetErrorBoundary componentId="kpi_1" componentType="KpiCard">
 *     <KpiCard {...props} />
 * </WidgetErrorBoundary>
 * ```
 */
export class WidgetErrorBoundary extends Component<WidgetErrorBoundaryProps, WidgetErrorBoundaryState> {
    constructor(props: WidgetErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): WidgetErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
        const { componentId, componentType, onError } = this.props;

        // Log to console for debugging
        console.error(
            `[WidgetErrorBoundary] Error in ${componentType || 'widget'} (${componentId}):`,
            error,
            errorInfo
        );

        // Call optional error callback
        if (onError) {
            onError(error, errorInfo);
        }
    }

    resetError = (): void => {
        this.setState({ hasError: false, error: null });
    };

    render(): ReactNode {
        const { hasError, error } = this.state;
        const { children, componentId, componentType, fallback } = this.props;

        if (hasError && error) {
            if (fallback) {
                return fallback;
            }

            return (
                <WidgetErrorFallback
                    error={error}
                    componentId={componentId}
                    componentType={componentType}
                    resetError={this.resetError}
                />
            );
        }

        return children;
    }
}

export default WidgetErrorBoundary;
