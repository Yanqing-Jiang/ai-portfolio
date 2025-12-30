/**
 * A2UI MultipleChoice Component
 *
 * Renders selectable options with max selection support.
 */

import React, { useCallback, useMemo, useState } from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { MultipleChoiceProps, MultipleChoiceOption } from '../../a2ui/types';
import { resolveArray, resolveString } from '../../a2ui/DataBinder';

/**
 * Function: A2UIMultipleChoice — registered in componentRegistry; renders selectable pills with max selection enforcement; backs the standard A2UI MultipleChoice component.
 */
export function A2UIMultipleChoice({
    componentId,
    props,
    dataModel,
    onAction,
}: A2UIRendererProps): React.ReactElement {
    const mcProps = props as unknown as MultipleChoiceProps;
    const options = useMemo(() => mcProps.options || [], [mcProps.options]);
    const initialSelections = resolveArray<string>(mcProps.selections, dataModel, []);
    const maxSelections = mcProps.maxAllowedSelections ?? options.length;
    const [selected, setSelected] = useState<string[]>(initialSelections);

    const toggle = useCallback(
        (value: string) => {
            setSelected((prev) => {
                const exists = prev.includes(value);
                let next: string[];
                if (exists) {
                    next = prev.filter((v) => v !== value);
                } else if (prev.length < maxSelections) {
                    next = [...prev, value];
                } else {
                    next = prev;
                }
                onAction('multiple_choice_change', { componentId, selections: next });
                return next;
            });
        },
        [componentId, onAction, maxSelections]
    );

    return (
        <div data-component-id={componentId} className="a2ui-multiple-choice" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {options.map((opt: MultipleChoiceOption, idx: number) => {
                const label = resolveString(opt.label, dataModel, opt.value || `Option ${idx + 1}`);
                const value = opt.value;
                const active = selected.includes(value);
                return (
                    <button
                        key={value}
                        onClick={() => toggle(value)}
                        style={{
                            padding: '0.4rem 0.75rem',
                            borderRadius: '999px',
                            border: active ? '1px solid #f43f5e' : '1px solid rgba(148,163,184,0.5)',
                            background: active ? 'rgba(244,63,94,0.15)' : 'transparent',
                            color: active ? '#f43f5e' : '#e2e8f0',
                            cursor: 'pointer',
                        }}
                    >
                        {label}
                    </button>
                );
            })}
        </div>
    );
}
