/**
 * A2UI AudioPlayer Component
 *
 * Renders an HTML5 audio player.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { AudioPlayerProps } from '../../a2ui/types';
import { resolveBoolean, resolveString } from '../../a2ui/DataBinder';

/**
 * Function: A2UIAudioPlayer — registered via componentRegistry; renders HTML5 audio for the standard A2UI AudioPlayer component.
 */
export function A2UIAudioPlayer({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const audioProps = props as unknown as AudioPlayerProps;
    const src = resolveString(audioProps.url, dataModel, '');
    const autoplay = resolveBoolean(audioProps.autoplay, dataModel, false);
    const controls = resolveBoolean(audioProps.controls, dataModel, true);

    return (
        <audio
            data-component-id={componentId}
            src={src}
            controls={controls}
            autoPlay={autoplay}
            style={{ width: '100%' }}
        />
    );
}
