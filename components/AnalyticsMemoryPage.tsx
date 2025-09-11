import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeftIcon } from './icons/ChevronLeftIcon';
import { ChevronRightIcon } from './icons/ChevronRightIcon';
import { configService } from '../services/config';

// Import modular components
import { 
  ChartErrorBoundary, 
  Header, 
  ChartCard, 
  AnalysisCard, 
  SqlCard 
} from './analytics/common';
import { ChatHistory } from './analytics/memory';
import { useAnalyticsMemoryStream } from './analytics/hooks';
import { withLightTheme, isValidChartSpec } from './analytics/utils';

const AnalyticsMemoryPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [showProcessPanel, setShowProcessPanel] = useState(false);
  const [useAltChart, setUseAltChart] = useState(false);
  const [chartRetryCount, setChartRetryCount] = useState(0);

  const {
    // State
    chatHistory,
    chartSpec,
    analysis,
    sqlQuery,
    dataSample,
    streamingText,
    
    // Stream state
    isLoading,
    error,
    currentStatus,
    
    // Process steps
    processSteps,
    
    // Actions
    handleQuery,
    submitClarification,
    stopAnalysis,
  } = useAnalyticsMemoryStream();

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

  const handleAnalyticsQuery = async () => {
    if (!query.trim() || isLoading) return;
    const queryToSubmit = query.trim();
    setQuery(''); // Clear input after starting analysis
    await handleQuery(queryToSubmit);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAnalyticsQuery();
    }
  };

  const suggestedQueries = [
    'Nvidia market share in the past 5 years?',
    "How's Nvidia margin growth compare to industry average?",
    'How is NVDA R&D expense compare to industry average',
    'How fast is NVDA growing vs industry average?'
  ];

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100 overflow-hidden">
      {/* Main Content */}
      <div className={`flex-1 flex flex-col transition-all duration-300 overflow-hidden ${showProcessPanel ? 'md:mr-80' : ''}`}>
        {/* Header */}
        <div className="bg-gray-800 border-b border-gray-700">
          <div className="w-full max-w-5xl mx-auto flex flex-col md:flex-row items-center gap-3 sm:gap-4 md:gap-6 p-3 sm:p-4 md:p-6 lg:p-8 overflow-hidden">
            {/* Left: Text */}
            <div className="flex-1 text-center md:text-left">
              <h1 className="text-xl sm:text-2xl md:text-3xl lg:text-4xl font-bold text-white">{projectData.title}</h1>
              {/* Feature bullets - More compact on mobile */}
              <ul className="mt-2 sm:mt-3 md:mt-4 text-gray-300 text-xs sm:text-sm md:text-base space-y-0.5 sm:space-y-1 md:space-y-1.5">
                <li>• AI-powered financial analytics with LangGraph memory pipeline and intelligent clarifications</li>
                <li>• Uses advanced intent detection → SQL planning → Chart Generation → financial analysis workflow</li>
                <li className="hidden sm:block">• Real-time streaming with conversational clarifications and session memory management</li>
              </ul>
              {/* Tech tags/pills - More compact on mobile */}
              <div className="mt-2 sm:mt-3 md:mt-4 flex flex-wrap gap-1.5 sm:gap-2 md:gap-2.5 justify-center md:justify-start">
                {projectData.technologies.map((tag) => (
                  <span
                    key={tag}
                    className="px-2 sm:px-3 py-0.5 sm:py-1 md:py-1.5 rounded-full bg-gray-700 text-gray-200 text-[10px] sm:text-xs md:text-sm border border-gray-600 shadow-inner"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            {/* Right: Image - Hidden on mobile */}
            <div className="hidden md:block w-full md:w-1/3 shrink-0 min-w-0">
              <img
                src={projectData.imageUrl}
                alt={projectData.title}
                className="w-full h-40 sm:h-48 object-cover rounded-lg border border-gray-700 shadow max-w-full"
              />
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 overflow-auto p-4 sm:p-6 lg:p-8 pb-32 md:pb-6 bg-gray-900">
          <div className="w-full max-w-5xl mx-auto space-y-4 sm:space-y-6 overflow-hidden">
            
            {/* Chat History Section */}
            <ChatHistory 
              messages={chatHistory} 
              isLoading={isLoading} 
              onSubmitClarification={submitClarification} 
            />

            {/* Chart Display */}
            {chartSpec && isValidChartSpec(chartSpec) && (
              <ChartCard
                chartSpec={chartSpec}
                dataSample={dataSample}
                onError={() => setUseAltChart(true)}
                enableDropdown={true}
                enableCsvDownload={true}
              />
            )}

            {/* Fallback Chart */}
            {!chartSpec && useAltChart && dataSample && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8">
                <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Interactive Visualization (Fallback)</h2>
                <div className="h-64 sm:h-80 md:h-96 bg-gray-900 rounded-lg p-4 sm:p-6 text-gray-300 text-sm sm:text-base">
                  Unable to render chart spec. Showing sample data preview:
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
          {(isLoading || currentStatus !== 'Ready to analyze financial data with intelligent memory...' || error) && (
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
                  {isLoading && (
                    <button
                      onClick={stopAnalysis}
                      className="px-3 py-1.5 text-xs bg-red-600/90 hover:bg-red-600 text-white rounded-lg transition-colors"
                    >
                      Stop
                    </button>
                  )}
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
              </div>
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
            {/* Panel Content */}
            <div className="flex-1 overflow-auto p-4 sm:p-6">
              <div className="space-y-3 sm:space-y-4">
                {processSteps.map((step) => (
                  <div key={step.id} className="flex items-start gap-3">
                    <div className={`w-3 h-3 rounded-full mt-1 flex-shrink-0 ${
                      step.status === 'completed' ? 'bg-green-500' :
                      step.status === 'in_progress' ? 'bg-blue-500 animate-pulse' :
                      step.status === 'error' ? 'bg-red-500' :
                      step.status === 'stopped' ? 'bg-yellow-500' :
                      'bg-gray-500'
                    }`} />
                    <div className="flex-1">
                      <div className="text-sm font-medium text-gray-200">{step.name}</div>
                      {step.thinking.length > 0 && (
                        <div className="text-xs text-gray-400 mt-1">
                          {step.thinking[step.thinking.length - 1]}
                        </div>
                      )}
                      {step.elapsed_ms && (
                        <div className="text-xs text-gray-500">
                          {step.elapsed_ms}ms
                        </div>
                      )}
                    </div>
                  </div>
                ))}
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