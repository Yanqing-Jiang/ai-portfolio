import React, { useCallback, useMemo, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

const WORDS = ['Agents', 'Experiments', 'Forecasts', 'Activation', 'Automation'];

export default function Style4MagneticCloud() {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement | null>(null);
  const [mouse, setMouse] = useState<{ x: number; y: number } | null>(null);

  const base = useMemo(() => {
    const r = 80;
    return WORDS.map((_, i) => {
      const a = (i / WORDS.length) * Math.PI * 2;
      return { x: Math.cos(a) * r, y: Math.sin(a) * r };
    });
  }, []);

  const onMove = useCallback((e: React.MouseEvent) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const x = e.clientX - (rect.left + rect.width / 2);
    const y = e.clientY - (rect.top + rect.height / 2);
    setMouse({ x, y });
  }, []);

  const onLeave = useCallback(() => setMouse(null), []);

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-6">
      <div className="mb-3 text-[11px] uppercase tracking-wide text-slate-400">Style 4 — Magnetic Keyword Cloud</div>
      <div
        ref={ref}
        className="relative mx-auto flex h-56 w-full max-w-xl items-center justify-center overflow-hidden"
        onMouseMove={onMove}
        onMouseLeave={onLeave}
      >
        {WORDS.map((w, i) => {
          const b = base[i];
          let dx = 0, dy = 0, rot = 0;
          if (mouse && !reduce) {
            const vx = mouse.x - b.x;
            const vy = mouse.y - b.y;
            const d = Math.max(24, Math.hypot(vx, vy));
            const strength = 120 / d;
            dx = vx * 0.08 * strength;
            dy = vy * 0.08 * strength;
            rot = (vx + vy) * 0.02;
          }
          return (
            <motion.div
              key={w}
              initial={false}
              animate={{ x: b.x + dx, y: b.y + dy, rotate: rot }}
              transition={{ type: 'spring', stiffness: 260, damping: 20 }}
              className="absolute select-none rounded-full border border-white/10 bg-slate-800/70 px-3 py-1 text-xs text-slate-200 shadow-[0_8px_20px_rgba(2,132,199,0.18)] hover:border-sky-400/50 hover:text-white"
              style={{ willChange: reduce ? undefined : 'transform' }}
            >
              {w}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

