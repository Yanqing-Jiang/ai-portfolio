/**
 * A2UI TextField Component
 *
 * Basic input with label and optional validation.
 */

import React, { useCallback, useState } from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { TextFieldProps } from '../../a2ui/types';
import { resolveString } from '../../a2ui/DataBinder';

/**
 * Function: A2UITextField — registered in componentRegistry; renders labeled text inputs with optional validation; supports the standard A2UI TextField component.
 */
export function A2UITextField({
    componentId,
    props,
    dataModel,
    onAction,
}: A2UIRendererProps): React.ReactElement {
    const tfProps = props as unknown as TextFieldProps;
    const label = resolveString(tfProps.label, dataModel, 'Text Field');
    const initial = resolveString(tfProps.text, dataModel, '');
    const [value, setValue] = useState(initial);

    const inputType = tfProps.textFieldType || 'text';
    const pattern = tfProps.validationRegexp;

    const handleChange = useCallback(
        (event: React.ChangeEvent<HTMLInputElement>) => {
            const next = event.target.value;
            setValue(next);
            onAction('text_field_change', { componentId, value: next });
        },
        [componentId, onAction]
    );

    return (
        <label data-component-id={componentId} style={{ display: 'block', width: '100%' }}>
            <span style={{ display: 'block', marginBottom: '0.25rem', color: '#cbd5e1', fontSize: '0.9rem' }}>
                {label}
            </span>
            <input
                type={inputType}
                value={value}
                pattern={pattern}
                onChange={handleChange}
                style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    borderRadius: '6px',
                    border: '1px solid rgba(148,163,184,0.4)',
                    backgroundColor: 'rgba(15,23,42,0.4)',
                    color: '#f8fafc',
                }}
            />
        </label>
    );
}
