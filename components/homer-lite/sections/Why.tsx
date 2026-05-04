import React from 'react';
import SectionShell from '../SectionShell';
import RollingNumber from '../RollingNumber';
import { HOMER_THEME } from '../theme';

// Function: Why — short framing of what Homer is.
// Closer line is a RollingNumber that climbs 3 → 5 each time the section
// enters the viewport, and resets to 3 when scrolled away. No background
// cycling — the animation is purely scroll-triggered, so the page reads as
// purposeful rather than busy.

export const Why: React.FC = () => {
  return (
    <SectionShell id="why" eyebrow="Why" title="Most agent demos die in the demo.">
      <div
        className="space-y-6 text-lg md:text-xl leading-[1.7]"
        style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
      >
        <p>
          Most agent prototypes work for thirty seconds in a screen recording and
          then never run again. They have no memory, no schedule, no recovery, no
          observability — and definitely no off-switch you&rsquo;d trust.
        </p>
        <p>
          Homer is the opposite. It&rsquo;s a system I actually use every day:
          durable memory, multi-CLI orchestration, a scheduler that survives
          sleep/wake, MCP tools shared across agents, a phone number, a
          notification layer, and a meta-harness that prunes its own dead skills.
        </p>
      </div>

      {/* Live rolling-number callout — the static "Six months in production"
          line is now a live odometer that climbs to the actual value, then
          cycles 4-6 quietly so the page never reads as static. */}
      <div
        className="mt-12 md:mt-16 pt-10 md:pt-12 border-t flex flex-col md:flex-row items-baseline gap-4 md:gap-8"
        style={{ borderColor: HOMER_THEME.divider }}
      >
        <div className="flex items-baseline gap-3 md:gap-4">
          <RollingNumber
            start={3}
            target={5}
            digitHeight={92}
            className="text-[88px] md:text-[120px] font-medium tracking-tight"
          />
          <div className="flex flex-col leading-tight">
            <span
              className="text-xl md:text-3xl"
              style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
            >
              months
            </span>
            <span
              className="text-[10px] tracking-[0.32em] uppercase mt-1.5"
              style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
            >
              in production
            </span>
          </div>
        </div>
        <p
          className="md:ml-auto md:max-w-sm text-sm md:text-base leading-relaxed"
          style={{ color: HOMER_THEME.textMuted }}
        >
          Still running while you read this. The counter above re-rolls every
          time you scroll back into the section — zero pre-rendered frames,
          fired entirely from the viewport intersection.
        </p>
      </div>
    </SectionShell>
  );
};

export default Why;
