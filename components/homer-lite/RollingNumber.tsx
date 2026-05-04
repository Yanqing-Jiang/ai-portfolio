import React, { useEffect, useRef, useState } from 'react';
import { motion, useInView } from 'framer-motion';
import { HOMER_THEME } from './theme';

// Function: RollingNumber — odometer-style digit animation.
// Animates from `start` to `target` whenever the element enters the viewport.
// Resets back to `start` when it scrolls out of view, so each return trip plays
// the climb again. No background cycling — the animation is gated entirely
// on scroll position.
//
// Used by Why section to show "{n} months in production": 3 → 5.

interface RollingNumberProps {
  /** Where the count-up starts when the component first scrolls into view. */
  start?: number;
  /** Where the count-up lands. */
  target: number;
  /** Climb duration in ms. */
  durationMs?: number;
  /** Pixel height of a single digit; controls roll motion magnitude. */
  digitHeight?: number;
  className?: string;
}

const DIGITS = '0123456789'.split('');

// Function: Digit — one rolling slot. Renders a vertical strip of 0-9 and
// translates it so the matching digit lands in the visible window.
const Digit: React.FC<{ value: number; height: number }> = ({ value, height }) => (
  <span
    className="relative inline-block overflow-hidden align-baseline"
    style={{ height, width: '0.62em' }}
  >
    <motion.span
      animate={{ y: -value * height }}
      transition={{ type: 'spring', stiffness: 110, damping: 18 }}
      className="absolute inset-x-0 top-0 flex flex-col items-center"
    >
      {DIGITS.map((d) => (
        <span
          key={d}
          className="flex items-center justify-center w-full"
          style={{ height, lineHeight: `${height}px` }}
        >
          {d}
        </span>
      ))}
    </motion.span>
  </span>
);

export const RollingNumber: React.FC<RollingNumberProps> = ({
  start = 0,
  target,
  durationMs = 1100,
  digitHeight = 72,
  className = '',
}) => {
  const ref = useRef<HTMLSpanElement>(null);
  // once: false → re-fires every time the element comes back into view.
  // amount: 0.5 — at least half of the number must be visible to count as "arrived".
  const inView = useInView(ref, { once: false, amount: 0.5 });
  const [value, setValue] = useState(start);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    // Cancel any in-flight climb whenever inView toggles.
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }

    if (!inView) {
      // Out of view: snap back so the next arrival shows the climb again.
      setValue(start);
      return;
    }

    // In view: climb from `start` to `target` once.
    const begin = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - begin) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setValue(Math.round(start + eased * (target - start)));
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
      else rafRef.current = null;
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [inView, start, target, durationMs]);

  const text = Math.max(0, Math.round(value)).toString();
  const digits = text.split('').map((d, i) => ({ d: parseInt(d, 10), key: `${i}` }));

  return (
    <span
      ref={ref}
      className={`inline-flex items-baseline ${className}`}
      style={{
        fontFamily: HOMER_THEME.fontSerif,
        color: HOMER_THEME.accent,
        fontFeatureSettings: '"tnum"',
        lineHeight: 1,
      }}
      aria-label={`${target} months`}
    >
      {digits.map(({ d, key }) => (
        <Digit key={key} value={d} height={digitHeight} />
      ))}
    </span>
  );
};

export default RollingNumber;
