/**
 * A2UI Modal Component
 *
 * Wraps a trigger (entryPointChild) and modal content (contentChild).
 */

import React, { useState } from 'react';
import type { A2UIRendererProps } from '../Registry';
import type { ModalProps } from '../../a2ui/types';

/**
 * Function: A2UIModal — registered in componentRegistry; wraps a trigger child and overlays modal content; supports the standard A2UI Modal component.
 */
export function A2UIModal({
    componentId,
    props,
    renderChild,
}: A2UIRendererProps): React.ReactElement {
    const modalProps = props as unknown as ModalProps;
    const [open, setOpen] = useState(false);

    return (
        <div data-component-id={componentId} className="a2ui-modal">
            <div onClick={() => setOpen(true)} style={{ display: 'inline-block', cursor: 'pointer' }}>
                {renderChild(modalProps.entryPointChild)}
            </div>

            {open && (
                <div
                    className="a2ui-modal__overlay"
                    onClick={() => setOpen(false)}
                    style={{
                        position: 'fixed',
                        inset: 0,
                        backgroundColor: 'rgba(0,0,0,0.5)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 50,
                    }}
                >
                    <div
                        className="a2ui-modal__content"
                        onClick={(e) => e.stopPropagation()}
                        style={{
                            background: '#0f172a',
                            border: '1px solid rgba(148,163,184,0.4)',
                            borderRadius: '12px',
                            padding: '1rem',
                            minWidth: '320px',
                            maxWidth: '640px',
                            width: '80%',
                        }}
                    >
                        <div style={{ textAlign: 'right', marginBottom: '0.5rem' }}>
                            <button
                                onClick={() => setOpen(false)}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    color: '#cbd5e1',
                                    cursor: 'pointer',
                                    fontSize: '1.2rem',
                                }}
                                aria-label="Close modal"
                            >
                                ×
                            </button>
                        </div>
                        {renderChild(modalProps.contentChild)}
                    </div>
                </div>
            )}
        </div>
    );
}
