/**
 * useAnimatedNumber - Animate numeric values with reduced-motion support.
 *
 * Hook: useAnimatedNumber
 * Called from: KpiCard, ComparisonKpiCard, MetricChart
 * Invokes: useEffect, requestAnimationFrame
 * Why: Provides smooth number transitions for KPIs and metrics.
 *      Respects user's prefers-reduced-motion preference.
 */

import { useState, useEffect, useRef } from 'react';

// ============================================================================
// Types
// ============================================================================

export interface AnimatedNumberOptions {
    /** Duration of animation in ms (default: 800) */
    duration?: number;
    /** Easing function (default: easeOutExpo) */
    easing?: 'linear' | 'easeOut' | 'easeOutExpo' | 'easeInOut';
    /** Decimal places to show (default: auto-detect) */
    decimals?: number;
    /** Whether to animate on initial mount (default: true) */
    animateOnMount?: boolean;
    /** Start value for animation (default: 0) */
    startValue?: number;
}

// ============================================================================
// Easing Functions
// ============================================================================

const easingFunctions = {
    linear: (t: number) => t,
    easeOut: (t: number) => 1 - Math.pow(1 - t, 3),
    easeOutExpo: (t: number) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t)),
    easeInOut: (t: number) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
};

// ============================================================================
// Hook
// ============================================================================

/**
 * Animate a numeric value with smooth transitions.
 *
 * @param value - The target value to animate to
 * @param options - Animation options
 * @returns The current animated value
 *
 * @example
 * ```tsx
 * const animatedRevenue = useAnimatedNumber(revenue, { duration: 1000 });
 * return <span>${animatedRevenue.toLocaleString()}</span>;
 * ```
 */
export function useAnimatedNumber(
    value: number,
    options: AnimatedNumberOptions = {}
): number {
    const {
        duration = 800,
        easing = 'easeOutExpo',
        decimals,
        animateOnMount = true,
        startValue = 0,
    } = options;

    // Check for reduced motion preference
    const prefersReducedMotion = typeof window !== 'undefined'
        && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    const [displayValue, setDisplayValue] = useState(animateOnMount ? startValue : value);
    const previousValue = useRef(animateOnMount ? startValue : value);
    const animationRef = useRef<number | null>(null);
    const isFirstRender = useRef(true);

    // Auto-detect decimals if not specified
    const getDecimals = (num: number): number => {
        if (decimals !== undefined) return decimals;
        const str = String(num);
        const decimalIndex = str.indexOf('.');
        return decimalIndex === -1 ? 0 : str.length - decimalIndex - 1;
    };

    useEffect(() => {
        // Skip animation on first render if animateOnMount is false
        if (isFirstRender.current) {
            isFirstRender.current = false;
            if (!animateOnMount) {
                setDisplayValue(value);
                previousValue.current = value;
                return;
            }
        }

        // Skip animation if reduced motion is preferred
        if (prefersReducedMotion) {
            setDisplayValue(value);
            previousValue.current = value;
            return;
        }

        // Skip if value hasn't changed
        if (previousValue.current === value) return;

        // Cancel any ongoing animation
        if (animationRef.current) {
            cancelAnimationFrame(animationRef.current);
        }

        const from = previousValue.current;
        const to = value;
        const diff = to - from;
        const targetDecimals = Math.max(getDecimals(from), getDecimals(to));
        const startTime = performance.now();
        const easeFn = easingFunctions[easing];

        const animate = (currentTime: number) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easedProgress = easeFn(progress);
            const currentValue = from + diff * easedProgress;

            // Round to appropriate decimals
            const roundedValue = Number(currentValue.toFixed(targetDecimals));
            setDisplayValue(roundedValue);

            if (progress < 1) {
                animationRef.current = requestAnimationFrame(animate);
            } else {
                // Ensure final value is exact
                setDisplayValue(to);
                previousValue.current = to;
            }
        };

        animationRef.current = requestAnimationFrame(animate);

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
        };
    }, [value, duration, easing, decimals, animateOnMount, prefersReducedMotion]);

    // Update previous value when animation completes or is skipped
    useEffect(() => {
        previousValue.current = value;
    }, [value]);

    return displayValue;
}

/**
 * Format an animated number with locale-aware formatting.
 *
 * @param value - The animated value
 * @param options - Formatting options
 * @returns Formatted string
 */
export function formatAnimatedNumber(
    value: number,
    options: {
        locale?: string;
        style?: 'decimal' | 'currency' | 'percent';
        currency?: string;
        minimumFractionDigits?: number;
        maximumFractionDigits?: number;
        compact?: boolean;
    } = {}
): string {
    const {
        locale = 'en-US',
        style = 'decimal',
        currency = 'USD',
        minimumFractionDigits,
        maximumFractionDigits,
        compact = false,
    } = options;

    const formatOptions: Intl.NumberFormatOptions = {
        style,
        ...(style === 'currency' && { currency }),
        ...(minimumFractionDigits !== undefined && { minimumFractionDigits }),
        ...(maximumFractionDigits !== undefined && { maximumFractionDigits }),
        ...(compact && { notation: 'compact', compactDisplay: 'short' }),
    };

    return new Intl.NumberFormat(locale, formatOptions).format(value);
}

export default useAnimatedNumber;
