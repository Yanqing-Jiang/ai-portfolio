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
export { ClarificationOverlay } from './ClarificationOverlay';
export type { ClarificationRequest, ClarificationOption } from './ClarificationOverlay';
export { FollowUpSuggestions } from './FollowUpSuggestions';
export type { FollowUpSuggestion } from './FollowUpSuggestions';
export { SkillHeaderBadge } from './SkillHeaderBadge';
export type { SkillInfo } from './SkillHeaderBadge';

// Styles
export { dashboardStyles, theme } from './styles';

