// --- Function/Class Map ---
// Component: ClarificationOverlay
//   Role: Render clarification prompts and collect user responses.
//   Called from: components/generativeUiDashboard/GenerativeUIPage.tsx
//   Invokes: onSubmit/onDismiss callbacks, framer-motion animations
//   Why: Blocks streaming until clarification is answered or skipped.
// --- End Function/Class Map ---
/**
 * ClarificationOverlay Component
 *
 * A2UI-native clarification overlay using Modal/MultipleChoice components.
 * Called from: GenerativeUIPage.tsx when agent needs user clarification
 * Why: Provides pre-generation and mid-stream clarification without custom UI
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface ClarificationOption {
    label: string;
    value: string;
    description?: string;
}

interface ClarificationRequest {
    /** Unique ID for this clarification request */
    id: string;
    /** Field ID used for backend submission */
    fieldId?: string;
    /** Type of clarification */
    type: 'single_choice' | 'multi_choice' | 'freeform';
    /** Question or prompt to show the user */
    prompt: string;
    /** Options for choice-based clarification */
    options?: ClarificationOption[];
    /** Max selections for multi_choice */
    maxSelections?: number;
    /** Optional placeholder for freeform input */
    placeholder?: string;
    /** Optional component ID this clarification targets (for individual widget overlay) */
    targetComponentId?: string;
}

interface ClarificationOverlayProps {
    /** The clarification request to display */
    request: ClarificationRequest | null;
    /** Callback when user submits their response */
    onSubmit: (requestId: string, response: string | string[]) => void;
    /** Callback when user dismisses without answering */
    onDismiss: (requestId: string) => void;
    /** Whether this is targeting the whole dashboard or a specific component */
    fullScreen?: boolean;
}

const theme = {
    colors: {
        bg: {
            overlay: 'rgba(10, 15, 26, 0.85)',
            card: '#1e293b',
            cardBorder: 'rgba(148, 163, 184, 0.2)',
        },
        accent: {
            primary: '#f43f5e',
            muted: 'rgba(244, 63, 94, 0.15)',
        },
        text: {
            primary: '#f8fafc',
            secondary: '#94a3b8',
            muted: '#64748b',
        },
    },
};

const ICONS = {
    prompt: 'ASK',
    close: 'x',
};

/**
 * ClarificationOverlay Component
 */
export function ClarificationOverlay({
    request,
    onSubmit,
    onDismiss,
    fullScreen = true,
}: ClarificationOverlayProps): React.ReactElement | null {
    const [selectedValues, setSelectedValues] = useState<string[]>([]);
    const [freeformValue, setFreeformValue] = useState('');
    const overlayRef = useRef<HTMLDivElement>(null);
    const [anchorStyle, setAnchorStyle] = useState<React.CSSProperties | null>(null);

    useEffect(() => {
        if (!request?.targetComponentId) {
            setAnchorStyle(null);
            return;
        }

        const updateAnchor = () => {
            const target = document.querySelector<HTMLElement>(
                `[data-component-id="${request.targetComponentId}"]`
            );
            const overlayEl = overlayRef.current;
            if (!target || !overlayEl) {
                setAnchorStyle(null);
                return;
            }

            const targetRect = target.getBoundingClientRect();
            const overlayRect = overlayEl.getBoundingClientRect();
            const top = targetRect.top - overlayRect.top + targetRect.height / 2;
            const left = targetRect.left - overlayRect.left + targetRect.width / 2;
            setAnchorStyle({ top, left, transform: 'translate(-50%, -50%)' });
        };

        updateAnchor();
        window.addEventListener('resize', updateAnchor);
        window.addEventListener('scroll', updateAnchor, true);
        return () => {
            window.removeEventListener('resize', updateAnchor);
            window.removeEventListener('scroll', updateAnchor, true);
        };
    }, [request?.targetComponentId]);

    const isAnchored = Boolean(request?.targetComponentId && anchorStyle);

    const handleOptionClick = useCallback((value: string) => {
        if (!request) return;

        if (request.type === 'single_choice') {
            setSelectedValues([value]);
        } else if (request.type === 'multi_choice') {
            setSelectedValues((prev) => {
                if (prev.includes(value)) {
                    return prev.filter((v) => v !== value);
                }
                if (request.maxSelections && prev.length >= request.maxSelections) {
                    return prev;
                }
                return [...prev, value];
            });
        }
    }, [request]);

    const handleSubmit = useCallback(() => {
        if (!request) return;

        if (request.type === 'freeform') {
            onSubmit(request.id, freeformValue);
        } else if (request.type === 'single_choice') {
            onSubmit(request.id, selectedValues[0] || '');
        } else {
            onSubmit(request.id, selectedValues);
        }

        // Reset state
        setSelectedValues([]);
        setFreeformValue('');
    }, [request, selectedValues, freeformValue, onSubmit]);

    const handleDismiss = useCallback(() => {
        if (!request) return;
        onDismiss(request.id);
        setSelectedValues([]);
        setFreeformValue('');
    }, [request, onDismiss]);

    const canSubmit = request?.type === 'freeform'
        ? freeformValue.trim().length > 0
        : selectedValues.length > 0;

    return (
        <AnimatePresence>
            {request && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className={`clarification-overlay ${fullScreen ? 'fixed inset-0 z-50' : 'absolute inset-0'}`}
                    ref={overlayRef}
                    style={{
                        backgroundColor: theme.colors.bg.overlay,
                        backdropFilter: 'blur(8px)',
                        display: isAnchored ? 'block' : 'flex',
                        alignItems: isAnchored ? 'stretch' : 'center',
                        justifyContent: isAnchored ? 'flex-start' : 'center',
                        padding: '1rem',
                    }}
                    onClick={handleDismiss}
                >
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 20 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        exit={{ scale: 0.95, opacity: 0, y: 20 }}
                        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                        className="clarification-card"
                        onClick={(e) => e.stopPropagation()}
                        style={{
                            backgroundColor: theme.colors.bg.card,
                            border: `1px solid ${theme.colors.bg.cardBorder}`,
                            borderRadius: '16px',
                            padding: '1.5rem',
                            maxWidth: '480px',
                            width: '100%',
                            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
                            position: isAnchored ? 'absolute' : 'relative',
                            ...(isAnchored && anchorStyle ? anchorStyle : {}),
                        }}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <span className="text-xl">{ICONS.prompt}</span>
                                <h3
                                    className="text-lg font-semibold"
                                    style={{ color: theme.colors.text.primary }}
                                >
                                    Quick Question
                                </h3>
                            </div>
                            <button
                                onClick={handleDismiss}
                                className="p-1 rounded-full transition-colors hover:bg-white/10"
                                style={{ color: theme.colors.text.muted }}
                            >
                                {ICONS.close}
                            </button>
                        </div>

                        {/* Prompt */}
                        <p
                            className="mb-4"
                            style={{ color: theme.colors.text.secondary, lineHeight: 1.6 }}
                        >
                            {request.prompt}
                        </p>

                        {/* Options (for single/multi choice) */}
                        {(request.type === 'single_choice' || request.type === 'multi_choice') && request.options && (
                            <div className="flex flex-wrap gap-2 mb-4">
                                {request.options.map((opt) => {
                                    const isSelected = selectedValues.includes(opt.value);
                                    return (
                                        <motion.button
                                            key={opt.value}
                                            onClick={() => handleOptionClick(opt.value)}
                                            whileHover={{ scale: 1.02 }}
                                            whileTap={{ scale: 0.98 }}
                                            style={{
                                                padding: '0.5rem 1rem',
                                                borderRadius: '999px',
                                                border: isSelected
                                                    ? `2px solid ${theme.colors.accent.primary}`
                                                    : `1px solid ${theme.colors.bg.cardBorder}`,
                                                background: isSelected
                                                    ? theme.colors.accent.muted
                                                    : 'transparent',
                                                color: isSelected
                                                    ? theme.colors.accent.primary
                                                    : theme.colors.text.primary,
                                                cursor: 'pointer',
                                                transition: 'all 0.2s',
                                            }}
                                        >
                                            {opt.label}
                                        </motion.button>
                                    );
                                })}
                            </div>
                        )}

                        {/* Freeform input */}
                        {request.type === 'freeform' && (
                            <textarea
                                value={freeformValue}
                                onChange={(e) => setFreeformValue(e.target.value)}
                                placeholder={request.placeholder || 'Type your response...'}
                                rows={3}
                                className="w-full mb-4 p-3 rounded-lg resize-none outline-none"
                                style={{
                                    backgroundColor: 'rgba(30, 41, 59, 0.8)',
                                    border: `1px solid ${theme.colors.bg.cardBorder}`,
                                    color: theme.colors.text.primary,
                                }}
                            />
                        )}

                        {/* Actions */}
                        <div className="flex justify-end gap-3">
                            <button
                                onClick={handleDismiss}
                                className="px-4 py-2 rounded-lg transition-colors"
                                style={{
                                    backgroundColor: 'transparent',
                                    border: `1px solid ${theme.colors.bg.cardBorder}`,
                                    color: theme.colors.text.secondary,
                                }}
                            >
                                Skip
                            </button>
                            <motion.button
                                onClick={handleSubmit}
                                disabled={!canSubmit}
                                whileHover={canSubmit ? { scale: 1.02 } : {}}
                                whileTap={canSubmit ? { scale: 0.98 } : {}}
                                className="px-4 py-2 rounded-lg font-medium transition-all"
                                style={{
                                    background: canSubmit
                                        ? `linear-gradient(135deg, ${theme.colors.accent.primary}, #f59e0b)`
                                        : theme.colors.bg.cardBorder,
                                    color: canSubmit ? 'white' : theme.colors.text.muted,
                                    cursor: canSubmit ? 'pointer' : 'not-allowed',
                                }}
                            >
                                Continue
                            </motion.button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

export type { ClarificationRequest, ClarificationOption };
export default ClarificationOverlay;
