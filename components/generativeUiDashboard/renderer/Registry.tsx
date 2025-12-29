/**
 * A2UI Component Registry
 *
 * Maps A2UI component type names to React component implementations.
 */

import React from 'react';
import type { ComponentType as A2UIComponentType, DataModel } from '../a2ui/types';

// Standard components
import { A2UIText } from './standard/Text';
import { A2UIRow } from './standard/Row';
import { A2UIColumn } from './standard/Column';
import { A2UICard } from './standard/Card';
import { A2UIButton } from './standard/Button';

// Financial widgets
import { PriceChart } from './widgets/PriceChart';
import { KpiCard } from './widgets/KpiCard';
import { DataTable } from './widgets/DataTable';
import { NewsTimeline } from './widgets/NewsTimeline';
import { CorrelationMatrix } from './widgets/CorrelationMatrix';
import { ExplainMovePanel } from './widgets/ExplainMovePanel';

/**
 * Common props passed to all A2UI component implementations.
 */
export interface A2UIRendererProps {
    /** Unique component ID */
    componentId: string;
    /** The component's raw props from A2UI */
    props: Record<string, unknown>;
    /** Data model for resolving bound values */
    dataModel: DataModel;
    /** Map of all components in the surface */
    components: Map<string, A2UIComponentType>;
    /** Callback for user actions */
    onAction: (actionName: string, context: Record<string, unknown>) => void;
    /** Render a child component by ID */
    renderChild: (childId: string) => React.ReactNode;
}

/**
 * Component registry mapping type names to React components.
 */
export const componentRegistry: Record<
    string,
    React.ComponentType<A2UIRendererProps>
> = {
    // Standard A2UI components
    Text: A2UIText,
    Row: A2UIRow,
    Column: A2UIColumn,
    Card: A2UICard,
    Button: A2UIButton,

    // Custom financial widgets
    PriceChart,
    KpiCard,
    DataTable,
    NewsTimeline,
    CorrelationMatrix,
    ExplainMovePanel,
};


/**
 * Extract component type and props from an A2UI component definition.
 */
export function extractComponent(
    componentDef: A2UIComponentType
): { type: string; props: Record<string, unknown> } | null {
    // componentDef is an object like { Text: { text: {...} } }
    const entries = Object.entries(componentDef as Record<string, unknown>);

    if (entries.length !== 1) {
        console.warn('A2UI component must have exactly one type key:', componentDef);
        return null;
    }

    const [type, props] = entries[0];
    return {
        type,
        props: props as Record<string, unknown>,
    };
}

/**
 * Resolve a component from the registry.
 */
export function resolveComponent(
    typeName: string
): React.ComponentType<A2UIRendererProps> | null {
    const Component = componentRegistry[typeName];

    if (!Component) {
        console.warn(`Unknown A2UI component type: ${typeName}`);
        return null;
    }

    return Component;
}

/**
 * Check if a component type is registered.
 */
export function isRegistered(typeName: string): boolean {
    return typeName in componentRegistry;
}

/**
 * Get all registered component type names.
 */
export function getRegisteredTypes(): string[] {
    return Object.keys(componentRegistry);
}
