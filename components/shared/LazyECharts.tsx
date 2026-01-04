/**
 * Component: LazyECharts — shared Suspense loader for `echarts-for-react`.
 * Used by: Conversational Analytics MessageBubble and A2UI widgets (MetricChart, PeerComparePanel, CorrelationMatrix).
 * Invokes: React.lazy(() => import('echarts-for-react')) and wraps it in <Suspense> with a lightweight skeleton.
 * Purpose: Code-split the heavy ECharts bundle for both projects while keeping a consistent loading state and avoiding initial bundle bloat.
 */
import React, { Suspense, lazy, useMemo } from 'react';
import type { EChartsReactProps } from 'echarts-for-react';

const ReactEChartsLazy = lazy(async () => {
  const mod = await import('echarts-for-react');
  return { default: (mod as any).default ?? mod };
});

type LazyEChartsProps = EChartsReactProps & {
  fallbackHeight?: number | string;
  fallback?: React.ReactNode;
};

const buildSkeleton = (
  fallback: React.ReactNode | undefined,
  fallbackHeight: number | string,
  style: React.CSSProperties | undefined,
) => {
  if (fallback) return fallback;
  const heightValue =
    typeof fallbackHeight === 'number' ? `${fallbackHeight}px` : fallbackHeight;
  return (
    <div
      style={{
        height: heightValue,
        width: style?.width ?? '100%',
        background:
          'linear-gradient(120deg, rgba(148,163,184,0.12) 0%, rgba(148,163,184,0.08) 40%, rgba(148,163,184,0.12) 80%)',
        border: '1px solid rgba(148, 163, 184, 0.15)',
        borderRadius: '12px',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          animation: 'pulse 1.6s ease-in-out infinite',
          background:
            'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.08) 50%, transparent 100%)',
          opacity: 0.6,
        }}
      />
      <style>
        {`@keyframes pulse { 0% { transform: translateX(-30%); } 100% { transform: translateX(130%); } }`}
      </style>
    </div>
  );
};

const LazyECharts: React.FC<LazyEChartsProps> = ({
  fallbackHeight = 320,
  fallback,
  style,
  ...rest
}) => {
  const skeleton = useMemo(
    () => buildSkeleton(fallback, fallbackHeight, style),
    [fallback, fallbackHeight, style],
  );

  return (
    <Suspense fallback={skeleton}>
      <ReactEChartsLazy {...rest} style={style} />
    </Suspense>
  );
};

export default LazyECharts;
