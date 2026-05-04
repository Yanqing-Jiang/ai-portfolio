import React from 'react';
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
    body: [
      'I loaded a stack of skills.md files, one per imagined use case. Then I instrumented invocation. Most never fired. The harness was carrying weight that returned nothing.',
      'I let the system self-prune. Today there are 10+ skills. Every one fires at least twice a week. The meta-harness watches usage and flags candidates for deletion before I notice them.',
    ],
    principle:
      'A system that lets you add features is worthless without a system that tells you which features to delete. I built the second one. That’s what kept Homer maintainable past month three.',
  },
];

export const Lessons: React.FC = () => (
  <SectionShell
    id="lessons"
    eyebrow="Lessons"
    title="Three things I learned the hard way."
    subtitle="Each one closes on a principle that transfers — not a war story."
  >
    <div className="space-y-16 md:space-y-24">
      {LESSONS.map((l) => (
        <article key={l.n} className="grid md:grid-cols-[80px_1fr] gap-4 md:gap-10 items-start">
          <div
            className="text-2xl md:text-3xl"
            style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.accent }}
          >
            {l.n}
          </div>
          <div>
            <div
              className="text-[11px] tracking-[0.32em] uppercase mb-3"
              style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
            >
              {l.eyebrow}
            </div>
            <h3
              className="text-2xl md:text-3xl leading-tight mb-5"
              style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
            >
              {l.hook}
            </h3>
            <div className="space-y-4 text-base md:text-lg leading-[1.7]" style={{ color: HOMER_THEME.textMuted }}>
              {l.body.map((p, i) => (
                <p key={i}>{p}</p>
              ))}
            </div>
            <blockquote
              className="mt-6 pl-5 border-l-2 text-base md:text-lg leading-snug italic"
              style={{
                borderColor: HOMER_THEME.accent,
                color: HOMER_THEME.text,
                fontFamily: HOMER_THEME.fontSerif,
              }}
            >
              &ldquo;{l.principle}&rdquo;
            </blockquote>
          </div>
        </article>
      ))}
    </div>
  </SectionShell>
);

export default Lessons;
