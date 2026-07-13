/**
 * MemoryPanel — compact SESSION MEMORY strip (Phase 5 / ledger-aligned).
 *
 * Reads the same hydrated store as the visible chat, so the two surfaces
 * cannot disagree after reload.
 */

import React, { useMemo, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { OBS_MEMORY_STRIP, OBSERVATORY_MONO } from '../designTokens';

export const MemoryPanel: React.FC = () => {
  const reduceMotion = useReducedMotion();
  const askHistory = useFortuneStore(useShallow((s) => s.askHistory));

  const [open, setOpen] = useState(false);

  const turns = useMemo(() => {
    return askHistory.map((h) => ({
      role: h.role === 'agent' ? 'assistant' : 'user',
      text: h.content,
      at: h.timestampISO,
    }));
  }, [askHistory]);

  return (
    <div className={OBS_MEMORY_STRIP}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left"
        style={{ fontFamily: OBSERVATORY_MONO }}
        aria-expanded={open}
      >
        <div className="min-w-0 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#9fb3a8]">
          Session Memory · {turns.length} Turn{turns.length === 1 ? '' : 's'}
        </div>
        {open ? (
          <ChevronDown size={14} className="text-[#5c6963]" />
        ) : (
          <ChevronRight size={14} className="text-[#5c6963]" />
        )}
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={reduceMotion ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={reduceMotion ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.18 }}
            className="overflow-hidden border-t border-white/[0.05]"
          >
            <div className="max-h-48 space-y-1.5 overflow-y-auto px-4 py-3" style={{ fontFamily: OBSERVATORY_MONO }}>
              {turns.length === 0 ? (
                <p className="py-2 text-center text-[10.5px] text-[#5c6963]">
                  No prior turns yet. Ask a follow-up to seed session memory.
                </p>
              ) : (
                turns.map((t, i) => (
                  <div
                    key={`${t.role}-${i}-${t.at}`}
                    className="border-b border-white/[0.04] py-1.5 last:border-0"
                  >
                    <div className="mb-0.5 flex items-center justify-between gap-2 text-[9px] uppercase tracking-[0.16em] text-[#5c6963]">
                      <span>
                        {t.role}
                      </span>
                      {t.at ? <span>{t.at.slice(11, 19) || t.at}</span> : null}
                    </div>
                    <p className="line-clamp-2 text-[10.5px] leading-relaxed text-[#b9c4bd]">
                      {t.text}
                    </p>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default MemoryPanel;
