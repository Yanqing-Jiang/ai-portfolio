/**
 * A2UI Slider Component
 *
 * Simple range input for numeric selection.
 */

import React, { useCallback, useState } from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { SliderProps } from '../../a2ui/types';
import { resolveNumber } from '../../a2ui/DataBinder';

/**
 * Function: A2UISlider — registered in componentRegistry; renders a range input and emits value changes; supports the standard A2UI Slider component.
 */
export function A2UISlider({
    componentId,
    props,
    dataModel,
    onAction,
}: A2UIRendererProps): React.ReactElement {
    const sliderProps = props as unknown as SliderProps;
    const initial = resolveNumber(sliderProps.value, dataModel, 0);
    const [value, setValue] = useState(initial);
    const min = sliderProps.minValue ?? 0;
    const max = sliderProps.maxValue ?? 100;

    const handleChange = useCallback(
        (event: React.ChangeEvent<HTMLInputElement>) => {
            const next = Number(event.target.value);
            setValue(next);
            onAction('slider_change', { componentId, value: next });
        },
        [componentId, onAction]
    );

    return (
        <div data-component-id={componentId} style={{ width: '100%' }}>
            <input
                type="range"
                min={min}
                max={max}
                value={value}
                onChange={handleChange}
                style={{ width: '100%' }}
            />
            <div style={{ fontSize: '0.85rem', color: '#cbd5e1', marginTop: '0.25rem' }}>{value}</div>
        </div>
    );
}
