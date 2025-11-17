import React, { useState, useEffect, useMemo, useRef } from 'react';
import { motion } from 'framer-motion';
import { AnalysisCard } from '../common';
import { ProcessPanel } from '../common/ProcessPanel';
import { ChatHistory } from './';
import { useAnalyticsMemoryStream } from '../hooks';
import type { FlowMode } from '../types';
import { deriveRevisionContext, buildPromptCandidates } from './revisionPrompts';
import type { PromptCandidate } from './revisionPrompts';


type FlowOption = FlowMode;

const FLOW_META: Record<FlowOption, { chip: string; chipClass: string; helper: string; placeholder: string }> = {
  'planner-executor': {
    chip: 'Direct fixed workflow with RAG-backed SQL guidance',
    chipClass: 'bg-emerald-600/20 text-emerald-300 border-emerald-500/30',
    helper: 'Direct fixed workflow with RAG-backed SQL guidance.',
    placeholder: 'Ask about financial data (direct workflow)',
  },
  'single-agent': {
    chip: 'Claude-Code style single agent with multiple tool calling capability',
    chipClass: 'bg-blue-600/20 text-blue-300 border-blue-500/30',
    helper: 'Claude-Code style single LLM agent with multiple tool calling capability.',
    placeholder: 'Ask about financial data (single-agent tools flow)',
  },
  'multi-agent': {
    chip: 'Single Supervisor agent collaboration across multiple specialist agents',
    chipClass: 'bg-purple-600/20 text-purple-300 border-purple-500/30',
    helper: 'Supervisor agent collaboration across multiple specialists',
    placeholder: 'Ask about financial data (multi-agent orchestration)',
  },
};

const REVISION_META: Record<'chart' | 'analysis' | 'market' | 'mixed', { label: string; helper: string; className: string }> = {
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
  market: {
    label: 'Market Revision Fast-Path',
    helper: 'Refreshing market research cards without triggering SQL or chart regeneration.',
    className: 'bg-sky-600/20 text-sky-200 border-sky-500/30',
  },
  mixed: {
    label: 'Chart + Analysis Revision',
    helper: 'Applying cached chart and narrative tweaks without rerunning SQL.',
    className: 'bg-cyan-600/20 text-cyan-200 border-cyan-500/30',
  },
};

const formatLaneTitle = (raw?: string) => {
  if (!raw) return 'Lane';
  return raw
    .split(/[_-]/g)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
};

const formatAgeSeconds = (value?: number) => {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return undefined;
  }
  if (value >= 3600) {
    const hours = Math.floor(value / 3600);
    const minutes = Math.round((value % 3600) / 60);
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
  if (value >= 90) {
    const minutes = Math.floor(value / 60);
    const seconds = Math.round(value % 60);
    return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
  }
  if (value >= 60) {
    return `${(value / 60).toFixed(1)}m`;
  }
  if (value >= 1) {
    return `${Math.round(value)}s`;
  }
  return '<1s';
};

const MemoryAnalyticsPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [showProcessPanel, setShowProcessPanel] = useState(false);
  const [useAltChart, setUseAltChart] = useState(false);
  const [hasStartedChat, setHasStartedChat] = useState(false);
  const [isHeaderCollapsed, setIsHeaderCollapsed] = useState(false);
  const [selectedFlow, setSelectedFlow] = useState<FlowOption>('planner-executor');
  const [promptRotationKey, setPromptRotationKey] = useState(0);

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
    analysisOverview,
    analysisSources,
    sqlQuery,
    dataSample,
    streamingText,
    webSearch,
    stockWidget,
    progressiveAnalysis,
    progressiveText,
    singleAgentFanout,
    followUpBanner,
    slotStatuses,
    slotFollowups,
    snapshotReuse,
    laneReuseNotices,
    agenticRevisionActive,
    freshLaneStates,
    specialistCards,
    latencyGuardrail,
    redirectNotice,
    flowMode: activeFlowMode,
    
    // Stream state
    isLoading,
    currentStatus,
    statusTimestamp,
    
    // Process steps
    processSteps,

    // Revision telemetry
    revisionMode,
    
    // Actions
    handleQuery,
    submitClarification,
    stopAnalysis,
    clearRedirectNotice,
  } = useAnalyticsMemoryStream(selectedFlow);
  const revisionContext = useMemo(
    () =>
      deriveRevisionContext({
        chatHistory,
        chartSpec,
        analysis,
        analysisOverview,
        analysisSources,
        stockWidget,
        webSearch,
        sqlQuery,
        dataSample,
      }),
    [
      chatHistory,
      chartSpec,
      analysis,
      analysisOverview,
      analysisSources,
      stockWidget,
      webSearch,
      sqlQuery,
      dataSample,
    ],
  );

  const revisionCandidates = useMemo<PromptCandidate[]>(
    () => buildPromptCandidates(revisionContext, { rotationKey: promptRotationKey }),
    [revisionContext, promptRotationKey],
  );

  const hasResultMessage = useMemo(
    () => (chatHistory ?? []).some((message) => message?.type === 'result'),
    [chatHistory],
  );

  const isShowingRevisionPrompts = hasResultMessage && revisionCandidates.length > 0;

  useEffect(() => {
    if (!hasResultMessage) {
      setPromptRotationKey(0);
    }
  }, [hasResultMessage]);

  const previousRevisionModeRef = useRef(revisionMode);
  useEffect(() => {
    const previous = previousRevisionModeRef.current;
    if (previous !== 'none' && revisionMode === 'none' && !isLoading) {
      setPromptRotationKey((value) => value + 1);
    }
    previousRevisionModeRef.current = revisionMode;
  }, [revisionMode, isLoading]);

  useEffect(() => {
    if (hasStartedChat) {
      return;
    }
    const historyHasMessages = (chatHistory?.length ?? 0) > 0;
    const hasStreamingText = typeof streamingText === 'string' && streamingText.trim().length > 0;
    const hasProgressiveText = typeof progressiveText === 'string' && progressiveText.trim().length > 0;
    if (historyHasMessages || hasStreamingText || hasProgressiveText) {
      setHasStartedChat(true);
    }
  }, [chatHistory, streamingText, progressiveText, hasStartedChat]);

  const flowSelectionLocked = hasStartedChat;

  // Project data for the analytics memory project
  const projectData = {
    title: 'Next Gen Analytics (Agents)',
    description: `**Future of Analytics: agent workflow demo**
Direct Workflow: no flexibility on tools, run through all tools all at once
Single Agent: ability to pick tools, revise single/multiple analytic element
Multi-Agent: workload delegation & orchestration, fastest speed
**Human-in-the-loop**: Compact widget for clarification on peers/metrics/range
**Explainable thinking process diagram**: thinking graph + per-step trace.
**Available financials**: AMD, AVGO, INTC, MU, NVDA, QCOM, TXN.
**Memory optimization**: RAG optimized, Cached queries, vectorized prompts, stateful nodes`,
    technologies: ['Single Agent Workflow', 'Multi-Agent Workflow', 'Human-in-the-Loop', 'RAG', 'Long-Term Memory'],
    imageUrl: 'https://yanqing.app/next-gen-analytics-agent-hero.gif'
  };

  const snapshotReuseChips = useMemo(() => {
    if (!snapshotReuse) return [] as string[];
    const chips: string[] = [];
    if (snapshotReuse.reusedSql) chips.push('SQL');
    if (snapshotReuse.reusedChart) chips.push('Chart');
    if (snapshotReuse.reusedAnalysis) chips.push('Analysis');
    if (snapshotReuse.reusedWeb) chips.push('Web');
    if (snapshotReuse.reusedStock) chips.push('Market');
    return chips;
  }, [snapshotReuse]);

  const snapshotReuseBadge = useMemo(() => {
    if (!snapshotReuse) return null;
    if (snapshotReuse.criteriaChanged) {
      return {
        text: 'Criteria changed - running full pipeline',
        className: 'bg-amber-600/20 text-amber-100 border-amber-500/40',
      };
    }
    if (snapshotReuseChips.length === 0) {
      return null;
    }
    const detail = snapshotReuseChips.join(', ');
    return {
      text: `Reusing cached ${detail}`,
      className: 'bg-emerald-600/15 text-emerald-200 border-emerald-500/30',
    };
  }, [snapshotReuse, snapshotReuseChips]);

  const analysisRefreshBadge = useMemo(() => {
    if (followUpBanner?.refreshMode !== 'light') {
      return null;
    }
    return {
      text: 'Quick narrative refresh',
      className: 'bg-emerald-600/20 text-emerald-200 border-emerald-500/30',
    };
  }, [followUpBanner?.refreshMode]);

  const showLaneReuseUi = false;
  const laneReuseBadges = useMemo(() => {
    if (!showLaneReuseUi || !laneReuseNotices || laneReuseNotices.length === 0) {
      return [] as Array<{ key: string; text: string; title?: string }>;
    }
    return laneReuseNotices.map((notice) => {
      const ageLabel = formatAgeSeconds(notice.ageSeconds);
      const text =
        ageLabel && ageLabel !== '<1s'
          ? `${formatLaneTitle(notice.lane)} reused · cache ${ageLabel}`
          : `${formatLaneTitle(notice.lane)} reused`;
      return {
        key: `${notice.lane}-${notice.ts ?? notice.message}`,
        text,
        title: notice.message ?? notice.reason ?? text,
      };
    });
  }, [showLaneReuseUi, laneReuseNotices]);

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

  const discoveryPrompts = [
    'AMD vs NVIDIA revenue comparison in the past 5 years?',
    "How's Nvidia margin growth compare to industry average?",
    'How is NVDA R&D expense compare to industry average',
    'How fast is NVDA growing vs industry average?'
  ];

  const displayedPrompts: Array<string | PromptCandidate> = isShowingRevisionPrompts
    ? revisionCandidates
    : discoveryPrompts;

  const processSubtitle =
    revisionMode === 'chart'
      ? 'Revision fast-path Â· chart adjustments without SQL rerun'
      : revisionMode === 'analysis'
        ? 'Revision fast-path Â· narrative refinements on cached data'
        : revisionMode === 'market'
          ? 'Revision fast-path A� market snapshots without SQL rerun'
          : revisionMode === 'mixed'
          ? 'Revision fast-path Â· chart & narrative tweaks on cached data'
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
                      if (!trimmed) return null;

                      // Bold header/labels pattern (e.g., **Human-in-the-loop**: ...)
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

                      // Flow label highlight + chip effect for three lines
                      const colonIdx = trimmed.indexOf(':');
                      const label = colonIdx >= 0 ? trimmed.slice(0, colonIdx).trim() : undefined;
                      const restText = colonIdx >= 0 ? trimmed.slice(colonIdx + 1).trim() : '';
                      const FLOW_LABEL_TO_OPTION: Record<string, FlowOption> = {
                        'Direct Workflow': 'planner-executor',
                        'Single Agent': 'single-agent',
                        'Multi-Agent': 'multi-agent',
                      };
                      const flowKey = label ? FLOW_LABEL_TO_OPTION[label] : undefined;
                      if (flowKey) {
                        const chipClass = FLOW_META[flowKey].chipClass;
                        return (
                          <p key={idx} className="leading-relaxed flex items-center gap-2">
                            <span
                              role="button"
                              onClick={() => { if (!isLoading && !flowSelectionLocked) setSelectedFlow(flowKey); }}
                              title={
                                flowSelectionLocked
                                  ? 'Flow selection locked for this chat. Refresh to choose a different workflow.'
                                  : `Switch flow to ${FLOW_META[flowKey].chip}`
                              }
                              aria-disabled={flowSelectionLocked || isLoading}
                              className={`px-2 py-0.5 text-[10px] sm:text-xs rounded-full border transition-colors duration-200 ${
                                isLoading || flowSelectionLocked
                                  ? 'opacity-60 cursor-not-allowed'
                                  : 'cursor-pointer hover:opacity-90'
                              } ${chipClass}`}
                            >
                              {label}
                            </span>
                            {restText && (
                              <span className="text-gray-400">: {restText}</span>
                            )}
                          </p>
                        );
                      }

                      // Fallback: plain line
                      return (
                        <p key={idx} className="leading-relaxed">{trimmed}</p>
                      );
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
            <ChatHistory 
              messages={chatHistory} 
              isLoading={isLoading} 
              status={{ text: currentStatus, timestamp: statusTimestamp }}
              onSubmitClarification={submitClarification}
              processSteps={processSteps}
            />
          </div>
        </div>

        {/* Bottom Chat/Input Bar (fixed position on mobile, sticky on desktop) */}
        <div className="fixed md:sticky bottom-0 left-0 right-0 md:left-auto md:right-auto bg-gray-800/95 backdrop-blur-sm border-t border-gray-700 z-30">
          {/* Input Section */}
          <div className="px-4 sm:px-6 md:px-8 py-3 sm:py-4">
            <div className="w-full max-w-5xl mx-auto">
              {/* Suggested queries (only show when not loading) */}
              {!isLoading && (
                <div className="flex gap-2 sm:gap-2.5 overflow-x-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800 py-1 sm:py-2 -mx-2 sm:-mx-1 px-2 sm:px-1 max-w-full">
                  {displayedPrompts.map((prompt, idx) => {
                    const copy = typeof prompt === 'string' ? prompt : prompt.copy;
                    const key =
                      typeof prompt === 'string'
                        ? `discovery-${idx}`
                        : `${prompt.intent}-${prompt.lane}-${idx}`;
                    return (
                      <button
                        key={key}
                        onClick={() => setQuery(copy)}
                        className="px-2 sm:px-3 md:px-4 py-1 sm:py-1.5 md:py-2 text-[10px] sm:text-xs md:text-sm bg-gradient-to-r from-gray-700 to-gray-600 hover:from-gray-600 hover:to-gray-500 rounded-full text-gray-100 transition-colors border border-gray-600/60 whitespace-nowrap shadow-sm min-h-[28px] sm:min-h-[32px] md:min-h-[36px] flex items-center"
                      >
                        {copy}
                      </button>
                    );
                  })}
                </div>
              )}
              {/* Flow Selector */}
              <div className="mt-3 sm:mt-4 flex flex-wrap items-center gap-2 sm:gap-3">
                <label className="text-sm font-medium text-gray-300 whitespace-nowrap">Flow:</label>
                <select
                  value={selectedFlow}
                  onChange={(e) => setSelectedFlow(e.target.value as FlowOption)}
                  disabled={isLoading || flowSelectionLocked}
                  className="px-3 py-2 text-xs sm:text-sm bg-gray-700/80 border border-emerald-500/30 rounded-lg focus:ring-2 focus:ring-emerald-500/40 focus:border-emerald-500/40 text-gray-100 transition-all duration-200 disabled:cursor-not-allowed disabled:bg-gray-700/50 disabled:border-gray-600/40 disabled:text-gray-500 disabled:opacity-70"
                  title={
                    flowSelectionLocked
                      ? 'Flow selection locked for this chat. Refresh to choose a different workflow.'
                      : 'Select an analytics workflow before starting a chat.'
                  }
                >
                  <option value="planner-executor">Direct Workflow</option>
                  <option value="single-agent">Single Agent</option>
                  <option value="multi-agent">Multi-Agent</option>
                </select>
                <span
                  className={"px-2 py-1 text-xs rounded-full border transition-colors duration-200 " + FLOW_META[selectedFlow].chipClass}
                  title={FLOW_META[selectedFlow].helper}
                >
                  {FLOW_META[selectedFlow].chip}
                </span>
                {/* Removed grey helper text to avoid duplicating the colored chip */}
                {revisionMode !== 'none' && (
                  <span
                    className={`px-2 py-1 text-xs rounded-full border transition-colors duration-200 ${REVISION_META[revisionMode].className}`}
                    title={REVISION_META[revisionMode].helper}
                  >
                    {REVISION_META[revisionMode].label}
                  </span>
                )}
                {snapshotReuseBadge && (
                  <span
                    className={`px-2 py-1 text-xs rounded-full border transition-colors duration-200 ${snapshotReuseBadge.className}`}
                    title={snapshotReuse?.followUpRoute ? `Route: ${snapshotReuse.followUpRoute}` : 'Snapshot reuse active'}
                  >
                    {snapshotReuseBadge.text}
                  </span>
                )}
                {analysisRefreshBadge && (
                  <span
                    className={`px-2 py-1 text-xs rounded-full border transition-colors duration-200 ${analysisRefreshBadge.className}`}
                    title="Cached SQL and web context reused for this revision"
                  >
                    {analysisRefreshBadge.text}
                  </span>
                )}
                {laneReuseBadges.map((badge) => (
                  <span
                    key={badge.key}
                    title={badge.title}
                    className="px-2 py-1 text-xs rounded-full border border-sky-500/40 bg-sky-600/20 text-sky-100 transition-colors duration-200"
                  >
                    {badge.text}
                  </span>
                ))}
              </div>

              {redirectNotice && (
                <div className="mt-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-amber-100 shadow-inner">
                  <div className="flex items-start justify-between gap-3">
                    <div className="text-sm font-medium leading-snug">{redirectNotice}</div>
                    <button
                      type="button"
                      onClick={clearRedirectNotice}
                      className="rounded-md border border-amber-400/40 px-3 py-1 text-xs uppercase tracking-wide text-amber-100 transition hover:border-amber-300 hover:text-white"
                    >
                      Dismiss
                    </button>
                  </div>
                  <div className="mt-1 text-xs text-amber-200/80">
                    Start a fresh analysis run or rerun the previous query to continue.
                  </div>
                </div>
              )}
              
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
        flowMode={activeFlowMode}
        singleAgentFanout={singleAgentFanout}
        followUpBanner={followUpBanner}
        slotStatuses={slotStatuses}
        slotFollowups={slotFollowups}
        laneReuseNotices={showLaneReuseUi ? laneReuseNotices : null}
        agenticRevision={agenticRevisionActive}
        freshLaneStates={freshLaneStates}
        redirectNotice={redirectNotice}
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








