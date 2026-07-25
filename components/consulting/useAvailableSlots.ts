import { useState, useEffect, useCallback, useRef } from 'react';
import { configService } from '@/services/config';

export interface Slot {
  start: string; // ISO 8601
  end: string;
}

interface UseAvailableSlotsResult {
  slots: Slot[];
  loading: boolean;
  error: string | null;
  timezone: string;
  /** True only while a *current, successful* response says the backend can book.
   *  Any other state — loading, error, no date, an older backend that doesn't
   *  report the field — is false, because offering a time we cannot honour is
   *  worse than showing the email fallback. */
  bookable: boolean;
  refetch: () => void;
}

export function useAvailableSlots(date: string | null, sessionType: '30' | '60'): UseAvailableSlotsResult {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timezone, setTimezone] = useState('America/Los_Angeles');
  const [bookable, setBookable] = useState(false);
  // Only the newest request may write state. Without this, switching from date A
  // to date B and having A resolve second leaves A's slots on screen under B's
  // heading — and a visitor books a time they never chose.
  const requestId = useRef(0);

  const fetchSlots = useCallback(async () => {
    const id = ++requestId.current;

    if (!date) {
      setSlots([]);
      setBookable(false);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setBookable(false);

    try {
      const backendUrl = configService.getBackendUrl().replace(/\/$/, '');
      const response = await fetch(
        `${backendUrl}/api/booking/slots?date=${date}&session_type=${sessionType}`
      );

      if (!response.ok) {
        throw new Error(`Failed to load available times (${response.status})`);
      }

      const data = await response.json();
      if (id !== requestId.current) return; // superseded

      setSlots(data.slots || []);
      setTimezone(data.timezone || 'America/Los_Angeles');
      // Must be explicitly true. A backend that predates the flag served mock
      // slots when its calendar was unconfigured, so treating "absent" as
      // bookable would offer unbookable times during a partial rollout.
      setBookable(data.bookable === true);
    } catch (err) {
      if (id !== requestId.current) return;
      setError(err instanceof Error ? err.message : 'Failed to load slots');
      setSlots([]);
      setBookable(false);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [date, sessionType]);

  useEffect(() => {
    fetchSlots();
  }, [fetchSlots]);

  return { slots, loading, error, timezone, bookable, refetch: fetchSlots };
}
