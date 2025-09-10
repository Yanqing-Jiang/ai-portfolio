import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeftIcon } from './icons/ChevronLeftIcon';
import { ChevronRightIcon } from './icons/ChevronRightIcon';
import EChartsReact from 'echarts-for-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiService } from '../services/apiService';
import { configService } from '../services/config';

// Error boundary to prevent full-app crash on chart render failures
class ChartErrorBoundary extends React.Component<{ onError: (error: unknown) => void; children: React.ReactNode }, { hasError: boolean }> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(_: Error) {
    return { hasError: true };
  }
  componentDidCatch(error: Error) {
    this.props.onError(error);
  }
  render() {
    if (this.state.hasError) {
      return null;
    }
    return this.props.children as React.ReactElement;
  }
}

// Clarification types
interface ClarifyRequest {
  session_id: string;
  request_id: string;
  slot: string;
  question: string;
  type: 'single' | 'multi' | 'free';
  options: string[];
  default: any;
  proposed?: any;
  proposed_confidence?: number;
  reason?: string;
  required: boolean;
  timeout_ms?: number;
}

interface ClarifyAnswer {
  session_id: string;
  request_id: string;
  slot: string;
  value: any;
  ts: string;
}

interface ProcessStep {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'stopped';
  thinking: string[];
  details?: any;
  elapsed_ms?: number;
  timestamp?: string;
}

const STEP_NAME: Record<string, string> = {
  intent_detection: 'Intent Detection',
  plan_generation: 'Query Planning',
  template_selection: 'Template Selection',
  clarification: 'Requirements Clarification',
  sql_compilation: 'SQL Compilation',
  sql_validation: 'SQL Validation',
  sql_execution: 'Data Retrieval',
  chart_generation: 'Chart Generation',
  analysis_generation: 'Analysis Generation',
};

const STEP_ORDER = [
  'intent_detection',
  'plan_generation',
  'template_selection',
  'clarification',
  'sql_compilation',
  'sql_validation',
  'sql_execution',
  'chart_generation',
  'analysis_generation',
];

// Inline clarification component (replaces modal)
const ClarifyInline: React.FC<{
  request: ClarifyRequest;
  onSubmit: (value: any) => Promise<void>;
  disabled?: boolean;
}> = ({ request, onSubmit, disabled }) => {
  const [selectedValue, setSelectedValue] = useState<any>(request.proposed ?? request.default);
  const [submitting, setSubmitting] = useState(false);

  const doSubmit = async (value: any) => {
    if (submitting || disabled) return;
    setSubmitting(true);
    try {
      await onSubmit(value);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-3 sm:p-4">
      <div className="text-sm font-medium">{request.question}</div>
      {request.reason && <div className="text-xs text-blue-700 mt-1">{request.reason}</div>}

      <div className="mt-3 space-y-2">
        {request.type === 'single' && (
          <div className="flex flex-wrap gap-2">
            {request.options.map((opt) => (
              <button
                key={opt}
                onClick={() => setSelectedValue(opt)}
                className={`px-3 py-1.5 rounded-full border text-sm ${selectedValue === opt ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-blue-900 border-blue-300'}`}
              >
                {opt}
              </button>
            ))}
          </div>
        )}
        {request.type === 'multi' && (
          <div className="flex flex-col gap-1">
            {request.options.map((opt) => {
              const arr: any[] = Array.isArray(selectedValue) ? selectedValue : [];
              const checked = arr.includes(opt);
              return (
                <label key={opt} className="inline-flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      if (e.target.checked) setSelectedValue([...arr, opt]);
                      else setSelectedValue(arr.filter((v) => v !== opt));
                    }}
                  />
                  <span>{opt}</span>
                </label>
              );
            })}
          </div>
        )}
        {request.type === 'free' && (
          <input
            type="text"
            value={selectedValue ?? ''}
            onChange={(e) => setSelectedValue(e.target.value)}
            className="w-full px-3 py-2 border rounded-md text-sm"
            placeholder="Type your answer..."
          />
        )}
      </div>

      <div className="mt-3 flex gap-2">
        <button
          onClick={() => doSubmit(selectedValue)}
          disabled={submitting || disabled}
          className="px-3 py-2 rounded-md bg-blue-600 text-white text-sm disabled:opacity-50"
        >
          {submitting ? 'Submitting…' : 'Continue'}
        </button>
        <button
          onClick={() => doSubmit(request.default)}
          disabled={submitting || disabled}
          className="px-3 py-2 rounded-md bg-white border border-blue-300 text-blue-900 text-sm"
        >
          Use Default
        </button>
      </div>
    </div>
  );
};

const AnalyticsMemoryPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [chartSpec, setChartSpec] = useState<any>(null);
  const [analysis, setAnalysis] = useState('');
  const [sqlQuery, setSqlQuery] = useState('');
  const [dataSample, setDataSample] = useState<any[] | null>(null);
  const [processSteps, setProcessSteps] = useState<ProcessStep[]>([]);
  const [currentStatus, setCurrentStatus] = useState('Ready to analyze financial data with intelligent memory...');
  const [showProcessPanel, setShowProcessPanel] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [error, setError] = useState('');
  const [useAltChart, setUseAltChart] = useState(false);
  const [chartRetryCount, setChartRetryCount] = useState(0);
  const [sessionId, setSessionId] = useState<string>('');
  const [pendingClarification, setPendingClarification] = useState<ClarifyRequest | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Project data for the analytics memory project
  const projectData = {
    title: 'Next Gen Analytics (Memory)',
    description: `• AI-powered financial analytics with LangGraph memory pipeline and intelligent clarifications.
• Uses advanced intent detection → SQL planning → Chart Generation → financial analysis workflow.
• Real-time streaming with conversational clarifications and session memory management.

Result:

• Interactive financial analysis for AMD, AVGO, INTC, MU, NVDA, QCOM, TXN with memory optimization.
• Streaming agent coordination with inline clarification UI.
• Dynamic Chart Generation with session persistence and memory-aware caching.`,
    technologies: ['LangGraph', 'Memory Pipeline', 'Intent Detection', 'Clarifications', 'FastAPI', 'PostgreSQL'],
    imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/next-gen-sql.png'
  };

  const isValidChartSpec = (spec: any) => {
    try {
      if (!spec || typeof spec !== 'object') return false;
      if (spec.series && !Array.isArray(spec.series)) return false;
      return true;
    } catch {
      return false;
    }
  };

  const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

  // Apply light theme overrides and smart formatting to chart options
  const withLightTheme = (spec: any) => {
    if (!spec || typeof spec !== 'object') return spec;
    const option: any = { ...spec };
    option.backgroundColor = '#ffffff';
    option.textStyle = { ...(spec.textStyle || {}), color: '#333333', fontFamily: 'Inter, ui-sans-serif, system-ui' };
    option.title = {
      ...(spec.title || {}),
      textStyle: { ...((spec.title || {}).textStyle || {}), color: '#111111', fontWeight: 700 },
    };
    option.legend = {
      ...(spec.legend || {}),
      textStyle: { ...((spec.legend || {}).textStyle || {}), color: '#333333' },
    };
    option.tooltip = {
      ...(spec.tooltip || {}),
      backgroundColor: '#ffffff',
      borderColor: '#dddddd',
      textStyle: { ...((spec.tooltip || {}).textStyle || {}), color: '#333333' },
    };
    option.animation = true;

    // Axis formatting: percent vs currency based on series meta, with heuristics fallback
    const percentSeries = new Set<string>(Object.entries((spec.meta?.seriesValueType || {}))
      .filter(([_, v]) => v === 'percent')
      .map(([k]) => k));
    const includedColumns: string[] = spec.meta?.includedColumns || spec.meta?.defaultColumns || [];
    const metaChartValueType = (spec.meta?.chartValueType || '').toLowerCase();
    const isPercentyName = (name: string) => {
      const n = (name || '').toLowerCase();
      return (
        n.includes('share') || n.includes('ratio') || n.includes('margin') ||
        n.includes('pct') || n.includes('percent') || n.includes('growth') || n.includes('qoq')
      );
    };
    const includedPercent = Array.isArray(includedColumns) && includedColumns.some(isPercentyName);
    const usesPercent = metaChartValueType === 'percent' || (percentSeries.size > 0) || includedPercent;

    const chartIsPercent = metaChartValueType === 'percent';
    const formatPercent = (v: any, seriesName?: string) => {
      const num = typeof v === 'number' ? v : Number(v);
      if (Number.isFinite(num)) {
        // Check if backend provided specific format info for this series
        const percentFormat = spec.meta?.seriesPercentFormat?.[seriesName || ''];
        
        if (percentFormat === 'pre_multiplied' || chartIsPercent) {
          // Value is already in 0-100 range (e.g., 53.4 for 53.4%)
          return `${num.toFixed(1)}%`;
        } else if (percentFormat === 'decimal') {
          // Value is in 0-1 range (e.g., 0.534 for 53.4%)
          return `${(num * 100).toFixed(1)}%`;
        } else {
          // Fallback: If value is already in percentage format (> 1), display as-is
          // If value is in decimal format (0-1), multiply by 100
          const percentValue = num > 1 ? num : num * 100;
          return `${percentValue.toFixed(1)}%`;
        }
      }
      return v;
    };
    const formatCurrency0 = (v: any) => {
      const num = typeof v === 'number' ? v : Number(v);
      if (Number.isFinite(num)) return `$${Math.round(num).toLocaleString()}`;
      return v;
    };

    const axisFormatter = (value: any) => {
      // Heuristic: if any series is percent, show percent; else currency
      return usesPercent ? formatPercent(value) : formatCurrency0(value);
    };

    const normalizeXAxis = (ax: any) => ({
      ...(ax || {}),
      axisLabel: { ...((ax || {}).axisLabel || {}), color: '#555555' },
      axisLine: {
        ...((ax || {}).axisLine || {}),
        lineStyle: { ...(((ax || {}).axisLine || {}).lineStyle || {}), color: '#cccccc' },
      },
      splitLine: {
        ...((ax || {}).splitLine || {}),
        show: false,
      },
      nameTextStyle: { ...((ax || {}).nameTextStyle || {}), color: '#333333' },
    });
    const normalizeYAxis = (ax: any) => ({
      ...(ax || {}),
      // Always use smart formatter unless backend explicitly sends a function
      axisLabel: {
        ...((ax || {}).axisLabel || {}),
        color: '#555555',
        formatter: (typeof (ax?.axisLabel?.formatter) === 'function') ? ax.axisLabel.formatter : axisFormatter,
      },
      axisLine: {
        ...((ax || {}).axisLine || {}),
        lineStyle: { ...(((ax || {}).axisLine || {}).lineStyle || {}), color: '#cccccc' },
      },
      splitLine: {
        ...((ax || {}).splitLine || {}),
        show: true,
        lineStyle: { ...(((ax || {}).splitLine || {}).lineStyle || {}), color: '#eeeeee' },
      },
      nameTextStyle: { ...((ax || {}).nameTextStyle || {}), color: '#333333' },
    });
    const xAxisArr = Array.isArray(spec.xAxis) ? spec.xAxis : spec.xAxis ? [spec.xAxis] : [];
    const yAxisArr = Array.isArray(spec.yAxis) ? spec.yAxis : spec.yAxis ? [spec.yAxis] : [];
    if (xAxisArr.length) option.xAxis = xAxisArr.map(normalizeXAxis);
    if (yAxisArr.length) option.yAxis = yAxisArr.map(normalizeYAxis);

    // Tooltip value formatting by series type
    option.tooltip.formatter = (params: any) => {
      const list = Array.isArray(params) ? params : [params];
      const name = list[0]?.axisValueLabel ?? list[0]?.name ?? '';
      const lines = [name];
      for (const p of list) {
        const isSingleSeries = Array.isArray(option.series) && option.series.length === 1;
        const isPercent = percentSeries.has(p.seriesName) || (includedPercent && isSingleSeries);
        const val = p.value;
        const formatted = isPercent ? formatPercent(val, p.seriesName) : formatCurrency0(val);
        lines.push(`${p.marker || ''} ${p.seriesName}: ${formatted}`);
      }
      return lines.join('<br/>');
    };
    // Enable data labels with smart positioning
    if (Array.isArray(option.series)) {
      option.series = option.series.map((s: any) => ({
        ...s,
        label: {
          show: true,
          position: 'top',
          color: '#444',
          formatter: (params: any) => {
            const isSingleSeries = Array.isArray(option.series) && option.series.length === 1;
            const isPercent = percentSeries.has(params.seriesName) || (includedPercent && isSingleSeries);
            return isPercent ? formatPercent(params.value, params.seriesName) : formatCurrency0(params.value);
          },
        },
        smooth: true,
        lineStyle: { ...(s.lineStyle || {}), width: 2 },
        symbol: 'circle',
        symbolSize: 6,
        areaStyle: s.type === 'line' ? { opacity: 0.06 } : undefined,
      }));
    }

    return option;
  };

  const updateStepStatus = (
    stepId: string,
    status: ProcessStep['status'],
    thinking: string[] = [],
    details?: any,
    elapsed_ms?: number,
    timestamp?: string,
  ) => {
    setProcessSteps((prev) => {
      const existing = prev.find((s) => s.id === stepId);
      if (existing) {
        return prev.map((s) => (s.id === stepId ? { ...s, status, thinking: thinking.length ? thinking : s.thinking, details: details ?? s.details, elapsed_ms: elapsed_ms ?? s.elapsed_ms, timestamp: timestamp ?? s.timestamp } : s));
      }
      const next: ProcessStep[] = [
        ...prev,
        {
          id: stepId,
          name: STEP_NAME[stepId] || stepId,
          status,
          thinking,
          details,
          elapsed_ms,
          timestamp,
        },
      ];
      next.sort((a, b) => STEP_ORDER.indexOf(a.id) - STEP_ORDER.indexOf(b.id));
      return next;
    });
  };

  const simulatePreSteps = async () => {
    // Pre-steps simulation for better UX
    await sleep(100);
    updateStepStatus('intent_detection', 'in_progress', ['Analyzing query intent...']);
    await sleep(100);
    updateStepStatus('intent_detection', 'completed', ['Intent detected']);
    await sleep(100);
    updateStepStatus('plan_generation', 'in_progress', ['Planning query execution...']);
    await sleep(100);
    updateStepStatus('plan_generation', 'completed', ['Query plan ready']);
  };

  const stopAnalysis = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    setIsLoading(false);
    setCurrentStatus('Analysis stopped');
    setProcessSteps((prev) => prev.map((s) => (s.status === 'in_progress' ? { ...s, status: 'stopped' } : s)));
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
      const resp = await fetch(`${configService.getBackendUrl()}/api/analytics/memory/clarify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(answer),
      });
      if (!resp.ok) {
        const j = await resp.json().catch(() => ({} as any));
        throw new Error(j.error || `HTTP ${resp.status}`);
      }
      setPendingClarification(null);
    } catch (e: any) {
      setError(`Failed to submit clarification: ${e?.message || e}`);
    }
  };

  const handleAnalyticsQuery = async () => {
    if (!query.trim() || isLoading) return;
    setIsLoading(true);
    setError('');
    setChartSpec(null);
    setAnalysis('');
    setSqlQuery('');
    setStreamingText('');
    setProcessSteps([]);
    setUseAltChart(false);
    setChartRetryCount(0);
    setDataSample(null);
    setPendingClarification(null);
    abortControllerRef.current = new AbortController();

    // Simulate pre-steps with brief delays for modern UX
    simulatePreSteps();

    try {
      await apiService.streamWithAuth(
        `/api/analytics/memory/stream?query=${encodeURIComponent(query)}${sessionId ? `&session_id=${sessionId}` : ''}`,
        (data) => {
          try {
            console.log('[MEMORY DEBUG] Received event:', data.event || data.type, data);
            const eventType = data.event || data.type;
            const eventData = data.data || data;
            
            switch (eventType) {
              case 'session_started':
                setSessionId(eventData.session_id);
                break;
                
              case 'status':
                setCurrentStatus(eventData.message || '');
                if (eventData.step) {
                  updateStepStatus(eventData.step, 'in_progress', [], undefined, eventData.elapsed_ms, eventData.ts);
                }
                break;
                
              case 'intent_draft':
                updateStepStatus('intent_detection', 'in_progress', ['Intent detected; needs clarification'], eventData, eventData.elapsed_ms);
                break;
                
              case 'intent_decided':
              case 'intent_resolved':
                updateStepStatus('intent_detection', 'completed', [], eventData, eventData.elapsed_ms);
                break;
                
              case 'clarification_request':
                setPendingClarification(eventData as ClarifyRequest);
                updateStepStatus('clarification', 'in_progress', [eventData.question]);
                setCurrentStatus(`Clarification needed: ${eventData.question}`);
                break;
                
              case 'clarification_ack':
                setPendingClarification(null);
                updateStepStatus('clarification', 'completed');
                break;
                
              case 'clarification_timeout':
                setPendingClarification(null);
                updateStepStatus('clarification', 'completed', ['Timed out; using default']);
                break;
                
              case 'plan_built':
                updateStepStatus('plan_generation', 'completed', [], { plan: eventData.plan }, eventData.elapsed_ms);
                break;
                
              case 'template_selected':
                updateStepStatus('template_selection', 'completed', [], { template: eventData.template }, eventData.elapsed_ms);
                break;
                
              case 'sql_compiled':
                updateStepStatus('sql_compilation', 'completed', [], undefined, eventData.elapsed_ms);
                break;
                
              case 'sql_validated':
                updateStepStatus('sql_validation', eventData.validation?.ok ? 'completed' : 'error', [], { validation: eventData.validation }, eventData.elapsed_ms);
                break;
                
              case 'sql_generated':
                if (eventData.sql) {
                  setSqlQuery(eventData.sql);
                  updateStepStatus('sql_compilation', 'completed');
                }
                break;
                
              case 'execution_stats':
                updateStepStatus('sql_execution', 'completed', [], { row_count: eventData.row_count, columns: eventData.columns }, eventData.elapsed_ms);
                break;
                
              case 'data_retrieved':
                if (Array.isArray(eventData.sample_data)) {
                  setDataSample(eventData.sample_data);
                  updateStepStatus('sql_execution', 'completed', [], { 
                    rowCount: eventData.row_count,
                    sampleData: eventData.sample_data 
                  });
                }
                break;
                
              case 'chart_planned':
                updateStepStatus('chart_generation', 'in_progress', [], eventData, eventData.elapsed_ms);
                break;
                
              case 'chart_generated':
                if (eventData.chart_spec) {
                  try {
                    // Ensure spec is an object for ECharts
                    if (typeof eventData.chart_spec === 'string') {
                      const parsed = JSON.parse(eventData.chart_spec);
                      if (isValidChartSpec(parsed)) {
                        setChartSpec(parsed);
                        setUseAltChart(false);
                        updateStepStatus('chart_generation', 'completed');
                      } else {
                        throw new Error('Invalid chart spec structure');
                      }
                    } else {
                      if (isValidChartSpec(eventData.chart_spec)) {
                        setChartSpec(eventData.chart_spec);
                        setUseAltChart(false);
                        updateStepStatus('chart_generation', 'completed');
                      } else {
                        throw new Error('Invalid chart spec structure');
                      }
                    }
                    console.log('[MEMORY DEBUG] Received chart spec keys:', Object.keys(eventData.chart_spec || {}));
                  } catch (e) {
                    console.error('Chart spec parse error:', e);
                    // Add retry logic instead of immediate fallback
                    if (chartRetryCount < 2) {
                      console.log(`[MEMORY DEBUG] Chart retry ${chartRetryCount + 1}/2`);
                      setChartRetryCount(prev => prev + 1);
                      // Retry after a short delay
                      setTimeout(() => {
                        setChartSpec(eventData.chart_spec);
                        setUseAltChart(false);
                      }, 100);
                    } else {
                      setUseAltChart(true);
                      updateStepStatus('chart_generation', 'error');
                    }
                  }
                }
                break;
                
              case 'warning':
                console.warn('[MEMORY DEBUG] Warning:', eventData.message);
                break;
                
              case 'analysis_streaming':
                if (eventData.partial_analysis) {
                  console.log('[MEMORY DEBUG] Streaming analysis chunk:', eventData.partial_analysis.substring(0, 50));
                  setStreamingText((prev) => (prev || '') + eventData.partial_analysis);
                  setAnalysis((prev) => (prev || '') + eventData.partial_analysis);
                  updateStepStatus('analysis_generation', 'in_progress', ['🧠 Streaming financial analysis...']);
                }
                break;
                
              case 'analysis_complete':
                if (eventData.analysis) {
                  console.log('[MEMORY DEBUG] Setting final analysis:', eventData.analysis.substring(0, 100));
                  setAnalysis(eventData.analysis);
                  updateStepStatus('analysis_generation', 'completed');
                }
                break;
                
              case 'errors':
              case 'error':
                setError(eventData.message || (Array.isArray(eventData.errors) ? eventData.errors.join(' | ') : 'Error'));
                setCurrentStatus('Error occurred during analysis');
                setIsLoading(false);
                break;
                
              case 'workflow_complete':
                setCurrentStatus('Analytics memory workflow completed!');
                setIsLoading(false);
                break;
                
              case 'done':
                setIsLoading(false);
                break;
                
              case 'heartbeat':
                console.log('[MEMORY DEBUG] Heartbeat received');
                break;
            }
          } catch (e) {
            console.error('Error parsing SSE data:', e);
          }
        },
        (err, needsAuth) => {
          setError(needsAuth ? 'Authentication required. Please sign in.' : err);
          setIsLoading(false);
        },
        () => {
          console.log('Stream completed');
        },
        abortControllerRef.current?.signal,
      );
    } catch (e) {
      if ((e as any)?.name !== 'AbortError') setError('Failed to start analytics');
      setIsLoading(false);
    }
  };

  const suggestedQueries = [
    'Nvidia market share in the past 5 years?',
    "How's Nvidia margin growth compare to industry average?",
    'How is NVDA R&D expense compare to industry average',
    'How fast is NVDA growing vs industry average?',
  ];

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100 overflow-hidden">
      {/* Main Content */}
      <div className={`flex-1 flex flex-col transition-all duration-300 overflow-hidden ${showProcessPanel ? 'md:mr-80' : ''}`}>
        {/* Header */}
        <div className="bg-gray-800 border-b border-gray-700">
          <div className="w-full max-w-5xl mx-auto flex flex-col md:flex-row items-center gap-3 sm:gap-4 md:gap-6 p-3 sm:p-4 md:p-6 lg:p-8">
            <div className="flex-1 text-center md:text-left">
              <h1 className="text-xl sm:text-2xl md:text-3xl lg:text-4xl font-bold text-white">{projectData.title}</h1>
              <ul className="mt-2 sm:mt-3 md:mt-4 text-gray-300 text-xs sm:text-sm md:text-base space-y-0.5 sm:space-y-1 md:space-y-1.5">
                <li>• Conversational clarifications with streaming analysis</li>
                <li>• Advanced intent detection and query planning</li>
                <li className="hidden sm:block">• Semiconductor tickers: AMD, AVGO, INTC, MU, NVDA, QCOM, TXN</li>
              </ul>
              <div className="mt-2 sm:mt-3 md:mt-4 flex flex-wrap gap-1.5 sm:gap-2 md:gap-2.5 justify-center md:justify-start">
                {projectData.technologies.map((tag) => (
                  <span key={tag} className="px-2 sm:px-3 py-0.5 sm:py-1 md:py-1.5 rounded-full bg-gray-700 text-gray-200 text-[10px] sm:text-xs md:text-sm border border-gray-600 shadow-inner">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            <div className="hidden md:block w-full md:w-1/3">
              <img src={projectData.imageUrl} alt={projectData.title} className="w-full h-40 sm:h-48 object-cover rounded-lg border border-gray-700 shadow" />
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-4 sm:p-6 lg:p-8 pb-32 md:pb-6 bg-gray-900">
          <div className="w-full max-w-5xl mx-auto space-y-4 sm:space-y-6">
            {pendingClarification && (
              <ClarifyInline
                request={pendingClarification}
                onSubmit={async (val) => submitClarification(val, pendingClarification)}
                disabled={isLoading === false}
              />
            )}

            {chartSpec && !useAltChart && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8">
                <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Interactive Visualization</h2>
                <div className="h-[280px] sm:h-[360px] md:h-[440px] lg:h-[520px] bg-white rounded-lg p-2 sm:p-3">
                  <ChartErrorBoundary onError={() => setUseAltChart(true)}>
                    <EChartsReact option={withLightTheme(chartSpec)} style={{ height: 'calc(100% - 4px)', width: '100%' }} />
                  </ChartErrorBoundary>
                </div>
              </motion.div>
            )}

            {!chartSpec && useAltChart && dataSample && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8">
                <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Interactive Visualization (Fallback)</h2>
                <div className="h-64 sm:h-80 md:h-96 bg-gray-900 rounded-lg p-4 sm:p-6 text-gray-300 text-sm sm:text-base">
                  Unable to render chart spec. Showing sample data preview:
                  <pre className="mt-2 overflow-auto">{JSON.stringify(dataSample.slice(0, 5), null, 2)}</pre>
                </div>
              </motion.div>
            )}

            {analysis && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8">
                <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Financial Analysis</h2>
                <div className="prose prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{analysis}</ReactMarkdown>
                </div>
              </motion.div>
            )}

            {sqlQuery && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8">
                <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Generated SQL Query</h2>
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 sm:p-6 overflow-x-auto">
                  <pre className="text-green-400 text-sm sm:text-base font-mono whitespace-pre-wrap">{sqlQuery}</pre>
                </div>
              </motion.div>
            )}
          </div>
        </div>

        {/* Bottom Input Bar */}
        <div className="fixed md:sticky bottom-0 left-0 right-0 md:left-auto md:right-auto bg-gray-800/95 backdrop-blur-sm border-t border-gray-700 z-30">
          {(isLoading || currentStatus !== 'Ready to analyze financial data with intelligent memory...' || error) && (
            <div className="px-4 sm:px-6 md:px-8 py-2 sm:py-3 border-b border-gray-700">
              <div className="w-full max-w-5xl mx-auto flex items-center gap-3">
                {isLoading && <div className="animate-spin h-4 w-4 border-2 border-blue-400 rounded-full border-t-transparent" />}
                <span className="text-blue-300 text-xs sm:text-sm font-medium flex-1 truncate">{currentStatus}</span>
                {error && <span className="text-red-400 text-xs sm:text-sm truncate">{error}</span>}
              </div>
            </div>
          )}

          <div className="px-4 sm:px-6 lg:px-8 py-3 sm:py-4">
            <div className="w-full max-w-5xl mx-auto">
              {!isLoading && (
                <div className="flex gap-2 overflow-x-auto py-1 sm:py-2 -mx-2 px-2">
                  {suggestedQueries.map((s, i) => (
                    <button key={i} onClick={() => setQuery(s)} className="px-3 py-1.5 text-xs md:text-sm bg-gradient-to-r from-gray-700 to-gray-600 hover:from-gray-600 hover:to-gray-500 rounded-full text-gray-100 border border-gray-600/60 whitespace-nowrap">
                      {s}
                    </button>
                  ))}
                </div>
              )}

              <div className="mt-3 sm:mt-4 flex items-center gap-2 sm:gap-3">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={pendingClarification ? 'Please answer the clarification above to continue…' : 'Ask about NVDA, AMD, AVGO, INTC, MU, QCOM, TXN'}
                  className="flex-1 px-4 py-3.5 text-sm md:text-base bg-gray-700/80 backdrop-blur-sm border border-gray-600/50 rounded-xl focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 text-gray-100 placeholder-gray-400 min-h-[48px] shadow-lg"
                  onKeyDown={(e) => e.key === 'Enter' && handleAnalyticsQuery()}
                  disabled={isLoading || !!pendingClarification}
                />
                <button
                  onClick={isLoading ? stopAnalysis : handleAnalyticsQuery}
                  disabled={(!query.trim() && !isLoading) || !!pendingClarification}
                  className={`px-4 sm:px-6 py-3.5 text-sm md:text-base rounded-xl font-medium min-h-[48px] shadow-lg ${
                    isLoading ? 'bg-red-600/90 hover:bg-red-600 text-white' : 'bg-blue-600/90 hover:bg-blue-600 text-white disabled:bg-gray-600/50'
                  }`}
                >
                  {isLoading ? 'Stop' : 'Analyze'}
                </button>
                <button
                  onClick={() => setShowProcessPanel(!showProcessPanel)}
                  className="flex items-center justify-center px-3 py-3.5 text-sm bg-gray-700/80 text-gray-200 rounded-xl hover:bg-gray-600/80 border border-gray-600/50 min-h-[48px] shadow-lg min-w-[48px] sm:min-w-[120px]"
                >
                  {showProcessPanel ? (
                    <>
                      <span className="w-5 h-5 inline-block"><ChevronRightIcon /></span>
                      <span className="hidden sm:inline ml-2">Hide Progress</span>
                    </>
                  ) : (
                    <>
                      <span className="w-5 h-5 inline-block"><ChevronLeftIcon /></span>
                      <span className="hidden sm:inline ml-2">Show Progress</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Process Visualization Panel */}
      <AnimatePresence>
        {showProcessPanel && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden" onClick={() => setShowProcessPanel(false)} />
            <motion.div initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', damping: 25, stiffness: 200 }} className="fixed inset-y-0 right-0 w-full md:w-80 bg-gray-800 md:border-l border-gray-700 shadow-2xl z-50 flex flex-col">
              <div className="p-4 sm:p-6 border-b border-gray-700 flex items-center justify-between">
                <div>
                  <h2 className="text-lg sm:text-xl font-semibold text-white">LangGraph Process</h2>
                  <p className="text-sm text-gray-400">Real-time workflow visualization</p>
                </div>
                <button onClick={() => setShowProcessPanel(false)} className="md:hidden p-2 hover:bg-gray-700 rounded-lg transition-colors">×</button>
              </div>
              <div className="flex-1 overflow-auto p-4 sm:p-6">
                <div className="relative">
                  {processSteps.length > 1 && <div className="absolute left-3 top-7 bottom-7 w-1 bg-gradient-to-b from-blue-500/60 via-purple-500/60 to-pink-500/60 rounded-full opacity-40" />}
                  <div className="space-y-3">
                    {processSteps.map((step, index) => (
                      <motion.div key={step.id} initial={{ opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ delay: index * 0.05, type: 'spring', stiffness: 220, damping: 22 }} className={`relative pl-10 pr-3 py-4 rounded-xl border backdrop-blur-sm ${
                        step.status === 'completed' ? 'bg-green-500/10 border-green-400/30' :
                        step.status === 'in_progress' ? 'bg-blue-500/10 border-blue-400/30' :
                        step.status === 'stopped' ? 'bg-yellow-500/10 border-yellow-400/30' :
                        step.status === 'error' ? 'bg-red-500/10 border-red-400/30' : 'bg-gray-700/40 border-gray-600/40'
                      }`}>
                        <div className={`absolute left-0 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center shadow-md ${
                          step.status === 'completed' ? 'bg-green-500 text-white' :
                          step.status === 'in_progress' ? 'bg-blue-500 text-white animate-pulse' :
                          step.status === 'stopped' ? 'bg-yellow-500 text-white' :
                          step.status === 'error' ? 'bg-red-500 text-white' : 'bg-gray-600 text-white/80'
                        }`}>
                          {step.status === 'completed' ? '✓' : step.status === 'error' ? '!' : step.status === 'stopped' ? '■' : '•'}
                        </div>
                        <div className="font-semibold text-gray-100">{step.name}</div>
                        {step.thinking.length > 0 && (
                          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }} className="mt-1 text-xs text-gray-300">
                            {step.thinking[0]}
                          </motion.div>
                        )}
                        {step.elapsed_ms && (
                          <div className="mt-1 text-xs text-gray-400">
                            {step.elapsed_ms}ms
                          </div>
                        )}
                      </motion.div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
};

export default AnalyticsMemoryPage;