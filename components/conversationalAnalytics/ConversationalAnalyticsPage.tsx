/**
 * Function: ConversationalAnalyticsPage - Next Gen Analytics (Agent) chat UI inspired by ChatGPT/Claude
 * Called from: ProjectView for the conversational-analytics project
 * Invokes: useSSEStream hook for Claude agent streaming, renders MessageBubble, ProcessPanel with dynamic steps
 * Purpose: Delivers a sleek, minimalist chat experience for semiconductor financial analysis
 */

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSSEStream, ThinkingStep, NewsResult, HtmlArtifact } from './hooks/useSSEStream';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';
import SelectionCard from './SelectionCard';
import ProcessPanel from './ProcessPanel';
import { theme } from './styles';

/**
 * Function: WelcomeScreen - used when there are no chat messages to show starter prompts
 * Called from: ConversationalAnalyticsPage conditional render prior to the messages list
 * Invokes: onSuggestionClick callback to stage prompts in ChatInput
 * Purpose: Accelerates onboarding by giving one-click example queries for the analytics agents
 */
const WelcomeScreen: React.FC<{ onSuggestionClick: (prompt: string) => void; mode?: string }> = ({ onSuggestionClick, mode }) => {
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
      prompt: 'Net margin vs peers for NVDA over last 5 years',
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
          Next Gen Analytics (Agent)
        </h1>
        <p
          className="text-sm max-w-md"
          style={{ color: theme.colors.text.secondary }}
        >
          {mode === 'auto'
            ? 'Multi-agent routes to SQL, Chart Builder, TradingView, or News specialists.'
            : 'Available tickers: NVDA, AMD, INTC, AVGO, QCOM, MU, TXN.'}
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
  agentLabel?: string | null;
  htmlArtifact?: HtmlArtifact | null;
}

/**
 * Function: ConversationalAnalyticsPage - orchestrates chat layout, streaming state, and agent controls
 * Called from: ProjectView route for conversational analytics
 * Invokes: useSSEStream for backend interaction; renders ProcessPanel (dynamic steps), MessageBubble, SelectionCard, ChatInput
 * Purpose: Central hub connecting UI, agent selection, and streaming data flow
 */
// Main Page Component
const ConversationalAnalyticsPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [sessionId] = useState(() => `session-${Date.now()}`);
  const [agentMode, setAgentMode] = useState<string>('single');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const {
    isStreaming,
    isPaused,
    content,
    thinkingSteps,
    chartConfig,
    dataResult,
    newsResult,
    skillInfo,
    htmlArtifact,
    error,
    debugLogs,
    pendingSelection,
    activeAgent,
    processNodes,
    processEdges,
    lastAgentLabel,
    runId,
    permissionState,
    sendMessage,
    pauseStream,
    resumeLast,
    submitSelection,
    cancelSelection,
  } = useSSEStream();
  const activeAgentLabel = activeAgent?.name || lastAgentLabel || (agentMode === 'single' ? 'Single Agent' : 'Assistant');

  /**
   * Function: buildDynamicSuggestions - crafts quick prompts based on the latest user text and tickers
   * Called from: ChatInput via suggestionsOverride prop
   * Invokes: Regex parsing for ticker symbols; returns suggestion metadata consumed by ChatInput
   * Purpose: Keep assistant proactive with context-aware prompts without manual typing
   */
  const buildDynamicSuggestions = (): { label: string; prompt: string; icon: string }[] => {
    const lastUser = [...messages].reverse().find((m) => m.role === 'user');
    const text = lastUser?.content || '';
    const tickers = Array.from(
      new Set((text.match(/\b[A-Z]{2,5}\b/g) || []).filter((t) => t.length >= 2 && t.length <= 5))
    );
    const suggestions: { label: string; prompt: string; icon: string }[] = [];

    if (tickers.length > 0) {
      const ticker = tickers[0];
      suggestions.push({
        label: 'Stock price',
        prompt: `Show stock price for ${ticker} (6M, candlestick + volume)`,
        icon: '📈',
      });
      suggestions.push({
        label: 'News sentiment',
        prompt: `Latest news sentiment for ${ticker}`,
        icon: '📰',
      });
    }

    if (suggestions.length < 3 && text.toLowerCase().includes('year')) {
      suggestions.push({
        label: 'Quarterly view',
        prompt: 'Show quarterly trend for the last 8 quarters',
        icon: '📅',
      });
    }

    return suggestions.slice(0, 3);
  };

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
    const hasPayload = content || chartConfig || dataResult || newsResult || htmlArtifact;
    if (!isStreaming && hasPayload) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content,
          thinkingSteps,
          chartConfig,
          dataResult,
          newsResult,
          agentLabel: activeAgentLabel,
          htmlArtifact,
        },
      ]);
    }
  }, [isStreaming, content, thinkingSteps, chartConfig, dataResult, newsResult, htmlArtifact, activeAgentLabel]);

  /**
   * Function: handleSubmit - dispatches the typed prompt to the SSE pipeline
   * Called from: ChatInput onSubmit
   * Invokes: sendMessage with session/agent context and updates local message log
   * Purpose: Central guard preventing empty submissions or overlapping sends
   */
  const handleSubmit = () => {
    if (!inputValue.trim() || (isStreaming && !isPaused)) return;

    setMessages((prev) => [...prev, { role: 'user', content: inputValue }]);
    sendMessage(inputValue, sessionId, agentMode);
    setInputValue('');
  };

  /**
   * Function: handleSuggestionClick - stages a suggested prompt for the user
   * Called from: WelcomeScreen suggestion buttons
   * Invokes: setInputValue to prefill ChatInput
   * Purpose: Simplifies prompt entry from curated examples
   */
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
              Next Gen Analytics (Agent)
            </h1>
            <p className="text-xs" style={{ color: theme.colors.text.muted }}>
              Select Single Agent or Multi-agent
              <span
                aria-hidden="true"
                className="ml-1 text-sm align-middle"
                style={{ color: '#facc15' }}
              >
                →
              </span>
            </p>
          </div>
        </div>

        {/* Process Panel + agent selector */}
        <div className="flex items-center gap-4">
          {/* Process Panel (replaces Connected status) */}
          <ProcessPanel
            isStreaming={isStreaming}
            processNodes={processNodes}
            processEdges={processEdges}
            activeAgent={activeAgent}
            agentMode={agentMode}
            skillInfo={skillInfo}
            debugLogs={debugLogs}
            runId={runId}
            permissionState={permissionState}
          />

          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: theme.colors.text.muted }}>
              Agent
            </span>
            <select
              value={agentMode}
              onChange={(e) => setAgentMode(e.target.value)}
              className="text-xs px-2 py-1 rounded-lg border"
              style={{
                backgroundColor: theme.colors.bg.elevated,
                borderColor: theme.colors.border.subtle,
                color: theme.colors.text.primary,
              }}
              disabled={isStreaming}
            >
              <option value="single">Single Agent</option>
              <option value="auto">Multi-agent</option>
            </select>
          </div>
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
              mode={agentMode}
            />
          ) : (
            <motion.div
              key="messages"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="max-w-4xl mx-auto px-4 py-6"
            >
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
                  agentLabel={msg.agentLabel}
                  htmlArtifact={msg.htmlArtifact}
                />
              ))}

              {/* Streaming message */}
              {isStreaming && (content || chartConfig || dataResult || newsResult || htmlArtifact) && (
                <MessageBubble
                  role="assistant"
                  content={content}
                  chartConfig={chartConfig}
                  dataResult={dataResult}
                  newsResult={newsResult}
                  htmlArtifact={htmlArtifact}
                  isStreaming={true}
                  agentLabel={activeAgentLabel}
                />
              )}

              {/* HITL Selection Card */}
              {pendingSelection && (
                <SelectionCard
                  selection={pendingSelection}
                  sessionId={sessionId}
                  onSubmit={async (sid, optId, customVal) => {
                    await submitSelection(sid, optId, customVal);
                    // After successful selection, re-send the original message to resume
                    if (messages.length > 0) {
                      const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
                      if (lastUserMsg) {
                        sendMessage(lastUserMsg.content, sid, agentMode);
                      }
                    }
                  }}
                  onCancel={cancelSelection}
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
        onPause={pauseStream}
        onResume={resumeLast}
        isStreaming={isStreaming}
        isPaused={isPaused}
        placeholder="Ask about semiconductor financials..."
        suggestionsOverride={buildDynamicSuggestions()}
      />
    </div>
  );
};

export default ConversationalAnalyticsPage;
