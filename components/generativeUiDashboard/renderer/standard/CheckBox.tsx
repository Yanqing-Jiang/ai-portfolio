/**
 * A2UI CheckBox Component
 *
 * Simple checkbox with label.
 */

import React, { useCallback, useState } from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { CheckBoxProps } from '../../a2ui/types';
import { resolveBoolean, resolveString } from '../../a2ui/DataBinder';

/**
 * Function: A2UICheckBox — registered in componentRegistry; renders a labeled checkbox and forwards state via onAction; supports the standard A2UI CheckBox component.
 */
export function A2UICheckBox({
    componentId,
    props,
    dataModel,
    onAction,
}: A2UIRendererProps): React.ReactElement {
    const checkProps = props as unknown as CheckBoxProps;
    const label = resolveString(checkProps.label, dataModel, 'Option');
    const initialValue = resolveBoolean(checkProps.value, dataModel, false);
    const [checked, setChecked] = useState(initialValue);

    const handleChange = useCallback(
        (event: React.ChangeEvent<HTMLInputElement>) => {
            const next = event.target.checked;
            setChecked(next);
            onAction('toggle_checkbox', { componentId, value: next });
        },
        [componentId, onAction]
    );

    return (
        <label
            data-component-id={componentId}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}
        >
            <input type="checkbox" checked={checked} onChange={handleChange} />
            <span>{label}</span>
        </label>
    );
}
