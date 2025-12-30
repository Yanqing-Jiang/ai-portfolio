/**
 * A2UI Divider Component
 *
 * Simple horizontal rule for separating sections.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';

/**
 * Function: Divider — called from componentRegistry in Registry.tsx; renders a simple separator line; exists to support the standard A2UI Divider component.
 */
export function Divider({
    componentId,
}: A2UIRendererProps): React.ReactElement {
    return (
        <hr
            data-component-id={componentId}
            style={{
                border: 'none',
                borderTop: '1px solid rgba(148, 163, 184, 0.3)',
                margin: '0.75rem 0',
            }}
        />
    );
}
