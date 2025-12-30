/**
 * A2UI Video Component
 *
 * Renders an HTML5 video player.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { VideoProps } from '../../a2ui/types';
import { resolveBoolean, resolveString } from '../../a2ui/DataBinder';

/**
 * Function: A2UIVideo — registered via componentRegistry; renders HTML5 video for the standard A2UI Video component.
 */
export function A2UIVideo({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const videoProps = props as unknown as VideoProps;
    const src = resolveString(videoProps.url, dataModel, '');
    const autoplay = resolveBoolean(videoProps.autoplay, dataModel, false);
    const controls = resolveBoolean(videoProps.controls, dataModel, true);

    return (
        <video
            data-component-id={componentId}
            src={src}
            autoPlay={autoplay}
            controls={controls}
            style={{
                width: '100%',
                borderRadius: '8px',
                backgroundColor: 'rgba(0,0,0,0.6)',
            }}
        />
    );
}
