import React, { useRef } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

// Why — five Before/After couplets demonstrating why Homer exists.
//
// On each row, BEFORE is muted with a thin strikethrough that draws across as
// the row scrolls into view; AFTER fades up beneath it with a soft gold glow
// bloom (background flash + box-shadow) that decays back to transparent.
// Both retrigger on scroll-back (useInView is not pinned with `once: true`).
//
// Source of the animation pattern: Direction A (Strikethrough Reveal) from
// ~/homer/output/gemini/homer-why-v2-flash-2026-05-13/anim-demo.html.
// Copy is the user's voice; sequence is deliberate — bookmarks and voice
// lead because they're the most concrete to a recruiter / founder skimming
// on a phone. Memory, phone, and skills follow.
//
// Replaces the prior "Most agent demos die in the demo" + RollingNumber
// section. RollingNumber and the eyebrow subtitle are intentionally gone;
// the closing italic "I'm asleep. Homer isn't." carries the close instead.

interface Pair {
  before: string;
  after: string;
}

const PAIRS: ReadonlyArray<Pair> = [
  {
    before: 'My X bookmarks were where articles remained unread.',
    after: "Homer hands me the insights, based on what I'd care about.",
  },
  {
    before: 'My best thinking got lost between the car and the laptop.',
    after: 'I talk. Homer transcribes, files, and keeps the nuance.',
  },
  {
    before: 'I copy & pasted my style prompts into every new chat window.',
    after: 'It remembered my preferences. Applied them without mentioning.',
  },
  {
    before: "Critical alerts buried in an inbox I'd check tomorrow.",
    after: 'Homer calls my phone and we talk it through.',
  },
  {
    before: 'Every new assistant needed me to re-teach how I work.',
    after: 'Homer learned once. Every CLI I use now knows the way.',
  },
];

// Per-row animation component.
// - useInView is per-row (not for the whole section) so each row triggers
//   independently as the reader scrolls through.
// - amount: 0.4 — fires when ~40% of the row is in view, matching the prior
//   anim-demo prototype.
// - shouldReduceMotion collapses every timing to 0 and skips the bloom
//   keyframes, so reduced-motion users see the final state instantly.
const PairRow: React.FC<Pair> = ({ before, after }) => {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { amount: 0.4 });
  const shouldReduceMotion = useReducedMotion();
  const t = shouldReduceMotion ? 0 : 1;

  return (
    <div
      ref={ref}
      className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-10 py-7 border-b"
      style={{ borderColor: HOMER_THEME.divider }}
    >
      {/* BEFORE column */}
      <div>
        <span
          className="block text-[10px] uppercase tracking-[0.12em] mb-2"
          style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
        >
          Before
        </span>
        <p
          className="relative inline text-base md:text-[1.05rem] leading-snug"
          style={{ color: HOMER_THEME.textMuted }}
        >
          {before}
          {/* Strikethrough — draws left→right on entry. For wrapped text it
              draws through the bounding-box mid-line, matching the demo's
              behavior. */}
          <motion.span
            aria-hidden
            className="absolute left-0 right-0 origin-left pointer-events-none"
            style={{
              top: '50%',
              height: 1,
              background: HOMER_THEME.textMuted,
              opacity: 0.85,
            }}
            initial={{ scaleX: 0 }}
            animate={{ scaleX: inView ? 1 : 0 }}
            transition={{
              duration: 0.6 * t,
              delay: 0.1 * t,
              ease: [0.16, 1, 0.3, 1],
            }}
          />
        </p>
      </div>

      {/* AFTER column — fade up, then glow-bloom on the text itself */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: inView ? 1 : 0, y: inView ? 0 : 8 }}
        transition={{ duration: 0.5 * t, delay: inView ? 0.5 * t : 0 }}
      >
        <span
          className="block text-[10px] uppercase tracking-[0.12em] mb-2"
          style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
        >
          After
        </span>
        <motion.span
          className="text-base md:text-[1.05rem] leading-snug font-medium"
          style={{
            color: HOMER_THEME.text,
            display: 'inline-block',
            padding: '0 4px',
            margin: '0 -4px',
            borderRadius: 4,
          }}
          initial={{ backgroundColor: 'rgba(0,0,0,0)', boxShadow: '0 0 0 0 rgba(0,0,0,0)' }}
          animate={
            inView && !shouldReduceMotion
              ? {
                  backgroundColor: [
                    HOMER_THEME.accentSoft,
                    HOMER_THEME.accentSoft,
                    'rgba(0,0,0,0)',
                  ],
                  boxShadow: [
                    '0 0 0 0 rgba(0,0,0,0)',
                    `0 0 22px 0 ${HOMER_THEME.accentGlow}`,
                    '0 0 0 0 rgba(0,0,0,0)',
                  ],
                }
              : {
                  backgroundColor: 'rgba(0,0,0,0)',
                  boxShadow: '0 0 0 0 rgba(0,0,0,0)',
                }
          }
          transition={{
            duration: 0.9 * t,
            delay: inView ? 0.7 * t : 0,
            times: [0, 0.4, 1],
          }}
        >
          {after}
        </motion.span>
      </motion.div>
    </div>
  );
};

export const Why: React.FC = () => {
  return (
    <SectionShell
      id="why"
      eyebrow="Why"
      title="There are 1000s of AI Agents out there. This one works for ME."
    >
      <div className="border-t" style={{ borderColor: HOMER_THEME.divider }}>
        {PAIRS.map((p, i) => (
          <PairRow key={i} {...p} />
        ))}
      </div>

      <p
        className="italic mt-12 md:mt-16 leading-tight"
        style={{
          fontFamily: HOMER_THEME.fontSerif,
          color: HOMER_THEME.accent,
          fontSize: 'clamp(1.75rem, 5vw, 2.5rem)',
        }}
      >
        I&rsquo;m asleep. Homer isn&rsquo;t.
      </p>
    </SectionShell>
  );
};

export default Why;
