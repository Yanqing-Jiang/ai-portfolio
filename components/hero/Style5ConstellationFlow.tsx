import React, { useCallback, useRef, useState } from 'react';

export default function Style5ConstellationFlow() {
  const wrapper = useRef<HTMLDivElement | null>(null);
  const [hover, setHover] = useState(false);
  const [parallax, setParallax] = useState({ x: 0, y: 0 });

  const onMove = useCallback((e: React.MouseEvent) => {
    if (!wrapper.current) return;
    const r = wrapper.current.getBoundingClientRect();
    const nx = (e.clientX - (r.left + r.width / 2)) / r.width;
    const ny = (e.clientY - (r.top + r.height / 2)) / r.height;
    setParallax({ x: nx, y: ny });
  }, []);

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-6">
      <div className="mb-3 text-[11px] uppercase tracking-wide text-slate-400">Style 5 — Constellation Flow</div>
      <div
        ref={wrapper}
        className="relative h-56 w-full overflow-hidden"
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onMouseMove={onMove}
      >
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 720 240">
          <defs>
            <filter id="pulse" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" />
            </filter>
          </defs>
          <g stroke="#38bdf8" strokeWidth={2} fill="none" style={{ opacity: hover ? 1 : 0.7 }}>
            <path className="yg-edge" d="M140 120 C 230 60, 300 60, 380 120" />
            <path className="yg-edge" d="M400 120 C 490 60, 560 60, 640 120" />
            <path className="yg-edge" d="M400 120 C 310 180, 230 180, 140 120" />
          </g>
          <g className="transition-transform duration-200" style={{ transform: `translate(${parallax.x * -8}px, ${parallax.y * -8}px)` }}>
            <rect x={80} y={90} width={120} height={60} rx={12} className="fill-slate-800/85 stroke-slate-400/40" />
            <text x={140} y={125} textAnchor="middle" className="fill-slate-100 text-[12px] font-semibold">Data</text>
          </g>
          <g className="transition-transform duration-200" style={{ transform: `translate(${parallax.x * 8}px, ${parallax.y * 8}px)` }}>
            <rect x={340} y={90} width={120} height={60} rx={12} className="fill-slate-800/85 stroke-sky-400/60" />
            <text x={400} y={125} textAnchor="middle" className="fill-slate-100 text-[12px] font-semibold">Agent</text>
            {hover && (
              <circle cx={400} cy={120} r={18} className="fill-sky-400/25" filter="url(#pulse)">
                <animate attributeName="r" values="14;22;14" dur="2.4s" repeatCount="indefinite" />
              </circle>
            )}
          </g>
          <g className="transition-transform duration-200" style={{ transform: `translate(${parallax.x * -6}px, ${parallax.y * -6}px)` }}>
            <rect x={580} y={90} width={120} height={60} rx={12} className="fill-slate-800/85 stroke-slate-400/40" />
            <text x={640} y={125} textAnchor="middle" className="fill-slate-100 text-[12px] font-semibold">Action</text>
          </g>
        </svg>
        <style>{`
          @media (prefers-reduced-motion: no-preference) {
            .yg-edge { stroke-dasharray: 10 8; animation: dash 3.2s linear infinite; }
            .yg-edge:hover { animation-duration: 1.3s; }
            @keyframes dash { to { stroke-dashoffset: -360 } }
          }
        `}</style>
      </div>
      <p className="mt-2 text-slate-300">Edges speed up and nodes parallax toward your cursor.</p>
    </div>
  );
}

