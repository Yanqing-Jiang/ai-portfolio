import React from 'react';
import { ChatHistoryProps } from '../types';
import { ClarificationOptions } from './ClarificationOptions';
import { ChartCard, AnalysisCard, SqlCard, CollapsibleSection } from '../common';
import { isValidChartSpec } from '../utils';

export const ChatHistory: React.FC<ChatHistoryProps> = ({ 
  messages, 
  isLoading, 
  onSubmitClarification,
  onApproveWorkflow,
  processSteps = []
}) => {
  if (messages.length === 0) return null;

  return (
    <div className="bg-gray-900 py-4 mb-6">
      <div className="space-y-4">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] ${message.type === 'user' ? 'order-2' : 'order-1'}`}>
              {/* Message bubble */}
              <div className={`transition-all hover:shadow-sm ${
                message.type === 'user' 
                  ? 'bg-gray-800 text-gray-100 rounded-2xl rounded-br-md px-4 py-3' 
                  : message.type === 'result'
                    ? 'bg-gray-800/30 text-gray-100 rounded-2xl rounded-bl-md p-2'
                    : 'bg-gray-800/50 text-gray-100 rounded-2xl rounded-bl-md px-4 py-3'
              }`}>
                <div className={message.type === 'result' ? 'px-2 py-1' : ''}>
                  <div className="text-sm leading-relaxed">{message.content}</div>
                  {message.answers && Object.keys(message.answers).length > 0 && (
                    <div className={`text-xs mt-2 ${
                      message.type === 'user' ? 'text-blue-100' : 'text-gray-400'
                    }`}>
                      Answered: {Object.entries(message.answers).map(([k, v]) => `${k}: ${v}`).join(', ')}
                    </div>
                  )}
                  {message.clarifications && message.clarifications.length > 0 && onSubmitClarification && (
                    <ClarificationOptions 
                      clarification={message.clarifications[0]} 
                      onSubmit={async (val) => onSubmitClarification(val, message.clarifications![0])}
                    />
                  )}
                </div>
                
                {/* Embedded Rich Content for Result Messages */}
                {message.type === 'result' && (
                  <div className="mt-3 space-y-4">
                    {/* Chart Display */}
                    {message.chartSpec && isValidChartSpec(message.chartSpec) && (
                      <div className="rounded-xl overflow-hidden border border-gray-700">
                        <ChartCard
                          chartSpec={message.chartSpec}
                          dataSample={message.dataSample}
                          enableDropdown={true}
                          enableCsvDownload={true}
                        />
                      </div>
                    )}
                    
                    {/* Analysis Display */}
                    {message.analysis && (
                      <div className="rounded-xl overflow-hidden">
                        <AnalysisCard analysis={message.analysis} />
                      </div>
                    )}
                    
                    {/* SQL Query Display (Collapsible) */}
                    {message.sqlQuery && (
                      <CollapsibleSection 
                        title="Generated SQL Query" 
                        defaultOpen={false}
                        className="bg-gray-800/50"
                      >
                        <SqlCard sqlQuery={message.sqlQuery} compact={true} />
                      </CollapsibleSection>
                    )}
                    
                    {/* Thinking Process Display (Collapsible) */}
                    {processSteps.length > 0 && (
                      <CollapsibleSection 
                        title="Thinking (internal)" 
                        defaultOpen={false}
                        className="bg-gray-800/30"
                      >
                        <div className="space-y-2 p-2">
                          {processSteps.map((step) => (
                            <div key={step.id} className="flex items-start gap-3 text-sm">
                              {/* Status indicator */}
                              <div className="flex-shrink-0 mt-1">
                                {step.status === 'completed' && (
                                  <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                                )}
                                {step.status === 'in_progress' && (
                                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div>
                                )}
                                {step.status === 'error' && (
                                  <div className="w-2 h-2 bg-red-400 rounded-full"></div>
                                )}
                                {step.status === 'pending' && (
                                  <div className="w-2 h-2 bg-gray-500 rounded-full"></div>
                                )}
                              </div>
                              
                              {/* Step content */}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="text-gray-300 font-medium">{step.name}</span>
                                  {step.elapsed_ms && (
                                    <span className="text-xs text-gray-500">
                                      ({step.elapsed_ms}ms)
                                    </span>
                                  )}
                                </div>
                                {step.thinking.length > 0 && (
                                  <div className="text-gray-400 text-xs mt-1">
                                    {step.thinking[step.thinking.length - 1]}
                                  </div>
                                )}
                                {step.details && Object.keys(step.details).length > 0 && (
                                  <div className="text-gray-500 text-xs mt-1">
                                    {Object.entries(step.details).map(([key, value]) => (
                                      <span key={key} className="mr-3">
                                        {key}: {typeof value === 'object' ? JSON.stringify(value).slice(0, 50) + '...' : String(value)}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </CollapsibleSection>
                    )}
                  </div>
                )}
              </div>
              
              {/* Timestamp only */}
              <div className={`flex items-center gap-2 mt-1 px-1 ${
                message.type === 'user' ? 'justify-end' : 'justify-start'
              }`}>
                <span className="text-xs text-gray-500">
                  {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
            
            {/* Avatar */}
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
              message.type === 'user' 
                ? 'bg-gray-700 text-gray-300 order-3 ml-2' 
                : 'bg-gray-700/50 text-gray-400 order-0 mr-2'
            }`}>
              {message.type === 'user' ? '👤' : '🤖'}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="max-w-[80%] order-1">
              <div className="bg-gray-800/50 text-gray-100 rounded-2xl rounded-bl-md px-4 py-3 transition-all">
                <div className="flex items-center gap-2">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                  <span className="text-sm text-gray-300">Analyzing...</span>
                </div>
              </div>
              <div className="flex items-center gap-2 mt-1 px-1 justify-start">
                <span className="text-xs text-gray-500">
                  {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
            <div className="w-8 h-8 rounded-full bg-gray-600 text-gray-300 flex items-center justify-center flex-shrink-0 order-0 mr-2">
              🤖
            </div>
          </div>
        )}
      </div>
    </div>
  );
};