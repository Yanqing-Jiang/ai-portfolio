/**
 * Hook: useWorkflowState
 * Purpose: Manages workflow state machine for analytics sessions
 * Called from: useAnalyticsMemoryStream
 * Invokes: State transitions, event handlers
 * Why: Centralizes workflow state management to reduce complexity in the main hook.
 * 
 * Part of Phase 4.1 of the analytics refactor plan - hook decomposition.
 * Target: ~500-800 LOC
 */

import { useCallback, useRef, useState } from 'react';
import { ParsedEvent } from './useEventParser';

// Workflow states
export type WorkflowState = 
  | 'idle'
  | 'connecting'
  | 'session_started'
  | 'classification'
  | 'intent_detection'
  | 'clarification'
  | 'plan_generation'
  | 'sql_execution'
  | 'chart_generation'
  | 'analysis_generation'
  | 'web_search'
  | 'market_data'
  | 'revision'
  | 'finalization'
  | 'completed'
  | 'error';

// Lane states
export type LaneState = 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'reused';

// Lane configuration
export interface LaneConfig {
  id: string;
  name: string;
  requiredFor: ('full_pipeline' | 'stock_only' | 'reuse_sql')[];
  dependencies: string[];
}

// Lane definitions
export const LANE_CONFIGS: LaneConfig[] = [
  { id: 'web', name: 'Web Research', requiredFor: ['full_pipeline'], dependencies: [] },
  { id: 'market', name: 'Market Data', requiredFor: ['full_pipeline', 'stock_only'], dependencies: [] },
  { id: 'sql', name: 'SQL Query', requiredFor: ['full_pipeline', 'stock_only'], dependencies: [] },
  { id: 'chart', name: 'Chart Generation', requiredFor: ['full_pipeline', 'stock_only'], dependencies: ['sql'] },
  { id: 'analysis', name: 'Analysis', requiredFor: ['full_pipeline', 'stock_only', 'reuse_sql'], dependencies: ['sql', 'chart'] },
];

// Workflow metrics
export interface WorkflowMetrics {
  startTime: number;
  endTime?: number;
  totalLatencyMs?: number;
  laneLatencies: Record<string, number>;
  toolCounts: Record<string, number>;
  cacheHits: number;
  retries: number;
}

// Workflow state machine state
export interface WorkflowStateData {
  state: WorkflowState;
  previousState: WorkflowState;
  laneStates: Record<string, LaneState>;
  activeLane?: string;
  followUpRoute?: string;
  revisionLanes?: string[];
  metrics: WorkflowMetrics;
  error?: string;
}

// Initial state
const INITIAL_STATE: WorkflowStateData = {
  state: 'idle',
  previousState: 'idle',
  laneStates: {
    web: 'pending',
    market: 'pending',
    sql: 'pending',
    chart: 'pending',
    analysis: 'pending',
  },
  metrics: {
    startTime: 0,
    laneLatencies: {},
    toolCounts: {},
    cacheHits: 0,
    retries: 0,
  },
};

// Event to state mapping
const EVENT_STATE_MAP: Record<string, WorkflowState> = {
  'session_started': 'session_started',
  'classification_complete': 'classification',
  'intent_detected': 'intent_detection',
  'clarification_complete': 'clarification',
  'clarification_needed': 'clarification',
  'plan_ready': 'plan_generation',
  'sql_generated': 'sql_execution',
  'sql_ready': 'sql_execution',
  'data_retrieved': 'sql_execution',
  'chart_ready': 'chart_generation',
  'analysis_complete': 'analysis_generation',
  'analysis_ready': 'analysis_generation',
  'web_ready': 'web_search',
  'stock_ready': 'market_data',
  'market_ready': 'market_data',
  'revision_started': 'revision',
  'revision_complete': 'revision',
  'workflow_complete': 'completed',
  'workflow_error': 'error',
  'error': 'error',
};

// Event to lane mapping
const EVENT_LANE_MAP: Record<string, string> = {
  'web_ready': 'web',
  'web_search_complete': 'web',
  'stock_ready': 'market',
  'market_ready': 'market',
  'sql_generated': 'sql',
  'sql_ready': 'sql',
  'data_retrieved': 'sql',
  'chart_ready': 'chart',
  'analysis_complete': 'analysis',
  'analysis_ready': 'analysis',
};

/**
 * Hook for managing workflow state machine.
 */
export const useWorkflowState = () => {
  const [workflow, setWorkflow] = useState<WorkflowStateData>(INITIAL_STATE);
  const workflowRef = useRef<WorkflowStateData>(INITIAL_STATE);
  
  // Lane start times for latency calculation
  const laneStartTimes = useRef<Record<string, number>>({});
  
  /**
   * Update workflow state atomically.
   */
  const updateWorkflow = useCallback((
    updater: (prev: WorkflowStateData) => WorkflowStateData
  ) => {
    setWorkflow((prev) => {
      const next = updater(prev);
      workflowRef.current = next;
      return next;
    });
  }, []);
  
  /**
   * Transition to a new workflow state.
   */
  const transitionTo = useCallback((newState: WorkflowState, extra?: Partial<WorkflowStateData>) => {
    updateWorkflow((prev) => ({
      ...prev,
      previousState: prev.state,
      state: newState,
      ...extra,
    }));
  }, [updateWorkflow]);
  
  /**
   * Update lane state.
   */
  const updateLaneState = useCallback((lane: string, state: LaneState) => {
    const now = Date.now();
    
    updateWorkflow((prev) => {
      const next = { ...prev };
      next.laneStates = { ...prev.laneStates, [lane]: state };
      
      // Track lane start time
      if (state === 'running') {
        laneStartTimes.current[lane] = now;
        next.activeLane = lane;
      }
      
      // Calculate lane latency on completion
      if (state === 'completed' || state === 'failed' || state === 'reused') {
        const startTime = laneStartTimes.current[lane];
        if (startTime) {
          next.metrics = {
            ...prev.metrics,
            laneLatencies: {
              ...prev.metrics.laneLatencies,
              [lane]: now - startTime,
            },
          };
        }
        if (next.activeLane === lane) {
          next.activeLane = undefined;
        }
      }
      
      return next;
    });
  }, [updateWorkflow]);
  
  /**
   * Process a parsed event and update workflow state.
   */
  const processWorkflowEvent = useCallback((event: ParsedEvent): boolean => {
    const { eventType, eventData, receipt } = event;
    
    // Map event to workflow state
    const newState = EVENT_STATE_MAP[eventType];
    if (newState) {
      transitionTo(newState);
    }
    
    // Map event to lane state
    const lane = EVENT_LANE_MAP[eventType];
    if (lane) {
      const laneState: LaneState = receipt?.from_cache 
        ? 'reused' 
        : receipt?.status === 'failed' 
          ? 'failed' 
          : 'completed';
      updateLaneState(lane, laneState);
    }
    
    // Handle special events
    switch (eventType) {
      case 'session_started': {
        updateWorkflow((prev) => ({
          ...prev,
          metrics: {
            ...prev.metrics,
            startTime: Date.now(),
          },
        }));
        return true;
      }
      
      case 'progress': {
        const stage = String(eventData.stage ?? '');
        const laneName = stage.toLowerCase();
        if (LANE_CONFIGS.some((l) => l.id === laneName)) {
          const current = workflowRef.current.laneStates[laneName];
          if (current === 'pending') {
            updateLaneState(laneName, 'running');
          }
        }
        return true;
      }
      
      case 'workflow_complete': {
        updateWorkflow((prev) => ({
          ...prev,
          state: 'completed',
          previousState: prev.state,
          metrics: {
            ...prev.metrics,
            endTime: Date.now(),
            totalLatencyMs: Date.now() - prev.metrics.startTime,
          },
        }));
        return true;
      }
      
      case 'workflow_error':
      case 'error': {
        const errorMsg = String(eventData.error ?? eventData.message ?? 'Unknown error');
        updateWorkflow((prev) => ({
          ...prev,
          state: 'error',
          previousState: prev.state,
          error: errorMsg,
          metrics: {
            ...prev.metrics,
            endTime: Date.now(),
            totalLatencyMs: Date.now() - prev.metrics.startTime,
          },
        }));
        return true;
      }
      
      case 'revision_started': {
        const lanes = event.revisionLanes;
        if (lanes && lanes.length > 0) {
          updateWorkflow((prev) => ({
            ...prev,
            state: 'revision',
            revisionLanes: lanes,
          }));
          // Mark revision lanes as running
          for (const l of lanes) {
            if (LANE_CONFIGS.some((c) => c.id === l)) {
              updateLaneState(l, 'running');
            }
          }
        }
        return true;
      }
      
      default:
        return newState !== undefined || lane !== undefined;
    }
  }, [transitionTo, updateLaneState, updateWorkflow]);
  
  /**
   * Start a new workflow.
   */
  const startWorkflow = useCallback((followUpRoute?: string) => {
    laneStartTimes.current = {};
    setWorkflow({
      ...INITIAL_STATE,
      state: 'connecting',
      previousState: 'idle',
      followUpRoute,
      metrics: {
        ...INITIAL_STATE.metrics,
        startTime: Date.now(),
      },
    });
    workflowRef.current = {
      ...INITIAL_STATE,
      state: 'connecting',
      previousState: 'idle',
      followUpRoute,
      metrics: {
        ...INITIAL_STATE.metrics,
        startTime: Date.now(),
      },
    };
  }, []);
  
  /**
   * Reset workflow to idle.
   */
  const reset = useCallback(() => {
    laneStartTimes.current = {};
    setWorkflow(INITIAL_STATE);
    workflowRef.current = INITIAL_STATE;
  }, []);
  
  /**
   * Increment tool count for a lane.
   */
  const incrementToolCount = useCallback((lane: string) => {
    updateWorkflow((prev) => ({
      ...prev,
      metrics: {
        ...prev.metrics,
        toolCounts: {
          ...prev.metrics.toolCounts,
          [lane]: (prev.metrics.toolCounts[lane] ?? 0) + 1,
        },
      },
    }));
  }, [updateWorkflow]);
  
  /**
   * Increment cache hit count.
   */
  const incrementCacheHits = useCallback(() => {
    updateWorkflow((prev) => ({
      ...prev,
      metrics: {
        ...prev.metrics,
        cacheHits: prev.metrics.cacheHits + 1,
      },
    }));
  }, [updateWorkflow]);
  
  /**
   * Increment retry count.
   */
  const incrementRetries = useCallback(() => {
    updateWorkflow((prev) => ({
      ...prev,
      metrics: {
        ...prev.metrics,
        retries: prev.metrics.retries + 1,
      },
    }));
  }, [updateWorkflow]);
  
  /**
   * Get lanes that are required for current follow-up route.
   */
  const getRequiredLanes = useCallback((): string[] => {
    const route = workflowRef.current.followUpRoute ?? 'full_pipeline';
    return LANE_CONFIGS
      .filter((l) => l.requiredFor.includes(route as any))
      .map((l) => l.id);
  }, []);
  
  /**
   * Get lanes that are pending.
   */
  const getPendingLanes = useCallback((): string[] => {
    return Object.entries(workflowRef.current.laneStates)
      .filter(([, state]) => state === 'pending' || state === 'running')
      .map(([lane]) => lane);
  }, []);
  
  /**
   * Check if all required lanes are complete.
   */
  const isComplete = useCallback((): boolean => {
    const required = getRequiredLanes();
    const states = workflowRef.current.laneStates;
    return required.every((lane) => 
      states[lane] === 'completed' || 
      states[lane] === 'reused' || 
      states[lane] === 'skipped'
    );
  }, [getRequiredLanes]);
  
  /**
   * Check if workflow is in progress.
   */
  const isInProgress = useCallback((): boolean => {
    const state = workflowRef.current.state;
    return state !== 'idle' && state !== 'completed' && state !== 'error';
  }, []);
  
  return {
    workflow,
    workflowRef,
    processWorkflowEvent,
    startWorkflow,
    reset,
    transitionTo,
    updateLaneState,
    incrementToolCount,
    incrementCacheHits,
    incrementRetries,
    getRequiredLanes,
    getPendingLanes,
    isComplete,
    isInProgress,
    // Constants
    LANE_CONFIGS,
  };
};

export default useWorkflowState;

