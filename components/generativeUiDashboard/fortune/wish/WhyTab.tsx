import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { MechanismCard, CitationBlock, ChineseToggle } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { Mechanism, Citation, Interaction } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS.wish;

export const WhyTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [showChinese, setShowChinese] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  // Real backend paths: interactions come as { items: Interaction[] }
  // Convert interactions into mechanism-like cards for display
  const rawInteractions = (dataModel?.interactions?.items || []) as Interaction[];
  const interactionCards: Mechanism[] = rawInteractions.map((inter, i) => ({
    id: `inter-${i}`,
    title: `${inter.type}: ${inter.from} → ${inter.to}`,
    type: inter.type,
    bullets: [inter.description, inter.effect].filter(Boolean) as string[],
  }));

  // If wish-specific mechanisms exist (future backend extension), use them too
  const wishMechanisms = (dataModel?.wish?.mechanisms || []) as Mechanism[];

  const allMechanisms = [...wishMechanisms, ...interactionCards];
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

      {/* Standalone citations if no mechanisms yet */}
      {allMechanisms.length === 0 && citations.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
            Classical References
          </h3>
          {citations.map((c) => (
            <CitationBlock key={c.id} citation={c} showChinese={showChinese} />
          ))}
        </div>
      )}

      {allMechanisms.length === 0 && citations.length === 0 ? (
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
          {allMechanisms.map((m, i) => (
            <MechanismCard
              key={m.id || m.title || i}
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
