/**
 * A2UI Card Component
 *
 * Container with border and shadow styling.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { CardProps } from '../../a2ui/types';

export function A2UICard({
    componentId,
    props,
    renderChild,
}: A2UIRendererProps): React.ReactElement {
    const cardProps = props as unknown as CardProps;
    const childId = cardProps.child;

    return (
        <div
            className="a2ui-card"
            data-component-id={componentId}
            style={{
                backgroundColor: 'rgba(15, 23, 42, 0.8)',
                borderRadius: '12px',
                border: '1px solid rgba(99, 102, 241, 0.2)',
                padding: '1.5rem',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
            }}
        >
            {childId && renderChild(childId)}
        </div>
    );
}
