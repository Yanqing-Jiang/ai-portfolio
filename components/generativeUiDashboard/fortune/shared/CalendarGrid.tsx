import React from 'react';
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { OccasionDay } from '../../lib/fortuneTypes';
import { scoreBg } from '../designTokens';
import { staggerContainer, staggerItem, pickVariants } from '../animations';
import { formatDateOnly } from './dateOnly';

interface CalendarGridProps {
  month: string;
  year: number;
  dayScores: OccasionDay[];
  topPickDates?: string[];
  accentColor?: string;
  onDaySelect?: (day: OccasionDay) => void;
  onMonthChange?: (direction: -1 | 1) => void;
  isReplay?: boolean;
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const CalendarGrid: React.FC<CalendarGridProps> = ({
  month,
  year,
  dayScores,
  topPickDates = [],
  accentColor = '#f59e0b',
  onDaySelect,
  onMonthChange,
  isReplay = false,
}) => {
  // Build a sparse map: date string -> OccasionDay
  const dayMap = new Map(dayScores.map((d) => [d.date, d]));

  // Parse first day of month for layout
  const monthNumber = parseInt(month, 10);
  const monthDate = new Date(year, monthNumber - 1, 1);
  const startDow = monthDate.getDay();
  const daysInMonth = new Date(year, monthNumber, 0).getDate();

  // Build grid cells
  const cells: (OccasionDay | null)[] = [];
  for (let i = 0; i < startDow; i++) cells.push(null); // padding
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${month.padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    cells.push(dayMap.get(dateStr) || { date: dateStr, score: -1 });
  }

  return (
    <div>
      {/* Month header */}
      <div className="flex items-center justify-between mb-3">
        <button
          type="button"
          aria-label="Previous month"
          onClick={() => onMonthChange?.(-1)}
          className="p-1.5 rounded-lg hover:bg-white/5 text-slate-400"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <div className="text-sm font-semibold text-slate-200">
          {formatDateOnly(`${year}-${month.padStart(2, '0')}-01`, {
            month: 'long',
            year: 'numeric',
          })}
        </div>
        <button
          type="button"
          aria-label="Next month"
          onClick={() => onMonthChange?.(1)}
          className="p-1.5 rounded-lg hover:bg-white/5 text-slate-400"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Weekday headers */}
      <div className="grid grid-cols-7 gap-1 mb-1">
        {WEEKDAYS.map((wd) => (
          <div key={wd} className="text-center text-[9px] font-medium uppercase tracking-wider text-slate-500">
            {wd}
          </div>
        ))}
      </div>

      {/* Day cells */}
      <motion.div
        variants={pickVariants(isReplay, staggerContainer(0.02))}
        initial="hidden"
        animate="visible"
        className="grid grid-cols-7 gap-1"
      >
        {cells.map((cell, i) => {
          if (!cell) {
            return <div key={`empty-${i}`} className="aspect-square" />;
          }

          const dayNum = parseInt(cell.date.split('-')[2]);
          const hasScore = cell.score >= 0;
          const isTopPick = topPickDates.includes(cell.date);

          return (
            <motion.button
              key={cell.date}
              type="button"
              variants={pickVariants(isReplay, staggerItem)}
              onClick={() => hasScore && onDaySelect?.(cell)}
              disabled={!hasScore}
              className={`aspect-square rounded-lg flex flex-col items-center justify-center text-[11px] transition-all ${
                hasScore ? 'cursor-pointer hover:scale-110' : 'opacity-30'
              } ${isTopPick ? 'ring-2' : ''}`}
              style={{
                ...(isTopPick ? { ['--tw-ring-color' as string]: accentColor } : {}),
              }}
            >
              <span className={`font-medium ${hasScore ? 'text-white' : 'text-slate-600'}`}>
                {dayNum}
              </span>
              {hasScore && (
                <div className={`w-2 h-2 rounded-full mt-0.5 ${scoreBg(cell.score)}`} />
              )}
            </motion.button>
          );
        })}
      </motion.div>
    </div>
  );
};
