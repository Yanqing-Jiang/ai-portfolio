/**
 * DashboardWithLayout - Wrapper that provides full A2UI context for surfaces.
 *
 * Component: DashboardWithLayout
 * Called from: GenerativeUIPage.tsx
 * Invokes: LayoutProvider, ComponentSwapProvider, ComponentSelectionProvider,
 *          useLayoutEventListener, ComponentActionMenu
 * Why: Bridges LLM-driven layout commands to React component updates and provides
 *      component swapping and selection features.
 *
 * This component:
 * 1. Wraps content with LayoutProvider for layout state management
 * 2. Wraps content with ComponentSwapProvider for component swapping
 * 3. Wraps content with ComponentSelectionProvider for component targeting
 * 4. Uses useLayoutEventListener to handle 'a2ui:layout-change' events
 * 5. Renders ComponentActionMenu for swap interactions
 *
 * Note: LayoutSwitcher removed. ReorderToggle moved to ProcessPanel.
 */

import React, { ReactNode, useRef, useEffect } from 'react';
import { LayoutProvider, useLayoutPreferences, type LayoutEmphasis } from './context/LayoutContext';
import { ComponentSwapProvider } from './context/ComponentSwapContext';
import { ComponentSelectionProvider } from './context/ComponentSelectionContext';
import { useLayoutEventListener } from './hooks/useLayoutEventListener';
import { ComponentActionMenu } from './widgets';

interface DashboardWithLayoutProps {
    children: ReactNode;
    /** Dashboard ID for server-side swaps */
    dashboardId?: string;
    /** Initial layout emphasis (kept for backward compat, no UI control) */
    initialEmphasis?: LayoutEmphasis;
    /** Enable component swapping */
    enableSwapping?: boolean;
}


/**
 * Inner component that uses the layout event listener.
 * Must be inside LayoutProvider.
 * Note: Layout controls (reorder toggle) moved to ProcessPanel.
 * Listens for 'a2ui:toggle-reorder' event from ProcessPanel.
 */
function LayoutEventHandler({
    children,
    enableSwapping = true,
    containerRef,
}: {
    children: ReactNode;
    enableSwapping?: boolean;
    containerRef: React.RefObject<HTMLDivElement>;
}) {
    // Listen for layout change events and apply them
    useLayoutEventListener();

    // Listen for reorder toggle events from ProcessPanel
    const { toggleReorderMode } = useLayoutPreferences();

    useEffect(() => {
        const handleToggleReorder = () => {
            console.log('[DashboardWithLayout] Received toggle-reorder event');
            toggleReorderMode();
        };

        window.addEventListener('a2ui:toggle-reorder', handleToggleReorder);
        return () => {
            window.removeEventListener('a2ui:toggle-reorder', handleToggleReorder);
        };
    }, [toggleReorderMode]);

    return (
        <div className="layout-event-handler" ref={containerRef}>
            {/* Main content with selection context */}
            <ComponentSelectionProvider containerRef={containerRef}>
                {children}

                {/* Component action menu (appears when component is selected) */}
                {enableSwapping && <ComponentActionMenu />}
            </ComponentSelectionProvider>
        </div>
    );
}

/**
 * Wrapper component that provides full A2UI context and controls.
 *
 * Features enabled:
 * - Drag-and-drop reordering (controlled via LayoutContext, toggle in ProcessPanel)
 * - Component swapping (click to swap components)
 * - LLM-driven layout commands via events
 *
 * Note: Layout switching removed. Reorder toggle moved to ProcessPanel.
 */
export function DashboardWithLayout({
    children,
    dashboardId,
    initialEmphasis = 'balanced',
    enableSwapping = true,
}: DashboardWithLayoutProps) {
    const containerRef = useRef<HTMLDivElement>(null);

    return (
        <LayoutProvider initialPreferences={{ emphasis: initialEmphasis }}>
            <ComponentSwapProvider dashboardId={dashboardId}>
                <LayoutEventHandler
                    enableSwapping={enableSwapping}
                    containerRef={containerRef as React.RefObject<HTMLDivElement>}
                >
                    {children}
                </LayoutEventHandler>
            </ComponentSwapProvider>
        </LayoutProvider>
    );
}

export default DashboardWithLayout;
