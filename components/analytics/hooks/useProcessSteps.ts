import { useState } from 'react';
import { ProcessStep } from '../types';
import { STEP_NAME, STEP_ORDER } from '../../../constants/analytics';

interface StepConfig {
  stepNames?: Record<string, string>;
  stepOrder?: string[];
}

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
  ) => {
    setProcessSteps((prev) => {
      const existing = prev.find((s) => s.id === stepId);
      if (existing) {
        return prev.map((s) => 
          s.id === stepId 
            ? { 
                ...s, 
                status, 
                thinking: thinking.length ? thinking : s.thinking, 
                details: details ?? s.details, 
                elapsed_ms: elapsed_ms ?? s.elapsed_ms, 
                timestamp: timestamp ?? s.timestamp 
              } 
            : s
        );
      }
      const next: ProcessStep[] = [
        ...prev,
        {
          id: stepId,
          name: stepNames[stepId] || stepId,
          status,
          thinking,
          details,
          elapsed_ms,
          timestamp,
        },
      ];
      next.sort((a, b) => stepOrder.indexOf(a.id) - stepOrder.indexOf(b.id));
      return next;
    });
  };

  const resetSteps = () => {
    setProcessSteps([]);
  };

  const stopInProgressSteps = () => {
    setProcessSteps((prev) => 
      prev.map((s) => (s.status === 'in_progress' ? { ...s, status: 'stopped' } : s))
    );
  };

  return {
    processSteps,
    updateStepStatus,
    resetSteps,
    stopInProgressSteps,
  };
};