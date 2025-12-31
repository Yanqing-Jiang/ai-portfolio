/**
 * A2UI Component Renderer
 *
 * Recursively renders A2UI components from the component tree.
 * Uses Framer Motion for smooth layout animations.
 */

import React, { useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { ComponentType as A2UIComponentType, DataModel } from '../a2ui/types';
import { extractComponent, resolveComponent, type A2UIRendererProps } from './Registry';

export interface ComponentRendererProps {
    /** ID of the component to render */
    componentId: string;
    /** Map of all components in the surface */
    components: Map<string, A2UIComponentType>;
    /** Data model for the surface */
    dataModel: DataModel;
    /** Callback for user actions */
    onAction: (actionName: string, context: Record<string, unknown>) => void;
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
 */
export function ComponentRenderer({
    componentId,
    components,
    dataModel,
    onAction,
}: ComponentRendererProps): React.ReactElement | null {
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

    const { type, props } = extracted;

    // Get React component from registry
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
                />
            </AnimatePresence>
        ),
        [components, dataModel, onAction]
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
        <motion.div
            layout
            layoutId={componentId}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={springConfig}
            className="a2ui-component-wrapper"
            data-component-id={componentId}
            data-component-type={type}
        >
            <Component {...rendererProps} />
        </motion.div>
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
