import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import {
  PillarRow, ElementRadar, DayMasterCard, SeasonalStrengthBar, ChineseToggle,
} from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { tabContentVariants } from '../animations';
import type { PillarSet, ElementCounts, ElementType, SeasonalStrength as SeasonalStrengthType } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS.wish;

export const AnchorTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [showChinese, setShowChinese] = useState(false);
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

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
      className="space-y-5"
    >
      <div className="flex justify-end">
        <ChineseToggle showChinese={showChinese} onToggle={() => setShowChinese(!showChinese)} />
      </div>

      {/* Pillars */}
      {pillars && (
        <PillarRow
          pillars={pillars}
          showChinese={showChinese}
          accentColor={ACCENT.primary}
          isReplay={isReplay}
        />
      )}

      {/* Day Master */}
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

      {/* Element Radar */}
      {elements && (
        <div className="flex justify-center">
          <ElementRadar
            scores={elements}
            dominant={kpi?.dominantElement as ElementType | undefined}
            weak={kpi?.weakestElement as ElementType | undefined}
            accentColor={ACCENT.primary}
            isReplay={isReplay}
          />
        </div>
      )}

      {/* Seasonal Strength */}
      {seasonal && (
        <SeasonalStrengthBar
          strength={seasonal.strength}
          score={seasonal.score}
          season={seasonal.season}
          accentColor={ACCENT.primary}
          isReplay={isReplay}
        />
      )}
    </motion.div>
  );
};
