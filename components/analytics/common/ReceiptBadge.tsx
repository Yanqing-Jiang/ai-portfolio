/**
 * Component: ReceiptBadge
 * Purpose: Renders badges from receipt data fields
 * Called from: ProcessPanel, WorkflowCanvas
 * Invokes: useBadgeLogic hook
 * Why: Provides receipt-driven badge rendering per Phase 4.2 of the refactor plan.
 * 
 * Part of Phase 4.2: Update ProcessPanel/WorkflowCanvas to render from receipt fields.
 * Per spec: Render from receipt fields (from_cache, guardrail, retry_count, specialist_role)
 */

import React from 'react';
import { Badge, useBadgeLogic, BadgeSeverity } from '../hooks/useBadgeLogic';
import type { ReceiptData } from '../hooks/useEventParser';

export interface ReceiptBadgeProps {
  /** Receipt data from tool invocation */
  receipt?: ReceiptData;
  /** Maximum number of badges to show */
  maxBadges?: number;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Whether to show icons */
  showIcons?: boolean;
  /** Whether to show tooltips */
  showTooltips?: boolean;
  /** Custom class name */
  className?: string;
}

// Size-specific styles
const sizeStyles = {
  sm: {
    container: 'gap-1',
    badge: 'px-1.5 py-0.5 text-[10px]',
    icon: 'text-[9px]',
  },
  md: {
    container: 'gap-1.5',
    badge: 'px-2 py-0.5 text-[11px]',
    icon: 'text-[10px]',
  },
  lg: {
    container: 'gap-2',
    badge: 'px-2.5 py-1 text-xs',
    icon: 'text-sm',
  },
};

// Severity-specific colors
const severityColors: Record<BadgeSeverity, string> = {
  info: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  warning: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  error: 'bg-red-500/10 text-red-400 border-red-500/30',
};

/**
 * Single badge renderer
 */
const SingleBadge: React.FC<{
  badge: Badge;
  size: 'sm' | 'md' | 'lg';
  showIcon: boolean;
  showTooltip: boolean;
}> = ({ badge, size, showIcon, showTooltip }) => {
  const styles = sizeStyles[size];
  const colorClass = severityColors[badge.severity];
  
  const content = (
    <span
      className={`
        inline-flex items-center gap-0.5 rounded border font-medium
        ${styles.badge}
        ${colorClass}
      `}
    >
      {showIcon && badge.icon && (
        <span className={styles.icon}>{badge.icon}</span>
      )}
      <span>{badge.label}</span>
    </span>
  );
  
  if (showTooltip && badge.tooltip) {
    return (
      <span title={badge.tooltip} className="cursor-help">
        {content}
      </span>
    );
  }
  
  return content;
};

/**
 * ReceiptBadge - Renders badges from receipt data
 * 
 * Usage:
 * ```tsx
 * <ReceiptBadge 
 *   receipt={toolReceipt} 
 *   maxBadges={3} 
 *   size="sm" 
 * />
 * ```
 */
export const ReceiptBadge: React.FC<ReceiptBadgeProps> = ({
  receipt,
  maxBadges = 3,
  size = 'sm',
  showIcons = true,
  showTooltips = true,
  className = '',
}) => {
  const { createBadgesFromReceipt, filterTopBadges } = useBadgeLogic();
  
  if (!receipt) {
    return null;
  }
  
  const allBadges = createBadgesFromReceipt(receipt);
  const visibleBadges = filterTopBadges(allBadges, maxBadges);
  const styles = sizeStyles[size];
  
  if (visibleBadges.length === 0) {
    return null;
  }
  
  return (
    <span className={`inline-flex flex-wrap items-center ${styles.container} ${className}`}>
      {visibleBadges.map((badge, idx) => (
        <SingleBadge
          key={`${badge.type}-${idx}`}
          badge={badge}
          size={size}
          showIcon={showIcons}
          showTooltip={showTooltips}
        />
      ))}
      {allBadges.length > maxBadges && (
        <span 
          className={`${styles.badge} text-gray-500`}
          title={`+${allBadges.length - maxBadges} more badges`}
        >
          +{allBadges.length - maxBadges}
        </span>
      )}
    </span>
  );
};

/**
 * Props for LaneBadges component
 */
export interface LaneBadgesProps {
  /** Lane name */
  lane: string;
  /** Receipts for the lane */
  receipts: ReceiptData[];
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Custom class name */
  className?: string;
}

/**
 * LaneBadges - Renders aggregated badges for a lane
 */
export const LaneBadges: React.FC<LaneBadgesProps> = ({
  lane,
  receipts,
  size = 'sm',
  className = '',
}) => {
  const { aggregateLaneBadges, sortBadges } = useBadgeLogic();
  
  if (!receipts || receipts.length === 0) {
    return null;
  }
  
  const laneBadges = aggregateLaneBadges(lane, receipts);
  const sorted = sortBadges(laneBadges.badges);
  const styles = sizeStyles[size];
  
  if (sorted.length === 0) {
    return null;
  }
  
  return (
    <span className={`inline-flex flex-wrap items-center ${styles.container} ${className}`}>
      {sorted.map((badge, idx) => (
        <SingleBadge
          key={`${badge.type}-${idx}`}
          badge={badge}
          size={size}
          showIcon={true}
          showTooltip={true}
        />
      ))}
    </span>
  );
};

/**
 * Props for legacy badge compatibility
 */
export interface LegacyBadgeProps {
  /** Reused flag (legacy) */
  reused?: boolean;
  /** Cache age in seconds (legacy) */
  cacheAgeSeconds?: number;
  /** Fast path latency (legacy) */
  fastPathLatencyMs?: number;
  /** Guardrail status (legacy) */
  guardrail?: {
    type?: string;
    severity?: string;
    message?: string;
  };
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Custom class name */
  className?: string;
}

/**
 * LegacyBadge - Converts legacy badge data to receipt-based rendering
 * Use this for backwards compatibility during migration.
 */
export const LegacyBadge: React.FC<LegacyBadgeProps> = ({
  reused,
  cacheAgeSeconds,
  fastPathLatencyMs,
  guardrail,
  size = 'sm',
  className = '',
}) => {
  // Convert legacy data to receipt format
  const receipt: ReceiptData = {
    tool: 'legacy',
    status: reused ? 'reused' : 'completed',
    from_cache: reused,
    age_seconds: cacheAgeSeconds,
    latency_ms: fastPathLatencyMs,
    guardrail: guardrail?.type as ReceiptData['guardrail'],
  };
  
  return (
    <ReceiptBadge
      receipt={receipt}
      size={size}
      className={className}
    />
  );
};

export default ReceiptBadge;

