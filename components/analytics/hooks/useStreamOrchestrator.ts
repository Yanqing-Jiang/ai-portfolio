import { useCallback } from 'react';
import { useAnalyticsStream } from './useAnalyticsStream';

/*
Function: useStreamOrchestrator — called from useAnalyticsMemoryStream to centralize starting and stopping the analytics SSE stream. Invokes useAnalyticsStream.startStream/stopStream and delegates event routing to a provided onEvent callback. Exists to slim useAnalyticsMemoryStream and prepare full event orchestration extraction.
*/
type StreamOrchestratorDeps = {
  streamHook: ReturnType<typeof useAnalyticsStream>;
};

type StreamOrchestrator = {
  startStream: (endpoint: string, onEvent: (data: any) => void) => Promise<void>;
  stopStream: () => void;
  streamHook: ReturnType<typeof useAnalyticsStream>;
};

export const useStreamOrchestrator = ({ streamHook }: StreamOrchestratorDeps): StreamOrchestrator => {
  const startStream = useCallback(
    async (endpoint: string, onEvent: (data: any) => void) => {
      await streamHook.startStream(endpoint, onEvent);
    },
    [streamHook],
  );

  const stopStream = useCallback(() => {
    streamHook.stopStream();
  }, [streamHook]);

  return {
    startStream,
    stopStream,
    streamHook,
  };
};

