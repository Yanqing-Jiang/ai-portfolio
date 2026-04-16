import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, Zap } from 'lucide-react';
import type { Mechanism, Citation } from '../../lib/fortuneTypes';
import { GLASS } from '../designTokens';
import { staggerItem, slideDown, pickVariants } from '../animations';
import { CitationBlock } from './CitationBlock';

interface MechanismCardProps {
  mechanism: Mechanism;
  citations?: Citation[];
  accentColor?: string;
  showChinese?: boolean;
  isExpanded?: boolean;
  onToggle?: () => void;
  index?: number;
  isReplay?: boolean;
}

export const MechanismCard: React.FC<MechanismCardProps> = ({
  mechanism,
  citations = [],
  accentColor = '#14b8a6',
  showChinese = false,
  isExpanded = false,
  onToggle,
  isReplay = false,
}) => {
  const matchedCitations = citations.filter(
    (c) => mechanism.citationIds?.includes(c.id)
  );

  return (
    <motion.div
      variants={pickVariants(isReplay, staggerItem)}
      className={`${GLASS} overflow-hidden`}
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-4 text-left"
      >
        <div
          className="flex h-8 w-8 flex-none items-center justify-center rounded-lg"
          style={{ background: `${accentColor}1A` }}
        >
          <Zap className="w-4 h-4" style={{ color: accentColor }} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-slate-100 truncate">
            {mechanism.title}
          </div>
          {mechanism.type && (
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mt-0.5">
              {mechanism.type}
            </div>
          )}
        </div>
        <ChevronDown
          className={`w-4 h-4 text-slate-400 flex-none transition-transform ${isExpanded ? 'rotate-180' : ''}`}
        />
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            variants={slideDown}
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-3">
              {/* Bullet points */}
              <ul className="space-y-1.5">
                {mechanism.bullets.map((b, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-300">
                    <span className="mt-1 h-1.5 w-1.5 flex-none rounded-full" style={{ background: accentColor }} />
                    {b}
                  </li>
                ))}
              </ul>

              {/* Citations */}
              {matchedCitations.length > 0 && (
                <div className="space-y-2 pt-1">
                  {matchedCitations.map((c) => (
                    <CitationBlock key={c.id} citation={c} showChinese={showChinese} />
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
