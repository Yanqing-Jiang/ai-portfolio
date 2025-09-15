import { useState, useRef } from 'react';
import { ChatMessage, ClarifyRequest, ClarifyAnswer } from '../types';
import { apiService } from '../../../services/apiService';
import { useAnalyticsStream } from './useAnalyticsStream';
import { useProcessSteps } from './useProcessSteps';

export const useAnalyticsMemoryStream = (mode: 'memory' | 'supervisor' = 'memory') => {
  const [sessionId, setSessionId] = useState<string>('');
  const [pendingClarification, setPendingClarification] = useState<ClarifyRequest | null>(null);
  const [supervisorState, setSupervisorState] = useState<{
    plan?: any;
    requiresApproval?: boolean;
    approvalPending?: boolean;
    currentSessionId?: string;
  }>({});
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
          // Compilation stats only; SQL text arrives in 'sql_generated'
          stepsHook.updateStepStatus('sql_compilation', 'completed', [], {
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
          {
            const chunk: string =
              typeof eventData?.partial_analysis === 'string'
                ? eventData.partial_analysis
                : typeof eventData?.delta === 'string'
                ? eventData.delta
                : typeof eventData?.text === 'string'
                ? eventData.text
                : ''
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
          const finalAnalysis = eventData.analysis || workflowDataRef.current.streamingText;
          setAnalysis(finalAnalysis);
          workflowDataRef.current.analysis = finalAnalysis;
          setStreamingText('');
          workflowDataRef.current.streamingText = '';
          stepsHook.updateStepStatus('analysis_generation', 'completed', [], { analysis: finalAnalysis }, eventData.elapsed_ms);
          break;
          
        // ===== SUPERVISOR MODE EVENTS =====
        case 'planning_proposed':
          setSupervisorState(prev => ({ ...prev, plan: eventData }));
          stepsHook.updateStepStatus('planning', 'completed', [eventData.plan]);
          streamHook.setCurrentStatus('Plan proposed by supervisor agent');
          addChatMessage({
            type: 'assistant',
            content: `📋 **Plan Proposed:**\n${eventData.plan}\n\n**Steps:** ${eventData.steps?.length || 0} tools planned\n**Requires Approval:** ${eventData.requires_approval ? 'Yes' : 'No'}`,
          });
          break;

        case 'approval_required':
          setSupervisorState(prev => ({ 
            ...prev, 
            requiresApproval: true, 
            approvalPending: true,
            currentSessionId: eventData.session_id 
          }));
          stepsHook.updateStepStatus('approval', 'in_progress', ['Waiting for user approval']);
          streamHook.setCurrentStatus('Plan requires approval - please review and approve');
          addChatMessage({
            type: 'approval_request',
            content: '🔒 **Approval Required** - This plan includes SQL execution which requires your approval.',
            approvalSessionId: eventData.session_id,
            previewSql: eventData.preview_sql,
            applyTargets: eventData.apply_targets,
          });
          break;
          
        case 'approval_auto_granted':
        case 'approval_granted':
          setSupervisorState(prev => ({ ...prev, approvalPending: false }));
          stepsHook.updateStepStatus('approval', 'completed', ['Auto-approved for demo']);
          streamHook.setCurrentStatus('Plan approved - executing tools...');
          addChatMessage({
            type: 'assistant',
            content: '✅ **Plan Approved** - Proceeding with tool execution',
          });
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
          addChatMessage({
            type: 'assistant',
            content: `📊 **Final Summary:**\n\n**SQL:** ${eventData.sql_summary}\n**Chart:** ${eventData.chart_summary}\n\n**Key Findings:**\n${eventData.key_findings?.map((f: string) => `• ${f}`).join('\n') || 'No findings available'}`,
          });
          break;

        case 'workflow_complete':
          const statusMessage = mode === 'supervisor' 
            ? 'Claude Code supervisor workflow completed!'
            : 'Analytics memory workflow completed!';
          streamHook.setCurrentStatus(statusMessage);
          addChatMessage({
            type: 'result',
            content: 'Analysis completed! Here are your results:',
            analysis: workflowDataRef.current.analysis || workflowDataRef.current.streamingText,
            chartSpec: workflowDataRef.current.chartSpec,
            sqlQuery: workflowDataRef.current.sqlQuery,
            dataSample: workflowDataRef.current.dataSample,
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

  const approveWorkflow = async (sessionId: string) => {
    try {
      const response = await apiService.post('/api/analytics/memory/supervisor/approve', { session_id: sessionId });
      console.log('Approval submitted:', response);
    } catch (error) {
      console.error('Failed to submit approval:', error);
      streamHook.setError('Failed to submit approval');
    }
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
    approveWorkflow,
  };
};
