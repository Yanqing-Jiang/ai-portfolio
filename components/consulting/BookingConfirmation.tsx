import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, Clock, Loader2, Calendar, Video } from 'lucide-react';
import { configService } from '@/services/config';

interface BookingDetails {
  status: string;
  session_type: string;
  slot_start: string;
  slot_end: string;
  client_name: string;
  meet_link: string | null;
}

interface BookingConfirmationProps {
  stripeSessionId: string;
  onBack: () => void;
}

export const BookingConfirmation: React.FC<BookingConfirmationProps> = ({
  stripeSessionId,
  onBack,
}) => {
  const [booking, setBooking] = useState<BookingDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [pollCount, setPollCount] = useState(0);

  useEffect(() => {
    if (!stripeSessionId) return;

    const fetchBooking = async () => {
      try {
        const backendUrl = configService.getBackendUrl().replace(/\/$/, '');
        const res = await fetch(`${backendUrl}/api/booking/confirmation/${stripeSessionId}`);
        if (res.ok) {
          const data = await res.json();
          setBooking(data);
          if (data.status !== 'hold') {
            setLoading(false);
            return;
          }
        }
      } catch {
        // Continue polling
      }
      setPollCount((c) => c + 1);
    };

    fetchBooking();
    const interval = setInterval(fetchBooking, 2000);

    // Stop polling after 30 seconds
    const timeout = setTimeout(() => {
      clearInterval(interval);
      setLoading(false);
    }, 30000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [stripeSessionId]);

  const formatDate = (iso: string) => {
    try {
      return new Intl.DateTimeFormat('en-US', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        timeZoneName: 'short',
      }).format(new Date(iso));
    } catch {
      return iso;
    }
  };

  if (loading && (!booking || booking.status === 'hold')) {
    return (
      <div className="text-center py-20 space-y-6">
        <Loader2 className="w-12 h-12 mx-auto text-blue-400 animate-spin" />
        <h2 className="text-2xl font-bold text-white">Confirming your booking...</h2>
        <p className="text-slate-400 text-sm">
          {pollCount > 10
            ? 'Payment received. You\'ll receive a calendar invite shortly.'
            : 'Setting up your session and calendar invite.'}
        </p>
      </div>
    );
  }

  const isConfirmed = booking?.status === 'confirmed' || booking?.status === 'calendar_failed';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center py-16 space-y-8 max-w-lg mx-auto"
    >
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', stiffness: 200, delay: 0.2 }}
      >
        <CheckCircle className="w-20 h-20 mx-auto text-emerald-400" />
      </motion.div>

      <div className="space-y-2">
        <h2 className="text-3xl font-bold text-white">
          {isConfirmed ? 'Booking Confirmed!' : 'Payment Received'}
        </h2>
        <p className="text-slate-400">
          {isConfirmed
            ? 'Check your email for a calendar invite with the meeting link.'
            : 'Your booking is being processed. You\'ll receive a calendar invite shortly.'}
        </p>
      </div>

      {booking && (
        <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6 text-left space-y-4">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-blue-400 flex-shrink-0" />
            <div>
              <p className="text-sm text-slate-400">Session</p>
              <p className="text-white font-medium">
                {booking.session_type === '30' ? '30 minutes' : '60 minutes'} consultation
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Calendar className="w-5 h-5 text-purple-400 flex-shrink-0" />
            <div>
              <p className="text-sm text-slate-400">When</p>
              <p className="text-white font-medium">{formatDate(booking.slot_start)}</p>
            </div>
          </div>
          {booking.meet_link && (
            <div className="flex items-center gap-3">
              <Video className="w-5 h-5 text-emerald-400 flex-shrink-0" />
              <div>
                <p className="text-sm text-slate-400">Meeting</p>
                <a
                  href={booking.meet_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 font-medium underline"
                >
                  Join Google Meet
                </a>
              </div>
            </div>
          )}
        </div>
      )}

      <button
        onClick={onBack}
        className="text-sm text-slate-400 hover:text-white transition-colors"
      >
        Back to booking page
      </button>
    </motion.div>
  );
};
