import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
// ECharts removed; using Vega-Lite
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { ChevronLeftIcon } from './icons/ChevronLeftIcon';
import { ChevronRightIcon } from './icons/ChevronRightIcon';
import EChartsReact from 'echarts-for-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
  
  const abortControllerRef = useRef<AbortController | null>(null);

  const isValidChartSpec = (spec: any) => {
    try {
      if (!spec || typeof spec !== 'object') return false;
      if (!Array.isArray(spec.series)) return false;
      return true;
    } catch {
      return false;
    }
  };

  const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

  const simulatePreSteps = async () => {
    // Show panel for visibility
    setShowProcessPanel(true);
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
    setDataSample(null);

    // Create new AbortController for this request
    abortControllerRef.current = new AbortController();

    // Simulate pre-steps with brief delays for modern UX
    simulatePreSteps();

    try {
      await fetchEventSource(`http://localhost:8000/api/analytics/stream?query=${encodeURIComponent(query)}`, {
        signal: abortControllerRef.current.signal,
        onmessage: (event) => {
          try {
            const data: any = JSON.parse(event.data);
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
                    setUseAltChart(true);
                    updateStepStatus('chart', 'error');
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
        onopen: async (response) => {
          if (response.ok) {
            console.log('Analytics stream connected');
          } else {
            throw new Error(`HTTP ${response.status}`);
          }
        },
        onerror: (err) => {
          console.error('Analytics stream error:', err);
          setError('Connection error occurred');
          setIsLoading(false);
        }
      });
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
    <div className="flex h-screen bg-gray-900 text-gray-100">
      {/* Main Content */}
      <div className={`flex-1 flex flex-col transition-all duration-300 ${showProcessPanel ? 'mr-80' : ''}`}>
        {/* Header */}
        <div className="bg-gray-800 border-b border-gray-700">
          <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center gap-4 p-4 sm:p-6">
            {/* Left: Text */}
            <div className="flex-1 text-center md:text-left">
              <h1 className="text-2xl sm:text-3xl font-bold text-white">Next Gen Analytics (SQL)</h1>
              <p className="text-gray-300 mt-1">Agentic Workflow • SQL Agent • Agentic Charting • Dynamic Download</p>
              {/* Feature bullets */}
              <ul className="mt-3 text-gray-300 text-sm sm:text-base space-y-1">
                <li>• Tired of looking for answers in Dashboard? try ask questions and get a direct answer.</li>
                <li>• Dynamic table selection and schema detection</li>
                <li>• Dynamic Charting and Data download</li>
              </ul>
              {/* Tech tabs/pills */}
              <div className="mt-3 flex flex-wrap gap-2 justify-center md:justify-start">
                {['Agentic Workflow','SQL Agent','Agentic Charting','Dynamic Download'].map((tag) => (
                  <span
                    key={tag}
                    className="px-3 py-1 rounded-full bg-gray-700 text-gray-200 text-xs sm:text-sm border border-gray-600 shadow-inner"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            {/* Right: Image */}
            <div className="w-full md:w-1/3">
              <img
                src="https://yanqinghot.blob.core.windows.net/public-access/next-gen-sql.png"
                alt="Next Gen Analytics (SQL)"
                className="w-full h-40 sm:h-48 object-cover rounded-lg border border-gray-700 shadow"
              />
            </div>
          </div>
        </div>

        {/* Summary section removed per request */}

        {/* Main Content Area */}
        <div className="flex-1 overflow-auto p-4 sm:p-6 pb-6 bg-gray-900">
          <div className="max-w-6xl mx-auto space-y-4 sm:space-y-6">
            
            {/* Chart Display with ECharts (guarded by error boundary) */}
            {chartSpec && !useAltChart && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6"
              >
                <h2 className="text-xl font-semibold text-white mb-4">Interactive Visualization</h2>
                <div className="h-[360px] sm:h-[440px] lg:h-[520px] bg-white rounded-lg p-2">
                  {/* Controls row */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 text-gray-700 text-sm">
                      <label className="font-medium">Series:</label>
                      <select
                        className="bg-gray-100 border border-gray-300 rounded px-2 py-1 text-sm"
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
                  <ChartErrorBoundary onError={() => setUseAltChart(true)}>
                    <EChartsReact 
                      option={withLightTheme(chartSpec)} 
                      style={{ height: 'calc(100% - 36px)', width: '100%' }} 
                      opts={{ renderer: 'canvas' }} 
                      onChartReady={(instance) => { (window as any)._echarts_instance_ = instance; }}
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
                className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6"
              >
                <h2 className="text-xl font-semibold text-white mb-4">Interactive Visualization (Fallback)</h2>
                <div className="h-96 bg-gray-900 rounded-lg p-4 text-gray-300 text-sm">
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
                className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6"
              >
                <h2 className="text-xl font-semibold text-white mb-4">Financial Analysis</h2>
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
                className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-6"
              >
                <h2 className="text-xl font-semibold text-white mb-4">Generated SQL Query</h2>
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 overflow-x-auto">
                  <pre className="text-green-400 text-sm font-mono whitespace-pre-wrap">
                    {sqlQuery}
                  </pre>
                </div>
              </motion.div>
            )}

          </div>
        </div>

        {/* Bottom Chat/Input Bar (sticky within content area to avoid covering sidebar/menu) */}
        <div className="sticky bottom-0 bg-gray-800 border-t border-gray-700">
          {/* Status + Error */}
          {(isLoading || currentStatus !== 'Ready to analyze financial data...' || error) && (
            <div className="px-6 py-2 border-b border-gray-700">
              <div className="max-w-6xl mx-auto flex items-center gap-3">
                {isLoading && (
                  <div className="animate-spin h-4 w-4 border-2 border-blue-400 rounded-full border-t-transparent" />
                )}
                <span className="text-blue-300 text-xs sm:text-sm font-medium flex-1 truncate">{currentStatus}</span>
                {error && <span className="text-red-400 text-xs">{error}</span>}
              </div>
            </div>
          )}

          {/* Prompts and Controls */}
          <div className="px-4 sm:px-6 py-3">
            <div className="max-w-6xl mx-auto">
              {/* Prompt chips row (scroll horizontally to the right) */}
              {!isLoading && (
                <div className="flex gap-2 overflow-x-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800 py-1">
                  {suggestedQueries.map((suggestion, idx) => (
                    <button
                      key={idx}
                      onClick={() => setQuery(suggestion)}
                      className="px-3 py-1.5 text-xs sm:text-sm bg-gradient-to-r from-gray-700 to-gray-600 hover:from-gray-600 hover:to-gray-500 rounded-full text-gray-100 transition-colors border border-gray-600/60 whitespace-nowrap shadow-sm"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}

              {/* Input row */}
              <div className="mt-3 flex gap-2 sm:gap-3 items-center">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask about financial data..."
                  className="flex-1 px-3 sm:px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100 placeholder-gray-400"
                onKeyPress={(e) => e.key === 'Enter' && handleAnalyticsQuery()}
                disabled={isLoading}
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={isLoading ? stopAnalysis : handleAnalyticsQuery}
                  disabled={!query.trim() && !isLoading}
                  className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                    isLoading 
                      ? 'bg-red-600 hover:bg-red-700 text-white'
                      : 'bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-600 disabled:cursor-not-allowed'
                  }`}
                >
                  {isLoading ? 'Stop' : 'Analyze'}
                </button>
                <button
                  onClick={() => setShowProcessPanel(!showProcessPanel)}
                  className="flex items-center gap-2 px-3 py-2 bg-gray-700 text-gray-200 rounded-lg hover:bg-gray-600 transition-colors border border-gray-600"
                >
                  {showProcessPanel ? (
                    <>
                      <span className="w-4 h-4 inline-block"><ChevronRightIcon /></span>
                      Hide Progress
                    </>
                  ) : (
                    <>
                      <span className="w-4 h-4 inline-block"><ChevronLeftIcon /></span>
                      Show Progress
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
          <motion.div
            initial={{ x: 320 }}
            animate={{ x: 0 }}
            exit={{ x: 320 }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 h-full w-80 bg-gray-800 border-l border-gray-700 shadow-2xl z-50 flex flex-col"
          >
            <div className="p-4 border-b border-gray-700">
              <h2 className="text-lg font-semibold text-white">LangGraph Process</h2>
              <p className="text-sm text-gray-400">Real-time workflow visualization</p>
            </div>
            
            <div className="flex-1 overflow-auto p-4">
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
        )}
      </AnimatePresence>
      </div>
    </div>
  );
};

export default AnalyticsPage;