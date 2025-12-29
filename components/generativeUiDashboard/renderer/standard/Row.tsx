/**
 * A2UI Row Component
 *
 * Horizontal flexbox layout container.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { RowProps } from '../../a2ui/types';

export function A2UIRow({
    componentId,
    props,
    renderChild,
}: A2UIRendererProps): React.ReactElement {
    const rowProps = props as unknown as RowProps;
    const children = rowProps.children;

    // Get child IDs
    const childIds: string[] = 'explicitList' in children ? children.explicitList : [];

    // Map alignment to CSS
    const alignmentMap: Record<string, string> = {
        start: 'flex-start',
        center: 'center',
        end: 'flex-end',
        spaceBetween: 'space-between',
        spaceAround: 'space-around',
    };

    const justifyContent = rowProps.alignment
        ? alignmentMap[rowProps.alignment] || 'flex-start'
        : 'flex-start';

    return (
        <div
            className="a2ui-row"
            data-component-id={componentId}
            style={{
                display: 'flex',
                flexDirection: 'row',
                justifyContent,
                gap: '1rem',
                width: '100%',
            }}
        >
            {childIds.map((childId) => (
                <div key={childId} className="a2ui-row__item" style={{ flex: '1 1 0' }}>
                    {renderChild(childId)}
                </div>
            ))}
        </div>
    );
}
