import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { PillarRow, ElementRadar, DayMasterCard, ConnectionLines, ChineseToggle } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { tabContentVariants } from '../animations';
import type { PairInteraction } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS.compatibility;

export const PillarsTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [showChinese, setShowChinese] = useState(false);
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  const compat = dataModel?.compatibility;
  const personA = compat?.personA;
  const personB = compat?.personB;
  const interactions = (compat?.pairInteractions || []) as PairInteraction[];

  return (
    <motion.div
      key="pillars"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-5"
    >
      <div className="flex justify-end">
        <ChineseToggle showChinese={showChinese} onToggle={() => setShowChinese(!showChinese)} />
      </div>

      {/* Person A */}
      {personA?.pillars && (
        <div className="space-y-2">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em]" style={{ color: ACCENT.primary }}>
            {personA.name || 'Person A'}
          </h3>
          <PillarRow
            pillars={personA.pillars}
            showChinese={showChinese}
            accentColor={ACCENT.primary}
            isReplay={isReplay}
          />
          {personA.dayMaster && (
            <DayMasterCard
              stem={personA.dayMaster}
              element={personA.dayMasterElement || 'Wood'}
              strength="moderate"
              accentColor={ACCENT.primary}
              isReplay={isReplay}
            />
          )}
        </div>
      )}

      {/* Connection lines */}
      {interactions.length > 0 && (
        <div className="flex justify-center overflow-x-auto">
          <ConnectionLines interactions={interactions} />
        </div>
      )}

      {/* Person B */}
      {personB?.pillars && (
        <div className="space-y-2">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-300">
            {personB.name || 'Person B'}
          </h3>
          <PillarRow
            pillars={personB.pillars}
            showChinese={showChinese}
            accentColor="#94a3b8"
            isReplay={isReplay}
          />
          {personB.dayMaster && (
            <DayMasterCard
              stem={personB.dayMaster}
              element={personB.dayMasterElement || 'Wood'}
              strength="moderate"
              accentColor="#94a3b8"
              isReplay={isReplay}
            />
          )}
        </div>
      )}

      {/* Dual element radar */}
      {personA?.elements && personB?.elements && (
        <div className="flex justify-center">
          <ElementRadar
            scores={personA.elements}
            accentColor={ACCENT.primary}
            secondaryScores={personB.elements}
            secondaryColor="#94a3b8"
            isReplay={isReplay}
          />
        </div>
      )}
    </motion.div>
  );
};
