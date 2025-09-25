import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Draggable from 'react-draggable';
import { ProcessStep } from '../types';
import { WorkflowCanvas } from '../visualization/WorkflowCanvas';

interface ProcessPanelProps {
  steps: ProcessStep[];
  show: boolean;
  onClose: () => void;
  title?: string;
  subtitle?: string;
  viewMode?: 'canvas' | 'list';
  draggable?: boolean;
  resizable?: boolean;
  defaultWidth?: number;
  minWidth?: number;
  maxWidth?: number;
}

interface PanelState {
  width: number;
  isMaximized: boolean;
  isMinimized: boolean;
  isDragging: boolean;
  position: { x: number; y: number };
}

export const ProcessPanel: React.FC<ProcessPanelProps> = ({
  steps,
  show,
  onClose,
  title = "Agent Thinking Process",
  subtitle = "Real-time agent reasoning & tool execution",
  viewMode = 'canvas',
  draggable = true,
  resizable = true,
  defaultWidth = 384, // md:w-96 equivalent
  minWidth = 300,
  maxWidth = 1200
}) => {
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const [breakdownSteps, setBreakdownSteps] = useState<Set<string>>(new Set());
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [currentViewMode, setCurrentViewMode] = useState<'canvas' | 'list'>(viewMode);
  const [panelState, setPanelState] = useState<PanelState>(() => {
    // Load from localStorage or use defaults
    const saved = typeof window !== 'undefined' ? localStorage.getItem('processPanelState') : null;
    const defaultState: PanelState = {
      width: defaultWidth,
      isMaximized: false,
      isMinimized: false,
      isDragging: false,
      position: { x: 0, y: 0 }
    };
    return saved ? { ...defaultState, ...JSON.parse(saved) } : defaultState;
  });

  const panelRef = useRef<HTMLDivElement>(null);
  const nodeRef = useRef(null);

  // Save panel state to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('processPanelState', JSON.stringify(panelState));
    }
  }, [panelState]);

  // Panel control functions
  const toggleMaximize = () => {
    setPanelState(prev => ({
      ...prev,
      isMaximized: !prev.isMaximized,
      width: !prev.isMaximized ? window.innerWidth * 0.8 : defaultWidth
    }));
  };

  const toggleMinimize = () => {
    setPanelState(prev => ({ ...prev, isMinimized: !prev.isMinimized }));
  };

  const handleDragStart = () => {
    setPanelState(prev => ({ ...prev, isDragging: true }));
  };

  const handleDragStop = (e: any, data: any) => {
    setPanelState(prev => ({
      ...prev,
      isDragging: false,
      position: { x: data.x, y: data.y }
    }));
  };

  const handleResize = (newWidth: number) => {
    const clampedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
    setPanelState(prev => ({ ...prev, width: clampedWidth }));
  };

  const toggleStep = (stepId: string) => {
    setExpandedSteps(prev => {
      const newSet = new Set(prev);
      if (newSet.has(stepId)) {
        newSet.delete(stepId);
      } else {
        newSet.add(stepId);
      }
      return newSet;
    });
  };

  const toggleBreakdown = (stepId: string) => {
    setBreakdownSteps(prev => {
      const newSet = new Set(prev);
      if (newSet.has(stepId)) {
        newSet.delete(stepId);
      } else {
        newSet.add(stepId);
      }
      return newSet;
    });
  };

  const generateSubSteps = (step: ProcessStep) => {
    const subSteps = [];
    const details = step.details ?? {};

    // Generate sub-steps based on step content
    if (step.thinking && step.thinking.length > 0) {
      subSteps.push({
        name: 'Decision Analysis',
        status: 'completed' as const,
        confidence: details.confidence || 0.8,
        description: 'Analyzing available options and constraints'
      });
    }

    if (details.plan) {
      subSteps.push({
        name: 'Plan Generation',
        status: 'completed' as const,
        confidence: 0.9,
        description: 'Creating execution strategy'
      });
    }

    if (details.sql || details.sql_executed) {
      subSteps.push({
        name: 'SQL Compilation',
        status: 'completed' as const,
        confidence: 0.95,
        description: 'Generating database query'
      });
    }

    if (details.result || details.sample_data) {
      subSteps.push({
        name: 'Data Processing',
        status: 'completed' as const,
        confidence: 0.85,
        description: 'Processing query results'
      });
    }

    if (details.chart_spec) {
      subSteps.push({
        name: 'Visualization Spec',
        status: 'completed' as const,
        confidence: 0.88,
        description: 'Creating chart specification'
      });
    }

    // Add a pending or in-progress sub-step if the main step is active
    if (step.status === 'in_progress') {
      subSteps.push({
        name: 'Execution',
        status: 'in_progress' as const,
        confidence: 0.7,
        description: 'Currently processing...'
      });
    }

    return subSteps;
  };

  const renderDetailedContent = (step: ProcessStep) => {
    const details = step.details ?? {};
    const sections: React.ReactNode[] = [];

    if (step.thinking && step.thinking.length > 0) {
      sections.push(
        <div key="thinking" className="mt-3">
          <h4 className="text-xs font-medium text-blue-300 mb-2">Decision Log</h4>
          <ul className="space-y-1 text-xs text-gray-300">
            {step.thinking.slice(-6).map((entry, idx) => (
              <li key={`${step.id}-thought-${idx}`} className="flex items-start gap-2">
                <span className="mt-0.5 text-blue-400">-</span>
                <span className="flex-1 break-words">{entry}</span>
              </li>
            ))}
          </ul>
        </div>
      );
    }

    if (details.plan) {
      sections.push(
        <div key="plan" className="mt-3">
          <h4 className="text-xs font-medium text-purple-300 mb-2">Plan Summary</h4>
          <pre className="text-xs bg-gray-900 p-3 rounded border border-gray-600 overflow-x-auto max-h-40">
            <code className="text-purple-200">{JSON.stringify(details.plan, null, 2)}</code>
          </pre>
        </div>
      );
    }

    if (details.result) {
      sections.push(
        <div key="result" className="mt-3">
          <h4 className="text-xs font-medium text-emerald-300 mb-2">Result</h4>
          <pre className="text-xs bg-gray-900 p-3 rounded border border-gray-600 overflow-x-auto max-h-40">
            <code className="text-emerald-200">{typeof details.result === 'string' ? details.result : JSON.stringify(details.result, null, 2)}</code>
          </pre>
        </div>
      );
    }

    if (details.chart_spec) {
      sections.push(
        <div key="chart" className="mt-3">
          <h4 className="text-xs font-medium text-blue-200 mb-2">Chart Spec</h4>
          <pre className="text-xs bg-gray-900 p-3 rounded border border-gray-600 overflow-x-auto max-h-40">
            <code className="text-blue-200">{JSON.stringify(details.chart_spec, null, 2)}</code>
          </pre>
        </div>
      );
    }

    if (details.key_findings && Array.isArray(details.key_findings)) {
      sections.push(
        <div key="findings" className="mt-3">
          <h4 className="text-xs font-medium text-amber-300 mb-2">Key Findings</h4>
          <ul className="list-disc pl-4 text-xs text-amber-200 space-y-1">
            {details.key_findings.map((finding: string, idx: number) => (
              <li key={`${step.id}-finding-${idx}`}>{finding}</li>
            ))}
          </ul>
        </div>
      );
    }

    if (details.sql || details.sql_executed) {
      sections.push(
        <div key="sql" className="mt-3">
          <h4 className="text-xs font-medium text-blue-300 mb-2">SQL Query</h4>
          <pre className="text-xs bg-gray-900 p-3 rounded border border-gray-600 overflow-x-auto">
            <code className="text-green-300">{details.sql || details.sql_executed}</code>
          </pre>
        </div>
      );
    }

    if (details.template || details.template_used) {
      sections.push(
        <div key="template" className="mt-3">
          <h4 className="text-xs font-medium text-purple-300 mb-2">Template Used</h4>
          <div className="text-xs bg-gray-900 p-3 rounded border border-gray-600">
            <code className="text-purple-200">{details.template || details.template_used}</code>
          </div>
        </div>
      );
    }

    if (details.sample_data || details.sampleData) {
      const sampleData = details.sample_data || details.sampleData;
      sections.push(
        <div key="data" className="mt-3">
          <h4 className="text-xs font-medium text-yellow-300 mb-2">
            Data Sample ({details.row_count || details.rowCount || sampleData?.length || 0} rows)
          </h4>
          <pre className="text-xs bg-gray-900 p-3 rounded border border-gray-600 overflow-x-auto max-h-32">
            <code className="text-yellow-200">{JSON.stringify(sampleData, null, 2)}</code>
          </pre>
        </div>
      );
    }

    if (details.args || details.args_summary || details.args_preview) {
      sections.push(
        <div key="args" className="mt-3">
          <h4 className="text-xs font-medium text-cyan-300 mb-2">Tool Arguments</h4>
          <pre className="text-xs bg-gray-900 p-3 rounded border border-gray-600 overflow-x-auto">
            <code className="text-cyan-200">
              {details.args_summary || details.args_preview || JSON.stringify(details.args, null, 2)}
            </code>
          </pre>
        </div>
      );
    }

    if (details.reasoning || details.strategy) {
      sections.push(
        <div key="reasoning" className="mt-3">
          <h4 className="text-xs font-medium text-indigo-300 mb-2">Reasoning</h4>
          <div className="text-xs bg-gray-900 p-3 rounded border border-gray-600">
            <p className="text-indigo-200">{details.reasoning || details.strategy}</p>
          </div>
        </div>
      );
    }

    if (details.error) {
      sections.push(
        <div key="error" className="mt-3">
          <h4 className="text-xs font-medium text-red-300 mb-2">Error</h4>
          <div className="text-xs bg-red-900/20 p-3 rounded border border-red-600">
            <code className="text-red-200">{details.error}</code>
          </div>
        </div>
      );
    }

    if (details.tool || details.confidence || details.category || details.duration_ms || details.sql_length || details.intent_key) {
      sections.push(
        <div key="metadata" className="mt-3">
          <h4 className="text-xs font-medium text-gray-300 mb-2">Metadata</h4>
          <div className="text-xs space-y-1">
            {details.tool && <div className="text-gray-400">Tool: <span className="text-gray-200">{details.tool}</span></div>}
            {details.intent_key && <div className="text-gray-400">Intent: <span className="text-gray-200">{details.intent_key}</span></div>}
            {details.confidence && <div className="text-gray-400">Confidence: <span className="text-gray-200">{(details.confidence * 100).toFixed(1)}%</span></div>}
            {details.category && <div className="text-gray-400">Category: <span className="text-gray-200">{details.category}</span></div>}
            {details.duration_ms && <div className="text-gray-400">Duration: <span className="text-gray-200">{details.duration_ms}ms</span></div>}
            {details.sql_length && <div className="text-gray-400">SQL Length: <span className="text-gray-200">{details.sql_length} chars</span></div>}
          </div>
        </div>
      );
    }

    return sections.length > 0 ? <div>{sections}</div> : null;
  };

  const panelWidth = panelState.isMaximized ? window.innerWidth * 0.8 : panelState.width;
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  const isCanvasVisible = show && !panelState.isMinimized && currentViewMode === 'canvas';

  return (
    <AnimatePresence>
      {show && (
        <>
          {/* Mobile Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden"
            onClick={onClose}
          />

          {/* Panel Container - Draggable on desktop, fixed on mobile */}
          {draggable && !isMobile ? (
            <Draggable
              nodeRef={nodeRef}
              handle=".drag-handle"
              position={panelState.position}
              onStart={handleDragStart}
              onStop={handleDragStop}
              bounds="parent"
            >
              <motion.div
                ref={nodeRef}
                initial={{ x: '100%' }}
                animate={{ x: 0 }}
                exit={{ x: '100%' }}
                transition={{ type: "spring", damping: 25, stiffness: 200 }}
                className={`fixed bg-gray-800 border border-gray-700 shadow-2xl z-50 flex flex-col rounded-lg overflow-hidden ${
                  panelState.isMinimized ? 'h-12' : 'h-auto max-h-[90vh]'
                }`}
                style={{
                  width: panelWidth,
                  right: 0,
                  top: '5%',
                  maxWidth: '80vw'
                }}
              >
                {/* Panel content will go here */}
                {renderPanelContent()}
              </motion.div>
            </Draggable>
          ) : (
            /* Non-draggable panel (mobile or disabled) */
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="fixed inset-y-0 right-0 w-full md:max-w-none bg-gray-800 md:border-l border-gray-700 shadow-2xl z-50 flex flex-col"
              style={{ width: isMobile ? '100%' : panelWidth }}
            >
              {/* Panel content will go here */}
              {renderPanelContent()}
            </motion.div>
          )}
        </>
      )}
    </AnimatePresence>
  );

  function renderPanelContent() {
    return (
      <>
        {/* Resize Handle (left side) */}
        {resizable && !isMobile && (
          <div
            className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize bg-gray-600 hover:bg-blue-500 transition-colors"
            onMouseDown={(e) => {
              e.preventDefault();
              const startX = e.clientX;
              const startWidth = panelState.width;

              const handleMouseMove = (e: MouseEvent) => {
                const newWidth = startWidth - (e.clientX - startX);
                handleResize(newWidth);
              };

              const handleMouseUp = () => {
                document.removeEventListener('mousemove', handleMouseMove);
                document.removeEventListener('mouseup', handleMouseUp);
              };

              document.addEventListener('mousemove', handleMouseMove);
              document.addEventListener('mouseup', handleMouseUp);
            }}
          />
        )}

        {/* Panel Header - Enhanced with controls */}
        <div className={`drag-handle p-4 sm:p-6 border-b border-gray-700 ${draggable && !isMobile ? 'cursor-move' : ''}`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex-1">
              <h2 className="text-lg sm:text-xl font-semibold text-white">{title}</h2>
              {!panelState.isMinimized && <p className="text-sm text-gray-400">{subtitle}</p>}
            </div>

            {/* Control Buttons */}
            <div className="flex items-center gap-2">
              {!isMobile && (
                <>
                  <button
                    onClick={toggleMinimize}
                    className="p-1.5 hover:bg-gray-700 rounded transition-colors"
                    title={panelState.isMinimized ? 'Expand' : 'Minimize'}
                  >
                    <span className="w-4 h-4 text-gray-400 block">
                      {panelState.isMinimized ? '[ ]' : '_'}
                    </span>
                  </button>

                  <button
                    onClick={toggleMaximize}
                    className="p-1.5 hover:bg-gray-700 rounded transition-colors"
                    title={panelState.isMaximized ? 'Restore' : 'Maximize'}
                  >
                    <span className="w-4 h-4 text-gray-400 block">
                      {panelState.isMaximized ? '[R]' : '[ ]'}
                    </span>
                  </button>
                </>
              )}

              <button
                onClick={onClose}
                className="p-1.5 hover:bg-gray-700 rounded transition-colors"
              >
                <span className="w-4 h-4 text-gray-400 block">X</span>
              </button>
            </div>
          </div>

          {/* View Mode Toggle - only show when not minimized */}
          {!panelState.isMinimized && (
            <div className="space-y-3">
              {/* View Toggle */}
              <div className="flex bg-gray-700 rounded-lg p-1">
                <button
                  onClick={() => setCurrentViewMode('canvas')}
                  className={`flex-1 px-3 py-2 text-sm rounded-md transition-colors ${
                    currentViewMode === 'canvas'
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-300 hover:text-white'
                  }`}
                >
                  Flow View
                </button>
                <button
                  onClick={() => setCurrentViewMode('list')}
                  className={`flex-1 px-3 py-2 text-sm rounded-md transition-colors ${
                    currentViewMode === 'list'
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-300 hover:text-white'
                  }`}
                >
                  List View
                </button>
              </div>

              {/* Mission Control Bar */}
              <div className="flex items-center justify-between p-3 bg-gradient-to-r from-gray-800/80 to-gray-700/80 rounded-lg backdrop-blur-sm border border-gray-600/30">
                {/* Current Phase Indicator */}
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></div>
                  <span className="text-xs font-medium text-blue-300">
                    {steps.find(s => s.status === 'in_progress')?.name || 'Completed'}
                  </span>
                </div>

                {/* Control Buttons */}
                <div className="flex items-center gap-2">
                  {/* Playback Speed */}
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-gray-400">Speed:</span>
                    <select
                      value={playbackSpeed}
                      onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
                      className="text-xs bg-gray-700 text-gray-200 rounded px-2 py-1 border border-gray-600 focus:border-blue-500"
                    >
                      <option value={0.5}>0.5x</option>
                      <option value={1}>1x</option>
                      <option value={2}>2x</option>
                      <option value={3}>3x</option>
                    </select>
                  </div>

                  {/* Playback Controls */}
                  <motion.button
                    onClick={() => setIsPaused(!isPaused)}
                    className="p-2 hover:bg-gray-600 rounded-md transition-colors"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    title={isPaused ? "Resume" : "Pause"}
                  >
                    {isPaused ? (
                      <svg className="w-4 h-4 text-green-400" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z"/>
                      </svg>
                    ) : (
                      <svg className="w-4 h-4 text-yellow-400" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                      </svg>
                    )}
                  </motion.button>

                  {/* Step Controls */}
                  <motion.button
                    className="p-2 hover:bg-gray-600 rounded-md transition-colors"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    title="Previous Step"
                  >
                    <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0019 16V8a1 1 0 00-1.6-.8L12.066 11.2zM4.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0011 16V8a1 1 0 00-1.6-.8L4.066 11.2z" />
                    </svg>
                  </motion.button>

                  <motion.button
                    className="p-2 hover:bg-gray-600 rounded-md transition-colors"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    title="Next Step"
                  >
                    <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.933 12.8a1 1 0 000-1.6L6.6 7.2A1 1 0 005 8v8a1 1 0 001.6.8L11.933 12.8zM19.933 12.8a1 1 0 000-1.6l-5.333-4A1 1 0 0013 8v8a1 1 0 001.6.8L19.933 12.8z" />
                    </svg>
                  </motion.button>
                </div>

                {/* Progress Indicator */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">
                    {steps.filter(s => s.status === 'completed').length}/{steps.length}
                  </span>
                  <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-blue-400 to-emerald-400 rounded-full"
                      initial={{ width: 0 }}
                      animate={{
                        width: `${(steps.filter(s => s.status === 'completed').length / steps.length) * 100}%`
                      }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Panel Content - only show when not minimized */}
        {!panelState.isMinimized && (
          <div className="flex-1 overflow-auto">
            {currentViewMode === 'canvas' ? (
              <div className="h-full min-h-[600px]">
                <WorkflowCanvas steps={steps} isVisible={isCanvasVisible} />
              </div>
            ) : (
              <div className="p-4 sm:p-6">
                <div className="space-y-3 sm:space-y-4">
                  {steps.map((step, index) => {
                    const isExpanded = expandedSteps.has(step.id);
                    const isBreakdownExpanded = breakdownSteps.has(step.id);
                    const hasDetails = (
                    step.details && Object.keys(step.details).some(
                      key => step.details![key as keyof typeof step.details] != null
                    )
                  ) || (step.thinking && step.thinking.length > 0);
                    const subSteps = generateSubSteps(step);
                    const hasBreakdown = subSteps.length > 0;

                    return (
                    <motion.div
                      key={step.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: index * 0.1 }}
                      className={`
                        relative border rounded-lg overflow-hidden transition-all duration-300
                        ${step.status === 'in_progress' ?
                          'border-blue-400 bg-gradient-to-r from-blue-900/20 to-transparent shadow-lg shadow-blue-500/20' :
                          step.status === 'completed' ?
                          'border-emerald-400 bg-gradient-to-r from-emerald-900/20 to-transparent' :
                          step.status === 'error' ?
                          'border-red-400 bg-gradient-to-r from-red-900/20 to-transparent' :
                          'border-gray-700 hover:border-gray-600'
                        }
                        backdrop-blur-sm
                      `}
                      whileHover={hasDetails ? { scale: 1.01, y: -2 } : undefined}
                    >
                      {/* Step Header - Clickable */}
                      <div
                        className={`flex items-start gap-3 p-3 ${hasDetails ? 'cursor-pointer hover:bg-gray-700/50' : ''} transition-colors`}
                        onClick={hasDetails ? () => toggleStep(step.id) : undefined}
                      >
                        <div className="relative w-6 h-6 mt-0.5 flex-shrink-0">
                          {/* Enhanced Status Indicator */}
                          {step.status === 'completed' && (
                            <motion.div
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              transition={{ type: "spring", stiffness: 400, damping: 10 }}
                              className="w-6 h-6 rounded-full bg-gradient-to-r from-emerald-400 to-emerald-600 flex items-center justify-center relative overflow-hidden"
                            >
                              <motion.div
                                initial={{ pathLength: 0 }}
                                animate={{ pathLength: 1 }}
                                transition={{ duration: 0.5, delay: 0.2 }}
                              >
                                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <motion.path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={3}
                                    d="M5 13l4 4L19 7"
                                    initial={{ pathLength: 0 }}
                                    animate={{ pathLength: 1 }}
                                    transition={{ duration: 0.3, delay: 0.3 }}
                                  />
                                </svg>
                              </motion.div>
                              {/* Success burst effect */}
                              <motion.div
                                initial={{ scale: 1, opacity: 0 }}
                                animate={{ scale: 2, opacity: [0, 0.8, 0] }}
                                transition={{ duration: 0.6, delay: 0.1 }}
                                className="absolute inset-0 rounded-full bg-emerald-400"
                              />
                            </motion.div>
                          )}
                          {step.status === 'in_progress' && (
                            <div className="w-6 h-6 rounded-full bg-gradient-to-r from-blue-400 to-blue-600 flex items-center justify-center relative overflow-hidden">
                              {/* Neural network thinking animation */}
                              <motion.div
                                animate={{
                                  rotate: 360,
                                  scale: [1, 1.1, 1]
                                }}
                                transition={{
                                  rotate: { duration: 2, repeat: Infinity, ease: "linear" },
                                  scale: { duration: 1.5, repeat: Infinity, ease: "easeInOut" }
                                }}
                                className="absolute inset-0"
                              >
                                <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none">
                                  <circle cx="12" cy="12" r="3" stroke="white" strokeWidth="2" opacity="0.8" />
                                  <circle cx="12" cy="12" r="7" stroke="white" strokeWidth="1" opacity="0.4" />
                                  <motion.circle
                                    cx="12" cy="12" r="7"
                                    stroke="white"
                                    strokeWidth="1"
                                    strokeDasharray="44"
                                    strokeLinecap="round"
                                    animate={{ strokeDashoffset: [0, -44] }}
                                    transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                                    opacity="0.6"
                                  />
                                </svg>
                              </motion.div>
                              {/* Pulsing glow */}
                              <motion.div
                                animate={{
                                  scale: [1, 1.5, 1],
                                  opacity: [0.3, 0.1, 0.3]
                                }}
                                transition={{
                                  duration: 2,
                                  repeat: Infinity,
                                  ease: "easeInOut"
                                }}
                                className="absolute inset-0 rounded-full bg-blue-400 -z-10"
                              />
                            </div>
                          )}
                          {step.status === 'error' && (
                            <motion.div
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              whileHover={{ scale: 1.1 }}
                              transition={{ type: "spring", stiffness: 400, damping: 10 }}
                              className="w-6 h-6 rounded-full bg-gradient-to-r from-red-400 to-red-600 flex items-center justify-center relative"
                            >
                              <motion.div
                                animate={{ rotate: [0, -5, 5, 0] }}
                                transition={{ duration: 0.5, repeat: 2 }}
                              >
                                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </motion.div>
                              {/* Error pulse */}
                              <motion.div
                                animate={{
                                  scale: [1, 1.3, 1],
                                  opacity: [0.5, 0.2, 0.5]
                                }}
                                transition={{
                                  duration: 1,
                                  repeat: Infinity,
                                  ease: "easeInOut"
                                }}
                                className="absolute inset-0 rounded-full bg-red-400 -z-10"
                              />
                            </motion.div>
                          )}
                          {step.status === 'stopped' && (
                            <div className="w-6 h-6 rounded-full bg-gradient-to-r from-yellow-400 to-yellow-600 flex items-center justify-center">
                              <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 24 24">
                                <rect x="6" y="6" width="12" height="12" rx="2" />
                              </svg>
                            </div>
                          )}
                          {step.status === 'pending' && (
                            <motion.div
                              animate={{
                                scale: [1, 1.05, 1],
                                opacity: [0.6, 0.8, 0.6]
                              }}
                              transition={{
                                duration: 2,
                                repeat: Infinity,
                                ease: "easeInOut"
                              }}
                              className="w-6 h-6 rounded-full bg-gradient-to-r from-gray-400 to-gray-600 border-2 border-gray-300"
                            />
                          )}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <div className="text-sm font-medium text-gray-200 flex-1">{step.name}</div>
                            <div className="flex items-center gap-2">
                              {/* Breakdown Button */}
                              {hasBreakdown && (
                                <motion.button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleBreakdown(step.id);
                                  }}
                                  className={`
                                    px-2 py-1 text-xs rounded-md transition-all duration-200
                                    ${isBreakdownExpanded ?
                                      'bg-purple-500/20 text-purple-300 border border-purple-500/40' :
                                      'bg-gray-600/40 text-gray-400 border border-gray-600/60 hover:bg-purple-500/20 hover:text-purple-300'
                                    }
                                  `}
                                  whileHover={{ scale: 1.05 }}
                                  whileTap={{ scale: 0.95 }}
                                  title=\"Show step breakdown\"
                                >
                                  <div className=\"flex items-center gap-1\">
                                    <svg className=\"w-3 h-3\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\">
                                      <path strokeLinecap=\"round\" strokeLinejoin=\"round\" strokeWidth={2} d=\"M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4\" />
                                    </svg>
                                    {subSteps.length}
                                  </div>
                                </motion.button>
                              )}
                              {/* Expand Button */}
                              {hasDetails && (
                                <motion.div
                                  className=\"text-gray-400 text-lg font-bold cursor-pointer hover:text-gray-200 transition-colors\"
                                  animate={{ rotate: isExpanded ? 180 : 0 }}
                                  transition={{ duration: 0.2 }}
                                >
                                  <svg className=\"w-4 h-4\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\">
                                    <path strokeLinecap=\"round\" strokeLinejoin=\"round\" strokeWidth={2} d=\"M19 9l-7 7-7-7\" />
                                  </svg>
                                </motion.div>
                              )}
                            </div>
                          </div>
                          {step.thinking && step.thinking.length > 0 && (
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

                      {/* Glow effect for active steps */}
                      {step.status === 'in_progress' && (
                        <motion.div
                          animate={{
                            opacity: [0.2, 0.5, 0.2],
                            scale: [1, 1.02, 1]
                          }}
                          transition={{
                            duration: 2,
                            repeat: Infinity,
                            ease: "easeInOut"
                          }}
                          className="absolute inset-0 bg-blue-400 opacity-10 rounded-lg pointer-events-none"
                        />
                      )}

                      {/* Breakdown Content */}
                      <AnimatePresence>
                        {isBreakdownExpanded && hasBreakdown && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.3, ease: 'easeOut' }}
                            className="overflow-hidden bg-gradient-to-r from-purple-900/10 to-transparent"
                          >
                            <div className="px-6 py-4 border-t border-purple-500/20">
                              <h4 className="text-xs font-semibold text-purple-300 mb-3 flex items-center gap-2">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                                Step Breakdown
                              </h4>
                              <div className="space-y-3">
                                {subSteps.map((subStep, idx) => (
                                  <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, x: -20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ duration: 0.2, delay: idx * 0.1 }}
                                    className="flex items-center gap-3 p-3 bg-gray-800/50 rounded-lg border border-gray-700/50 hover:border-gray-600/50 transition-colors"
                                  >
                                    {/* Sub-step Status */}
                                    <div className="w-4 h-4 flex-shrink-0">
                                      {subStep.status === 'completed' && (
                                        <motion.div
                                          initial={{ scale: 0 }}
                                          animate={{ scale: 1 }}
                                          transition={{ delay: idx * 0.1 + 0.2 }}
                                          className="w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center"
                                        >
                                          <svg className="w-2 h-2 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={4} d="M5 13l4 4L19 7" />
                                          </svg>
                                        </motion.div>
                                      )}
                                      {subStep.status === 'in_progress' && (
                                        <motion.div
                                          animate={{ rotate: 360 }}
                                          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                                          className="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent"
                                        />
                                      )}
                                    </div>

                                    {/* Sub-step Content */}
                                    <div className="flex-1">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className="text-sm font-medium text-gray-200">{subStep.name}</span>
                                        {/* Confidence indicator */}
                                        <div className="flex items-center gap-1">
                                          <div className="w-8 h-1 bg-gray-700 rounded-full overflow-hidden">
                                            <motion.div
                                              className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full"
                                              initial={{ width: 0 }}
                                              animate={{ width: `${subStep.confidence * 100}%` }}
                                              transition={{ duration: 0.8, delay: idx * 0.1 + 0.3 }}
                                            />
                                          </div>
                                          <span className="text-xs text-gray-400">{Math.round(subStep.confidence * 100)}%</span>
                                        </div>
                                      </div>
                                      <p className="text-xs text-gray-400">{subStep.description}</p>
                                    </div>
                                  </motion.div>
                                ))}
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>

                      {/* Expanded Content */}
                      <AnimatePresence>
                        {isExpanded && hasDetails && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="px-3 pb-3 border-t border-gray-700">
                              {renderDetailedContent(step)}
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
        )}
      </>
    );
  }
};

export default ProcessPanel;









