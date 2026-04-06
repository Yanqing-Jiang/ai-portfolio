/**
 * DisclaimerBanner — Collapsible disclaimer with follow-up action buttons.
 *
 * Renders guardrail message, toggleable disclaimer text,
 * and follow-up action buttons for fortune readings.
 *
 * Called from: ComponentRenderer.tsx via Registry
 * Data path: /data/guardrail (emitted by stream_bridge.emit_guardrail)
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';

interface FollowUpButton {
    id: string;
    label: string;
}

interface GuardrailData {
    level: 'info' | 'warning' | 'critical';
    message: string;
    disclaimer: string;
    followUpButtons: FollowUpButton[];
}

const LEVEL_STYLES: Record<string, { border: string; icon: string }> = {
    info: { border: 'rgba(100, 116, 139, 0.4)', icon: 'ℹ️' },
    warning: { border: 'rgba(245, 158, 11, 0.6)', icon: '⚠️' },
    critical: { border: 'rgba(239, 68, 68, 0.6)', icon: '🔴' },
};

export function DisclaimerBanner({
    componentId,
    props,
    dataModel,
    onAction,
}: A2UIRendererProps): React.ReactElement {
    const data = resolveBoundValue(
        props.guardrailPath as BoundValue | undefined,
        dataModel
    ) as GuardrailData | undefined;

    const [showDisclaimer, setShowDisclaimer] = useState(false);

    if (!data) {
        return <div data-component-id={componentId} />;
    }

    const levelStyle = LEVEL_STYLES[data.level] || LEVEL_STYLES.info;

    return (
        <motion.div
            data-component-id={componentId}
            className="w-full rounded-lg p-4"
            style={{
                background: 'rgba(148, 163, 184, 0.04)',
                border: `1px solid ${levelStyle.border}`,
            }}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 200, damping: 25, mass: 0.8 }}
        >
            {/* Message */}
            <div className="flex items-start gap-2">
                <span className="text-sm">{levelStyle.icon}</span>
                <p className="text-sm leading-relaxed text-slate-300">
                    {data.message}
                </p>
            </div>

            {/* Disclaimer toggle */}
            {data.disclaimer && (
                <div className="mt-2">
                    <button
                        className="text-xs text-slate-500 underline decoration-dotted hover:text-slate-400"
                        onClick={() => setShowDisclaimer(!showDisclaimer)}
                    >
                        {showDisclaimer ? 'Hide disclaimer' : 'Show disclaimer'}
                    </button>
                    <AnimatePresence>
                        {showDisclaimer && (
                            <motion.p
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                transition={{ duration: 0.2 }}
                                className="mt-1 overflow-hidden text-xs leading-relaxed text-slate-500"
                            >
                                {data.disclaimer}
                            </motion.p>
                        )}
                    </AnimatePresence>
                </div>
            )}

            {/* Follow-up buttons */}
            {data.followUpButtons?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                    {data.followUpButtons.map((btn) => (
                        <button
                            key={btn.id}
                            className="w-full min-h-[44px] rounded-full px-4 py-2 text-sm font-medium transition-colors sm:w-auto"
                            style={{
                                background: 'rgba(148, 163, 184, 0.08)',
                                border: '1px solid rgba(148, 163, 184, 0.2)',
                                color: '#e2e8f0',
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.background =
                                    'rgba(148, 163, 184, 0.15)';
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.background =
                                    'rgba(148, 163, 184, 0.08)';
                            }}
                            onClick={() =>
                                onAction('userAction', { actionId: btn.id })
                            }
                        >
                            {btn.label}
                        </button>
                    ))}
                </div>
            )}
        </motion.div>
    );
}
