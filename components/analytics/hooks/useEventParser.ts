/**
 * Hook: useEventParser
 * Purpose: Parses SSE events from the analytics backend
 * Called from: useAnalyticsMemoryStream
 * Invokes: Event normalization utilities
 * Why: Centralizes event parsing logic to reduce complexity in the main hook.
 * 
 * Part of Phase 4.1 of the analytics refactor plan - hook decomposition.
 * Target: ~500-800 LOC
 */

import { useCallback, useRef } from 'react';

// Event aliases for legacy/new format compatibility
export const REVISION_EVENT_ALIASES: Record<string, string> = {
  // Legacy -> normalized event names
  'revision_started': 'revision_started',
  'revision_complete': 'revision_complete',
  'analysis_revision_started': 'revision_started',
  'analysis_revision_complete': 'revision_complete',
  'chart_revision_started': 'revision_started',
  'chart_revision_complete': 'revision_complete',
  'market_revision_started': 'revision_started',
  'market_revision_complete': 'revision_complete',
  // Agent events
  'agent_turn_start': 'agent_turn_start',
  'agent_turn_end': 'agent_turn_end',
  'agent_tool_start': 'agent_tool_start',
  'agent_tool_end': 'agent_tool_end',
  // Pool events (Phase 3)
  'sql_pool_complete': 'sql_pool_complete',
  'chart_pool_complete': 'chart_pool_complete',
  'analysis_pool_complete': 'analysis_pool_complete',
  'web_pool_complete': 'web_pool_complete',
  'market_pool_complete': 'market_pool_complete',
};

// Event visibility types
export type EventVisibility = 'user' | 'thinking' | 'system' | 'debug';

// Receipt data from backend
export interface ReceiptData {
  tool: string;
  status: 'completed' | 'failed' | 'reused' | 'pending';
  from_cache?: boolean;
  age_seconds?: number;
  latency_ms?: number;
  retry_count?: number;
  guardrail?: 'passed' | 'blocked' | 'warnings';
  specialist_role?: string;
  schema_version?: string;
  output_hash?: string;
}

// Parsed event structure
export interface ParsedEvent {
  eventType: string;
  eventData: Record<string, unknown>;
  visibility: EventVisibility;
  isThinking: boolean;
  revisionId?: string;
  revisionLanes?: string[];
  thoughtId?: string;
  timestamp: number;
  // Receipt data if present
  receipt?: ReceiptData;
  // Pool execution data (Phase 3)
  poolData?: {
    poolId: string;
    success: boolean;
    fromCache: boolean;
    latencyMs: number;
  };
}

// Coerce value to string or undefined
export const coerceString = (value: unknown): string | undefined => {
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  return undefined;
};

// Coerce value to boolean
export const coerceBoolean = (value: unknown): boolean => {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') {
    const lower = value.toLowerCase();
    return lower === 'true' || lower === '1' || lower === 'yes';
  }
  return Boolean(value);
};

// Coerce value to number or undefined
export const coerceNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && !Number.isNaN(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = parseFloat(value);
    if (!Number.isNaN(parsed)) return parsed;
  }
  return undefined;
};

// Parse receipt data from event
const parseReceiptData = (data: Record<string, unknown>): ReceiptData | undefined => {
  const receiptRaw = data.receipt ?? data.tool_receipt;
  if (!receiptRaw || typeof receiptRaw !== 'object') {
    return undefined;
  }
  
  const receipt = receiptRaw as Record<string, unknown>;
  return {
    tool: coerceString(receipt.tool) ?? 'unknown',
    status: (coerceString(receipt.status) ?? 'pending') as ReceiptData['status'],
    from_cache: coerceBoolean(receipt.from_cache),
    age_seconds: coerceNumber(receipt.age_seconds),
    latency_ms: coerceNumber(receipt.latency_ms ?? receipt.elapsed_ms),
    retry_count: coerceNumber(receipt.retry_count),
    guardrail: coerceString(receipt.guardrail) as ReceiptData['guardrail'],
    specialist_role: coerceString(receipt.specialist_role),
    schema_version: coerceString(receipt.schema_version),
    output_hash: coerceString(receipt.output_hash),
  };
};

// Parse pool execution data (Phase 3)
const parsePoolData = (eventType: string, data: Record<string, unknown>) => {
  if (!eventType.endsWith('_pool_complete')) {
    return undefined;
  }
  
  const poolData = data.data ?? data;
  if (typeof poolData !== 'object') return undefined;
  
  const pool = poolData as Record<string, unknown>;
  return {
    poolId: coerceString(pool.pool_id) ?? eventType.replace('_complete', ''),
    success: coerceBoolean(pool.success),
    fromCache: coerceBoolean(pool.from_cache),
    latencyMs: coerceNumber(pool.latency_ms) ?? 0,
  };
};

/**
 * Hook for parsing SSE events from the analytics backend.
 * Normalizes event formats, extracts receipt data, and handles visibility.
 */
export const useEventParser = () => {
  // Track seen event IDs for deduplication
  const seenEventIds = useRef<Set<string>>(new Set());
  
  /**
   * Parse a raw SSE event into a normalized structure.
   */
  const parseEvent = useCallback((rawData: Record<string, unknown>): ParsedEvent | null => {
    // Get event type (support both formats)
    const rawEventType = rawData.event ?? rawData.type;
    if (typeof rawEventType !== 'string') {
      return null;
    }
    
    // Normalize event type using aliases
    const eventType = REVISION_EVENT_ALIASES[rawEventType] ?? rawEventType;
    
    // Get event data (support both heavy and lightweight formats)
    const eventData = (rawData.data ?? rawData) as Record<string, unknown>;
    
    // Extract visibility
    const eventVisibility: EventVisibility = 
      typeof rawData.event_type === 'string' 
        ? rawData.event_type as EventVisibility 
        : 'user';
    const isThinking = eventVisibility === 'thinking';
    
    // Extract revision context
    const revisionId = coerceString(rawData.revision_id ?? eventData.revision_id);
    const revisionLanesRaw = Array.isArray(rawData.revision_lanes)
      ? rawData.revision_lanes
      : Array.isArray(eventData.revision_lanes)
        ? eventData.revision_lanes
        : undefined;
    
    const revisionLanes = Array.isArray(revisionLanesRaw)
      ? (revisionLanesRaw as unknown[])
          .map((lane) => (typeof lane === 'string' ? lane.toLowerCase() : ''))
          .filter((lane): lane is string => lane.length > 0)
      : undefined;
    
    // Extract thought ID for deduplication
    const thoughtId = coerceString(eventData.thought_id ?? rawData.thought_id);
    
    // Check for duplicates
    if (thoughtId && seenEventIds.current.has(thoughtId)) {
      return null; // Skip duplicate
    }
    if (thoughtId) {
      seenEventIds.current.add(thoughtId);
    }
    
    // Parse receipt data if present
    const receipt = parseReceiptData(eventData);
    
    // Parse pool data for Phase 3 events
    const poolData = parsePoolData(eventType, eventData);
    
    return {
      eventType,
      eventData,
      visibility: eventVisibility,
      isThinking,
      revisionId,
      revisionLanes,
      thoughtId,
      timestamp: Date.now(),
      receipt,
      poolData,
    };
  }, []);
  
  /**
   * Reset seen events (call when starting a new query).
   */
  const resetSeenEvents = useCallback(() => {
    seenEventIds.current.clear();
  }, []);
  
  /**
   * Check if an event should be rendered based on visibility and flow mode.
   */
  const shouldRenderEvent = useCallback((
    event: ParsedEvent,
    options?: {
      showThinking?: boolean;
      showDebug?: boolean;
      flowMode?: 'planner-executor' | 'single-agent' | 'multi-agent';
    }
  ): boolean => {
    const { showThinking = false, showDebug = false, flowMode = 'single-agent' } = options ?? {};
    
    // Always hide system events from rendering
    if (event.visibility === 'system') {
      return false;
    }
    
    // Debug events only shown if explicitly enabled
    if (event.visibility === 'debug' && !showDebug) {
      return false;
    }
    
    // Thinking events shown based on preference
    if (event.isThinking && !showThinking) {
      return false;
    }
    
    // Planner events (classification, plan_ready, etc.) only in DIRECT mode
    const plannerOnlyEvents = [
      'classification_complete',
      'plan_ready',
      'sql_compiled',
      'sql_validated',
      'template_selected',
    ];
    if (plannerOnlyEvents.includes(event.eventType) && flowMode !== 'planner-executor') {
      // In agent modes, these should be hidden by default
      return false;
    }
    
    return true;
  }, []);
  
  /**
   * Extract badge-relevant data from an event.
   */
  const extractBadgeData = useCallback((event: ParsedEvent) => {
    const badges: Array<{
      type: 'reuse' | 'guardrail' | 'retry' | 'cache' | 'specialist';
      value: string | number | boolean;
      severity?: 'info' | 'warning' | 'error';
    }> = [];
    
    if (event.receipt) {
      // Reuse badge
      if (event.receipt.status === 'reused' || event.receipt.from_cache) {
        badges.push({
          type: 'reuse',
          value: true,
          severity: 'info',
        });
      }
      
      // Cache badge with age
      if (event.receipt.from_cache && event.receipt.age_seconds !== undefined) {
        badges.push({
          type: 'cache',
          value: event.receipt.age_seconds,
          severity: 'info',
        });
      }
      
      // Guardrail badge
      if (event.receipt.guardrail && event.receipt.guardrail !== 'passed') {
        badges.push({
          type: 'guardrail',
          value: event.receipt.guardrail,
          severity: event.receipt.guardrail === 'blocked' ? 'error' : 'warning',
        });
      }
      
      // Retry badge
      if (event.receipt.retry_count && event.receipt.retry_count > 0) {
        badges.push({
          type: 'retry',
          value: event.receipt.retry_count,
          severity: 'warning',
        });
      }
      
      // Specialist badge
      if (event.receipt.specialist_role) {
        badges.push({
          type: 'specialist',
          value: event.receipt.specialist_role,
          severity: 'info',
        });
      }
    }
    
    return badges;
  }, []);
  
  return {
    parseEvent,
    resetSeenEvents,
    shouldRenderEvent,
    extractBadgeData,
    // Expose utilities for direct use
    coerceString,
    coerceBoolean,
    coerceNumber,
  };
};

export default useEventParser;

