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
import type { ComponentType as A2UIComponentType, DataModel } from '../a2ui/types';
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
}

/** Spring animation config for smooth, natural-feeling transitions */
const springConfig = {
    type: "spring" as const,
    stiffness: 200,
    damping: 25,
    mass: 0.8,
};

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
}: ComponentRendererProps): React.ReactElement | null {
    // Try to use contexts (may be null if not wrapped in providers)
    const swapContext = useContext(SwapContext);
    const layoutContext = useContext(LayoutContext);

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

    // Get emphasis classes from layout context (if available)
    const emphasisClasses = layoutContext?.getEmphasisClasses(type) ?? '';

    // Check if this widget type is hidden
    const isHidden = layoutContext?.isWidgetHidden(originalType) ?? false;
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

    // Create render child helper with AnimatePresence wrapper
    const renderChild = useCallback(
        (childId: string): React.ReactNode => (
            <AnimatePresence mode="popLayout" key={childId}>
                <ComponentRenderer
                    componentId={childId}
                    components={components}
                    dataModel={dataModel}
                    onAction={onAction}
                    enableSwap={enableSwap}
                />
            </AnimatePresence>
        ),
        [components, dataModel, onAction, enableSwap]
    );

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
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={springConfig}
                className={`a2ui-component-wrapper relative group ${emphasisClasses}`}
                data-component-id={componentId}
                data-component-type={type}
                data-original-type={originalType}
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
