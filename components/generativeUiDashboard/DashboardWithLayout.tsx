/**
 * DashboardWithLayout - Wrapper that provides LayoutContext for A2UI surfaces.
 * 
 * Component: DashboardWithLayout
 * Called from: GenerativeUIPage.tsx
 * Invokes: LayoutProvider, useLayoutEventListener, A2UISurface
 * Why: Bridges LLM-driven layout commands to React component updates.
 * 
 * This component:
 * 1. Wraps content with LayoutProvider for layout state management
 * 2. Uses useLayoutEventListener to handle 'a2ui:layout-change' events
 * 3. Allows LLM query responses to control dashboard layout
 */

import { ReactNode } from 'react';
import { LayoutProvider, type LayoutEmphasis } from './context/LayoutContext';
import { useLayoutEventListener } from './hooks/useLayoutEventListener';

interface DashboardWithLayoutProps {
    children: ReactNode;
    initialEmphasis?: LayoutEmphasis;
}

/**
 * Inner component that uses the layout event listener.
 * Must be inside LayoutProvider.
 * Wrapped in div to accept refs from parent motion wrappers.
 */
function LayoutEventHandler({ children }: { children: ReactNode }) {
    // Listen for layout change events and apply them
    useLayoutEventListener();
    return <div className="layout-event-handler">{children}</div>;
}

/**
 * Wrapper component that provides layout context and event handling.
 */
export function DashboardWithLayout({
    children,
    initialEmphasis = 'balanced'
}: DashboardWithLayoutProps) {
    return (
        <LayoutProvider initialPreferences={{ emphasis: initialEmphasis }}>
            <LayoutEventHandler>
                {children}
            </LayoutEventHandler>
        </LayoutProvider>
    );
}

export default DashboardWithLayout;
