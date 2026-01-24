/**
 * ComponentSelectionContext - Track user's component selection for targeting.
 *
 * Context: ComponentSelectionContext
 * Called from: GenerativeUIPage.tsx (provider), action menu (consumer)
 * Invokes: React.createContext, DOM event listeners
 * Why: Enables targeted component actions via click or text input.
 */

import { createContext, useContext, useState, useCallback, useEffect, ReactNode, RefObject } from 'react';

// ============================================================================
// Types
// ============================================================================

export interface SelectedComponent {
    /** Unique component ID from data-component-id */
    componentId: string;
    /** Current component type (may be swapped) */
    componentType: string;
    /** Original component type before any swaps */
    originalType: string;
    /** Bounding rect for positioning action menu */
    boundingRect: DOMRect | null;
}

export interface SelectionContextValue {
    /** Currently selected component, or null if none */
    selectedComponent: SelectedComponent | null;
    /** Programmatically select a component */
    selectComponent: (componentId: string, componentType: string, originalType: string) => void;
    /** Clear the current selection */
    clearSelection: () => void;
    /** Select a component by text query (natural language parsing) */
    selectByText: (query: string, allComponents: Map<string, string>) => boolean;
    /** Whether the action menu is visible */
    showActionMenu: boolean;
    /** Toggle action menu visibility */
    setShowActionMenu: (show: boolean) => void;
}

// ============================================================================
// Keyword mappings for text-based targeting
// ============================================================================

/**
 * Maps natural language keywords to component types.
 * Used for text-based component selection (e.g., "focus on the chart").
 */
const COMPONENT_KEYWORDS: Record<string, string[]> = {
    PriceChart: ['chart', 'price chart', 'stock chart', 'candlestick', 'trading chart', 'price'],
    MetricChart: ['metric chart', 'line chart', 'bar chart', 'area chart', 'trend chart', 'graph'],
    DataTable: ['table', 'data table', 'grid', 'rows', 'columns', 'data'],
    NewsTimeline: ['news', 'timeline', 'events', 'headlines', 'articles'],
    ExplainMovePanel: ['explanation', 'analysis', 'insight', 'summary', 'why', 'explain'],
    KpiCard: ['kpi', 'metric', 'card', 'number', 'value', 'indicator'],
    CorrelationMatrix: ['correlation', 'matrix', 'heatmap', 'relationship'],
    PeerComparePanel: ['comparison', 'peers', 'compare', 'vs', 'versus'],
};

/**
 * Find a component type that matches keywords in the query.
 */
export function findComponentByKeyword(query: string): string | null {
    const lower = query.toLowerCase();

    for (const [componentType, keywords] of Object.entries(COMPONENT_KEYWORDS)) {
        for (const keyword of keywords) {
            if (lower.includes(keyword)) {
                return componentType;
            }
        }
    }

    return null;
}

// ============================================================================
// Context
// ============================================================================

const SelectionContext = createContext<SelectionContextValue | null>(null);

// ============================================================================
// Provider
// ============================================================================

export interface ComponentSelectionProviderProps {
    children: ReactNode;
    /** Ref to the container element for click event handling */
    containerRef: RefObject<HTMLElement | null>;
}

export function ComponentSelectionProvider({
    children,
    containerRef
}: ComponentSelectionProviderProps) {
    const [selectedComponent, setSelectedComponent] = useState<SelectedComponent | null>(null);
    const [showActionMenu, setShowActionMenu] = useState(false);

    // Handle click events to select components
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        const handleClick = (event: MouseEvent) => {
            const target = event.target as HTMLElement;

            // Ignore clicks on action menu (prevents clearing selection before button handler runs)
            if (target.closest('[data-ignore-selection="true"]')) {
                return;
            }

            // FIX: Ignore clicks on interactive elements (buttons, links, inputs)
            // This prevents swap menu from opening when clicking tabs, buttons, etc.
            if (target.closest('button, a, input, select, textarea, [role="button"], [role="tab"]')) {
                return;
            }

            // Find the closest component wrapper
            const componentEl = target.closest('[data-component-id]') as HTMLElement | null;

            if (componentEl) {
                const componentId = componentEl.getAttribute('data-component-id') || '';
                const componentType = componentEl.getAttribute('data-component-type') || '';
                const originalType = componentEl.getAttribute('data-original-type') || componentType;
                const rect = componentEl.getBoundingClientRect();

                setSelectedComponent({
                    componentId,
                    componentType,
                    originalType,
                    boundingRect: rect,
                });
                setShowActionMenu(true);
                event.stopPropagation();
            } else {
                // Clicked outside any component - clear selection
                setSelectedComponent(null);
                setShowActionMenu(false);
            }
        };

        container.addEventListener('click', handleClick);
        return () => container.removeEventListener('click', handleClick);
    }, [containerRef]);

    // Programmatically select a component
    const selectComponent = useCallback((
        componentId: string,
        componentType: string,
        originalType: string
    ) => {
        const el = document.querySelector(`[data-component-id="${componentId}"]`);
        setSelectedComponent({
            componentId,
            componentType,
            originalType,
            boundingRect: el?.getBoundingClientRect() || null,
        });
        setShowActionMenu(true);
    }, []);

    // Clear selection
    const clearSelection = useCallback(() => {
        setSelectedComponent(null);
        setShowActionMenu(false);
    }, []);

    // Select component by text query (for conversational targeting)
    const selectByText = useCallback((
        query: string,
        allComponents: Map<string, string>
    ): boolean => {
        const targetType = findComponentByKeyword(query);
        if (!targetType) return false;

        // Find first component of matching type
        for (const [componentId, componentType] of allComponents) {
            if (componentType === targetType) {
                selectComponent(componentId, componentType, componentType);
                return true;
            }
        }

        return false;
    }, [selectComponent]);

    const value: SelectionContextValue = {
        selectedComponent,
        selectComponent,
        clearSelection,
        selectByText,
        showActionMenu,
        setShowActionMenu,
    };

    return (
        <SelectionContext.Provider value={value}>
            {children}
        </SelectionContext.Provider>
    );
}

// ============================================================================
// Hook
// ============================================================================

export function useComponentSelection(): SelectionContextValue {
    const ctx = useContext(SelectionContext);
    if (!ctx) {
        throw new Error('useComponentSelection must be used within ComponentSelectionProvider');
    }
    return ctx;
}

export default SelectionContext;
