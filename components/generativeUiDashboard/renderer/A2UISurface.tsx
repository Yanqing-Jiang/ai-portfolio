/**
 * A2UI Surface Renderer
 *
 * Renders an entire A2UI surface from root component.
 */

import React from 'react';
import type { Surface, DataModel } from '../a2ui/types';
import { ComponentRenderer } from './ComponentRenderer';
import { DashboardSkeleton } from './widgets/WidgetSkeleton';

export interface A2UISurfaceProps {
    /** The surface to render */
    surface: Surface;
    /** Data model for the surface */
    dataModel: DataModel;
    /** Callback when user triggers an action */
    onAction: (actionName: string, context: Record<string, unknown>) => void;
    /** Additional CSS class */
    className?: string;
    /** Set of component IDs that were streamed incrementally (Phase 5) */
    streamedComponentIds?: Set<string>;
}

/**
 * Renders an A2UI surface starting from its root component.
 */
export function A2UISurface({
    surface,
    dataModel,
    onAction,
    className = '',
    streamedComponentIds,
}: A2UISurfaceProps): React.ReactElement | null {
    // Check if surface has a root
    if (!surface.root) {
        return (
            <div className={`a2ui-surface a2ui-surface--empty ${className}`}>
                <p>Waiting for content...</p>
            </div>
        );
    }

    // Render from root
    return (
        <div
            className={`a2ui-surface ${className}`}
            data-surface-id={surface.surfaceId}
        >
            <ComponentRenderer
                componentId={surface.root}
                components={surface.components}
                dataModel={dataModel}
                onAction={onAction}
                streamedComponentIds={streamedComponentIds}
            />
        </div>
    );
}

/**
 * Loading state for surfaces — uses shimmer skeleton for premium feel.
 */
export function A2UISurfaceLoading(): React.ReactElement {
    return (
        <div className="a2ui-surface a2ui-surface--loading">
            <DashboardSkeleton />
        </div>
    );
}


/**
 * Error state for surfaces.
 */
export function A2UISurfaceError({
    error,
    onRetry,
}: {
    error: Error;
    onRetry?: () => void;
}): React.ReactElement {
    return (
        <div className="a2ui-surface a2ui-surface--error">
            <div className="a2ui-error-content">
                <h3>Error Loading Dashboard</h3>
                <p>{error.message}</p>
                {onRetry && (
                    <button onClick={onRetry} className="a2ui-retry-button">
                        Retry
                    </button>
                )}
            </div>
        </div>
    );
}
