/**
 * OutlookSection — the compact "what's ahead" cards shared by all four modes.
 *
 * One card per validated window: year (and the brief's own birthday age),
 * the possible event, the action for each year, and an optional expandable
 * watch-out. Technical basis, evidence paths and limitations stay in the
 * backend explorer under Why.
 */

import React from 'react';
import { motion } from 'framer-motion';
import { ChevronDown, Shuffle, Target, TrendingUp, TriangleAlert } from 'lucide-react';
import { OBSERVATORY_MONO } from '../designTokens';
import { staggerContainer, staggerItem, pickVariants } from '../animations';
import { supportBand, SUPPORT_FOOTNOTE, type OutlookEntry } from './outlook';

interface OutlookSectionProps {
  entries: OutlookEntry[];
  accentColor: string;
  isReplay?: boolean;
  /** Section label; keep it short. */
  title?: string;
}

const ROW = 'flex gap-2 text-[12px] leading-relaxed text-[#9aa0a8]';

export const OutlookSection: React.FC<OutlookSectionProps> = ({
  entries,
  accentColor,
  isReplay = false,
  title = "What's ahead",
}) => {
  if (entries.length === 0) return null;

  return (
    <section className="space-y-2.5" aria-label={title}>
      <h3
        className="px-1 font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500"
        style={{ fontFamily: OBSERVATORY_MONO }}
      >
        {title}
      </h3>

      <motion.ul
        variants={pickVariants(isReplay, staggerContainer(0.08))}
        initial="hidden"
        animate="visible"
        className="space-y-2"
      >
        {entries.map((entry) => {
          const band = supportBand(entry.support);
          const multiYear = entry.steps.length > 1;
          return (
            <motion.li
              key={entry.id}
              variants={pickVariants(isReplay, staggerItem)}
              className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-3"
            >
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                {entry.icon && (
                  <span className="text-[13px] leading-none" aria-hidden>
                    {entry.icon}
                  </span>
                )}
                <span
                  className="font-mono text-[12px] font-semibold tabular-nums"
                  style={{ color: accentColor, fontFamily: OBSERVATORY_MONO }}
                >
                  {entry.yearLabel}
                </span>
                {entry.ageLabel && (
                  <span className="text-[11px] text-[#7a7f88]">· {entry.ageLabel}</span>
                )}
                {entry.support > 0 && (
                  <span className="ml-auto flex items-center gap-1.5">
                    <span className="text-[10px] uppercase tracking-wide text-[#7a7f88]">
                      {band.label}
                    </span>
                    <span
                      className="h-1 w-9 overflow-hidden rounded-full bg-white/10"
                      aria-hidden
                    >
                      <motion.span
                        className="block h-full rounded-full"
                        style={{ background: accentColor }}
                        initial={isReplay ? { width: `${band.percent}%` } : { width: 0 }}
                        animate={{ width: `${band.percent}%` }}
                        transition={{ duration: isReplay ? 0 : 0.6 }}
                      />
                    </span>
                  </span>
                )}
              </div>

              {entry.title && (
                <p className="mt-1.5 text-[13px] font-medium leading-snug text-[#f4e9c8]">
                  {entry.title}
                </p>
              )}

              <ul className="mt-2 space-y-1.5">
                {entry.possible && (
                  <li className={ROW}>
                    <TrendingUp size={13} className="mt-0.5 flex-none" style={{ color: accentColor }} aria-hidden />
                    <span>
                      <span className="sr-only">Possible: </span>
                      {entry.possible}
                    </span>
                  </li>
                )}
                {entry.steps.map((step) => (
                  <li key={step.year} className={ROW}>
                    <Target size={13} className="mt-0.5 flex-none text-slate-500" aria-hidden />
                    <span>
                      <span className="sr-only">Action: </span>
                      {multiYear && (
                        <b className="font-mono text-[11px] text-slate-300">{step.year} · </b>
                      )}
                      {step.text}
                    </span>
                  </li>
                ))}
              </ul>

              {(entry.risk || entry.alternative) && (
                <details className="group mt-1.5">
                  <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-1.5 text-[11px] text-slate-400 outline-none hover:text-slate-200 focus-visible:ring-1 focus-visible:ring-white/40">
                    <ChevronDown
                      size={12}
                      className="transition-transform group-open:rotate-180"
                      aria-hidden
                    />
                    Watch-outs
                  </summary>
                  <div className="space-y-1.5 pb-1">
                    {entry.risk && (
                      <p className={ROW}>
                        <TriangleAlert size={13} className="mt-0.5 flex-none text-amber-500/80" aria-hidden />
                        <span>{entry.risk}</span>
                      </p>
                    )}
                    {entry.alternative && (
                      <p className={ROW}>
                        <Shuffle size={13} className="mt-0.5 flex-none text-slate-500" aria-hidden />
                        <span>{entry.alternative}</span>
                      </p>
                    )}
                  </div>
                </details>
              )}
            </motion.li>
          );
        })}
      </motion.ul>

      <p className="px-1 text-[10px] leading-relaxed text-slate-500">{SUPPORT_FOOTNOTE}</p>
    </section>
  );
};

export default OutlookSection;
