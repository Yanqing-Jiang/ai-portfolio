import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Play, RotateCcw, SkipForward, Terminal } from 'lucide-react';
import { useReducedMotion } from 'framer-motion';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

type CastTone = 'info' | 'ok' | 'work';

interface CastEvent {
  t: number;
  text: string;
  tone: CastTone;
}

const CAST_SCRIPT: ReadonlyArray<CastEvent> = [
  { t: 0, text: '[06:00:00] sched_tick :: morning-brief woke (job 01/48)', tone: 'work' },
  { t: 520, text: '[06:00:01] daemon :: mac_mini awake · production lock acquired', tone: 'ok' },
  { t: 1050, text: '[06:00:02] executors :: claude · codex · gemini · kimi · opencode ready', tone: 'ok' },
  { t: 1680, text: '[06:00:03] memory_context :: pulled overnight deltas + active commitments', tone: 'info' },
  { t: 2620, text: '[06:00:06] calendar.fetch :: today agenda + travel buffers loaded', tone: 'info' },
  { t: 3340, text: '[06:00:08] weather.fetch :: local forecast + commute risk fetched', tone: 'info' },
  { t: 4200, text: '[06:00:12] executor.claude :: drafting brief from memory + calendar + weather', tone: 'work' },
  { t: 5480, text: '[06:00:25] verifier.codex :: private names redacted · links checked', tone: 'info' },
  { t: 6560, text: '[06:00:34] telegram.relay :: delivered morning brief to Yanqing', tone: 'ok' },
  { t: 7640, text: '[06:10:00] sched_tick :: morning-reads woke (job 02/48)', tone: 'work' },
  { t: 8360, text: '[06:10:03] link_inbox :: classify youtube/medium/twitter/github/website', tone: 'info' },
  { t: 9320, text: '[06:10:11] executor.gemini :: clustered reading queue into five themes', tone: 'work' },
  { t: 10380, text: '[06:10:22] memory.suggest :: 3 candidate insights queued for review', tone: 'info' },
  { t: 11280, text: '[06:10:31] daemon :: morning routine done · next sched_tick in 48m', tone: 'ok' },
];

const CAST_DURATION_MS = 11_700;

const TONE_COLOR: Record<CastTone, string> = {
  info: HOMER_THEME.textMuted,
  ok: '#86efac',
  work: HOMER_THEME.accent,
};

const splitLine = (text: string) => {
  const match = text.match(/^(\[[^\]]+\])\s(.+)$/);
  if (!match) return { ts: '', body: text };
  return { ts: match[1], body: match[2] };
};

export const MorningRoutineCast: React.FC = () => {
  const frameRef = useRef<HTMLDivElement>(null);
  const timersRef = useRef<number[]>([]);
  const runRef = useRef(0);
  const startedRef = useRef(false);
  const shouldReduceMotion = useReducedMotion();
  const [visibleLines, setVisibleLines] = useState<CastEvent[]>([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [hasFinished, setHasFinished] = useState(false);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach((timer) => window.clearTimeout(timer));
    timersRef.current = [];
  }, []);

  const skipToEnd = useCallback(() => {
    runRef.current += 1;
    clearTimers();
    startedRef.current = true;
    setVisibleLines([...CAST_SCRIPT]);
    setIsPlaying(false);
    setHasFinished(true);
  }, [clearTimers]);

  const playFromStart = useCallback(() => {
    if (shouldReduceMotion) {
      skipToEnd();
      return;
    }

    runRef.current += 1;
    const runId = runRef.current;
    clearTimers();
    startedRef.current = true;
    setVisibleLines([]);
    setIsPlaying(true);
    setHasFinished(false);

    CAST_SCRIPT.forEach((event) => {
      const timer = window.setTimeout(() => {
        if (runRef.current !== runId) return;
        setVisibleLines((current) => [...current, event]);
      }, event.t);
      timersRef.current.push(timer);
    });

    const doneTimer = window.setTimeout(() => {
      if (runRef.current !== runId) return;
      setIsPlaying(false);
      setHasFinished(true);
    }, CAST_DURATION_MS);
    timersRef.current.push(doneTimer);
  }, [clearTimers, shouldReduceMotion, skipToEnd]);

  useEffect(() => {
    if (shouldReduceMotion) {
      skipToEnd();
      return;
    }

    const frame = frameRef.current;
    if (!frame) return;

    if (typeof IntersectionObserver === 'undefined') {
      playFromStart();
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !startedRef.current) playFromStart();
      },
      { threshold: 0.35 },
    );

    observer.observe(frame);
    return () => observer.disconnect();
  }, [playFromStart, shouldReduceMotion, skipToEnd]);

  useEffect(() => {
    return () => {
      runRef.current += 1;
      clearTimers();
    };
  }, [clearTimers]);

  return (
    <SectionShell
      id="morning-routine"
      eyebrow="60-SECOND ROUTINE"
      title="What an autonomous morning looks like."
      subtitle="A replayed capture of the production daemon's morning routine, sanitized for the portfolio view."
    >
      <div
        ref={frameRef}
        className="rounded-lg border overflow-hidden"
        style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bgSoft }}
      >
        <div
          className="flex flex-wrap items-center gap-2 px-4 py-2.5 border-b"
          style={{ borderColor: HOMER_THEME.divider, background: 'rgba(0,0,0,0.25)' }}
        >
          <Terminal size={13} style={{ color: HOMER_THEME.accent }} />
          <span
            className="text-[10px] tracking-[0.24em] uppercase"
            style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
          >
            production-daemon.cast
          </span>
          <span
            className="ml-auto text-[10px] uppercase tracking-[0.18em]"
            style={{ fontFamily: HOMER_THEME.fontMono, color: isPlaying ? HOMER_THEME.accent : HOMER_THEME.textMuted }}
          >
            {isPlaying ? 'playing' : hasFinished ? 'complete' : 'armed'}
          </span>
        </div>

        <div
          className="min-h-[330px] max-h-[430px] overflow-y-auto px-4 py-3"
          role="log"
          aria-live="polite"
          style={{
            fontFamily: HOMER_THEME.fontMono,
            background: '#08070a',
            scrollbarWidth: 'thin',
          }}
        >
          {visibleLines.length === 0 && (
            <div className="text-[11px] leading-[1.8]" style={{ color: HOMER_THEME.textMuted }}>
              [waiting for viewport]
            </div>
          )}
          {visibleLines.map((line, index) => {
            const { ts, body } = splitLine(line.text);
            return (
              <div key={`${line.t}-${index}`} className="text-[11px] md:text-xs leading-[1.8]">
                {ts && <span style={{ color: HOMER_THEME.textMuted, opacity: 0.58 }}>{ts}</span>}{' '}
                <span style={{ color: TONE_COLOR[line.tone] }}>{body}</span>
              </div>
            );
          })}
        </div>

        <div
          className="flex flex-col gap-3 px-4 py-3 border-t sm:flex-row sm:items-center sm:justify-between"
          style={{
            borderColor: HOMER_THEME.divider,
            color: HOMER_THEME.textMuted,
            fontFamily: HOMER_THEME.fontMono,
          }}
        >
          <div className="text-[10px] leading-relaxed">
            48 daily tasks · five executors · sanitized terminal capture
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={playFromStart}
              className="inline-flex min-h-[36px] items-center gap-2 rounded border px-3 py-2 text-[10px] uppercase tracking-[0.18em] transition-colors hover:bg-white/[0.03]"
              style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.text }}
            >
              {hasFinished ? <RotateCcw size={13} /> : <Play size={13} />}
              {hasFinished ? 'replay' : 'play'}
            </button>
            <button
              type="button"
              onClick={skipToEnd}
              className="inline-flex min-h-[36px] items-center gap-2 rounded border px-3 py-2 text-[10px] uppercase tracking-[0.18em] transition-colors hover:bg-white/[0.03]"
              style={{ borderColor: HOMER_THEME.divider, color: HOMER_THEME.textMuted }}
            >
              <SkipForward size={13} />
              skip
            </button>
          </div>
        </div>
      </div>
    </SectionShell>
  );
};

export default MorningRoutineCast;
