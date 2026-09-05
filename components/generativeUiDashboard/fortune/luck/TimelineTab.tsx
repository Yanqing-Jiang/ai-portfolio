import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { LuckFilmStrip, YearCard, ChineseToggle, Sparkline } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { staggerContainer, tabContentVariants, pickVariants } from '../animations';
import type { LuckPillar, AnnualPillar } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS['luck-cycle'];
const CURRENT_YEAR = new Date().getFullYear();

function findCurrentDecadeIndex(decades: LuckPillar[]) {
  const flagged = decades.findIndex((d) => d.isCurrent);
  if (flagged >= 0) return flagged;
  return decades.findIndex((d) => (
    typeof d.startYear === 'number' &&
    typeof d.endYear === 'number' &&
    CURRENT_YEAR >= d.startYear &&
    CURRENT_YEAR <= d.endYear
  ));
}

export function filterAnnualYearsForDecade(
  activeDecade: LuckPillar | undefined,
  allYears: AnnualPillar[],
): AnnualPillar[] {
  if (!activeDecade) return allYears;

  const startYear = activeDecade.startYear ?? (
    activeDecade.startAge > 1900 ? activeDecade.startAge : undefined
  );
  const endYear = activeDecade.endYear ?? (
    activeDecade.endAge > 1900 ? activeDecade.endAge : undefined
  );
  if (typeof startYear !== 'number' || typeof endYear !== 'number') return [];

  return allYears.filter((year) => year.year >= startYear && year.year <= endYear);
}

export function getDecadeScores(decades: LuckPillar[]): number[] {
  return decades.flatMap((decade) => (
    typeof decade.score === 'number' && Number.isFinite(decade.score)
      ? [decade.score]
      : []
  ));
}

export const TimelineTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [showChinese, setShowChinese] = useState(false);
  const [selectedDecadeIdx, setSelectedDecadeIdx] = useState<number>(-1);
  const [expandedYear, setExpandedYear] = useState<number | null>(null);

  const { dataModel, status } = useFortuneStore(useShallow((s) => ({
    dataModel: s.dataModel,
    status: s.status,
  })));

  const decades = (dataModel?.luckPillars?.items || dataModel?.luckCycle?.timeline?.decades || []) as LuckPillar[];
  const allYears = (dataModel?.annualPillars?.items || dataModel?.luckCycle?.timeline?.years || []) as AnnualPillar[];

  const currentDecadeIdx = findCurrentDecadeIndex(decades);
  const activeIdx = selectedDecadeIdx >= 0 ? selectedDecadeIdx : currentDecadeIdx;
  const activeDecade = decades[activeIdx];

  // Filter years by decade. startAge/endAge are ages (not calendar years), so a
  // decade without calendar bounds cannot truthfully claim any annual years.
  const filteredYears = useMemo(() => {
    return filterAnnualYearsForDecade(activeDecade, allYears);
  }, [activeDecade, allYears]);

  const sparkData = getDecadeScores(decades);

  return (
    <motion.div
      key="timeline"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6 pb-24"
    >
      <div className="flex items-center justify-between px-1">
        <div>
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
            Life Chapters
          </h3>
          <p className="text-[11px] text-indigo-400/80 font-medium">10-Year Luck Pillars</p>
        </div>
        <ChineseToggle showChinese={showChinese} onToggle={() => setShowChinese(!showChinese)} />
      </div>

      {/* Main Film Strip Component */}
      <LuckFilmStrip
        decades={decades}
        currentDecadeIndex={currentDecadeIdx}
        selectedIndex={selectedDecadeIdx >= 0 ? selectedDecadeIdx : undefined}
        onDecadeSelect={setSelectedDecadeIdx}
        showChinese={showChinese}
        isReplay={isReplay}
        isStreaming={status === 'streaming'}
      />

      {/* Sparkline for Trend Visualization */}
      {sparkData.length >= 2 && (
        <div className="flex flex-col items-center gap-2 py-2">
          <div className="text-[9px] uppercase tracking-widest text-slate-500">Vitality Trend</div>
          <Sparkline data={sparkData} width={320} height={48} color={ACCENT.primary} />
        </div>
      )}

      {/* Annual Detail Section */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeIdx}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          className="space-y-3"
        >
          <div className="flex items-baseline justify-between px-1">
            <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
              {activeDecade ? `Ages ${activeDecade.startAge}-${activeDecade.endAge} · Annual Pillars` : 'Annual Outlook'}
            </h3>
            {activeDecade?.element && (
              <span className="text-[10px] text-indigo-400 font-medium">
                {activeDecade.element} Decade
              </span>
            )}
          </div>

          {filteredYears.length > 0 ? (
            <motion.div
              variants={pickVariants(isReplay, staggerContainer(0.06))}
              initial="hidden"
              animate="visible"
              className="space-y-2.5"
            >
              {filteredYears.map((y, index) => (
                <YearCard
                  key={`${y.year}-${index}`}
                  item={y}
                  isExpanded={expandedYear === y.year}
                  onToggle={() => setExpandedYear(expandedYear === y.year ? null : y.year)}
                  isReplay={isReplay}
                />
              ))}
            </motion.div>
          ) : (
            <div className="text-center py-12 rounded-2xl border border-dashed border-slate-800 bg-slate-900/20">
              <p className="text-xs text-slate-500">
                {status === 'streaming'
                  ? 'Calculating annual pillars...'
                  : activeDecade
                    ? 'No annual pillars are available for this decade.'
                    : 'Select a decade to view yearly details'}
              </p>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
};
