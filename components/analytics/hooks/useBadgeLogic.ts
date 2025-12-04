/**
 * Hook: useBadgeLogic
 * Purpose: Computes reuse/guardrail/retry badges from receipt fields
 * Called from: ProcessPanel, WorkflowCanvas, useAnalyticsMemoryStream
 * Invokes: Receipt data analysis
 * Why: Centralizes badge logic to ensure consistent rendering across components.
 * 
 * Part of Phase 4.1 of the analytics refactor plan - hook decomposition.
 * Target: ~500-800 LOC
 * 
 * Per Phase 4.2: Render badges from receipt fields, not heuristics.
 */

import { useCallback, useMemo } from 'react';
import { ReceiptData } from './useEventParser';

// Badge types
export type BadgeType = 
  | 'reuse'      // Tool result was reused from cache
  | 'cache'      // Data served from cache (with age)
  | 'guardrail'  // Guardrail status (passed/blocked/warnings)
  | 'retry'      // Tool was retried
  | 'specialist' // Specialist role attribution
  | 'latency'    // Latency indicator (fast/slow)
  | 'fresh'      // Fresh data (not cached)
  | 'error';     // Error occurred

// Badge severity for styling
export type BadgeSeverity = 'info' | 'success' | 'warning' | 'error';

// Badge data structure
export interface Badge {
  type: BadgeType;
  label: string;
  value?: string | number | boolean;
  severity: BadgeSeverity;
  tooltip?: string;
  icon?: string;
}

// Lane-specific badges (accumulated across a lane's tools)
export interface LaneBadges {
  lane: string;
  badges: Badge[];
  totalLatencyMs: number;
  cacheHits: number;
  retries: number;
  errors: number;
}

// Latency thresholds (ms)
const LATENCY_THRESHOLDS = {
  fast: 500,     // < 500ms = fast
  normal: 2000,  // < 2000ms = normal
  slow: 5000,    // < 5000ms = slow
  // >= 5000ms = very slow
};

// Cache age thresholds (seconds)
const CACHE_AGE_THRESHOLDS = {
  fresh: 60,      // < 60s = fresh
  recent: 300,    // < 5min = recent
  stale: 1800,    // < 30min = stale
  // >= 30min = very stale
};

/**
 * Format latency for display.
 */
const formatLatency = (ms: number): string => {
  if (ms < 1000) {
    return `${Math.round(ms)}ms`;
  }
  return `${(ms / 1000).toFixed(1)}s`;
};

/**
 * Format cache age for display.
 */
const formatCacheAge = (seconds: number): string => {
  if (seconds < 60) {
    return `${Math.round(seconds)}s ago`;
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)}m ago`;
  }
  return `${Math.round(seconds / 3600)}h ago`;
};

/**
 * Get severity for latency.
 */
const getLatencySeverity = (ms: number): BadgeSeverity => {
  if (ms < LATENCY_THRESHOLDS.fast) return 'success';
  if (ms < LATENCY_THRESHOLDS.normal) return 'info';
  if (ms < LATENCY_THRESHOLDS.slow) return 'warning';
  return 'error';
};

/**
 * Get severity for cache age.
 */
const getCacheAgeSeverity = (seconds: number): BadgeSeverity => {
  if (seconds < CACHE_AGE_THRESHOLDS.fresh) return 'success';
  if (seconds < CACHE_AGE_THRESHOLDS.recent) return 'info';
  if (seconds < CACHE_AGE_THRESHOLDS.stale) return 'warning';
  return 'error';
};

/**
 * Hook for computing and managing badges from receipt data.
 */
export const useBadgeLogic = () => {
  /**
   * Create badges from a single receipt.
   */
  const createBadgesFromReceipt = useCallback((receipt: ReceiptData): Badge[] => {
    const badges: Badge[] = [];
    
    // Reuse/Cache badge
    if (receipt.status === 'reused' || receipt.from_cache) {
      const ageSeconds = receipt.age_seconds;
      if (ageSeconds !== undefined) {
        badges.push({
          type: 'cache',
          label: 'Cached',
          value: ageSeconds,
          severity: getCacheAgeSeverity(ageSeconds),
          tooltip: `Result from cache (${formatCacheAge(ageSeconds)})`,
          icon: '♻️',
        });
      } else {
        badges.push({
          type: 'reuse',
          label: 'Reused',
          value: true,
          severity: 'info',
          tooltip: 'Result reused from previous execution',
          icon: '♻️',
        });
      }
    } else if (receipt.status === 'completed') {
      // Fresh data badge
      badges.push({
        type: 'fresh',
        label: 'Fresh',
        value: true,
        severity: 'success',
        tooltip: 'Freshly computed result',
        icon: '✨',
      });
    }
    
    // Guardrail badge
    if (receipt.guardrail) {
      const guardrail = receipt.guardrail;
      let severity: BadgeSeverity = 'success';
      let icon = '✓';
      let tooltip = 'Guardrail checks passed';
      
      if (guardrail === 'blocked') {
        severity = 'error';
        icon = '🚫';
        tooltip = 'Blocked by guardrail';
      } else if (guardrail === 'warnings') {
        severity = 'warning';
        icon = '⚠️';
        tooltip = 'Guardrail warnings';
      }
      
      badges.push({
        type: 'guardrail',
        label: guardrail === 'passed' ? 'Safe' : guardrail === 'blocked' ? 'Blocked' : 'Warnings',
        value: guardrail,
        severity,
        tooltip,
        icon,
      });
    }
    
    // Retry badge
    if (receipt.retry_count && receipt.retry_count > 0) {
      badges.push({
        type: 'retry',
        label: `Retry ${receipt.retry_count}`,
        value: receipt.retry_count,
        severity: receipt.retry_count > 2 ? 'error' : 'warning',
        tooltip: `Retried ${receipt.retry_count} time(s)`,
        icon: '🔄',
      });
    }
    
    // Latency badge
    if (receipt.latency_ms !== undefined) {
      badges.push({
        type: 'latency',
        label: formatLatency(receipt.latency_ms),
        value: receipt.latency_ms,
        severity: getLatencySeverity(receipt.latency_ms),
        tooltip: `Execution took ${formatLatency(receipt.latency_ms)}`,
        icon: '⏱️',
      });
    }
    
    // Specialist badge
    if (receipt.specialist_role) {
      badges.push({
        type: 'specialist',
        label: receipt.specialist_role,
        value: receipt.specialist_role,
        severity: 'info',
        tooltip: `Handled by ${receipt.specialist_role} specialist`,
        icon: '👤',
      });
    }
    
    // Error badge
    if (receipt.status === 'failed') {
      badges.push({
        type: 'error',
        label: 'Failed',
        value: true,
        severity: 'error',
        tooltip: 'Tool execution failed',
        icon: '❌',
      });
    }
    
    return badges;
  }, []);
  
  /**
   * Aggregate badges from multiple receipts for a lane.
   */
  const aggregateLaneBadges = useCallback((
    lane: string,
    receipts: ReceiptData[]
  ): LaneBadges => {
    let totalLatencyMs = 0;
    let cacheHits = 0;
    let retries = 0;
    let errors = 0;
    
    const allBadges: Badge[] = [];
    
    for (const receipt of receipts) {
      if (receipt.latency_ms) {
        totalLatencyMs += receipt.latency_ms;
      }
      if (receipt.from_cache || receipt.status === 'reused') {
        cacheHits++;
      }
      if (receipt.retry_count) {
        retries += receipt.retry_count;
      }
      if (receipt.status === 'failed') {
        errors++;
      }
      
      // Don't add individual badges, we'll create aggregated ones
    }
    
    // Create aggregated badges
    const badges: Badge[] = [];
    
    // Cache summary badge
    if (cacheHits > 0) {
      const cacheRate = receipts.length > 0 ? cacheHits / receipts.length : 0;
      badges.push({
        type: 'cache',
        label: `${Math.round(cacheRate * 100)}% cached`,
        value: cacheHits,
        severity: cacheRate > 0.5 ? 'success' : 'info',
        tooltip: `${cacheHits} of ${receipts.length} results from cache`,
        icon: '♻️',
      });
    }
    
    // Latency summary badge
    if (totalLatencyMs > 0) {
      badges.push({
        type: 'latency',
        label: formatLatency(totalLatencyMs),
        value: totalLatencyMs,
        severity: getLatencySeverity(totalLatencyMs / Math.max(receipts.length, 1)),
        tooltip: `Total lane latency: ${formatLatency(totalLatencyMs)}`,
        icon: '⏱️',
      });
    }
    
    // Retry summary badge
    if (retries > 0) {
      badges.push({
        type: 'retry',
        label: `${retries} retries`,
        value: retries,
        severity: retries > 3 ? 'error' : 'warning',
        tooltip: `${retries} total retries in this lane`,
        icon: '🔄',
      });
    }
    
    // Error summary badge
    if (errors > 0) {
      badges.push({
        type: 'error',
        label: `${errors} errors`,
        value: errors,
        severity: 'error',
        tooltip: `${errors} tools failed in this lane`,
        icon: '❌',
      });
    }
    
    return {
      lane,
      badges,
      totalLatencyMs,
      cacheHits,
      retries,
      errors,
    };
  }, []);
  
  /**
   * Get badge CSS class based on type and severity.
   */
  const getBadgeClassName = useCallback((badge: Badge): string => {
    const baseClass = 'analytics-badge';
    const typeClass = `analytics-badge--${badge.type}`;
    const severityClass = `analytics-badge--${badge.severity}`;
    return `${baseClass} ${typeClass} ${severityClass}`;
  }, []);
  
  /**
   * Get badge style object for inline styling.
   */
  const getBadgeStyle = useCallback((badge: Badge): React.CSSProperties => {
    const colors: Record<BadgeSeverity, { bg: string; text: string; border: string }> = {
      info: { bg: '#e3f2fd', text: '#1565c0', border: '#90caf9' },
      success: { bg: '#e8f5e9', text: '#2e7d32', border: '#a5d6a7' },
      warning: { bg: '#fff3e0', text: '#ef6c00', border: '#ffcc80' },
      error: { bg: '#ffebee', text: '#c62828', border: '#ef9a9a' },
    };
    
    const colorSet = colors[badge.severity];
    
    return {
      backgroundColor: colorSet.bg,
      color: colorSet.text,
      border: `1px solid ${colorSet.border}`,
      borderRadius: '4px',
      padding: '2px 8px',
      fontSize: '12px',
      fontWeight: 500,
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
    };
  }, []);
  
  /**
   * Sort badges by importance.
   */
  const sortBadges = useCallback((badges: Badge[]): Badge[] => {
    const priority: Record<BadgeType, number> = {
      error: 0,
      guardrail: 1,
      retry: 2,
      cache: 3,
      reuse: 4,
      fresh: 5,
      latency: 6,
      specialist: 7,
    };
    
    return [...badges].sort((a, b) => {
      // First by severity (errors first)
      const severityOrder: Record<BadgeSeverity, number> = {
        error: 0,
        warning: 1,
        info: 2,
        success: 3,
      };
      const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
      if (severityDiff !== 0) return severityDiff;
      
      // Then by type priority
      return priority[a.type] - priority[b.type];
    });
  }, []);
  
  /**
   * Filter badges to show only the most important ones.
   */
  const filterTopBadges = useCallback((badges: Badge[], maxCount: number = 3): Badge[] => {
    const sorted = sortBadges(badges);
    return sorted.slice(0, maxCount);
  }, [sortBadges]);
  
  /**
   * Check if any badges indicate an issue.
   */
  const hasIssues = useCallback((badges: Badge[]): boolean => {
    return badges.some((b) => b.severity === 'error' || b.severity === 'warning');
  }, []);
  
  /**
   * Get summary text for badges.
   */
  const getSummaryText = useCallback((badges: Badge[]): string => {
    if (badges.length === 0) return '';
    
    const parts: string[] = [];
    
    const cacheHit = badges.find((b) => b.type === 'cache' || b.type === 'reuse');
    if (cacheHit) parts.push('cached');
    
    const retries = badges.find((b) => b.type === 'retry');
    if (retries) parts.push(`${retries.value} retries`);
    
    const errors = badges.find((b) => b.type === 'error');
    if (errors) parts.push('failed');
    
    const latency = badges.find((b) => b.type === 'latency');
    if (latency && typeof latency.value === 'number') {
      parts.push(formatLatency(latency.value));
    }
    
    return parts.join(' • ');
  }, []);
  
  return {
    createBadgesFromReceipt,
    aggregateLaneBadges,
    getBadgeClassName,
    getBadgeStyle,
    sortBadges,
    filterTopBadges,
    hasIssues,
    getSummaryText,
    // Constants
    LATENCY_THRESHOLDS,
    CACHE_AGE_THRESHOLDS,
  };
};

export default useBadgeLogic;

