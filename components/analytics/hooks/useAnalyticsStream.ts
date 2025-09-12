import { useState, useRef } from 'react';
import { apiService } from '../../../services/apiService';

export const useAnalyticsStream = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [currentStatus, setCurrentStatus] = useState('Ready to analyze financial data...');
  const abortControllerRef = useRef<AbortController | null>(null);

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
    setCurrentStatus('Ready to analyze financial data...');
  };

  return {
    isLoading,
    error,
    currentStatus,
    setCurrentStatus,
    setError,
    startStream,
    stopStream,
    resetState,
  };
};