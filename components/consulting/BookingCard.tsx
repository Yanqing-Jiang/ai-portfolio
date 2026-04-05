import React from 'react';
import { Clock, Calendar, Video, XCircle, RefreshCw } from 'lucide-react';
import type { BookingEntry } from './useMyBookings';

const STATUS_STYLES: Record<string, { label: string; color: string }> = {
  confirmed: { label: 'Confirmed', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' },
  cancelled: { label: 'Cancelled', color: 'text-red-400 bg-red-500/10 border-red-500/30' },
  refunded: { label: 'Refunded', color: 'text-amber-400 bg-amber-500/10 border-amber-500/30' },
  rescheduled: { label: 'Rescheduled', color: 'text-blue-400 bg-blue-500/10 border-blue-500/30' },
  calendar_failed: { label: 'Confirmed', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' },
};

function formatDate(iso: string) {
  try {
    return new Intl.DateTimeFormat('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      timeZoneName: 'short',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

interface BookingCardProps {
  booking: BookingEntry;
  onCancel: (id: string) => void;
  onReschedule: (id: string) => void;
}

export const BookingCard: React.FC<BookingCardProps> = ({ booking, onCancel, onReschedule }) => {
  const statusInfo = STATUS_STYLES[booking.status] || { label: booking.status, color: 'text-slate-400 bg-slate-500/10 border-slate-500/30' };
  const isPast = new Date(booking.slot_start) < new Date();

  return (
    <div className={`rounded-xl border bg-white/[0.03] p-5 space-y-4 transition-all ${isPast ? 'border-white/5 opacity-60' : 'border-white/10'}`}>
      {/* Header: session type + status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-blue-400" />
          <span className="text-white font-medium">
            {booking.session_type === '30' ? '30 min' : '60 min'} session
          </span>
        </div>
        <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${statusInfo.color}`}>
          {statusInfo.label}
        </span>
      </div>

      {/* Date/time */}
      <div className="flex items-center gap-2 text-sm">
        <Calendar className="w-4 h-4 text-purple-400 flex-shrink-0" />
        <span className="text-slate-300">{formatDate(booking.slot_start)}</span>
      </div>

      {/* Meet link */}
      {booking.meet_link && booking.status === 'confirmed' && (
        <div className="flex items-center gap-2 text-sm">
          <Video className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <a
            href={booking.meet_link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400 hover:text-blue-300 underline"
          >
            Join Google Meet
          </a>
        </div>
      )}

      {/* Actions */}
      {(booking.can_cancel || booking.can_reschedule) && (
        <div className="flex gap-3 pt-2 border-t border-white/5">
          {booking.can_reschedule && (
            <button
              onClick={() => onReschedule(booking.id)}
              className="flex items-center gap-1.5 text-xs font-medium text-blue-400 hover:text-blue-300 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Reschedule
            </button>
          )}
          {booking.can_cancel && (
            <button
              onClick={() => onCancel(booking.id)}
              className="flex items-center gap-1.5 text-xs font-medium text-red-400 hover:text-red-300 transition-colors"
            >
              <XCircle className="w-3.5 h-3.5" />
              Cancel
            </button>
          )}
        </div>
      )}
    </div>
  );
};
