import React from 'react';
import { ChatHistoryProps } from '../types';
import { ClarificationOptions } from './ClarificationOptions';

export const ChatHistory: React.FC<ChatHistoryProps> = ({ 
  messages, 
  isLoading, 
  onSubmitClarification 
}) => {
  if (messages.length === 0) return null;

  return (
    <div className="bg-gray-900 py-4 mb-6">
      <div className="space-y-4">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] ${message.type === 'user' ? 'order-2' : 'order-1'}`}>
              {/* Message bubble */}
              <div className={`rounded-2xl px-4 py-3 transition-all hover:shadow-sm ${
                message.type === 'user' 
                  ? 'bg-gray-800 text-gray-100 rounded-br-md' 
                  : 'bg-gray-800/50 text-gray-100 rounded-bl-md'
              }`}>
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