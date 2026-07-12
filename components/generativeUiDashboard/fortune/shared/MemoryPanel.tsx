/**
 * MemoryPanel — Session Memory inspector for the Ask tab.
 *
 * Hydrates from GET /conversation on mount and appends local Ask turns so
 * the panel demos SQLAlchemySession continuity without ops noise.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, ChevronRight, MessageSquare } from 'lucide-react';
import { useShallow } from 'zustand/react/shallow';
import { fortuneClient } from '../../lib/fortuneClient';
import { useFortuneStore } from '../../stores/fortuneStore';
import { GLASS } from '../designTokens';

interface MemoryTurn {
  role: 'user' | 'assistant';
  text: string;
  at: string;
  local?: boolean;
}

export const MemoryPanel: React.FC = () => {
  const { fortuneId, askHistory } = useFortuneStore(
    useShallow((s) => ({
      fortuneId: s.fortuneId,
      askHistory: s.askHistory,
    })),
  );

  const [open, setOpen] = useState(false);
  const [remote, setRemote] = useState<MemoryTurn[]>([]);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  useEffect(() => {
    if (!fortuneId) {
      setRemote([]);
      setLoadedFor(null);
      return;
    }
    if (loadedFor === fortuneId) return;

    let cancelled = false;
    (async () => {
      try {
        const res = await fortuneClient.getConversation(fortuneId);
        if (cancelled) return;
        setRemote(
          (res.turns || []).map((t) => ({
            role: t.role,
            text: t.text,
            at: t.at || '',
          })),
        );
        setLoadedFor(fortuneId);
      } catch {
        if (!cancelled) {
          setRemote([]);
          setLoadedFor(fortuneId);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [fortuneId, loadedFor]);

  const turns = useMemo(() => {
    const local: MemoryTurn[] = askHistory.map((h) => ({
      role: h.role === 'agent' ? 'assistant' : 'user',
      text: h.content,
      at: h.timestampISO,
      local: true,
    }));

    // Prefer remote history; append local turns that aren't already present
    // (remote may lag until next tab open after an Ask).
    if (remote.length === 0) return local;

    const remoteKeys = new Set(
      remote.map((t) => `${t.role}:${t.text.slice(0, 120)}`),
    );
    const extras = local.filter(
      (t) => !remoteKeys.has(`${t.role}:${t.text.slice(0, 120)}`),
    );
    return [...remote, ...extras];
  }, [remote, askHistory]);

  return (
    <div className={`${GLASS} overflow-hidden border-white/10`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        aria-expanded={open}
      >
        <div className="flex min-w-0 items-center gap-2.5">
          <MessageSquare size={13} className="flex-none text-slate-400" />
          <div className="min-w-0">
            <div className="text-[11px] font-semibold tracking-wide text-slate-200">
              Session Memory · {turns.length} turn{turns.length === 1 ? '' : 's'}
            </div>
            <div className="truncate text-[10px] text-slate-500">
              Follow-ups run with full session memory — earlier turns shape later answers.
            </div>
          </div>
        </div>
        {open ? (
          <ChevronDown size={14} className="text-slate-500" />
        ) : (
          <ChevronRight size={14} className="text-slate-500" />
        )}
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden border-t border-white/5"
          >
            <div className="max-h-48 space-y-2 overflow-y-auto px-4 py-3">
              {turns.length === 0 ? (
                <p className="py-3 text-center text-[11px] text-slate-500">
                  No prior turns yet. Ask a follow-up to seed session memory.
                </p>
              ) : (
                turns.map((t, i) => (
                  <div
                    key={`${t.role}-${i}-${t.at}`}
                    className="rounded-lg border border-white/5 bg-black/20 px-3 py-2"
                  >
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="text-[9px] font-bold uppercase tracking-wider text-slate-500">
                        {t.role}
                        {t.local ? ' · live' : ''}
                      </span>
                      {t.at ? (
                        <span className="font-mono text-[9px] text-slate-600">
                          {t.at.slice(11, 19) || t.at}
                        </span>
                      ) : null}
                    </div>
                    <p className="line-clamp-3 text-[11px] leading-relaxed text-slate-300">
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
