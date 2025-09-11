import { useState } from 'react';
import { useAnalyticsStream } from './useAnalyticsStream';
import { useProcessSteps } from './useProcessSteps';
import { STEP_NAME_SQL, STEP_ORDER_SQL } from '../../../constants/analytics';

export const useAnalyticsSqlStream = () => {
  const [chartSpec, setChartSpec] = useState<any>(null);
  const [analysis, setAnalysis] = useState('');
  const [sqlQuery, setSqlQuery] = useState('');
  const [dataSample, setDataSample] = useState<any[] | null>(null);
  const [streamingText, setStreamingText] = useState('');

  const streamHook = useAnalyticsStream();
  const stepsHook = useProcessSteps({ 
    stepNames: STEP_NAME_SQL, 
    stepOrder: STEP_ORDER_SQL 
  });

  const handleQuery = async (query: string) => {
    if (!query.trim() || streamHook.isLoading) return;
    
    // Reset state
    setChartSpec(null);
    setAnalysis('');
    setSqlQuery('');
    setStreamingText('');
    setDataSample(null);
    stepsHook.resetSteps();

    const endpoint = `/api/analytics/stream?query=${encodeURIComponent(query.trim())}`;

    await streamHook.startStream(endpoint, (data) => {
      const eventType = data.event || data.type;
      const eventData = data.data || data;
      
      switch (eventType) {
        case 'status':
          streamHook.setCurrentStatus(eventData.message || '');
          if (eventData.step) {
            stepsHook.updateStepStatus(
              eventData.step, 
              'in_progress', 
              [], 
              undefined, 
              eventData.elapsed_ms, 
              eventData.ts
            );
          }
          break;
          
        case 'sql_generated':
          setSqlQuery(eventData.sql);
          stepsHook.updateStepStatus('sql', 'completed', [], { sql: eventData.sql }, eventData.elapsed_ms);
          break;
          
        case 'data_retrieved':
          if (Array.isArray(eventData.sample_data)) {
            setDataSample(eventData.sample_data);
            stepsHook.updateStepStatus('table', 'completed', [], { 
              rowCount: eventData.row_count,
              sampleData: eventData.sample_data 
            });
          }
          break;
          
        case 'chart_generated':
          setChartSpec(eventData.chart_spec);
          stepsHook.updateStepStatus('chart', 'completed', [], { chart_spec: eventData.chart_spec }, eventData.elapsed_ms);
          break;
          
        case 'analysis_streaming':
          // Support multiple back-end payload shapes
          {
            const chunk: string =
              typeof eventData?.partial_analysis === 'string'
                ? eventData.partial_analysis
                : typeof eventData?.delta === 'string'
                ? eventData.delta
                : typeof eventData?.text === 'string'
                ? eventData.text
                : ''
            if (chunk) setStreamingText(prev => prev + chunk)
          }
          stepsHook.updateStepStatus('analysis', 'in_progress', ['Generating analysis...']);
          break;
          
        case 'analysis_complete':
          setAnalysis(eventData.analysis || streamingText);
          setStreamingText('');
          stepsHook.updateStepStatus('analysis', 'completed', [], { analysis: eventData.analysis }, eventData.elapsed_ms);
          break;
          
        case 'workflow_complete':
        case 'done':
          streamHook.setCurrentStatus('Analysis complete');
          break;
          
        case 'error':
          stepsHook.updateStepStatus(eventData.step || 'unknown', 'error', [eventData.message]);
          streamHook.setError(eventData.message);
          streamHook.setCurrentStatus(`Error: ${eventData.message}`);
          break;
          
        default:
          console.log(`[SQL Stream] Unhandled event: ${eventType}`, eventData);
      }
    });
  };

  const stopAnalysis = () => {
    streamHook.stopStream();
    stepsHook.stopInProgressSteps();
  };

  const resetAll = () => {
    streamHook.resetState();
    stepsHook.resetSteps();
    setChartSpec(null);
    setAnalysis('');
    setSqlQuery('');
    setDataSample(null);
    setStreamingText('');
  };

  return {
    // State
    chartSpec,
    analysis,
    sqlQuery,
    dataSample,
    streamingText,
    
    // Stream state
    isLoading: streamHook.isLoading,
    error: streamHook.error,
    currentStatus: streamHook.currentStatus,
    
    // Process steps
    processSteps: stepsHook.processSteps,
    
    // Actions
    handleQuery,
    stopAnalysis,
    resetAll,
  };
};
