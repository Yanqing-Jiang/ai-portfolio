/**
 * A2UI Button Component
 *
 * Interactive button that triggers userAction messages.
 */

import React, { useCallback } from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { ButtonProps } from '../../a2ui/types';
import { resolveString, resolveBoundValue } from '../../a2ui/DataBinder';

export function A2UIButton({
    componentId,
    props,
    dataModel,
    onAction,
}: A2UIRendererProps): React.ReactElement {
    const buttonProps = props as unknown as ButtonProps;

    const label = resolveString(buttonProps.label, dataModel, 'Button');
    const actionName = buttonProps.action?.name || 'click';
    const variant = buttonProps.variant || 'primary';

    // Resolve action context
    const resolveContext = useCallback((): Record<string, unknown> => {
        const context: Record<string, unknown> = {};

        if (buttonProps.action?.context) {
            for (const { key, value } of buttonProps.action.context) {
                context[key] = resolveBoundValue(value, dataModel);
            }
        }

        return context;
    }, [buttonProps.action?.context, dataModel]);

    const handleClick = useCallback(() => {
        const context = resolveContext();
        onAction(actionName, context);
    }, [actionName, resolveContext, onAction]);

    // Variant styles
    const variantStyles: Record<string, React.CSSProperties> = {
        primary: {
            backgroundColor: '#6366f1',
            color: 'white',
            border: 'none',
        },
        secondary: {
            backgroundColor: 'transparent',
            color: '#6366f1',
            border: '1px solid #6366f1',
        },
        text: {
            backgroundColor: 'transparent',
            color: '#6366f1',
            border: 'none',
        },
    };

    return (
        <button
            className={`a2ui-button a2ui-button--${variant}`}
            data-component-id={componentId}
            onClick={handleClick}
            style={{
                padding: '0.5rem 1rem',
                borderRadius: '6px',
                fontSize: '0.875rem',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                ...variantStyles[variant],
            }}
        >
            {label}
        </button>
    );
}
