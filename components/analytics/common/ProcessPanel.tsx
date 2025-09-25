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
                  {steps.map((step) => {
                    const isExpanded = expandedSteps.has(step.id);
                    const hasDetails = (
                    step.details && Object.keys(step.details).some(
                      key => step.details![key as keyof typeof step.details] != null
                    )
                  ) || (step.thinking && step.thinking.length > 0);

                    return (
                    <div key={step.id} className="border border-gray-700 rounded-lg">
                      {/* Step Header - Clickable */}
                      <div
                        className={`flex items-start gap-3 p-3 ${hasDetails ? 'cursor-pointer hover:bg-gray-700/50' : ''} transition-colors`}
                        onClick={hasDetails ? () => toggleStep(step.id) : undefined}
                      >
                        <div className={`w-3 h-3 rounded-full mt-1 flex-shrink-0 ${
                          step.status === 'completed' ? 'bg-green-500' :
                          step.status === 'in_progress' ? 'bg-blue-500 animate-pulse' :
                          step.status === 'error' ? 'bg-red-500' :
                          step.status === 'stopped' ? 'bg-yellow-500' :
                          'bg-gray-500'
                        }`} />
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <div className="text-sm font-medium text-gray-200">{step.name}</div>
                            {hasDetails && (
                              <div className="text-gray-400 ml-2">
                                {isExpanded ? '−' : '+'}
                              </div>
                            )}
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
                    </div>
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









