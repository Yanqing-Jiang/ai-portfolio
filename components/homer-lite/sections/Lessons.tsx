import React, { useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

// Function: Lessons — Plan §7.0.
// 3 user-authored Director-voice vignettes:
//   1. Memory system evolution
//   2. Voice agent iteration
//   3. Skills.md self-evolve
// Each vignette MUST close on a transferable principle — that closing line is
// the recruiter signal. Sprint 1 ships the locked text and section structure;
// Sprint 3 will add per-lesson visual assets (evolution arrows, side-by-side,
// bar chart) into the right-hand column.

const LESSONS = [
  {
    n: '01',
    eyebrow: 'Memory system evolution',
    hook: 'Agent memory retrieval is never an easy task.',
    context: 'The memory layer only became reliable after multiple production retrieval failures.',
    body: [
      'I started from OpenClaw. Studied mainstream Hermes-style architectures. Borrowed the best primitives from each, then built Homer’s own hybrid: structured claims + FTS5 + vector, scored together, with markdown as the durable human-readable surface.',
      'Multiple CLI sessions write into the same memory layer concurrently. Conflict guard sits in the promotion path. I rewrote the retrieval scorer three times before the recall numbers stopped lying to me.',
    ],
    principle:
      'You don’t pick a memory architecture — you evolve into one. The right shape only reveals itself once you’ve been wrong three times in production.',
  },
  {
    n: '02',
    eyebrow: 'Voice agent iteration',
    hook: 'I tested several voice agent stacks. None were close.',
    context: 'The useful lesson was where custom infrastructure stopped paying rent.',
    body: [
      'Custom STT+TTS pipeline. Then LiveKit. Then a hybrid orchestrator. Each one was technically interesting and operationally fragile.',
      'I shipped ElevenLabs Managed Agent in a day. Calls work. The pipeline I would have built would have cost a quarter, broken weekly, and not done anything the managed platform doesn’t already do.',
    ],
    principle:
      'Director-level engineering isn’t about building the most. It’s about knowing when a managed platform beats your custom stack — and having the ego to admit it.',
  },
  {
    n: '03',
    eyebrow: 'Skills.md overload',
    hook: 'I started with 40 skills. Most were dead weight.',
    context: 'Instrumentation turned a growing harness into a maintainable one.',
    body: [
      'I loaded a stack of skills.md files, one per imagined use case. Then I instrumented invocation. Most never fired. The harness was carrying weight that returned nothing.',
      'I let the system self-prune. Today there are 10+ skills. Every one fires at least twice a week. The meta-harness watches usage and flags candidates for deletion before I notice them.',
    ],
    principle:
      'A system that lets you add features is worthless without a system that tells you which features to delete. I built the second one. That’s what kept Homer maintainable past month three.',
  },
];

type Lesson = (typeof LESSONS)[number];

const LessonCard: React.FC<{ lesson: Lesson; open: boolean; onToggle: () => void }> = ({
  lesson,
  open,
  onToggle,
}) => {
  const shouldReduceMotion = useReducedMotion();
  const t = shouldReduceMotion ? 0 : 1;
  const panelId = `lesson-panel-${lesson.n}`;

  return (
    <article
      className="rounded-lg border overflow-hidden"
      style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bgSoft }}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="w-full min-h-[44px] text-left p-5 md:p-7"
      >
        <div
          className="text-[10px] tracking-[0.28em] uppercase mb-5"
          style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
        >
          {lesson.n} · {lesson.eyebrow}
        </div>
        <blockquote
          className="text-xl md:text-3xl leading-tight italic"
          style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
        >
          &ldquo;{lesson.principle}&rdquo;
        </blockquote>
        <div className="mt-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <p className="text-sm md:text-base leading-relaxed max-w-2xl" style={{ color: HOMER_THEME.textMuted }}>
            {lesson.context}
          </p>
          <span
            className="text-[10px] uppercase tracking-[0.24em] shrink-0"
            style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
          >
            {open ? 'collapse' : 'expand'}
          </span>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={panelId}
            key="panel"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28 * t, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div
              className="px-5 md:px-7 pb-6 md:pb-8 pt-1 border-t space-y-4 text-base md:text-lg leading-[1.7]"
              style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted }}
            >
              <h3
                className="text-2xl md:text-3xl leading-tight"
                style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
              >
                {lesson.hook}
              </h3>
              {lesson.body.map((p, i) => (
                <p key={i}>{p}</p>
              ))}
              <blockquote
                className="pl-5 border-l-2 text-base md:text-lg leading-snug italic"
                style={{
                  borderColor: HOMER_THEME.accent,
                  color: HOMER_THEME.text,
                  fontFamily: HOMER_THEME.fontSerif,
                }}
              >
                &ldquo;{lesson.principle}&rdquo;
              </blockquote>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </article>
  );
};

export const Lessons: React.FC = () => {
  const [openLesson, setOpenLesson] = useState<string | null>(null);

  return (
    <SectionShell
      id="lessons"
      eyebrow="Lessons"
      title="Three things I learned the hard way."
      subtitle="Each one closes on a principle that transfers — not a war story."
    >
      <div className="space-y-5">
        {LESSONS.map((lesson) => (
          <LessonCard
            key={lesson.n}
            lesson={lesson}
            open={openLesson === lesson.n}
            onToggle={() => setOpenLesson((current) => (current === lesson.n ? null : lesson.n))}
          />
        ))}
      </div>
    </SectionShell>
  );
};

export default Lessons;
