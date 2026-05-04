/**
 * Shared primitive to show the agent's current orchestration progress.
 * Inlined/Sticky below tab bar.
 */
import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Loader2 } from 'lucide-react';
import { GLASS } from '../designTokens';
import { slideDown } from '../animations';

interface AgentPhaseStripProps {
  progress?: { stage?: string; message?: string; percent?: number };
  isComplete: boolean;
}

export const AgentPhaseStrip: React.FC<AgentPhaseStripProps> = ({ progress, isComplete }) => {
  if (isComplete || !progress?.message) return null;

  const percent = progress.percent ?? 0;

  return (
    <motion.div
      variants={slideDown}
      initial="hidden"
      animate="visible"
      exit="hidden"
      className="sticky top-0 z-20 w-full px-4 py-2"
    >
      <div className={`${GLASS} flex flex-col gap-1.5 p-3 overflow-hidden border-amber-500/30`}>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-500" />
            <span className="text-[11px] font-medium text-amber-100/80 uppercase tracking-wider">
              Agent Orchestration
            </span>
          </div>
          <span className="text-[10px] text-white/40 tabular-nums">
            {percent}%
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-amber-400 shrink-0" />
          <p className="text-xs text-white/90 truncate font-light">
            {progress.message}
          </p>
        </div>

        {/* Progress bar background */}
        <div className="h-0.5 w-full bg-white/5 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-amber-500"
            initial={{ width: 0 }}
            animate={{ width: `${percent}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>
      </div>
    </motion.div>
  );
};
