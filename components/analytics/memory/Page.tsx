import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  AnalysisCard,
  ProcessPanel
} from '../common';
import { ChatHistory } from './';
import { LiveArtifacts } from './LiveArtifacts';
import { useAnalyticsMemoryStream } from '../hooks';
import type { FlowMode } from '../types';



type FlowOption = FlowMode;

const FLOW_META: Record<FlowOption, { chip: string; chipClass: string; helper: string; placeholder: string }> = {
  'planner-executor': {
    chip: 'Direct Workflow',
    chipClass: 'bg-emerald-600/20 text-emerald-300 border-emerald-500/30',
    helper: 'Deterministic direct workflow with YAML-backed SQL guidance.',
    placeholder: 'Ask about financial data (direct workflow)',
  },
  'single-agent': {
    chip: 'Single Agent + Tools',
    chipClass: 'bg-blue-600/20 text-blue-300 border-blue-500/30',
    helper: 'Claude-style agent calling structured tools with live telemetry.',
    placeholder: 'Ask about financial data (single-agent tools flow)',
  },
  'multi-agent': {
    chip: 'Multi-Agent Orchestration',
    chipClass: 'bg-purple-600/20 text-purple-300 border-purple-500/30',
    helper: 'Lightweight collaboration across planner, analyst, and charting agents.',
    placeholder: 'Ask about financial data (multi-agent orchestration)',
  },
};

const REVISION_META: Record<'chart' | 'analysis' | 'mixed', { label: string; helper: string; className: string }> = {
  chart: {
    label: 'Chart Revision Fast-Path',
    helper: 'Replaying cached data; only chart specification is being adjusted.',
    className: 'bg-amber-600/20 text-amber-200 border-amber-500/30',
  },
  analysis: {
    label: 'Analysis Revision Fast-Path',
    helper: 'Re-using latest data to update narrative only.',
    className: 'bg-pink-600/20 text-pink-200 border-pink-500/30',
  },
  mixed: {
    label: 'Chart + Analysis Revision',
    helper: 'Applying cached chart and narrative tweaks without rerunning SQL.',
    className: 'bg-cyan-600/20 text-cyan-200 border-cyan-500/30',
  },
};

const MemoryAnalyticsPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [showProcessPanel, setShowProcessPanel] = useState(false);
  const [useAltChart, setUseAltChart] = useState(false);
  const [hasStartedChat, setHasStartedChat] = useState(false);
  const [isHeaderCollapsed, setIsHeaderCollapsed] = useState(false);
  const [selectedFlow, setSelectedFlow] = useState<FlowOption>('planner-executor');

  // Reset header to expanded state when component mounts (project navigation)
  useEffect(() => {
    setIsHeaderCollapsed(false);
    setHasStartedChat(false);
  }, []);

  const {
    // State
    chatHistory,
    chartSpec,
    analysis,
    sqlQuery,
    dataSample,
    streamingText,
    webSearch,
    stockWidget,
    progressiveAnalysis,
    progressiveText,
    singleAgentFanout,
    
    // Stream state
    isLoading,
    error,
    currentStatus,
    
    // Process steps
    processSteps,

    // Revision telemetry
    revisionMode,
    
    // Actions
    handleQuery,
    submitClarification,
    stopAnalysis,
  } = useAnalyticsMemoryStream(selectedFlow);

  // Project data for the analytics memory project
  const projectData = {
    title: 'Next Gen Analytics (Memory)',
    description: `**Three Agentic Workflows**: Direct (fast path), Single-Agent (multi-tool use), Multi-Agent (supervisor + specialists).
**Human-in-the-loop**: Compact choice widget for peers/metrics/range; one-tap approvals & reruns.
**Explainable thinking process panel**: plan graph + per-step trace.
**Financial scope (peers)**: AMD, AVGO, INTC, MU, NVDA, QCOM, TXN.
**Memory optimization**: Cached queries, vectorized prompts, result reuse.`,
    technologies: ['Single Agent workflow', 'Multi-agent workflow', 'Human-in-loop', 'RAG', 'long term memory'],
    imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Agent%20demo.gif'
  };

  const handleAnalyticsQuery = async () => {
    if (!query.trim() || isLoading) return;
    const queryToSubmit = query.trim();
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
    'Nvidia market share in the past 5 years?',
    "How's Nvidia margin growth compare to industry average?",
    'How is NVDA R&D expense compare to industry average',
    'How fast is NVDA growing vs industry average?'
  ];

  const processSubtitle =
    revisionMode === 'chart'
      ? 'Revision fast-path · chart adjustments without SQL rerun'
      : revisionMode === 'analysis'
        ? 'Revision fast-path · narrative refinements on cached data'
        : revisionMode === 'mixed'
          ? 'Revision fast-path · chart & narrative tweaks on cached data'
          : 'Real-time agent reasoning & tool execution';

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
            <LiveArtifacts
              chartSpec={chartSpec}
              dataSample={dataSample}
              sqlQuery={sqlQuery}
              analysis={analysis}
              progressiveAnalysis={progressiveAnalysis}
              progressiveText={progressiveText}
              webSearch={webSearch}
              stockWidget={stockWidget}
              isLoading={isLoading}
              flowMode={selectedFlow}
            />

            <ChatHistory 
              messages={chatHistory} 
              isLoading={isLoading} 
              onSubmitClarification={submitClarification}
              processSteps={processSteps}
            />

            {/* Current Analysis Streaming (temporary display) */}
            {streamingText && !analysis && (
              <div className="bg-gray-800/30 rounded-xl border border-gray-700">
                <AnalysisCard analysis={streamingText} />
              </div>
            )}
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
              {/* Flow Selector */}
              <div className="mt-3 sm:mt-4 flex flex-wrap items-center gap-2 sm:gap-3">
                <label className="text-sm font-medium text-gray-300 whitespace-nowrap">Flow:</label>
                <select
                  value={selectedFlow}
                  onChange={(e) => setSelectedFlow(e.target.value as FlowOption)}
                  disabled={isLoading}
                  className="px-3 py-2 text-xs sm:text-sm bg-gray-700/80 border border-emerald-500/30 rounded-lg focus:ring-2 focus:ring-emerald-500/40 focus:border-emerald-500/40 text-gray-100 transition-all duration-200"
                >
                  <option value="planner-executor">Direct Workflow</option>
                  <option value="single-agent">Single Agent + Tools</option>
                  <option value="multi-agent">Multi-Agent Orchestration</option>
                </select>
                <span
                  className={"px-2 py-1 text-xs rounded-full border transition-colors duration-200 " + FLOW_META[selectedFlow].chipClass}
                  title={FLOW_META[selectedFlow].helper}
                >
                  {FLOW_META[selectedFlow].chip}
                </span>
                <span className="text-xs text-gray-400 hidden lg:block">
                  {FLOW_META[selectedFlow].helper}
                </span>
                {revisionMode !== 'none' && (
                  <span
                    className={`px-2 py-1 text-xs rounded-full border transition-colors duration-200 ${REVISION_META[revisionMode].className}`}
                    title={REVISION_META[revisionMode].helper}
                  >
                    {REVISION_META[revisionMode].label}
                  </span>
                )}
              </div>
              
              {/* Input row */}
              <div className="mt-3 sm:mt-4 flex items-center gap-2 sm:gap-3 w-full">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={FLOW_META[selectedFlow].placeholder}
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

      {/* Process Panel */}
      <ProcessPanel
        steps={processSteps}
        flowMode={selectedFlow}
        singleAgentFanout={singleAgentFanout}
        show={showProcessPanel}
        showVisualization={true}
        onClose={() => setShowProcessPanel(false)}
        title="Agent Thinking Process"
        subtitle={processSubtitle}
      />

    </div>
  );
};

export default MemoryAnalyticsPage;



