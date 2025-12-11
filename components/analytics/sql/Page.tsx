import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AnalysisCard, SqlCard, ChartCard } from '../common';
import { useAnalyticsSqlStream } from '../hooks';
import { isValidChartSpec } from '../utils';

/**
 * Function: ProcessNodeIcon — Renders an icon based on step status.
 * Called from: DiagramProcessPanel node rendering
 * Invokes: None
 * Why: Visual status indication for each process node
 */
const ProcessNodeIcon: React.FC<{ status: string; isExpanded?: boolean }> = ({ status, isExpanded }) => {
  if (status === 'completed') {
    return (
      <motion.div 
        initial={{ scale: 0 }} 
        animate={{ scale: 1 }} 
        className="w-5 h-5 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/30"
      >
        <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
        </svg>
      </motion.div>
    );
  }
  if (status === 'in_progress') {
    return (
      <div className="relative w-5 h-5">
        <motion.div 
          animate={{ rotate: 360 }} 
          transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
          className="w-5 h-5 rounded-full border-2 border-cyan-400 border-t-transparent shadow-lg shadow-cyan-500/30"
        />
        <div className="absolute inset-0 rounded-full bg-cyan-400/20 animate-ping" />
      </div>
    );
  }
  if (status === 'error') {
    return (
      <motion.div 
        initial={{ scale: 0 }} 
        animate={{ scale: 1 }}
        className="w-5 h-5 rounded-full bg-gradient-to-br from-rose-400 to-rose-600 flex items-center justify-center shadow-lg shadow-rose-500/30"
      >
        <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </motion.div>
    );
  }
  if (status === 'stopped') {
    return (
      <div className="w-5 h-5 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/30">
        <div className="w-2 h-2 bg-white rounded-sm" />
      </div>
    );
  }
  return (
    <div className="w-5 h-5 rounded-full bg-gray-700/80 border-2 border-gray-600 shadow-inner" />
  );
};

/**
 * Function: DiagramProcessPanel — Modern diagram-based SQL process visualization.
 * Called from: SqlAnalyticsPage
 * Invokes: ProcessNodeIcon
 * Why: Provides visual feedback for the SQL workflow process with expandable nodes
 */
const DiagramProcessPanel: React.FC<{
  open: boolean;
  steps: ReturnType<typeof useAnalyticsSqlStream>['processSteps'];
  onClose: () => void;
}> = ({ open, steps, onClose }) => {
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({});

  const toggleStep = (stepId: string) => {
    setExpandedSteps(prev => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  // Calculate progress
  const completedCount = steps.filter(s => s.status === 'completed').length;
  const progressPercent = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0;

  // Panel animation variants
  const panelVariants = {
    hidden: { 
      x: '100%', 
      opacity: 0,
      transition: { duration: 0.3, ease: [0.4, 0, 0.2, 1] }
    },
    visible: { 
      x: 0, 
      opacity: 1,
      transition: { duration: 0.4, ease: [0, 0, 0.2, 1] }
    }
  };

  // Node animation variants
  const nodeVariants = {
    hidden: { opacity: 0, x: 20, scale: 0.95 },
    visible: (i: number) => ({
      opacity: 1,
      x: 0,
      scale: 1,
      transition: { 
        delay: i * 0.08,
        duration: 0.35,
        ease: [0, 0, 0.2, 1]
      }
    })
  };

  // Details animation
  const detailsVariants = {
    hidden: { height: 0, opacity: 0 },
    visible: { 
      height: 'auto', 
      opacity: 1,
      transition: { duration: 0.25, ease: [0, 0, 0.2, 1] }
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial="hidden"
          animate="visible"
          exit="hidden"
          variants={panelVariants}
          className="fixed top-0 right-0 h-screen w-full sm:w-[340px] md:w-[380px] lg:w-[420px] max-w-[420px] z-50 flex flex-col bg-gray-900/95 shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="flex-shrink-0 px-5 py-4 border-b border-cyan-500/10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-white tracking-wide">SQL Pipeline</h3>
                  <p className="text-[11px] text-gray-400 mt-0.5">Real-time process flow</p>
                </div>
              </div>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={onClose}
                className="w-8 h-8 rounded-lg bg-gray-800/60 hover:bg-gray-700/80 border border-gray-700/50 hover:border-gray-600 flex items-center justify-center transition-all duration-200"
              >
                <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </motion.button>
            </div>

            {/* Progress Bar */}
            {steps.length > 0 && (
              <div className="mt-4">
                <div className="flex items-center justify-between text-[10px] text-gray-400 mb-2">
                  <span>{completedCount} of {steps.length} completed</span>
                  <span className="text-cyan-400 font-medium">{progressPercent}%</span>
                </div>
                <div className="h-1.5 bg-gray-800/80 rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${progressPercent}%` }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                    className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 shadow-lg shadow-cyan-500/30"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Process Diagram */}
          <div className="flex-1 overflow-y-auto overflow-x-hidden px-4 py-5 custom-scrollbar">
            {steps.length === 0 ? (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col items-center justify-center h-full text-center px-6"
              >
                <div className="w-16 h-16 rounded-2xl bg-gray-800/50 border border-gray-700/50 flex items-center justify-center mb-4">
                  <motion.div
                    animate={{ rotate: [0, 10, -10, 0] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                  >
                    <svg className="w-8 h-8 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </motion.div>
                </div>
                <p className="text-sm text-gray-400 font-medium">Awaiting query</p>
                <p className="text-xs text-gray-500 mt-1">Process flow will appear here</p>
              </motion.div>
            ) : (
              <div>
                {/* Process nodes */}
                <div className="space-y-3">
                  {steps.map((step, index) => {
                    const isExpanded = expandedSteps[step.id];
                    const statusColors = {
                      completed: { bg: 'from-emerald-500/10 to-emerald-600/5', border: 'border-emerald-500/30', text: 'text-emerald-300' },
                      in_progress: { bg: 'from-cyan-500/10 to-blue-500/5', border: 'border-cyan-500/40', text: 'text-cyan-300' },
                      error: { bg: 'from-rose-500/10 to-rose-600/5', border: 'border-rose-500/30', text: 'text-rose-300' },
                      stopped: { bg: 'from-amber-500/10 to-amber-600/5', border: 'border-amber-500/30', text: 'text-amber-300' },
                      pending: { bg: 'from-gray-500/10 to-gray-600/5', border: 'border-gray-600/30', text: 'text-gray-400' }
                    };
                    const colors = statusColors[step.status as keyof typeof statusColors] || statusColors.pending;

                    return (
                      <motion.div
                        key={step.id}
                        custom={index}
                        initial="hidden"
                        animate="visible"
                        variants={nodeVariants}
                        className="relative"
                      >
                        <motion.button
                          onClick={() => toggleStep(step.id)}
                          whileHover={{ scale: 1.01, x: 2 }}
                          whileTap={{ scale: 0.99 }}
                          className={`w-full text-left pl-9 pr-3 py-3 rounded-xl bg-gradient-to-r ${colors.bg} border ${colors.border} transition-all duration-200 hover:shadow-lg group`}
                          style={{ boxShadow: step.status === 'in_progress' ? '0 0 20px rgba(56, 189, 248, 0.15)' : undefined }}
                        >
                          {/* Node icon - positioned on the vertical line */}
                          <div className="absolute left-0 top-1/2 -translate-y-1/2 z-10">
                            <ProcessNodeIcon status={step.status} isExpanded={isExpanded} />
                          </div>

                          <div className="flex items-center justify-between">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold text-white truncate">{step.name}</span>
                                <span className={`text-[9px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded ${colors.text} bg-white/5`}>
                                  {step.status.replace('_', ' ')}
                                </span>
                              </div>
                              {step.thinking?.length ? (
                                <p className="text-[11px] text-gray-400 mt-1 line-clamp-1 pr-4">
                                  {step.thinking.slice(-1)[0]}
                                </p>
                              ) : null}
                            </div>
                            <motion.div
                              animate={{ rotate: isExpanded ? 180 : 0 }}
                              transition={{ duration: 0.2 }}
                              className="ml-2 text-gray-500 group-hover:text-gray-300"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                              </svg>
                            </motion.div>
                          </div>
                        </motion.button>

                        {/* Expandable details */}
                        <AnimatePresence>
                          {isExpanded && (
                            <motion.div
                              initial="hidden"
                              animate="visible"
                              exit="hidden"
                              variants={detailsVariants}
                              className="overflow-hidden"
                            >
                              <div className="ml-9 mt-2 p-3 rounded-lg bg-gray-900/60 border border-gray-800/50 space-y-3">
                                {/* Thinking section */}
                                {step.thinking?.length ? (
                                  <div>
                                    <div className="text-[9px] uppercase tracking-wider text-gray-500 mb-1.5 flex items-center gap-1.5">
                                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                      </svg>
                                      Agent Thoughts
                                    </div>
                                    <div className="space-y-1">
                                      {step.thinking.slice(-3).map((thought, i) => (
                                        <p key={i} className="text-[11px] text-gray-300 leading-relaxed pl-2 border-l-2 border-gray-700">
                                          {thought}
                                        </p>
                                      ))}
                                    </div>
                                  </div>
                                ) : null}

                                {/* Details/Telemetry */}
                                {step.details && Object.keys(step.details).length > 0 && (
                                  <div>
                                    <div className="text-[9px] uppercase tracking-wider text-gray-500 mb-1.5 flex items-center gap-1.5">
                                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                      </svg>
                                      Telemetry
                                    </div>
                                    <div className="grid grid-cols-2 gap-2">
                                      {Object.entries(step.details as Record<string, any>)
                                        .filter(([, v]) => v != null && v !== '')
                                        .slice(0, 6)
                                        .map(([key, value]) => (
                                          <div key={key} className="bg-gray-800/50 rounded-md p-2">
                                            <div className="text-[9px] text-gray-500 truncate">{key}</div>
                                            <div className="text-[10px] text-gray-200 truncate font-mono">
                                              {typeof value === 'object' ? JSON.stringify(value).slice(0, 30) + '...' : String(value).slice(0, 30)}
                                            </div>
                                          </div>
                                        ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </motion.div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

        </motion.div>
      )}
    </AnimatePresence>
  );
};

const SqlAnalyticsPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [showProcessPanel, setShowProcessPanel] = useState(false);
  const [useAltChart, setUseAltChart] = useState(false);
  const [hasStartedChat, setHasStartedChat] = useState(false);
  const [isHeaderCollapsed, setIsHeaderCollapsed] = useState(false);

  // Reset header to expanded state when component mounts (project navigation)
  useEffect(() => {
    setIsHeaderCollapsed(false);
    setHasStartedChat(false);
  }, []);

  const {
    // State
    chartSpec,
    analysis,
    sqlQuery,
    dataSample,
    streamingText,
    flowMode,
    
    // Stream state
    isLoading,
    error,
    currentStatus,
    
    // Process steps
    processSteps,
    
    // Actions
    handleQuery,
    stopAnalysis,
    resetAll,
    clearChartSpec,
  } = useAnalyticsSqlStream();

  // Debug logging
  React.useEffect(() => {
    if (chartSpec) {
      console.log('[SQL Page] chartSpec updated:', chartSpec);
      console.log('[SQL Page] isValidChartSpec result:', isValidChartSpec(chartSpec));
    }
  }, [chartSpec]);

  // Project data for the SQL analytics project
  const projectData = {
    title: 'Next Gen Analytics (SQL)',
    description: `**Streamlined workflow**: Query analysis -> SQL generation -> chart creation -> insight delivery.
**Interactive financial analysis**: AMD, AVGO, INTC, MU, NVDA, QCOM, TXN with optimized performance.
**Real-time streaming analytics**: Comprehensive charting and data export.
**Direct database queries**: Intelligent chart generation with detailed financial commentary.`,
    technologies: ['Direct SQL workflow', 'Query analysis', 'Chart generation', 'Real-time streaming', 'Data exports', 'Financial insights'],
    imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/next-gen-sql.png'
  };

  const handleAnalyticsQuery = async () => {
    if (!query.trim() || isLoading) return;
    const queryToSubmit = query.trim();
    setUseAltChart(false);
    setQuery(''); // Clear input after starting analysis
    
    // Auto-collapse header on first query
    if (!hasStartedChat) {
      setHasStartedChat(true);
      setIsHeaderCollapsed(true);
    }
    
    await handleQuery(queryToSubmit);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAnalyticsQuery();
    }
  };

  const suggestedQueries = [
    'Show Nvidia market share in the past 5 years?',
    'Compare profit margins between tech companies',
    'How is AMD  R&D expense compare to industry average',
    'AMD vs NVIDIA revenue comparison 2021-2024'
  ];

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100 overflow-hidden">
      {/* Main Content */}
      <div
        className={`flex-1 flex flex-col transition-[margin] duration-300 ease-in-out overflow-hidden ${
          showProcessPanel ? 'sm:mr-0 md:mr-[360px] lg:mr-[420px]' : ''
        }`}
      >
        {/* Enhanced Header */}
        <motion.div 
          initial={false}
          animate={isHeaderCollapsed ? { height: 60 } : { height: 'auto' }}
          transition={{ duration: 0.3, ease: 'easeInOut' }}
          className="flex-shrink-0 border-b border-gray-700 bg-gray-800 overflow-hidden"
        >
          {isHeaderCollapsed ? (
            // Collapsed header view
            <div className="h-full flex items-center justify-between px-4 md:px-6 lg:px-8">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <h2 className="text-lg md:text-xl font-bold text-white truncate">{projectData.title}</h2>
                <div className="hidden sm:flex gap-2">
                  {projectData.technologies.slice(0, 3).map(tech => (
                    <span 
                      key={tech} 
                      className="px-2 py-0.5 rounded-full bg-gray-700 text-gray-200 text-xs border border-gray-600"
                    >
                      {tech}
                    </span>
                  ))}
                  {projectData.technologies.length > 3 && (
                    <span className="px-2 py-0.5 rounded-full bg-gray-700 text-gray-200 text-xs border border-gray-600">
                      +{projectData.technologies.length - 3}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {hasStartedChat && (
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setShowProcessPanel(!showProcessPanel)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 ${
                      showProcessPanel 
                        ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-lg shadow-cyan-500/10' 
                        : 'bg-gray-700/80 hover:bg-gray-600/80 text-gray-200 border border-gray-600/50 hover:border-gray-500/50'
                    }`}
                  >
                    {showProcessPanel ? 'Hide Pipeline' : 'Show Pipeline'}
                  </motion.button>
                )}
                <button
                  onClick={() => setIsHeaderCollapsed(!isHeaderCollapsed)}
                  className="p-2 hover:bg-gray-700 rounded-lg transition-colors text-gray-400 hover:text-white shrink-0"
                  title="Expand header"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
              </div>
            </div>
          ) : (
            // Expanded header view - compact design
            <div className="p-2 sm:p-3 md:p-4 lg:p-5 relative">
              {/* Remove standalone Show Process button - only keep it in collapsed view */}
              
              <div className="flex flex-col md:flex-row gap-3 sm:gap-4 md:gap-5">
                {/* Project content - responsive layout */}
                <div className="flex-1 flex flex-col justify-center min-w-0">
                  <h2 className="text-lg sm:text-xl md:text-2xl lg:text-3xl font-bold text-white 
                                 mb-2 sm:mb-2.5 md:mb-3 leading-tight">
                    {projectData.title}
                  </h2>
                  
                  <div className="text-gray-400 text-xs sm:text-sm md:text-base 
                                  max-w-none md:max-w-2xl mb-2 sm:mb-3 md:mb-4 
                                  space-y-1 sm:space-y-1.5 overflow-y-auto flex-1 md:flex-none">
                    {projectData.description.split('\n').map((line, idx) => {
                      const trimmed = line.trim();
                      if (!trimmed) {
                        return null;
                      }
                      const boldMatch = trimmed.match(/^\*\*(.+?)\*\*(?::\s*)?(.*)$/);
                      if (boldMatch) {
                        const [, label, rest] = boldMatch;
                        const restText = rest?.trim() ?? '';
                        return (
                          <p key={idx} className="leading-relaxed">
                            <span className="font-semibold text-gray-200">{label}</span>
                            {restText && <span className="text-gray-400">: {restText}</span>}
                          </p>
                        );
                      }

                      return <p key={idx} className="leading-relaxed">{trimmed}</p>;
                    })}
                  </div>
                  
                  {/* Technology tags - compact sizing */}
                  <div className="flex gap-1 sm:gap-1.5 flex-wrap mt-auto">
                    {projectData.technologies.map(tech => (
                      <span 
                        key={tech} 
                        className="bg-gray-700 text-gray-300 text-[10px] sm:text-xs font-medium 
                                 px-1.5 sm:px-2 py-0.5 sm:py-1 rounded-full whitespace-nowrap"
                      >
                        {tech}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Project image - responsive */}
                {projectData.imageUrl && (
                  <div className="order-first md:order-none w-full md:w-1/3 lg:w-2/5 flex justify-center md:justify-end mb-3 md:mb-0 flex-shrink-0">
                    <img
                      src={projectData.imageUrl}
                      alt={projectData.title}
                      className="w-full max-w-sm sm:max-w-md md:max-w-full h-auto rounded-xl object-contain shadow-xl"
                    />
                  </div>
                )}
              </div>

              {/* Collapse button - bottom right */}
              <button
                onClick={() => setIsHeaderCollapsed(!isHeaderCollapsed)}
                className="absolute bottom-1 right-1 p-1.5 hover:bg-gray-700 rounded-lg transition-colors text-gray-400 hover:text-white"
                title="Collapse header"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                </svg>
              </button>
            </div>
          )}
        </motion.div>

        {/* Main Content Area */}
        <div className="flex-1 overflow-auto p-4 sm:p-6 lg:p-8 pb-32 md:pb-6 bg-gray-900">
          <div className="w-full max-w-5xl mx-auto space-y-4 sm:space-y-6 overflow-hidden">
            
            {/* Chart Display */}
            {chartSpec && isValidChartSpec(chartSpec) && (
              <ChartCard
                chartSpec={chartSpec}
                dataSample={dataSample}
                onError={() => {
                  clearChartSpec();
                  setUseAltChart(true);
                }}
                enableDropdown={true}
                enableCsvDownload={true}
              />
            )}

            {/* Fallback Chart */}
            {!chartSpec && useAltChart && dataSample && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8">
                <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Data Preview (Fallback)</h2>
                <div className="h-64 sm:h-80 md:h-96 bg-gray-900 rounded-lg p-4 sm:p-6 text-gray-300 text-sm sm:text-base">
                  Unable to render chart. Showing sample data preview:
                  <pre className="mt-2 overflow-auto">{JSON.stringify(dataSample.slice(0, 5), null, 2)}</pre>
                </div>
              </motion.div>
            )}

            {/* Analysis Display */}
            <AnalysisCard analysis={analysis || streamingText} />

            {/* SQL Query Display */}
            <SqlCard sqlQuery={sqlQuery} />
          </div>
        </div>

        {/* Bottom Chat/Input Bar (fixed position on mobile, sticky on desktop) */}
        <div className="fixed md:sticky bottom-0 left-0 right-0 md:left-auto md:right-auto bg-gray-800/95 backdrop-blur-sm border-t border-gray-700 z-30">
          {/* Status + Error */}
          {(isLoading || Boolean(currentStatus) || error) && (
            <div className="px-4 sm:px-6 md:px-8 py-2 sm:py-3 border-b border-gray-700">
              <div className="w-full max-w-5xl mx-auto flex items-center gap-3 sm:gap-4 overflow-hidden">
                {isLoading && (
                  <div className="flex items-center gap-2 text-sm text-blue-400">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                )}
                <div className="text-sm text-gray-300 min-w-0 flex-1 truncate">{currentStatus}</div>
              </div>
              {error && (
                <div className="mt-2 bg-red-900/30 border border-red-700/50 rounded-lg p-2">
                  <div className="text-red-300 text-xs">{error}</div>
                </div>
              )}
            </div>
          )}

          {/* Input Section */}
          <div className="px-4 sm:px-6 md:px-8 py-3 sm:py-4">
            <div className="w-full max-w-5xl mx-auto">
              {/* Suggested queries (only show when not loading) */}
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
                  placeholder="Ask about financial data on NVDA, AMD, AVGO, INTC, MU, QCOM, TXN"
                  className="flex-1 px-4 py-3.5 text-sm md:text-base bg-gray-700/80 backdrop-blur-sm border border-gray-600/50 rounded-xl focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 text-gray-100 placeholder-gray-400 min-h-[48px] shadow-lg transition-all duration-200 min-w-0"
                  onKeyPress={handleKeyPress}
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
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Diagram Process Panel - Modern diagram-based visualization */}
      <DiagramProcessPanel
        open={showProcessPanel}
        steps={processSteps}
        onClose={() => setShowProcessPanel(false)}
      />
    </div>
  );
};

export default SqlAnalyticsPage;

