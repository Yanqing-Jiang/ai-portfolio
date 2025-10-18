import { useState, useRef } from 'react';
import { apiService } from '../../../services/apiService';

export const useAnalyticsStream = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState<{ text: string; timestamp: string | null }>({
    text: '',
    timestamp: null,
  });
  const abortControllerRef = useRef<AbortController | null>(null);

  const setCurrentStatus = (text: string, options?: { timestamp?: string | null }) => {
    const nextTimestamp =
      options && options.hasOwnProperty('timestamp')
        ? options.timestamp ?? null
        : new Date().toISOString();
    setStatus({ text, timestamp: nextTimestamp });
  };

  const startStream = async (
    endpoint: string,
    onEvent: (data: any) => void,
    onComplete?: () => void
  ) => {
    setIsLoading(true);
    setError('');
    abortControllerRef.current = new AbortController();

    const handleError = (error: string, needsAuth?: boolean) => {
      setError(error);
      setCurrentStatus(`Error: ${error}`);
    };

    try {
      await apiService.streamWithAuth(
        endpoint,
        onEvent,
        handleError,
        onComplete,
        abortControllerRef.current.signal
      );
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        const errorMsg = e?.message || e || 'Analytics stream failed';
        handleError(errorMsg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const stopStream = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsLoading(false);
    setCurrentStatus('Analysis stopped');
  };

  const resetState = () => {
    setError('');
    setCurrentStatus('', { timestamp: new Date().toISOString() });
  };

  return {
    isLoading,
    error,
    currentStatus: status.text,
    statusTimestamp: status.timestamp,
    setCurrentStatus,
    setError,
    startStream,
    stopStream,
    resetState,
  };
};
