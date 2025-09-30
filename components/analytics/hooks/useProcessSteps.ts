import { useState } from 'react';
import { ProcessStep } from '../types';
import { STEP_NAME, STEP_ORDER } from '../../../constants/analytics';

interface StepConfig {
  stepNames?: Record<string, string>;
  stepOrder?: string[];
}

const getOrderIndex = (order: string[], id: string) => {
  const idx = order.indexOf(id);
  return idx === -1 ? Number.MAX_SAFE_INTEGER : idx;
};

const mergeThinking = (current: string[], incoming: string[]) => {
  if (!incoming.length) {
    return current;
  }

  const cleaned = incoming.filter(Boolean);
  if (!cleaned.length) {
    return current;
  }

  const next = [...current];
  cleaned.forEach((entry) => {
    if (next[next.length - 1] !== entry) {
      next.push(entry);
    }
  });
  return next;
};

export const useProcessSteps = (config?: StepConfig) => {
  const [processSteps, setProcessSteps] = useState<ProcessStep[]>([]);

  const stepNames = config?.stepNames || STEP_NAME;
  const stepOrder = config?.stepOrder || STEP_ORDER;

  const updateStepStatus = (
    stepId: string,
    status: ProcessStep['status'],
    thinking: string[] = [],
    details?: any,
    elapsed_ms?: number,
    timestamp?: string,
    sequence?: number,
    parallelGroup?: string,
  ) => {
    setProcessSteps((prev) => {
      const existing = prev.find((s) => s.id === stepId);

      if (existing) {
        const mergedDetails = details
          ? { ...(existing.details ?? {}), ...details }
          : existing.details;

        return prev.map((step) => {
          if (step.id !== stepId) {
            return step;
          }

          return {
            ...step,
            status,
            thinking: mergeThinking(step.thinking, thinking),
            details: mergedDetails,
            elapsed_ms: elapsed_ms ?? step.elapsed_ms,
            timestamp: timestamp ?? step.timestamp,
            sequence: sequence ?? step.sequence,
            parallelGroup: parallelGroup ?? step.parallelGroup,
          };
        });
      }

      const next: ProcessStep[] = [
        ...prev,
        {
          id: stepId,
          name: stepNames[stepId] || stepId,
          status,
          thinking: thinking.filter(Boolean),
          details,
          elapsed_ms,
          timestamp,
          sequence,
          parallelGroup,
        },
      ];

      next.sort((a, b) => {
        const orderDiff = getOrderIndex(stepOrder, a.id) - getOrderIndex(stepOrder, b.id);
        if (orderDiff !== 0) {
          return orderDiff;
        }
        const seqA = a.sequence ?? Number.MAX_SAFE_INTEGER;
        const seqB = b.sequence ?? Number.MAX_SAFE_INTEGER;
        if (seqA !== seqB) {
          return seqA - seqB;
        }
        return (a.timestamp || '').localeCompare(b.timestamp || '');
      });

      return next;
    });
  };

  const resetSteps = () => {
    setProcessSteps([]);
  };

  const stopInProgressSteps = () => {
    setProcessSteps((prev) =>
      prev.map((step) => (step.status === 'in_progress' ? { ...step, status: 'stopped' } : step))
    );
  };

  return {
    processSteps,
    updateStepStatus,
    resetSteps,
    stopInProgressSteps,
  };
};
