/**
 * Function: ConversationalAnalyticsPage - Next Gen Analytics (Agent) chat UI inspired by ChatGPT/Claude
 * Called from: ProjectView for the conversational-analytics project
 * Invokes: useSSEStream hook for Claude agent streaming, renders MessageBubble, ProcessPanel with dynamic steps
 * Purpose: Delivers a sleek, minimalist chat experience for semiconductor financial analysis
 */

import React, { useState, useRef, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSSEStream, ThinkingStep, NewsResult, HtmlArtifact, SkillInfo, ProcessNode, ProcessEdge, AgentInfo, DebugLog } from './hooks/useSSEStream';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';
import SelectionCard from './SelectionCard';
import { theme } from './styles';

/**
 * Function: ParticleField - Animated background particles for landing view
 * Called from: LandingView
 * Purpose: Creates an immersive, premium feel with floating particles
 */
const ParticleField: React.FC = () => {
  const particles = useMemo(() => {
    return Array.from({ length: 50 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 3 + 1,
      duration: Math.random() * 20 + 10,
      delay: Math.random() * 5,
    }));
  }, []);

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className="absolute rounded-full"
          style={{
            left: `${p.x}%`,
            top: `${p.y}%`,
            width: p.size,
            height: p.size,
            background: `rgba(${Math.random() > 0.5 ? '59, 130, 246' : '245, 158, 11'}, ${0.3 + Math.random() * 0.3})`,
          }}
          animate={{
            y: [0, -30, 0],
            opacity: [0.3, 0.7, 0.3],
          }}
          transition={{
            duration: p.duration,
            delay: p.delay,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  );
};

/**
 * Function: GlowOrb - Animated gradient orb for background effects
 * Called from: LandingView
 * Purpose: Creates depth and ambience
 */
const GlowOrb: React.FC<{ color: string; size: number; position: { x: string; y: string }; delay?: number }> = ({
  color,
  size,
  position,
  delay = 0,
}) => (
  <motion.div
    className="absolute rounded-full blur-3xl"
    style={{
      left: position.x,
      top: position.y,
      width: size,
      height: size,
      background: color,
      opacity: 0.4,
    }}
    animate={{
      scale: [1, 1.2, 1],
      opacity: [0.3, 0.5, 0.3],
    }}
    transition={{
      duration: 8,
      delay,
      repeat: Infinity,
      ease: 'easeInOut',
    }}
  />
);





/**
 * Function: AgentModeToggle - Premium toggle with holographic tooltips for Single/Multi-agent modes
 * Called from: WelcomeScreen
 * Props: agentMode (current mode), onModeChange (callback to toggle modes)
 * Purpose: Allows users to switch between single-agent and multi-agent execution with visual explanations
 */
const AgentModeToggle: React.FC<{
  agentMode: 'single' | 'multi';
  onModeChange: (mode: 'single' | 'multi') => void;
}> = ({ agentMode, onModeChange }) => {
  const [hoveredMode, setHoveredMode] = useState<'single' | 'multi' | null>(null);

  const singleAgentTraits = [
    { icon: '🔗', text: 'Linear Thought Process' },
    { icon: '🎯', text: 'SQL & Chart Generation' },
    { icon: '📰', text: 'News Sentiment Analysis' },
  ];

  const multiAgentTraits = [
    { icon: '⚡', text: 'Concurrent Run with Faster Response' },
    { icon: '🎭', text: 'Supervisor Orchestration' },
    { icon: '🤝', text: 'Specialist Handoffs' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3, duration: 0.5 }}
      className="relative flex flex-col items-center mb-10"
    >
      {/* Toggle Container */}
      <div
        className="relative flex items-center p-1.5 rounded-2xl"
        style={{
          background: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          backdropFilter: 'blur(10px)',
        }}
      >
        {/* Sliding Background Indicator */}
        <motion.div
          className="absolute top-1.5 bottom-1.5 rounded-xl"
          style={{
            background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.4) 0%, rgba(139, 92, 246, 0.4) 100%)',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            boxShadow: '0 0 20px rgba(59, 130, 246, 0.3)',
          }}
          initial={false}
          animate={{
            left: agentMode === 'single' ? '6px' : 'calc(50% + 2px)',
            width: 'calc(50% - 8px)',
          }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        />

        {/* Single Agent Button with hover wrapper */}
        <div
          className="relative"
          onMouseEnter={() => setHoveredMode('single')}
          onMouseLeave={() => setHoveredMode(null)}
        >
          <motion.button
            className="relative z-10 flex items-center gap-2 px-5 py-3 rounded-xl transition-colors"
            onClick={() => onModeChange('single')}
            whileTap={{ scale: 0.98 }}
          >
            <span className="text-xl">🧠</span>
            <span
              className="text-sm font-medium whitespace-nowrap"
              style={{ color: agentMode === 'single' ? '#fff' : 'rgba(255, 255, 255, 0.6)' }}
            >
              Single Agent
            </span>
          </motion.button>

          {/* Holographic Tooltip - Single Agent */}
          <AnimatePresence>
            {hoveredMode === 'single' && (
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className="absolute top-full mt-3 left-1/2 -translate-x-1/2 z-50"
                style={{
                  background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.9) 0%, rgba(139, 92, 246, 0.85) 100%)',
                  border: '1px solid rgba(59, 130, 246, 0.4)',
                  backdropFilter: 'blur(20px)',
                  borderRadius: '16px',
                  boxShadow: '0 0 40px rgba(59, 130, 246, 0.25), inset 0 0 60px rgba(59, 130, 246, 0.08)',
                  minWidth: '260px',
                }}
              >
                {/* Hologram Scan Line Effect */}
                <motion.div
                  className="absolute inset-x-0 h-px overflow-hidden rounded-2xl"
                  style={{
                    background: 'linear-gradient(90deg, transparent 0%, rgba(59, 130, 246, 0.6) 50%, transparent 100%)',
                  }}
                  animate={{ top: ['0%', '100%'] }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                />

                <div className="p-4 space-y-2.5">
                  {singleAgentTraits.map((trait, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.08 }}
                      className="flex items-center gap-3"
                    >
                      <span className="text-lg">{trait.icon}</span>
                      <span className="text-sm text-white font-medium">{trait.text}</span>
                    </motion.div>
                  ))}
                </div>

                {/* Corner Accents */}
                <div className="absolute top-0 left-0 w-3 h-3 border-t border-l rounded-tl-2xl" style={{ borderColor: 'rgba(59, 130, 246, 0.5)' }} />
                <div className="absolute top-0 right-0 w-3 h-3 border-t border-r rounded-tr-2xl" style={{ borderColor: 'rgba(59, 130, 246, 0.5)' }} />
                <div className="absolute bottom-0 left-0 w-3 h-3 border-b border-l rounded-bl-2xl" style={{ borderColor: 'rgba(59, 130, 246, 0.5)' }} />
                <div className="absolute bottom-0 right-0 w-3 h-3 border-b border-r rounded-br-2xl" style={{ borderColor: 'rgba(59, 130, 246, 0.5)' }} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Multi-Agent Button with hover wrapper */}
        <div
          className="relative"
          onMouseEnter={() => setHoveredMode('multi')}
          onMouseLeave={() => setHoveredMode(null)}
        >
          <motion.button
            className="relative z-10 flex items-center gap-2 px-5 py-3 rounded-xl transition-colors"
            onClick={() => onModeChange('multi')}
            whileTap={{ scale: 0.98 }}
          >
            <span className="text-xl">🌐</span>
            <span
              className="text-sm font-medium whitespace-nowrap"
              style={{ color: agentMode === 'multi' ? '#fff' : 'rgba(255, 255, 255, 0.6)' }}
            >
              Multi-Agent Run
            </span>
          </motion.button>

          {/* Holographic Tooltip - Multi-Agent */}
          <AnimatePresence>
            {hoveredMode === 'multi' && (
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className="absolute top-full mt-3 left-1/2 -translate-x-1/2 z-50"
                style={{
                  background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.9) 0%, rgba(139, 92, 246, 0.85) 100%)',
                  border: '1px solid rgba(245, 158, 11, 0.4)',
                  backdropFilter: 'blur(20px)',
                  borderRadius: '16px',
                  boxShadow: '0 0 40px rgba(245, 158, 11, 0.25), inset 0 0 60px rgba(245, 158, 11, 0.08)',
                  minWidth: '300px',
                }}
              >
                {/* Hologram Scan Line Effect */}
                <motion.div
                  className="absolute inset-x-0 h-px overflow-hidden rounded-2xl"
                  style={{
                    background: 'linear-gradient(90deg, transparent 0%, rgba(245, 158, 11, 0.6) 50%, transparent 100%)',
                  }}
                  animate={{ top: ['0%', '100%'] }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                />

                <div className="p-4 space-y-2.5">
                  {multiAgentTraits.map((trait, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.08 }}
                      className="flex items-center gap-3"
                    >
                      <span className="text-lg">{trait.icon}</span>
                      <span className="text-sm text-white font-medium">{trait.text}</span>
                    </motion.div>
                  ))}
                </div>

                {/* Corner Accents */}
                <div className="absolute top-0 left-0 w-3 h-3 border-t border-l rounded-tl-2xl" style={{ borderColor: 'rgba(245, 158, 11, 0.5)' }} />
                <div className="absolute top-0 right-0 w-3 h-3 border-t border-r rounded-tr-2xl" style={{ borderColor: 'rgba(245, 158, 11, 0.5)' }} />
                <div className="absolute bottom-0 left-0 w-3 h-3 border-b border-l rounded-bl-2xl" style={{ borderColor: 'rgba(245, 158, 11, 0.5)' }} />
                <div className="absolute bottom-0 right-0 w-3 h-3 border-b border-r rounded-br-2xl" style={{ borderColor: 'rgba(245, 158, 11, 0.5)' }} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
};

/**
 * Function: WelcomeScreen - Welcome view with premium styling and starter prompts
 * Called from: ConversationalAnalyticsPage when no messages exist
 * Invokes: onSuggestionClick callback to prefill chat input
 * Purpose: Immersive entry point with premium design and quick-start prompts (defaults to single agent)
 */
const WelcomeScreen: React.FC<{
  onSuggestionClick: (prompt: string) => void;
  agentMode: 'single' | 'multi';
  onModeChange: (mode: 'single' | 'multi') => void;
}> = ({ onSuggestionClick, agentMode, onModeChange }) => {
  const suggestions = [
    {
      icon: '✨',
      title: 'Project Showcase',
      description: 'See what I can do',
      prompt: 'Showcase the main capabilities of this analysis agent. What can you help me with?',
    },
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
  ];

  const features = [
    { icon: '📡', text: 'Real-time Streaming' },
    { icon: '🔧', text: 'Tool Orchestration' },
    { icon: '🎯', text: 'Skill-based Routing' },
    { icon: '⚡', text: 'Live Financial Data' },
    { icon: '🧠', text: 'Context-aware Logic' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, y: -20 }}
      className="relative flex flex-col items-center justify-center min-h-full px-6 py-12 overflow-hidden"
    >
      {/* Background Effects */}
      <div className="absolute inset-0 bg-gradient-to-b from-gray-900 via-gray-900 to-black" />
      <GlowOrb color="rgba(59, 130, 246, 0.3)" size={400} position={{ x: '10%', y: '20%' }} />
      <GlowOrb color="rgba(139, 92, 246, 0.25)" size={300} position={{ x: '70%', y: '60%' }} delay={2} />
      <GlowOrb color="rgba(245, 158, 11, 0.2)" size={250} position={{ x: '80%', y: '10%' }} delay={4} />
      <ParticleField />

      {/* Content */}
      <div className="relative z-10 max-w-4xl w-full mx-auto flex flex-col items-center">
        {/* Hero Section with Premium Heading */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="flex flex-col md:flex-row items-center justify-center gap-8 mb-8"
        >
          {/* Animated Logo */}
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5, type: 'spring' }}
            className="relative inline-block shrink-0"
          >
            <motion.div
              className="w-24 h-24 rounded-3xl mx-auto flex items-center justify-center text-5xl relative overflow-hidden"
              style={{
                background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.3) 0%, rgba(139, 92, 246, 0.3) 50%, rgba(245, 158, 11, 0.3) 100%)',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                boxShadow: '0 0 60px rgba(59, 130, 246, 0.3), inset 0 0 30px rgba(255, 255, 255, 0.1)',
              }}
              animate={{
                boxShadow: [
                  '0 0 60px rgba(59, 130, 246, 0.3), inset 0 0 30px rgba(255, 255, 255, 0.1)',
                  '0 0 80px rgba(139, 92, 246, 0.4), inset 0 0 40px rgba(255, 255, 255, 0.15)',
                  '0 0 60px rgba(59, 130, 246, 0.3), inset 0 0 30px rgba(255, 255, 255, 0.1)',
                ],
              }}
              transition={{ duration: 4, repeat: Infinity }}
            >
              ⚡
            </motion.div>
            {/* Orbiting Ring */}
            <motion.div
              className="absolute inset-0 rounded-3xl border border-blue-500/30"
              animate={{ rotate: 360 }}
              transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
              style={{ transformOrigin: 'center center' }}
            />
          </motion.div>

          {/* Title - Premium "Next Gen Analytics / Agent + Skills.md" style */}
          <div className="text-left md:text-left text-center">
            <h1 className="text-5xl md:text-7xl font-bold tracking-tight">
              <span className="bg-gradient-to-r from-white via-blue-100 to-white bg-clip-text text-transparent">
                Next Gen Analytics
              </span>
              <br />
              <span className="bg-gradient-to-r from-blue-400 via-purple-400 to-amber-400 bg-clip-text text-transparent text-4xl md:text-5xl block mt-2 pb-2">
                Agent + Skills.md
              </span>
            </h1>
          </div>
        </motion.div>

        {/* Rolling Feature Ticker (New Badge Style) */}
        <div className="w-full overflow-hidden mb-12 relative">
          <div className="absolute inset-y-0 left-0 w-20 bg-gradient-to-r from-gray-900 to-transparent z-20 pointer-events-none" />
          <div className="absolute inset-y-0 right-0 w-20 bg-gradient-to-l from-gray-900 to-transparent z-20 pointer-events-none" />
          <motion.div
            className="flex gap-4 whitespace-nowrap"
            animate={{ x: ["0%", "-25%"] }}
            transition={{
              duration: 20,
              repeat: Infinity,
              ease: "linear"
            }}
          >
            {/* Triplicated for endless loop illusion */}
            {[...features, ...features, ...features, ...features].map((f, i) => (
              <div
                key={i}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/5 backdrop-blur-sm"
              >
                <span className="text-xl">{f.icon}</span>
                <span className="text-sm font-medium text-gray-200">{f.text}</span>
              </div>
            ))}
          </motion.div>
        </div>

        {/* Agent Mode Toggle */}
        <AgentModeToggle agentMode={agentMode} onModeChange={onModeChange} />

        {/* Quick Start Suggestion Cards */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
          className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full"
        >
          {suggestions.map((s, idx) => (
            <motion.button
              key={idx}
              onClick={() => onSuggestionClick(s.prompt)}
              className="relative p-5 rounded-2xl text-left transition-all overflow-hidden group"
              style={{
                background: idx === 0 ? 'rgba(59, 130, 246, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                border: idx === 0 ? '1px solid rgba(59, 130, 246, 0.4)' : '1px solid rgba(255, 255, 255, 0.1)',
              }}
              whileHover={{
                background: 'rgba(59, 130, 246, 0.1)',
                borderColor: 'rgba(59, 130, 246, 0.3)',
                scale: 1.02,
              }}
              whileTap={{ scale: 0.98 }}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 + idx * 0.1 }}
            >
              <div className="flex items-start gap-4">
                <span className="text-3xl">{s.icon}</span>
                <div className="flex-1">
                  <h3 className={`text-base font-semibold mb-1 ${idx === 0 ? 'text-blue-300' : 'text-white'}`}>
                    {s.title}
                  </h3>
                  <p className="text-sm text-gray-400">
                    {s.description}
                  </p>
                </div>
                <motion.span
                  className="text-lg opacity-0 group-hover:opacity-100 transition-opacity text-blue-400"
                >
                  →
                </motion.span>
              </div>
            </motion.button>
          ))}
        </motion.div>
      </div>
    </motion.div>
  );
};

// Message type for chat history
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  thinkingSteps?: ThinkingStep[];
  chartConfig?: Record<string, unknown> | null;
  dataResult?: { rows: unknown[]; columns: string[]; sql?: string } | null;
  newsResult?: NewsResult | null;
  agentLabel?: string | null;
  htmlArtifact?: HtmlArtifact | null;
  skillInfo?: SkillInfo | null;
  // Process Data
  processNodes?: ProcessNode[];
  processEdges?: ProcessEdge[];
  activeAgent?: AgentInfo | null;
  debugLogs?: DebugLog[];
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
  const [agentMode, setAgentMode] = useState<'single' | 'multi'>('single'); // Default to single agent
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
          skillInfo,
          // Save process state to the message history
          processNodes: [...processNodes],
          processEdges: [...processEdges],
          activeAgent: activeAgent,
          debugLogs: [...debugLogs],
        },
      ]);
    }
  }, [isStreaming, content, thinkingSteps, chartConfig, dataResult, newsResult, htmlArtifact, activeAgentLabel, skillInfo, processNodes, processEdges, activeAgent, debugLogs]);

  /**
   * Function: handleSubmit - dispatches the typed prompt to the SSE pipeline
   * Called from: ChatInput onSubmit
   * Invokes: sendMessage with session/agent context and updates local message log
   * Purpose: Central guard preventing empty submissions or overlapping sends
   */
  const handleSubmit = () => {
    if (!inputValue.trim() || (isStreaming && !isPaused)) return;

    setMessages((prev) => [...prev, { role: 'user', content: inputValue }]);
    // Map frontend 'multi' mode to backend 'auto' for supervisor orchestration
    const backendMode = agentMode === 'multi' ? 'auto' : agentMode;
    sendMessage(inputValue, sessionId, backendMode);
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

  const handleNewChat = () => {
    setMessages([]);
    setInputValue('');
  };

  const showWelcome = messages.length === 0 && !isStreaming;

  // Responsive placeholder
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.matchMedia('(max-width: 768px)').matches);
    checkMobile(); // Initial check
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  return (
    <div
      className="flex flex-col h-full"
      style={{ backgroundColor: theme.colors.bg.primary }}
    >
      {/* Header - Always visible */}
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
              Next Gen Analytics
            </h1>
            <p
              className="text-xs"
              style={{
                background: 'linear-gradient(to right, rgb(96, 165, 250), rgb(167, 139, 250), rgb(251, 191, 36))',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              Agent + Skills.md
            </p>
          </div>
        </div>
        {messages.length > 0 && (
          <motion.button
            onClick={handleNewChat}
            className="text-xs px-3 py-1.5 rounded-lg transition-colors"
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              color: theme.colors.text.secondary,
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}
            whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.1)' }}
            whileTap={{ scale: 0.95 }}
          >
            New Chat
          </motion.button>
        )}
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
              agentMode={agentMode}
              onModeChange={setAgentMode}
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
                  skillInfo={msg.skillInfo}
                  processNodes={msg.processNodes}
                  processEdges={msg.processEdges}
                  activeAgent={msg.activeAgent}
                  agentMode={agentMode}
                  debugLogs={msg.debugLogs}
                />
              ))}

              {/* Streaming message */}
              {isStreaming && (content || chartConfig || dataResult || newsResult || htmlArtifact || processNodes.length > 0) && (
                <MessageBubble
                  role="assistant"
                  content={content}
                  chartConfig={chartConfig}
                  dataResult={dataResult}
                  newsResult={newsResult}
                  htmlArtifact={htmlArtifact}
                  isStreaming={true}
                  agentLabel={activeAgentLabel}
                  skillInfo={skillInfo}
                  processNodes={processNodes}
                  processEdges={processEdges}
                  activeAgent={activeAgent}
                  agentMode={agentMode}
                  debugLogs={debugLogs}
                  runId={runId}
                  permissionState={permissionState}
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
                        const resumeMode = agentMode === 'multi' ? 'auto' : agentMode;
                        sendMessage(lastUserMsg.content, sid, resumeMode);
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

      {/* Input area - Always visible */}
      <ChatInput
        value={inputValue}
        onChange={setInputValue}
        onSubmit={handleSubmit}
        onPause={pauseStream}
        onResume={resumeLast}
        isStreaming={isStreaming}
        isPaused={isPaused}
        placeholder={isMobile
          ? "Ask about NVDA, AMD, INTC..."
          : "Available tickers: NVDA, AMD, INTC, AVGO, QCOM, MU, TXN..."}
        suggestionsOverride={buildDynamicSuggestions()}
      />
    </div>
  );
};

export default ConversationalAnalyticsPage;
