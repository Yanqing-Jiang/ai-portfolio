import React, { useCallback, useRef } from 'react';

export default function Style6SpotlightText() {
  const ref = useRef<HTMLDivElement | null>(null);

  const onMove = useCallback((e: React.MouseEvent) => {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const x = e.clientX - r.left; const y = e.clientY - r.top;
    ref.current.style.setProperty('--mx', `${x}px`);
    ref.current.style.setProperty('--my', `${y}px`);
  }, []);

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-6">
      <div className="mb-3 text-[11px] uppercase tracking-wide text-slate-400">Style 6 — Spotlight Typography</div>
      <div
        ref={ref}
        onMouseMove={onMove}
        className="relative isolate overflow-hidden rounded-xl border border-white/10 bg-slate-950 px-6 py-10"
        style={{ ['--mx' as any]: '50%', ['--my' as any]: '50%' }}
      >
        <h3 className="relative z-10 text-4xl sm:text-5xl font-extrabold tracking-tight text-white">
          Agentic Analytics
        </h3>
        <p className="relative z-10 mt-2 max-w-[65ch] text-slate-300">Move your cursor to reveal the glow.</p>
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'radial-gradient(160px 160px at var(--mx) var(--my), rgba(56,189,248,0.22), transparent 60%), radial-gradient(220px 220px at calc(var(--mx) + 80px) calc(var(--my) + 40px), rgba(192,132,252,0.18), transparent 60%)',
            transition: 'background 120ms ease-out',
          }}
        />
      </div>
      <style>{`
        @media (prefers-reduced-motion: reduce) {
          .isolate > div[aria-hidden] { display: none; }
        }
      `}</style>
    </div>
  );
}

