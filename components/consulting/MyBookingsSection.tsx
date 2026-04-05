import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Loader2, CalendarDays } from 'lucide-react';
import type { User } from '@/services/auth';
import { useMyBookings } from './useMyBookings';
import { BookingCard } from './BookingCard';
import { CancelDialog } from './CancelDialog';
import { RescheduleFlow } from './RescheduleFlow';

interface MyBookingsSectionProps {
  user: User;
}

export const MyBookingsSection: React.FC<MyBookingsSectionProps> = ({ user }) => {
  const { bookings, loading, error, cancelBooking, rescheduleBooking, refetch } = useMyBookings();
  const [cancelTarget, setCancelTarget] = useState<string | null>(null);
  const [rescheduleTarget, setRescheduleTarget] = useState<string | null>(null);

  const cancelTargetBooking = cancelTarget ? bookings.find((b) => b.id === cancelTarget) : null;
  const rescheduleTargetBooking = rescheduleTarget ? bookings.find((b) => b.id === rescheduleTarget) : null;

  const upcoming = bookings.filter((b) => b.status === 'confirmed' && new Date(b.slot_start) > new Date());
  const past = bookings.filter((b) => b.status !== 'confirmed' || new Date(b.slot_start) <= new Date());

  if (loading) {
    return (
      <section className="px-6 pb-8 max-w-5xl mx-auto">
        <div className="flex items-center justify-center gap-2 text-slate-400 py-8">
          <Loader2 className="w-5 h-5 animate-spin" /> Loading your bookings...
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="px-6 pb-8 max-w-5xl mx-auto">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-center text-red-400 text-sm">
          {error}
        </div>
      </section>
    );
  }

  if (bookings.length === 0) {
    return (
      <section className="px-6 pb-8 max-w-5xl mx-auto">
        <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6 text-center">
          <CalendarDays className="w-8 h-8 mx-auto text-slate-500 mb-3" />
          <p className="text-slate-400 text-sm">
            No bookings yet. Book your first consulting session below!
          </p>
        </div>
      </section>
    );
  }

  return (
    <>
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="px-6 pb-8 max-w-5xl mx-auto"
      >
        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          <CalendarDays className="w-5 h-5 text-blue-400" />
          My Bookings
          <span className="text-xs text-slate-500 font-normal ml-2">
            {user.email}
          </span>
        </h3>

        {/* Upcoming */}
        {upcoming.length > 0 && (
          <div className="space-y-3 mb-6">
            <p className="text-xs uppercase tracking-wider text-slate-500 font-medium">Upcoming</p>
            {upcoming.map((b) => (
              <BookingCard
                key={b.id}
                booking={b}
                onCancel={setCancelTarget}
                onReschedule={setRescheduleTarget}
              />
            ))}
          </div>
        )}

        {/* Past / Cancelled */}
        {past.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-wider text-slate-500 font-medium">Past & Cancelled</p>
            {past.map((b) => (
              <BookingCard
                key={b.id}
                booking={b}
                onCancel={setCancelTarget}
                onReschedule={setRescheduleTarget}
              />
            ))}
          </div>
        )}
      </motion.section>

      {/* Cancel confirmation dialog */}
      {cancelTargetBooking && (
        <CancelDialog
          booking={cancelTargetBooking}
          onConfirm={async (id, reason) => {
            await cancelBooking(id, reason);
          }}
          onClose={() => setCancelTarget(null)}
        />
      )}

      {/* Reschedule flow */}
      {rescheduleTargetBooking && (
        <RescheduleFlow
          booking={rescheduleTargetBooking}
          onConfirm={async (id, newSlot) => {
            await rescheduleBooking(id, newSlot);
          }}
          onClose={() => setRescheduleTarget(null)}
        />
      )}
    </>
  );
};
