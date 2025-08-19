import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
// ECharts removed; using Vega-Lite
import { ChevronLeftIcon } from './icons/ChevronLeftIcon';
import { ChevronRightIcon } from './icons/ChevronRightIcon';
import EChartsReact from 'echarts-for-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiService } from '../services/apiService';
import { configService } from '../services/config';

// Removed unused AnalyticsMessage interface

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

interface ProcessStep {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'stopped';
  thinking: string[];
  details?: any;
}

const AnalyticsPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [chartSpec, setChartSpec] = useState<any>(null);
  const [analysis, setAnalysis] = useState('');
  const [sqlQuery, setSqlQuery] = useState('');
  const [dataSample, setDataSample] = useState<any[] | null>(null);
  // Start with no steps; they will appear in real-time as they start processing
  const [processSteps, setProcessSteps] = useState<ProcessStep[]>([]);
  const STEP_NAME: Record<string, string> = {
    table: 'Database Table Selection',
    schema: 'Schema Detection',
    sql: 'SQL Generation',
    chart: 'Chart Creation',
    analysis: 'Financial Analysis',
  };
  const STEP_ORDER = ['table', 'schema', 'sql', 'chart', 'analysis'];
  const [currentStatus, setCurrentStatus] = useState('Ready to analyze financial data...');
  const [showProcessPanel, setShowProcessPanel] = useState(false);
  const [streamingText, setStreamingText] = useState(''); // kept for UI; now updated without duplication
  const [error, setError] = useState('');
  const [useAltChart, setUseAltChart] = useState(false);
  const [chartRetryCount, setChartRetryCount] = useState(0);
  
  const abortControllerRef = useRef<AbortController | null>(null);

  // Project data for the analytics project
  const projectData = {
    title: 'Next Gen Analytics (SQL)',
    description: `• AI-powered financial analytics chatbot that queries semiconductor company financials via an agentic SQL workflow.
• Uses LangGraph agents to coordinate schema understanding → SQL generation → Charting Agent → financial analysis.
• Real-time streaming with progressive chart updates and expandable process visualization panel.

Result:

• Interactive financial analysis for AMD, AVGO, INTC, MU, NVDA, QCOM, TXN with 29 key metrics.
• Streaming agent coordination with live process visualization.
• Dynamic Charting Agent and Context Engineering for comprehensive financial insights.`,
    technologies: ['LangGraph', 'Agentic Workflow', 'SQL Agent', 'Charting Agent', 'Context Engineering', 'FastAPI', 'PostgreSQL'],
    imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/next-gen-sql.png'
  };

  const isValidChartSpec = (spec: any) => {
    try {
      if (!spec || typeof spec !== 'object') return false;
      // More permissive validation - allow both series array and other chart types
      if (spec.series && !Array.isArray(spec.series)) return false;
      // Also accept chart specs without series (like pie charts, etc.)
      return true;
    } catch {
      return false;
    }
  };

  const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

  const simulatePreSteps = async () => {
    // Pre-steps simulation - panel will only show if user manually toggles it
    await sleep(100);
    updateStepStatus('table', 'in_progress', ['Database Table Selection']);
    await sleep(100);
    updateStepStatus('table', 'completed', ['Table selected']);
    await sleep(100);
    updateStepStatus('schema', 'in_progress', ['Schema Detection']);
    await sleep(100);
    updateStepStatus('schema', 'completed', ['8 Schema Detected']);
  };

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

    // Axis formatting: percent vs currency based on series meta
    const percentSeries = new Set<string>(Object.entries((spec.meta?.seriesValueType || {}))
      .filter(([_, v]) => v === 'percent')
      .map(([k]) => k));
    const usesPercent = Object.keys(spec.meta?.seriesValueType || {}).some((k) => percentSeries.has(k));

    const formatPercent = (v: any) => {
      const num = typeof v === 'number' ? v : Number(v);
      if (Number.isFinite(num)) return `${(num * 100).toFixed(0)}%`;
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
      axisLabel: { ...((ax || {}).axisLabel || {}), color: '#555555', formatter: (ax?.axisLabel?.formatter ?? axisFormatter) },
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
        const isPercent = percentSeries.has(p.seriesName);
        const val = p.value;
        const formatted = isPercent ? formatPercent(val) : formatCurrency0(val);
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
          formatter: (params: any) => (percentSeries.has(params.seriesName) ? formatPercent(params.value) : formatCurrency0(params.value)),
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

  const handleAnalyticsQuery = async () => {
    if (!query.trim() || isLoading) return;

    // Reset state
    setIsLoading(true);
    setError('');
    setChartSpec(null);
    setAnalysis('');
    setSqlQuery('');
    setStreamingText('');
    // Clear previous steps; show in real-time as they start
    setProcessSteps([]);
    setUseAltChart(false);
    setChartRetryCount(0);
    setDataSample(null);

    // Create new AbortController for this request
    abortControllerRef.current = new AbortController();

    // Simulate pre-steps with brief delays for modern UX
    simulatePreSteps();

    try {
      await apiService.streamWithAuth(
        `/api/analytics/stream?query=${encodeURIComponent(query)}`,
        (data) => {
          try {
            console.log('[FRONTEND DEBUG] Received event:', data.event || data.type, data);
            
            // Handle new event structure
            const eventType = data.event || data.type;
            const eventData = data.data || data;
            
            switch (eventType) {
              case 'status':
                setCurrentStatus(eventData.message || '');
                if (eventData.step) {
                  // Map backend step names to frontend step ids
                  const stepMapping: { [key: string]: string } = {
                    'sql_agent': 'sql',
                    'sql_generation': 'sql',
                    'echarts_agent': 'chart',
                    'chart_generation': 'chart',
                    'analysis_agent': 'analysis',
                    'analysis_generation': 'analysis'
                  };
                  const stepId = stepMapping[eventData.step] || eventData.step;
                  console.log('[FRONTEND DEBUG] Updating step:', eventData.step, '->', stepId);
                  updateStepStatus(stepId, 'in_progress', eventData.thinking || []);
                }
                break;
                
              case 'sql_generated':
                if (eventData.sql) {
                  setSqlQuery(eventData.sql);
                  updateStepStatus('sql', 'completed');
                }
                break;
                
              case 'data_retrieved':
                setDataSample(eventData.sample_data || null);
                updateStepStatus('sql', 'completed', [], { 
                  rowCount: eventData.row_count,
                  sampleData: eventData.sample_data 
                });
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
                        updateStepStatus('chart', 'completed');
                      } else {
                        throw new Error('Invalid chart spec structure');
                      }
                    } else {
                      if (isValidChartSpec(eventData.chart_spec)) {
                        setChartSpec(eventData.chart_spec);
                        setUseAltChart(false);
                        updateStepStatus('chart', 'completed');
                      } else {
                        throw new Error('Invalid chart spec structure');
                      }
                    }
                    console.log('[FRONTEND DEBUG] Received chart spec keys:', Object.keys(eventData.chart_spec || {}));
                  } catch (e) {
                    console.error('Chart spec parse error:', e);
                    // Add retry logic instead of immediate fallback
                    if (chartRetryCount < 2) {
                      console.log(`[FRONTEND DEBUG] Chart retry ${chartRetryCount + 1}/2`);
                      setChartRetryCount(prev => prev + 1);
                      // Retry after a short delay
                      setTimeout(() => {
                        setChartSpec(eventData.chart_spec);
                        setUseAltChart(false);
                      }, 100);
                    } else {
                      setUseAltChart(true);
                      updateStepStatus('chart', 'error');
                    }
                  }
                }
                break;
                
              case 'analysis_complete':
                if (eventData.analysis) {
                  console.log('[FRONTEND DEBUG] Setting final analysis:', eventData.analysis.substring(0, 100));
                  setAnalysis(eventData.analysis);
                  updateStepStatus('analysis', 'completed');
                }
                break;
                
              case 'analysis_streaming':
                if (eventData.partial_analysis) {
                  console.log('[FRONTEND DEBUG] Streaming analysis chunk:', eventData.partial_analysis.substring(0, 50));
                  // Append streaming chunks so text grows progressively
                  setStreamingText(prev => (prev || '') + eventData.partial_analysis);
                  setAnalysis(prev => (prev || '') + eventData.partial_analysis);
                  updateStepStatus('analysis', 'in_progress', ['🧠 Streaming financial analysis...']);
                }
                break;

              case 'errors_verbose':
                console.warn('[FRONTEND DEBUG] Verbose errors:', eventData.error_details);
                break;
                
              case 'error':
                setError(eventData.message || eventData.errors?.[0] || 'An error occurred');
                setCurrentStatus('Error occurred during analysis');
                setIsLoading(false);
                break;

              case 'errors':
                if (Array.isArray(eventData.errors) && eventData.errors.length > 0) {
                  const msg = eventData.errors.join(' | ');
                  setError(msg);
                  setCurrentStatus('Error occurred during analysis');
                  setIsLoading(false);
                  // If echarts failed, switch to alt chart automatically
                  if (msg.toLowerCase().includes('echarts')) {
                    setUseAltChart(true);
                  }
                }
                break;
                
              case 'workflow_complete':
                setCurrentStatus('Analysis completed successfully!');
                setIsLoading(false);
                break;
                
              case 'heartbeat':
                console.log('[FRONTEND DEBUG] Received heartbeat');
                break;
                
              case 'done':
                setIsLoading(false);
                break;
            }
          } catch (e) {
            console.error('Error parsing SSE data:', e);
          }
        },
        (error, needsAuth) => {
          console.error('Analytics stream error:', error);
          if (needsAuth) {
            setError('Authentication required. Please sign in to continue.');
          } else {
            setError(error || 'Connection error occurred');
          }
          setIsLoading(false);
        },
        () => {
          console.log('Analytics stream completed');
        }
      );
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('Analytics request error:', err);
        setError('Failed to start analytics');
        setIsLoading(false);
      }
    }
  };

  const toThinkingArray = (value: unknown): string[] => {
    if (Array.isArray(value)) {
      return value.filter((v) => typeof v === 'string') as string[];
    }
    if (typeof value === 'string' && value.trim().length > 0) {
      return [value];
    }
    return [];
  };

  const updateStepStatus = (stepId: string, status: ProcessStep['status'], thinkingInput: unknown = [], details?: any) => {
    const thinking = toThinkingArray(thinkingInput);
    setProcessSteps(prev => {
      const existing = prev.find(s => s.id === stepId);
      if (existing) {
        return prev.map(s => s.id === stepId
          ? { ...s, status, thinking: thinking.length ? thinking : s.thinking, details: details || s.details }
          : s
        );
      }
      // Insert new step with friendly name and maintain desired order
      const newStep: ProcessStep = {
        id: stepId,
        name: STEP_NAME[stepId] || stepId,
        status,
        thinking: thinking,
        details,
      };
      const next = [...prev, newStep];
      next.sort((a, b) => STEP_ORDER.indexOf(a.id) - STEP_ORDER.indexOf(b.id));
      return next;
    });
  };

  const stopAnalysis = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsLoading(false);
    setCurrentStatus('Analysis stopped');
    // Mark the current in-progress step as stopped
    setProcessSteps(prev => prev.map(s => s.status === 'in_progress' ? { ...s, status: 'stopped' } : s));
  };

  const suggestedQueries = [
    'Nvidia market share in the past 5 years?',
    "How's Nvidia margin growth compare to peers?",
    'How is NVDA R&D expense compare',
    'How fast is NVDA growing vs peers?'
  ];

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100 overflow-hidden">
      {/* Main Content */}
      <div className={`flex-1 flex flex-col transition-all duration-300 overflow-hidden ${showProcessPanel ? 'md:mr-80' : ''}`}>
        {/* Header */}
        <div className="bg-gray-800 border-b border-gray-700">
          <div className="w-full max-w-5xl mx-auto flex flex-col md:flex-row items-center gap-4 sm:gap-6 p-4 sm:p-6 lg:p-8 xl:p-12 overflow-hidden">
            {/* Left: Text */}
            <div className="flex-1 text-center md:text-left">
              <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-white">Next Gen Analytics (SQL)</h1>
              {/* Feature bullets */}
              <ul className="mt-3 sm:mt-4 text-gray-300 text-sm sm:text-base space-y-1 sm:space-y-1.5">
                <li>• Tired of finding what you need on a dashboard? try ask questions directly</li>
                <li>• Automated chart generation with streaming data analysis</li>
                <li>• Semi-conductor industry tickers for AMD, AVGO, INTC, MU, NVDA, QCOM, TXN</li>
              </ul>
              {/* Tech tags/pills */}
              <div className="mt-3 sm:mt-4 flex flex-wrap gap-2 sm:gap-2.5 justify-center md:justify-start">
                {['Agentic Workflow','SQL Agent','Charting Agent','Context Engineering'].map((tag) => (
                  <span
                    key={tag}
                    className="px-3 py-1 sm:py-1.5 rounded-full bg-gray-700 text-gray-200 text-xs sm:text-sm border border-gray-600 shadow-inner"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            {/* Right: Image - Hidden on mobile */}
            <div className="hidden md:block w-full md:w-1/3 shrink-0 min-w-0">
              <img
                src="https://yanqinghot.blob.core.windows.net/public-access/next-gen-sql.png"
                alt="Next Gen Analytics (SQL)"
                className="w-full h-40 sm:h-48 object-cover rounded-lg border border-gray-700 shadow max-w-full"
              />
            </div>
          </div>
        </div>

        {/* Summary section removed per request */}

        {/* Main Content Area */}
        <div className="flex-1 overflow-auto p-4 sm:p-6 lg:p-8 xl:p-12 pb-32 md:pb-6 bg-gray-900">
          <div className="w-full max-w-5xl mx-auto space-y-4 sm:space-y-6 overflow-hidden">
            
            {/* Chart Display with ECharts (guarded by error boundary) */}
            {chartSpec && !useAltChart && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8"
              >
                <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Interactive Visualization</h2>
                <div className="h-[280px] sm:h-[360px] md:h-[440px] lg:h-[520px] bg-white rounded-lg p-2 sm:p-3">
                  {/* Controls row */}
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-4 mb-3 sm:mb-2">
                    <div className="flex items-center gap-2 text-gray-700 text-sm sm:text-base">
                      <label className="font-medium">Series:</label>
                      <select
                        className="bg-gray-100 border border-gray-300 rounded px-2 sm:px-3 py-1 sm:py-1.5 text-sm sm:text-base min-h-[32px] sm:min-h-[36px]"
                        onChange={(e) => {
                          const selected = e.target.value
                          // Toggle legend selection by series name match
                          const instance = (window as any)._echarts_instance_;
                          if (instance) {
                            const current = instance.getOption();
                            const legend = current.legend && current.legend[0];
                            if (legend && legend.data) {
                              const selectedMap: any = legend.selected || {};
                              // Turn all off first, then enable chosen series
                              legend.data.forEach((name: string) => selectedMap[name] = false);
                              // Try to find matching by suffix after dash as well
                              const target = legend.data.find((name: string) => name === selected || name.endsWith(' - ' + selected));
                              if (target) selectedMap[target] = true;
                              instance.setOption({ legend: [{ selected: selectedMap }] });
                            }
                          }
                        }}
                        defaultValue={((chartSpec.meta?.defaultColumns || []).map((c: string) => c.replace(/_/g, ' ').replace(/\b\w/g, (m: string) => m.toUpperCase())))[0]}
                      >
                        {(chartSpec.meta?.includedColumns || []).map((c: string) => {
                          const label = c.replace(/_/g, ' ').replace(/\b\w/g, (m: string) => m.toUpperCase());
                          return <option key={c} value={label}>{label}</option>;
                        })}
                      </select>
                    </div>
                    <button
                      className="px-3 py-1.5 bg-gray-100 border border-gray-300 rounded text-gray-700 text-sm hover:bg-gray-200"
                      onClick={() => {
                        try {
                          const rows: any[] = Array.isArray(chartSpec.meta?.rawData) ? chartSpec.meta.rawData : [];
                          if (!rows.length) return;
                          const headersSet = new Set<string>();
                          rows.forEach(r => Object.keys(r || {}).forEach(k => headersSet.add(k)));
                          const headers = Array.from(headersSet);
                          const escape = (v: any) => {
                            if (v === null || v === undefined) return '';
                            const s = String(v).replace(/"/g, '""');
                            return '"' + s + '"';
                          };
                          const lines = [headers.join(',')];
                          for (const r of rows) {
                            lines.push(headers.map(h => escape((r as any)[h])).join(','));
                          }
                          const csv = '\uFEFF' + lines.join('\r\n'); // BOM for Excel
                          const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = 'analytics_data.csv';
                          a.click();
                          URL.revokeObjectURL(url);
                        } catch (e) {
                          console.error('Download failed', e);
                        }
                      }}
                    >
                      Download CSV
                    </button>
                  </div>
                  <ChartErrorBoundary key={`chart-${chartRetryCount}-${JSON.stringify(chartSpec)?.substring(0,50)}`} onError={(error) => {
                    console.log('[FRONTEND DEBUG] Chart error boundary triggered:', error);
                    // Only switch to alt chart after multiple failures
                    if (chartRetryCount >= 1) {
                      setUseAltChart(true);
                    } else {
                      // First error - increment retry count and try again
                      setChartRetryCount(prev => prev + 1);
                      setTimeout(() => {
                        // Force re-render by updating chartSpec
                        setChartSpec(current => ({ ...current }));
                      }, 200);
                    }
                  }}>
                    <EChartsReact 
                      option={withLightTheme(chartSpec)} 
                      style={{ height: 'calc(100% - 36px)', width: '100%' }} 
                      opts={{ renderer: 'canvas', devicePixelRatio: window.devicePixelRatio }} 
                      onChartReady={(instance) => { 
                        (window as any)._echarts_instance_ = instance;
                        // Small delay to ensure proper initialization
                        setTimeout(() => instance.resize(), 100);
                      }}
                    />
                  </ChartErrorBoundary>
                </div>
              </motion.div>
            )}

            {/* Fallback preview if ECharts fails */}
            {!chartSpec && useAltChart && dataSample && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8"
              >
                <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Interactive Visualization (Fallback)</h2>
                <div className="h-64 sm:h-80 md:h-96 bg-gray-900 rounded-lg p-4 sm:p-6 text-gray-300 text-sm sm:text-base">
                  Unable to render chart spec. Showing sample data preview:
                  <pre className="mt-2 overflow-auto">{JSON.stringify(dataSample.slice(0, 5), null, 2)}</pre>
                </div>
              </motion.div>
            )}

            {/* Analysis Display */}
            {analysis && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8"
              >
                <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Financial Analysis</h2>
                <div className="prose prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {analysis}
                  </ReactMarkdown>
                </div>
              </motion.div>
            )}

            {/* SQL Query Display */}
            {sqlQuery && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8"
              >
                <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Generated SQL Query</h2>
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 sm:p-6 overflow-x-auto">
                  <pre className="text-green-400 text-sm sm:text-base font-mono whitespace-pre-wrap">
                    {sqlQuery}
                  </pre>
                </div>
              </motion.div>
            )}

          </div>
        </div>

        {/* Bottom Chat/Input Bar (fixed position on mobile, sticky on desktop) */}
        <div className="fixed md:sticky bottom-0 left-0 right-0 md:left-auto md:right-auto bg-gray-800/95 backdrop-blur-sm border-t border-gray-700 z-30">
          {/* Status + Error */}
          {(isLoading || currentStatus !== 'Ready to analyze financial data...' || error) && (
            <div className="px-4 sm:px-6 md:px-8 py-2 sm:py-3 border-b border-gray-700">
              <div className="w-full max-w-5xl mx-auto flex items-center gap-3 sm:gap-4 overflow-hidden">
                {isLoading && (
                  <div className="animate-spin h-4 w-4 sm:h-5 sm:w-5 border-2 border-blue-400 rounded-full border-t-transparent" />
                )}
                <span className="text-blue-300 text-xs sm:text-sm font-medium flex-1 truncate">{currentStatus}</span>
                {error && <span className="text-red-400 text-xs sm:text-sm truncate max-w-xs sm:max-w-none">{error}</span>}
              </div>
            </div>
          )}

          {/* Prompts and Controls */}
          <div className="px-4 sm:px-6 lg:px-16 xl:px-24 py-3 sm:py-4">
            <div className="w-full max-w-5xl mx-auto overflow-hidden">
              {/* Prompt chips row (scroll horizontally to the right) */}
              {!isLoading && (
                <div className="flex gap-2 sm:gap-2.5 overflow-x-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800 py-1 sm:py-2 -mx-2 sm:-mx-1 px-2 sm:px-1 max-w-full">
                  {suggestedQueries.map((suggestion, idx) => (
                    <button
                      key={idx}
                      onClick={() => setQuery(suggestion)}
                      className="px-2 sm:px-3 md:px-4 py-1 sm:py-1.5 md:py-2 text-[10px] sm:text-xs md:text-sm bg-gradient-to-r from-gray-700 to-gray-600 hover:from-gray-600 hover:to-gray-500 rounded-full text-gray-100 transition-colors border border-gray-600/60 whitespace-nowrap shadow-sm min-h-[28px] sm:min-h-[32px] md:min-h-[36px] flex items-center"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}

              {/* Input row */}
              <div className="mt-3 sm:mt-4 flex items-center gap-2 sm:gap-3 w-full">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask about financial data on NVDA, AMD, AVGO, INTC, MU, NVDA, QCOM, TXN"
                  className="flex-1 px-4 py-3.5 text-sm md:text-base bg-gray-700/80 backdrop-blur-sm border border-gray-600/50 rounded-xl focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 text-gray-100 placeholder-gray-400 min-h-[48px] shadow-lg transition-all duration-200 min-w-0"
                  onKeyPress={(e) => e.key === 'Enter' && handleAnalyticsQuery()}
                  disabled={isLoading}
                />
                <button
                  onClick={isLoading ? stopAnalysis : handleAnalyticsQuery}
                  disabled={!query.trim() && !isLoading}
                  className={`px-4 sm:px-6 py-3.5 text-sm md:text-base rounded-xl font-medium transition-all duration-200 min-h-[48px] shrink-0 shadow-lg ${
                    isLoading 
                      ? 'bg-red-600/90 hover:bg-red-600 text-white'
                      : 'bg-blue-600/90 hover:bg-blue-600 text-white disabled:bg-gray-600/50 disabled:cursor-not-allowed'
                  }`}
                >
                  {isLoading ? 'Stop' : 'Analyze'}
                </button>
                <button
                  onClick={() => setShowProcessPanel(!showProcessPanel)}
                  className="flex items-center justify-center px-3 py-3.5 text-sm bg-gray-700/80 text-gray-200 rounded-xl hover:bg-gray-600/80 transition-all duration-200 border border-gray-600/50 min-h-[48px] shrink-0 shadow-lg min-w-[48px] sm:min-w-[120px]"
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

      {/* Process Visualization Panel */}
      <AnimatePresence>
        {showProcessPanel && (
          <>
            {/* Mobile Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden"
              onClick={() => setShowProcessPanel(false)}
            />
            {/* Panel */}
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="fixed inset-y-0 right-0 w-full md:w-80 max-w-sm md:max-w-none bg-gray-800 md:border-l border-gray-700 shadow-2xl z-50 flex flex-col"
            >
            {/* Panel Header */}
            <div className="p-4 sm:p-6 border-b border-gray-700 flex items-center justify-between">
              <div>
                <h2 className="text-lg sm:text-xl font-semibold text-white">LangGraph Process</h2>
                <p className="text-sm text-gray-400">Real-time workflow visualization</p>
              </div>
              {/* Mobile Close Button */}
              <button 
                onClick={() => setShowProcessPanel(false)}
                className="md:hidden p-2 hover:bg-gray-700 rounded-lg transition-colors"
              >
                <span className="w-5 h-5 text-gray-400 block">✕</span>
              </button>
            </div>
            
            <div className="flex-1 overflow-auto p-4 sm:p-6">
              <div className="relative">
                {processSteps.length > 1 && (
                  <div className="absolute left-3 top-7 bottom-7 w-1 bg-gradient-to-b from-blue-500/60 via-purple-500/60 to-pink-500/60 rounded-full opacity-40" />
                )}
                <div className="space-y-2">
                  {processSteps.map((step, index) => (
                    <motion.div
                      key={step.id}
                      initial={{ opacity: 0, y: 16, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ delay: index * 0.08, type: 'spring', stiffness: 220, damping: 22 }}
                      className={`relative pl-10 pr-3 py-3 rounded-xl border backdrop-blur-sm ${
                        step.status === 'completed' ? 'bg-green-500/10 border-green-400/30' :
                        step.status === 'in_progress' ? 'bg-blue-500/10 border-blue-400/30' :
                        step.status === 'stopped' ? 'bg-yellow-500/10 border-yellow-400/30' :
                        step.status === 'error' ? 'bg-red-500/10 border-red-400/30' :
                        'bg-gray-700/40 border-gray-600/40'
                      }`}
                    >
                      {/* Node */}
                      <div className={`absolute left-0 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center shadow-md ${
                        step.status === 'completed' ? 'bg-green-500 text-white' :
                        step.status === 'in_progress' ? 'bg-blue-500 text-white animate-pulse' :
                        step.status === 'stopped' ? 'bg-yellow-500 text-white' :
                        step.status === 'error' ? 'bg-red-500 text-white' :
                        'bg-gray-600 text-white/80'
                      }`}>
                        {step.status === 'completed' ? '✓' : step.status === 'error' ? '!' : step.status === 'stopped' ? '■' : '•'}
                      </div>

                      {/* Content */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-gray-100">{step.name}</span>
                        {index < processSteps.length - 1 && (
                          <motion.span
                            initial={{ opacity: 0, x: -6 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: 0.12 }}
                            className="ml-auto mr-1 text-gray-400"
                          >
                            →
                          </motion.span>
                        )}
                      </div>
                      {step.thinking.length > 0 && (
                        <motion.div
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: 0.05 }}
                          className="mt-1 text-xs text-gray-300"
                        >
                          {step.thinking[0]}
                        </motion.div>
                      )}
                      {step.details?.rowCount && (
                        <div className="mt-1 text-xs text-gray-400">
                          Retrieved {step.details.rowCount} rows
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
    </div>
  );
};

export default AnalyticsPage;