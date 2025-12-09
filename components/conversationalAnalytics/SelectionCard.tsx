/**
 * Function: SelectionCard — Renders HITL selection cards for slot disambiguation
 * Called from: ConversationalAnalyticsPage when pendingSelection is present
 * Purpose: Displays up to 3 bundled options + optional custom input for user to pick
 */

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { SelectionRequest, SelectionOption } from './hooks/useSSEStream';
import { theme, motionVariants } from './styles';

interface SelectionCardProps {
  selection: SelectionRequest;
  sessionId: string;
  onSubmit: (sessionId: string, optionId: string | null, customValue: string | null) => Promise<void>;
  onCancel: () => void;
  isSubmitting?: boolean;
}

const SelectionCard: React.FC<SelectionCardProps> = ({
  selection,
  sessionId,
  onSubmit,
  onCancel,
  isSubmitting = false,
}) => {
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [customValue, setCustomValue] = useState('');
  const [useCustom, setUseCustom] = useState(false);

  const handleSubmit = async () => {
    if (useCustom && customValue.trim()) {
      await onSubmit(sessionId, null, customValue.trim());
    } else if (selectedOptionId) {
      await onSubmit(sessionId, selectedOptionId, null);
    }
  };

  const canSubmit = (selectedOptionId && !useCustom) || (useCustom && customValue.trim());

  return (
    <motion.div
      {...motionVariants.fadeInUp}
      className="mb-4 rounded-xl overflow-hidden"
      style={{
        backgroundColor: theme.colors.bg.elevated,
        border: `1px solid ${theme.colors.accent.primary}40`,
        boxShadow: theme.shadows.glow,
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center gap-3"
        style={{
          backgroundColor: theme.colors.thinking.bg,
          borderBottom: `1px solid ${theme.colors.thinking.border}`,
        }}
      >
        <span className="text-xl">🎯</span>
        <div>
          <h3
            className="text-sm font-semibold"
            style={{ color: theme.colors.text.primary }}
          >
            {selection.title}
          </h3>
          <p
            className="text-xs"
            style={{ color: theme.colors.text.secondary }}
          >
            {selection.prompt}
          </p>
        </div>
      </div>

      {/* Options */}
      <div className="p-4 space-y-2">
        {selection.options.map((option: SelectionOption) => (
          <motion.button
            key={option.id}
            onClick={() => {
              setSelectedOptionId(option.id);
              setUseCustom(false);
            }}
            className="w-full p-3 rounded-lg text-left transition-all flex items-start gap-3"
            style={{
              backgroundColor:
                selectedOptionId === option.id && !useCustom
                  ? theme.colors.accent.muted
                  : theme.colors.bg.tertiary,
              border: `1px solid ${
                selectedOptionId === option.id && !useCustom
                  ? theme.colors.accent.primary
                  : theme.colors.border.subtle
              }`,
            }}
            whileHover={{
              borderColor: theme.colors.accent.primary + '60',
            }}
            whileTap={{ scale: 0.98 }}
            disabled={isSubmitting}
          >
            {/* Radio indicator */}
            <div
              className="w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5"
              style={{
                borderColor:
                  selectedOptionId === option.id && !useCustom
                    ? theme.colors.accent.primary
                    : theme.colors.text.muted,
              }}
            >
              {selectedOptionId === option.id && !useCustom && (
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: theme.colors.accent.primary }}
                />
              )}
            </div>
            <div>
              <span
                className="text-sm font-medium block"
                style={{ color: theme.colors.text.primary }}
              >
                {option.label}
              </span>
              {option.description && (
                <span
                  className="text-xs block mt-0.5"
                  style={{ color: theme.colors.text.muted }}
                >
                  {option.description}
                </span>
              )}
            </div>
          </motion.button>
        ))}

        {/* Custom input option */}
        {selection.allow_custom && (
          <motion.div
            className="p-3 rounded-lg transition-all"
            style={{
              backgroundColor: useCustom
                ? theme.colors.accent.muted
                : theme.colors.bg.tertiary,
              border: `1px solid ${
                useCustom
                  ? theme.colors.accent.primary
                  : theme.colors.border.subtle
              }`,
            }}
          >
            <button
              onClick={() => {
                setUseCustom(true);
                setSelectedOptionId(null);
              }}
              className="w-full flex items-start gap-3 text-left"
              disabled={isSubmitting}
            >
              <div
                className="w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5"
                style={{
                  borderColor: useCustom
                    ? theme.colors.accent.primary
                    : theme.colors.text.muted,
                }}
              >
                {useCustom && (
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: theme.colors.accent.primary }}
                  />
                )}
              </div>
              <span
                className="text-sm font-medium"
                style={{ color: theme.colors.text.primary }}
              >
                Other (specify)
              </span>
            </button>
            {useCustom && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="mt-2 ml-7"
              >
                <input
                  type="text"
                  value={customValue}
                  onChange={(e) => setCustomValue(e.target.value)}
                  placeholder="Enter your preference..."
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{
                    backgroundColor: theme.colors.bg.primary,
                    border: `1px solid ${theme.colors.border.medium}`,
                    color: theme.colors.text.primary,
                  }}
                  disabled={isSubmitting}
                  autoFocus
                />
              </motion.div>
            )}
          </motion.div>
        )}
      </div>

      {/* Actions */}
      <div
        className="px-4 py-3 flex items-center justify-end gap-3"
        style={{
          borderTop: `1px solid ${theme.colors.border.subtle}`,
          backgroundColor: theme.colors.bg.tertiary,
        }}
      >
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style={{
            color: theme.colors.text.secondary,
            backgroundColor: 'transparent',
          }}
          disabled={isSubmitting}
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={!canSubmit || isSubmitting}
          className="px-4 py-2 rounded-lg text-sm font-medium transition-all"
          style={{
            backgroundColor: canSubmit
              ? theme.colors.accent.primary
              : theme.colors.bg.tertiary,
            color: canSubmit
              ? theme.colors.bg.primary
              : theme.colors.text.muted,
            opacity: isSubmitting ? 0.7 : 1,
          }}
        >
          {isSubmitting ? 'Submitting...' : 'Continue'}
        </button>
      </div>
    </motion.div>
  );
};

export default SelectionCard;

