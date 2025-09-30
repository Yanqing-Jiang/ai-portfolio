import { useState, useRef } from 'react';
import { ChatMessage, ClarifyRequest, ClarifyAnswer, ToolCallTelemetry, AgentTurnTelemetry, AgentReasoningTelemetry, ProcessStep } from '../types';
import { apiService } from '../../../services/apiService';
import { useAnalyticsStream } from './useAnalyticsStream';
import { useProcessSteps } from './useProcessSteps';
import { resolveChartSpecOption } from '../utils';

export const useAnalyticsMemoryStream = (
  flow: 'planner-executor' | 'single-agent' | 'multi-agent' = 'planner-executor',
) => {
  const [sessionId, setSessionId] = useState<string>('');
  const [pendingClarification, setPendingClarification] = useState<ClarifyRequest | null>(null);

  const [criteria, setCriteria] = useState<any | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chartSpec, setChartSpec] = useState<any>(null);
  const [analysis, setAnalysis] = useState('');
  const [sqlQuery, setSqlQuery] = useState('');
  const [dataSample, setDataSample] = useState<any[] | null>(null);
  const [streamingText, setStreamingText] = useState('');
  
  // Progressive rendering: update state immediately instead of accumulating in refs
  const [progressiveAnalysis, setProgressiveAnalysis] = useState('');
  const [progressiveText, setProgressiveText] = useState('');

  // Ref for debouncing rapid updates
  const updateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pendingUpdatesRef = useRef<{
    analysis?: string;
    streamingText?: string;
    chartSpec?: any;
    sqlQuery?: string;
    dataSample?: any[];
  }>({});

  const toolTelemetryRef = useRef<ToolCallTelemetry[]>([]);
  const agentTurnsRef = useRef<AgentTurnTelemetry[]>([]);
  const agentReasoningRef = useRef<AgentReasoningTelemetry[]>([]);

  // Workflow data ref for result accumulation
  const workflowDataRef = useRef<{
    chartSpec: any;
    analysis: string;
    sqlQuery: string;
    dataSample: any[] | null;
    streamingText: string;
    criteria: any | null;
  }>({
    chartSpec: null,
    analysis: '',
    sqlQuery: '',
    dataSample: null,
    streamingText: '',
    criteria: null
  });

  const streamHook = useAnalyticsStream();
  const stepsHook = useProcessSteps();

  // Progressive update function with debouncing
  const scheduleProgressiveUpdate = (updates: Partial<typeof pendingUpdatesRef.current>) => {
    // Merge pending updates
    Object.assign(pendingUpdatesRef.current, updates);

    // Clear existing timeout
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }

    // Schedule batched update for better performance
    updateTimeoutRef.current = setTimeout(() => {
      const pending = pendingUpdatesRef.current;

      if (pending.analysis !== undefined) {
        setAnalysis(pending.analysis);
        setProgressiveAnalysis(pending.analysis);
        workflowDataRef.current.analysis = pending.analysis;
      }
      if (pending.streamingText !== undefined) {
        setStreamingText(pending.streamingText);
        setProgressiveText(pending.streamingText);
        workflowDataRef.current.streamingText = pending.streamingText;
      }
      if (pending.chartSpec !== undefined) {
        setChartSpec(pending.chartSpec);
        workflowDataRef.current.chartSpec = pending.chartSpec;
      }
      if (pending.sqlQuery !== undefined) {
        setSqlQuery(pending.sqlQuery);
        workflowDataRef.current.sqlQuery = pending.sqlQuery;
      }
      if (pending.dataSample !== undefined) {
        setDataSample(pending.dataSample);
        workflowDataRef.current.dataSample = pending.dataSample;
      }

      // Clear pending updates
      pendingUpdatesRef.current = {};
    }, 50); // 50ms debounce for smooth updates
  };

  const recordToolCallEvent = (payload: any, meta?: { ts?: string; elapsed_ms?: number; sequence?: number; parallel_group?: string; tool_group?: string }) => {
    if (!payload || !payload.tool || !payload.status) {
      return;
    }

    const entry: ToolCallTelemetry = {
      tool: payload.tool,
      status: payload.status,
      ts: meta?.ts || payload.ts,
      elapsed_ms: meta?.elapsed_ms ?? payload.elapsed_ms,
      details: payload.details,
      sequence: meta?.sequence ?? payload.sequence,
      parallelGroup: meta?.parallel_group ?? payload.parallel_group,
      toolGroup: meta?.tool_group ?? payload.tool_group,
    };

    toolTelemetryRef.current = [...toolTelemetryRef.current, entry].slice(-15);

    const elapsed = meta?.elapsed_ms ?? payload.elapsed_ms;
    const ts = meta?.ts || payload.ts;
    const statusLabel = payload.status === 'start' ? 'started' : payload.status === 'end' ? 'completed' : payload.status;
    const durationText = elapsed ? ` (${elapsed}ms)` : '';
    const message = `Tool ${payload.tool} ${statusLabel}${durationText}`;

    stepsHook.updateStepStatus(
      'tool_execution',
      'in_progress',
      [message],
      { tool_calls: [...toolTelemetryRef.current] },
      elapsed,
      ts,
      meta?.sequence,
      meta?.parallel_group,
    );
  };

  const recordAgentTurnEvent = (payload: any, meta?: { ts?: string; elapsed_ms?: number; sequence?: number; parallel_group?: string }) => {
    if (!payload || !payload.role || !payload.status) {
      return;
    }

    const entry: AgentTurnTelemetry = {
      role: payload.role,
      status: payload.status,
      ts: meta?.ts || payload.ts,
      elapsed_ms: meta?.elapsed_ms ?? payload.elapsed_ms,
      summary: payload.summary,
      sequence: meta?.sequence ?? payload.sequence,
      parallelGroup: meta?.parallel_group ?? payload.parallel_group,
    };
    agentTurnsRef.current = [...agentTurnsRef.current, entry].slice(-15);

    const ts = meta?.ts || payload.ts;
    const elapsed = meta?.elapsed_ms ?? payload.elapsed_ms;

    const rawSummary = payload.summary;
    const summaryText = typeof rawSummary === 'string' ? rawSummary : rawSummary ? JSON.stringify(rawSummary) : undefined;
    const labelParts = [`${payload.role.replace(/_/g, ' ')} ${payload.status}`];
    if (summaryText) {
      labelParts.push(summaryText);
    }

    const stepStatus = payload.status === 'complete' ? 'completed' : 'in_progress';

    stepsHook.updateStepStatus(
      'agent_coordination',
      stepStatus,
      [labelParts.join(' - ')],
      {
        agent_turns: [...agentTurnsRef.current],
        agent_reasoning: [...agentReasoningRef.current],
      },
      elapsed,
      ts,
      meta?.sequence,
      meta?.parallel_group,
    );
  };

  const recordAgentReasoningEvent = (payload: any, meta?: { ts?: string; elapsed_ms?: number; sequence?: number; parallel_group?: string }) => {
    if (!payload || !payload.thought) {
      return;
    }

    const ts = meta?.ts || payload.ts;
    const entry: AgentReasoningTelemetry = {
      role: payload.role || 'insight_reviewer',
      thought: payload.thought,
      ts,
      sequence: meta?.sequence ?? payload.sequence,
      parallelGroup: meta?.parallel_group ?? payload.parallel_group,
    };
    agentReasoningRef.current = [...agentReasoningRef.current, entry].slice(-40);

    const thought = typeof payload.thought === 'string' ? payload.thought : JSON.stringify(payload.thought);

    stepsHook.updateStepStatus(
      'agent_coordination',
      'in_progress',
      [thought],
      {
        agent_turns: [...agentTurnsRef.current],
        agent_reasoning: [...agentReasoningRef.current],
      },
      meta?.elapsed_ms ?? payload.elapsed_ms,
      ts,
      meta?.sequence,
      meta?.parallel_group,
    );

    stepsHook.updateStepStatus(
      'analysis_generation',
      'in_progress',
      [thought],
      undefined,
      undefined,
      ts,
    );
  };

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
    setProgressiveText('');
    setProgressiveAnalysis('');
    setPendingClarification(null);
    setCriteria(null);
    stepsHook.resetSteps();

    // Clear any pending updates
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }
    pendingUpdatesRef.current = {};

    toolTelemetryRef.current = [];
    agentTurnsRef.current = [];
    agentReasoningRef.current = [];

    const baseEndpoint = `/api/analytics/memory/stream`;

    const params = new URLSearchParams({ query: query.trim() });
    if (sessionId) {
      params.append('session_id', sessionId);
    }
    if (flow) {
      params.append('flow', flow);
    }

    const endpoint = `${baseEndpoint}?${params.toString()}`;

    await streamHook.startStream(endpoint, (data) => {
      const eventType = data.event || data.type;
      // Handle both old (heavy) and new (lightweight) event formats
      const eventData = data.data || data;
      const eventVisibility =
        typeof data.event_type === 'string' ? data.event_type : 'user';
      const isThinkingEvent = eventVisibility === 'thinking';

      // For lightweight events, extract step and timing info from top level
      const stepInfo = {
        step: data.step || eventData.step,
        ts: data.ts || eventData.ts,
        elapsed_ms: data.elapsed_ms || eventData.elapsed_ms
      };
            const sequence: number | undefined =
        typeof data.seq === 'number'
          ? data.seq
          : typeof eventData.sequence === 'number'
          ? eventData.sequence
          : undefined;
      const parallelGroup: string | undefined =
        typeof data.parallel_group === 'string'
          ? data.parallel_group
          : typeof eventData.parallel_group === 'string'
          ? eventData.parallel_group
          : undefined;
      const toolGroup: string | undefined =
        typeof data.tool_group === 'string'
          ? data.tool_group
          : typeof eventData.tool_group === 'string'
          ? eventData.tool_group
          : undefined;

      const updateStep = (
        stepId: string,
        status: ProcessStep['status'],
        thinking: string[] = [],
        details?: any,
        elapsed?: number,
        ts?: string,
      ) => {
        stepsHook.updateStepStatus(stepId, status, thinking, details, elapsed, ts, sequence, parallelGroup);
      };
      
      switch (eventType) {
        case 'session_started':
          setSessionId(eventData.session_id);
          break;
          

        case 'status':
        case 'progress':
          // Handle both old 'status' and new 'progress' event types
          const statusMessage = eventData.message || data.message || '';
          streamHook.setCurrentStatus(statusMessage);
          if (stepInfo.step) {
            const thinkingLogs: string[] = [];
            if (isThinkingEvent && statusMessage) {
              thinkingLogs.push(statusMessage);
            }
            if (eventData.code) {
              const codeTag = statusMessage ? `${statusMessage} [${eventData.code}]` : `Code: ${eventData.code}`;
              if (!thinkingLogs.includes(codeTag)) {
                thinkingLogs.push(codeTag);
              }
            }
            const detailPayload = eventData.code || eventData.attempt
              ? {
                  code: eventData.code,
                  attempt: eventData.attempt,
                  message: statusMessage,
                }
              : undefined;
            updateStep(stepInfo.step, 'in_progress', thinkingLogs, detailPayload, stepInfo.elapsed_ms, stepInfo.ts);
          }
          break;
          
        case 'intent_draft':
          updateStep('intent_detection', 'in_progress', ['Intent detected; needs clarification'], eventData, eventData.elapsed_ms);
          break;
          
        case 'intent_decided':
        case 'intent_resolved':
          // Handle both old heavy format and new lightweight format
          const intentData = eventData.intent || eventData; // Old format has nested intent, new format is flat
          updateStep('intent_detection', 'completed', [], intentData, stepInfo.elapsed_ms, stepInfo.ts);
          updateStep('clarification', 'completed', ['Clarifications resolved'], intentData, stepInfo.elapsed_ms, stepInfo.ts);
          setPendingClarification(null);
          break;
          
        case 'clarification_request':
          console.log('?? [DEBUG] Received clarification_request:', eventData);
          setPendingClarification(eventData as ClarifyRequest);
          updateStep('clarification', 'in_progress', [eventData.question]);
          streamHook.setCurrentStatus(`Clarification needed: ${eventData.question}`);
          const clarificationMessage = {
            type: 'clarification' as const,
            content: eventData.question,
            clarifications: [eventData as ClarifyRequest],
          };
          console.log('?? [DEBUG] Adding clarification message:', clarificationMessage);
          addChatMessage(clarificationMessage);
          break;
          
        case 'clarification_ack':
          setPendingClarification(null);
          addChatMessage({
            type: 'user',
            content: `${eventData.answer}`,
      e({
            type: 'user',
            content: `${eventData.answer}`,
          });
          stepsHook.updateStepStatus('clarification', 'in_progress', ['Processing your answer...']);
          streamHook.setCurrentStatus('Processing your clarification answer...');
          break;
          
        case 'plan_built':
          // Combined planning step for streamlined agent flow
          // Handle both old (eventData.plan) and new (simplified) formats
          const planData = eventData.plan || { metrics_count: eventData.metrics_count, granularity: eventData.granularity, comparison: eventData.comparison };
          stepsHook.updateStepStatus('plan_and_select_template', 'in_progress', ['Plan built'], { plan: planData }, stepInfo.elapsed_ms);
          break;

        case 'template_selected':
          // Complete combined planning + selection step
          // Handle both old (eventData.template) and new (eventData.template_id) formats
          const templateId = eventData.template?.id || eventData.template_id;
          const templateData = eventData.template || { id: templateId, has_template: eventData.has_template };
          stepsHook.updateStepStatus('plan_and_select_template', 'completed', [
            templateId ? `Selected template: ${templateId}` : 'Template selected'
          ], { template: templateData }, stepInfo.elapsed_ms);
          break;
          
        case 'sql_compiled':
          {
            const attempt = eventData.attempt ?? 1;
            const messages = [`SQL compiled (len: ${eventData.sql_length})`];
            if (eventData.fallback_reason) {
              messages.push(`Fallback: ${eventData.fallback_reason.replace(/_/g, ' ')}`);
            }
            stepsHook.updateStepStatus(
              'sql_compilation',
              'completed',
              messages,
              {
                sql_length: eventData.sql_length,
                template_used: eventData.template_used,
                template_fallback: eventData.template_fallback,
                fallback_reason: eventData.fallback_reason,
                attempt,
                llm_used: eventData.llm_used,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts
            );
            if (eventData.fallback_reason) {
              streamHook.setCurrentStatus(`Template fallback applied: ${eventData.fallback_reason.replace(/_/g, ' ')}`);
            }
          }
          break;

        case 'sql_generated':
          if (typeof eventData.sql === 'string') {
            scheduleProgressiveUpdate({ sqlQuery: eventData.sql });
          }
          stepsHook.updateStepStatus(
            'sql_compilation',
            'completed',
            [`SQL ready (attempt ${eventData.attempt ?? 1})`],
            {
              sql: eventData.sql,
              attempt: eventData.attempt,
              llm_used: eventData.llm_used,
              fallback_reason: eventData.fallback_reason,
            },
            stepInfo.elapsed_ms,
            stepInfo.ts
          );
          break;


        case 'sql_validated':
          {
            const attempt = eventData.attempt ?? 1;
            const issues = Array.isArray(eventData.issues) ? eventData.issues : [];
            const validationMessages = eventData.ok
              ? [`SQL validation passed (attempt ${attempt})`]
              : [issues.length ? `Validation issues: ${issues.join(', ')}` : `Validation failed (attempt ${attempt})`];
            stepsHook.updateStepStatus(
              'sql_validation',
              eventData.ok ? 'completed' : 'error',
              validationMessages,
              {
                ok: eventData.ok,
                issues,
                issues_count: eventData.issues_count,
                attempt,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts
            );
            if (!eventData.ok) {
              streamHook.setCurrentStatus('SQL validation issues detected; applying fallback');
            }
          }
          break;
          
        case 'execution_stats':
          // Handle both old (eventData.columns) and new (eventData.columns_count) formats
          const executionData = {
            row_count: eventData.row_count,
            columns: eventData.columns || [],
            columns_count: eventData.columns_count || (eventData.columns ? eventData.columns.length : 0)
          };
          stepsHook.updateStepStatus('sql_execution', 'completed', [], executionData, stepInfo.elapsed_ms);
          break;
          
        case 'data_retrieved':
          // Handle both old and new formats
          if (Array.isArray(eventData.sample_data)) {
            scheduleProgressiveUpdate({ dataSample: eventData.sample_data });
          }
          stepsHook.updateStepStatus('sql_execution', 'completed', [], {
            rowCount: eventData.row_count,
            sampleData: eventData.sample_data || []
          });
          break;
          
        case 'chart_generated': {
          // Normalize chart payloads from legacy + lightweight emitters
          const normalizedChartSpec =
            resolveChartSpecOption(eventData) ?? resolveChartSpecOption(data);
          const chartType =
            eventData.chart_type ??
            (typeof eventData.chart_spec === 'object' && eventData.chart_spec
              ? eventData.chart_spec.chart_type
              : undefined) ??
            (typeof (data as any)?.chart_spec === 'object'
              ? (data as any).chart_spec.chart_type
              : undefined) ??
            normalizedChartSpec?.meta?.chartDesign?.chart_type;

          if (normalizedChartSpec) {
            scheduleProgressiveUpdate({ chartSpec: normalizedChartSpec });
          } else {
            console.warn('[AnalyticsMemoryStream] chart_generated event without resolvable chart spec', { event: data });
          }

          stepsHook.updateStepStatus(
            'chart_generation',
            'completed',
            [],
            { chart_spec: normalizedChartSpec, chart_type: chartType },
            stepInfo.elapsed_ms
          );
          break;
        }
          
        case 'analysis_streaming':
          if (!isThinkingEvent) {
            const chunk: string =
              typeof eventData?.partial_analysis === 'string'
                ? eventData.partial_analysis
                : typeof eventData?.delta === 'string'
                ? eventData.delta
                : typeof eventData?.text === 'string'
                ? eventData.text
                : typeof data?.partial_analysis === 'string' // New format: direct access
                ? data.partial_analysis
                : '';
            if (chunk) {
              // Progressive streaming: update immediately for each chunk
              setStreamingText(prev => {
                const newText = prev + chunk;
                scheduleProgressiveUpdate({ streamingText: newText });
                return newText;
              });
            }
          }
          stepsHook.updateStepStatus('analysis_generation', 'in_progress', ['Generating financial analysis...']);
          break;
          
        case 'analysis_complete':
          // Handle both old and new formats for analysis
          const finalAnalysis =
            !isThinkingEvent
              ? eventData.analysis || data.analysis || streamingText
              : eventData.analysis || data.analysis;
          if (!isThinkingEvent && typeof finalAnalysis === 'string') {
            scheduleProgressiveUpdate({ analysis: finalAnalysis });
          }
          setStreamingText('');
          setProgressiveText('');
          stepsHook.updateStepStatus('short_financial_analysis', 'completed', ['Short financial analysis complete'], { analysis: finalAnalysis, analysis_length: eventData.analysis_length }, stepInfo.elapsed_ms);
          stepsHook.updateStepStatus('analysis_generation', 'completed', [], { analysis: finalAnalysis, analysis_length: eventData.analysis_length }, stepInfo.elapsed_ms);
          break;

        // Optional richer logs for agent demo

        case 'tool_call':
          recordToolCallEvent(eventData, { ts: stepInfo.ts, elapsed_ms: stepInfo.elapsed_ms, sequence, parallel_group: parallelGroup, tool_group: toolGroup });
          break;

        case 'agent_turn':
          recordAgentTurnEvent(eventData, { ts: stepInfo.ts, elapsed_ms: stepInfo.elapsed_ms, sequence, parallel_group: parallelGroup });
          break;

        case 'agent_reasoning':
          recordAgentReasoningEvent(eventData, { ts: stepInfo.ts, elapsed_ms: stepInfo.elapsed_ms, sequence, parallel_group: parallelGroup });
          break;

        case 'catalog_trace':
          {
            const targetStep = eventData.tool ?? 'plan_and_select_template';
            const notes = ['YAML catalogue lookup via ' + (eventData.tool || 'lookup')];
            const metadata = eventData.metadata ?? {};
            const candidates = Array.isArray(eventData.candidates) ? eventData.candidates : [];
            stepsHook.updateStepStatus(targetStep, 'in_progress', notes, { candidates, metadata }, eventData.elapsed_ms);
          }
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
          updateStep('classification', 'completed', [`Fallback to ${eventData.method}`], { method: eventData.method }, undefined, eventData.ts);
          break;

        case 'memory_gate_decision':
          {
            const reasons = Array.isArray(eventData.reasons) ? eventData.reasons : eventData.reasons ? [eventData.reasons] : [];
            const details = {
              policy: eventData.policy,
              reuse_sql: eventData.reuse_sql,
              reuse_chart: eventData.reuse_chart,
              reuse_analysis: eventData.reuse_analysis,
              tool_directives: eventData.tool_directives,
            };
            updateStep('classification', 'completed', reasons.length ? reasons : ['Memory gate evaluated session state'], details, eventData.elapsed_ms, eventData.ts);
            streamHook.setCurrentStatus(`Memory gate policy: ${eventData.policy}`);
          }
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

        case 'criteria_ready':
          workflowDataRef.current.criteria = eventData;
          setCriteria(eventData);
          stepsHook.updateStepStatus('schema_validation', 'completed', ['SQL criteria ready'], eventData, eventData.elapsed_ms, eventData.ts);
          streamHook.setCurrentStatus('SQL criteria locked in.');
          break;

        case 'clarification_needed':
          stepsHook.updateStepStatus('clarification', 'in_progress', [`Missing fields: ${eventData.missing_fields?.join(', ')}`], { missing_fields: eventData.missing_fields }, undefined, eventData.ts);
          break;

        case 'clarification_skipped':
          stepsHook.updateStepStatus('clarification', 'completed', [eventData.reason || 'Clarification not needed'], undefined, undefined, eventData.ts);
          setPendingClarification(null);
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
          stepsHook.updateStepStatus('planning', 'completed', [eventData.plan]);
          streamHook.setCurrentStatus('Plan proposed by flow coordinator');
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
            content: `?? **Tool Error:** ${eventData.tool} - ${eventData.error}`,
          });
          break;
          
        case 'final_summary':
          stepsHook.updateStepStatus('finalization', 'completed', ['Workflow summary generated']);
          const summaryStatusMessage =
            flow === 'single-agent'
              ? 'Single-agent tools workflow completed!'
              : flow === 'multi-agent'
                ? 'Multi-agent workflow completed!'
                : 'Planner/executor workflow completed!';
          streamHook.setCurrentStatus(summaryStatusMessage);
          if (!isThinkingEvent) {
            addChatMessage({
              type: 'assistant',
              content: `?? **Final Summary:**\n\n**SQL:** ${eventData.sql_summary}\n**Chart:** ${eventData.chart_summary}\n\n**Key Findings:**\n${eventData.key_findings?.map((f: string) => `• ${f}`).join('\n') || 'No findings available'}`,
            });
          }
          break;

        case 'workflow_complete':
          const workflowStatusMessage =
            flow === 'single-agent'
              ? 'Single-agent tools workflow completed!'
              : flow === 'multi-agent'
                ? 'Multi-agent workflow completed!'
                : 'Planner/executor workflow completed!';
          const isEarlyExit = Boolean(eventData?.early_exit);
          // Handle both old and new formats for completion message
          const completionMessage = eventData?.message || (eventData.total_elapsed_ms ? `Completed in ${eventData.total_elapsed_ms}ms` : null);
          streamHook.setCurrentStatus(completionMessage || workflowStatusMessage);
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
              criteria: null,
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
          {
            const errorStep = eventData.step || stepInfo.step || 'unknown';
            const errorMessage = eventData.error || eventData.message || 'Analytics error occurred';
            const errorCodeLabel = eventData.code ? `[${eventData.code}] ` : '';
            streamHook.setError(eventData.code ? `${eventData.code}: ${errorMessage}` : errorMessage);
            stepsHook.updateStepStatus(
              errorStep,
              'error',
              [`${errorCodeLabel}${errorMessage}`],
              {
                error: errorMessage,
                code: eventData.code,
                details: eventData.details,
              },
              stepInfo.elapsed_ms,
              stepInfo.ts
            );
          }
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
    setCriteria(null);
    setChatHistory([]);
    setChartSpec(null);
    setAnalysis('');
    setSqlQuery('');
    setDataSample(null);
    setStreamingText('');
    setProgressiveAnalysis('');
    setProgressiveText('');

    // Clear any pending updates
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }
    pendingUpdatesRef.current = {};
    toolTelemetryRef.current = [];
    agentTurnsRef.current = [];
    agentReasoningRef.current = [];

    // Reset workflow data ref
    workflowDataRef.current = {
      chartSpec: null,
      analysis: '',
      sqlQuery: '',
      dataSample: null,
      streamingText: '',
      criteria: null
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
    criteria,
    streamingText,

    // Progressive rendering state
    progressiveAnalysis,
    progressiveText,

    // Stream state
    isLoading: streamHook.isLoading,
    error: streamHook.error,
    currentStatus: streamHook.currentStatus,

    // Process steps
    processSteps: stepsHook.processSteps,

    // Supervisor state

    // Actions
    handleQuery,
    submitClarification,
    stopAnalysis,
    resetAll,
    addChatMessage,
    updateChatMessage,
  };
};






