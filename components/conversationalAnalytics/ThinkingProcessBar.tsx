/**
 * Function: ThinkingProcessBar — ChatGPT/Claude-style thinking process indicator
 * Called from: ConversationalAnalyticsPage during streaming
 * Purpose: Shows real-time agent thinking steps with expandable details
 * Note: Skill visualization has been moved to ProcessPanel for better UX
 */

import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PlanStep, DebugLog, SkillInfo, AgentInfo, HandoffInfo } from './hooks/useSSEStream';
import { theme } from './styles';

interface ThinkingProcessBarProps {
  steps: PlanStep[];
  currentStepId: string | null;
  isExpanded: boolean;
  onToggle: () => void;
  debugLogs?: DebugLog[];
  error?: string | null;
  errorDetails?: string | null;
  skillInfo?: SkillInfo | null;  // Kept for compatibility but skill UI moved to ProcessPanel
  isStreaming?: boolean;
  activeAgent?: AgentInfo | null;
  handoffs?: HandoffInfo[];
  isPaused?: boolean;
}

/**
 * Function: ThinkingProcessBar — renders thinking/plan steps in a ChatGPT-style collapsible bar.
 * Shows latest step collapsed, all steps when expanded.
 * Skill visualization has been moved to the ProcessPanel component for a more integrated experience.
 */
const ThinkingProcessBar: React.FC<ThinkingProcessBarProps> = ({
  steps,
  currentStepId,
  isExpanded,
  onToggle,
  error = null,
  errorDetails = null,
  isStreaming = false,
  handoffs = [],
  isPaused = false,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stepsContainerRef = useRef<HTMLDivElement>(null);

  // Find current step or latest running step
  const currentStep = steps.find(s => s.id === currentStepId) || steps.find(s => s.status === 'running');
  const latestStep = currentStep || steps[steps.length - 1];
  const completedCount = steps.filter(s => s.status === 'completed').length;
  const hasError = error || steps.some(s => s.status === 'error');
  const isComplete = !isStreaming && steps.length > 0 && steps.every(s => s.status === 'completed');

  // Auto-scroll to current step when expanded
  useEffect(() => {
    if (isExpanded && stepsContainerRef.current && currentStep) {
      const stepElements = stepsContainerRef.current.querySelectorAll('[data-step]');
      const currentIndex = steps.findIndex(s => s.id === currentStep.id);
      if (stepElements[currentIndex]) {
        stepElements[currentIndex].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [currentStep, isExpanded, steps]);

  // Status helpers
  const getStatusIcon = (status: PlanStep['status']) => {
    switch (status) {
      case 'completed': return '✓';
      case 'running': return null; // Will use animated dot
      case 'error': return '✕';
      default: return '○';
    }
  };

  const getStatusColor = (status: PlanStep['status']) => {
    switch (status) {
      case 'completed': return theme.colors.status.success;
      case 'running': return theme.colors.accent.primary;
      case 'error': return theme.colors.status.error;
      default: return theme.colors.text.muted;
    }
  };

  // Don't render if no steps and not streaming
  if (steps.length === 0 && !isStreaming && !error) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="rounded-2xl overflow-hidden mb-4"
      style={{
        backgroundColor: theme.colors.bg.tertiary,
        border: `1px solid ${hasError ? theme.colors.status.error + '40' : theme.colors.border.subtle}`,
        boxShadow: isStreaming ? theme.shadows.glow : theme.shadows.sm,
      }}
    >
      {/* Collapsed Header - Shows Latest Step */}
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between transition-all hover:bg-opacity-80"
        style={{ backgroundColor: 'transparent' }}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* Thinking Animation or Status Icon */}
          <div className="flex items-center gap-1 shrink-0">
            {isStreaming && !hasError ? (
              // Animated thinking dots
              <div className="flex items-center gap-1">
                {[0, 1, 2].map(i => (
                  <motion.div
                    key={i}
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: theme.colors.accent.primary }}
                    animate={{
                      y: [0, -5, 0],
                      opacity: [0.4, 1, 0.4],
                    }}
                    transition={{
                      duration: 0.6,
                      repeat: Infinity,
                      delay: i * 0.15,
                      ease: 'easeInOut',
                    }}
                  />
                ))}
              </div>
            ) : hasError ? (
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center text-sm"
                style={{
                  backgroundColor: theme.colors.status.error + '20',
                  color: theme.colors.status.error,
                }}
              >
                ✕
              </div>
            ) : isComplete ? (
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center text-sm"
                style={{
                  backgroundColor: theme.colors.status.success + '20',
                  color: theme.colors.status.success,
                }}
              >
                ✓
              </div>
            ) : (
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center"
                style={{
                  backgroundColor: theme.colors.bg.elevated,
                  color: theme.colors.text.muted,
                }}
              >
                ○
              </div>
            )}
          </div>

          {/* Latest Step Label */}
          <div
            ref={scrollRef}
            className="flex-1 min-w-0 overflow-hidden"
          >
            <span
              className="text-sm font-medium truncate block"
              style={{
                color: hasError
                  ? theme.colors.status.error
                  : isStreaming
                    ? theme.colors.text.primary
                    : theme.colors.status.success,
              }}
            >
              {hasError
                ? error || 'Error occurred'
                : latestStep?.label || (isStreaming ? 'Thinking...' : 'Ready')
              }
            </span>
            {latestStep?.summary && !hasError && (
              <span
                className="text-xs truncate block mt-0.5"
                style={{ color: theme.colors.text.muted }}
              >
                {latestStep.summary}
              </span>
            )}
          </div>

          {/* Step Counter */}
          {steps.length > 0 && (
            <span
              className="text-xs px-2 py-1 rounded-full shrink-0"
              style={{
                backgroundColor: theme.colors.bg.elevated,
                color: theme.colors.text.muted,
              }}
            >
              {completedCount}/{steps.length}
            </span>
          )}

          {isPaused && (
            <span
              className="text-[11px] px-2 py-1 rounded-full shrink-0"
              style={{
                backgroundColor: theme.colors.bg.elevated,
                color: theme.colors.text.primary,
                border: `1px solid ${theme.colors.border.subtle}`,
              }}
            >
              Paused
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0 ml-3">
          {handoffs.length > 0 && (
            <span
              className="text-xs px-2 py-1 rounded-full"
              style={{
                backgroundColor: theme.colors.bg.elevated,
                color: theme.colors.text.muted,
              }}
            >
              {handoffs.length} handoff{handoffs.length > 1 ? 's' : ''}
            </span>
          )}

          {/* Expand/Collapse Arrow */}
          <motion.span
            className="text-sm"
            style={{ color: theme.colors.text.muted }}
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            ▼
          </motion.span>
        </div>
      </button>

      {/* Expanded Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            style={{ overflow: 'hidden' }}
          >
            <div
              className="px-4 pb-4 pt-2 space-y-2"
              style={{ borderTop: `1px solid ${theme.colors.border.subtle}` }}
            >
              {/* All Steps */}
              {steps.length > 0 && (
                <div ref={stepsContainerRef} className="space-y-2">
                  {steps.map((step, idx) => (
                    <motion.div
                      key={step.id}
                      data-step={step.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.03 }}
                      className="flex items-start gap-3 py-2 px-3 rounded-lg transition-colors"
                      style={{
                        backgroundColor: step.status === 'running'
                          ? theme.colors.accent.muted
                          : 'transparent',
                      }}
                    >
                      {/* Step Status */}
                      <div className="w-6 flex justify-center pt-0.5 shrink-0">
                        {step.status === 'running' ? (
                          <motion.div
                            className="w-2.5 h-2.5 rounded-full"
                            style={{ backgroundColor: theme.colors.accent.primary }}
                            animate={{ scale: [1, 1.3, 1], opacity: [1, 0.7, 1] }}
                            transition={{ duration: 0.8, repeat: Infinity }}
                          />
                        ) : (
                          <span
                            className="text-sm"
                            style={{ color: getStatusColor(step.status) }}
                          >
                            {getStatusIcon(step.status)}
                          </span>
                        )}
                      </div>

                      {/* Step Content */}
                      <div className="flex-1 min-w-0">
                        <span
                          className="text-sm font-medium block"
                          style={{
                            color: step.status === 'running'
                              ? theme.colors.text.primary
                              : step.status === 'completed'
                                ? theme.colors.text.secondary
                                : step.status === 'error'
                                  ? theme.colors.status.error
                                  : theme.colors.text.muted,
                          }}
                        >
                          {step.label}
                        </span>
                        {step.summary && (
                          <span
                            className="text-xs block mt-0.5"
                            style={{ color: theme.colors.text.muted }}
                          >
                            {step.summary}
                          </span>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}

              {/* Error Details */}
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-4 rounded-xl"
                  style={{
                    backgroundColor: theme.colors.status.error + '15',
                    border: `1px solid ${theme.colors.status.error}40`,
                  }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span style={{ color: theme.colors.status.error }}>⚠️</span>
                    <span
                      className="text-sm font-medium"
                      style={{ color: theme.colors.status.error }}
                    >
                      Error
                    </span>
                  </div>
                  <p
                    className="text-sm"
                    style={{ color: theme.colors.text.secondary }}
                  >
                    {error}
                  </p>
                  {errorDetails && (
                    <details className="mt-3">
                      <summary
                        className="text-xs cursor-pointer hover:underline"
                        style={{ color: theme.colors.status.error }}
                      >
                        Show stack trace
                      </summary>
                      <pre
                        className="mt-2 p-3 rounded-lg text-xs overflow-x-auto"
                        style={{
                          backgroundColor: theme.colors.bg.primary,
                          color: theme.colors.text.muted,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {errorDetails}
                      </pre>
                    </details>
                  )}
                </motion.div>
              )}

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default ThinkingProcessBar;
