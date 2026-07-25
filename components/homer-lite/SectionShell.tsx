import React, { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { HOMER_THEME } from './theme';

// Function: SectionShell — wraps every Homer Lite section with a consistent
// IntersectionObserver-based fade-up reveal + max-width container. Called from
// Hero / Why / Architecture / TryHomer / MemorySearchDemo / MemoryLifecycleDemo
// / MorningRoutineCast / Lessons / Roadmap / CTA. Exists so individual section
// files stay content-only and inherit the page's scroll choreography.
//
// `eyebrow` renders as a small monospace label above the title — matches the
// editorial-essay framing locked in the plan ("Director-voice essay, not engineer
// demo"). Pass `noPad` for full-bleed sections like Hero or video.

interface SectionShellProps {
  id: string;
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  noPad?: boolean;
}

export const SectionShell: React.FC<SectionShellProps> = ({
  id,
  eyebrow,
  title,
  subtitle,
  children,
  className = '',
  noPad = false,
}) => {
  const ref = useRef<HTMLElement>(null);
  // amount: 0.15 — fire when ~15% of the section is in viewport. Matches LandingPageFlow's
  // scroll feel without requiring GSAP ScrollTrigger plumbing.
  const inView = useInView(ref, { once: true, amount: 0.15 });

  return (
    <section
      ref={ref}
      id={id}
      data-homer-section={id}
      className={`relative ${noPad ? '' : 'py-16 md:py-24 lg:py-32 px-4 md:px-12'} ${className}`}
    >
      <motion.div
        initial={{ opacity: 0, y: 32 }}
        animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y: 32 }}
        transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        className="relative max-w-5xl mx-auto"
      >
        {(eyebrow || title || subtitle) && (
          <header className="mb-10 md:mb-14">
            {eyebrow && (
              <div
                className="text-[11px] tracking-[0.32em] uppercase mb-5"
                style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
              >
                {eyebrow}
              </div>
            )}
            {title && (
              <h2
                className="text-3xl md:text-5xl leading-[1.1] tracking-tight font-medium"
                style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
              >
                {title}
              </h2>
            )}
            {subtitle && (
              <p
                className="mt-5 text-base md:text-lg max-w-3xl leading-relaxed"
                style={{ color: HOMER_THEME.textMuted }}
              >
                {subtitle}
              </p>
            )}
          </header>
        )}
        {children}
      </motion.div>
    </section>
  );
};

export default SectionShell;
