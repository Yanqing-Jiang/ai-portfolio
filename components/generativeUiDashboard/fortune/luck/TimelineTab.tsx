import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { TimelineBar, YearCard, Sparkline, ChineseToggle } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { LuckPillar, AnnualPillar } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS['luck-cycle'];

export const TimelineTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [showChinese, setShowChinese] = useState(false);
  const [selectedDecade, setSelectedDecade] = useState<number>(-1);
  const [expandedYear, setExpandedYear] = useState<number | null>(null);
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  const decades = (dataModel?.luckPillars?.items || []) as LuckPillar[];
  const years = (dataModel?.annualPillars?.items || []) as AnnualPillar[];
  const currentDecadeIdx = decades.findIndex((d) => d.isCurrent);
  void (selectedDecade >= 0 ? selectedDecade : currentDecadeIdx); // reserved for per-decade detail

  // Sparkline data from decade scores
  const sparkData = decades.map((d) => d.score ?? 50);

  return (
    <motion.div
      key="timeline"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-5"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
          Decade Pillars
        </h3>
        <ChineseToggle showChinese={showChinese} onToggle={() => setShowChinese(!showChinese)} />
      </div>

      {/* Decade timeline */}
      {decades.length > 0 ? (
        <TimelineBar
          decades={decades}
          currentDecadeIndex={currentDecadeIdx}
          accentColor={ACCENT.primary}
          showChinese={showChinese}
          onDecadeSelect={setSelectedDecade}
          isReplay={isReplay}
        />
      ) : (
        <div className="text-center py-6 text-xs text-slate-500">
          Decade pillars loading...
        </div>
      )}

      {/* Sparkline */}
      {sparkData.length >= 2 && (
        <div className="flex justify-center">
          <Sparkline data={sparkData} width={280} height={40} color={ACCENT.primary} />
        </div>
      )}

      {/* Annual pillars */}
      {years.length > 0 && (
        <>
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400 pt-2">
            Annual Pillars
          </h3>
          <motion.div
            variants={pickVariants(isReplay, staggerContainer(0.06))}
            initial="hidden"
            animate="visible"
            className="space-y-2"
          >
            {years.map((y) => (
              <YearCard
                key={y.year}
                item={y}
                isExpanded={expandedYear === y.year}
                onToggle={() => setExpandedYear(expandedYear === y.year ? null : y.year)}
                isReplay={isReplay}
              />
            ))}
          </motion.div>
        </>
      )}
    </motion.div>
  );
};
