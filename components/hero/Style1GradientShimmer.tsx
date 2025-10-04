import React from 'react';

export default function Style1GradientShimmer() {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-6">
      <div className="mb-3 text-[11px] uppercase tracking-wide text-slate-400">Style 1 — Gradient Shimmer</div>
      <h3
        className="text-3xl sm:text-4xl md:text-5xl font-extrabold leading-tight"
        style={{
          backgroundImage:
            'linear-gradient(90deg, #7dd3fc 0%, #c084fc 35%, #f472b6 65%, #7dd3fc 100%)',
          WebkitBackgroundClip: 'text',
          backgroundClip: 'text',
          color: 'transparent',
          backgroundSize: '200% 100%',
          animation: 'yg-shimmer 10s ease-in-out infinite',
        }}
      >
        Agentic Analytics
      </h3>
      <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-slate-200">
        AI Project Preview
        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h8m0 0l-4-4m4 4l-4 4" />
        </svg>
      </div>
      <style>{`
        @media (prefers-reduced-motion: no-preference) {
          @keyframes yg-shimmer { 0% { background-position: 0% 50% } 50% { background-position: 100% 50% } 100% { background-position: 0% 50% } }
        }
        @media (prefers-reduced-motion: reduce) {
          h3 { animation: none !important; }
        }
      `}</style>
    </div>
  );
}
