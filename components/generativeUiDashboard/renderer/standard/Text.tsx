/**
 * A2UI Text Component
 *
 * Renders text with optional usage hints for styling.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import { resolveString } from '../../a2ui/DataBinder';
import type { TextProps } from '../../a2ui/types';

export function A2UIText({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const textProps = props as unknown as TextProps;
    const text = resolveString(textProps.text, dataModel, '');
    const usageHint = textProps.usageHint;

    // Map usage hints to HTML elements and styles
    const getElement = () => {
        switch (usageHint) {
            case 'h1':
                return (
                    <h1 className="a2ui-text a2ui-text--h1" data-component-id={componentId}>
                        {text}
                    </h1>
                );
            case 'h2':
                return (
                    <h2 className="a2ui-text a2ui-text--h2" data-component-id={componentId}>
                        {text}
                    </h2>
                );
            case 'h3':
                return (
                    <h3 className="a2ui-text a2ui-text--h3" data-component-id={componentId}>
                        {text}
                    </h3>
                );
            case 'caption':
                return (
                    <span className="a2ui-text a2ui-text--caption" data-component-id={componentId}>
                        {text}
                    </span>
                );
            case 'body':
            default:
                return (
                    <p className="a2ui-text a2ui-text--body" data-component-id={componentId}>
                        {text}
                    </p>
                );
        }
    };

    return getElement();
}
