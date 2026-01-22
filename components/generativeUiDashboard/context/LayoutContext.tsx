/**
 * LayoutContext - Manages dashboard layout preferences.
 *
 * Context: LayoutContext
 * Called from: GenerativeUIPage.tsx (provider)
 * Invokes: React.createContext, localStorage for persistence
 * Why: Enables client-side layout switching without backend calls.
 */

import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';

// ============================================================================
// Types
// ============================================================================

export type LayoutEmphasis = 'balanced' | 'focus_chart' | 'focus_table' | 'focus_news';

export interface LayoutPreferences {
    /** Current emphasis mode for the dashboard */
    emphasis: LayoutEmphasis;
    /** List of widget types that are hidden */
    hiddenWidgets: string[];
    /** Custom widget ordering (widget type IDs) - legacy global order */
    widgetOrder: string[];
    /** Per-container ordering: Map<containerId, childIds[]> */
    containerOrder: Record<string, string[]>;
    /** Whether reorder mode is enabled */
    reorderModeEnabled: boolean;
}

export interface LayoutContextValue {
    /** Current layout preferences */
    preferences: LayoutPreferences;
    /** Set the emphasis mode */
    setEmphasis: (emphasis: LayoutEmphasis) => void;
    /** Toggle widget visibility */
    toggleWidget: (widgetType: string) => void;
    /** Hide a specific widget type */
    hideWidget: (widgetType: string) => void;
    /** Show a specific widget type */
    showWidget: (widgetType: string) => void;
    /** Check if widget type is hidden */
    isWidgetHidden: (widgetType: string) => boolean;
    /** Reorder widgets (legacy global) */
    reorderWidgets: (newOrder: string[]) => void;
    /** Reorder children within a specific container */
    reorderContainer: (containerId: string, newOrder: string[]) => void;
    /** Get order for a specific container */
    getContainerOrder: (containerId: string) => string[] | null;
    /** Toggle reorder mode */
    toggleReorderMode: () => void;
    /** Set reorder mode */
    setReorderMode: (enabled: boolean) => void;
    /** Reset to default layout */
    resetLayout: () => void;
    /** Get CSS classes for emphasis mode */
    getEmphasisClasses: (componentType: string) => string;
}

// ============================================================================
// Default values
// ============================================================================

const DEFAULT_PREFERENCES: LayoutPreferences = {
    emphasis: 'balanced',
    hiddenWidgets: [],
    widgetOrder: [],
    containerOrder: {},
    reorderModeEnabled: false,
};

const STORAGE_KEY = 'a2ui-layout-preferences';

// ============================================================================
// Emphasis CSS mappings
// ============================================================================

/**
 * Maps emphasis modes to CSS classes for different component types.
 * Returns responsive grid/size classes based on current emphasis.
 */
const EMPHASIS_CLASSES: Record<LayoutEmphasis, Record<string, string>> = {
    balanced: {
        PriceChart: 'col-span-1',
        MetricChart: 'col-span-1',
        DataTable: 'col-span-1',
        NewsTimeline: 'col-span-1',
        KpiCard: '',
        default: '',
    },
    focus_chart: {
        PriceChart: 'col-span-2 row-span-2',
        MetricChart: 'col-span-2',
        DataTable: 'col-span-1 text-sm',
        NewsTimeline: 'col-span-1',
        KpiCard: 'scale-90',
        default: '',
    },
    focus_table: {
        PriceChart: 'col-span-1',
        MetricChart: 'col-span-1',
        DataTable: 'col-span-2 row-span-2',
        NewsTimeline: 'col-span-1',
        KpiCard: '',
        default: '',
    },
    focus_news: {
        PriceChart: 'col-span-1',
        MetricChart: 'col-span-1',
        DataTable: 'col-span-1',
        NewsTimeline: 'col-span-2 row-span-2',
        KpiCard: '',
        default: '',
    },
};

// ============================================================================
// Context
// ============================================================================

const LayoutContext = createContext<LayoutContextValue | null>(null);

// ============================================================================
// Provider
// ============================================================================

export interface LayoutProviderProps {
    children: ReactNode;
    /** Optional initial preferences (overrides localStorage) */
    initialPreferences?: Partial<LayoutPreferences>;
}

export function LayoutProvider({ children, initialPreferences }: LayoutProviderProps) {
    // Initialize preferences from localStorage or defaults
    const [preferences, setPreferences] = useState<LayoutPreferences>(() => {
        if (typeof window === 'undefined') return { ...DEFAULT_PREFERENCES, ...initialPreferences };

        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored);
                return { ...DEFAULT_PREFERENCES, ...parsed, ...initialPreferences };
            }
        } catch (e) {
            console.warn('[LayoutContext] Failed to load preferences from localStorage:', e);
        }

        return { ...DEFAULT_PREFERENCES, ...initialPreferences };
    });

    // Persist to localStorage whenever preferences change
    useEffect(() => {
        if (typeof window === 'undefined') return;

        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
        } catch (e) {
            console.warn('[LayoutContext] Failed to save preferences to localStorage:', e);
        }
    }, [preferences]);

    // Set emphasis mode
    const setEmphasis = useCallback((emphasis: LayoutEmphasis) => {
        setPreferences(prev => ({ ...prev, emphasis }));
    }, []);

    // Toggle widget visibility
    const toggleWidget = useCallback((widgetType: string) => {
        setPreferences(prev => {
            const hidden = new Set(prev.hiddenWidgets);
            if (hidden.has(widgetType)) {
                hidden.delete(widgetType);
            } else {
                hidden.add(widgetType);
            }
            return { ...prev, hiddenWidgets: Array.from(hidden) };
        });
    }, []);

    // Hide a widget type
    const hideWidget = useCallback((widgetType: string) => {
        setPreferences(prev => {
            const hidden = new Set(prev.hiddenWidgets);
            hidden.add(widgetType);
            return { ...prev, hiddenWidgets: Array.from(hidden) };
        });
    }, []);

    // Show a widget type
    const showWidget = useCallback((widgetType: string) => {
        setPreferences(prev => {
            const hidden = new Set(prev.hiddenWidgets);
            hidden.delete(widgetType);
            return { ...prev, hiddenWidgets: Array.from(hidden) };
        });
    }, []);

    // Check if widget is hidden
    const isWidgetHidden = useCallback((widgetType: string): boolean => {
        return preferences.hiddenWidgets.includes(widgetType);
    }, [preferences.hiddenWidgets]);

    // Reorder widgets (legacy global)
    const reorderWidgets = useCallback((newOrder: string[]) => {
        setPreferences(prev => ({ ...prev, widgetOrder: newOrder }));
    }, []);

    // Reorder children within a specific container
    const reorderContainer = useCallback((containerId: string, newOrder: string[]) => {
        setPreferences(prev => ({
            ...prev,
            containerOrder: {
                ...prev.containerOrder,
                [containerId]: newOrder,
            },
        }));
    }, []);

    // Get order for a specific container
    const getContainerOrder = useCallback((containerId: string): string[] | null => {
        return preferences.containerOrder[containerId] || null;
    }, [preferences.containerOrder]);

    // Toggle reorder mode
    const toggleReorderMode = useCallback(() => {
        setPreferences(prev => ({
            ...prev,
            reorderModeEnabled: !prev.reorderModeEnabled,
        }));
    }, []);

    // Set reorder mode
    const setReorderMode = useCallback((enabled: boolean) => {
        setPreferences(prev => ({
            ...prev,
            reorderModeEnabled: enabled,
        }));
    }, []);

    // Reset to defaults
    const resetLayout = useCallback(() => {
        setPreferences(DEFAULT_PREFERENCES);
    }, []);

    // Get emphasis classes for a component type
    const getEmphasisClasses = useCallback((componentType: string): string => {
        const emphasisMap = EMPHASIS_CLASSES[preferences.emphasis];
        return emphasisMap[componentType] || emphasisMap.default || '';
    }, [preferences.emphasis]);

    const value: LayoutContextValue = {
        preferences,
        setEmphasis,
        toggleWidget,
        hideWidget,
        showWidget,
        isWidgetHidden,
        reorderWidgets,
        reorderContainer,
        getContainerOrder,
        toggleReorderMode,
        setReorderMode,
        resetLayout,
        getEmphasisClasses,
    };

    return (
        <LayoutContext.Provider value={value}>
            {children}
        </LayoutContext.Provider>
    );
}

// ============================================================================
// Hook
// ============================================================================

export function useLayoutPreferences(): LayoutContextValue {
    const ctx = useContext(LayoutContext);
    if (!ctx) {
        throw new Error('useLayoutPreferences must be used within LayoutProvider');
    }
    return ctx;
}

export default LayoutContext;
