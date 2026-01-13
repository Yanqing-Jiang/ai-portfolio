/**
 * Dashboard Page
 *
 * Full page component with dashboard creation and viewing.
 */

import React, { useState } from 'react';
import { DashboardViewer, CreateDashboardForm } from './DashboardViewer';
import { dashboardStyles } from './styles';
import { configService } from '../../services/config';

export interface DashboardPageProps {
    /** Initial dashboard ID to load */
    initialDashboardId?: string;
    /** Base URL for API */
    apiBaseUrl?: string;
}

/**
 * Dashboard Page component.
 *
 * Provides a full-page experience for creating and viewing dashboards.
 */
export function DashboardPage({
    initialDashboardId,
    apiBaseUrl = `${configService.getBackendUrl()}/api/dash`,
}: DashboardPageProps): React.ReactElement {
    const [dashboardId, setDashboardId] = useState<string | null>(initialDashboardId || null);
    const [history, setHistory] = useState<string[]>([]);

    const handleCreated = (id: string) => {
        if (dashboardId) {
            setHistory((prev) => [...prev, dashboardId]);
        }
        setDashboardId(id);
    };

    const handleBack = () => {
        setDashboardId(null);
    };

    const handleHistoryClick = (id: string) => {
        setDashboardId(id);
    };

    return (
        <div style={dashboardStyles.page}>
            {/* Header */}
            <header style={dashboardStyles.header}>
                <div style={dashboardStyles.headerContent}>
                    <h1 style={dashboardStyles.headerTitle}>
                        <span style={dashboardStyles.headerIcon}>📊</span>
                        Generative UI Dashboard
                    </h1>
                    <span style={dashboardStyles.headerBadge}>A2UI v0.8</span>
                </div>

                {dashboardId && (
                    <button onClick={handleBack} style={dashboardStyles.backButton}>
                        ← New Dashboard
                    </button>
                )}
            </header>

            {/* Main content */}
            <main style={dashboardStyles.main}>
                {dashboardId ? (
                    <DashboardViewer dashboardId={dashboardId} apiBaseUrl={apiBaseUrl} />
                ) : (
                    <CreateDashboardForm onCreated={handleCreated} apiBaseUrl={apiBaseUrl} />
                )}
            </main>

            {/* History sidebar (if any) */}
            {history.length > 0 && !dashboardId && (
                <aside style={dashboardStyles.sidebar}>
                    <h3 style={dashboardStyles.sidebarTitle}>Recent Dashboards</h3>
                    <ul style={dashboardStyles.historyList}>
                        {history.slice(-5).reverse().map((id) => (
                            <li key={id}>
                                <button
                                    onClick={() => handleHistoryClick(id)}
                                    style={dashboardStyles.historyItem}
                                >
                                    {id.slice(0, 8)}...
                                </button>
                            </li>
                        ))}
                    </ul>
                </aside>
            )}
        </div>
    );
}
