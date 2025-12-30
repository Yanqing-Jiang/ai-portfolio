/**
 * A2UI Image Component
 *
 * Renders an image with optional alt text.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { ImageProps } from '../../a2ui/types';
import { resolveString } from '../../a2ui/DataBinder';

/**
 * Function: A2UIImage — used by componentRegistry to render the standard A2UI Image component; resolves bound url/alt into an img element.
 */
export function A2UIImage({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const imageProps = props as unknown as ImageProps;
    const src = resolveString(imageProps.url, dataModel, '');
    const alt = resolveString(imageProps.alt, dataModel, '');

    return (
        <img
            data-component-id={componentId}
            src={src}
            alt={alt}
            style={{
                width: '100%',
                height: 'auto',
                borderRadius: '8px',
                objectFit: 'cover',
                backgroundColor: 'rgba(148,163,184,0.1)',
            }}
        />
    );
}
