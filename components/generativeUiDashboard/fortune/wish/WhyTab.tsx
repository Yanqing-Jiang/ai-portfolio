import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { Layers, Zap, BookOpen } from 'lucide-react';
import { useFortuneStore } from '../../stores/fortuneStore';
import { MechanismCard, CitationBlock, ChineseToggle } from '../shared';
import { FLOW_ACCENTS, GLASS, CITATION_GOLD } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { Mechanism, Citation, Interaction, WishModel } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS.wish;

export const WhyTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [showChinese, setShowChinese] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  const wish = dataModel?.wish as WishModel | undefined;
  const wishMechanisms = wish?.mechanisms || [];
  const rawInteractions = (dataModel?.interactions?.items || []) as Interaction[];
  const citations = (dataModel?.classics?.references || []) as Citation[];

  // Grouping logic
  const groups = useMemo(() => {
    const interactionMechanisms: Mechanism[] = rawInteractions.map((inter, i) => ({
      id: `inter-${i}`,
      title: `${inter.type}: ${inter.from} → ${inter.to}`,
      type: 'interaction',
      bullets: [inter.description, inter.effect].filter(Boolean) as string[],
    }));

    const luckMechanisms = wishMechanisms.filter(m => m.type === 'luck' || m.title.toLowerCase().includes('luck') || m.title.toLowerCase().includes('cycle'));
    const chartMechanisms = wishMechanisms.filter(m => !luckMechanisms.includes(m));

    return [
      {
        id: 'interactions',
        label: 'Chart Interactions',
        icon: <Layers className="h-3 w-3" />,
        items: [...chartMechanisms, ...interactionMechanisms]
      },
      {
        id: 'luck',
        label: 'Luck Drivers',
        icon: <Zap className="h-3 w-3" />,
        items: luckMechanisms
      },
      {
        id: 'classics',
        label: 'Classical Patterns',
        icon: <BookOpen className="h-3 w-3" />,
        items: [] as Mechanism[],
        citations: citations
      }
    ].filter(g => g.items.length > 0 || (g.citations && g.citations.length > 0));
  }, [wishMechanisms, rawInteractions, citations]);

  return (
    <motion.div
      key="why"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6 pb-8"
    >
      <div className="flex justify-end px-1">
        <ChineseToggle showChinese={showChinese} onToggle={() => setShowChinese(!showChinese)} />
      </div>

      {groups.length === 0 ? (
        <div className={`${GLASS} p-12 text-center border-dashed`}>
          <p className="text-xs text-slate-500 italic">Deep analysis in progress...</p>
        </div>
      ) : (
        <div className="space-y-8">
          {groups.map((group) => (
            <div key={group.id} className="space-y-3">
              <div className="flex items-center gap-2 px-1">
                <div className="p-1.5 rounded-lg bg-white/5 border border-white/10" style={{ color: group.id === 'classics' ? CITATION_GOLD : ACCENT.primary }}>
                  {group.icon}
                </div>
                <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
                  {group.label}
                </h3>
              </div>

              <motion.div
                variants={pickVariants(isReplay, staggerContainer(0.1))}
                initial="hidden"
                animate="visible"
                className="space-y-3"
              >
                {group.items.map((m, i) => (
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

                {group.id === 'classics' && group.citations?.map((c) => (
                  <CitationBlock 
                    key={c.id} 
                    citation={c} 
                    showChinese={showChinese} 
                  />
                ))}
              </motion.div>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
};
