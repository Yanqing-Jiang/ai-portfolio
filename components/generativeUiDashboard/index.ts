/**
 * Generative UI Dashboard Module
 *
 * A2UI v0.8 implementation for financial dashboards.
 */

// A2UI Protocol Layer
export * from './a2ui';

// Renderer
export * from './renderer';

// Main Components
export { DashboardViewer, CreateDashboardForm } from './DashboardViewer';
export { DashboardPage } from './DashboardPage';
export { GenerativeUIPage } from './GenerativeUIPage';
export { default as ClarificationCard } from './ClarificationCard';

// Styles
export { dashboardStyles, theme } from './styles';

