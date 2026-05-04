// Single-variant page for /homer/architecture/:variant.
//
// Renders only the chosen variant component on HOMER_THEME.bg, with a sticky
// top bar (back to index, name + counter, prev/next arrows). Keyboard:
//   ←  prev variant
//   →  next variant
//   Esc  back to index
// If the slug is unknown we redirect to the index.

import React, { Suspense, useCallback, useEffect, useMemo } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { HOMER_THEME } from '../theme';
import { VARIANTS, type VariantSlug } from './variants';

const ArchitectureComparePage: React.FC = () => {
  const { variant } = useParams<{ variant: string }>();
  const navigate = useNavigate();

  const idx = useMemo(
    () => VARIANTS.findIndex((v) => v.slug === variant),
    [variant],
  );
  const entry = idx >= 0 ? VARIANTS[idx] : undefined;

  const goPrev = useCallback(() => {
    if (idx < 0) return;
    const prev = VARIANTS[(idx - 1 + VARIANTS.length) % VARIANTS.length];
    navigate(`/homer/architecture/${prev.slug}`);
  }, [idx, navigate]);

  const goNext = useCallback(() => {
    if (idx < 0) return;
    const next = VARIANTS[(idx + 1) % VARIANTS.length];
    navigate(`/homer/architecture/${next.slug}`);
  }, [idx, navigate]);

  const goIndex = useCallback(() => {
    navigate('/homer/architecture');
  }, [navigate]);

  // Keyboard shortcuts: ← prev / → next / Esc to index.
  useEffect(() => {
    if (!entry) return;
    const onKey = (e: KeyboardEvent) => {
      // Don't fight with text inputs.
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        goPrev();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        goNext();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        goIndex();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [entry, goPrev, goNext, goIndex]);

  if (!entry) {
    return <Navigate to="/homer/architecture" replace />;
  }

  const { Component } = entry;

  return (
    <div
      className="min-h-screen w-full"
      style={{ backgroundColor: HOMER_THEME.bg, color: HOMER_THEME.text }}
    >
      {/* Sticky top bar */}
      <header
        className="sticky top-0 z-40 w-full border-b backdrop-blur"
        style={{
          backgroundColor: 'rgba(11, 10, 8, 0.78)',
          borderColor: HOMER_THEME.divider,
        }}
      >
        <div className="max-w-6xl mx-auto h-12 px-4 md:px-6 flex items-center justify-between gap-3">
          <Link
            to="/homer/architecture"
            className="text-[11px] tracking-[0.24em] uppercase transition-colors hover:opacity-80"
            style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
          >
            ← all variants
          </Link>

          <div
            className="flex items-center gap-3 text-[11px] tracking-[0.24em] uppercase"
            style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}
          >
            <span style={{ color: HOMER_THEME.text }}>{entry.name}</span>
            <span aria-hidden>·</span>
            <span>
              {idx + 1} of {VARIANTS.length}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={goPrev}
              aria-label="Previous variant"
              className="px-3 py-1 rounded-md border text-xs transition-colors hover:opacity-80"
              style={{
                fontFamily: HOMER_THEME.fontMono,
                borderColor: HOMER_THEME.divider,
                color: HOMER_THEME.textMuted,
              }}
            >
              ← prev
            </button>
            <button
              type="button"
              onClick={goNext}
              aria-label="Next variant"
              className="px-3 py-1 rounded-md border text-xs transition-colors hover:opacity-80"
              style={{
                fontFamily: HOMER_THEME.fontMono,
                borderColor: HOMER_THEME.divider,
                color: HOMER_THEME.textMuted,
              }}
            >
              next →
            </button>
          </div>
        </div>
      </header>

      {/* Variant body */}
      <main>
        <Suspense
          fallback={
            <div
              className="w-full flex items-center justify-center py-32 text-sm"
              style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}
            >
              loading {entry.name.toLowerCase()}…
            </div>
          }
        >
          <Component />
        </Suspense>
      </main>
    </div>
  );
};

// Convenience export so we can also import the slug type from the route file.
export type { VariantSlug };

export default ArchitectureComparePage;
