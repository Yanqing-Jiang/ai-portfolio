/**
 * Function: ConversationalAnalyticsPage — Modern ChatGPT/Claude-inspired conversational analytics UI
 * Called from: ProjectView for the conversational-analytics project
 * Invokes: useSSEStream hook for Claude agent streaming, renders MessageBubble, ThinkingProcessBar
 * Purpose: Delivers a sleek, minimalist chat experience for semiconductor financial analysis
 */

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSSEStream, ThinkingStep, NewsResult } from './hooks/useSSEStream';
import MessageBubble from './MessageBubble';
import ThinkingProcessBar from './ThinkingProcessBar';
import ChatInput from './ChatInput';
import { theme } from './styles';

// Welcome screen component
const WelcomeScreen: React.FC<{ onSuggestionClick: (prompt: string) => void }> = ({ onSuggestionClick }) => {
  const suggestions = [
    {
      icon: '📊',
      title: 'Market Share Analysis',
      description: 'Compare market positions',
      prompt: 'Market share of NVDA vs peers over the last 5 years',
    },
    {
      icon: '📈',
      title: 'Revenue Comparison',
      description: 'Cross-company revenue trends',
      prompt: 'Compare revenue for NVDA, AMD, INTC by year (last 5 years)',
    },
    {
      icon: '📉',
      title: 'Growth Metrics',
      description: 'YoY/QoQ growth rates',
      prompt: 'YoY revenue growth for NVDA and AMD by quarter',
    },
    {
      icon: '💹',
      title: 'Margin Analysis',
      description: 'Profitability vs peers',
      prompt: 'Net margin vs peers for TXN over last 5 years',
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex flex-col items-center justify-center h-full px-6"
    >
      {/* Logo/Title */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="text-center mb-10"
      >
        <div
          className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center text-3xl"
          style={{
            background: `linear-gradient(135deg, ${theme.colors.accent.muted} 0%, ${theme.colors.bg.elevated} 100%)`,
            border: `1px solid ${theme.colors.border.medium}`,
          }}
        >
          ⚡
        </div>
        <h1
          className="text-2xl font-semibold mb-2"
          style={{ color: theme.colors.text.primary }}
        >
          Semiconductor Analyst
        </h1>
        <p
          className="text-sm max-w-md"
          style={{ color: theme.colors.text.secondary }}
        >
          AI-powered financial analysis for semiconductor companies.
          Ask questions about revenue, margins, market share, and growth.
        </p>
      </motion.div>

      {/* Suggestion cards */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl"
      >
        {suggestions.map((s, idx) => (
          <motion.button
            key={idx}
            onClick={() => onSuggestionClick(s.prompt)}
            className="p-4 rounded-xl text-left transition-all group"
            style={{
              backgroundColor: theme.colors.bg.tertiary,
              border: `1px solid ${theme.colors.border.subtle}`,
            }}
            whileHover={{
              borderColor: theme.colors.accent.primary + '40',
              backgroundColor: theme.colors.bg.elevated,
            }}
            whileTap={{ scale: 0.98 }}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 + idx * 0.05 }}
          >
            <div className="flex items-start gap-3">
              <span className="text-2xl">{s.icon}</span>
              <div>
                <h3
                  className="text-sm font-medium mb-0.5"
                  style={{ color: theme.colors.text.primary }}
                >
                  {s.title}
                </h3>
                <p
                  className="text-xs"
                  style={{ color: theme.colors.text.muted }}
                >
                  {s.description}
                </p>
              </div>
              <motion.span
                className="ml-auto text-sm opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ color: theme.colors.accent.primary }}
              >
                →
              </motion.span>
            </div>
          </motion.button>
        ))}
      </motion.div>

      {/* Powered by */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="mt-8 text-xs"
        style={{ color: theme.colors.text.muted }}
      >
        Powered by Claude AI • Data from comp_financials
      </motion.p>
    </motion.div>
  );
};

// Message type for chat history
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  thinkingSteps?: ThinkingStep[];
  chartConfig?: Record<string, unknown> | null;
  dataResult?: { rows: unknown[]; columns: string[] } | null;
  newsResult?: NewsResult | null;
}

// Main Page Component
const ConversationalAnalyticsPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [sessionId] = useState(() => `session-${Date.now()}`);
  const [isPlanExpanded, setIsPlanExpanded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const {
    isStreaming,
    content,
    thinkingSteps,
    chartConfig,
    dataResult,
    newsResult,
    skillInfo,
    planSteps,
    currentStepId,
    error,
    errorDetails,
    debugLogs,
    sendMessage,
    reset,
  } = useSSEStream();

  // Auto-scroll to bottom
  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [messages, content, thinkingSteps]);

  // Handle streaming completion
  useEffect(() => {
    if (!isStreaming && content) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content,
          thinkingSteps,
          chartConfig,
          dataResult,
          newsResult,
        },
      ]);
    }
  }, [isStreaming, content, thinkingSteps, chartConfig, dataResult, newsResult, reset]);

  const handleSubmit = () => {
    if (!inputValue.trim() || isStreaming) return;

    setMessages((prev) => [...prev, { role: 'user', content: inputValue }]);
    sendMessage(inputValue, sessionId);
    setInputValue('');
  };

  const handleSuggestionClick = (prompt: string) => {
    setInputValue(prompt);
  };

  const showWelcome = messages.length === 0 && !isStreaming;

  return (
    <div
      className="flex flex-col h-full"
      style={{ backgroundColor: theme.colors.bg.primary }}
    >
      {/* Header */}
      <header
        className="flex items-center justify-between px-6 py-4 shrink-0"
        style={{
          backgroundColor: theme.colors.bg.secondary,
          borderBottom: `1px solid ${theme.colors.border.subtle}`,
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-lg"
            style={{
              background: theme.colors.accent.muted,
              color: theme.colors.accent.primary,
            }}
          >
            ⚡
          </div>
          <div>
            <h1
              className="text-base font-semibold"
              style={{ color: theme.colors.text.primary }}
            >
              Conversational Analytics
            </h1>
            <p className="text-xs" style={{ color: theme.colors.text.muted }}>
              Claude-powered semiconductor insights
            </p>
          </div>
        </div>

        {/* Session indicator */}
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full"
            style={{
              backgroundColor: isStreaming
                ? theme.colors.accent.primary
                : theme.colors.status.success,
            }}
          />
          <span className="text-xs" style={{ color: theme.colors.text.muted }}>
            {isStreaming ? 'Processing...' : 'Connected'}
          </span>
        </div>
      </header>

      {/* Messages area */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto"
        style={{ backgroundColor: theme.colors.bg.primary }}
      >
        <AnimatePresence mode="wait">
          {showWelcome ? (
            <WelcomeScreen
              key="welcome"
              onSuggestionClick={handleSuggestionClick}
            />
          ) : (
            <motion.div
              key="messages"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="max-w-4xl mx-auto px-4 py-6"
            >
              {/* Thinking / Plan bar pinned at top */}
              {(isStreaming || planSteps.length > 0 || error) && (
                <div className="sticky top-0 z-10 pb-3" style={{ backgroundColor: `${theme.colors.bg.primary}cc`, backdropFilter: 'blur(6px)' }}>
                  <ThinkingProcessBar
                    steps={planSteps}
                    currentStepId={currentStepId}
                    isExpanded={isPlanExpanded}
                    onToggle={() => setIsPlanExpanded(prev => !prev)}
                    debugLogs={debugLogs}
                    error={error}
                    errorDetails={errorDetails}
                    skillInfo={skillInfo}
                    isStreaming={isStreaming}
                  />
                </div>
              )}

              {/* Message thread */}
              {messages.map((msg, idx) => (
                <MessageBubble
                  key={idx}
                  role={msg.role}
                  content={msg.content}
                  thinkingSteps={msg.thinkingSteps}
                  chartConfig={msg.chartConfig}
                  dataResult={msg.dataResult}
                  newsResult={msg.newsResult}
                />
              ))}

              {/* Streaming message */}
              {isStreaming && (content || chartConfig || dataResult || newsResult) && (
                <MessageBubble
                  role="assistant"
                  content={content}
                  chartConfig={chartConfig}
                  dataResult={dataResult}
                  newsResult={newsResult}
                  isStreaming={true}
                />
              )}

              {/* Error display */}
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-4 rounded-xl mb-4"
                  style={{
                    backgroundColor: theme.colors.status.error + '15',
                    border: `1px solid ${theme.colors.status.error}40`,
                  }}
                >
                  <div className="flex items-center gap-2">
                    <span style={{ color: theme.colors.status.error }}>⚠️</span>
                    <span
                      className="text-sm"
                      style={{ color: theme.colors.status.error }}
                    >
                      {error}
                    </span>
                  </div>
                </motion.div>
              )}

              <div ref={messagesEndRef} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Input area */}
      <ChatInput
        value={inputValue}
        onChange={setInputValue}
        onSubmit={handleSubmit}
        disabled={isStreaming}
      />
    </div>
  );
};

export default ConversationalAnalyticsPage;
