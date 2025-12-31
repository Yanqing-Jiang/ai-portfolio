// --- Function/Class Map ---
// Component: UnifiedHeader
//   Role: Display streaming status and dashboard-level actions.
//   Called from: components/generativeUiDashboard/GenerativeUIPage.tsx
//   Invokes: onDebugToggle, onReset callbacks
//   Why: Keeps stream state visible and actions accessible.
// Component: SuggestionPopup
//   Role: Render quick-start suggestion cards for common queries.
//   Called from: components/generativeUiDashboard/GenerativeUIPage.tsx
//   Invokes: onSelect callback
//   Why: Helps users discover example prompts quickly.
// Component: GenerativeUIPage
//   Role: Orchestrate A2UI streaming, clarifications, and dashboard layout.
//   Called from: App routing
//   Invokes: useA2UIStream, useSurface, ClarificationOverlay, FollowUpSuggestions
//   Why: Main A2UI experience container for the portfolio.
// --- End Function/Class Map ---
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
import { ClarificationOverlay, type ClarificationRequest } from './ClarificationOverlay';
import { FollowUpSuggestions, type FollowUpSuggestion } from './FollowUpSuggestions';
import { SkillHeaderBadge, type SkillInfo } from './SkillHeaderBadge';

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

const ICONS = {
    suggestions: {
        price: 'PRICE',
        revenue: 'REV',
        margins: 'MARG',
        earnings: 'EARN',
        position: 'PEER',
    },
    header: {
        debug: 'DBG',
        reset: 'NEW',
    },
    prompt: {
        tip: 'TIP',
        close: 'x',
    },
    emptyState: 'CHART',
    followUps: {
        deep: 'DEEP',
        peer: 'PEER',
    },
    events: {
        skillSelected: 'SKL',
        streamStarted: 'STR',
        dataReceived: 'DATA',
        layoutUpdated: 'LAY',
        streamComplete: 'DONE',
        error: 'ERR',
        default: '...',
    },
};

// ============================================================================
// Suggestions - Using actual comp_financials tickers
// ============================================================================

const SUGGESTIONS = [
    {
        text: 'Why did NVDA drop recently?',
        icon: ICONS.suggestions.price,
        description: 'Price movement analysis with news'
    },
    {
        text: 'Compare AMD vs INTC revenue',
        icon: ICONS.suggestions.revenue,
        description: 'Revenue comparison chart'
    },
    {
        text: 'QCOM vs AVGO margins trend',
        icon: ICONS.suggestions.margins,
        description: 'Margin analysis over time'
    },
    {
        text: 'Show MU quarterly earnings',
        icon: ICONS.suggestions.earnings,
        description: 'Quarterly KPIs and chart'
    },
    {
        text: 'TXN market position vs peers',
        icon: ICONS.suggestions.position,
        description: 'Competitive landscape'
    },
];

// Available tickers for the database
const AVAILABLE_TICKERS = ['AMD', 'AVGO', 'INTC', 'MU', 'NVDA', 'QCOM', 'TXN'];

// ============================================================================
// Debug Panel Component
// ============================================================================

// ============================================================================
// Unified Header & Status Component
// ============================================================================

interface UnifiedHeaderProps {
    dashboardId: string | null;
    streamState: {
        messageCount: number;
        isConnected: boolean;
        isDone: boolean;
        error: string | null;
        isLoading?: boolean;
    };
    onDebugToggle: () => void;
    onReset: () => void;
}

function UnifiedHeader({ dashboardId, streamState, onDebugToggle, onReset }: UnifiedHeaderProps) {
    const isStreaming = streamState.isConnected;
    const isComplete = streamState.isDone;

    return (
        <div className="flex items-center gap-4">
            {/* Status Indicator */}
            <div
                className="flex items-center gap-3 px-4 py-2 rounded-full border transition-all"
                style={{
                    backgroundColor: theme.colors.bg.tertiary,
                    borderColor: isStreaming ? theme.colors.accent.primary + '50' : theme.colors.border.subtle,
                    boxShadow: isStreaming ? `0 0 15px ${theme.colors.accent.glow}` : 'none'
                }}
            >
                <div className="relative">
                    <motion.div
                        className="w-2.5 h-2.5 rounded-full"
                        animate={{
                            scale: isStreaming ? [1, 1.4, 1] : 1,
                            opacity: isStreaming ? [1, 0.6, 1] : 1
                        }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                        style={{
                            backgroundColor: isStreaming
                                ? theme.colors.status.streaming
                                : (isComplete ? theme.colors.status.success : theme.colors.text.muted)
                        }}
                    />
                </div>
                <div className="flex flex-col">
                    <span className="text-[10px] uppercase tracking-widest font-bold" style={{ color: theme.colors.text.muted }}>
                        System Status
                    </span>
                    <span className="text-xs font-semibold" style={{ color: theme.colors.text.primary }}>
                        {isStreaming ? 'AI Analysis Streaming...' : (isComplete ? 'Analysis Complete' : 'A2UI Ready')}
                    </span>
                </div>
            </div>

            <div className="h-8 w-px" style={{ backgroundColor: theme.colors.border.medium }} />

            {/* Actions */}
            <div className="flex items-center gap-2">
                <button
                    onClick={onDebugToggle}
                    className="p-2 rounded-lg transition-all hover:bg-white/5 active:scale-95"
                    title="Toggle Debug Inspector"
                    style={{ color: theme.colors.text.secondary }}
                >
                    <span className="text-lg">{ICONS.header.debug}</span>
                </button>

                {dashboardId && (
                    <button
                        onClick={onReset}
                        className="p-2 rounded-lg transition-all hover:bg-white/5 active:scale-95"
                        title="Start New Analysis"
                        style={{ color: theme.colors.text.secondary }}
                    >
                        <span className="text-lg">{ICONS.header.reset}</span>
                    </button>
                )}
            </div>
        </div>
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
                             <span className="mr-2">{ICONS.prompt.tip}</span>
                             Try asking about semiconductor stocks
                        </h3>
                        <button
                            onClick={onClose}
                            className="text-xs px-2 py-1 rounded"
                            style={{ color: theme.colors.text.muted }}
                        >
                            {ICONS.prompt.close}
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

    // Clarification and follow-up state
    const [clarificationRequest, setClarificationRequest] = useState<ClarificationRequest | null>(null);
    const [followUpSuggestions, setFollowUpSuggestions] = useState<FollowUpSuggestion[]>([]);
    const [activeSkill, setActiveSkill] = useState<SkillInfo | null>(null);

    // Audit trail for debug panel - tracks execution timeline
    interface AuditEvent {
        id: string;
        type: 'skill_selected' | 'stream_started' | 'data_received' | 'layout_updated' | 'stream_complete' | 'error';
        label: string;
        timestamp: Date;
        details?: string;
    }
    const [auditTrail, setAuditTrail] = useState<AuditEvent[]>([]);

    // Add audit event helper
    const addAuditEvent = useCallback((type: AuditEvent['type'], label: string, details?: string) => {
        setAuditTrail((prev) => [
            ...prev,
            { id: `${Date.now()}`, type, label, timestamp: new Date(), details },
        ]);
    }, []);

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
    const handleSubmit = useCallback(async (overrideQuestion?: string) => {
        const nextQuestion = (overrideQuestion ?? question).trim();
        if (!nextQuestion || isCreating) return;

        setIsCreating(true);
        setError(null);
        setShowSuggestions(false);

        try {
            const response = await fetch('/api/dash/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: nextQuestion }),
            });

            if (!response.ok) {
                throw new Error(`Failed to create dashboard: ${response.statusText}`);
            }

            const data = await response.json();
            setDashboardId(data.dashboard_id);
            setQuestion(nextQuestion);
            addAuditEvent('stream_started', 'Dashboard created', `ID: ${data.dashboard_id}`);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
            addAuditEvent('error', 'Creation failed', err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setIsCreating(false);
        }
    }, [question, isCreating, addAuditEvent]);

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
        setClarificationRequest(null);
        setFollowUpSuggestions([]);
        setActiveSkill(null);
        streamActions.close();
    };

    // Fetch skill info when dashboard is created
    useEffect(() => {
        if (dashboardId && !activeSkill) {
            const fetchSkillInfo = async () => {
                try {
                    const response = await fetch(`/api/dash/${dashboardId}/spec`);
                    if (response.ok) {
                        const data = await response.json();
                        if (data.plan?.skill_id) {
                            setActiveSkill({
                                id: data.plan.skill_id,
                                name: data.plan.skill_id.replace('a2ui_', '').replace(/_/g, ' '),
                            });
                            addAuditEvent('skill_selected', 'Skill selected', data.plan.skill_id);
                        }
                    }
                } catch (err) {
                    console.error('Failed to fetch skill info:', err);
                }
            };
            fetchSkillInfo();
        }
    }, [dashboardId, activeSkill, addAuditEvent]);

    // Convert backend clarification to frontend format when received
    useEffect(() => {
        if (streamState.pendingClarification && !clarificationRequest) {
            const backend = streamState.pendingClarification;
            // Convert to frontend ClarificationRequest format
            const firstField = backend.fields[0];
            if (firstField) {
                const converted: ClarificationRequest = {
                    id: backend.request_id,
                    fieldId: firstField.field_id,
                    type: firstField.input_type === 'multi_choice' ? 'multi_choice'
                        : firstField.input_type === 'freeform' ? 'freeform'
                            : 'single_choice',
                    prompt: backend.subtitle || firstField.label,
                    options: firstField.options?.map((o) => ({
                        label: o.label,
                        value: o.id,
                        description: o.description,
                    })),
                    maxSelections: firstField.input_type === 'multi_choice' ? firstField.options?.length : undefined,
                    placeholder: firstField.placeholder,
                    targetComponentId: backend.target_component_id,
                };
                setClarificationRequest(converted);
            }
        }
    }, [streamState.pendingClarification, clarificationRequest]);

    // Handle clarification response
    const handleClarificationSubmit = useCallback(
        async (requestId: string, response: string | string[]) => {
            setClarificationRequest(null);
            streamActions.clearClarification();
            const fieldId = clarificationRequest?.fieldId || 'response';

            // Send response to backend
            if (dashboardId) {
                try {
                    await fetch(`/api/dash/${dashboardId}/clarification`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            request_id: requestId,
                            values: { [fieldId]: response },
                            skipped: false,
                        }),
                    });
                } catch (err) {
                    console.error('Failed to submit clarification:', err);
                }
            }
        },
        [dashboardId, streamActions, clarificationRequest]
    );

    const handleClarificationDismiss = useCallback((_requestId: string) => {
        setClarificationRequest(null);
        streamActions.clearClarification();
    }, [streamActions]);

    // Handle follow-up suggestion click
    const handleFollowUpSelect = useCallback(
        (suggestion: FollowUpSuggestion) => {
            setQuestion(suggestion.query);
            setFollowUpSuggestions([]);
            // Auto-submit the follow-up
            handleSubmit(suggestion.query);
        },
        [handleSubmit]
    );

    // Track stream completion
    useEffect(() => {
        if (streamState.isDone && !auditTrail.some((e) => e.type === 'stream_complete')) {
            addAuditEvent('stream_complete', 'Stream completed', `${streamState.surfaces.size} surfaces rendered`);
        }
    }, [streamState.isDone, streamState.surfaces.size, auditTrail, addAuditEvent]);

    // Track layout updates when surface changes
    useEffect(() => {
        if (surface?.root && !auditTrail.some((e) => e.type === 'layout_updated')) {
            addAuditEvent('layout_updated', 'Layout rendered', surfaceId);
        }
    }, [surface?.root, surfaceId, auditTrail, addAuditEvent]);

    // Generate follow-up suggestions when dashboard completes via backend API
    useEffect(() => {
        if (streamState.isDone && surface?.root && followUpSuggestions.length === 0 && dashboardId) {
            const fetchFollowUps = async () => {
                try {
                    const response = await fetch(`/api/dash/${dashboardId}/follow-ups`);
                    if (response.ok) {
                        const data = await response.json();
                        if (data.suggestions && Array.isArray(data.suggestions)) {
                            setFollowUpSuggestions(data.suggestions);
                        }
                    }
                } catch (err) {
                    console.error('Failed to fetch follow-up suggestions:', err);
                    // Fall back to basic suggestions
                    setFollowUpSuggestions([
                        { id: '1', label: 'Deeper analysis', query: 'Explain the key drivers', icon: ICONS.followUps.deep },
                        { id: '2', label: 'Compare peers', query: 'Compare to industry peers', icon: ICONS.followUps.peer },
                    ]);
                }
            };

            // Small delay to let the dashboard render
            const timer = setTimeout(fetchFollowUps, 500);
            return () => clearTimeout(timer);
        }
    }, [streamState.isDone, surface?.root, dashboardId, followUpSuggestions.length]);

    // Unified Debug Panel with Audit Trail
    const renderDebugPanel = () => {
        if (!showDebugPanel) return null;

        const getEventIcon = (type: AuditEvent['type']) => {
            switch (type) {
                case 'skill_selected': return ICONS.events.skillSelected;
                case 'stream_started': return ICONS.events.streamStarted;
                case 'data_received': return ICONS.events.dataReceived;
                case 'layout_updated': return ICONS.events.layoutUpdated;
                case 'stream_complete': return ICONS.events.streamComplete;
                case 'error': return ICONS.events.error;
                default: return ICONS.events.default;
            }
        };

        const getEventColor = (type: AuditEvent['type']) => {
            switch (type) {
                case 'skill_selected': return '#f59e0b';
                case 'stream_started': return '#3b82f6';
                case 'data_received': return '#10b981';
                case 'layout_updated': return '#8b5cf6';
                case 'stream_complete': return '#22c55e';
                case 'error': return '#ef4444';
                default: return '#94a3b8';
            }
        };

        return (
            <AnimatePresence>
                <div
                    className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
                    style={{ backgroundColor: 'rgba(0, 0, 0, 0.4)', backdropFilter: 'blur(4px)' }}
                    onClick={() => setShowDebugPanel(false)}
                >
                    <motion.div
                        initial={{ opacity: 0, y: 50 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 50 }}
                        onClick={(e) => e.stopPropagation()}
                        className="w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-2xl overflow-hidden shadow-2xl"
                    >
                        <div className="p-4 border-b border-slate-800 flex justify-between items-center">
                            <h3 className="font-bold text-white">Stream Inspector</h3>
                            <button onClick={() => setShowDebugPanel(false)} className="text-slate-400">{ICONS.prompt.close}</button>
                        </div>
                        <div className="p-4 max-h-[60vh] overflow-auto">
                            {/* Stats Grid */}
                            <div className="grid grid-cols-3 gap-3 mb-4">
                                <div className="p-3 bg-slate-800 rounded-xl">
                                    <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">Messages</p>
                                    <p className="text-xl text-white font-mono">{streamState.surfaces.size}</p>
                                </div>
                                <div className="p-3 bg-slate-800 rounded-xl">
                                    <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">Skill</p>
                                    <p className="text-sm text-amber-400 font-mono truncate">{activeSkill?.id || 'pending'}</p>
                                </div>
                                <div className="p-3 bg-slate-800 rounded-xl">
                                    <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">Status</p>
                                    <p className="text-sm text-white font-mono">{streamState.connectionStatus}</p>
                                </div>
                            </div>

                            {/* Audit Trail Timeline */}
                            <div className="mb-4">
                                <h4 className="text-xs uppercase text-slate-500 font-bold mb-2">Execution Timeline</h4>
                                <div className="bg-black/30 rounded-xl p-3 space-y-2 max-h-40 overflow-auto">
                                    {auditTrail.length === 0 ? (
                                        <p className="text-xs text-slate-500 italic">No events yet...</p>
                                    ) : (
                                        auditTrail.map((event) => (
                                            <motion.div
                                                key={event.id}
                                                initial={{ opacity: 0, x: -10 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                className="flex items-start gap-2"
                                            >
                                                <span className="text-sm" style={{ color: getEventColor(event.type) }}>
                                                    {getEventIcon(event.type)}
                                                </span>
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-xs text-white truncate">{event.label}</p>
                                                    {event.details && (
                                                        <p className="text-[10px] text-slate-500 truncate">{event.details}</p>
                                                    )}
                                                </div>
                                                <span className="text-[10px] text-slate-600 font-mono">
                                                    {event.timestamp.toLocaleTimeString()}
                                                </span>
                                            </motion.div>
                                        ))
                                    )}
                                </div>
                            </div>

                            {/* Data Model JSON */}
                            <h4 className="text-xs uppercase text-slate-500 font-bold mb-2">Data Model</h4>
                            <pre className="text-[10px] font-mono bg-black/50 p-4 rounded-xl text-slate-300 overflow-auto max-h-40">
                                {JSON.stringify(dataModel, null, 2)}
                            </pre>
                        </div>
                    </motion.div>
                </div>
            </AnimatePresence>
        );
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
                                <UnifiedHeader
                                    dashboardId={dashboardId}
                                    streamState={{
                                        messageCount: streamState.surfaces.size,
                                        isConnected: streamState.isConnected,
                                        isDone: streamState.isDone,
                                        error: streamState.error?.message ?? null,
                                        isLoading: isCreating
                                    }}
                                    onDebugToggle={() => setShowDebugPanel(!showDebugPanel)}
                                    onReset={handleReset}
                                />
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
                                                <span className="text-5xl">{ICONS.emptyState}</span>
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
                                        <>
                                            {/* Skill Header Badge */}
                                            <SkillHeaderBadge
                                                skill={activeSkill}
                                                isLoading={streamState.isLoading && !activeSkill}
                                            />

                                            <A2UISurface
                                                surface={surface}
                                                dataModel={dataModel}
                                                onAction={handleAction}
                                            />

                                            {/* Follow-up Suggestions */}
                                            {streamState.isDone && followUpSuggestions.length > 0 && (
                                                <div className="mt-4">
                                                    <FollowUpSuggestions
                                                        suggestions={followUpSuggestions}
                                                        onSelect={handleFollowUpSelect}
                                                    />
                                                </div>
                                            )}
                                        </>
                                    )}

                                    {/* Clarification Overlay */}
                                    <ClarificationOverlay
                                        request={clarificationRequest}
                                        onSubmit={handleClarificationSubmit}
                                        onDismiss={handleClarificationDismiss}
                                        fullScreen={!clarificationRequest?.targetComponentId}
                                    />
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

                {/* Debug Panel Portal */}
                {renderDebugPanel()}
            </div>
        </>
    );
}

export default GenerativeUIPage;
