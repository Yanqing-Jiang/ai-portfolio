/**
 * A2UI Row Component
 *
 * Horizontal flexbox layout container.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { RowProps } from '../../a2ui/types';
import { getByPath } from '../../a2ui/DataBinder';

export function A2UIRow({
    componentId,
    props,
    dataModel,
    components,
    renderChild,
}: A2UIRendererProps): React.ReactElement {
    const rowProps = props as unknown as RowProps;
    const children = rowProps.children;

    // Get child IDs (support ChildrenTemplate)
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
                    {renderChild(componentsHasId(components, childId) ? childId : templateValue || childId)}
                </div>
            ))}
        </div>
    );
}

function componentsHasId(map: Map<string, any>, id: string): boolean {
    return map.has(id);
}
