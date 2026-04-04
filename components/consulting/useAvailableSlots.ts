import { useState, useEffect, useCallback } from 'react';
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
  refetch: () => void;
}

export function useAvailableSlots(date: string | null, sessionType: '30' | '60'): UseAvailableSlotsResult {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timezone, setTimezone] = useState('America/Los_Angeles');

  const fetchSlots = useCallback(async () => {
    if (!date) {
      setSlots([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const backendUrl = configService.getBackendUrl().replace(/\/$/, '');
      const response = await fetch(
        `${backendUrl}/api/booking/slots?date=${date}&session_type=${sessionType}`
      );

      if (!response.ok) {
        throw new Error(`Failed to load available times (${response.status})`);
      }

      const data = await response.json();
      setSlots(data.slots || []);
      setTimezone(data.timezone || 'America/Los_Angeles');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load slots');
      setSlots([]);
    } finally {
      setLoading(false);
    }
  }, [date, sessionType]);

  useEffect(() => {
    fetchSlots();
  }, [fetchSlots]);

  return { slots, loading, error, timezone, refetch: fetchSlots };
}
