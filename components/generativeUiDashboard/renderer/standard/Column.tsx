/**
 * A2UI Column Component
 *
 * Vertical flexbox layout container.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { ColumnProps } from '../../a2ui/types';
import { getByPath } from '../../a2ui/DataBinder';

export function A2UIColumn({
    componentId,
    props,
    dataModel,
    components,
    renderChild,
}: A2UIRendererProps): React.ReactElement {
    const columnProps = props as unknown as ColumnProps;
    const children = columnProps.children;

    // Get child IDs (supports ChildrenTemplate)
    const childIds: string[] = [];
    let templateValue: string | undefined;
    if ('explicitList' in children) {
        childIds.push(...children.explicitList);
    } else if ('template' in children && children.template) {
        templateValue = children.template;
        const dataArray = getByPath(dataModel, children.dataPath);
        const items = Array.isArray(dataArray) ? dataArray : [];
        items.forEach((item, idx) => {
            const childId =
                typeof item === 'string'
                    ? item
                    : templateValue!.includes('{index}')
                        ? templateValue!.replace('{index}', String(idx))
                        : `${templateValue}_${idx}`;
            childIds.push(childId);
        });
    }

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
                    {renderChild(componentsHasId(components, childId) ? childId : templateValue || childId)}
                </div>
            ))}
        </div>
    );
}

function componentsHasId(map: Map<string, any>, id: string): boolean {
    return map.has(id);
}
