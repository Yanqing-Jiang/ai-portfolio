/**
 * Dashboard Styles
 *
 * Theme tokens and style objects for the dashboard components.
 */

import type { CSSProperties } from 'react';

// ============================================================================
// Theme Tokens
// ============================================================================

export const theme = {
    colors: {
        // Base
        background: '#0f172a',
        surface: '#1e293b',
        surfaceHover: '#334155',

        // Text
        textPrimary: '#f8fafc',
        textSecondary: '#94a3b8',
        textMuted: '#64748b',

        // Accent
        primary: '#6366f1',
        primaryHover: '#818cf8',

        // Status
        success: '#22c55e',
        warning: '#fbbf24',
        error: '#ef4444',

        // Border
        border: 'rgba(99, 102, 241, 0.2)',
        borderHover: 'rgba(99, 102, 241, 0.4)',
    },

    spacing: {
        xs: '0.25rem',
        sm: '0.5rem',
        md: '1rem',
        lg: '1.5rem',
        xl: '2rem',
        xxl: '3rem',
    },

    borderRadius: {
        sm: '4px',
        md: '8px',
        lg: '12px',
        xl: '16px',
    },

    fontSizes: {
        xs: '0.75rem',
        sm: '0.875rem',
        md: '1rem',
        lg: '1.125rem',
        xl: '1.25rem',
        xxl: '1.5rem',
        xxxl: '2rem',
    },

    shadows: {
        sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    },
};

// ============================================================================
// Component Styles
// ============================================================================

export const dashboardStyles: Record<string, CSSProperties> = {
    // Page layout
    page: {
        minHeight: '100vh',
        backgroundColor: theme.colors.background,
        color: theme.colors.textPrimary,
        display: 'flex',
        flexDirection: 'column',
    },

    // Header
    header: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: `${theme.spacing.md} ${theme.spacing.xl}`,
        borderBottom: `1px solid ${theme.colors.border}`,
        backgroundColor: theme.colors.surface,
    },

    headerContent: {
        display: 'flex',
        alignItems: 'center',
        gap: theme.spacing.md,
    },

    headerTitle: {
        margin: 0,
        fontSize: theme.fontSizes.xl,
        fontWeight: 600,
        display: 'flex',
        alignItems: 'center',
        gap: theme.spacing.sm,
    },

    headerIcon: {
        fontSize: theme.fontSizes.xxl,
    },

    headerBadge: {
        fontSize: theme.fontSizes.xs,
        padding: `${theme.spacing.xs} ${theme.spacing.sm}`,
        backgroundColor: 'rgba(99, 102, 241, 0.2)',
        color: theme.colors.primary,
        borderRadius: theme.borderRadius.sm,
        fontWeight: 500,
    },

    backButton: {
        padding: `${theme.spacing.sm} ${theme.spacing.md}`,
        backgroundColor: 'transparent',
        color: theme.colors.textSecondary,
        border: `1px solid ${theme.colors.border}`,
        borderRadius: theme.borderRadius.md,
        cursor: 'pointer',
        fontSize: theme.fontSizes.sm,
        transition: 'all 0.2s ease',
    },

    // Main content
    main: {
        flex: 1,
        padding: theme.spacing.xl,
        maxWidth: '1400px',
        margin: '0 auto',
        width: '100%',
    },

    // Dashboard viewer
    viewer: {
        display: 'flex',
        flexDirection: 'column',
        gap: theme.spacing.lg,
    },

    statusBar: {
        display: 'flex',
        alignItems: 'center',
        gap: theme.spacing.sm,
        padding: `${theme.spacing.xs} ${theme.spacing.md}`,
        backgroundColor: theme.colors.surface,
        borderRadius: theme.borderRadius.md,
        alignSelf: 'flex-start',
    },

    statusDot: {
        width: '8px',
        height: '8px',
        borderRadius: '50%',
    },

    statusText: {
        fontSize: theme.fontSizes.xs,
        color: theme.colors.textSecondary,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
    },

    // Create form
    createForm: {
        maxWidth: '600px',
        margin: '0 auto',
        padding: theme.spacing.xxl,
    },

    formTitle: {
        margin: 0,
        fontSize: theme.fontSizes.xxxl,
        fontWeight: 700,
        textAlign: 'center',
        marginBottom: theme.spacing.sm,
    },

    formSubtitle: {
        margin: 0,
        fontSize: theme.fontSizes.md,
        color: theme.colors.textSecondary,
        textAlign: 'center',
        marginBottom: theme.spacing.xl,
    },

    textarea: {
        width: '100%',
        padding: theme.spacing.md,
        backgroundColor: theme.colors.surface,
        border: `1px solid ${theme.colors.border}`,
        borderRadius: theme.borderRadius.lg,
        color: theme.colors.textPrimary,
        fontSize: theme.fontSizes.md,
        resize: 'vertical',
        fontFamily: 'inherit',
    },

    error: {
        margin: `${theme.spacing.sm} 0`,
        padding: theme.spacing.sm,
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        border: `1px solid ${theme.colors.error}`,
        borderRadius: theme.borderRadius.md,
        color: theme.colors.error,
        fontSize: theme.fontSizes.sm,
    },

    submitButton: {
        width: '100%',
        marginTop: theme.spacing.lg,
        padding: `${theme.spacing.md} ${theme.spacing.lg}`,
        backgroundColor: theme.colors.primary,
        color: 'white',
        border: 'none',
        borderRadius: theme.borderRadius.lg,
        fontSize: theme.fontSizes.md,
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
    },

    suggestions: {
        marginTop: theme.spacing.xl,
        paddingTop: theme.spacing.xl,
        borderTop: `1px solid ${theme.colors.border}`,
    },

    suggestionsTitle: {
        margin: 0,
        marginBottom: theme.spacing.md,
        fontSize: theme.fontSizes.sm,
        color: theme.colors.textMuted,
    },

    suggestionsPills: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: theme.spacing.sm,
    },

    suggestionPill: {
        padding: `${theme.spacing.sm} ${theme.spacing.md}`,
        backgroundColor: theme.colors.surface,
        color: theme.colors.textSecondary,
        border: `1px solid ${theme.colors.border}`,
        borderRadius: theme.borderRadius.xl,
        fontSize: theme.fontSizes.sm,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
    },

    // Sidebar
    sidebar: {
        position: 'fixed',
        right: theme.spacing.xl,
        top: '100px',
        width: '200px',
        padding: theme.spacing.lg,
        backgroundColor: theme.colors.surface,
        borderRadius: theme.borderRadius.lg,
        border: `1px solid ${theme.colors.border}`,
    },

    sidebarTitle: {
        margin: 0,
        marginBottom: theme.spacing.md,
        fontSize: theme.fontSizes.sm,
        color: theme.colors.textMuted,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
    },

    historyList: {
        listStyle: 'none',
        margin: 0,
        padding: 0,
    },

    historyItem: {
        display: 'block',
        width: '100%',
        padding: `${theme.spacing.sm} ${theme.spacing.md}`,
        backgroundColor: 'transparent',
        color: theme.colors.textSecondary,
        border: 'none',
        borderRadius: theme.borderRadius.md,
        textAlign: 'left',
        cursor: 'pointer',
        fontSize: theme.fontSizes.sm,
        transition: 'all 0.2s ease',
    },
};
