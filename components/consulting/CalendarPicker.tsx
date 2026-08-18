import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface CalendarPickerProps {
  selectedDate: string | null;
  onSelectDate: (date: string) => void; // YYYY-MM-DD
  disabled?: boolean;
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const CalendarPicker: React.FC<CalendarPickerProps> = ({ selectedDate, onSelectDate, disabled = false }) => {
  const [viewMonth, setViewMonth] = useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() };
  });

  const today = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }, []);

  const calendarDays = useMemo(() => {
    const { year, month } = viewMonth;
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    const days: Array<{ date: string; day: number; disabled: boolean } | null> = [];

    // Leading empty cells
    for (let i = 0; i < firstDay; i++) days.push(null);

    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const isPast = dateStr < today;

      days.push({
        date: dateStr,
        day: d,
        disabled: isPast,
      });
    }

    return days;
  }, [viewMonth, today]);

  const monthLabel = new Date(viewMonth.year, viewMonth.month).toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  });

  const goMonth = (delta: number) => {
    setViewMonth((prev) => {
      let m = prev.month + delta;
      let y = prev.year;
      if (m > 11) { m = 0; y++; }
      if (m < 0) { m = 11; y--; }
      return { year: y, month: m };
    });
  };

  return (
    <div className="bg-[#12110F] border border-[#37332E] p-4 sm:p-6 rounded-[6px]">
      {/* Month navigation */}
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => goMonth(-1)}
          className="p-2 rounded-[4px] hover:bg-white/5 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
        >
          <ChevronLeft className="w-5 h-5 text-[#A8A096]" />
        </button>
        <span className="text-base font-semibold text-[#F1EADF]">{monthLabel}</span>
        <button
          onClick={() => goMonth(1)}
          className="p-2 rounded-[4px] hover:bg-white/5 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
        >
          <ChevronRight className="w-5 h-5 text-[#A8A096]" />
        </button>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-7 gap-1 mb-2">
        {DAYS.map((d) => (
          <div key={d} className="text-center text-xs font-medium text-[#A8A096] py-1">
            {d}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {calendarDays.map((cell, i) =>
          cell ? (
            <motion.button
              key={cell.date}
              disabled={cell.disabled || disabled}
              onClick={() => !cell.disabled && !disabled && onSelectDate(cell.date)}
              whileTap={cell.disabled || disabled ? undefined : { scale: 0.9 }}
              className={`
                min-h-[44px] rounded-[4px] text-sm font-medium transition-all
                ${cell.disabled || disabled
                  ? 'text-[#565049] cursor-not-allowed'
                  : cell.date === selectedDate
                    ? 'bg-[#F04A32] text-[#12110F] font-semibold'
                    : cell.date === today
                      ? 'text-[#F04A32] border border-[#F04A32]/40 hover:bg-[#F04A32]/10'
                      : 'text-[#F1EADF] hover:bg-white/5'
                }
              `}
            >
              {cell.day}
            </motion.button>
          ) : (
            <div key={`empty-${i}`} />
          )
        )}
      </div>
    </div>
  );
};
