import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { Anchor } from 'lucide-react';
import { useFortuneStore } from '../../stores/fortuneStore';
import {
  PillarRow, ElementRadar, DayMasterCard, SeasonalStrengthBar, ChineseToggle, AnchorPill
} from '../shared';
import { FLOW_ACCENTS, GLASS } from '../designTokens';
import { tabContentVariants, pickVariants, staggerContainer } from '../animations';
import type { PillarSet, ElementCounts, ElementType, SeasonalStrength as SeasonalStrengthType, WishModel } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS.wish;

export const AnchorTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [showChinese, setShowChinese] = useState(false);
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  const wish = dataModel?.wish as WishModel | undefined;
  const anchors = wish?.anchors || [];
  const pillars = dataModel?.pillars as PillarSet | undefined;
  const elements = dataModel?.elements as ElementCounts | undefined;
  const seasonal = dataModel?.seasonalStrength as SeasonalStrengthType | undefined;
  const kpi = dataModel?.kpi as Record<string, unknown> | undefined;

  const dayMasterStem = (pillars?.day?.stem || kpi?.dayMaster || '') as string;
  const dayMasterElement = (pillars?.day?.element || kpi?.dayMasterElement || 'Wood') as ElementType;

  return (
    <motion.div
      key="anchor"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6 pb-8"
    >
      <div className="flex justify-between items-center px-1">
        <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500 flex items-center gap-2">
          <Anchor className="h-3 w-3" style={{ color: ACCENT.primary }} />
          Chart Anchors
        </h3>
        <ChineseToggle showChinese={showChinese} onToggle={() => setShowChinese(!showChinese)} />
      </div>

      {/* 1. Weighted Anchor Pills */}
      {anchors.length > 0 ? (
        <motion.div
          variants={pickVariants(isReplay, staggerContainer(0.08))}
          initial="hidden"
          animate="visible"
          className="flex flex-col gap-3"
        >
          {[...anchors].sort((a, b) => b.relevance - a.relevance).slice(0, 3).map((anchor) => (
            <AnchorPill
              key={anchor.id}
              {...anchor}
              accentColor={ACCENT.primary}
              isReplay={isReplay}
            />
          ))}
        </motion.div>
      ) : (
        <div className={`${GLASS} p-4 text-center border-dashed`}>
          <p className="text-[11px] text-slate-500 italic">Identifying chart anchors...</p>
        </div>
      )}

      {/* 2. Pillars Section Header */}
      <div className="pt-2">
        <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500 mb-3 px-1">
          Bazi Foundation
        </h3>
        {pillars && (
          <PillarRow
            pillars={pillars}
            showChinese={showChinese}
            accentColor={ACCENT.primary}
            isReplay={isReplay}
          />
        )}
      </div>

      {/* 3. Day Master & Element Dynamics */}
      <div className="grid grid-cols-1 gap-4">
        {dayMasterStem && (
          <DayMasterCard
            stem={dayMasterStem}
            element={dayMasterElement}
            strength={seasonal?.strength || 'moderate'}
            description={seasonal?.description}
            accentColor={ACCENT.primary}
            isReplay={isReplay}
          />
        )}

        <div className={`${GLASS} p-4 space-y-4`}>
          <div className="flex flex-col items-center">
             <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-slate-500 mb-4">Element Balance</span>
             {elements && (
                <ElementRadar
                  scores={elements}
                  dominant={kpi?.dominantElement as ElementType | undefined}
                  weak={kpi?.weakestElement as ElementType | undefined}
                  accentColor={ACCENT.primary}
                  isReplay={isReplay}
                />
              )}
          </div>
          
          {seasonal && (
            <SeasonalStrengthBar
              strength={seasonal.strength}
              score={seasonal.score}
              season={seasonal.season}
              accentColor={ACCENT.primary}
              isReplay={isReplay}
            />
          )}
        </div>
      </div>
    </motion.div>
  );
};
