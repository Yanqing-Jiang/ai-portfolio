import { useState, useRef } from 'react';
import { ChatMessage, ClarifyRequest, ClarifyAnswer } from '../types';
import { apiService } from '../../../services/apiService';
import { useAnalyticsStream } from './useAnalyticsStream';
import { useProcessSteps } from './useProcessSteps';

export const useAnalyticsMemoryStream = () => {
  const [sessionId, setSessionId] = useState<string>('');
  const [pendingClarification, setPendingClarification] = useState<ClarifyRequest | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chartSpec, setChartSpec] = useState<any>(null);
  const [analysis, setAnalysis] = useState('');
  const [sqlQuery, setSqlQuery] = useState('');
  const [dataSample, setDataSample] = useState<any[] | null>(null);
  const [streamingText, setStreamingText] = useState('');

  const streamHook = useAnalyticsStream();
  const stepsHook = useProcessSteps();

  // Chat history management
  const addChatMessage = (message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
    };
    setChatHistory(prev => [...prev, newMessage]);
    return newMessage.id;
  };

  const updateChatMessage = (id: string, updates: Partial<ChatMessage>) => {
    setChatHistory(prev => prev.map(msg => msg.id === id ? { ...msg, ...updates } : msg));
  };

  const submitClarification = async (value: any, request?: ClarifyRequest) => {
    const req = request || pendingClarification;
    if (!req) return;
    try {
      const answer: ClarifyAnswer = {
        session_id: req.session_id || sessionId,
        request_id: req.request_id,
        slot: req.slot,
        value,
        ts: new Date().toISOString(),
      };
      await apiService.post('/api/analytics/memory/clarify', answer);
      setPendingClarification(null);
    } catch (e: any) {
      streamHook.setError(`Failed to submit clarification: ${e?.message || e}`);
    }
  };

  const handleQuery = async (query: string) => {
    if (!query.trim() || streamHook.isLoading) return;
    
    // Add user query to chat history
    addChatMessage({
      type: 'user',
      content: query.trim(),
    });
    
    // Reset state
    setChartSpec(null);
    setAnalysis('');
    setSqlQuery('');
    setStreamingText('');
    setDataSample(null);
    setPendingClarification(null);
    stepsHook.resetSteps();

    const endpoint = `/api/analytics/memory/stream?query=${encodeURIComponent(query.trim())}${sessionId ? `&session_id=${sessionId}` : ''}`;

    await streamHook.startStream(endpoint, (data) => {
      const eventType = data.event || data.type;
      const eventData = data.data || data;
      
      switch (eventType) {
        case 'session_started':
          setSessionId(eventData.session_id);
          break;
          
        case 'status':
          streamHook.setCurrentStatus(eventData.message || '');
          if (eventData.step) {
            stepsHook.updateStepStatus(eventData.step, 'in_progress', [], undefined, eventData.elapsed_ms, eventData.ts);
          }
          break;
          
        case 'intent_draft':
          stepsHook.updateStepStatus('intent_detection', 'in_progress', ['Intent detected; needs clarification'], eventData, eventData.elapsed_ms);
          break;
          
        case 'intent_decided':
        case 'intent_resolved':
          stepsHook.updateStepStatus('intent_detection', 'completed', [], eventData, eventData.elapsed_ms);
          break;
          
        case 'clarification_request':
          setPendingClarification(eventData as ClarifyRequest);
          stepsHook.updateStepStatus('clarification', 'in_progress', [eventData.question]);
          streamHook.setCurrentStatus(`Clarification needed: ${eventData.question}`);
          addChatMessage({
            type: 'clarification',
            content: eventData.question,
            clarifications: [eventData as ClarifyRequest],
          });
          break;
          
        case 'clarification_ack':
          setPendingClarification(null);
          addChatMessage({
            type: 'user',
            content: `${eventData.answer}`,
          });
          stepsHook.updateStepStatus('clarification', 'in_progress', ['Processing your answer...']);
          streamHook.setCurrentStatus('Processing your clarification answer...');
          break;
          
        case 'plan_built':
          stepsHook.updateStepStatus('plan_generation', 'completed', [], { plan: eventData.plan }, eventData.elapsed_ms);
          break;
          
        case 'template_selected':
          stepsHook.updateStepStatus('template_selection', 'completed', [], { template: eventData.template }, eventData.elapsed_ms);
          break;
          
        case 'sql_compiled':
          stepsHook.updateStepStatus('sql_compilation', 'completed', [], { sql: eventData.sql }, eventData.elapsed_ms);
          setSqlQuery(eventData.sql);
          break;
          
        case 'execution_stats':
          stepsHook.updateStepStatus('sql_execution', 'completed', [], { row_count: eventData.row_count, columns: eventData.columns }, eventData.elapsed_ms);
          break;
          
        case 'data_retrieved':
          if (Array.isArray(eventData.sample_data)) {
            setDataSample(eventData.sample_data);
            stepsHook.updateStepStatus('sql_execution', 'completed', [], { 
              rowCount: eventData.row_count,
              sampleData: eventData.sample_data 
            });
          }
          break;
          
        case 'chart_generated':
          setChartSpec(eventData.chart_spec);
          stepsHook.updateStepStatus('chart_generation', 'completed', [], { chart_spec: eventData.chart_spec }, eventData.elapsed_ms);
          break;
          
        case 'analysis_streaming':
          setStreamingText(prev => prev + eventData.text);
          stepsHook.updateStepStatus('analysis_generation', 'in_progress', ['Generating financial analysis...']);
          break;
          
        case 'analysis_complete':
          const finalAnalysis = eventData.text || streamingText;
          setAnalysis(finalAnalysis);
          setStreamingText('');
          stepsHook.updateStepStatus('analysis_generation', 'completed', [], { analysis: finalAnalysis }, eventData.elapsed_ms);
          break;
          
        case 'workflow_complete':
          streamHook.setCurrentStatus('Analytics memory workflow completed!');
          addChatMessage({
            type: 'result',
            content: 'Analysis completed! Here are your results:',
            analysis: analysis,
            chartSpec: chartSpec,
            sqlQuery: sqlQuery,
          });
          break;
          
        case 'done':
          streamHook.setCurrentStatus('Analysis completed successfully!');
          break;
          
        case 'error':
          streamHook.setError(eventData.message || 'Analytics error occurred');
          stepsHook.updateStepStatus(eventData.step || 'unknown', 'error', [eventData.message]);
          break;
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
    setSessionId('');
    setPendingClarification(null);
    setChatHistory([]);
    setChartSpec(null);
    setAnalysis('');
    setSqlQuery('');
    setDataSample(null);
    setStreamingText('');
  };

  return {
    // State
    sessionId,
    pendingClarification,
    chatHistory,
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
    submitClarification,
    stopAnalysis,
    resetAll,
    addChatMessage,
    updateChatMessage,
  };
};