/**
 * Hook: usePlannerEvents
 * Purpose: Handles deterministic planner events (DIRECT mode only)
 * Called from: useAnalyticsMemoryStream
 * Invokes: State management for planner steps
 * Why: Centralizes planner event handling, separate from agent events.
 * 
 * Part of Phase 4.1 of the analytics refactor plan - hook decomposition.
 * Target: ~500-800 LOC
 * 
 * Per Phase 4.2: Hide planner nodes in agent modes on WorkflowCanvas.
 */

import { useCallback, useRef, useState } from 'react';
import { ParsedEvent, ReceiptData } from './useEventParser';

// Planner step states
export type PlannerStepState = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

// Planner step data
export interface PlannerStep {
  id: string;
  name: string;
  state: PlannerStepState;
  startTime?: number;
  endTime?: number;
  latencyMs?: number;
  receipt?: ReceiptData;
  output?: unknown;
  error?: string;
}

// Planner pipeline state
export interface PlannerPipelineState {
  isActive: boolean;
  flowMode: 'planner-executor' | 'single-agent' | 'multi-agent';
  currentStep?: string;
  steps: Record<string, PlannerStep>;
  startTime?: number;
  endTime?: number;
  totalLatencyMs?: number;
}

// Default planner steps (DIRECT mode pipeline)
export const DEFAULT_PLANNER_STEPS: Record<string, { name: string; order: number }> = {
  classification: { name: 'Classification', order: 1 },
  intent_detection: { name: 'Intent Detection', order: 2 },
  clarification: { name: 'Clarification', order: 3 },
  plan_generation: { name: 'Plan Generation', order: 4 },
  sql_compilation: { name: 'SQL Compilation', order: 5 },
  sql_execution: { name: 'SQL Execution', order: 6 },
  sql_validation: { name: 'SQL Validation', order: 7 },
  chart_generation: { name: 'Chart Generation', order: 8 },
  analysis_generation: { name: 'Analysis Generation', order: 9 },
  finalization: { name: 'Finalization', order: 10 },
};

// Event to step mapping
const EVENT_STEP_MAP: Record<string, { step: string; state: PlannerStepState }> = {
  // Classification
  'classification_complete': { step: 'classification', state: 'completed' },
  'classification_failed': { step: 'classification', state: 'failed' },
  
  // Intent
  'intent_detected': { step: 'intent_detection', state: 'completed' },
  'intent_failed': { step: 'intent_detection', state: 'failed' },
  
  // Clarification
  'clarification_needed': { step: 'clarification', state: 'running' },
  'clarification_complete': { step: 'clarification', state: 'completed' },
  'clarification_skipped': { step: 'clarification', state: 'skipped' },
  
  // Plan
  'plan_ready': { step: 'plan_generation', state: 'completed' },
  'plan_failed': { step: 'plan_generation', state: 'failed' },
  
  // SQL
  'sql_compiled': { step: 'sql_compilation', state: 'completed' },
  'sql_generated': { step: 'sql_execution', state: 'running' },
  'sql_validated': { step: 'sql_validation', state: 'completed' },
  'sql_ready': { step: 'sql_execution', state: 'completed' },
  'sql_failed': { step: 'sql_execution', state: 'failed' },
  'data_retrieved': { step: 'sql_execution', state: 'completed' },
  
  // Chart
  'chart_ready': { step: 'chart_generation', state: 'completed' },
  'chart_failed': { step: 'chart_generation', state: 'failed' },
  
  // Analysis
  'analysis_complete': { step: 'analysis_generation', state: 'completed' },
  'analysis_ready': { step: 'analysis_generation', state: 'completed' },
  'analysis_failed': { step: 'analysis_generation', state: 'failed' },
  
  // Finalization
  'workflow_complete': { step: 'finalization', state: 'completed' },
  'workflow_error': { step: 'finalization', state: 'failed' },
};

// Initial state factory
const createInitialState = (
  flowMode: 'planner-executor' | 'single-agent' | 'multi-agent'
): PlannerPipelineState => {
  const steps: Record<string, PlannerStep> = {};
  for (const [id, config] of Object.entries(DEFAULT_PLANNER_STEPS)) {
    steps[id] = {
      id,
      name: config.name,
      state: 'pending',
    };
  }
  
  return {
    isActive: flowMode === 'planner-executor',
    flowMode,
    steps,
  };
};

/**
 * Hook for managing planner events in DIRECT mode.
 * In agent modes, this provides minimal tracking but hides UI nodes.
 */
export const usePlannerEvents = (
  flowMode: 'planner-executor' | 'single-agent' | 'multi-agent' = 'planner-executor'
) => {
  const [pipeline, setPipeline] = useState<PlannerPipelineState>(() => 
    createInitialState(flowMode)
  );
  const pipelineRef = useRef<PlannerPipelineState>(createInitialState(flowMode));
  
  // Step start times for latency calculation
  const stepStartTimes = useRef<Record<string, number>>({});
  
  /**
   * Update pipeline state atomically.
   */
  const updatePipeline = useCallback((
    updater: (prev: PlannerPipelineState) => PlannerPipelineState
  ) => {
    setPipeline((prev) => {
      const next = updater(prev);
      pipelineRef.current = next;
      return next;
    });
  }, []);
  
  /**
   * Update a specific step's state.
   */
  const updateStepState = useCallback((
    stepId: string,
    state: PlannerStepState,
    extra?: Partial<PlannerStep>
  ) => {
    const now = Date.now();
    
    updatePipeline((prev) => {
      const step = prev.steps[stepId];
      if (!step) return prev;
      
      // Calculate latency if completing
      let latencyMs = extra?.latencyMs;
      if (state === 'completed' || state === 'failed') {
        const startTime = stepStartTimes.current[stepId] ?? step.startTime;
        if (startTime && !latencyMs) {
          latencyMs = now - startTime;
        }
      }
      
      // Track start time
      if (state === 'running' && !stepStartTimes.current[stepId]) {
        stepStartTimes.current[stepId] = now;
      }
      
      return {
        ...prev,
        currentStep: state === 'running' ? stepId : prev.currentStep,
        steps: {
          ...prev.steps,
          [stepId]: {
            ...step,
            state,
            startTime: state === 'running' ? now : step.startTime,
            endTime: (state === 'completed' || state === 'failed') ? now : step.endTime,
            latencyMs,
            ...extra,
          },
        },
      };
    });
  }, [updatePipeline]);
  
  /**
   * Process a parsed event and update planner state.
   * Returns true if the event was a planner event.
   */
  const processPlannerEvent = useCallback((event: ParsedEvent): boolean => {
    const mapping = EVENT_STEP_MAP[event.eventType];
    if (!mapping) {
      return false;
    }
    
    const { step, state } = mapping;
    const receipt = event.receipt;
    
    // If step is about to complete, set running first if not already
    const currentState = pipelineRef.current.steps[step]?.state;
    if ((state === 'completed' || state === 'failed') && currentState === 'pending') {
      updateStepState(step, 'running');
    }
    
    updateStepState(step, state, {
      receipt,
      output: event.eventData,
      error: state === 'failed' ? String(event.eventData.error ?? 'Unknown error') : undefined,
    });
    
    return true;
  }, [updateStepState]);
  
  /**
   * Handle progress events (intermediate updates).
   */
  const handleProgressEvent = useCallback((event: ParsedEvent) => {
    const stage = String(event.eventData.stage ?? '');
    const stepId = stage.toLowerCase().replace(/_/g, '_');
    
    if (pipelineRef.current.steps[stepId]) {
      const currentState = pipelineRef.current.steps[stepId].state;
      if (currentState === 'pending') {
        updateStepState(stepId, 'running');
      }
    }
  }, [updateStepState]);
  
  /**
   * Start the pipeline for a new query.
   */
  const startPipeline = useCallback(() => {
    stepStartTimes.current = {};
    const newState = createInitialState(pipelineRef.current.flowMode);
    newState.startTime = Date.now();
    newState.isActive = pipelineRef.current.flowMode === 'planner-executor';
    setPipeline(newState);
    pipelineRef.current = newState;
  }, []);
  
  /**
   * Complete the pipeline.
   */
  const completePipeline = useCallback((success: boolean) => {
    updatePipeline((prev) => ({
      ...prev,
      endTime: Date.now(),
      totalLatencyMs: prev.startTime ? Date.now() - prev.startTime : undefined,
      currentStep: undefined,
    }));
    
    // Mark finalization step
    updateStepState('finalization', success ? 'completed' : 'failed');
  }, [updatePipeline, updateStepState]);
  
  /**
   * Reset the pipeline.
   */
  const reset = useCallback(() => {
    stepStartTimes.current = {};
    const newState = createInitialState(pipelineRef.current.flowMode);
    setPipeline(newState);
    pipelineRef.current = newState;
  }, []);
  
  /**
   * Set flow mode (affects isActive).
   */
  const setFlowMode = useCallback((
    mode: 'planner-executor' | 'single-agent' | 'multi-agent'
  ) => {
    updatePipeline((prev) => ({
      ...prev,
      flowMode: mode,
      isActive: mode === 'planner-executor',
    }));
  }, [updatePipeline]);
  
  /**
   * Get steps in order for rendering.
   */
  const getOrderedSteps = useCallback((): PlannerStep[] => {
    return Object.entries(DEFAULT_PLANNER_STEPS)
      .sort(([, a], [, b]) => a.order - b.order)
      .map(([id]) => pipelineRef.current.steps[id])
      .filter((step): step is PlannerStep => step !== undefined);
  }, []);
  
  /**
   * Get completed steps count.
   */
  const getCompletedCount = useCallback((): number => {
    return Object.values(pipelineRef.current.steps)
      .filter((s) => s.state === 'completed' || s.state === 'skipped')
      .length;
  }, []);
  
  /**
   * Get total steps count.
   */
  const getTotalCount = useCallback((): number => {
    return Object.keys(pipelineRef.current.steps).length;
  }, []);
  
  /**
   * Get progress percentage.
   */
  const getProgress = useCallback((): number => {
    const total = getTotalCount();
    if (total === 0) return 0;
    return (getCompletedCount() / total) * 100;
  }, [getCompletedCount, getTotalCount]);
  
  /**
   * Check if a step should be visible based on flow mode.
   * In agent modes, most planner steps should be hidden.
   */
  const shouldShowStep = useCallback((stepId: string): boolean => {
    // In DIRECT mode, show all steps
    if (pipelineRef.current.flowMode === 'planner-executor') {
      return true;
    }
    
    // In agent modes, only show high-level steps
    const visibleInAgentMode = ['finalization'];
    return visibleInAgentMode.includes(stepId);
  }, []);
  
  /**
   * Get visible steps for UI rendering.
   */
  const getVisibleSteps = useCallback((): PlannerStep[] => {
    return getOrderedSteps().filter((step) => shouldShowStep(step.id));
  }, [getOrderedSteps, shouldShowStep]);
  
  /**
   * Check if pipeline is in progress.
   */
  const isInProgress = useCallback((): boolean => {
    const current = pipelineRef.current;
    return current.startTime !== undefined && current.endTime === undefined;
  }, []);
  
  return {
    pipeline,
    pipelineRef,
    processPlannerEvent,
    handleProgressEvent,
    startPipeline,
    completePipeline,
    reset,
    setFlowMode,
    updateStepState,
    getOrderedSteps,
    getVisibleSteps,
    getCompletedCount,
    getTotalCount,
    getProgress,
    shouldShowStep,
    isInProgress,
    // Constants
    DEFAULT_PLANNER_STEPS,
  };
};

export default usePlannerEvents;

