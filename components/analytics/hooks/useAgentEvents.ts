/**
 * Hook: useAgentEvents
 * Purpose: Handles agent_turn and agent_tool events from the analytics backend
 * Called from: useAnalyticsMemoryStream
 * Invokes: useEventParser, state management
 * Why: Centralizes agent event handling to reduce complexity in the main hook.
 * 
 * Part of Phase 4.1 of the analytics refactor plan - hook decomposition.
 * Target: ~500-800 LOC
 */

import { useCallback, useRef, useState } from 'react';
import { ParsedEvent, ReceiptData } from './useEventParser';

// Agent turn state
export interface AgentTurn {
  turnId: string;
  agentRole: string;
  startTime: number;
  endTime?: number;
  status: 'running' | 'completed' | 'failed';
  tools: AgentToolCall[];
  thinking?: string;
  output?: string;
}

// Agent tool call state
export interface AgentToolCall {
  callId: string;
  tool: string;
  lane?: string;
  startTime: number;
  endTime?: number;
  status: 'running' | 'completed' | 'failed' | 'reused';
  receipt?: ReceiptData;
  result?: unknown;
  error?: string;
}

// Agent evidence accumulated during a session
export interface AgentEvidence {
  turns: AgentTurn[];
  totalToolCalls: number;
  completedToolCalls: number;
  cachedToolCalls: number;
  failedToolCalls: number;
  hasEvidenceGap: boolean; // True if expected events are missing
  lastUpdate: number;
}

// Initial evidence state
const INITIAL_EVIDENCE: AgentEvidence = {
  turns: [],
  totalToolCalls: 0,
  completedToolCalls: 0,
  cachedToolCalls: 0,
  failedToolCalls: 0,
  hasEvidenceGap: false,
  lastUpdate: 0,
};

/**
 * Hook for managing agent events (turns and tool calls).
 * Tracks agent activity and accumulates evidence for UI rendering.
 */
export const useAgentEvents = () => {
  const [evidence, setEvidence] = useState<AgentEvidence>(INITIAL_EVIDENCE);
  const evidenceRef = useRef<AgentEvidence>(INITIAL_EVIDENCE);
  
  // Active turns by ID
  const activeTurns = useRef<Map<string, AgentTurn>>(new Map());
  
  // Active tool calls by ID
  const activeToolCalls = useRef<Map<string, AgentToolCall>>(new Map());
  
  /**
   * Update evidence state and ref atomically.
   */
  const updateEvidence = useCallback((
    updater: (prev: AgentEvidence) => AgentEvidence
  ) => {
    setEvidence((prev) => {
      const next = updater(prev);
      evidenceRef.current = next;
      return next;
    });
  }, []);
  
  /**
   * Handle agent_turn_start event.
   */
  const handleTurnStart = useCallback((event: ParsedEvent) => {
    const data = event.eventData;
    const turnId = String(data.turn_id ?? data.id ?? `turn-${Date.now()}`);
    const agentRole = String(data.agent_role ?? data.role ?? 'supervisor');
    
    const turn: AgentTurn = {
      turnId,
      agentRole,
      startTime: event.timestamp,
      status: 'running',
      tools: [],
    };
    
    activeTurns.current.set(turnId, turn);
    
    updateEvidence((prev) => ({
      ...prev,
      turns: [...prev.turns, turn],
      lastUpdate: Date.now(),
    }));
    
    return turn;
  }, [updateEvidence]);
  
  /**
   * Handle agent_turn_end event.
   */
  const handleTurnEnd = useCallback((event: ParsedEvent) => {
    const data = event.eventData;
    const turnId = String(data.turn_id ?? data.id ?? '');
    const status = String(data.status ?? 'completed');
    const output = typeof data.output === 'string' ? data.output : undefined;
    
    const turn = activeTurns.current.get(turnId);
    if (turn) {
      turn.endTime = event.timestamp;
      turn.status = status === 'failed' ? 'failed' : 'completed';
      turn.output = output;
      activeTurns.current.delete(turnId);
      
      updateEvidence((prev) => ({
        ...prev,
        turns: prev.turns.map((t) => (t.turnId === turnId ? turn : t)),
        lastUpdate: Date.now(),
      }));
    }
    
    return turn;
  }, [updateEvidence]);
  
  /**
   * Handle agent_tool_start event.
   */
  const handleToolStart = useCallback((event: ParsedEvent) => {
    const data = event.eventData;
    const callId = String(data.call_id ?? data.id ?? `tool-${Date.now()}`);
    const tool = String(data.tool ?? data.tool_name ?? 'unknown');
    const lane = typeof data.lane === 'string' ? data.lane : undefined;
    const turnId = String(data.turn_id ?? '');
    
    const toolCall: AgentToolCall = {
      callId,
      tool,
      lane,
      startTime: event.timestamp,
      status: 'running',
    };
    
    activeToolCalls.current.set(callId, toolCall);
    
    // Associate with turn if available
    const turn = activeTurns.current.get(turnId);
    if (turn) {
      turn.tools.push(toolCall);
    }
    
    updateEvidence((prev) => ({
      ...prev,
      totalToolCalls: prev.totalToolCalls + 1,
      lastUpdate: Date.now(),
    }));
    
    return toolCall;
  }, [updateEvidence]);
  
  /**
   * Handle agent_tool_end event.
   */
  const handleToolEnd = useCallback((event: ParsedEvent) => {
    const data = event.eventData;
    const callId = String(data.call_id ?? data.id ?? '');
    const status = String(data.status ?? 'completed');
    const result = data.result;
    const error = typeof data.error === 'string' ? data.error : undefined;
    
    const toolCall = activeToolCalls.current.get(callId);
    if (toolCall) {
      toolCall.endTime = event.timestamp;
      toolCall.status = status === 'failed' 
        ? 'failed' 
        : status === 'reused' || event.receipt?.from_cache 
          ? 'reused' 
          : 'completed';
      toolCall.result = result;
      toolCall.error = error;
      toolCall.receipt = event.receipt;
      
      activeToolCalls.current.delete(callId);
      
      updateEvidence((prev) => ({
        ...prev,
        completedToolCalls: prev.completedToolCalls + (toolCall.status === 'completed' ? 1 : 0),
        cachedToolCalls: prev.cachedToolCalls + (toolCall.status === 'reused' ? 1 : 0),
        failedToolCalls: prev.failedToolCalls + (toolCall.status === 'failed' ? 1 : 0),
        lastUpdate: Date.now(),
      }));
    }
    
    return toolCall;
  }, [updateEvidence]);
  
  /**
   * Process a parsed event and update agent state accordingly.
   */
  const processAgentEvent = useCallback((event: ParsedEvent): boolean => {
    switch (event.eventType) {
      case 'agent_turn_start':
        handleTurnStart(event);
        return true;
      case 'agent_turn_end':
        handleTurnEnd(event);
        return true;
      case 'agent_tool_start':
        handleToolStart(event);
        return true;
      case 'agent_tool_end':
        handleToolEnd(event);
        return true;
      default:
        return false; // Not an agent event
    }
  }, [handleTurnStart, handleTurnEnd, handleToolStart, handleToolEnd]);
  
  /**
   * Check if agent evidence is missing (evidence gap).
   * Called at workflow completion to detect missing agent events.
   */
  const checkEvidenceGap = useCallback((
    expectedToolCount: number,
    flowMode: 'planner-executor' | 'single-agent' | 'multi-agent'
  ): boolean => {
    // In DIRECT mode, no agent events expected
    if (flowMode === 'planner-executor') {
      return false;
    }
    
    const current = evidenceRef.current;
    
    // Check if any agent turns were recorded
    if (current.turns.length === 0) {
      return true; // No agent turns at all
    }
    
    // Check for incomplete turns
    const hasIncompleteTurns = current.turns.some((t) => t.status === 'running');
    if (hasIncompleteTurns) {
      return true;
    }
    
    // Check tool call count matches expected
    if (expectedToolCount > 0 && current.totalToolCalls < expectedToolCount * 0.8) {
      return true; // Less than 80% of expected tool calls
    }
    
    // Check for high failure rate
    const failureRate = current.totalToolCalls > 0 
      ? current.failedToolCalls / current.totalToolCalls 
      : 0;
    if (failureRate > 0.5) {
      return true; // More than 50% failures
    }
    
    return false;
  }, []);
  
  /**
   * Mark evidence gap detected.
   * Emits workflow_error:AGENT_RUNTIME_MISSING_EVIDENCE per Phase 2.2 spec.
   */
  const markEvidenceGap = useCallback(() => {
    updateEvidence((prev) => ({
      ...prev,
      hasEvidenceGap: true,
      lastUpdate: Date.now(),
    }));
  }, [updateEvidence]);
  
  /**
   * Reset agent state for a new query.
   */
  const reset = useCallback(() => {
    activeTurns.current.clear();
    activeToolCalls.current.clear();
    setEvidence(INITIAL_EVIDENCE);
    evidenceRef.current = INITIAL_EVIDENCE;
  }, []);
  
  /**
   * Get current turn by role (for UI display).
   */
  const getCurrentTurnByRole = useCallback((role: string): AgentTurn | undefined => {
    for (const turn of activeTurns.current.values()) {
      if (turn.agentRole === role && turn.status === 'running') {
        return turn;
      }
    }
    return undefined;
  }, []);
  
  /**
   * Get active tool calls (for progress display).
   */
  const getActiveToolCalls = useCallback((): AgentToolCall[] => {
    return Array.from(activeToolCalls.current.values());
  }, []);
  
  /**
   * Get tool calls by lane (for lane-specific progress).
   */
  const getToolCallsByLane = useCallback((lane: string): AgentToolCall[] => {
    const all = evidenceRef.current.turns.flatMap((t) => t.tools);
    return all.filter((tc) => tc.lane === lane);
  }, []);
  
  /**
   * Calculate cache hit rate (for metrics display).
   */
  const getCacheHitRate = useCallback((): number => {
    const current = evidenceRef.current;
    if (current.totalToolCalls === 0) return 0;
    return current.cachedToolCalls / current.totalToolCalls;
  }, []);
  
  return {
    evidence,
    evidenceRef,
    processAgentEvent,
    checkEvidenceGap,
    markEvidenceGap,
    reset,
    getCurrentTurnByRole,
    getActiveToolCalls,
    getToolCallsByLane,
    getCacheHitRate,
    // Individual handlers for direct use
    handleTurnStart,
    handleTurnEnd,
    handleToolStart,
    handleToolEnd,
  };
};

export default useAgentEvents;

