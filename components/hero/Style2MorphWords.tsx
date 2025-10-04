import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';

interface Props {
  words?: string[];
  gradient?: boolean;
  variant?: 'card' | 'inline';
  className?: string;
  size?: 'md' | 'lg' | 'xl' | 'xxl';
  intervalMs?: number;
}

const DEFAULT_WORDS = ['Agents', 'Experiments', 'Forecasts', 'Actions'];

export default function Style2MorphWords({ words = DEFAULT_WORDS, gradient = false, variant = 'card', className, size = 'md', intervalMs = 2200 }: Props) {
  const [index, setIndex] = useState(0);
  const reduce = useReducedMotion();

  useEffect(() => {
    const id = setInterval(() => setIndex((i) => (i + 1) % words.length), intervalMs);
    return () => clearInterval(id);
  }, [words.length, intervalMs]);

  const sizeClass =
    size === 'xxl'
      ? 'text-6xl sm:text-7xl md:text-8xl'
      : size === 'xl'
      ? 'text-5xl sm:text-6xl md:text-7xl'
      : size === 'lg'
      ? 'text-4xl sm:text-5xl'
      : 'text-3xl sm:text-4xl';

  const inlineHeight =
    size === 'xxl'
      ? 'h-24 sm:h-28 md:h-32'
      : size === 'xl'
      ? 'h-20 sm:h-24 md:h-28'
      : size === 'lg'
      ? 'h-16 sm:h-20 md:h-24'
      : 'h-14 sm:h-16 md:h-18';
  const content = (
    <div className={`relative select-none ${variant === 'inline' ? inlineHeight : 'h-14 sm:h-16'} ${className ?? ''}`}>
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={index}
          className={`absolute inset-0 flex items-center font-extrabold tracking-tight ${sizeClass} text-balance`}
          initial={{ opacity: 0, y: reduce ? 0 : 6, letterSpacing: reduce ? '0em' : '0.02em' }}
          animate={{ opacity: 1, y: 0, letterSpacing: '0em' }}
          exit={{ opacity: 0, y: reduce ? 0 : -6, letterSpacing: reduce ? '0em' : '-0.01em' }}
          transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
          style={{
            fontVariationSettings: `'wght' ${reduce ? 700 : 800}, 'wdth' ${reduce ? 100 : 110}`,
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
          {words[index]}
        </motion.span>
      </AnimatePresence>
    </div>
  );

  if (variant === 'inline') return content;

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-6">
      <div className="mb-3 text-[11px] uppercase tracking-wide text-slate-400">Style 2 — Morphing Keywords</div>
      {content}
      <style>{`
        @media (prefers-reduced-motion: reduce) {
          .font-extrabold { animation: none !important; }
        }
        @media (prefers-reduced-motion: no-preference) {
          @keyframes yg-shimmer { 0% { background-position: 0% 50% } 50% { background-position: 100% 50% } 100% { background-position: 0% 50% } }
        }
      `}</style>
    </div>
  );
}
