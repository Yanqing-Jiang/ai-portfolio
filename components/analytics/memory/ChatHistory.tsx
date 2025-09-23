import React, { Suspense } from 'react';
import { ChatHistoryProps } from '../types';
import { ClarificationOptions } from './ClarificationOptions';
import { AnalysisCard, SqlCard, CollapsibleSection } from '../common';
import { isValidChartSpec } from '../utils';

const ChartCard = React.lazy(() => import('../common/ChartCard').then(m => ({ default: m.ChartCard }))); // Lazy-load heavy chart component

export const ChatHistory: React.FC<ChatHistoryProps> = ({ 
  messages, 
  isLoading, 
  onSubmitClarification,
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
                    <>
                      {console.log('🔍 [DEBUG] Rendering clarifications for message:', message.id, message.clarifications)}
                      <ClarificationOptions
                        clarification={message.clarifications[0]}
                        onSubmit={async (val) => onSubmitClarification(val, message.clarifications![0])}
                      />
                    </>
                  )}
                </div>

                {message.type === 'result' && (
                  <div className="mt-3 space-y-4">
                    {/* Chart Display */}
                    {message.chartSpec && isValidChartSpec(message.chartSpec) && (
                      <Suspense fallback={<div className="rounded-xl border border-gray-700 bg-gray-800/40 p-6 text-sm text-gray-300">Loading chart...</div>}>
                        <div className="rounded-xl overflow-hidden border border-gray-700">
                          <ChartCard
                            chartSpec={message.chartSpec}
                            dataSample={message.dataSample}
                            enableDropdown={true}
                            enableCsvDownload={true}
                          />
                        </div>
                      </Suspense>
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
