/**
 * Function: ClarificationCard — Renders HITL clarification widgets for pre-generation guidance
 * Called from: GenerativeUIPage when clarificationRequest is present
 * Purpose: Displays LLM-chosen input types (single/multi choice, dropdown, freeform) for user to customize
 */

import React, { useState } from 'react';
import { motion } from 'framer-motion';

// Types matching backend clarification.py
export interface ClarificationOption {
    id: string;
    label: string;
    description?: string;
    icon?: string;
}

export interface ClarificationField {
    field_id: string;
    input_type: 'single_choice' | 'multi_choice' | 'dropdown' | 'freeform' | 'ticker_select' | 'timeframe_select';
    label: string;
    prompt?: string;
    required: boolean;
    options?: ClarificationOption[];
    placeholder?: string;
    default?: string;
}

export interface ClarificationRequest {
    request_id: string;
    title: string;
    subtitle?: string;
    fields: ClarificationField[];
    timeout_seconds: number;
    skip_allowed: boolean;
}

interface ClarificationCardProps {
    request: ClarificationRequest;
    onSubmit: (values: Record<string, any>, skipped: boolean) => Promise<void>;
    onCancel: () => void;
    isSubmitting?: boolean;
}

// Theme matching GenerativeUI styles
const theme = {
    bg: {
        primary: '#0a0f1a',
        secondary: '#111827',
        tertiary: '#1f2937',
        elevated: '#172033',
    },
    accent: {
        primary: '#f59e0b',
        muted: 'rgba(245, 158, 11, 0.1)',
        gradient: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
    },
    text: {
        primary: '#f3f4f6',
        secondary: '#9ca3af',
        muted: '#6b7280',
    },
    border: {
        subtle: 'rgba(255, 255, 255, 0.08)',
        medium: 'rgba(255, 255, 255, 0.12)',
    },
};

const ClarificationCard: React.FC<ClarificationCardProps> = ({
    request,
    onSubmit,
    onCancel,
    isSubmitting = false,
}) => {
    const [values, setValues] = useState<Record<string, any>>(() => {
        // Initialize with defaults
        const initial: Record<string, any> = {};
        request.fields.forEach(field => {
            if (field.default) {
                initial[field.field_id] = field.input_type === 'multi_choice' ? [field.default] : field.default;
            }
        });
        return initial;
    });

    const handleFieldChange = (fieldId: string, value: any) => {
        setValues(prev => ({ ...prev, [fieldId]: value }));
    };

    const handleMultiChoiceToggle = (fieldId: string, optionId: string) => {
        setValues(prev => {
            const current = prev[fieldId] || [];
            if (current.includes(optionId)) {
                return { ...prev, [fieldId]: current.filter((id: string) => id !== optionId) };
            } else {
                return { ...prev, [fieldId]: [...current, optionId] };
            }
        });
    };

    const canSubmit = request.fields.every(field => {
        if (!field.required) return true;
        const val = values[field.field_id];
        if (field.input_type === 'multi_choice') return val && val.length > 0;
        if (field.input_type === 'freeform') return val && val.trim();
        return val;
    });

    const handleSubmit = () => onSubmit(values, false);
    const handleSkip = () => onSubmit({}, true);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={{ duration: 0.3 }}
            className="rounded-xl overflow-hidden"
            style={{
                backgroundColor: theme.bg.elevated,
                border: `1px solid ${theme.accent.primary}40`,
                boxShadow: `0 0 30px ${theme.accent.primary}20`,
            }}
        >
            {/* Header */}
            <div
                className="px-5 py-4"
                style={{
                    background: `linear-gradient(135deg, ${theme.bg.secondary} 0%, ${theme.bg.tertiary} 100%)`,
                    borderBottom: `1px solid ${theme.border.subtle}`,
                }}
            >
                <div className="flex items-center gap-3">
                    <span className="text-2xl">🎯</span>
                    <div>
                        <h3 className="text-base font-semibold" style={{ color: theme.text.primary }}>
                            {request.title}
                        </h3>
                        {request.subtitle && (
                            <p className="text-sm mt-0.5" style={{ color: theme.text.secondary }}>
                                {request.subtitle}
                            </p>
                        )}
                    </div>
                </div>
            </div>

            {/* Fields */}
            <div className="px-5 py-4 space-y-5">
                {request.fields.map(field => (
                    <div key={field.field_id}>
                        <label className="block text-sm font-medium mb-2" style={{ color: theme.text.primary }}>
                            {field.label}
                            {field.required && <span style={{ color: theme.accent.primary }}> *</span>}
                        </label>

                        {/* Single Choice - Radio buttons */}
                        {field.input_type === 'single_choice' && field.options && (
                            <div className="space-y-2">
                                {field.options.map(opt => (
                                    <motion.button
                                        key={opt.id}
                                        onClick={() => handleFieldChange(field.field_id, opt.id)}
                                        className="w-full p-3 rounded-lg text-left transition-all flex items-start gap-3"
                                        style={{
                                            backgroundColor: values[field.field_id] === opt.id ? theme.accent.muted : theme.bg.tertiary,
                                            border: `1px solid ${values[field.field_id] === opt.id ? theme.accent.primary : theme.border.subtle}`,
                                        }}
                                        whileHover={{ borderColor: theme.accent.primary + '60' }}
                                        whileTap={{ scale: 0.98 }}
                                        disabled={isSubmitting}
                                    >
                                        {/* Radio indicator */}
                                        <div
                                            className="w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5"
                                            style={{
                                                borderColor: values[field.field_id] === opt.id ? theme.accent.primary : theme.text.muted,
                                            }}
                                        >
                                            {values[field.field_id] === opt.id && (
                                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: theme.accent.primary }} />
                                            )}
                                        </div>
                                        <div className="flex-1">
                                            <span className="flex items-center gap-2">
                                                {opt.icon && <span>{opt.icon}</span>}
                                                <span className="text-sm font-medium" style={{ color: theme.text.primary }}>
                                                    {opt.label}
                                                </span>
                                            </span>
                                            {opt.description && (
                                                <span className="text-xs block mt-0.5" style={{ color: theme.text.muted }}>
                                                    {opt.description}
                                                </span>
                                            )}
                                        </div>
                                    </motion.button>
                                ))}
                            </div>
                        )}

                        {/* Multi Choice - Checkboxes */}
                        {field.input_type === 'multi_choice' && field.options && (
                            <div className="space-y-2">
                                {field.options.map(opt => {
                                    const selected = (values[field.field_id] || []).includes(opt.id);
                                    return (
                                        <motion.button
                                            key={opt.id}
                                            onClick={() => handleMultiChoiceToggle(field.field_id, opt.id)}
                                            className="w-full p-3 rounded-lg text-left transition-all flex items-start gap-3"
                                            style={{
                                                backgroundColor: selected ? theme.accent.muted : theme.bg.tertiary,
                                                border: `1px solid ${selected ? theme.accent.primary : theme.border.subtle}`,
                                            }}
                                            whileHover={{ borderColor: theme.accent.primary + '60' }}
                                            whileTap={{ scale: 0.98 }}
                                            disabled={isSubmitting}
                                        >
                                            {/* Checkbox indicator */}
                                            <div
                                                className="w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 mt-0.5"
                                                style={{
                                                    borderColor: selected ? theme.accent.primary : theme.text.muted,
                                                    backgroundColor: selected ? theme.accent.primary : 'transparent',
                                                }}
                                            >
                                                {selected && (
                                                    <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                                                        <path d="M2 6L5 9L10 3" stroke={theme.bg.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                                    </svg>
                                                )}
                                            </div>
                                            <div className="flex-1">
                                                <span className="flex items-center gap-2">
                                                    {opt.icon && <span>{opt.icon}</span>}
                                                    <span className="text-sm font-medium" style={{ color: theme.text.primary }}>
                                                        {opt.label}
                                                    </span>
                                                </span>
                                                {opt.description && (
                                                    <span className="text-xs block mt-0.5" style={{ color: theme.text.muted }}>
                                                        {opt.description}
                                                    </span>
                                                )}
                                            </div>
                                        </motion.button>
                                    );
                                })}
                            </div>
                        )}

                        {/* Dropdown */}
                        {field.input_type === 'dropdown' && field.options && (
                            <select
                                value={values[field.field_id] || ''}
                                onChange={(e) => handleFieldChange(field.field_id, e.target.value)}
                                className="w-full px-4 py-3 rounded-lg text-sm appearance-none cursor-pointer"
                                style={{
                                    backgroundColor: theme.bg.tertiary,
                                    border: `1px solid ${theme.border.medium}`,
                                    color: theme.text.primary,
                                    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%239ca3af'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E")`,
                                    backgroundRepeat: 'no-repeat',
                                    backgroundPosition: 'right 12px center',
                                    backgroundSize: '20px',
                                }}
                                disabled={isSubmitting}
                            >
                                <option value="">Select...</option>
                                {field.options.map(opt => (
                                    <option key={opt.id} value={opt.id}>
                                        {opt.icon ? `${opt.icon} ${opt.label}` : opt.label}
                                    </option>
                                ))}
                            </select>
                        )}

                        {/* Freeform input */}
                        {field.input_type === 'freeform' && (
                            <input
                                type="text"
                                value={values[field.field_id] || ''}
                                onChange={(e) => handleFieldChange(field.field_id, e.target.value)}
                                placeholder={field.placeholder || 'Enter value...'}
                                className="w-full px-4 py-3 rounded-lg text-sm"
                                style={{
                                    backgroundColor: theme.bg.tertiary,
                                    border: `1px solid ${theme.border.medium}`,
                                    color: theme.text.primary,
                                }}
                                disabled={isSubmitting}
                            />
                        )}

                        {field.prompt && (
                            <p className="text-xs mt-2" style={{ color: theme.text.muted }}>
                                {field.prompt}
                            </p>
                        )}
                    </div>
                ))}
            </div>

            {/* Actions */}
            <div
                className="px-5 py-4 flex items-center justify-between"
                style={{
                    borderTop: `1px solid ${theme.border.subtle}`,
                    backgroundColor: theme.bg.secondary,
                }}
            >
                <button
                    onClick={onCancel}
                    className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                    style={{ color: theme.text.secondary }}
                    disabled={isSubmitting}
                >
                    Cancel
                </button>

                <div className="flex items-center gap-3">
                    {request.skip_allowed && (
                        <button
                            onClick={handleSkip}
                            className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                            style={{
                                color: theme.text.secondary,
                                backgroundColor: theme.bg.tertiary,
                            }}
                            disabled={isSubmitting}
                        >
                            Skip & Let AI Decide
                        </button>
                    )}
                    <motion.button
                        onClick={handleSubmit}
                        disabled={!canSubmit || isSubmitting}
                        className="px-5 py-2 rounded-lg text-sm font-semibold transition-all"
                        style={{
                            background: canSubmit ? theme.accent.gradient : theme.bg.tertiary,
                            color: canSubmit ? theme.bg.primary : theme.text.muted,
                            opacity: isSubmitting ? 0.7 : 1,
                        }}
                        whileHover={canSubmit ? { scale: 1.02 } : {}}
                        whileTap={canSubmit ? { scale: 0.98 } : {}}
                    >
                        {isSubmitting ? 'Processing...' : 'Continue →'}
                    </motion.button>
                </div>
            </div>
        </motion.div>
    );
};

export default ClarificationCard;
