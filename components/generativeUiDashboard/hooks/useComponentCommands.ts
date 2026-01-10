/**
 * @deprecated This hook is DEPRECATED in favor of the LLM-driven CommandRouter.
 * 
 * The backend now handles intent classification via /api/dash/{id}/query endpoint.
 * See: backend/generative_ui/command_router.py for the replacement.
 * 
 * This hook will be removed in a future version once all frontend callers
 * are migrated to use streamActions.sendQuery() instead.
 * 
 * --- Legacy Documentation ---
 * useComponentCommands - Parse natural language for component actions.
 *
 * Hook: useComponentCommands
 * Called from: GenerativeUIPage.tsx (follow-up input handler)
 * Invokes: findComponentByKeyword, layout/swap contexts
 * Why: Enables conversational component targeting without LLM calls.
 *      Parses commands like "hide the chart" or "focus on tables".
 */

import { useCallback } from 'react';
import { useComponentSelection, findComponentByKeyword } from '../context/ComponentSelectionContext';
import { useComponentSwap, canSwapTo } from '../context/ComponentSwapContext';
import { useLayoutPreferences, type LayoutEmphasis } from '../context/LayoutContext';

// ============================================================================
// Types
// ============================================================================

export interface CommandResult {
    /** Whether the command was handled (should not be sent to backend) */
    handled: boolean;
    /** Action that was performed */
    action?: 'hide' | 'show' | 'focus' | 'swap' | 'reset';
    /** Target component type or focus mode */
    target?: string;
    /** Human-readable message for feedback */
    message?: string;
}

// ============================================================================
// Hook
// ============================================================================

export function useComponentCommands(components: Map<string, string>) {
    const { selectedComponent, selectByText } = useComponentSelection();
    const { swapComponent } = useComponentSwap();
    const { toggleWidget, setEmphasis, resetLayout, showWidget, hideWidget } = useLayoutPreferences();

    /**
     * Parse a natural language command and execute it if recognized.
     * Returns { handled: true } if the command was processed locally,
     * or { handled: false } to let it pass through to the backend.
     */
    const parseCommand = useCallback((input: string): CommandResult => {
        const lower = input.toLowerCase().trim();

        // ----------------------------------------------------------------
        // Pattern: "reset layout" / "reset view" / "default layout"
        // ----------------------------------------------------------------
        if (lower.match(/^(reset|restore|default)\s+(layout|view|all)/)) {
            resetLayout();
            return {
                handled: true,
                action: 'reset',
                message: 'Layout reset to default'
            };
        }

        // ----------------------------------------------------------------
        // Pattern: "hide the [component]" / "hide [component]"
        // ----------------------------------------------------------------
        const hideMatch = lower.match(/^hide\s+(the\s+)?(.+)$/);
        if (hideMatch) {
            const targetType = findComponentByKeyword(hideMatch[2]);
            if (targetType) {
                hideWidget(targetType);
                return {
                    handled: true,
                    action: 'hide',
                    target: targetType,
                    message: `Hidden ${targetType}`
                };
            }
        }

        // ----------------------------------------------------------------
        // Pattern: "show the [component]" / "show [component]" (unhide)
        // ----------------------------------------------------------------
        const showMatch = lower.match(/^show\s+(the\s+)?(.+)$/);
        if (showMatch) {
            const targetType = findComponentByKeyword(showMatch[2]);
            if (targetType) {
                showWidget(targetType);
                return {
                    handled: true,
                    action: 'show',
                    target: targetType,
                    message: `Showing ${targetType}`
                };
            }
        }

        // ----------------------------------------------------------------
        // Pattern: "focus on [chart/table/news]" / "emphasize [...]"
        // ----------------------------------------------------------------
        const focusMatch = lower.match(/^(focus|emphasize|highlight)\s+(on\s+)?(the\s+)?(.+)$/);
        if (focusMatch) {
            const target = focusMatch[4];
            let emphasis: LayoutEmphasis | null = null;

            if (target.includes('chart') || target.includes('price') || target.includes('graph')) {
                emphasis = 'focus_chart';
            } else if (target.includes('table') || target.includes('data') || target.includes('grid')) {
                emphasis = 'focus_table';
            } else if (target.includes('news') || target.includes('timeline') || target.includes('event')) {
                emphasis = 'focus_news';
            } else if (target.includes('balance') || target.includes('all') || target.includes('equal')) {
                emphasis = 'balanced';
            }

            if (emphasis) {
                setEmphasis(emphasis);
                return {
                    handled: true,
                    action: 'focus',
                    target: emphasis,
                    message: `Focus set to ${emphasis.replace('_', ' ')}`
                };
            }
        }

        // ----------------------------------------------------------------
        // Pattern: "swap [that/the chart/this] to [table/chart]"
        // Pattern: "show as [table]" / "view as [chart]"
        // ----------------------------------------------------------------
        const swapMatch = lower.match(/^(swap|change|convert)\s+(.+?)\s+to\s+(.+)$/);
        const viewAsMatch = lower.match(/^(show|view|display)\s+(this|that|it)?\s*(as|like)\s+(.+)$/);

        if (swapMatch || viewAsMatch) {
            const sourceRef = swapMatch ? swapMatch[2] : (viewAsMatch?.[2] || 'that');
            const targetRef = swapMatch ? swapMatch[3] : viewAsMatch?.[4] || '';

            // Resolve source component
            let sourceId: string | null = null;
            let sourceType: string | null = null;

            // Check for pronoun references (that, this, it)
            if (sourceRef === 'that' || sourceRef === 'this' || sourceRef === 'it' || sourceRef === '') {
                // Use selected component
                if (selectedComponent) {
                    sourceId = selectedComponent.componentId;
                    sourceType = selectedComponent.originalType;
                }
            } else {
                // Parse component type from text
                sourceType = findComponentByKeyword(sourceRef);
                if (sourceType) {
                    // Find first component of this type
                    for (const [id, type] of components) {
                        if (type === sourceType) {
                            sourceId = id;
                            break;
                        }
                    }
                }
            }

            const targetType = findComponentByKeyword(targetRef);

            if (sourceId && sourceType && targetType && canSwapTo(sourceType, targetType)) {
                swapComponent(sourceId, sourceType, targetType);
                return {
                    handled: true,
                    action: 'swap',
                    target: targetType,
                    message: `Swapped to ${targetType}`
                };
            }
        }

        // ----------------------------------------------------------------
        // Pattern: "select [component]" / "click on [component]"
        // ----------------------------------------------------------------
        const selectMatch = lower.match(/^(select|click\s+on|highlight)\s+(the\s+)?(.+)$/);
        if (selectMatch) {
            const found = selectByText(selectMatch[3], components);
            if (found) {
                return {
                    handled: true,
                    action: 'focus',
                    target: 'selection',
                    message: 'Component selected'
                };
            }
        }

        // Not a recognized component command - let it pass through to backend
        return { handled: false };
    }, [
        selectedComponent,
        components,
        toggleWidget,
        setEmphasis,
        swapComponent,
        resetLayout,
        selectByText,
        showWidget,
        hideWidget,
    ]);

    return { parseCommand };
}

export default useComponentCommands;
