/**
 * A2UI List Component
 *
 * Renders children either vertically or horizontally.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { ListProps } from '../../a2ui/types';
import { getByPath } from '../../a2ui/DataBinder';

/**
 * Function: A2UIList — called from componentRegistry; renders children in row/column layouts; enables the standard A2UI List component within the React renderer.
 */
export function A2UIList({
    componentId,
    props,
    dataModel,
    components,
    renderChild,
}: A2UIRendererProps): React.ReactElement {
    const listProps = props as unknown as ListProps;
    const children = listProps.children;
    const direction = listProps.direction || 'column';

    const childIds: string[] = [];
    if ('explicitList' in children) {
        childIds.push(...children.explicitList);
    } else if ('template' in children && children.template) {
        const dataArray = getByPath(dataModel, children.dataPath);
        const items = Array.isArray(dataArray) ? dataArray : [];
        items.forEach((item, idx) => {
            const childId =
                typeof item === 'string'
                    ? item
                    : children.template.includes('{index}')
                        ? children.template.replace('{index}', String(idx))
                        : `${children.template}_${idx}`;
            childIds.push(childId);
        });
    }

    const alignmentMap: Record<string, string> = {
        start: 'flex-start',
        center: 'center',
        end: 'flex-end',
        spaceBetween: 'space-between',
        spaceAround: 'space-around',
        stretch: 'stretch',
    };

    const alignItems = listProps.alignment ? alignmentMap[listProps.alignment] || 'stretch' : 'stretch';

    return (
        <div
            className="a2ui-list"
            data-component-id={componentId}
            style={{
                display: 'flex',
                flexDirection: direction === 'row' ? 'row' : 'column',
                gap: '0.75rem',
                alignItems,
            }}
        >
            {childIds.map((childId) => (
                <div key={childId} style={{ width: '100%' }}>
                    {renderChild(componentsHasId(components, childId) ? childId : children.template || childId)}
                </div>
            ))}
        </div>
    );
}

function componentsHasId(map: Map<string, any>, id: string): boolean {
    return map.has(id);
}
