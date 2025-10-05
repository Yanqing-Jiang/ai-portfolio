import { useState } from 'react';
import { useAnalyticsStream } from './useAnalyticsStream';
import { useProcessSteps } from './useProcessSteps';
import { STEP_NAME_SQL, STEP_ORDER_SQL } from '../../../constants/analytics';

const STEP_ALIASES: Record<string, string> = {
  plan_and_select_template: 'schema',
  schema_validation: 'schema',
  sql_validation: 'schema',
  sql_compilation: 'sql',
  sql_generation: 'sql',
  table_selection: 'table',
  sql_execution: 'table',
  data_retrieval: 'table',
  chart_generation: 'chart',
  chart_rendering: 'chart',
  analysis_generation: 'analysis',
};

const normalizeStepId = (rawStep?: string): string => {
  if (!rawStep) return '';
  const normalized = rawStep.toString().toLowerCase();
  return STEP_ALIASES[normalized] || normalized;
};

const toThinkingList = (value: unknown): string[] => {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value
      .map((entry) => (typeof entry === 'string' ? entry : ''))
      .filter(Boolean);
  }
  if (typeof value === 'string') {
    return value.trim() ? [value] : [];
  }
  return [];
};

const extractStepDetails = (data: any) => {
  if (!data || typeof data !== 'object') {
    return undefined;
  }
  const {
    step,
    message,
    msg,
    thinking,
    sequence,
    seq,
    parallelGroup,
    parallel_group,
    elapsed_ms,
    elapsed,
    ts,
    timestamp,
    status,
    ...rest
  } = data;
  return Object.keys(rest).length ? rest : undefined;
};

export const useAnalyticsSqlStream = () => {
  const [chartSpec, setChartSpec] = useState<any>(null);
  const [analysis, setAnalysis] = useState('');
  const [sqlQuery, setSqlQuery] = useState('');
  const [dataSample, setDataSample] = useState<any[] | null>(null);
  const [streamingText, setStreamingText] = useState('');

  const streamHook = useAnalyticsStream();
  const stepsHook = useProcessSteps({
    stepNames: STEP_NAME_SQL,
    stepOrder: STEP_ORDER_SQL,
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
        case 'progress': {
          const statusMessage = eventData.message || eventData.msg || '';
          if (statusMessage) {
            streamHook.setCurrentStatus(statusMessage);
          }
          const resolvedStep = normalizeStepId(eventData.step);
          if (resolvedStep) {
            stepsHook.updateStepStatus(
              resolvedStep,
              'in_progress',
              toThinkingList(eventData.thinking),
              undefined,
              eventData.elapsed_ms ?? eventData.elapsed,
              eventData.ts ?? eventData.timestamp,
              eventData.sequence ?? eventData.seq,
              eventData.parallel_group ?? eventData.parallelGroup,
            );
          }
          break;
        }

        case 'sql_compiled': {
          const resolvedStep = normalizeStepId(eventData.step) || 'sql';
          stepsHook.updateStepStatus(
            resolvedStep,
            'completed',
            toThinkingList(eventData.thinking),
            extractStepDetails(eventData),
            eventData.elapsed_ms ?? eventData.elapsed,
            eventData.ts ?? eventData.timestamp,
            eventData.sequence ?? eventData.seq,
            eventData.parallel_group ?? eventData.parallelGroup,
          );
          break;
        }

        case 'sql_generated': {
          const resolvedStep = normalizeStepId(eventData.step) || 'sql';
          setSqlQuery(eventData.sql);
          stepsHook.updateStepStatus(
            resolvedStep,
            'completed',
            [],
            { sql: eventData.sql },
            eventData.elapsed_ms ?? eventData.elapsed,
            eventData.ts ?? eventData.timestamp,
          );
          break;
        }

        case 'data_retrieved': {
          const resolvedStep = normalizeStepId(eventData.step) || 'table';
          if (Array.isArray(eventData.sample_data)) {
            setDataSample(eventData.sample_data);
            stepsHook.updateStepStatus(
              resolvedStep,
              'completed',
              [],
              {
                rowCount: eventData.row_count,
                sampleData: eventData.sample_data,
              },
              eventData.elapsed_ms ?? eventData.elapsed,
              eventData.ts ?? eventData.timestamp,
            );
          }
          break;
        }

        case 'chart_generated': {
          const resolvedStep = normalizeStepId(eventData.step) || 'chart';
          setChartSpec(eventData.chart_spec);
          stepsHook.updateStepStatus(
            resolvedStep,
            'completed',
            [],
            { chart_spec: eventData.chart_spec },
            eventData.elapsed_ms ?? eventData.elapsed,
            eventData.ts ?? eventData.timestamp,
          );
          break;
        }

        case 'analysis_streaming': {
          const chunk: string =
            typeof eventData?.partial_analysis === 'string'
              ? eventData.partial_analysis
              : typeof eventData?.delta === 'string'
              ? eventData.delta
              : typeof eventData?.text === 'string'
              ? eventData.text
              : '';
          if (chunk) setStreamingText((prev) => prev + chunk);
          const resolvedStep = normalizeStepId(eventData.step) || 'analysis';
          stepsHook.updateStepStatus(
            resolvedStep,
            'in_progress',
            ['Generating analysis...'],
            undefined,
            eventData.elapsed_ms ?? eventData.elapsed,
            eventData.ts ?? eventData.timestamp,
          );
          break;
        }

        case 'analysis_complete': {
          const finalAnalysis = eventData.analysis || streamingText;
          setAnalysis(finalAnalysis);
          setStreamingText('');
          const resolvedStep = normalizeStepId(eventData.step) || 'analysis';
          stepsHook.updateStepStatus(
            resolvedStep,
            'completed',
            [],
            { analysis: finalAnalysis },
            eventData.elapsed_ms ?? eventData.elapsed,
            eventData.ts ?? eventData.timestamp,
          );
          break;
        }

        case 'result': {
          const resolvedStep = normalizeStepId(eventData.step);
          if (resolvedStep) {
            stepsHook.updateStepStatus(
              resolvedStep,
              'completed',
              toThinkingList(eventData.thinking),
              extractStepDetails(eventData),
              eventData.elapsed_ms ?? eventData.elapsed,
              eventData.ts ?? eventData.timestamp,
              eventData.sequence ?? eventData.seq,
              eventData.parallel_group ?? eventData.parallelGroup,
            );
            if (resolvedStep === 'analysis' && typeof eventData.analysis === 'string') {
              setAnalysis(eventData.analysis);
            }
          }
          break;
        }

        case 'workflow_complete':
        case 'done':
          streamHook.setCurrentStatus('Analysis complete');
          break;

        case 'error': {
          const resolvedStep = normalizeStepId(eventData.step) || 'unknown';
          const message = eventData.message || eventData.error || 'An error occurred';
          stepsHook.updateStepStatus(
            resolvedStep,
            'error',
            toThinkingList(eventData.thinking).concat(message ? [message] : []),
            extractStepDetails(eventData),
            eventData.elapsed_ms ?? eventData.elapsed,
            eventData.ts ?? eventData.timestamp,
            eventData.sequence ?? eventData.seq,
            eventData.parallel_group ?? eventData.parallelGroup,
          );
          streamHook.setError(message);
          streamHook.setCurrentStatus(`Error: ${message}`);
          break;
        }

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
