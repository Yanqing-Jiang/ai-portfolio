/**
 * Wrapper for PickCard to handle inline mechanism expansion.
 */
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, Sparkles } from 'lucide-react';
import { PickCard } from '../shared/PickCard';
import { MechanismCard } from '../shared/MechanismCard';
import { FLOW_ACCENTS } from '../designTokens';
import type { OccasionPick, Citation } from '../../lib/fortuneTypes';

interface ExpandablePickCardProps {
  pick: OccasionPick;
  rank: number;
  citations: Citation[];
  isReplay?: boolean;
}

export const ExpandablePickCard: React.FC<ExpandablePickCardProps> = ({
  pick,
  rank,
  citations,
  isReplay = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const accent = FLOW_ACCENTS['lucky-day'];

  return (
    <div className="flex flex-col gap-2">
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="relative cursor-pointer active:scale-[0.98] transition-transform"
      >
        <PickCard
          pick={pick}
          rank={rank}
          accentColor={accent.primary}
          isReplay={isReplay}
        />
        <div className="pointer-events-none absolute bottom-3 right-3 text-white/20">
          <motion.div animate={{ rotate: isExpanded ? 180 : 0 }}>
            <ChevronDown size={14} />
          </motion.div>
        </div>
      </div>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden flex flex-col gap-2 px-1"
          >
            <div className="text-[10px] font-bold text-white/30 uppercase tracking-tighter flex items-center gap-2 mb-1 px-3">
              <Sparkles size={10} />
              Key Mechanisms
            </div>
            {pick.mechanisms?.map((mech, idx) => (
              <MechanismCard
                key={mech.id || idx}
                mechanism={mech}
                citations={citations}
                accentColor={accent.primary}
                isExpanded={false}
                isReplay={isReplay}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
