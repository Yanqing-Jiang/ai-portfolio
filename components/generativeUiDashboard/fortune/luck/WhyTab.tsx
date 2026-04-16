import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { MechanismCard, ChineseToggle } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { Mechanism, Citation } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS['luck-cycle'];

export const WhyTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [showChinese, setShowChinese] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  const mechanisms = (dataModel?.luckCycle?.mechanisms || []) as Mechanism[];
  const citations = (dataModel?.classics?.references || []) as Citation[];

  return (
    <motion.div
      key="why"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-5"
    >
      <div className="flex justify-end">
        <ChineseToggle showChinese={showChinese} onToggle={() => setShowChinese(!showChinese)} />
      </div>

      {mechanisms.length === 0 ? (
        <div className="text-center py-8 text-xs text-slate-500">
          Mechanisms will appear as the reading progresses...
        </div>
      ) : (
        <motion.div
          variants={pickVariants(isReplay, staggerContainer(0.12))}
          initial="hidden"
          animate="visible"
          className="space-y-3"
        >
          {mechanisms.map((m, i) => (
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
    </motion.div>
  );
};
