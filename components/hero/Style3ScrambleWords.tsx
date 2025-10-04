import React, { useEffect, useMemo, useState } from 'react';

interface Props {
  words?: string[];
  gradient?: boolean;
  variant?: 'card' | 'inline';
  className?: string;
  size?: 'md' | 'lg' | 'xl';
}

function useScramble(target: string, duration = 700) {
  const [text, setText] = useState(target);
  const [done, setDone] = useState(false);
  const letters = useMemo(() => 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'.split(''), []);

  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const step = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const reveal = Math.floor(p * target.length);
      const scrambled = target
        .split('')
        .map((ch, i) => (i < reveal ? ch : letters[Math.floor(Math.random() * letters.length)]))
        .join('');
      setText(scrambled);
      if (p < 1) {
        raf = requestAnimationFrame(step);
      } else {
        setDone(true);
      }
    };
    setDone(false);
    setText(target);
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, letters]);

  return { text, done } as const;
}

const DEFAULT_KEYS = ['Agents', 'Experiments', 'Forecasts', 'Activation'];

export default function Style3ScrambleWords({ words = DEFAULT_KEYS, gradient = false, variant = 'card', className, size = 'md' }: Props) {
  const [index, setIndex] = useState(0);
  const { text, done } = useScramble(words[index]);

  useEffect(() => {
    if (!done) return;
    const id = setTimeout(() => setIndex((i) => (i + 1) % words.length), 1400);
    return () => clearTimeout(id);
  }, [done, words.length]);

  const sizeClass = size === 'xl' ? 'text-5xl sm:text-6xl md:text-7xl' : size === 'lg' ? 'text-4xl sm:text-5xl' : 'text-3xl sm:text-4xl';

  const content = (
    <div
      className={`font-extrabold tracking-tight ${sizeClass} ${className ?? ''}`}
      aria-live="polite"
      style={{
        ...(gradient
          ? {
              backgroundImage:
                'linear-gradient(90deg, #7dd3fc 0%, #c084fc 35%, #f472b6 65%, #7dd3fc 100%)',
              WebkitBackgroundClip: 'text',
              backgroundClip: 'text',
              color: 'transparent',
              backgroundSize: '200% 100%',
              animation: 'yg-shimmer 10s ease-in-out infinite',
            }
          : { color: '#ffffff' }),
      }}
    >
      {text}
    </div>
  );

  if (variant === 'inline') {
    return content;
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-6">
      <div className="mb-3 text-[11px] uppercase tracking-wide text-slate-400">Style 3 — Decode/Scramble Reveal</div>
      {content}
      <style>{`
        @media (prefers-reduced-motion: reduce) {
          .rounded-2xl div[aria-live] { transition: opacity .3s ease; }
        }
        @media (prefers-reduced-motion: no-preference) {
          @keyframes yg-shimmer { 0% { background-position: 0% 50% } 50% { background-position: 100% 50% } 100% { background-position: 0% 50% } }
        }
      `}</style>
    </div>
  );
}
