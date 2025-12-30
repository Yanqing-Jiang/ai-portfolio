/**
 * A2UI Tabs Component
 *
 * Renders tab headers and the active child component.
 */

import React, { useMemo, useState } from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { TabsProps } from '../../a2ui/types';
import { resolveString } from '../../a2ui/DataBinder';

/**
 * Function: A2UITabs — registered via componentRegistry; renders tab headers and swaps child surfaces; enables the standard A2UI Tabs component for multi-view layouts.
 */
export function A2UITabs({
    componentId,
    props,
    dataModel,
    renderChild,
}: A2UIRendererProps): React.ReactElement {
    const { tabItems } = props as unknown as TabsProps;
    const items = useMemo(() => tabItems || [], [tabItems]);
    const [activeIndex, setActiveIndex] = useState(0);

    const activeItem = items[activeIndex] || items[0];

    return (
        <div className="a2ui-tabs" data-component-id={componentId}>
            <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid rgba(148,163,184,0.3)' }}>
                {items.map((item, idx) => {
                    const title = resolveString(item.title, dataModel, `Tab ${idx + 1}`);
                    const isActive = idx === activeIndex;
                    return (
                        <button
                            key={idx}
                            onClick={() => setActiveIndex(idx)}
                            style={{
                                padding: '0.5rem 0.75rem',
                                border: 'none',
                                borderBottom: isActive ? '2px solid #f43f5e' : '2px solid transparent',
                                background: 'transparent',
                                color: isActive ? '#f43f5e' : '#94a3b8',
                                cursor: 'pointer',
                                fontWeight: 600,
                            }}
                        >
                            {title}
                        </button>
                    );
                })}
            </div>
            <div style={{ paddingTop: '0.75rem' }}>
                {activeItem ? renderChild(activeItem.child) : null}
            </div>
        </div>
    );
}
