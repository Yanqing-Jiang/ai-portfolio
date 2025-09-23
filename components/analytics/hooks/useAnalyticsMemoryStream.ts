import { useState, useRef } from 'react';
import { ChatMessage, ClarifyRequest, ClarifyAnswer } from '../types';
import { apiService } from '../../../services/apiService';
import { useAnalyticsStream } from './useAnalyticsStream';
import { useProcessSteps } from './useProcessSteps';

export const useAnalyticsMemoryStream = (mode: 'memory' | 'supervisor' = 'memory') => {
  const [sessionId, setSessionId] = useState<string>('');
  const [pendingClarification, setPendingClarification] = useState<ClarifyRequest | null>(null);
  const [supervisorState, setSupervisorState] = useState<{ plan?: any }>({});
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chartSpec, setChartSpec] = useState<any>(null);
  const [analysis, setAnalysis] = useState('');
  const [sqlQuery, setSqlQuery] = useState('');
  const [dataSample, setDataSample] = useState<any[] | null>(null);
  const [streamingText, setStreamingText] = useState('');
  
  // Ref to accumulate workflow data throughout the stream to avoid async state issues
  const workflowDataRef = useRef<{
    chartSpec: any;
    analysis: string;
    sqlQuery: string;
    dataSample: any[] | null;
    streamingText: string;
  }>({
    chartSpec: null,
    analysis: '',
    sqlQuery: '',
    dataSample: null,
    streamingText: ''
  });

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
    if (!query.trim()) return;
    
    // Stop any existing stream before starting a new one
    if (streamHook.isLoading) {
      streamHook.stopStream();
      // Wait a brief moment for the stream to be properly closed
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    // Add user query to chat history
    addChatMessage({
      type: 'user',
      content: query.trim(),
    });
    
    // Reset only temporary state for new query (keep results in chat history)
    setStreamingText('');
    setPendingClarification(null);
    stepsHook.resetSteps();
    
    // Reset workflow data ref for new query
    workflowDataRef.current = {
      chartSpec: null,
      analysis: '',
      sqlQuery: '',
      dataSample: null,
      streamingText: ''
    };

    const baseEndpoint = mode === 'supervisor' 
      ? `/api/analytics/memory/supervisor/stream`
      : `/api/analytics/memory/stream`;
    
    const endpoint = `${baseEndpoint}?query=${encodeURIComponent(query.trim())}${sessionId ? `&session_id=${sessionId}` : ''}`;

    await streamHook.startStream(endpoint, (data) => {
      const eventType = data.event || data.type;
      const eventData = data.data || data;
      const eventVisibility =
        typeof data.event_type === 'string' ? data.event_type : 'user';
      const isThinkingEvent = eventVisibility === 'thinking';
      
      switch (eventType) {
        case 'session_started':
          setSessionId(eventData.session_id);
          break;
          
        case 'status':
          streamHook.setCurrentStatus(eventData.message || '');
          if (eventData.step) {
            const thinkingLogs: string[] = isThinkingEvent && eventData.message ? [eventData.message] : [];
            stepsHook.updateStepStatus(eventData.step, 'in_progress', thinkingLogs, undefined, eventData.elapsed_ms, eventData.ts);
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
          console.log('🔍 [DEBUG] Received clarification_request:', eventData);
          setPendingClarification(eventData as ClarifyRequest);
          stepsHook.updateStepStatus('clarification', 'in_progress', [eventData.question]);
          streamHook.setCurrentStatus(`Clarification needed: ${eventData.question}`);
          const clarificationMessage = {
            type: 'clarification' as const,
            content: eventData.question,
            clarifications: [eventData as ClarifyRequest],
          };
          console.log('🔍 [DEBUG] Adding clarification message:', clarificationMessage);
          addChatMessage(clarificationMessage);
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
          // Combined planning step for streamlined agent mode
          stepsHook.updateStepStatus('plan_and_select_template', 'in_progress', ['Plan built'], { plan: eventData.plan }, eventData.elapsed_ms);
          break;

        case 'template_selected':
          // Complete combined planning + selection step
          stepsHook.updateStepStatus('plan_and_select_template', 'completed', [
            eventData?.template?.id ? `Selected template: ${eventData.template.id}` : 'Template selected'
          ], { template: eventData.template }, eventData.elapsed_ms);
          break;
          
        case 'sql_compiled':
          // Compilation stats only; SQL text may arrive in 'sql_generated'
          stepsHook.updateStepStatus('sql_compilation', 'completed', [
            `SQL compiled (len: ${eventData.sql_length})`
          ], {
            sql_length: eventData.sql_length,
            template_used: eventData.template_used,
          }, eventData.elapsed_ms);
          break;

        case 'sql_generated':
          if (typeof eventData.sql === 'string') {
            setSqlQuery(eventData.sql);
            workflowDataRef.current.sqlQuery = eventData.sql;
          }
          stepsHook.updateStepStatus('sql_validation', 'completed', [], { sql: eventData.sql }, eventData.elapsed_ms);
          break;
          
        case 'execution_stats':
          stepsHook.updateStepStatus('sql_execution', 'completed', [], { row_count: eventData.row_count, columns: eventData.columns }, eventData.elapsed_ms);
          break;
          
        case 'data_retrieved':
          if (Array.isArray(eventData.sample_data)) {
            setDataSample(eventData.sample_data);
            workflowDataRef.current.dataSample = eventData.sample_data;
            stepsHook.updateStepStatus('sql_execution', 'completed', [], { 
              rowCount: eventData.row_count,
              sampleData: eventData.sample_data 
            });
          }
          break;
          
        case 'chart_generated':
          setChartSpec(eventData.chart_spec);
          workflowDataRef.current.chartSpec = eventData.chart_spec;
          stepsHook.updateStepStatus('chart_generation', 'completed', [], { chart_spec: eventData.chart_spec }, eventData.elapsed_ms);
          break;
          
        case 'analysis_streaming':
          if (!isThinkingEvent) {
            const chunk: string =
              typeof eventData?.partial_analysis === 'string'
                ? eventData.partial_analysis
                : typeof eventData?.delta === 'string'
                ? eventData.delta
                : typeof eventData?.text === 'string'
                ? eventData.text
                : '';
            if (chunk) {
              setStreamingText(prev => {
                const newText = prev + chunk;
                workflowDataRef.current.streamingText = newText;
                return newText;
              });
            }
          }
          stepsHook.updateStepStatus('analysis_generation', 'in_progress', ['Generating financial analysis...']);
          break;
          
        case 'analysis_complete':
          const finalAnalysis =
            !isThinkingEvent
              ? eventData.analysis || workflowDataRef.current.streamingText
              : eventData.analysis;
          if (!isThinkingEvent && typeof finalAnalysis === 'string') {
            setAnalysis(finalAnalysis);
            workflowDataRef.current.analysis = finalAnalysis;
          }
          setStreamingText('');
          workflowDataRef.current.streamingText = '';
          stepsHook.updateStepStatus('short_financial_analysis', 'completed', ['Short financial analysis complete'], { analysis: finalAnalysis }, eventData.elapsed_ms);
          stepsHook.updateStepStatus('analysis_generation', 'completed', [], { analysis: finalAnalysis }, eventData.elapsed_ms);
          break;

        // Optional richer logs for agent demo
        case 'rag_trace':
          stepsHook.updateStepStatus('plan_and_select_template', 'in_progress', ['RAG retrieved candidates'], {
            candidates: eventData.candidates,
            selected: eventData.selected
          }, eventData.elapsed_ms);
          break;

        case 'thinking_log':
          stepsHook.updateStepStatus('tool_execution', 'in_progress', [eventData.message]);
          break;
          
        // ===== NEW ENHANCED EVENTS =====
        case 'classification_started':
          stepsHook.updateStepStatus('classification', 'in_progress', ['Starting query classification...'], { model: eventData.model }, undefined, eventData.ts);
          streamHook.setCurrentStatus('Classifying query...');
          break;

        case 'classification_reasoning':
          stepsHook.updateStepStatus('classification', 'in_progress', [eventData.thinking || 'Analyzing query type...'], {
            confidence: eventData.confidence,
            category: eventData.category
          }, undefined, eventData.ts);
          break;

        case 'classification_complete':
          stepsHook.updateStepStatus('classification', 'completed', [
            eventData.is_financial ? 'Query classified as financial analytics' : 'Query classified as non-financial'
          ], {
            is_financial: eventData.is_financial,
            category: eventData.category,
            confidence: eventData.confidence
          }, eventData.elapsed_ms, eventData.ts);
          break;

        case 'classification_error':
          stepsHook.updateStepStatus('classification', 'error', [`Classification failed: ${eventData.error}`], undefined, eventData.elapsed_ms, eventData.ts);
          break;

        case 'classification_fallback':
          stepsHook.updateStepStatus('classification', 'completed', [`Fallback to ${eventData.method}`], { method: eventData.method }, undefined, eventData.ts);
          break;

        case 'intent_detection_started':
          stepsHook.updateStepStatus('intent_detection', 'in_progress', ['Detecting query intent...'], undefined, undefined, eventData.ts);
          streamHook.setCurrentStatus('Analyzing query intent...');
          break;

        case 'intent_detection_complete':
          stepsHook.updateStepStatus('intent_detection', 'completed', [
            `Intent: ${eventData.intent_key} (${Math.round((eventData.confidence || 0) * 100)}%)`
          ], {
            intent_key: eventData.intent_key,
            confidence: eventData.confidence,
            slots_detected: eventData.slots_detected
          }, undefined, eventData.ts);
          break;

        case 'schema_validation_started':
          stepsHook.updateStepStatus('schema_validation', 'in_progress', ['Validating required fields...'], undefined, undefined, eventData.ts);
          streamHook.setCurrentStatus('Validating schema...');
          break;

        case 'schema_validation_complete':
          const validationPassed = eventData.validation_passed;
          stepsHook.updateStepStatus('schema_validation', validationPassed ? 'completed' : 'in_progress', [
            validationPassed ? 'All required fields present' : `Missing: ${eventData.missing_fields?.join(', ')}`
          ], {
            required_fields: eventData.required_fields,
            provided_fields: eventData.provided_fields,
            missing_fields: eventData.missing_fields,
            validation_passed: validationPassed
          }, undefined, eventData.ts);
          break;

        case 'clarification_needed':
          stepsHook.updateStepStatus('clarification', 'in_progress', [`Missing fields: ${eventData.missing_fields?.join(', ')}`], { missing_fields: eventData.missing_fields }, undefined, eventData.ts);
          break;

        case 'clarification_skipped':
          stepsHook.updateStepStatus('clarification', 'completed', [eventData.reason || 'Clarification not needed'], undefined, undefined, eventData.ts);
          break;

        case 'intent_finalized':
          stepsHook.updateStepStatus('intent_detection', 'completed', ['Intent and schema finalized'], eventData, undefined, eventData.ts);
          break;

        case 'tool_planning_started':
          stepsHook.updateStepStatus('tool_planning', 'in_progress', [eventData.message || 'Planning tool execution...'], { intent_key: eventData.intent_key }, undefined, eventData.ts);
          streamHook.setCurrentStatus('Agent planning tools...');
          break;

        case 'tool_selection_reasoning':
          stepsHook.updateStepStatus('tool_planning', 'in_progress', [`Strategy: ${eventData.strategy}`], {
            available_tools: eventData.available_tools,
            strategy: eventData.strategy
          }, undefined, eventData.ts);
          break;

        // ===== SUPERVISOR MODE EVENTS =====
        case 'planning_proposed':
          setSupervisorState(prev => ({ ...prev, plan: eventData }));
          stepsHook.updateStepStatus('planning', 'completed', [eventData.plan]);
          streamHook.setCurrentStatus('Plan proposed by supervisor agent');
          if (!isThinkingEvent) {
            addChatMessage({
              type: 'assistant',
              content: `**Plan Proposed:**\n${eventData.plan}\n\n**Steps:** ${eventData.steps?.length || 0} tools planned`,
            });
          }
          break;

        case 'tool_start':
          stepsHook.updateStepStatus('tool_execution', 'in_progress', [`Executing: ${eventData.tool}`]);
          streamHook.setCurrentStatus(`Executing tool: ${eventData.tool}`);
          break;
          
        case 'tool_end':
          // Tool completed - keep execution phase active until all tools done
          stepsHook.updateStepStatus('tool_execution', 'in_progress', [`Completed: ${eventData.tool}`]);
          break;
          
        case 'tool_error':
          stepsHook.updateStepStatus('tool_execution', 'error', [`Error in ${eventData.tool}: ${eventData.error}`]);
          streamHook.setCurrentStatus(`Tool error: ${eventData.error}`);
          addChatMessage({
            type: 'assistant',
            content: `⚠️ **Tool Error:** ${eventData.tool} - ${eventData.error}`,
          });
          break;
          
        case 'final_summary':
          stepsHook.updateStepStatus('finalization', 'completed', ['Workflow summary generated']);
          streamHook.setCurrentStatus('Supervisor workflow completed!');
          if (!isThinkingEvent) {
            addChatMessage({
              type: 'assistant',
              content: `📊 **Final Summary:**\n\n**SQL:** ${eventData.sql_summary}\n**Chart:** ${eventData.chart_summary}\n\n**Key Findings:**\n${eventData.key_findings?.map((f: string) => `• ${f}`).join('\n') || 'No findings available'}`,
            });
          }
          break;

        case 'workflow_complete':
          const statusMessage = mode === 'supervisor' 
            ? 'Claude Code supervisor workflow completed!'
            : 'Analytics memory workflow completed!';
          const isEarlyExit = Boolean(eventData?.early_exit);
          streamHook.setCurrentStatus(eventData?.message || statusMessage);
          if (!isThinkingEvent && !isEarlyExit) {
            addChatMessage({
              type: 'result',
              content: 'Analysis completed! Here are your results:',
              analysis: workflowDataRef.current.analysis || workflowDataRef.current.streamingText,
              chartSpec: workflowDataRef.current.chartSpec,
              sqlQuery: workflowDataRef.current.sqlQuery,
              dataSample: workflowDataRef.current.dataSample,
            });
          }

          if (isEarlyExit) {
            // Clear any partial workflow artifacts for clarity
            workflowDataRef.current = {
              chartSpec: null,
              analysis: '',
              sqlQuery: '',
              dataSample: null,
              streamingText: '',
            };
            setChartSpec(null);
            setAnalysis('');
            setSqlQuery('');
            setDataSample(null);
            setStreamingText('');
          }
          break;

        case 'final_answer':
          stepsHook.updateStepStatus('finalization', 'completed', ['Provided final response']);
          streamHook.setCurrentStatus(eventData?.message || 'Completed');
          if (!isThinkingEvent) {
            addChatMessage({
              type: 'assistant',
              content: eventData?.message || 'Happy to help with financial analytics questions!',
            });
          }
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
    
    // Reset workflow data ref
    workflowDataRef.current = {
      chartSpec: null,
      analysis: '',
      sqlQuery: '',
      dataSample: null,
      streamingText: ''
    };
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
    
    // Supervisor state
    supervisorState,
    
    // Actions
    handleQuery,
    submitClarification,
    stopAnalysis,
    resetAll,
    addChatMessage,
    updateChatMessage,
  };
};

