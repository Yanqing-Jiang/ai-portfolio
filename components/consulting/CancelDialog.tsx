import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Loader2 } from 'lucide-react';
import type { BookingEntry } from './useMyBookings';

interface CancelDialogProps {
  booking: BookingEntry | null;
  onConfirm: (id: string, reason: string) => Promise<void>;
  onClose: () => void;
}

export const CancelDialog: React.FC<CancelDialogProps> = ({ booking, onConfirm, onClose }) => {
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!booking) return null;

  const handleConfirm = async () => {
    setLoading(true);
    setError(null);
    try {
      await onConfirm(booking.id, reason);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cancellation failed');
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
          className="bg-slate-900 border border-white/10 rounded-2xl p-6 max-w-md w-full space-y-5"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-red-400" />
            </div>
            <h3 className="text-lg font-bold text-white">Cancel Booking</h3>
          </div>

          <div className="space-y-2 text-sm text-slate-400">
            <p>
              {booking.refund_eligible
                ? 'You will receive a full refund since the session is more than 24 hours away.'
                : 'No refund is available as the session is less than 24 hours away.'}
            </p>
            <p className="text-xs">
              {booking.session_type === '30' ? '30 min' : '60 min'} session
              {booking.refund_eligible && ` — $${(booking.amount_cents / 100).toFixed(0)} refund`}
            </p>
          </div>

          <textarea
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={200}
            className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm outline-none
                       focus:ring-2 ring-red-500/30 text-white placeholder-slate-500 resize-none"
            placeholder="Reason for cancellation (optional)"
          />

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 py-2.5 rounded-xl border border-white/10 text-slate-300 text-sm font-medium
                         hover:bg-white/5 transition-colors"
            >
              Keep Booking
            </button>
            <button
              onClick={handleConfirm}
              disabled={loading}
              className="flex-1 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white text-sm font-medium
                         transition-colors disabled:opacity-50"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Cancelling...
                </span>
              ) : (
                'Cancel Booking'
              )}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};
