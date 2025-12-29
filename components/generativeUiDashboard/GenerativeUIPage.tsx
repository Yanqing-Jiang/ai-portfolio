/**
 * Generative UI Project Page (2026)
 *
 * Award-winning split-screen layout:
 * - Top: A2UI-rendered dashboard (70vh)
 * - Bottom: Chat input with suggestions (30vh)
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import { motion, AnimatePresence } from 'framer-motion';

// A2UI imports
import { useA2UIStream, useSurface } from './a2ui';
import { A2UISurface, A2UISurfaceLoading, A2UISurfaceError } from './renderer';

// ============================================================================
// Theme Tokens
// ============================================================================

const theme = {
    accent: {
        primary: '#f43f5e',
        secondary: '#f59e0b',
        muted: 'rgba(244, 63, 94, 0.2)',
    },
    glass: {
        bg: 'rgba(15, 23, 42, 0.85)',
        border: 'rgba(244, 63, 94, 0.25)',
        borderHover: 'rgba(244, 63, 94, 0.5)',
    },
    text: {
        primary: '#f8fafc',
        secondary: '#94a3b8',
        muted: '#64748b',
    },
};

// ============================================================================
// Suggestion Pills
// ============================================================================

const SUGGESTIONS = [
    { text: 'Why did NVDA drop on Dec 18?', icon: '📉' },
    { text: 'Compare AAPL vs MSFT margins', icon: '📊' },
    { text: 'Show semiconductor correlation', icon: '🔗' },
    { text: 'TSLA quarterly revenue trend', icon: '📈' },
];

// ============================================================================
// Main Page Component
// ============================================================================

export function GenerativeUIPage(): React.ReactElement {
    const [question, setQuestion] = useState('');
    const [dashboardId, setDashboardId] = useState<string | null>(null);
    const [isCreating, setIsCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // A2UI stream state
    const streamUrl = dashboardId ? `/api/dash/${dashboardId}/stream` : null;
    const [streamState, streamActions] = useA2UIStream(streamUrl, {
        autoConnect: true,
        dashboardId: dashboardId || undefined,
        apiBaseUrl: '/api/dash',
    });

    // Get surface data
    const surfaceId = 'dashboard_main';
    const { surface, dataModel } = useSurface(streamState, surfaceId);

    // Auto-resize textarea
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        }
    }, [question]);

    // Handle dashboard creation
    const handleSubmit = useCallback(async () => {
        if (!question.trim() || isCreating) return;

        setIsCreating(true);
        setError(null);

        try {
            const response = await fetch('/api/dash/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: question.trim() }),
            });

            if (!response.ok) {
                throw new Error(`Failed to create dashboard: ${response.statusText}`);
            }

            const data = await response.json();
            setDashboardId(data.dashboard_id);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setIsCreating(false);
        }
    }, [question, isCreating]);

    // Handle suggestion click
    const handleSuggestion = (text: string) => {
        setQuestion(text);
        if (textareaRef.current) {
            textareaRef.current.focus();
        }
    };

    // Handle user actions from dashboard
    const handleAction = useCallback(
        async (actionName: string, context: Record<string, unknown>) => {
            if (!dashboardId) return;

            try {
                await streamActions.sendAction({
                    name: actionName,
                    surfaceId,
                    sourceComponentId: 'unknown',
                    timestamp: new Date().toISOString(),
                    context,
                });
            } catch (err) {
                console.error('Action failed:', err);
            }
        },
        [dashboardId, streamActions]
    );

    // Reset to create new dashboard
    const handleReset = () => {
        setDashboardId(null);
        setQuestion('');
        setError(null);
        streamActions.close();
    };

    return (
        <>
            <Helmet>
                <title>Generative Financial Dashboard | A2UI Protocol</title>
                <meta
                    name="description"
                    content="Ask a question and watch AI generate a custom financial dashboard in real-time using the A2UI protocol."
                />
            </Helmet>

            <div className="generative-ui-page relative min-h-screen bg-slate-950 overflow-hidden">
                {/* Ambient Background */}
                <div className="absolute inset-0 pointer-events-none overflow-hidden">
                    <div
                        className="absolute -top-1/2 -right-1/4 w-[800px] h-[800px] rounded-full opacity-20"
                        style={{
                            background: `radial-gradient(circle, ${theme.accent.primary} 0%, transparent 70%)`,
                            filter: 'blur(120px)',
                        }}
                    />
                    <div
                        className="absolute -bottom-1/4 -left-1/4 w-[600px] h-[600px] rounded-full opacity-15"
                        style={{
                            background: `radial-gradient(circle, ${theme.accent.secondary} 0%, transparent 70%)`,
                            filter: 'blur(100px)',
                        }}
                    />
                </div>

                {/* Header */}
                <header
                    className="relative z-20 border-b"
                    style={{
                        backgroundColor: theme.glass.bg,
                        borderColor: theme.glass.border,
                        backdropFilter: 'blur(16px)',
                    }}
                >
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <Link
                                    to="/"
                                    className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                                    </svg>
                                    <span className="hidden sm:inline">Back</span>
                                </Link>

                                <div className="h-6 w-px bg-slate-700" />

                                <div className="flex items-center gap-3">
                                    <span className="text-2xl">✨</span>
                                    <div>
                                        <h1 className="text-lg font-bold text-white">Generative Financial Dashboard</h1>
                                        <p className="text-xs text-slate-400">A2UI Protocol v0.8</p>
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                {/* Connection Status */}
                                <div
                                    className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium"
                                    style={{
                                        backgroundColor: theme.glass.bg,
                                        border: `1px solid ${theme.glass.border}`,
                                    }}
                                >
                                    <span
                                        className="w-2 h-2 rounded-full animate-pulse"
                                        style={{
                                            backgroundColor: streamState.isConnected
                                                ? '#22c55e'
                                                : streamState.isDone
                                                    ? '#f59e0b'
                                                    : '#64748b',
                                        }}
                                    />
                                    <span className="text-slate-300">
                                        {streamState.isConnected ? 'Streaming' : streamState.isDone ? 'Complete' : 'Ready'}
                                    </span>
                                </div>

                                {/* Year Badge */}
                                <span
                                    className="px-3 py-1.5 rounded-full text-xs font-bold"
                                    style={{
                                        background: `linear-gradient(135deg, ${theme.accent.primary}, ${theme.accent.secondary})`,
                                        color: 'white',
                                    }}
                                >
                                    2026
                                </span>
                            </div>
                        </div>
                    </div>
                </header>

                {/* Main Content - Split Screen */}
                <div className="relative z-10 flex flex-col" style={{ height: 'calc(100vh - 72px)' }}>
                    {/* Dashboard Area (70%) */}
                    <div className="flex-1 overflow-hidden" style={{ minHeight: '60%' }}>
                        <div className="h-full p-4 sm:p-6">
                            <div
                                className="h-full rounded-2xl overflow-hidden relative"
                                style={{
                                    backgroundColor: theme.glass.bg,
                                    border: `1px solid ${theme.glass.border}`,
                                    backdropFilter: 'blur(16px)',
                                }}
                            >
                                {/* Streaming border animation */}
                                {streamState.isConnected && (
                                    <div
                                        className="absolute inset-0 rounded-2xl pointer-events-none"
                                        style={{
                                            background: `linear-gradient(90deg, transparent, ${theme.accent.primary}40, transparent)`,
                                            backgroundSize: '200% 100%',
                                            animation: 'shimmer 2s ease-in-out infinite',
                                        }}
                                    />
                                )}

                                <div className="h-full overflow-auto p-4 sm:p-6">
                                    {/* Empty State */}
                                    {!dashboardId && !streamState.isLoading && (
                                        <div className="h-full flex flex-col items-center justify-center text-center">
                                            <div
                                                className="w-24 h-24 rounded-full flex items-center justify-center mb-6"
                                                style={{
                                                    background: `linear-gradient(135deg, ${theme.accent.muted}, transparent)`,
                                                    border: `1px solid ${theme.glass.border}`,
                                                }}
                                            >
                                                <span className="text-5xl">📊</span>
                                            </div>
                                            <h2 className="text-2xl font-bold text-white mb-3">
                                                Your Dashboard Will Appear Here
                                            </h2>
                                            <p className="text-slate-400 max-w-md">
                                                Ask a question below and watch as AI generates a custom financial dashboard
                                                with charts, KPIs, and insights in real-time.
                                            </p>
                                        </div>
                                    )}

                                    {/* Loading State */}
                                    {dashboardId && streamState.isLoading && !surface?.root && (
                                        <A2UISurfaceLoading />
                                    )}

                                    {/* Error State */}
                                    {streamState.error && !surface?.root && (
                                        <A2UISurfaceError error={streamState.error} onRetry={streamActions.reconnect} />
                                    )}

                                    {/* A2UI Surface */}
                                    {surface?.root && (
                                        <A2UISurface
                                            surface={surface}
                                            dataModel={dataModel}
                                            onAction={handleAction}
                                        />
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Animated Divider */}
                    <div className="relative h-1 mx-6">
                        <div
                            className="absolute inset-0 rounded-full"
                            style={{
                                background: `linear-gradient(90deg, transparent 0%, ${theme.accent.primary} 20%, ${theme.accent.secondary} 50%, ${theme.accent.primary} 80%, transparent 100%)`,
                                backgroundSize: '200% 100%',
                                animation: 'gradient-shift 3s ease infinite',
                            }}
                        />
                    </div>

                    {/* Chat Input Area (30%) */}
                    <div
                        className="flex-shrink-0 p-4 sm:p-6"
                        style={{ minHeight: '200px', maxHeight: '40%' }}
                    >
                        <div
                            className="h-full rounded-2xl p-4 sm:p-6 flex flex-col"
                            style={{
                                backgroundColor: theme.glass.bg,
                                border: `1px solid ${theme.glass.border}`,
                                backdropFilter: 'blur(16px)',
                            }}
                        >
                            {/* Input Row */}
                            <div className="flex gap-3 mb-4">
                                <div className="flex-1 relative">
                                    <textarea
                                        ref={textareaRef}
                                        value={question}
                                        onChange={(e) => setQuestion(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && !e.shiftKey) {
                                                e.preventDefault();
                                                handleSubmit();
                                            }
                                        }}
                                        placeholder="Ask about any stock... (e.g., Why did NVDA drop on Dec 18?)"
                                        rows={1}
                                        className="w-full px-4 py-3 rounded-xl resize-none text-white placeholder-slate-500 focus:outline-none transition-all"
                                        style={{
                                            backgroundColor: 'rgba(30, 41, 59, 0.8)',
                                            border: `1px solid ${theme.glass.border}`,
                                        }}
                                    />
                                </div>

                                <button
                                    onClick={handleSubmit}
                                    disabled={isCreating || !question.trim()}
                                    className="px-6 py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                    style={{
                                        background: `linear-gradient(135deg, ${theme.accent.primary}, ${theme.accent.secondary})`,
                                        boxShadow: `0 4px 20px ${theme.accent.muted}`,
                                    }}
                                >
                                    {isCreating ? (
                                        <span className="flex items-center gap-2">
                                            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                            Creating...
                                        </span>
                                    ) : (
                                        'Generate'
                                    )}
                                </button>

                                {dashboardId && (
                                    <button
                                        onClick={handleReset}
                                        className="px-4 py-3 rounded-xl font-medium text-slate-400 hover:text-white transition-colors"
                                        style={{
                                            backgroundColor: 'rgba(30, 41, 59, 0.8)',
                                            border: `1px solid ${theme.glass.border}`,
                                        }}
                                    >
                                        Clear
                                    </button>
                                )}
                            </div>

                            {/* Error Message */}
                            <AnimatePresence>
                                {error && (
                                    <motion.div
                                        initial={{ opacity: 0, y: -10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, y: -10 }}
                                        className="mb-4 px-4 py-2 rounded-lg text-sm"
                                        style={{
                                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                            border: '1px solid rgba(239, 68, 68, 0.3)',
                                            color: '#f87171',
                                        }}
                                    >
                                        {error}
                                    </motion.div>
                                )}
                            </AnimatePresence>

                            {/* Suggestions */}
                            <div className="flex flex-wrap gap-2 mt-auto">
                                <span className="text-xs text-slate-500 mr-2">Try:</span>
                                {SUGGESTIONS.map((s) => (
                                    <button
                                        key={s.text}
                                        onClick={() => handleSuggestion(s.text)}
                                        className="group flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all hover:scale-105"
                                        style={{
                                            backgroundColor: 'rgba(30, 41, 59, 0.8)',
                                            border: `1px solid ${theme.glass.border}`,
                                            color: theme.text.secondary,
                                        }}
                                    >
                                        <span>{s.icon}</span>
                                        <span className="group-hover:text-white transition-colors">{s.text}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* CSS Keyframes */}
                <style>{`
          @keyframes shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
          }
          @keyframes gradient-shift {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
          }
        `}</style>
            </div>
        </>
    );
}

export default GenerativeUIPage;
