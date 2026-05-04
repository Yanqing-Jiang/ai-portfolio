import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { Filter } from 'lucide-react';
import { useFortuneStore } from '../../stores/fortuneStore';
import { MechanismCard, ChineseToggle } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { Mechanism, Citation } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS.compatibility;
const CATEGORIES = ['all', 'combination', 'clash', 'harm', 'support'];

export const WhyTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [showChinese, setShowChinese] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');

  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  const mechanisms = (dataModel?.compatibility?.mechanisms || []) as Mechanism[];
  const citations = (dataModel?.classics?.references || []) as Citation[];

  const filteredMechanisms = useMemo(() => {
    if (filter === 'all') return mechanisms;
    return mechanisms.filter(m => m.type?.toLowerCase().includes(filter));
  }, [mechanisms, filter]);

  return (
    <motion.div
      key="why"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6 pb-12"
    >
      {/* Filter Row */}
      <div className="sticky top-0 z-20 py-2 -mx-1 px-1 bg-[#0B1120]/80 backdrop-blur-md border-b border-white/5">
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
          <div className="flex-none p-1.5 rounded-lg bg-white/5 text-slate-500">
            <Filter size={14} />
          </div>
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setFilter(cat)}
              className={`flex-none px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider transition-all ${
                filter === cat
                  ? 'bg-rose-500 text-white shadow-lg shadow-rose-500/20'
                  : 'bg-white/5 text-slate-400 hover:bg-white/10'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      <div className="flex justify-end">
        <ChineseToggle showChinese={showChinese} onToggle={() => setShowChinese(!showChinese)} />
      </div>

      <AnimatePresence mode="popLayout">
        {filteredMechanisms.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-12 text-xs text-slate-500 italic"
          >
            No {filter} mechanisms found for this pair.
          </motion.div>
        ) : (
          <motion.div
            variants={pickVariants(isReplay, staggerContainer(0.08))}
            initial="hidden"
            animate="visible"
            className="space-y-3"
          >
            {filteredMechanisms.map((m, i) => (
              <MechanismCard
                key={m.id || i}
                mechanism={m}
                citations={citations}
                accentColor={ACCENT.primary}
                showChinese={showChinese}
                isExpanded={expandedId === (m.id || String(i))}
                onToggle={() => setExpandedId(expandedId === (m.id || String(i)) ? null : (m.id || String(i)))}
                isReplay={isReplay}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
