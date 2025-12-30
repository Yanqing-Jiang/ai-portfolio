/**
 * Function: ErrorPanel — registered in componentRegistry; renders backend error code/message
 * from /data/error; exists to surface validation/agent errors to the user.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import { resolveString } from '../../a2ui/DataBinder';

export function ErrorPanel({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const code = resolveString((props as any).code, dataModel, 'unknown_error');
    const message = resolveString((props as any).message, dataModel, 'An error occurred.');
    const details = resolveString((props as any).details, dataModel, '');

    return (
        <div
            data-component-id={componentId}
            style={{
                border: '1px solid rgba(239,68,68,0.5)',
                background: 'rgba(239,68,68,0.1)',
                color: '#fecdd3',
                padding: '1rem',
                borderRadius: '10px',
            }}
        >
            <div style={{ fontWeight: 700, marginBottom: '0.25rem' }}>Error: {code}</div>
            <div style={{ marginBottom: '0.5rem' }}>{message}</div>
            {details ? (
                <pre
                    style={{
                        background: 'rgba(15,23,42,0.6)',
                        padding: '0.75rem',
                        borderRadius: '8px',
                        color: '#e2e8f0',
                        overflow: 'auto',
                        fontSize: '0.85rem',
                    }}
                >
                    {details}
                </pre>
            ) : null}
        </div>
    );
}
