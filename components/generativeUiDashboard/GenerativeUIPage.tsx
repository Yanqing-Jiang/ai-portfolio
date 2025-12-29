/**
 * Generative UI Project Page (2026) - Award-Winning Redesign
 *
 * Features:
 * - Split-screen: Dashboard (70%) + Chat (30%)
 * - Popup suggestion chips (not greyed hints)
 * - Debug panel with JSON export
 * - Premium glassmorphism + micro-animations
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
// Theme Tokens (Premium Rose/Amber)
// ============================================================================

const theme = {
    colors: {
        bg: {
            primary: '#0a0f1a',
            secondary: '#111827',
            tertiary: '#1a2332',
            elevated: '#1e293b',
        },
        accent: {
            primary: '#f43f5e',
            secondary: '#f59e0b',
            muted: 'rgba(244, 63, 94, 0.15)',
            glow: 'rgba(244, 63, 94, 0.4)',
        },
        text: {
            primary: '#f8fafc',
            secondary: '#94a3b8',
            muted: '#64748b',
        },
        border: {
            subtle: 'rgba(148, 163, 184, 0.1)',
            medium: 'rgba(148, 163, 184, 0.2)',
            accent: 'rgba(244, 63, 94, 0.3)',
        },
        status: {
            success: '#10b981',
            warning: '#f59e0b',
            error: '#ef4444',
            streaming: '#3b82f6',
        },
    },
    shadows: {
        glow: '0 0 30px rgba(244, 63, 94, 0.2)',
        card: '0 4px 20px rgba(0, 0, 0, 0.3)',
    },
};

// ============================================================================
// Suggestions - Using actual comp_financials tickers
// ============================================================================

const SUGGESTIONS = [
    {
        text: 'Why did NVDA drop recently?',
        icon: '📉',
        description: 'Price movement analysis with news'
    },
    {
        text: 'Compare AMD vs INTC revenue',
        icon: '📊',
        description: 'Revenue comparison chart'
    },
    {
        text: 'QCOM vs AVGO margins trend',
        icon: '💹',
        description: 'Margin analysis over time'
    },
    {
        text: 'Show MU quarterly earnings',
        icon: '📈',
        description: 'Quarterly KPIs and chart'
    },
    {
        text: 'TXN market position vs peers',
        icon: '🎯',
        description: 'Competitive landscape'
    },
];

// Available tickers for the database
const AVAILABLE_TICKERS = ['AMD', 'AVGO', 'INTC', 'MU', 'NVDA', 'QCOM', 'TXN'];

// ============================================================================
// Debug Panel Component
// ============================================================================

interface DebugPanelProps {
    isOpen: boolean;
    onClose: () => void;
    streamState: {
        messageCount: number;
        isConnected: boolean;
        isDone: boolean;
        error: string | null;
    };
    surface: unknown;
    dataModel: unknown;
    dashboardId: string | null;
}

function DebugPanel({ isOpen, onClose, streamState, surface, dataModel, dashboardId }: DebugPanelProps) {
    const [activeTab, setActiveTab] = useState<'surface' | 'data' | 'raw'>('surface');

    const debugData = {
        dashboardId,
        timestamp: new Date().toISOString(),
        streamState: {
            messageCount: streamState.messageCount,
            isConnected: streamState.isConnected,
            isDone: streamState.isDone,
            error: streamState.error,
        },
        surface,
        dataModel,
    };

    const handleDownload = () => {
        const blob = new Blob([JSON.stringify(debugData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `dashboard-debug-${dashboardId || 'unknown'}-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    if (!isOpen) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 flex items-center justify-center p-4"
                style={{ backgroundColor: 'rgba(0, 0, 0, 0.8)', backdropFilter: 'blur(8px)' }}
                onClick={onClose}
            >
                <motion.div
                    initial={{ opacity: 0, scale: 0.9, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.9, y: 20 }}
                    onClick={(e) => e.stopPropagation()}
                    className="w-full max-w-4xl max-h-[80vh] rounded-2xl overflow-hidden"
                    style={{
                        backgroundColor: theme.colors.bg.secondary,
                        border: `1px solid ${theme.colors.border.medium}`,
                        boxShadow: theme.shadows.card,
                    }}
                >
                    {/* Header */}
                    <div
                        className="flex items-center justify-between px-6 py-4 border-b"
                        style={{ borderColor: theme.colors.border.subtle }}
                    >
                        <div className="flex items-center gap-3">
                            <span className="text-xl">🔧</span>
                            <div>
                                <h2 className="text-lg font-bold" style={{ color: theme.colors.text.primary }}>
                                    Debug Panel
                                </h2>
                                <p className="text-xs" style={{ color: theme.colors.text.muted }}>
                                    A2UI Stream Inspector
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            <button
                                onClick={handleDownload}
                                className="px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-105"
                                style={{
                                    background: `linear-gradient(135deg, ${theme.colors.accent.primary}, ${theme.colors.accent.secondary})`,
                                    color: 'white',
                                }}
                            >
                                Download JSON
                            </button>
                            <button
                                onClick={onClose}
                                className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
                                style={{ backgroundColor: theme.colors.bg.tertiary, color: theme.colors.text.secondary }}
                            >
                                ✕
                            </button>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="flex gap-1 px-6 pt-4" style={{ borderBottom: `1px solid ${theme.colors.border.subtle}` }}>
                        {(['surface', 'data', 'raw'] as const).map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className="px-4 py-2 text-sm font-medium rounded-t-lg transition-colors"
                                style={{
                                    backgroundColor: activeTab === tab ? theme.colors.bg.tertiary : 'transparent',
                                    color: activeTab === tab ? theme.colors.text.primary : theme.colors.text.muted,
                                    borderBottom: activeTab === tab ? `2px solid ${theme.colors.accent.primary}` : 'none',
                                }}
                            >
                                {tab === 'surface' ? '🎨 Surface' : tab === 'data' ? '📊 Data Model' : '📄 Raw JSON'}
                            </button>
                        ))}
                    </div>

                    {/* Content */}
                    <div className="p-6 overflow-auto" style={{ maxHeight: 'calc(80vh - 180px)' }}>
                        <pre
                            className="text-xs font-mono p-4 rounded-lg overflow-auto"
                            style={{
                                backgroundColor: theme.colors.bg.primary,
                                color: theme.colors.text.secondary,
                                border: `1px solid ${theme.colors.border.subtle}`,
                            }}
                        >
                            {activeTab === 'surface' && JSON.stringify(surface, null, 2)}
                            {activeTab === 'data' && JSON.stringify(dataModel, null, 2)}
                            {activeTab === 'raw' && JSON.stringify(debugData, null, 2)}
                        </pre>
                    </div>

                    {/* Status Bar */}
                    <div
                        className="flex items-center justify-between px-6 py-3 text-xs"
                        style={{
                            backgroundColor: theme.colors.bg.tertiary,
                            borderTop: `1px solid ${theme.colors.border.subtle}`,
                            color: theme.colors.text.muted,
                        }}
                    >
                        <div className="flex items-center gap-4">
                            <span>Messages: {streamState.messageCount}</span>
                            <span>
                                Status:{' '}
                                <span style={{ color: streamState.isConnected ? theme.colors.status.streaming : theme.colors.status.success }}>
                                    {streamState.isConnected ? 'Streaming' : streamState.isDone ? 'Complete' : 'Idle'}
                                </span>
                            </span>
                        </div>
                        <span>Dashboard ID: {dashboardId || 'None'}</span>
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
}

// ============================================================================
// Suggestion Popup Component
// ============================================================================

interface SuggestionPopupProps {
    isVisible: boolean;
    onSelect: (text: string) => void;
    onClose: () => void;
}

function SuggestionPopup({ isVisible, onSelect, onClose }: SuggestionPopupProps) {
    return (
        <AnimatePresence>
            {isVisible && (
                <motion.div
                    initial={{ opacity: 0, y: 20, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 20, scale: 0.95 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                    className="absolute bottom-full left-0 right-0 mb-3 p-4 rounded-2xl"
                    style={{
                        backgroundColor: theme.colors.bg.secondary,
                        border: `1px solid ${theme.colors.border.medium}`,
                        boxShadow: theme.shadows.card,
                    }}
                >
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold" style={{ color: theme.colors.text.primary }}>
                            💡 Try asking about semiconductor stocks
                        </h3>
                        <button
                            onClick={onClose}
                            className="text-xs px-2 py-1 rounded"
                            style={{ color: theme.colors.text.muted }}
                        >
                            ✕
                        </button>
                    </div>

                    <div className="flex items-center gap-2 mb-3 flex-wrap">
                        <span className="text-xs" style={{ color: theme.colors.text.muted }}>Available:</span>
                        {AVAILABLE_TICKERS.map((ticker) => (
                            <span
                                key={ticker}
                                className="text-xs px-2 py-0.5 rounded font-mono"
                                style={{
                                    backgroundColor: theme.colors.accent.muted,
                                    color: theme.colors.accent.primary,
                                }}
                            >
                                {ticker}
                            </span>
                        ))}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {SUGGESTIONS.map((s, idx) => (
                            <motion.button
                                key={s.text}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: idx * 0.05 }}
                                onClick={() => onSelect(s.text)}
                                className="flex items-start gap-3 p-3 rounded-xl text-left transition-all group"
                                style={{
                                    backgroundColor: theme.colors.bg.tertiary,
                                    border: `1px solid ${theme.colors.border.subtle}`,
                                }}
                                whileHover={{
                                    backgroundColor: theme.colors.bg.elevated,
                                    borderColor: theme.colors.accent.primary + '50',
                                    scale: 1.02,
                                }}
                            >
                                <span className="text-xl flex-shrink-0">{s.icon}</span>
                                <div>
                                    <p className="text-sm font-medium" style={{ color: theme.colors.text.primary }}>
                                        {s.text}
                                    </p>
                                    <p className="text-xs mt-0.5" style={{ color: theme.colors.text.muted }}>
                                        {s.description}
                                    </p>
                                </div>
                            </motion.button>
                        ))}
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

// ============================================================================
// Main Page Component
// ============================================================================

export function GenerativeUIPage(): React.ReactElement {
    const [question, setQuestion] = useState('');
    const [dashboardId, setDashboardId] = useState<string | null>(null);
    const [isCreating, setIsCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [showDebugPanel, setShowDebugPanel] = useState(false);
    const [isFocused, setIsFocused] = useState(false);
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
        setShowSuggestions(false);

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
        setShowSuggestions(false);
        textareaRef.current?.focus();
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

    const getStatusColor = () => {
        if (streamState.isConnected) return theme.colors.status.streaming;
        if (streamState.isDone) return theme.colors.status.success;
        return theme.colors.text.muted;
    };

    const getStatusText = () => {
        if (streamState.isConnected) return 'Streaming';
        if (streamState.isDone) return 'Complete';
        if (isCreating) return 'Creating...';
        return 'Ready';
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

            <div className="generative-ui-page relative min-h-screen overflow-hidden" style={{ backgroundColor: theme.colors.bg.primary }}>
                {/* Ambient Background */}
                <div className="absolute inset-0 pointer-events-none overflow-hidden">
                    <div
                        className="absolute -top-1/2 -right-1/4 w-[800px] h-[800px] rounded-full opacity-20"
                        style={{
                            background: `radial-gradient(circle, ${theme.colors.accent.primary} 0%, transparent 70%)`,
                            filter: 'blur(120px)',
                        }}
                    />
                    <div
                        className="absolute -bottom-1/4 -left-1/4 w-[600px] h-[600px] rounded-full opacity-15"
                        style={{
                            background: `radial-gradient(circle, ${theme.colors.accent.secondary} 0%, transparent 70%)`,
                            filter: 'blur(100px)',
                        }}
                    />
                </div>

                {/* Header */}
                <header
                    className="relative z-20 border-b"
                    style={{
                        backgroundColor: theme.colors.bg.secondary + 'ee',
                        borderColor: theme.colors.border.subtle,
                        backdropFilter: 'blur(16px)',
                    }}
                >
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <Link
                                    to="/"
                                    className="flex items-center gap-2 transition-colors"
                                    style={{ color: theme.colors.text.muted }}
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                                    </svg>
                                    <span className="hidden sm:inline">Back</span>
                                </Link>

                                <div className="h-6 w-px" style={{ backgroundColor: theme.colors.border.medium }} />

                                <div className="flex items-center gap-3">
                                    <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `linear-gradient(135deg, ${theme.colors.accent.primary}, ${theme.colors.accent.secondary})` }}>
                                        <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                        </svg>
                                    </div>
                                    <div>
                                        <h1 className="text-lg font-bold" style={{ color: theme.colors.text.primary }}>
                                            Generative Financial Dashboard
                                        </h1>
                                        <p className="text-xs" style={{ color: theme.colors.text.muted }}>
                                            A2UI Protocol v0.8
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                {/* Debug Button */}
                                <button
                                    onClick={() => setShowDebugPanel(true)}
                                    className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all hover:scale-105"
                                    style={{
                                        backgroundColor: theme.colors.bg.tertiary,
                                        border: `1px solid ${theme.colors.border.subtle}`,
                                        color: theme.colors.text.secondary,
                                    }}
                                >
                                    <span>🔧</span>
                                    <span className="hidden sm:inline">Debug</span>
                                </button>

                                {/* Connection Status */}
                                <div
                                    className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium"
                                    style={{
                                        backgroundColor: theme.colors.bg.tertiary,
                                        border: `1px solid ${theme.colors.border.subtle}`,
                                    }}
                                >
                                    <motion.span
                                        className="w-2 h-2 rounded-full"
                                        animate={{ opacity: streamState.isConnected ? [1, 0.5, 1] : 1 }}
                                        transition={{ duration: 1, repeat: streamState.isConnected ? Infinity : 0 }}
                                        style={{ backgroundColor: getStatusColor() }}
                                    />
                                    <span style={{ color: theme.colors.text.secondary }}>{getStatusText()}</span>
                                </div>

                            </div>
                        </div>
                    </div>
                </header>

                {/* Main Content - Split Screen */}
                <div className="relative z-10 flex flex-col" style={{ height: 'calc(100vh - 72px)' }}>
                    {/* Dashboard Area (70%) */}
                    <div className="flex-1 overflow-hidden" style={{ minHeight: '55%' }}>
                        <div className="h-full p-4 sm:p-6">
                            <div
                                className="h-full rounded-2xl overflow-hidden relative"
                                style={{
                                    backgroundColor: theme.colors.bg.secondary + 'cc',
                                    border: `1px solid ${theme.colors.border.medium}`,
                                    backdropFilter: 'blur(16px)',
                                }}
                            >
                                {/* Streaming border animation */}
                                {streamState.isConnected && (
                                    <motion.div
                                        className="absolute inset-0 rounded-2xl pointer-events-none"
                                        animate={{ opacity: [0.3, 0.6, 0.3] }}
                                        transition={{ duration: 2, repeat: Infinity }}
                                        style={{
                                            border: `2px solid ${theme.colors.accent.primary}`,
                                            boxShadow: theme.shadows.glow,
                                        }}
                                    />
                                )}

                                <div className="h-full overflow-auto p-4 sm:p-6">
                                    {/* Empty State */}
                                    {!dashboardId && !streamState.isLoading && (
                                        <div className="h-full flex flex-col items-center justify-center text-center">
                                            <motion.div
                                                initial={{ scale: 0.9, opacity: 0 }}
                                                animate={{ scale: 1, opacity: 1 }}
                                                className="w-24 h-24 rounded-full flex items-center justify-center mb-6"
                                                style={{
                                                    background: `linear-gradient(135deg, ${theme.colors.accent.muted}, transparent)`,
                                                    border: `1px solid ${theme.colors.border.accent}`,
                                                }}
                                            >
                                                <span className="text-5xl">📊</span>
                                            </motion.div>
                                            <h2
                                                className="text-2xl font-bold mb-3"
                                                style={{ color: theme.colors.text.primary }}
                                            >
                                                Your Dashboard Will Appear Here
                                            </h2>
                                            <p style={{ color: theme.colors.text.muted }} className="max-w-md">
                                                Ask about{' '}
                                                <span style={{ color: theme.colors.accent.primary }}>
                                                    {AVAILABLE_TICKERS.join(', ')}
                                                </span>{' '}
                                                - the semiconductor companies in our database
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
                        <motion.div
                            className="absolute inset-0 rounded-full"
                            animate={{
                                backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'],
                            }}
                            transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
                            style={{
                                background: `linear-gradient(90deg, transparent 0%, ${theme.colors.accent.primary} 20%, ${theme.colors.accent.secondary} 50%, ${theme.colors.accent.primary} 80%, transparent 100%)`,
                                backgroundSize: '200% 100%',
                            }}
                        />
                    </div>

                    {/* Chat Input Area (30%) */}
                    <div
                        className="flex-shrink-0 p-4 sm:p-6"
                        style={{ minHeight: '200px', maxHeight: '45%' }}
                    >
                        <div
                            className="h-full rounded-2xl p-4 sm:p-6 flex flex-col relative"
                            style={{
                                backgroundColor: theme.colors.bg.secondary + 'cc',
                                border: `1px solid ${theme.colors.border.medium}`,
                                backdropFilter: 'blur(16px)',
                            }}
                        >
                            {/* Suggestion Popup */}
                            <SuggestionPopup
                                isVisible={showSuggestions && !question}
                                onSelect={handleSuggestion}
                                onClose={() => setShowSuggestions(false)}
                            />

                            {/* Input Row */}
                            <div className="flex gap-3 mb-4">
                                <div
                                    className="flex-1 relative rounded-xl transition-all duration-200"
                                    style={{
                                        backgroundColor: theme.colors.bg.tertiary,
                                        border: `1px solid ${isFocused ? theme.colors.accent.primary + '50' : theme.colors.border.medium}`,
                                        boxShadow: isFocused ? `0 0 0 3px ${theme.colors.accent.muted}` : 'none',
                                    }}
                                >
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
                                        onFocus={() => {
                                            setIsFocused(true);
                                            if (!question) setShowSuggestions(true);
                                        }}
                                        onBlur={() => {
                                            setIsFocused(false);
                                            setTimeout(() => setShowSuggestions(false), 200);
                                        }}
                                        placeholder="Ask about AMD, NVDA, INTC, QCOM, MU, AVGO, or TXN..."
                                        rows={1}
                                        className="w-full px-4 py-3 bg-transparent resize-none outline-none text-sm"
                                        style={{ color: theme.colors.text.primary, minHeight: '48px' }}
                                    />
                                </div>

                                <motion.button
                                    onClick={handleSubmit}
                                    disabled={isCreating || !question.trim()}
                                    className="px-6 py-3 rounded-xl font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                    style={{
                                        background: question.trim()
                                            ? `linear-gradient(135deg, ${theme.colors.accent.primary}, ${theme.colors.accent.secondary})`
                                            : theme.colors.bg.elevated,
                                        color: question.trim() ? 'white' : theme.colors.text.muted,
                                        boxShadow: question.trim() ? theme.shadows.glow : 'none',
                                    }}
                                    whileHover={question.trim() ? { scale: 1.05 } : {}}
                                    whileTap={question.trim() ? { scale: 0.95 } : {}}
                                >
                                    {isCreating ? (
                                        <span className="flex items-center gap-2">
                                            <motion.span
                                                className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
                                                animate={{ rotate: 360 }}
                                                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                                            />
                                            Creating...
                                        </span>
                                    ) : (
                                        'Generate'
                                    )}
                                </motion.button>

                                {dashboardId && (
                                    <button
                                        onClick={handleReset}
                                        className="px-4 py-3 rounded-xl font-medium transition-colors"
                                        style={{
                                            backgroundColor: theme.colors.bg.tertiary,
                                            border: `1px solid ${theme.colors.border.subtle}`,
                                            color: theme.colors.text.secondary,
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

                        </div>
                    </div>
                </div>

                {/* Debug Panel */}
                <DebugPanel
                    isOpen={showDebugPanel}
                    onClose={() => setShowDebugPanel(false)}
                    streamState={{
                        messageCount: streamState.surfaces.size,
                        isConnected: streamState.isConnected,
                        isDone: streamState.isDone,
                        error: streamState.error?.message ?? null,
                    }}
                    surface={surface}
                    dataModel={dataModel}
                    dashboardId={dashboardId}
                />
            </div>
        </>
    );
}

export default GenerativeUIPage;
