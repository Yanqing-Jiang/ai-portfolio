/**
 * InspectorModeContext — React context for the Truth Toggle.
 *
 * When inspectorMode is true, widgets show:
 * - Evidence badges on insight bullets (computation/classical/interpretation)
 * - Computation receipt popovers on click
 * - The Agent Trace Sidebar becomes visible
 * - Citation chips become interactive
 */

import React, { createContext, useContext } from 'react';

interface InspectorModeState {
    inspectorMode: boolean;
}

const InspectorModeContext = createContext<InspectorModeState>({ inspectorMode: false });

export function InspectorModeProvider({
    inspectorMode,
    children,
}: {
    inspectorMode: boolean;
    children: React.ReactNode;
}) {
    return (
        <InspectorModeContext.Provider value={{ inspectorMode }}>
            {children}
        </InspectorModeContext.Provider>
    );
}

export function useInspectorMode(): boolean {
    return useContext(InspectorModeContext).inspectorMode;
}
