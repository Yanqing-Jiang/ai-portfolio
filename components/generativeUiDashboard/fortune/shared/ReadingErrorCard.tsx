/**
 * ReadingErrorCard — terminal state for a run that stopped or was withheld.
 * Short message, one working recovery action, no raw backend detail.
 */

import React, { useState } from 'react';
import { RotateCcw, ShieldAlert, TriangleAlert } from 'lucide-react';
import { AuthModal } from '../../../AuthModal';
import type { ReadingFailure } from '../shell/readingStatus';

interface ReadingErrorCardProps {
  failure: ReadingFailure;
  onRestart: () => void;
  /** Shown when parts of the reading (chart, evidence) are still readable. */
  hasPartialContent?: boolean;
}

export const ReadingErrorCard: React.FC<ReadingErrorCardProps> = ({
  failure,
  onRestart,
  hasPartialContent = false,
}) => {
  const [showAuth, setShowAuth] = useState(false);
  const needsSignIn = /sign-in required after free quota|^Fortune 401$/i.test(failure.message);
  const rejected = failure.kind === 'rejected';
  const Icon = rejected ? ShieldAlert : TriangleAlert;
  const tone = rejected ? 'text-amber-400' : 'text-rose-400';

  return (
    <div
      role="alert"
      className={`rounded-2xl border p-4 ${
        rejected
          ? 'border-amber-500/25 bg-amber-500/[0.04]'
          : 'border-rose-500/25 bg-rose-500/[0.04]'
      }`}
    >
      <div className="flex gap-3">
        <Icon size={18} className={`mt-0.5 flex-none ${tone}`} aria-hidden />
        <div className="min-w-0 space-y-1">
          <p className={`text-[11px] font-bold uppercase tracking-[0.16em] ${tone}`}>
            {needsSignIn ? 'Free reading allowance reached' : rejected ? 'Reading withheld' : 'Reading incomplete'}
          </p>
          <p className="text-[12.5px] leading-relaxed text-slate-300">
            {needsSignIn ? 'Sign in to continue, or return after the daily allowance resets.' : failure.message}
          </p>
          {hasPartialContent && (
            <p className="text-[11px] leading-relaxed text-slate-500">
              Use the chart or Why tab to explore what finished.
            </p>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={needsSignIn ? () => setShowAuth(true) : onRestart}
        className="mt-3 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/[0.04] px-4 text-[12px] font-semibold text-slate-100 transition-colors hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50 sm:w-auto"
      >
        <RotateCcw size={14} aria-hidden />
        {needsSignIn ? 'Sign in to continue' : 'Start a new reading'}
      </button>
      {needsSignIn && (
        <AuthModal
          isOpen={showAuth}
          onClose={() => setShowAuth(false)}
          onSuccess={() => window.location.reload()}
        />
      )}
    </div>
  );
};

export default ReadingErrorCard;
