import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { useFortuneStore } from '../../stores/fortuneStore';
import { CalendarGrid, DayDetailSheet } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { tabContentVariants } from '../animations';
import type { OccasionDay, OccasionPick, Mechanism, Citation } from '../../lib/fortuneTypes';

const ACCENT = FLOW_ACCENTS['lucky-day'];

export const CalendarTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [selectedDay, setSelectedDay] = useState<OccasionDay | null>(null);
  const { dataModel } = useFortuneStore(useShallow((s) => ({ dataModel: s.dataModel })));

  const calendar = dataModel?.occasion?.calendar;
  const topPicks = (dataModel?.occasion?.topPicks || []) as OccasionPick[];
  const mechanisms = (dataModel?.occasion?.mechanisms || []) as Mechanism[];
  const citations = (dataModel?.classics?.references || []) as Citation[];
  const topPickDates = topPicks.map((p) => p.date);

  if (!calendar) {
    return (
      <motion.div
        key="calendar"
        variants={tabContentVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        className="text-center py-12 text-xs text-slate-500"
      >
        Calendar loading...
      </motion.div>
    );
  }

  return (
    <motion.div
      key="calendar"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-5"
    >
      <CalendarGrid
        month={calendar.month}
        year={calendar.year}
        dayScores={calendar.days as OccasionDay[]}
        topPickDates={topPickDates}
        accentColor={ACCENT.primary}
        onDaySelect={setSelectedDay}
        isReplay={isReplay}
      />

      <DayDetailSheet
        day={selectedDay}
        mechanisms={mechanisms}
        citations={citations}
        accentColor={ACCENT.primary}
        onClose={() => setSelectedDay(null)}
      />
    </motion.div>
  );
};
