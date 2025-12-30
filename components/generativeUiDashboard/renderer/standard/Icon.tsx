/**
 * A2UI Icon Component
 *
 * Simple text-based icon placeholder using the provided name.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { IconProps } from '../../a2ui/types';
import { resolveNumber, resolveString } from '../../a2ui/DataBinder';

/**
 * Function: A2UIIcon — registered in componentRegistry; renders a text-based icon badge; supports the standard A2UI Icon component.
 */
export function A2UIIcon({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const iconProps = props as unknown as IconProps;
    const name = resolveString(iconProps.name, dataModel, '★');
    const size = resolveNumber(iconProps.size, dataModel, 20);
    const color = resolveString(iconProps.color, dataModel, '#f8fafc');

    return (
        <span
            data-component-id={componentId}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: `${size}px`,
                height: `${size}px`,
                borderRadius: '50%',
                backgroundColor: 'rgba(244,63,94,0.15)',
                color,
                fontSize: `${Math.max(14, size * 0.6)}px`,
                fontWeight: 700,
            }}
        >
            {name}
        </span>
    );
}
