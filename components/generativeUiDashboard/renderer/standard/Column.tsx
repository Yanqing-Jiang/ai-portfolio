/**
 * A2UI Column Component
 *
 * Vertical flexbox layout container.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { ColumnProps } from '../../a2ui/types';

export function A2UIColumn({
    componentId,
    props,
    renderChild,
}: A2UIRendererProps): React.ReactElement {
    const columnProps = props as unknown as ColumnProps;
    const children = columnProps.children;

    // Get child IDs
    const childIds: string[] = 'explicitList' in children ? children.explicitList : [];

    // Map alignment to CSS
    const alignmentMap: Record<string, string> = {
        start: 'flex-start',
        center: 'center',
        end: 'flex-end',
        stretch: 'stretch',
    };

    const alignItems = columnProps.alignment
        ? alignmentMap[columnProps.alignment] || 'stretch'
        : 'stretch';

    return (
        <div
            className="a2ui-column"
            data-component-id={componentId}
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems,
                gap: '1rem',
                width: '100%',
            }}
        >
            {childIds.map((childId) => (
                <div key={childId} className="a2ui-column__item">
                    {renderChild(childId)}
                </div>
            ))}
        </div>
    );
}
