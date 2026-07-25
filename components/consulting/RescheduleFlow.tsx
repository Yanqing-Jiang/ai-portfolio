import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CalendarDays, Clock, Loader2 } from 'lucide-react';
import { CalendarPicker } from './CalendarPicker';
import { useAvailableSlots } from './useAvailableSlots';
import type { BookingEntry } from './useMyBookings';

interface RescheduleFlowProps {
  booking: BookingEntry;
  onConfirm: (id: string, newSlotStart: string) => Promise<void>;
  onClose: () => void;
}

function formatSlotTime(iso: string) {
  try {
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      timeZoneName: 'short',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export const RescheduleFlow: React.FC<RescheduleFlowProps> = ({ booking, onConfirm, onClose }) => {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedTime, setSelectedTime] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { slots, loading: slotsLoading, bookable } = useAvailableSlots(selectedDate, booking.session_type);

  const handleConfirm = async () => {
    if (!selectedTime) return;
    setLoading(true);
    setError(null);
    try {
      await onConfirm(booking.id, selectedTime);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reschedule failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-slate-900 border border-white/10 rounded-2xl p-6 max-w-lg w-full space-y-5 max-h-[90vh] overflow-y-auto"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center">
              <CalendarDays className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Reschedule Session</h3>
              <p className="text-xs text-slate-400">
                {booking.session_type === '30' ? '30 min' : '60 min'} session
              </p>
            </div>
          </div>

          {/* Calendar */}
          <div>
            <p className="text-sm text-slate-400 mb-3">Pick a new date</p>
            <CalendarPicker
              selectedDate={selectedDate}
              onSelectDate={(d) => {
                setSelectedDate(d);
                setSelectedTime(null);
              }}
            />
          </div>

          {/* Time slots */}
          {selectedDate && (
            <div className="space-y-3">
              <p className="text-sm text-slate-400 flex items-center gap-2">
                <Clock className="w-4 h-4 text-purple-400" /> Available times
              </p>
              {slotsLoading ? (
                <div className="flex items-center gap-2 text-slate-400 py-2 text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading...
                </div>
              ) : !bookable ? (
                // Same rule as the booking flow: if the backend cannot honour a
                // pick, don't show times that the reschedule call would reject.
                <p className="text-slate-400 text-sm py-2">
                  Rescheduling is temporarily unavailable. Email{' '}
                  <a href="mailto:jiangyanqing91@gmail.com" className="text-blue-400 underline">
                    jiangyanqing91@gmail.com
                  </a>{' '}
                  and Yanqing will move the call for you.
                </p>
              ) : slots.length === 0 ? (
                <p className="text-slate-400 text-sm py-2">No available times for this date.</p>
              ) : (
                <div className="grid grid-cols-3 gap-2">
                  {slots.map((slot) => (
                    <button
                      key={slot.start}
                      onClick={() => setSelectedTime(slot.start)}
                      className={`py-2.5 px-3 rounded-xl border text-xs font-medium transition-all ${
                        selectedTime === slot.start
                          ? 'bg-blue-600 border-blue-500 text-white'
                          : 'border-white/10 bg-white/5 hover:border-blue-500/50 text-slate-300'
                      }`}
                    >
                      {formatSlotTime(slot.start)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {error && <p className="text-red-400 text-sm">{error}</p>}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={onClose}
              className="flex-1 py-2.5 rounded-xl border border-white/10 text-slate-300 text-sm font-medium
                         hover:bg-white/5 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={!selectedTime || loading}
              className="flex-1 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium
                         transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Rescheduling...
                </span>
              ) : (
                'Confirm New Time'
              )}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};
