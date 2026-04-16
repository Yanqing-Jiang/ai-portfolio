/**
 * Shared Framer Motion variants for fortune result pages.
 *
 * Use `instantVariants` when `isReplay === true` to skip entrance animations.
 * All animations use the "smooth" easing curve for consistency.
 */

import type { Variants } from 'framer-motion';

// ---------------------------------------------------------------------------
// Easing curves
// ---------------------------------------------------------------------------

export const EASE = {
  smooth: [0.25, 0.46, 0.45, 0.94] as const,
  sharp: [0.4, 0, 0.2, 1] as const,
};

// ---------------------------------------------------------------------------
// Fade + slide up (default entrance for cards/sections)
// ---------------------------------------------------------------------------

export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE.smooth } },
};

// ---------------------------------------------------------------------------
// Stagger container + item
// ---------------------------------------------------------------------------

export const staggerContainer = (delay = 0.1): Variants => ({
  hidden: {},
  visible: { transition: { staggerChildren: delay, delayChildren: 0.2 } },
});

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 15 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: EASE.smooth } },
};

// ---------------------------------------------------------------------------
// SVG path drawing (for gauges, radar, connection lines)
// ---------------------------------------------------------------------------

export const drawPath: Variants = {
  hidden: { pathLength: 0, opacity: 0 },
  visible: { pathLength: 1, opacity: 1, transition: { duration: 1.5, ease: EASE.smooth } },
};

// ---------------------------------------------------------------------------
// Tab content enter/exit
// ---------------------------------------------------------------------------

export const tabContentVariants: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.32, 0.72, 0, 1] } },
  exit: { opacity: 0, y: -6, transition: { duration: 0.2 } },
};

// ---------------------------------------------------------------------------
// Scale-in for ring/gauge animations
// ---------------------------------------------------------------------------

export const scaleIn: Variants = {
  hidden: { scale: 0, opacity: 0 },
  visible: { scale: 1, opacity: 1, transition: { duration: 0.6, ease: EASE.smooth } },
};

// ---------------------------------------------------------------------------
// Bar grow (for timeline bars, strength bars)
// ---------------------------------------------------------------------------

export const barGrow: Variants = {
  hidden: { scaleY: 0, opacity: 0 },
  visible: { scaleY: 1, opacity: 1, transition: { duration: 0.5, ease: EASE.smooth } },
};

// ---------------------------------------------------------------------------
// Slide down (for expandable sections like hidden stems)
// ---------------------------------------------------------------------------

export const slideDown: Variants = {
  hidden: { height: 0, opacity: 0 },
  visible: { height: 'auto', opacity: 1, transition: { duration: 0.3, ease: EASE.smooth } },
};

// ---------------------------------------------------------------------------
// Instant (for replay mode — skip all animations)
// ---------------------------------------------------------------------------

export const instantVariants: Variants = {
  hidden: { opacity: 1 },
  visible: { opacity: 1 },
};

/**
 * Pick the correct variants based on replay state.
 * Usage: <motion.div variants={pickVariants(isReplay, fadeInUp)} />
 */
export function pickVariants(isReplay: boolean, liveVariants: Variants): Variants {
  return isReplay ? instantVariants : liveVariants;
}
