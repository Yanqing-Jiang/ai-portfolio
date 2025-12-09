/**
 * Function: styles — Shared style constants for Conversational Analytics UI
 * Called from: All conversational analytics components
 * Purpose: Maintains consistent design tokens across the chat interface
 */

export const theme = {
  // Rich midnight blue base
  colors: {
    // Background layers
    bg: {
      primary: '#0a0f1a',      // Deep midnight
      secondary: '#111827',    // Slightly lighter
      tertiary: '#1a2332',     // Card backgrounds
      elevated: '#1e293b',     // Elevated surfaces
    },
    // Accent - warm amber/gold for contrast
    accent: {
      primary: '#f59e0b',      // Amber
      secondary: '#fbbf24',    // Lighter amber
      muted: 'rgba(245, 158, 11, 0.15)',
    },
    // Text colors
    text: {
      primary: '#f8fafc',
      secondary: '#94a3b8',
      muted: '#64748b',
      accent: '#fbbf24',
    },
    // Borders
    border: {
      subtle: 'rgba(148, 163, 184, 0.1)',
      medium: 'rgba(148, 163, 184, 0.2)',
      strong: 'rgba(148, 163, 184, 0.3)',
    },
    // Status colors
    status: {
      success: '#10b981',
      warning: '#f59e0b',
      error: '#ef4444',
      info: '#3b82f6',
    },
    // Thinking/processing
    thinking: {
      bg: 'rgba(245, 158, 11, 0.08)',
      border: 'rgba(245, 158, 11, 0.25)',
      text: '#fbbf24',
      dot: '#f59e0b',
    },
    // User message
    user: {
      bg: 'linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)',
      text: '#ffffff',
    },
  },
  // Shadows
  shadows: {
    sm: '0 1px 2px rgba(0, 0, 0, 0.3)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -2px rgba(0, 0, 0, 0.2)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -4px rgba(0, 0, 0, 0.3)',
    glow: '0 0 20px rgba(245, 158, 11, 0.15)',
  },
  // Border radius
  radius: {
    sm: '6px',
    md: '12px',
    lg: '16px',
    xl: '24px',
    full: '9999px',
  },
  // Transitions
  transition: {
    fast: '150ms ease-out',
    normal: '250ms ease-out',
    slow: '400ms ease-out',
    spring: { type: 'spring', stiffness: 300, damping: 30 },
  },
} as const;

// Animation variants for Framer Motion
export const motionVariants = {
  // Fade in from below
  fadeInUp: {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -10 },
  },
  // Scale in
  scaleIn: {
    initial: { opacity: 0, scale: 0.95 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.95 },
  },
  // Slide in from right
  slideInRight: {
    initial: { opacity: 0, x: 20 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: 20 },
  },
  // Container stagger
  staggerContainer: {
    animate: {
      transition: {
        staggerChildren: 0.05,
      },
    },
  },
  // Modal backdrop
  backdrop: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
  // Modal content
  modal: {
    initial: { opacity: 0, scale: 0.9, y: 20 },
    animate: { 
      opacity: 1, 
      scale: 1, 
      y: 0,
      transition: { type: 'spring', stiffness: 300, damping: 30 }
    },
    exit: { opacity: 0, scale: 0.9, y: 20 },
  },
  // Thinking dots
  thinkingDot: {
    animate: {
      y: [0, -6, 0],
      transition: {
        duration: 0.6,
        repeat: Infinity,
        ease: 'easeInOut',
      },
    },
  },
} as const;

