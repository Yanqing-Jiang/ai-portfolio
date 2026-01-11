// --- Function/Class Map ---
// Hook: useLayoutEventListener
//   Role: Listen for layout-change events and apply them to LayoutContext.
//   Called from: components/generativeUiDashboard/DashboardWithLayout.tsx
//   Invokes: LayoutContext setters (setEmphasis/hide/show/reorder/reset).
//   Why: Bridges LLM layout intents from /query to client-side layout state.
// --- End Function/Class Map ---
/**
 * useLayoutEventListener - Listens for layout change events and applies them.
 * 
 * Hook: useLayoutEventListener
 * Called from: Components within LayoutProvider (e.g., DashboardWithLayout)
 * Invokes: useLayoutPreferences context methods
 * Why: Bridges custom events from query responses to React LayoutContext updates.
 * 
 * This enables LLM-driven layout control by listening for 'a2ui:layout-change' events
 * dispatched when the /query endpoint returns a modify_layout intent.
 */

import { useEffect } from 'react';
import { useLayoutPreferences, type LayoutEmphasis } from '../context/LayoutContext';

interface LayoutChangeEvent extends CustomEvent {
    detail: {
        action: string;
        params: Record<string, unknown>;
        dashboardId?: string;
    };
}

/**
 * Hook to listen for layout change events and apply them to LayoutContext.
 * Must be used within a LayoutProvider.
 */
export function useLayoutEventListener(): void {
    const {
        setEmphasis,
        hideWidget,
        showWidget,
        toggleWidget,
        reorderWidgets,
        resetLayout,
    } = useLayoutPreferences();

    useEffect(() => {
        const handleLayoutChange = (event: Event) => {
            const { action, params } = (event as LayoutChangeEvent).detail;

            console.log('[LayoutEventListener] Received layout change:', action, params);

            switch (action) {
                case 'set_emphasis':
                case 'change_emphasis':
                    if (params.emphasis) {
                        setEmphasis(params.emphasis as LayoutEmphasis);
                    }
                    break;

                case 'hide_widget':
                case 'toggle_widget': {
                    const target = params.target || params.widget_type || params.component || params.widget;
                    const visible = typeof params.visible === 'boolean' ? params.visible : undefined;
                    if (!target) break;

                    if (action === 'hide_widget') {
                        hideWidget(target as string);
                        break;
                    }

                    if (visible === true) {
                        showWidget(target as string);
                        break;
                    }

                    if (visible === false) {
                        hideWidget(target as string);
                        break;
                    }

                    toggleWidget(target as string);
                    break;
                }

                case 'show_widget': {
                    const target = params.target || params.widget_type || params.component || params.widget;
                    if (target) {
                        showWidget(target as string);
                    }
                    break;
                }

                case 'reorder_widgets':
                case 'reorder': {
                    const order = params.order || params.widget_order || params.new_order;
                    if (Array.isArray(order)) {
                        reorderWidgets(order as string[]);
                    } else if (params.infer_order) {
                        // Infer order based on hint from LLM
                        // Common reordering patterns based on hint text
                        const hint = (params.hint as string)?.toLowerCase() || '';

                        if (hint.includes('kpi') && (hint.includes('top') || hint.includes('first'))) {
                            // KPIs at top
                            reorderWidgets(['KpiCard', 'MetricChart', 'PriceChart', 'DataTable', 'NewsTimeline']);
                            console.log('[LayoutEventListener] Applied KPI-first reorder');
                        } else if (hint.includes('chart') && hint.includes('top')) {
                            // Charts at top
                            reorderWidgets(['PriceChart', 'MetricChart', 'KpiCard', 'DataTable', 'NewsTimeline']);
                        } else if (hint.includes('table') && hint.includes('top')) {
                            // Table at top
                            reorderWidgets(['DataTable', 'KpiCard', 'PriceChart', 'MetricChart', 'NewsTimeline']);
                        } else if (hint.includes('chart') && hint.includes('bottom')) {
                            // Charts at bottom
                            reorderWidgets(['KpiCard', 'DataTable', 'NewsTimeline', 'PriceChart', 'MetricChart']);
                        } else {
                            // Default to emphasis change if can't infer order
                            console.log('[LayoutEventListener] Could not infer order, using focus_chart');
                            setEmphasis('focus_chart');
                        }
                    }
                    break;
                }

                case 'reset_layout':
                case 'reset':
                    resetLayout();
                    break;

                case 'switch_layout':
                    if (params.emphasis) {
                        setEmphasis(params.emphasis as LayoutEmphasis);
                    } else {
                        resetLayout();
                    }
                    break;

                case 'focus_chart':
                    setEmphasis('focus_chart');
                    break;

                case 'focus_table':
                    setEmphasis('focus_table');
                    break;

                case 'focus_news':
                    setEmphasis('focus_news');
                    break;

                case 'balanced':
                    setEmphasis('balanced');
                    break;

                default:
                    console.warn('[LayoutEventListener] Unknown action:', action);
            }
        };

        window.addEventListener('a2ui:layout-change', handleLayoutChange);

        return () => {
            window.removeEventListener('a2ui:layout-change', handleLayoutChange);
        };
    }, [setEmphasis, hideWidget, showWidget, toggleWidget, reorderWidgets, resetLayout]);
}

export default useLayoutEventListener;
