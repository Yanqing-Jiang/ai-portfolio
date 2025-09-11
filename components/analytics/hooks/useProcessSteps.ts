import { useState } from 'react';
import { ProcessStep } from '../types';
import { STEP_NAME, STEP_ORDER } from '../../../constants/analytics';

export const useProcessSteps = () => {
  const [processSteps, setProcessSteps] = useState<ProcessStep[]>([]);

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
          name: STEP_NAME[stepId] || stepId,
          status,
          thinking,
          details,
          elapsed_ms,
          timestamp,
        },
      ];
      next.sort((a, b) => STEP_ORDER.indexOf(a.id) - STEP_ORDER.indexOf(b.id));
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