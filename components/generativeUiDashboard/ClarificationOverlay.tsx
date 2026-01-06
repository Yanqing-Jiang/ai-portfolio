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
    /** Value submitted to backend */
    value: string;
    /** Display label */
    label: string;
    /** Optional icon */
    icon?: string;
}

interface ClarificationField {
    /** Field ID used for backend submission */
    id: string;
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
}

interface ClarificationRequest {
    /** Unique ID for this clarification request */
    id: string;
    /** Title of the clarification card */
    title?: string;
    /** Subtitle or description */
    subtitle?: string;
    /** Fields in this clarification request */
    fields: ClarificationField[];
    /** Optional component ID this clarification targets (for individual widget overlay) */
    targetComponentId?: string;
}

interface ClarificationOverlayProps {
    /** The clarification request to display */
    request: ClarificationRequest | null;
    /** Callback when user submits their responses (fieldId -> response) */
    onSubmit: (requestId: string, responses: Record<string, string | string[]>, skipped: boolean) => void;
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
            input: 'rgba(30, 41, 59, 0.8)',
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
    const [responses, setResponses] = useState<Record<string, string | string[]>>({});
    const overlayRef = useRef<HTMLDivElement>(null);
    const [anchorStyle, setAnchorStyle] = useState<React.CSSProperties | null>(null);

    // Reset responses when request changes
    useEffect(() => {
        if (request) {
            setResponses({});
        }
    }, [request?.id]);

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

    const handleOptionClick = useCallback((fieldId: string, value: string, type: 'single_choice' | 'multi_choice', maxSelections?: number) => {
        setResponses((prev) => {
            const current = prev[fieldId] || (type === 'multi_choice' ? [] : '');

            if (type === 'single_choice') {
                return { ...prev, [fieldId]: value };
            } else {
                const currentArr = Array.isArray(current) ? current : [];
                if (currentArr.includes(value)) {
                    return { ...prev, [fieldId]: currentArr.filter((v) => v !== value) };
                }
                if (maxSelections && currentArr.length >= maxSelections) {
                    return prev;
                }
                return { ...prev, [fieldId]: [...currentArr, value] };
            }
        });
    }, []);

    const handleFreeformChange = useCallback((fieldId: string, value: string) => {
        setResponses((prev) => ({ ...prev, [fieldId]: value }));
    }, []);

    const handleSubmit = useCallback(() => {
        if (!request) return;
        onSubmit(request.id, responses, false);
    }, [request, responses, onSubmit]);

    const handleSkip = useCallback(() => {
        if (!request) return;
        onSubmit(request.id, {}, true);
    }, [request, onSubmit]);

    const handleDismiss = useCallback(() => {
        if (!request) return;
        onDismiss(request.id);
    }, [request, onDismiss]);

    const isFieldValid = (field: ClarificationField) => {
        const response = responses[field.id];
        if (field.type === 'freeform') {
            return typeof response === 'string' && response.trim().length > 0;
        }
        return Array.isArray(response) ? response.length > 0 : (typeof response === 'string' && response.length > 0);
    };

    const canSubmit = request?.fields.every(f => isFieldValid(f));

    return (
        <AnimatePresence>
            {request && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className={`clarification-overlay ${fullScreen ? 'fixed inset-0 z-[100]' : 'absolute inset-0'}`}
                    ref={overlayRef}
                    style={{
                        backgroundColor: theme.colors.bg.overlay,
                        backdropFilter: 'blur(8px)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '1rem',
                        // Ensure overlay covers entire viewport and prevents scroll
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        overflow: 'auto',
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
                            // For anchored mode, use absolute positioning; otherwise flex handles centering
                            position: isAnchored ? 'absolute' : 'relative',
                            // Ensure card stays in visible area
                            margin: isAnchored ? 0 : 'auto',
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
                                    {request.title || 'Quick Question'}
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

                        {/* Subtitle */}
                        {request.subtitle && (
                            <p
                                className="mb-4 text-sm"
                                style={{ color: theme.colors.text.secondary, lineHeight: 1.6 }}
                            >
                                {request.subtitle}
                            </p>
                        )}

                        {/* Fields */}
                        <div className="space-y-6 mb-6">
                            {request.fields.map((field) => (
                                <div key={field.id} className="clarification-field">
                                    <label
                                        className="block text-sm font-medium mb-2"
                                        style={{ color: theme.colors.text.secondary }}
                                    >
                                        {field.prompt}
                                    </label>

                                    {/* Options (for single/multi choice) */}
                                    {(field.type === 'single_choice' || field.type === 'multi_choice') && field.options && (
                                        <div className="flex flex-wrap gap-2">
                                            {field.options.map((opt) => {
                                                const currentResponse = responses[field.id];
                                                const isSelected = Array.isArray(currentResponse)
                                                    ? currentResponse.includes(opt.value)
                                                    : currentResponse === opt.value;
                                                return (
                                                    <motion.button
                                                        key={opt.value}
                                                        onClick={() => handleOptionClick(field.id, opt.value, field.type as any, field.maxSelections)}
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
                                                            fontSize: '0.85rem',
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
                                    {field.type === 'freeform' && (
                                        <textarea
                                            value={(responses[field.id] as string) || ''}
                                            onChange={(e) => handleFreeformChange(field.id, e.target.value)}
                                            placeholder={field.placeholder || 'Type your response...'}
                                            rows={2}
                                            className="w-full p-3 rounded-lg resize-none outline-none text-sm"
                                            style={{
                                                backgroundColor: theme.colors.bg.input,
                                                border: `1px solid ${theme.colors.bg.cardBorder}`,
                                                color: theme.colors.text.primary,
                                            }}
                                        />
                                    )}
                                </div>
                            ))}
                        </div>

                        {/* Actions */}
                        <div className="flex justify-end gap-3 pt-2">
                            <button
                                onClick={handleSkip}
                                className="px-4 py-2 rounded-lg transition-colors text-sm"
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
                                className="px-6 py-2 rounded-lg font-medium transition-all text-sm"
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

export type { ClarificationRequest, ClarificationOption, ClarificationField };
export default ClarificationOverlay;
