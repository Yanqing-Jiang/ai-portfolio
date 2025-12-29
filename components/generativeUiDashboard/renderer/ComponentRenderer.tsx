/**
 * A2UI Component Renderer
 *
 * Recursively renders A2UI components from the component tree.
 */

import React, { useCallback } from 'react';
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

/**
 * Renders a single A2UI component and its children.
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
            <div className="a2ui-unknown-component" data-component-id={componentId}>
                Unknown: {type}
            </div>
        );
    }

    // Create render child helper
    const renderChild = useCallback(
        (childId: string): React.ReactNode => (
            <ComponentRenderer
                key={childId}
                componentId={childId}
                components={components}
                dataModel={dataModel}
                onAction={onAction}
            />
        ),
        [components, dataModel, onAction]
    );

    // Render the component
    const rendererProps: A2UIRendererProps = {
        componentId,
        props,
        dataModel,
        components,
        onAction,
        renderChild,
    };

    return <Component {...rendererProps} />;
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
