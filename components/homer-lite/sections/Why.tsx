import React, { useRef } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

// Why — five Before/After couplets demonstrating why Homer exists.
//
// On each row, BEFORE is muted and a yellow highlighter underline draws
// left→right under the key phrase as the row scrolls into view; AFTER fades
// up beneath it with a soft gold glow bloom (background flash + box-shadow)
// that decays back to transparent. Both retrigger on scroll-back (useInView
// is not pinned with `once: true`).
//
// The underline replaces the prior full-width strikethrough — instead of
// crossing out the whole line, it marks just the phrase that matters
// (`highlight`), reading as emphasis rather than deletion.
//
// Copy is the user's voice; sequence is deliberate — bookmarks and voice
// lead because they're the most concrete to a recruiter / founder skimming
// on a phone. Memory, phone, and skills follow.
//
// Replaces the prior "Most agent demos die in the demo" + RollingNumber
// section. RollingNumber and the eyebrow subtitle are intentionally gone;
// the closing italic "I'm asleep. Homer isn't." carries the close instead.

// Highlighter yellow for the underline marker — distinct from the page's
// gold accent so it reads as a deliberate "marker" emphasis.
const HIGHLIGHT_YELLOW = '#ffd84d';

interface Pair {
  before: string;
  // Substring of `before` to underline. Must appear verbatim in `before`.
  highlight: string;
  after: string;
}

const PAIRS: ReadonlyArray<Pair> = [
  {
    before: 'My X bookmarks were where articles remained unread.',
    highlight: 'My X bookmarks',
    after: "Homer hands me the insights, based on what I'd care about.",
  },
  {
    before: 'My best thinking got lost between the car and the laptop.',
    highlight: 'the car and the laptop',
    after: 'I talk. Homer transcribes, files, and keeps the nuance.',
  },
  {
    before: 'I copy & pasted my style prompts into every new chat window.',
    highlight: 'copy & pasted',
    after: 'It remembered my preferences. Applied them without mentioning.',
  },
  {
    before: "Critical alerts buried in an inbox I'd check tomorrow.",
    highlight: 'Critical alerts',
    after: 'Homer calls my phone and we talk it through.',
  },
  {
    before: 'Every new assistant needed me to re-teach how I work.',
    highlight: 're-teach how I work',
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
const PairRow: React.FC<Pair> = ({ before, highlight, after }) => {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { amount: 0.4 });
  const shouldReduceMotion = useReducedMotion();
  const t = shouldReduceMotion ? 0 : 1;

  // Split `before` around the highlight phrase so only that phrase carries
  // the underline. If the phrase isn't found, `pre` holds the whole string
  // and the underline span renders empty (harmless).
  const idx = before.indexOf(highlight);
  const pre = idx === -1 ? before : before.slice(0, idx);
  const mark = idx === -1 ? '' : highlight;
  const post = idx === -1 ? '' : before.slice(idx + highlight.length);

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
          className="text-base md:text-[1.05rem] leading-snug"
          style={{ color: HOMER_THEME.textMuted }}
        >
          {pre}
          {/* Highlighter underline — draws left→right on entry under just
              the key phrase. 3px yellow bar sitting on the text baseline,
              slightly rounded so it reads as a marker stroke rather than a
              border. Replaces the prior full-width gold strikethrough. */}
          <span className="relative inline">
            {mark}
            <motion.span
              aria-hidden
              className="absolute left-0 right-0 origin-left pointer-events-none"
              style={{
                bottom: -1,
                height: 3,
                borderRadius: 2,
                background: HIGHLIGHT_YELLOW,
              }}
              initial={{ scaleX: 0 }}
              animate={{ scaleX: inView ? 1 : 0 }}
              transition={{
                duration: 0.6 * t,
                delay: 0.1 * t,
                ease: [0.16, 1, 0.3, 1],
              }}
            />
          </span>
          {post}
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
