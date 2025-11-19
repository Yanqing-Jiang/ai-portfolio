import { useState } from 'react';
import { FlowMode, ProcessStep } from '../types';
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

const STATUS_PRIORITY: Record<ProcessStep['status'], number> = {
  pending: 1,
  in_progress: 2,
  stopped: 3,
  completed: 4,
  error: 5,
};

const shouldUpgradeStatus = (current: ProcessStep['status'], incoming: ProcessStep['status']) => {
  if (!incoming) {
    return false;
  }
  if (!current) {
    return true;
  }
  const incomingRank = STATUS_PRIORITY[incoming] ?? 0;
  const currentRank = STATUS_PRIORITY[current] ?? 0;
  if (incomingRank > currentRank) {
    return true;
  }
  if (incomingRank < currentRank) {
    return false;
  }
  return incoming !== current;
};

const formatStepId = (id: string): string =>
  id
    .split(/[_-]/g)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');

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
    scheduleStage?: string,
    flowMode?: FlowMode,
    extras?: {
      lane?: string;
      reused?: boolean;
      finalAnswerOnly?: boolean;
      missingComponents?: string[];
      followUpRoute?: string;
      analysisAvailable?: boolean;
      toolCallId?: string;
      specialistRole?: string;
      specialistLabel?: string;
      guardrail?: Record<string, any>;
      retryCount?: number;
      cacheAgeSeconds?: number;
      cacheSource?: string;
      schemaVersion?: string;
      fastPathLatencyMs?: number;
      displayName?: string;
      replaceDetails?: boolean;
    },
  ) => {
    setProcessSteps((prev) => {
      const existing = prev.find((s) => s.id === stepId);

      if (existing) {
        const mergedDetails = extras?.replaceDetails
          ? details
          : details
            ? { ...(existing.details ?? {}), ...details }
            : existing.details;

        return prev.map((step) => {
          if (step.id !== stepId) {
            return step;
          }

          const nextStatus = shouldUpgradeStatus(step.status, status) ? status : step.status;

          const updated: ProcessStep = {
            ...step,
            status: nextStatus,
            thinking: mergeThinking(step.thinking, thinking),
            details: mergedDetails,
            elapsed_ms: elapsed_ms ?? step.elapsed_ms,
            timestamp: timestamp ?? step.timestamp,
            sequence: sequence ?? step.sequence,
            parallelGroup: parallelGroup ?? step.parallelGroup,
            scheduleStage: scheduleStage ?? step.scheduleStage,
            flowMode: flowMode ?? step.flowMode,
          };

          if (extras) {
            if (extras.displayName) {
              updated.name = extras.displayName;
            }
            if (extras.replaceDetails) {
              updated.details = details;
            }
            if (extras.lane !== undefined) {
              updated.lane = extras.lane;
            }
            if (extras.reused !== undefined) {
              updated.reused = extras.reused;
            }
            if (extras.finalAnswerOnly !== undefined) {
              updated.finalAnswerOnly = extras.finalAnswerOnly;
            }
            if (extras.missingComponents !== undefined) {
              updated.missingComponents = extras.missingComponents;
            }
            if (extras.followUpRoute !== undefined) {
              updated.followUpRoute = extras.followUpRoute;
            }
            if (extras.analysisAvailable !== undefined) {
              updated.analysisAvailable = extras.analysisAvailable;
            }
            if (extras.toolCallId !== undefined) {
              updated.toolCallId = extras.toolCallId;
            }
            if (extras.specialistRole !== undefined) {
              updated.specialistRole = extras.specialistRole;
            }
            if (extras.specialistLabel !== undefined) {
              updated.specialistLabel = extras.specialistLabel;
            }
            if (extras.guardrail !== undefined) {
              updated.guardrail = extras.guardrail;
            }
            if (extras.retryCount !== undefined) {
              updated.retryCount = extras.retryCount;
            }
            if (extras.cacheAgeSeconds !== undefined) {
              updated.cacheAgeSeconds = extras.cacheAgeSeconds;
            }
            if (extras.cacheSource !== undefined) {
              updated.cacheSource = extras.cacheSource;
            }
            if (extras.schemaVersion !== undefined) {
              updated.schemaVersion = extras.schemaVersion;
            }
            if (extras.fastPathLatencyMs !== undefined) {
              updated.fastPathLatencyMs = extras.fastPathLatencyMs;
            }
          }

          return updated;
        });
      }

      const next: ProcessStep[] = [
        ...prev,
        {
          id: stepId,
          name: extras?.displayName ?? stepNames[stepId] ?? formatStepId(stepId),
          status,
          thinking: thinking.filter(Boolean),
          details,
          elapsed_ms,
          timestamp,
          sequence,
          parallelGroup,
          scheduleStage,
          flowMode,
          lane: extras?.lane,
          reused: extras?.reused,
          finalAnswerOnly: extras?.finalAnswerOnly,
          missingComponents: extras?.missingComponents,
          followUpRoute: extras?.followUpRoute,
          analysisAvailable: extras?.analysisAvailable,
          toolCallId: extras?.toolCallId,
          specialistRole: extras?.specialistRole,
          specialistLabel: extras?.specialistLabel,
          guardrail: extras?.guardrail,
          retryCount: extras?.retryCount,
          cacheAgeSeconds: extras?.cacheAgeSeconds,
          cacheSource: extras?.cacheSource,
          schemaVersion: extras?.schemaVersion,
          fastPathLatencyMs: extras?.fastPathLatencyMs,
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
