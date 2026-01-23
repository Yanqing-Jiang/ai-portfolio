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

import React, { useCallback, useContext, useLayoutEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type {
    CardProps,
    Children,
    ColumnProps,
    ComponentType as A2UIComponentType,
    DataModel,
    RowProps,
} from '../a2ui/types';
import { getByPath, resolveBoundProps } from '../a2ui/DataBinder';
import { extractComponent, resolveComponent, type A2UIRendererProps } from './Registry';
import { WidgetErrorBoundary } from './WidgetErrorBoundary';

// Import contexts - using optional import pattern for graceful degradation
import SwapContext, { getSwapOptions } from '../context/ComponentSwapContext';
import LayoutContext from '../context/LayoutContext';
import { SwapButton } from '../widgets/SwapButton';
import { SwapPreviewOverlay } from '../widgets/SwapPreviewOverlay';

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

    // Phase 1 FIX: All hooks must be before any early returns (Rules of Hooks)
    const hasRegisteredRef = useRef(false);

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

    // Get component definition and extract early (for use in registration)
    const componentDef = components.get(componentId);
    const extracted = componentDef ? extractComponent(componentDef) : null;

    // FIX: Compute resolved props synchronously, but register in useLayoutEffect
    // useLayoutEffect runs synchronously after DOM commit but before paint,
    // ensuring registration completes before user can interact with swap buttons.
    // We resolve BoundValue objects to actual values so snapshots contain real data.
    const resolvedPropsRef = useRef<Record<string, unknown> | null>(null);
    if (!hasRegisteredRef.current && extracted) {
        // CRITICAL: Resolve binding paths to actual values BEFORE registering
        // Without this, snapshots contain {path: "/data/..."} instead of actual numbers
        resolvedPropsRef.current = resolveBoundProps(
            extracted.props as Record<string, unknown>,
            dataModel
        );
    }

    // Register in useLayoutEffect to avoid "setState during render" error
    // useLayoutEffect is synchronous and runs before browser paint
    useLayoutEffect(() => {
        if (!hasRegisteredRef.current && extracted && swapContext?.registerOriginalProps && resolvedPropsRef.current) {
            swapContext.registerOriginalProps(componentId, extracted.type, resolvedPropsRef.current);
            hasRegisteredRef.current = true;
        }
    }, [componentId, extracted, swapContext]);

    // Early returns AFTER all hooks
    if (!componentDef) {
        console.warn(`Component not found: ${componentId}`);
        return null;
    }

    if (!extracted) {
        return null;
    }

    const { type: originalType, props: originalProps } = extracted;

    // Check for swap override (if context available)
    const type = swapContext?.getSwappedType(componentId, originalType) ?? originalType;

    // Phase 1 FIX: Use transformed data from swap override or snapshot when available
    // This preserves data through swap/revert cycles
    const swapOverride = swapContext?.getSwapOverride?.(componentId);
    const transformedData = swapContext?.getTransformedData?.(componentId);
    const props = transformedData
        ? { ...originalProps, ...transformedData }
        : (swapOverride?.transformedData
            ? { ...originalProps, ...swapOverride.transformedData }
            : originalProps);

    const isSwappable = enableSwap && getSwapOptions(originalType).length > 0;
    const isSwapped = swapContext?.isSwapped(componentId) ?? false;
    const isSwapping = swapContext?.swapLoading?.get(componentId) ?? false;
    const isPreview = swapContext?.isPreviewing?.(componentId) ?? false;

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
                animate={{
                    opacity: 1,
                    y: 0,
                    scale: isSwapping ? 0.98 : 1,
                    // Smooth morphing animation for swapped components
                    boxShadow: isSwapped
                        ? '0 0 0 1px rgba(16, 185, 129, 0.3), 0 0 20px rgba(16, 185, 129, 0.1)'
                        : isSwapping
                            ? '0 0 0 2px rgba(251, 191, 36, 0.4), 0 0 30px rgba(251, 191, 36, 0.2)'
                            : 'none',
                }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={isSwapping
                    ? { duration: 0.3, ease: 'easeInOut' }
                    : isStreamedComponent
                        ? streamingEntranceConfig
                        : springConfig
                }
                className={`a2ui-component-wrapper relative group ${emphasisClasses} ${isSwapping ? 'pointer-events-none' : ''
                    }`}
                data-component-id={componentId}
                data-component-type={type}
                data-original-type={originalType}
                data-streamed={isStreamedComponent ? 'true' : undefined}
                data-swapped={isSwapped ? 'true' : undefined}
                data-swapping={isSwapping ? 'true' : undefined}
            >
                {/* Swap button overlay - appears on hover for swappable components */}
                {isSwappable && swapContext && (
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                        <SwapButton componentId={componentId} componentType={originalType} />
                    </div>
                )}
                {/* Preview Overlay */}
                {isPreview && <SwapPreviewOverlay componentId={componentId} />}
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
