/**
 * Dashboard Viewer
 *
 * Main component for rendering A2UI dashboards.
 * Wraps content with LayoutProvider and ComponentSwapProvider for
 * client-side layout switching and component swapping.
 */

import React, { useCallback, useState, useRef } from 'react';
import { useA2UIStream, useSurface } from './a2ui';
import { A2UISurface, A2UISurfaceLoading, A2UISurfaceError } from './renderer';
import { dashboardStyles } from './styles';

// Context providers for layout/swapping
import { LayoutProvider, ComponentSwapProvider, ComponentSelectionProvider } from './context';
import { LayoutSwitcher, ComponentActionMenu } from './widgets';

export interface DashboardViewerProps {
    /** Dashboard ID to load */
    dashboardId: string;
    /** Optional stream URL override */
    streamUrl?: string;
    /** Base URL for API */
    apiBaseUrl?: string;
    /** CSS class name */
    className?: string;
    /** Enable layout switching controls */
    enableLayoutControls?: boolean;
    /** Enable component swapping */
    enableSwapping?: boolean;
}

/**
 * Dashboard Viewer component.
 *
 * Connects to an A2UI stream and renders the dashboard.
 * Now includes context providers for layout preferences and component swapping.
 */
export function DashboardViewer({
    dashboardId,
    streamUrl,
    apiBaseUrl = '/api/dash',
    className = '',
    enableLayoutControls = true,
    enableSwapping = true,
}: DashboardViewerProps): React.ReactElement {
    const url = streamUrl || `${apiBaseUrl}/${dashboardId}/stream`;
    const containerRef = useRef<HTMLDivElement>(null);
    const [currentLayout, setCurrentLayout] = useState('balanced');

    const [state, actions] = useA2UIStream(url, {
        autoConnect: true,
        dashboardId,
        apiBaseUrl,
    });

    // Get the main surface
    const surfaceId = `dashboard_main`;
    const { surface, dataModel } = useSurface(state, surfaceId);

    // Handle user actions
    const handleAction = useCallback(
        async (actionName: string, context: Record<string, unknown>) => {
            try {
                const result = await actions.sendAction({
                    name: actionName,
                    surfaceId,
                    sourceComponentId: 'unknown',
                    timestamp: new Date().toISOString(),
                    context,
                });

                console.log('Action result:', result);

                // If action requires data refresh, reconnect stream
                if ((result as { refresh_data?: boolean })?.refresh_data) {
                    actions.reconnect();
                }
            } catch (error) {
                console.error('Action failed:', error);
            }
        },
        [actions, surfaceId]
    );

    // Handle layout change
    const handleLayoutChange = useCallback((emphasis: string) => {
        setCurrentLayout(emphasis);
    }, []);

    // Render loading state
    if (state.isLoading && !surface?.root) {
        return <A2UISurfaceLoading />;
    }

    // Render error state
    if (state.error && !surface?.root) {
        return <A2UISurfaceError error={state.error} onRetry={actions.reconnect} />;
    }

    // Render surface
    if (!surface) {
        return <A2UISurfaceLoading />;
    }

    return (
        <LayoutProvider initialPreferences={{ emphasis: currentLayout as 'balanced' | 'focus_chart' | 'focus_table' | 'focus_news' }}>
            <ComponentSwapProvider>
                <div
                    ref={containerRef}
                    className={`dashboard-viewer ${className}`}
                    style={dashboardStyles.viewer}
                >
                    {/* Header with connection status and layout controls */}
                    <div style={{ ...dashboardStyles.statusBar, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span
                                style={{
                                    ...dashboardStyles.statusDot,
                                    backgroundColor: state.isConnected ? '#22c55e' : '#fbbf24',
                                }}
                            />
                            <span style={dashboardStyles.statusText}>
                                {state.isConnected ? 'Connected' : state.isDone ? 'Complete' : 'Connecting...'}
                            </span>
                        </div>

                        {/* Layout Switcher */}
                        {enableLayoutControls && (
                            <LayoutSwitcher
                                currentLayout={currentLayout}
                                surfaceId={surfaceId}
                                onLayoutChange={handleLayoutChange}
                                disabled={!state.isDone}
                            />
                        )}
                    </div>

                    {/* Main surface with selection context for component targeting */}
                    <ComponentSelectionProvider containerRef={containerRef}>
                        <A2UISurface
                            surface={surface}
                            dataModel={dataModel}
                            onAction={handleAction}
                            className="dashboard-surface"
                        />

                        {/* Component action menu (appears when component is selected) */}
                        {enableSwapping && <ComponentActionMenu />}
                    </ComponentSelectionProvider>
                </div>
            </ComponentSwapProvider>
        </LayoutProvider>
    );
}

/**
 * Create Dashboard Form
 *
 * Simple form to create a new dashboard from a question.
 */
export function CreateDashboardForm({
    onCreated,
    apiBaseUrl = '/api/dash',
}: {
    onCreated: (dashboardId: string) => void;
    apiBaseUrl?: string;
}): React.ReactElement {
    const [question, setQuestion] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!question.trim()) return;

        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch(`${apiBaseUrl}/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question }),
            });

            if (!response.ok) {
                throw new Error(`Failed to create dashboard: ${response.statusText}`);
            }

            const data = await response.json();
            onCreated(data.dashboard_id);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setIsLoading(false);
        }
    };

    const suggestions = [
        'Why did NVDA drop on Dec 18?',
        'Compare AAPL vs MSFT vs SPY',
        'Show me TSLA quarterly revenue trend',
        'What\'s the correlation between tech stocks?',
    ];

    return (
        <div style={dashboardStyles.createForm}>
            <h2 style={dashboardStyles.formTitle}>Create a Dashboard</h2>
            <p style={dashboardStyles.formSubtitle}>
                Ask a question about stocks, financials, or market trends
            </p>

            <form onSubmit={handleSubmit}>
                <textarea
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="E.g., Why did NVDA drop on Dec 18?"
                    style={dashboardStyles.textarea}
                    rows={3}
                />

                {error && <p style={dashboardStyles.error}>{error}</p>}

                <button
                    type="submit"
                    disabled={isLoading || !question.trim()}
                    style={{
                        ...dashboardStyles.submitButton,
                        opacity: isLoading || !question.trim() ? 0.6 : 1,
                    }}
                >
                    {isLoading ? 'Creating...' : 'Create Dashboard'}
                </button>
            </form>

            <div style={dashboardStyles.suggestions}>
                <p style={dashboardStyles.suggestionsTitle}>Try these:</p>
                <div style={dashboardStyles.suggestionsPills}>
                    {suggestions.map((s) => (
                        <button
                            key={s}
                            onClick={() => setQuestion(s)}
                            style={dashboardStyles.suggestionPill}
                        >
                            {s}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}
