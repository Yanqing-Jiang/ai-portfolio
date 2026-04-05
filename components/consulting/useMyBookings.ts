import { useState, useEffect, useCallback } from 'react';
import { authService } from '@/services/auth';
import { configService } from '@/services/config';

export interface BookingEntry {
  id: string;
  session_type: '30' | '60';
  slot_start: string;
  slot_end: string;
  status: string;
  meet_link: string | null;
  amount_cents: number;
  created_at: string;
  can_cancel: boolean;
  can_reschedule: boolean;
  refund_eligible: boolean;
}

export function useMyBookings() {
  const [bookings, setBookings] = useState<BookingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBookings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = await authService.getAuthHeaders();
      if (!headers.Authorization) {
        setBookings([]);
        return;
      }
      const backendUrl = configService.getBackendUrl().replace(/\/$/, '');
      const res = await fetch(`${backendUrl}/api/booking/my-bookings`, { headers });
      if (!res.ok) throw new Error(`Failed to fetch bookings (${res.status})`);
      const data = await res.json();
      setBookings(data.bookings);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load bookings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBookings();
  }, [fetchBookings]);

  const cancelBooking = async (id: string, reason?: string) => {
    const headers = await authService.getAuthHeaders();
    const backendUrl = configService.getBackendUrl().replace(/\/$/, '');
    const res = await fetch(`${backendUrl}/api/booking/${id}/cancel`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason || '' }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Cancellation failed');
    }
    const result = await res.json();
    await fetchBookings();
    return result;
  };

  const rescheduleBooking = async (id: string, newSlotStart: string) => {
    const headers = await authService.getAuthHeaders();
    const backendUrl = configService.getBackendUrl().replace(/\/$/, '');
    const res = await fetch(`${backendUrl}/api/booking/${id}/reschedule`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_slot_start: newSlotStart }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Reschedule failed');
    }
    const result = await res.json();
    await fetchBookings();
    return result;
  };

  return { bookings, loading, error, refetch: fetchBookings, cancelBooking, rescheduleBooking };
}
