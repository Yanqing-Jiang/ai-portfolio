/**
 * Tab 2: Calendar Heat-map
 * Playable grid with legend and quick-links to top picks.
 */
import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { Star, Calendar as CalendarIcon } from 'lucide-react';
import { useFortuneStore } from '../../stores/fortuneStore';
import { CalendarGrid } from '../shared/CalendarGrid';
import { DayDetailSheet } from '../shared/DayDetailSheet';
import { FLOW_ACCENTS, GLASS } from '../designTokens';
import { formatDateOnly } from '../shared/dateOnly';
import { fadeInUp, pickVariants } from '../animations';
import type {
  OccasionDay,
  OccasionPick,
  Mechanism,
  Citation,
} from '../../lib/fortuneTypes';

export const CalendarTab: React.FC<{ isReplay?: boolean }> = ({ isReplay = false }) => {
  const [selectedDay, setSelectedDay] = useState<OccasionDay | null>(null);
  const [monthOffset, setMonthOffset] = useState(0);
  const { dataModel } = useFortuneStore(useShallow((s) => ({
    dataModel: s.dataModel,
  })));

  const calendarData = dataModel?.occasion?.calendar;
  const topPicks = (dataModel?.occasion?.topPicks || []) as OccasionPick[];
  const mechanisms = (dataModel?.occasion?.mechanisms || []) as Mechanism[];
  const citations = (dataModel?.classics?.references || []) as Citation[];
  const accent = FLOW_ACCENTS['lucky-day'];

  if (!calendarData) {
    return (
      <div className="px-4 py-12 flex flex-col items-center text-center gap-4">
        <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center border border-white/10">
          <CalendarIcon className="text-white/20" size={32} />
        </div>
        <div>
          <h3 className="text-white font-medium">Heat-map not generated</h3>
          <p className="text-xs text-white/40 max-w-[240px] mt-1">
            This occasion returned targeted picks only. Check the Top Picks tab for ranked dates.
          </p>
        </div>
      </div>
    );
  }

  const days = calendarData.days as OccasionDay[];
  const topPickDates = topPicks.map((p) => p.date);
  const visibleMonth = new Date(calendarData.year, Number(calendarData.month) - 1 + monthOffset, 1);

  return (
    <motion.div
      variants={pickVariants(isReplay, fadeInUp)}
      initial="hidden"
      animate="visible"
      className="flex flex-col gap-6 pb-24"
    >
      {/* Legend Row */}
      <div className="flex items-center justify-between px-2 text-[10px] text-white/40 uppercase tracking-tighter">
        <div className="flex gap-3">
          <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-green-500" /> Great</div>
          <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Good</div>
          <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> Caution</div>
        </div>
        <div className="flex items-center gap-1 text-amber-400 font-bold">
          <Star size={10} fill="currentColor" /> Top Pick
        </div>
      </div>

      <div className={`${GLASS} p-4`}>
        <CalendarGrid
          month={String(visibleMonth.getMonth() + 1).padStart(2, '0')}
          year={visibleMonth.getFullYear()}
          dayScores={days}
          topPickDates={topPickDates}
          accentColor={accent.primary}
          onDaySelect={setSelectedDay}
          onMonthChange={(direction) => setMonthOffset((offset) => offset + direction)}
          isReplay={isReplay}
        />
      </div>

      {/* Quick Links Strip */}
      {topPicks.length > 0 && (
        <div className="flex flex-col gap-3">
          <span className="text-[10px] font-bold text-white/30 uppercase tracking-widest px-1">
            Jump to Top Picks
          </span>
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
            {topPicks.slice(0, 3).map((pick, idx) => {
              const dayData = days.find((d) => d.date === pick.date) || {
                date: pick.date,
                score: pick.score,
              };
              return (
                <button
                  type="button"
                  key={pick.date}
                  onClick={() => setSelectedDay(dayData)}
                  className="shrink-0 flex items-center gap-3 px-4 py-3 bg-white/5 border border-white/10 rounded-2xl active:bg-white/10 transition-colors"
                >
                  <div className="flex flex-col items-start">
                    <span className="text-[10px] text-amber-500 font-bold">#{idx + 1}</span>
                    <span className="text-xs text-white font-medium">
                      {formatDateOnly(pick.date, { month: 'short', day: 'numeric' })}
                    </span>
                  </div>
                  <div className="h-6 w-px bg-white/10" />
                  <span className="text-sm font-bold text-white tabular-nums">{pick.score}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      <DayDetailSheet
        day={selectedDay}
        mechanisms={mechanisms}
        citations={citations}
        accentColor={accent.primary}
        onClose={() => setSelectedDay(null)}
      />
    </motion.div>
  );
};
