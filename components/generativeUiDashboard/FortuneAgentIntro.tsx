import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from 'react';
import {
  AnimatePresence,
  motion,
  useReducedMotion,
  type Variants,
} from 'framer-motion';

export interface FortuneAgentIntroProps {
  onFinish?: () => void;
  onSkip?: () => void;
  beats?: string[];
  autoAdvanceMs?: number;
}

const DEFAULT_BEATS: string[] = [
  'My Mom was obsessed with fortune telling.',
  'She spent a fortune on fortune tellers — and never got anything meaningful back.',
  'I happen to be tinkering with Agent Harnessing.',
  'So I gave an LLM ten classical Chinese fortune books, and let it learn the mechanism, book by book.',
  "This is what I built for her. You're welcome to ask.",
];

// One quiet glyph per beat. Meaning only — not decoration.
const BEAT_GLYPHS: string[] = ['母', '算', '學', '書', '緣'];

const SERIF_STACK =
  "Georgia, 'Noto Serif SC', 'Songti SC', 'Songti TC', 'Times New Roman', serif";

const ACCENT = 'var(--ming-accent, #b91c1c)';
const GOLD = 'var(--ming-gold, #eab308)';
const BG = 'var(--ming-bg, #0a0910)';

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
  exit: { opacity: 0, transition: { duration: 0.35, ease: 'easeOut' } },
};

const wordVariants: Variants = {
  hidden: { opacity: 0, y: 8, filter: 'blur(4px)' },
  visible: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] },
  },
};

export function FortuneAgentIntro({
  onFinish = () => console.log('[FortuneAgentIntro] onFinish'),
  onSkip = () => console.log('[FortuneAgentIntro] onSkip'),
  beats,
  autoAdvanceMs = 6500,
}: FortuneAgentIntroProps) {
  const prefersReducedMotion = useReducedMotion();
  const effectiveBeats = useMemo(
    () => (beats && beats.length > 0 ? beats : DEFAULT_BEATS),
    [beats],
  );
  const totalBeats = effectiveBeats.length;
  const lastIndex = totalBeats - 1;

  const [index, setIndex] = useState(0);
  const [progress, setProgress] = useState(0); // 0..1 for current beat
  const [paused, setPaused] = useState(false);
  const [finishedLast, setFinishedLast] = useState(false);

  // React 19 strict: useRef<T>(null!) for refs we write to.
  const rafRef = useRef<number>(null!);
  const startTsRef = useRef<number>(null!);
  const elapsedAtPauseRef = useRef<number>(0);
  const rootRef = useRef<HTMLDivElement>(null!);

  const currentGlyph =
    BEAT_GLYPHS[index] ?? BEAT_GLYPHS[BEAT_GLYPHS.length - 1];
  const isLast = index === lastIndex;

  // ---- RAF progress loop ----------------------------------------------------
  useEffect(() => {
    // Reset per-beat state
    setProgress(0);
    elapsedAtPauseRef.current = 0;
    startTsRef.current = null!;

    if (prefersReducedMotion) {
      // Skip the smooth fill; show full bar, auto-advance via timeout unless last.
      setProgress(1);
      if (!isLast) {
        const t = window.setTimeout(() => {
          setIndex((i) => Math.min(i + 1, lastIndex));
        }, autoAdvanceMs);
        return () => window.clearTimeout(t);
      }
      setFinishedLast(true);
      return;
    }

    const tick = (ts: number) => {
      if (paused) {
        // Freeze; reschedule so we keep RAF alive without advancing.
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      if (startTsRef.current == null) {
        startTsRef.current = ts - elapsedAtPauseRef.current;
      }
      const elapsed = ts - startTsRef.current;
      const p = Math.min(1, elapsed / autoAdvanceMs);
      setProgress(p);

      if (p >= 1) {
        if (isLast) {
          setFinishedLast(true);
          return; // stop here; wait for Begin.
        }
        setIndex((i) => Math.min(i + 1, lastIndex));
        return;
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, autoAdvanceMs, prefersReducedMotion, isLast, lastIndex]);

  // When paused toggles, stash elapsed so resume continues smoothly.
  useEffect(() => {
    if (prefersReducedMotion) return;
    if (paused) {
      elapsedAtPauseRef.current = progress * autoAdvanceMs;
      startTsRef.current = null!;
    } else {
      startTsRef.current = null!;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paused]);

  // ---- Navigation ----------------------------------------------------------
  const goPrev = useCallback(() => {
    setFinishedLast(false);
    setIndex((i) => Math.max(0, i - 1));
  }, []);

  const goNext = useCallback(() => {
    setIndex((i) => {
      if (i >= lastIndex) {
        setFinishedLast(true);
        return i;
      }
      return i + 1;
    });
  }, [lastIndex]);

  const togglePause = useCallback(() => {
    setPaused((p) => !p);
  }, []);

  const finish = useCallback(() => {
    onFinish();
  }, [onFinish]);

  // ---- Pointer: long-press anywhere to pause, release to resume ------------
  // Tap zones still work via click handlers; pointerdown sets paused.
  // Drag anywhere horizontally (mobile swipe or desktop click-drag) to navigate beats.
  const pointerDownRef = useRef<boolean>(false);
  const pointerDownTsRef = useRef<number>(0);
  const swipeStartRef = useRef<{ x: number; y: number; t: number }>({
    x: 0,
    y: 0,
    t: 0,
  });
  const LONG_PRESS_MS = 180;
  const SWIPE_THRESHOLD_PX = 50;
  const SWIPE_VELOCITY_THRESHOLD = 0.35; // px/ms

  const handlePointerDown = useCallback((e: PointerEvent<HTMLDivElement>) => {
    pointerDownRef.current = true;
    pointerDownTsRef.current = performance.now();
    swipeStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      t: performance.now(),
    };
    // Only pause on sustained press — small delay avoids flicker on quick taps.
    window.setTimeout(() => {
      if (pointerDownRef.current) {
        setPaused(true);
      }
    }, LONG_PRESS_MS);
  }, []);

  const handlePointerUp = useCallback(() => {
    pointerDownRef.current = false;
    setPaused(false);
  }, []);

  // Classify pointerup as swipe, tap, or neither. Swipe wins over tap/long-press.
  const classifyPointerUp = useCallback(
    (e: PointerEvent<HTMLButtonElement>): 'swipe-next' | 'swipe-prev' | 'tap' | 'ignore' => {
      const dx = e.clientX - swipeStartRef.current.x;
      const dy = e.clientY - swipeStartRef.current.y;
      const dt = performance.now() - swipeStartRef.current.t;
      const velocity = Math.abs(dx) / Math.max(dt, 1);
      const horizontalDominant = Math.abs(dx) > Math.abs(dy);
      if (
        horizontalDominant &&
        (Math.abs(dx) > SWIPE_THRESHOLD_PX || velocity > SWIPE_VELOCITY_THRESHOLD)
      ) {
        return dx < 0 ? 'swipe-next' : 'swipe-prev';
      }
      if (performance.now() - pointerDownTsRef.current < LONG_PRESS_MS) {
        return 'tap';
      }
      return 'ignore';
    },
    [],
  );

  // ---- Keyboard ------------------------------------------------------------
  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        goNext();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        goPrev();
      } else if (e.key === ' ') {
        e.preventDefault();
        togglePause();
      } else if (e.key === 'Enter' && isLast && finishedLast) {
        e.preventDefault();
        finish();
      }
    },
    [goNext, goPrev, togglePause, isLast, finishedLast, finish],
  );

  useEffect(() => {
    // Focus the root so keyboard works immediately.
    rootRef.current?.focus({ preventScroll: true });
  }, []);

  // ---- Tap zone handlers — swipe takes precedence over tap ----------------
  const handleLeftTap = useCallback(
    (e: PointerEvent<HTMLButtonElement>) => {
      const kind = classifyPointerUp(e);
      if (kind === 'swipe-next') { e.preventDefault(); goNext(); return; }
      if (kind === 'swipe-prev') { e.preventDefault(); goPrev(); return; }
      if (kind === 'tap') { e.preventDefault(); goPrev(); }
    },
    [classifyPointerUp, goPrev, goNext],
  );

  const handleRightTap = useCallback(
    (e: PointerEvent<HTMLButtonElement>) => {
      const kind = classifyPointerUp(e);
      if (kind === 'swipe-next') { e.preventDefault(); goNext(); return; }
      if (kind === 'swipe-prev') { e.preventDefault(); goPrev(); return; }
      if (kind === 'tap') { e.preventDefault(); goNext(); }
    },
    [classifyPointerUp, goNext, goPrev],
  );

  const handleCenterTap = useCallback(
    (e: PointerEvent<HTMLButtonElement>) => {
      const kind = classifyPointerUp(e);
      if (kind === 'swipe-next') { e.preventDefault(); goNext(); return; }
      if (kind === 'swipe-prev') { e.preventDefault(); goPrev(); return; }
      if (kind === 'tap') { e.preventDefault(); togglePause(); }
    },
    [classifyPointerUp, goNext, goPrev, togglePause],
  );

  // ---- Render --------------------------------------------------------------
  const currentText = effectiveBeats[index] ?? '';
  const words = currentText.split(' ');

  return (
    <div
      ref={rootRef}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      onPointerLeave={handlePointerUp}
      role="group"
      aria-label="Fortune agent introduction story"
      className="relative h-[100svh] w-full overflow-hidden select-none outline-none"
      style={{
        backgroundColor: BG,
        color: '#f6efe3',
        fontFamily: SERIF_STACK,
      }}
    >
      {/* Ambient ink-wash gradient */}
      {!prefersReducedMotion && (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          initial={{ opacity: 0.35 }}
          animate={{
            opacity: [0.28, 0.42, 0.3],
            backgroundPosition: ['0% 0%', '100% 50%', '0% 100%'],
          }}
          transition={{
            duration: 22,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          style={{
            background: `radial-gradient(60% 50% at 30% 20%, ${ACCENT}22 0%, transparent 60%), radial-gradient(55% 45% at 75% 80%, ${GOLD}1a 0%, transparent 65%), linear-gradient(180deg, #0a0910 0%, #120a18 50%, #0a0910 100%)`,
            backgroundSize: '200% 200%',
          }}
        />
      )}
      {prefersReducedMotion && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background: `radial-gradient(60% 50% at 30% 20%, ${ACCENT}18 0%, transparent 60%), linear-gradient(180deg, #0a0910 0%, #120a18 50%, #0a0910 100%)`,
          }}
        />
      )}

      {/* Progress bars */}
      <div
        className="absolute left-0 right-0 z-30 flex gap-1.5 px-4 pt-[calc(env(safe-area-inset-top)+10px)]"
        aria-hidden={false}
        aria-label="Story progress"
      >
        {effectiveBeats.map((_, i) => {
          const fill =
            i < index ? 1 : i === index ? (finishedLast && isLast ? 1 : progress) : 0;
          return (
            <div
              key={i}
              className="relative h-[3px] flex-1 overflow-hidden rounded-full"
              style={{ backgroundColor: 'rgba(246,239,227,0.18)' }}
            >
              <div
                className="absolute inset-y-0 left-0 rounded-full transition-[opacity] duration-200"
                style={{
                  width: `${Math.round(fill * 100)}%`,
                  backgroundColor: '#f6efe3',
                  opacity: paused ? 0.45 : 0.95,
                }}
              />
            </div>
          );
        })}
      </div>

      {/* Skip button */}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onSkip();
        }}
        className="absolute right-4 top-[calc(env(safe-area-inset-top)+22px)] z-40 rounded-full px-3 py-1.5 text-xs tracking-wide"
        style={{
          color: 'rgba(246,239,227,0.72)',
          border: '1px solid rgba(246,239,227,0.18)',
          backgroundColor: 'rgba(10,9,16,0.35)',
          backdropFilter: 'blur(6px)',
          WebkitBackdropFilter: 'blur(6px)',
          minHeight: 32,
        }}
        aria-label="Skip introduction"
      >
        Skip →
      </button>

      {/* Faint background glyph per beat */}
      <AnimatePresence mode="wait">
        <motion.div
          key={`glyph-${index}`}
          aria-hidden
          initial={{ opacity: 0, scale: 1.02 }}
          animate={{ opacity: 0.18, scale: 1 }}
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: prefersReducedMotion ? 0 : 1.1, ease: 'easeOut' }}
          className="pointer-events-none absolute left-1/2 top-[18%] z-10 -translate-x-1/2 select-none"
          style={{
            fontFamily: "'Noto Serif SC', 'Songti SC', serif",
            fontSize: 'clamp(180px, 46vw, 360px)',
            fontWeight: 500,
            color: '#f6efe3',
            lineHeight: 1,
            letterSpacing: '-0.04em',
            textShadow: `0 0 40px ${ACCENT}33`,
          }}
        >
          {currentGlyph}
        </motion.div>
      </AnimatePresence>

      {/* Tap zones (invisible, sized, accessible) */}
      <button
        type="button"
        aria-label="Previous beat"
        onPointerUp={handleLeftTap}
        className="absolute bottom-0 left-0 top-0 z-20 w-1/3 cursor-default bg-transparent"
        tabIndex={-1}
      />
      <button
        type="button"
        aria-label={paused ? 'Resume' : 'Pause'}
        onPointerUp={handleCenterTap}
        className="absolute bottom-0 left-1/3 top-0 z-20 w-1/3 cursor-default bg-transparent"
        tabIndex={-1}
      />
      <button
        type="button"
        aria-label="Next beat"
        onPointerUp={handleRightTap}
        className="absolute bottom-0 right-0 top-0 z-20 w-1/3 cursor-default bg-transparent"
        tabIndex={-1}
      />

      {/* Text block */}
      <div className="relative z-20 flex h-full w-full items-center justify-center px-6">
        <div className="w-full max-w-[560px]">
          <AnimatePresence mode="wait">
            <motion.p
              key={`beat-${index}`}
              variants={prefersReducedMotion ? undefined : containerVariants}
              initial={prefersReducedMotion ? { opacity: 0 } : 'hidden'}
              animate={prefersReducedMotion ? { opacity: 1 } : 'visible'}
              exit={prefersReducedMotion ? { opacity: 0 } : 'exit'}
              transition={
                prefersReducedMotion ? { duration: 0.25 } : undefined
              }
              className="text-center"
              style={{
                fontFamily: SERIF_STACK,
                fontSize: 'clamp(24px, 6.2vw, 34px)',
                lineHeight: 1.45,
                letterSpacing: '-0.005em',
                color: '#f6efe3',
                textWrap: 'balance',
              }}
            >
              {prefersReducedMotion
                ? currentText
                : words.map((word, wi) => (
                    <motion.span
                      key={`${index}-${wi}-${word}`}
                      variants={wordVariants}
                      className="inline-block"
                      style={{ marginRight: '0.32em' }}
                    >
                      {word}
                    </motion.span>
                  ))}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>

      {/* Begin CTA on last beat */}
      {isLast && (
        <div
          className="absolute inset-x-0 bottom-0 z-40 flex flex-col items-center gap-3 px-6 pb-[calc(env(safe-area-inset-bottom)+28px)] pt-6"
          style={{
            background:
              'linear-gradient(180deg, rgba(10,9,16,0) 0%, rgba(10,9,16,0.55) 55%, rgba(10,9,16,0.9) 100%)',
          }}
        >
          <motion.button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              finish();
            }}
            initial={{ opacity: 0, y: 10 }}
            animate={
              prefersReducedMotion
                ? { opacity: 1, y: 0 }
                : {
                    opacity: 1,
                    y: 0,
                    boxShadow: [
                      `0 0 0 0 ${GOLD}00`,
                      `0 0 22px 2px ${GOLD}55`,
                      `0 0 0 0 ${GOLD}00`,
                    ],
                  }
            }
            transition={
              prefersReducedMotion
                ? { duration: 0.4 }
                : {
                    opacity: { duration: 0.6 },
                    y: { duration: 0.6 },
                    boxShadow: {
                      duration: 3.2,
                      repeat: Infinity,
                      ease: 'easeInOut',
                    },
                  }
            }
            className="flex w-full flex-col items-center justify-center rounded-full"
            style={{
              minHeight: 60,
              padding: '10px 24px',
              maxWidth: 'min(520px, calc(100% - 0px))',
              background: `linear-gradient(180deg, ${GOLD} 0%, #c68f12 100%)`,
              color: '#1a1205',
              border: `1px solid ${GOLD}`,
              fontFamily: SERIF_STACK,
              fontWeight: 600,
              letterSpacing: '0.01em',
              cursor: 'pointer',
            }}
            aria-label="Begin — start the fortune agent"
          >
            <span style={{ fontSize: 20, lineHeight: 1.1 }}>Begin →</span>
            <span
              style={{
                fontFamily: "'Noto Serif SC', 'Songti SC', serif",
                fontSize: 12,
                opacity: 0.72,
                marginTop: 2,
                letterSpacing: '0.18em',
              }}
            >
              開始
            </span>
          </motion.button>
        </div>
      )}

      {/* Paused dim veil */}
      {paused && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 z-15"
          style={{ backgroundColor: 'rgba(10,9,16,0.18)' }}
        />
      )}

      {/* SR-only live announcement */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        style={{
          position: 'absolute',
          width: 1,
          height: 1,
          padding: 0,
          margin: -1,
          overflow: 'hidden',
          clip: 'rect(0,0,0,0)',
          whiteSpace: 'nowrap',
          border: 0,
        }}
      >
        {`Beat ${index + 1} of ${totalBeats}: ${currentText}${
          paused ? ' (paused)' : ''
        }`}
      </div>
    </div>
  );
}

export default FortuneAgentIntro;
