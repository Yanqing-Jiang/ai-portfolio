import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { AnalysisCard, SqlCard, ChartCard } from '../common';
import { useAnalyticsSqlStream } from '../hooks';
import { isValidChartSpec } from '../utils';

// Simple, lightweight process panel to avoid blank screen rendering and keep telemetry visible.
const SimpleProcessPanel: React.FC<{
  open: boolean;
  steps: ReturnType<typeof useAnalyticsSqlStream>['processSteps'];
  onClose: () => void;
}> = ({ open, steps, onClose }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 pointer-events-none">
      <div className="absolute top-16 right-4 w-[360px] max-h-[78vh] rounded-xl border border-gray-800 bg-gray-950/95 shadow-2xl overflow-hidden pointer-events-auto">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
          <div className="text-sm font-semibold text-gray-100">SQL Process</div>
          <button
            onClick={onClose}
            className="text-gray-300 hover:text-white text-xs px-2 py-1 rounded border border-gray-700 hover:border-gray-500"
          >
            Close
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto p-3 space-y-2 bg-gray-900/70">
          {steps.length === 0 ? (
            <div className="text-xs text-gray-400 border border-dashed border-gray-700 rounded-lg px-3 py-4 text-center">
              Waiting for telemetry…
            </div>
          ) : (
            steps.map((step) => {
              const statusClass =
                step.status === 'completed'
                  ? 'bg-emerald-500/20 text-emerald-200'
                  : step.status === 'in_progress'
                  ? 'bg-blue-500/20 text-blue-200'
                  : step.status === 'error'
                  ? 'bg-rose-500/20 text-rose-200'
                  : 'bg-gray-700/50 text-gray-300';
              return (
                <div
                  key={step.id}
                  className="rounded-lg border border-gray-800 bg-gray-900/80 px-3 py-2"
                >
                  <div className="flex items-center justify-between text-xs text-gray-200">
                    <span className="font-semibold truncate pr-2">{step.name}</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] uppercase tracking-wide ${statusClass}`}
                    >
                      {step.status.replace('_', ' ')}
                    </span>
                  </div>
                  {step.thinking?.length ? (
                    <div className="mt-1 text-[11px] text-gray-400 line-clamp-2">
                      {step.thinking.slice(-1)[0]}
                    </div>
                  ) : null}
                  {step.details ? (
                    <div className="mt-1 text-[10px] text-gray-500 line-clamp-2">
                      {Object.keys(step.details)
                        .slice(0, 2)
                        .map((k) => `${k}: ${String((step.details as any)[k])}`)
                        .join(' • ')}
                    </div>
                  ) : null}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
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
      <div className={`flex-1 flex flex-col transition-all duration-300 overflow-hidden ${showProcessPanel ? 'md:mr-80' : ''}`}>
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
                  <button
                    onClick={() => setShowProcessPanel(!showProcessPanel)}
                    className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors"
                  >
                    {showProcessPanel ? 'Hide' : 'Show'} Process
                  </button>
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
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => setShowProcessPanel(!showProcessPanel)}
                    className="px-3 py-1.5 text-xs bg-gray-700/90 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors"
                  >
                    {showProcessPanel ? 'Hide' : 'Show'} Process
                  </button>
                </div>
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

      {/* Simple Process Panel (lightweight to avoid blank rendering) */}
      <SimpleProcessPanel
        open={showProcessPanel}
        steps={processSteps}
        onClose={() => setShowProcessPanel(false)}
      />
    </div>
  );
};

export default SqlAnalyticsPage;

