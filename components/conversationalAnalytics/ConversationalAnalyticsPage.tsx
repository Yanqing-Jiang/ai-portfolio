import React, { useState, useRef, useEffect } from 'react';
import { useSSEStream, ThinkingStep } from './hooks/useSSEStream';

// Thinking Process Panel Component
const ThinkingPanel: React.FC<{ steps: ThinkingStep[]; isExpanded: boolean; onToggle: () => void }> = ({
    steps,
    isExpanded,
    onToggle,
}) => {
    if (steps.length === 0) return null;

    const getStatusIcon = (status: ThinkingStep['status']) => {
        switch (status) {
            case 'completed': return '✓';
            case 'running': return '●';
            case 'error': return '✗';
            default: return '○';
        }
    };

    const getStatusColor = (status: ThinkingStep['status']) => {
        switch (status) {
            case 'completed': return 'text-green-400';
            case 'running': return 'text-blue-400 animate-pulse';
            case 'error': return 'text-red-400';
            default: return 'text-gray-500';
        }
    };

    return (
        <div className="mb-4">
            <button
                onClick={onToggle}
                className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
            >
                <span className={`transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}>▶</span>
                <span>Thinking... ({steps.filter(s => s.status === 'completed').length}/{steps.length} steps)</span>
            </button>
            {isExpanded && (
                <div className="mt-2 pl-4 border-l-2 border-gray-700 space-y-1">
                    {steps.map((step, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-sm">
                            <span className={getStatusColor(step.status)}>{getStatusIcon(step.status)}</span>
                            <span className="text-gray-300">{step.message || step.step.replace(/_/g, ' ')}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

// Message Bubble Component
const MessageBubble: React.FC<{
    role: 'user' | 'assistant';
    content: string;
    thinkingSteps?: ThinkingStep[];
    chartConfig?: Record<string, unknown> | null;
    isStreaming?: boolean;
}> = ({ role, content, thinkingSteps, chartConfig, isStreaming }) => {
    const [thinkingExpanded, setThinkingExpanded] = useState(true);
    const isUser = role === 'user';

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
            <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${isUser
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-800 text-gray-100 border border-gray-700'
                    }`}
            >
                {!isUser && thinkingSteps && thinkingSteps.length > 0 && (
                    <ThinkingPanel
                        steps={thinkingSteps}
                        isExpanded={thinkingExpanded}
                        onToggle={() => setThinkingExpanded(!thinkingExpanded)}
                    />
                )}

                {/* Chart placeholder */}
                {chartConfig && (
                    <div className="mb-3 p-4 bg-gray-900 rounded-lg border border-gray-700">
                        <div className="text-sm text-gray-400 mb-2">📊 Chart Generated</div>
                        <div className="text-xs text-gray-500">
                            {JSON.stringify(chartConfig).slice(0, 100)}...
                        </div>
                    </div>
                )}

                <p className="whitespace-pre-wrap">{content}</p>
                {isStreaming && <span className="inline-block w-2 h-4 bg-blue-400 animate-pulse ml-1">|</span>}
            </div>
        </div>
    );
};

// Status Bar Component
const StatusBar: React.FC<{ status: string; isConnected: boolean }> = ({ status, isConnected }) => (
    <div className="flex items-center gap-2 px-4 py-2 bg-gray-800 border-b border-gray-700 text-sm">
        <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-500'}`} />
        <span className="text-gray-400">{status}</span>
    </div>
);

// Main Page Component
const ConversationalAnalyticsPage: React.FC = () => {
    const [messages, setMessages] = useState<Array<{
        role: 'user' | 'assistant';
        content: string;
        thinkingSteps?: ThinkingStep[];
        chartConfig?: Record<string, unknown> | null;
    }>>([]);
    const [inputValue, setInputValue] = useState('');
    const [sessionId] = useState(() => `session-${Date.now()}`);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const {
        isStreaming,
        content,
        thinkingSteps,
        chartConfig,
        error,
        sendMessage,
        reset,
    } = useSSEStream();

    // Auto-scroll to bottom
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, content]);

    // Handle streaming content updates
    useEffect(() => {
        if (!isStreaming && content) {
            // Stream completed - add assistant message
            setMessages(prev => [
                ...prev,
                {
                    role: 'assistant',
                    content,
                    thinkingSteps,
                    chartConfig,
                },
            ]);
            reset();
        }
    }, [isStreaming, content, thinkingSteps, chartConfig, reset]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!inputValue.trim() || isStreaming) return;

        // Add user message
        setMessages(prev => [...prev, { role: 'user', content: inputValue }]);

        // Send to API
        sendMessage(inputValue, sessionId);
        setInputValue('');
    };

    return (
        <div className="flex flex-col h-full bg-gray-900">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 bg-gray-800 border-b border-gray-700">
                <h1 className="text-xl font-semibold text-white">
                    Conversational Analytics
                    <span className="ml-2 text-sm font-normal text-gray-400">Claude Agent</span>
                </h1>
            </div>

            {/* Status Bar */}
            <StatusBar
                status={isStreaming ? 'Processing...' : 'Ready'}
                isConnected={true}
            />

            {/* Messages Container */}
            <div className="flex-1 overflow-y-auto p-6">
                {messages.length === 0 && !isStreaming && (
                    <div className="text-center text-gray-500 mt-20">
                        <p className="text-lg mb-4">Ask me about semiconductor company financials</p>
                        <div className="space-y-2">
                            <button
                                onClick={() => setInputValue('Show me NVDA revenue trends over the last 5 years')}
                                className="block mx-auto px-4 py-2 bg-gray-800 rounded-lg hover:bg-gray-700 text-sm text-gray-300"
                            >
                                Show me NVDA revenue trends
                            </button>
                            <button
                                onClick={() => setInputValue('Compare AMD and Intel profit margins')}
                                className="block mx-auto px-4 py-2 bg-gray-800 rounded-lg hover:bg-gray-700 text-sm text-gray-300"
                            >
                                Compare AMD and Intel margins
                            </button>
                        </div>
                    </div>
                )}

                {messages.map((msg, idx) => (
                    <MessageBubble
                        key={idx}
                        role={msg.role}
                        content={msg.content}
                        thinkingSteps={msg.thinkingSteps}
                        chartConfig={msg.chartConfig}
                    />
                ))}

                {/* Streaming message */}
                {isStreaming && (
                    <MessageBubble
                        role="assistant"
                        content={content}
                        thinkingSteps={thinkingSteps}
                        chartConfig={chartConfig}
                        isStreaming={true}
                    />
                )}

                {/* Error display */}
                {error && (
                    <div className="text-red-400 text-center py-4">
                        Error: {error}
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <form onSubmit={handleSubmit} className="p-4 bg-gray-800 border-t border-gray-700">
                <div className="flex gap-3">
                    <input
                        type="text"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        placeholder="Ask about semiconductor financials..."
                        className="flex-1 px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                        disabled={isStreaming}
                    />
                    <button
                        type="submit"
                        disabled={isStreaming || !inputValue.trim()}
                        className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        {isStreaming ? '...' : '➤'}
                    </button>
                </div>
            </form>
        </div>
    );
};

export default ConversationalAnalyticsPage;
