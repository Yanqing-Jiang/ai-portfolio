// --- Function/Class Map ---
// Component: ComponentRenderer
//   Role: Recursively render A2UI component trees with layout + swap support.
//   Called from: components/generativeUiDashboard/renderer/A2UISurface.tsx
//   Invokes: extractComponent, resolveComponent, LayoutContext, SwapContext
//   Why: Central renderer for A2UI surface trees.
// Function: resolveChildIds
//   Role: Resolve explicit or templated child IDs for layout inference.
//   Called from: getLayoutType.
//   Invokes: getByPath.
//   Why: Lets layout logic inspect container children.
// Function: getLayoutType
//   Role: Resolve a widget type for emphasis/visibility when wrapped in cards or containers.
//   Called from: ComponentRenderer.
//   Invokes: resolveChildIds, extractComponent, component map lookup.
//   Why: Aligns layout commands with rendered card wrappers.
// Component: UnknownComponent
//   Role: Render fallback UI for unknown component types.
//   Called from: ComponentRenderer.
//   Invokes: n/a.
//   Why: Makes missing catalog entries visible during development.
// --- End Function/Class Map ---
/**
 * A2UI Component Renderer
 *
 * Recursively renders A2UI components from the component tree.
 * Uses Framer Motion for smooth layout animations.
 * Includes error boundaries to prevent cascade failures (optimization #14).
 * Supports component swapping via ComponentSwapContext.
 * Supports layout preferences via LayoutContext.
 */

import React, { useCallback, useContext } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type {
    CardProps,
    Children,
    ColumnProps,
    ComponentType as A2UIComponentType,
    DataModel,
    RowProps,
} from '../a2ui/types';
import { getByPath } from '../a2ui/DataBinder';
import { extractComponent, resolveComponent, type A2UIRendererProps } from './Registry';
import { WidgetErrorBoundary } from './WidgetErrorBoundary';

// Import contexts - using optional import pattern for graceful degradation
import SwapContext, { getSwapOptions } from '../context/ComponentSwapContext';
import LayoutContext from '../context/LayoutContext';
import { SwapButton } from '../widgets/SwapButton';

export interface ComponentRendererProps {
    /** ID of the component to render */
    componentId: string;
    /** Map of all components in the surface */
    components: Map<string, A2UIComponentType>;
    /** Data model for the surface */
    dataModel: DataModel;
    /** Callback for user actions */
    onAction: (actionName: string, context: Record<string, unknown>) => void;
    /** Whether to enable swap functionality */
    enableSwap?: boolean;
    /** Set of component IDs that were streamed incrementally (Phase 5) */
    streamedComponentIds?: Set<string>;
}

/** Spring animation config for smooth, natural-feeling transitions */
const springConfig = {
    type: "spring" as const,
    stiffness: 200,
    damping: 25,
    mass: 0.8,
};

/** Phase 5: Enhanced animation for streamed (incremental) components */
const streamingEntranceConfig = {
    type: "spring" as const,
    stiffness: 150,
    damping: 20,
    mass: 1.0,
};

const LAYOUT_WIDGET_TYPES = new Set([
    'KpiCard',
    'MetricChart',
    'PriceChart',
    'DataTable',
    'NewsTimeline',
    'ExplainMovePanel',
    'PeerComparePanel',
    'CorrelationMatrix',
]);

function resolveChildIds(children: Children, dataModel: DataModel): string[] {
    const resolved: string[] = [];
    if ('explicitList' in children) {
        resolved.push(...children.explicitList);
    } else if ('template' in children && children.template) {
        const dataArray = getByPath(dataModel, children.dataPath);
        const items = Array.isArray(dataArray) ? dataArray : [];
        items.forEach((item, idx) => {
            const childId =
                typeof item === 'string'
                    ? item
                    : children.template!.includes('{index}')
                        ? children.template!.replace('{index}', String(idx))
                        : `${children.template}_${idx}`;
            resolved.push(childId);
        });
    }
    return resolved;
}

function getLayoutType(
    componentType: string,
    props: Record<string, unknown>,
    components: Map<string, A2UIComponentType>,
    dataModel: DataModel,
    depth = 0
): string | null {
    if (depth > 4) return null;
    if (LAYOUT_WIDGET_TYPES.has(componentType)) return componentType;

    if (componentType === 'Card') {
        const childId = (props as CardProps).child;
        if (!childId) return null;
        const childDef = components.get(childId);
        if (!childDef) return null;
        const extracted = extractComponent(childDef);
        if (!extracted) return null;
        if (LAYOUT_WIDGET_TYPES.has(extracted.type)) return extracted.type;
        return getLayoutType(extracted.type, extracted.props, components, dataModel, depth + 1);
    }

    if (componentType === 'Row' || componentType === 'Column') {
        const nestedChildren = resolveChildIds((props as RowProps | ColumnProps).children, dataModel);
        const nestedTypes = new Set<string>();
        for (const nestedId of nestedChildren) {
            const nestedDef = components.get(nestedId);
            if (!nestedDef) continue;
            const nestedExtracted = extractComponent(nestedDef);
            if (!nestedExtracted) continue;
            const nestedType = getLayoutType(nestedExtracted.type, nestedExtracted.props, components, dataModel, depth + 1);
            if (nestedType) nestedTypes.add(nestedType);
        }
        if (nestedTypes.size == 1) {
            return Array.from(nestedTypes)[0];
        }
    }

    return null;
}

/**
 * Renders a single A2UI component and its children.
 * Wraps each component with motion.div for layout animations.
 * Supports component swapping and layout preferences when contexts are available.
 */
export function ComponentRenderer({
    componentId,
    components,
    dataModel,
    onAction,
    enableSwap = true,
    streamedComponentIds,
}: ComponentRendererProps): React.ReactElement | null {
    // Determine if this component was streamed incrementally (Phase 5)
    const isStreamedComponent = streamedComponentIds?.has(componentId) ?? false;
    // Try to use contexts (may be null if not wrapped in providers)
    const swapContext = useContext(SwapContext);
    const layoutContext = useContext(LayoutContext);

    // IMPORTANT: useCallback must be called before any early returns to satisfy Rules of Hooks
    const renderChild = useCallback(
        (childId: string): React.ReactNode => (
            <AnimatePresence mode="popLayout" key={childId}>
                <ComponentRenderer
                    componentId={childId}
                    components={components}
                    dataModel={dataModel}
                    onAction={onAction}
                    enableSwap={enableSwap}
                    streamedComponentIds={streamedComponentIds}
                />
            </AnimatePresence>
        ),
        [components, dataModel, onAction, enableSwap, streamedComponentIds]
    );

    // Get component definition from map
    const componentDef = components.get(componentId);

    if (!componentDef) {
        console.warn(`Component not found: ${componentId}`);
        return null;
    }

    // Extract type and props
    const extracted = extractComponent(componentDef);
    if (!extracted) {
        return null;
    }

    const { type: originalType, props } = extracted;

    // Check for swap override (if context available)
    const type = swapContext?.getSwappedType(componentId, originalType) ?? originalType;
    const isSwappable = enableSwap && getSwapOptions(originalType).length > 0;

    const layoutType = getLayoutType(type, props as Record<string, unknown>, components, dataModel)
        || getLayoutType(originalType, props as Record<string, unknown>, components, dataModel);
    const emphasisTarget = layoutType || type;
    const hiddenTarget = layoutType || originalType;

    // Get emphasis classes from layout context (if available)
    const emphasisClasses = layoutContext?.getEmphasisClasses(emphasisTarget) ?? '';

    // Check if this widget type is hidden
    const isHidden = layoutContext?.isWidgetHidden(hiddenTarget) ?? false;
    if (isHidden) {
        return null; // Don't render hidden widgets
    }

    // Get React component from registry (using potentially swapped type)
    const Component = resolveComponent(type);
    if (!Component) {
        // Render placeholder for unknown components
        return (
            <motion.div
                className="a2ui-unknown-component"
                data-component-id={componentId}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={springConfig}
            >
                Unknown: {type}
            </motion.div>
        );
    }

    // Render the component with motion wrapper
    const rendererProps: A2UIRendererProps = {
        componentId,
        props,
        dataModel,
        components,
        onAction,
        renderChild,
    };

    return (
        <WidgetErrorBoundary
            componentId={componentId}
            componentType={type}
            onError={(error, errorInfo) => {
                console.error(
                    `[A2UI] Widget render error in ${type} (${componentId}):`,
                    error,
                    errorInfo
                );
            }}
        >
            <motion.div
                layout
                layoutId={componentId}
                initial={{ opacity: 0, y: isStreamedComponent ? 30 : 20, scale: isStreamedComponent ? 0.95 : 1 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={isStreamedComponent ? streamingEntranceConfig : springConfig}
                className={`a2ui-component-wrapper relative group ${emphasisClasses}`}
                data-component-id={componentId}
                data-component-type={type}
                data-original-type={originalType}
                data-streamed={isStreamedComponent ? 'true' : undefined}
            >
                {/* Swap button overlay - appears on hover for swappable components */}
                {isSwappable && swapContext && (
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                        <SwapButton componentId={componentId} componentType={originalType} />
                    </div>
                )}
                <Component {...rendererProps} />
            </motion.div>
        </WidgetErrorBoundary>
    );
}

/**
 * Placeholder component for unknown types.
 */
export function UnknownComponent({
    componentId,
    props,
}: {
    componentId: string;
    props: Record<string, unknown>;
}): React.ReactElement {
    return (
        <div
            className="a2ui-unknown"
            style={{
                padding: '1rem',
                border: '1px dashed #666',
                borderRadius: '4px',
                backgroundColor: 'rgba(255, 100, 100, 0.1)',
            }}
        >
            <strong>Unknown Component</strong>
            <pre style={{ fontSize: '0.75rem', overflow: 'auto' }}>
                {JSON.stringify({ id: componentId, props }, null, 2)}
            </pre>
        </div>
    );
}
