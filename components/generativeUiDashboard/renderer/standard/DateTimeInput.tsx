/**
 * A2UI DateTimeInput Component
 *
 * Date/time selector depending on enableDate/enableTime flags.
 */

import React, { useCallback, useState } from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { DateTimeInputProps } from '../../a2ui/types';
import { resolveBoolean, resolveString } from '../../a2ui/DataBinder';

/**
 * Function: A2UIDateTimeInput — registered in componentRegistry; renders date/time picker inputs and emits user actions; supports the standard A2UI DateTimeInput component.
 */
export function A2UIDateTimeInput({
    componentId,
    props,
    dataModel,
    onAction,
}: A2UIRendererProps): React.ReactElement {
    const dtProps = props as unknown as DateTimeInputProps;
    const initial = resolveString(dtProps.value, dataModel, '');
    const [value, setValue] = useState(initial);

    const enableDate = resolveBoolean(dtProps.enableDate, dataModel, true);
    const enableTime = resolveBoolean(dtProps.enableTime, dataModel, false);
    const inputType = enableDate && enableTime ? 'datetime-local' : enableDate ? 'date' : 'time';

    const handleChange = useCallback(
        (event: React.ChangeEvent<HTMLInputElement>) => {
            const next = event.target.value;
            setValue(next);
            onAction('datetime_change', { componentId, value: next });
        },
        [componentId, onAction]
    );

    return (
        <input
            data-component-id={componentId}
            type={inputType}
            value={value}
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
    );
}
