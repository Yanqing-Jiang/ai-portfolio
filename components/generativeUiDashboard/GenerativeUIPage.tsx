// --- Function/Class Map ---
// Component: ProcessPanel
//   Role: Collapsible process status panel at top of dashboard area.
//   Called from: GenerativeUIPage.tsx
//   Invokes: onToggle, onViewFullDebug callbacks
//   Why: Unified status display replacing scattered header icons.
// Component: SuggestionPopup
//   Role: Render quick-start suggestion cards for common queries.
//   Called from: components/generativeUiDashboard/GenerativeUIPage.tsx
//   Invokes: onSelect callback
//   Why: Helps users discover example prompts quickly.
// Component: GenerativeUIPage
//   Role: Orchestrate A2UI streaming, clarifications, SEO head tags, and dashboard layout.
//   Called from: App routing
//   Invokes: ProjectHelmet, useA2UIStream, useSurface, ProcessPanel, ClarificationOverlay, FollowUpSuggestions
//   Why: Main A2UI experience container with crawlable marketing context for the portfolio.
// --- End Function/Class Map ---
/**
 * Generative UI Project Page (2026) - Award-Winning Redesign v2
 *
 * Features:
 * - Clean header (no back button, no scattered icons)
 * - ProcessPanel at top with collapsible status + stages
 * - Smart Generate/Stop button morphing
 * - Premium glassmorphism + Framer Motion orchestration
 */

import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import { motion, AnimatePresence } from 'framer-motion';

// Auth & API
import { authService, type AuthState } from '../../services/auth';
import { apiService, type UsageStats } from '../../services/apiService';
import { configService } from '../../services/config';
import { AuthModal } from '../AuthModal';

// A2UI imports
import { useA2UIStream, useSurface } from './a2ui';
import { A2UISurface, A2UISurfaceLoading, A2UISurfaceError } from './renderer';
import { ClarificationOverlay, type ClarificationRequest } from './ClarificationOverlay';
import { FollowUpSuggestions, type FollowUpSuggestion } from './FollowUpSuggestions';
import { getOrCreateSessionId } from './utils/session';
import type { AnomalyData } from './widgets/AnomalyAlert';
import type { SkillInfo } from './SkillHeaderBadge';
import { ContextRibbon, type HistoryItem } from './ContextRibbon';
import { ProcessPanel, type AuditEvent } from './ProcessPanel';
import { DashboardWithLayout } from './DashboardWithLayout';
import { ProjectHelmet } from '../ProjectHelmet';
import { PROJECT_DATA } from '../../constants';
import type { Project } from '../../types';

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
        price: '📈',
        revenue: '💰',
        margins: '📊',
        earnings: '💎',
        position: '🏁',
    },
    header: {
        debug: '⚙️',
        reset: '🔄',
        download: '📥',
    },
    prompt: {
        tip: '💡',
        close: '✕',
    },
    emptyState: '📊',
    followUps: {
        deep: '🔍',
        peer: '👥',
    },
    events: {
        skillSelected: '⚡',
        streamStarted: '🔌',
        dataReceived: '📊',
        layoutUpdated: '🎨',
        streamComplete: '✅',
        error: '❌',
        default: '🔹',
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
];

// Available tickers for the database
const AVAILABLE_TICKERS = ['AMD', 'AVGO', 'INTC', 'MU', 'NVDA', 'QCOM', 'TXN'];

// ============================================================================
// Process Panel State (exported from ProcessPanel.tsx)
// ============================================================================

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
    const [isMobile, setIsMobile] = useState(false);
    const allProjects = useMemo<Project[]>(() => PROJECT_DATA.flatMap((year) => year.projects), []);
    const a2uiProject = useMemo<Project | undefined>(
        () => allProjects.find((proj) => proj.id === 'agent-to-ui'),
        [allProjects]
    );
    const showA2UISeoSummary = false;

    useEffect(() => {
        const checkMobile = () => setIsMobile(window.innerWidth < 640);
        checkMobile();
        window.addEventListener('resize', checkMobile);
        return () => window.removeEventListener('resize', checkMobile);
    }, []);

    useEffect(() => {
        console.log('GenerativeUIPage Rendered:', { dashboardId, question });
    }, [dashboardId, question]);

    const [isCreating, setIsCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [showDebugPanel, setShowDebugPanel] = useState(false);
    const [isFocused, setIsFocused] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auth & Rate Limit State
    const [authState, setAuthState] = useState<AuthState>({ user: null, loading: true, error: null });
    const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
    const [showAuthModal, setShowAuthModal] = useState(false);
    const [authToken, setAuthToken] = useState<string | null>(null);

    // Fetch usage stats
    const fetchUsageStats = useCallback(async () => {
        try {
            const response = await apiService.getUsageStats('chat');
            if (response.success && response.data) {
                setUsageStats(response.data);
            }
        } catch (error) {
            console.warn('Failed to fetch usage stats:', error);
        }
    }, []);

    useEffect(() => {
        const unsubscribe = authService.subscribe(setAuthState);
        return unsubscribe;
    }, []);

    // Keep auth token in sync for SSE streams (EventSource doesn't support headers)
    useEffect(() => {
        const updateToken = async () => {
            const token = await authService.getAccessToken();
            setAuthToken(token);
        };
        if (!authState.loading) {
            updateToken();
        }
    }, [authState.loading, authState.user]);

    useEffect(() => {
        if (!authState.loading) {
            fetchUsageStats();
        }
    }, [authState.loading, authState.user, fetchUsageStats]);

    // Clarification and follow-up state
    const [clarificationRequest, setClarificationRequest] = useState<ClarificationRequest | null>(null);
    const [followUpSuggestions, setFollowUpSuggestions] = useState<FollowUpSuggestion[]>([]);
    const [anomalies, setAnomalies] = useState<AnomalyData[]>([]);
    const [activeSkill, setActiveSkill] = useState<SkillInfo | null>(null);
    const [history, setHistory] = useState<HistoryItem[]>([]);

    // Track dashboards that have completed streaming (for skip-streaming on revisit)
    const [completedDashboards, setCompletedDashboards] = useState<Set<string>>(new Set());

    // Process Panel state (replaces scattered debug/status UI)
    const [isProcessPanelExpanded, setIsProcessPanelExpanded] = useState(false);

    // Audit trail for Process Panel - tracks execution timeline
    const [auditTrail, setAuditTrail] = useState<AuditEvent[]>([]);

    // Tooltip State for Ticker
    const [activeTooltip, setActiveTooltip] = useState<{ x: number, y: number, content: string, color: string } | null>(null);

    // Add audit event helper
    const addAuditEvent = useCallback((type: AuditEvent['type'], label: string, details?: string) => {
        setAuditTrail((prev) => [
            ...prev,
            { id: `${Date.now()}`, type, label, timestamp: new Date(), details },
        ]);
    }, []);

    // A2UI stream state
    const sessionId = useMemo(() => getOrCreateSessionId(), []);
    const backendUrl = configService.getBackendUrl();
    const streamUrl = useMemo(() => {
        if (!dashboardId) return null;
        const params = new URLSearchParams({ session_id: sessionId });
        if (authToken) params.set('token', authToken);
        return `${backendUrl}/api/dash/${dashboardId}/stream?${params.toString()}`;
    }, [dashboardId, sessionId, authToken, backendUrl]);
    const [streamState, streamActions] = useA2UIStream(streamUrl, {
        autoConnect: true,
        dashboardId: dashboardId || undefined,
        apiBaseUrl: `${backendUrl}/api/dash`,
        onAudit: (event) => {
            addAuditEvent(event.event, event.event.replace(/_/g, ' '), event.details);
        }
    });

    // Get surface data
    const surfaceId = 'dashboard_main';
    const { surface, dataModel: rawDataModel } = useSurface(streamState, surfaceId);

    // Enhance dataModel with isRevisit flag for completed dashboards (skip streaming on tab switch)
    const dataModel = useMemo(() => {
        if (!rawDataModel) return rawDataModel;
        const isRevisit = dashboardId ? completedDashboards.has(dashboardId) : false;
        return {
            ...rawDataModel,
            data: {
                ...(rawDataModel.data || {}),
                explanation: {
                    ...((rawDataModel.data as Record<string, unknown>)?.explanation || {}),
                    isRevisit,
                },
            },
        };
    }, [rawDataModel, dashboardId, completedDashboards]);

    // Auto-resize textarea
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        }
    }, [question]);

    // Handle dashboard creation (always creates new dashboard)
    const handleSubmit = useCallback(async (overrideQuestion?: string) => {
        const nextQuestion = (overrideQuestion ?? question).trim();
        if (!nextQuestion || isCreating) return;

        setIsCreating(true);
        setError(null);
        setShowSuggestions(false);

        try {
            const authHeaders = await authService.getAuthHeaders();
            const response = await fetch(`${backendUrl}/api/dash/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeaders },
                body: JSON.stringify({ question: nextQuestion }),
            });

            // Detailed HTTP error handling
            if (response.status === 401) {
                throw new Error('Authentication required. Please sign in.');
            }
            if (response.status === 429) {
                const retryAfter = response.headers.get('Retry-After');
                throw new Error(retryAfter
                    ? `Rate limited. Retry in ${retryAfter}s`
                    : 'Rate limited. Try again shortly.');
            }
            if (!response.ok) {
                let detail = response.statusText;
                try {
                    const errorBody = await response.text();
                    const parsed = JSON.parse(errorBody);
                    detail = parsed.detail || parsed.message || errorBody.slice(0, 200);
                } catch {
                    // Keep default statusText
                }
                throw new Error(`HTTP ${response.status}: ${detail}`);
            }

            // Safe JSON parsing with detailed error
            const text = await response.text();
            let data;
            try {
                data = JSON.parse(text);
            } catch (parseErr) {
                console.error('[A2UI] JSON parse failed. Response text:', text.slice(0, 500));
                throw new Error(`Invalid JSON response (${text.length} chars). Check console for details.`);
            }
            const newId = data.dashboard_id;

            setDashboardId(newId);
            setQuestion(nextQuestion);
            setHistory(prev => {
                if (prev.some(h => h.id === newId)) return prev;
                return [...prev, { id: newId, query: nextQuestion, timestamp: new Date() }];
            });
            addAuditEvent('stream_started', 'Dashboard created', `ID: ${newId}`);
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : 'Unknown error';
            console.error('[A2UI] Dashboard creation failed:', errorMsg);
            setError(errorMsg);
            addAuditEvent('error', 'Creation failed', errorMsg);
        } finally {
            setIsCreating(false);
        }
    }, [question, isCreating, addAuditEvent, backendUrl]);

    /**
     * handleInput - Unified input handler for chat input.
     * 
     * Function: handleInput
     * Called from: Enter keypress, Generate button click
     * Invokes: sendQuery (if dashboard exists) OR handleSubmit (no dashboard)
     * Why: Routes user input through LLM intent classification to determine
     *      whether to modify existing dashboard or create new one.
     */
    const handleInput = useCallback(async () => {
        const nextQuestion = question.trim();
        if (!nextQuestion || isCreating) return;

        setShowSuggestions(false);

        // If we have an active dashboard, use LLM-driven intent classification
        // This lets the LLM decide if we need a new dashboard or modify current one
        if (dashboardId && streamState.isDone) {
            setIsCreating(true);
            setError(null);

            try {
                addAuditEvent('stream_started', 'Query sent', nextQuestion);
                const result = await streamActions.sendQuery(nextQuestion);

                if (result.status === 'new_dashboard' && result.dashboard_id) {
                    // LLM determined this needs a new dashboard
                    setDashboardId(result.dashboard_id);
                    setQuestion(nextQuestion);
                    setHistory(prev => {
                        if (prev.some(h => h.id === result.dashboard_id)) return prev;
                        return [...prev, { id: result.dashboard_id!, query: nextQuestion, timestamp: new Date() }];
                    });
                    addAuditEvent('skill_selected', 'New analysis started', result.rationale || '');
                } else if (result.status === 'success') {
                    // LLM handled it within current dashboard context
                    addAuditEvent('data_received', `Intent: ${result.intent}`, result.rationale || '');

                    // Apply layout changes via custom event (listened by LayoutProvider components)
                    if (result.intent === 'modify_layout' && result.result) {
                        const layoutAction = result.result as { action?: string; details?: Record<string, unknown> };
                        const actionName = layoutAction.action;
                        const actionDetails = layoutAction.details || {};

                        // Emit custom event for layout updates
                        // This allows components within LayoutProvider to respond
                        window.dispatchEvent(new CustomEvent('a2ui:layout-change', {
                            detail: {
                                action: actionName,
                                params: actionDetails,
                                dashboardId,
                            }
                        }));

                        addAuditEvent('layout_updated', `Layout: ${actionName}`, JSON.stringify(actionDetails));
                    }
                } else if (result.status === 'error') {
                    setError(result.message || 'Query failed');
                    addAuditEvent('error', 'Query failed', result.message || 'Unknown error');
                }
            } catch (err) {
                console.error('Query failed, falling back to new dashboard:', err);
                setError(null); // Clear error before fallback
                // Fall back to creating new dashboard
                handleSubmit(nextQuestion);
                return;
            } finally {
                setIsCreating(false);
            }
        } else {
            // No active dashboard or still streaming - create new one
            handleSubmit(nextQuestion);
        }
    }, [question, isCreating, dashboardId, streamState.isDone, streamActions, handleSubmit, addAuditEvent]);

    // Handle history selection
    const handleHistorySelect = useCallback((item: HistoryItem) => {
        // Clear UI state that should refresh on tab switch
        setFollowUpSuggestions([]);
        setAnomalies([]);
        setClarificationRequest(null);
        setAuditTrail([]); // Clear audit trail for new stream

        // Update dashboard context - this will automatically trigger reconnect via streamUrl change
        setDashboardId(item.id);
        setQuestion(item.query);
        setActiveSkill(null);
    }, []);

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
        setAnomalies([]);
        setActiveSkill(null);
        streamActions.close();
    };

    // Fetch skill info when dashboard is created
    useEffect(() => {
        if (dashboardId && !activeSkill) {
            const fetchSkillInfo = async () => {
                try {
                    const authHeaders = await authService.getAuthHeaders();
                    const response = await fetch(`${backendUrl}/api/dash/${dashboardId}/spec`, {
                        headers: authHeaders,
                    });
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
                    console.error('[A2UI] Failed to fetch skill info:', err);
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
            const converted: ClarificationRequest = {
                id: backend.request_id,
                title: backend.title,
                subtitle: backend.subtitle,
                targetComponentId: backend.target_component_id,
                fields: backend.fields.map(f => ({
                    id: f.field_id,
                    type: f.input_type === 'multi_choice' ? 'multi_choice'
                        : f.input_type === 'freeform' ? 'freeform'
                            : 'single_choice',
                    prompt: f.label,
                    options: f.options?.map((o) => ({
                        label: o.label,
                        value: o.id,
                        description: o.description,
                    })),
                    maxSelections: f.input_type === 'multi_choice' ? f.options?.length : undefined,
                    placeholder: f.placeholder,
                })),
            };
            setClarificationRequest(converted);
        }
    }, [streamState.pendingClarification, clarificationRequest]);

    // Handle clarification response
    const handleClarificationSubmit = useCallback(
        async (requestId: string, responses: Record<string, string | string[]>, skipped: boolean) => {
            setClarificationRequest(null);
            streamActions.clearClarification();

            // Send response to backend
            if (dashboardId) {
                try {
                    const authHeaders = await authService.getAuthHeaders();
                    await fetch(`${backendUrl}/api/dash/${dashboardId}/clarification`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', ...authHeaders },
                        body: JSON.stringify({
                            request_id: requestId,
                            values: responses,
                            skipped: skipped,
                        }),
                    });
                    addAuditEvent('data_received', 'Clarification submitted', requestId);
                } catch (err) {
                    console.error('Failed to submit clarification:', err);
                    addAuditEvent('error', 'Clarification failed', err instanceof Error ? err.message : 'Unknown error');
                }
            }
        },
        [dashboardId, streamActions, addAuditEvent]
    );

    const handleClarificationDismiss = useCallback((_requestId: string) => {
        setClarificationRequest(null);
        streamActions.clearClarification();
    }, [streamActions]);

    // Handle follow-up suggestion click (uses LLM-driven intent classification)
    const handleFollowUpSelect = useCallback(
        async (suggestion: FollowUpSuggestion) => {
            setQuestion(suggestion.query);
            setFollowUpSuggestions([]);
            setAnomalies([]);

            // If we have an active dashboard, use the unified query endpoint
            // This allows the LLM to decide if this should be a new dashboard
            // or a modification to the current one
            // 
            // Exception: Anomaly category suggestions should always create new analysis
            if (suggestion.category === 'anomaly') {
                // Anomaly investigations always need a full new analysis
                handleSubmit(suggestion.query);
                return;
            }

            if (dashboardId) {
                try {
                    addAuditEvent('stream_started', 'Query sent', suggestion.query);
                    const result = await streamActions.sendQuery(suggestion.query);

                    if (result.status === 'new_dashboard' && result.dashboard_id) {
                        // LLM determined this needs a new dashboard
                        // The sendQuery event handler will emit 'a2ui:new-dashboard'
                        setDashboardId(result.dashboard_id);
                        setHistory(prev => {
                            if (prev.some(h => h.id === result.dashboard_id)) return prev;
                            return [...prev, { id: result.dashboard_id!, query: suggestion.query, timestamp: new Date() }];
                        });
                        addAuditEvent('skill_selected', 'New analysis started', result.rationale || '');
                    } else if (result.status === 'success') {
                        // LLM handled it within current dashboard context
                        if (result.intent === 'follow_up') {
                            // Follow-up questions should create new analysis to show results
                            // The current backend just returns text, which isn't displayed
                            handleSubmit(suggestion.query);
                        } else {
                            addAuditEvent('data_received', `Intent: ${result.intent}`, result.rationale || '');
                        }
                    } else if (result.status === 'error') {
                        addAuditEvent('error', 'Query failed', result.message || 'Unknown error');
                    }
                } catch (err) {
                    console.error('Query failed:', err);
                    addAuditEvent('error', 'Query failed', err instanceof Error ? err.message : 'Unknown error');
                    // Fall back to creating new dashboard
                    handleSubmit(suggestion.query);
                }
            } else {
                // No active dashboard - create new one
                handleSubmit(suggestion.query);
            }
        },
        [dashboardId, streamActions, handleSubmit, addAuditEvent]
    );

    // Track stream completion
    useEffect(() => {
        if (streamState.isDone && !auditTrail.some((e) => e.type === 'stream_complete')) {
            addAuditEvent('stream_complete', 'Stream completed', `${streamState.surfaces.size} surfaces rendered`);
        }
    }, [streamState.isDone, streamState.surfaces.size, auditTrail, addAuditEvent]);

    // Track completed dashboards for skip-streaming on revisit
    useEffect(() => {
        if (streamState.isDone && dashboardId && !completedDashboards.has(dashboardId)) {
            setCompletedDashboards(prev => new Set(prev).add(dashboardId));
        }
    }, [streamState.isDone, dashboardId, completedDashboards]);

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
                    const authHeaders = await authService.getAuthHeaders();
                    const response = await fetch(`${backendUrl}/api/dash/${dashboardId}/follow-ups`, {
                        headers: authHeaders,
                    });
                    if (response.ok) {
                        const data = await response.json();
                        if (data.suggestions && Array.isArray(data.suggestions)) {
                            setFollowUpSuggestions(data.suggestions);
                        }
                        // Store anomalies for AnomalyAlert display
                        if (data.anomalies && Array.isArray(data.anomalies)) {
                            setAnomalies(data.anomalies);
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

                            {/* JSON Download Button */}
                            <div className="mt-4 pt-4 border-t border-slate-800 flex justify-end">
                                <button
                                    onClick={() => {
                                        const data = { dashboardId, question, skill: activeSkill, streamState: { connectionStatus: streamState.connectionStatus, surfaces: streamState.surfaces.size }, auditTrail, dataModel };
                                        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = `a2ui-debug-${dashboardId || 'session'}-${Date.now()}.json`;
                                        a.click();
                                        URL.revokeObjectURL(url);
                                    }}
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-rose-500 to-amber-500 text-white hover:opacity-90 transition-opacity"
                                >
                                    {ICONS.header.download}
                                    Download JSON
                                </button>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </AnimatePresence>
        );
    };

    return (
        <>
            {a2uiProject ? (
                <ProjectHelmet project={a2uiProject} />
            ) : (
                <Helmet>
                    <title>Agent to UI | Agentic UI UX Design | A2UI</title>
                    <meta
                        name="description"
                        content="Agent-guided A2UI dashboard generation that streams widgets, KPIs, and news from finance questions using Claude Agent SDK, FastAPI SSE, and a custom React renderer."
                    />
                </Helmet>
            )}

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



                {/* Main Content - Split Screen */}

                <div className="relative z-10 flex flex-col min-h-screen overflow-hidden">
                    {showA2UISeoSummary && (
                        <section className="px-4 sm:px-8 pt-10 pb-6 max-w-6xl mx-auto space-y-4 text-slate-100">
                            <div className="flex flex-wrap items-start gap-4 justify-between">
                                <div className="space-y-3 max-w-3xl">
                                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
                                        {a2uiProject?.title ?? 'Agent to UI'}
                                    </h1>
                                    <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                                        {a2uiProject?.seoDescription ??
                                            'Agent-guided A2UI dashboard generation that streams widgets, KPIs, and news from finance questions using Claude Agent SDK, FastAPI SSE, and a custom React renderer.'}
                                    </p>
                                    <div className="flex flex-wrap gap-2">
                                        {(a2uiProject?.serviceTags ?? ['Generative UI', 'Agent UX', 'Financial Analytics']).map((tag) => (
                                            <span
                                                key={tag}
                                                className="px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/20 border border-rose-400/30 text-rose-100"
                                            >
                                                {tag}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                                {a2uiProject?.ogImage && (
                                    <figure className="w-full sm:w-64 rounded-xl overflow-hidden border border-white/10 shadow-lg bg-slate-900/60">
                                        <img
                                            src={a2uiProject.ogImage}
                                            alt="Generative financial dashboard rendered via the A2UI protocol"
                                            className="w-full h-full object-cover"
                                            loading="lazy"
                                        />
                                    </figure>
                                )}
                            </div>

                            <div className="grid gap-4 md:grid-cols-3">
                                <div className="p-4 rounded-xl border border-white/10 bg-slate-900/60 backdrop-blur">
                                    <h2 className="text-sm font-semibold text-rose-200 mb-2">Agentic workflow</h2>
                                    <ul className="space-y-1 text-slate-300 text-sm leading-relaxed list-disc list-inside">
                                        <li>Clarifies finance intent, streams A2UI surfaceUpdate + dataModelUpdate phases.</li>
                                        <li>SQL + chart toolchain via FastAPI SSE, Claude Agent SDK, and ECharts/TradingView rendering.</li>
                                        <li>Follow-ups reuse conversation memory, audit trail, and bound values.</li>
                                    </ul>
                                </div>
                                <div className="p-4 rounded-xl border border-white/10 bg-slate-900/60 backdrop-blur">
                                    <h2 className="text-sm font-semibold text-rose-200 mb-2">Data coverage</h2>
                                    <ul className="space-y-1 text-slate-300 text-sm leading-relaxed list-disc list-inside">
                                        <li>Default prompts cover NVDA, AMD, INTC, AVGO, QCOM, MU, TXN.</li>
                                        <li>Supports comparative KPIs, margins, cash flow, and earnings timelines.</li>
                                        <li>Server-side summary + h1 ensure crawlers see finance context instantly.</li>
                                    </ul>
                                </div>
                                <div className="p-4 rounded-xl border border-white/10 bg-slate-900/60 backdrop-blur">
                                    <h2 className="text-sm font-semibold text-rose-200 mb-2">Crawl-ready facts</h2>
                                    <ul className="space-y-1 text-slate-300 text-sm leading-relaxed list-disc list-inside">
                                        {(a2uiProject?.statHighlights ?? [
                                            'Streams custom dashboards from natural language queries via A2UI protocol',
                                            'Renders TradingView charts, ECharts visualizations, and real-time KPIs',
                                        ]).map((fact) => (
                                            <li key={fact}>{fact}</li>
                                        ))}
                                        <li>
                                            Architecture: <a
                                                className="text-rose-200 underline decoration-rose-400/50 hover:text-white"
                                                href="https://github.com/Yanqing-Jiang/ai-portfolio/blob/main/docs/architecture-generative-ui.md"
                                                target="_blank"
                                                rel="noopener noreferrer"
                                            >docs/architecture-generative-ui.md</a>
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </section>
                    )}

                    {/* Dashboard Area (70%) */}

                    <div className="flex-1 flex flex-col min-h-0">

                        <div className="flex-1 p-3 sm:p-6 flex flex-col min-h-0">

                            <div

                                className="flex-1 rounded-2xl relative flex flex-col min-h-0"

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



                                <div className="flex-1 overflow-auto p-4 sm:p-6 flex flex-col min-h-0">

                                    {/* History Ribbon */}

                                    <ContextRibbon

                                        history={history}

                                        currentId={dashboardId}

                                        onSelect={handleHistorySelect}

                                    />



                                    {/* Process Panel - Collapsible Status at Top */}

                                    <ProcessPanel

                                        isExpanded={isProcessPanelExpanded}

                                        onToggle={() => setIsProcessPanelExpanded(!isProcessPanelExpanded)}

                                        streamState={{

                                            isConnected: streamState.isConnected,

                                            isDone: streamState.isDone,

                                            isLoading: streamState.isLoading,

                                            connectionStatus: streamState.connectionStatus,

                                            surfaceCount: streamState.surfaces.size,

                                            error: streamState.error?.message ?? null,

                                        }}

                                        activeSkill={activeSkill}

                                        query={question}

                                        dashboardId={dashboardId}

                                        auditTrail={auditTrail}

                                        dataModel={dataModel}

                                        onViewFullDebug={() => setShowDebugPanel(true)}

                                    />



                                    {/* Empty State / Welcome Screen - Future of Analytics */}

                                    {!dashboardId && (

                                        <div className="flex-1 flex flex-col items-center justify-center relative overflow-hidden py-8">

                                            {/* Animated Background Layers */}

                                            <div className="absolute inset-0 pointer-events-none overflow-hidden">

                                                {/* Gradient Orbs */}

                                                <motion.div

                                                    className="absolute top-1/4 left-1/4 w-[500px] h-[500px] rounded-full"

                                                    animate={{

                                                        x: [0, 50, 0, -50, 0],

                                                        y: [0, -30, 0, 30, 0],

                                                        scale: [1, 1.1, 1, 0.9, 1],

                                                    }}

                                                    transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}

                                                    style={{

                                                        background: 'radial-gradient(circle, rgba(244, 63, 94, 0.15) 0%, transparent 70%)',

                                                        filter: 'blur(80px)',

                                                    }}

                                                />

                                                <motion.div

                                                    className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] rounded-full"

                                                    animate={{

                                                        x: [0, -40, 0, 40, 0],

                                                        y: [0, 40, 0, -40, 0],

                                                        scale: [1, 0.9, 1, 1.1, 1],

                                                    }}

                                                    transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}

                                                    style={{

                                                        background: 'radial-gradient(circle, rgba(245, 158, 11, 0.12) 0%, transparent 70%)',

                                                        filter: 'blur(60px)',

                                                    }}

                                                />



                                                {/* Floating Particles */}

                                                {[...Array(12)].map((_, i) => (

                                                    <motion.div

                                                        key={i}

                                                        className="absolute w-1 h-1 rounded-full"

                                                        style={{

                                                            left: `${10 + (i * 7) % 80}%`,

                                                            top: `${15 + (i * 11) % 70}%`,

                                                            backgroundColor: i % 2 === 0 ? 'rgba(244, 63, 94, 0.6)' : 'rgba(245, 158, 11, 0.5)',

                                                        }}

                                                        animate={{

                                                            y: [0, -30, 0],

                                                            x: [0, i % 2 === 0 ? 15 : -15, 0],

                                                            opacity: [0.2, 0.8, 0.2],

                                                            scale: [1, 1.5, 1],

                                                        }}

                                                        transition={{

                                                            duration: 4 + (i % 3),

                                                            repeat: Infinity,

                                                            delay: i * 0.3,

                                                            ease: "easeInOut",

                                                        }}

                                                    />

                                                ))}



                                                {/* Grid Pattern Overlay */}

                                                <div

                                                    className="absolute inset-0 opacity-[0.03]"

                                                    style={{

                                                        backgroundImage: `

                                                                        linear-gradient(rgba(244, 63, 94, 0.5) 1px, transparent 1px),

                                                                        linear-gradient(90deg, rgba(244, 63, 94, 0.5) 1px, transparent 1px)

                                                                    `,

                                                        backgroundSize: '60px 60px',

                                                    }}

                                                />

                                            </div>



                                            {/* Main Content */}



                                            <motion.div



                                                initial={{ y: 30, opacity: 0 }}



                                                animate={{ y: 0, opacity: 1 }}



                                                transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}



                                                className="relative z-10 text-center max-w-4xl px-4 w-full"



                                            >



                                                {/* Main Headline */}



                                                <motion.h2



                                                    initial={{ y: 20, opacity: 0 }}



                                                    animate={{ y: 0, opacity: 1 }}



                                                    transition={{ delay: 0.3, duration: 0.8 }}



                                                    className="text-3xl sm:text-5xl md:text-6xl font-black tracking-tight leading-tight sm:leading-snug mb-6"



                                                    style={{ color: 'rgba(248, 250, 252, 0.95)' }}



                                                >



                                                    Agent to UI.



                                                    <br />



                                                    <span



                                                        className="bg-clip-text text-transparent"



                                                        style={{



                                                            backgroundImage: 'linear-gradient(135deg, #f43f5e 0%, #f59e0b 50%, #f43f5e 100%)',



                                                            backgroundSize: '200% 100%',



                                                            animation: 'gradientShift 3s ease infinite',



                                                        }}



                                                    >



                                                        Live Dashboard Generation.



                                                    </span>



                                                </motion.h2>







                                                {/* Subtitle */}







                                                <motion.p







                                                    initial={{ y: 20, opacity: 0 }}







                                                    animate={{ y: 0, opacity: 1 }}







                                                    transition={{ delay: 0.4, duration: 0.8 }}







                                                    className="flex flex-wrap justify-center items-center gap-4 max-w-2xl mx-auto mb-12"







                                                >







                                                    {/* Rolling News Bar / Ticker */}
                                                    <div className="relative h-10 w-[200px] sm:w-[400px] overflow-hidden flex items-center" style={{ maskImage: 'linear-gradient(to right, transparent, black 10%, black 90%, transparent)', WebkitMaskImage: 'linear-gradient(to right, transparent, black 10%, black 90%, transparent)' }}>
                                                        <style>{`
                                                                                                                                                                                                                        @keyframes marquee {
                                                                                                                                                                                                                            0% { transform: translateX(0); }
                                                                                                                                                                                                                            100% { transform: translateX(-50%); }
                                                                                                                                                                                                                        }
                                                                                                                                                                                                                        .animate-marquee {
                                                                                                                                                                                                                            animation: marquee 30s linear infinite;
                                                                                                                                                                                                                        }
                                                                                                                                                                                                                        .animate-marquee:hover {
                                                                                                                                                                                                                            animation-play-state: paused;
                                                                                                                                                                                                                        }
                                                                                                                                                                                                                    `}</style>

                                                        <div className="flex gap-4 animate-marquee whitespace-nowrap px-4">
                                                            {[
                                                                { label: 'Google A2UI Framework', desc: "Open standard for agent-driven interfaces.", color: 'blue' },
                                                                { label: 'Claude Agent SDK', desc: "The core framework driving the agent's logic and capabilities.", color: 'orange' },
                                                                { label: 'Agent Guided UI Generation', desc: "Dynamically constructing interfaces based on user needs in real-time.", color: 'emerald' },
                                                                { label: 'Agent Runtime Loop', desc: "Continuous cycle of reasoning, action, and observation.", color: 'rose' },
                                                                { label: 'Agentic Analytics', desc: "Deep insights derived by autonomous agents analyzing data patterns.", color: 'cyan' },
                                                                { label: 'Google A2UI Framework', desc: "Open standard for agent-driven interfaces.", color: 'blue' },
                                                                { label: 'Claude Agent SDK', desc: "The core framework driving the agent's logic and capabilities.", color: 'orange' },
                                                                { label: 'Agent Guided UI Generation', desc: "Dynamically constructing interfaces based on user needs in real-time.", color: 'emerald' },
                                                                { label: 'Agent Runtime Loop', desc: "Continuous cycle of reasoning, action, and observation.", color: 'rose' },
                                                                { label: 'Agentic Analytics', desc: "Deep insights derived by autonomous agents analyzing data patterns.", color: 'cyan' },
                                                            ].map((tag, i) => {
                                                                const colors: any = {
                                                                    blue: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/20', hoverBg: 'hover:bg-blue-500/20', hoverBorder: 'hover:border-blue-500/30' },
                                                                    orange: { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/20', hoverBg: 'hover:bg-orange-500/20', hoverBorder: 'hover:border-orange-500/30' },
                                                                    emerald: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20', hoverBg: 'hover:bg-emerald-500/20', hoverBorder: 'hover:border-emerald-500/30' },
                                                                    rose: { bg: 'bg-rose-500/10', text: 'text-rose-400', border: 'border-rose-500/20', hoverBg: 'hover:bg-rose-500/20', hoverBorder: 'hover:border-rose-500/30' },
                                                                    cyan: { bg: 'bg-cyan-500/10', text: 'text-cyan-400', border: 'border-cyan-500/20', hoverBg: 'hover:bg-cyan-500/20', hoverBorder: 'hover:border-cyan-500/30' },
                                                                }[tag.color];

                                                                return (
                                                                    <div key={i} className="group relative inline-block">
                                                                        <span
                                                                            onMouseEnter={(e) => {
                                                                                const rect = e.currentTarget.getBoundingClientRect();
                                                                                setActiveTooltip({
                                                                                    x: rect.left + rect.width / 2,
                                                                                    y: rect.top,
                                                                                    content: tag.desc,
                                                                                    color: tag.color
                                                                                });
                                                                            }}
                                                                            onMouseLeave={() => setActiveTooltip(null)}
                                                                            className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium border transition-all cursor-default whitespace-nowrap ${colors.bg} ${colors.text} ${colors.border} ${colors.hoverBg} ${colors.hoverBorder}`}
                                                                        >
                                                                            {tag.label}
                                                                        </span>
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>



                                                </motion.p>







                                                {/* Simplified "You Ask -> Generative UI" Visual */}



                                                <motion.div



                                                    initial={{ y: 30, opacity: 0 }}







                                                    animate={{ y: 0, opacity: 1 }}







                                                    transition={{ delay: 0.5, duration: 0.8 }}







                                                    className="flex items-center justify-center gap-2 sm:gap-6 mb-16"







                                                >



                                                    {/* Step 1: Input */}







                                                    <div className="flex flex-col items-center gap-3 group relative cursor-help">







                                                        <div className="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center text-3xl shadow-xl group-hover:border-rose-500/50 transition-colors duration-300">







                                                            💬







                                                        </div>







                                                        <p className="text-sm font-medium text-slate-400 group-hover:text-rose-400 transition-colors">Your Question</p>















                                                        {/* Tooltip */}







                                                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 w-64 p-3 bg-slate-900/95 backdrop-blur-xl border border-rose-500/30 rounded-lg shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 z-50 pointer-events-none transform translate-y-2 group-hover:translate-y-0">







                                                            <div className="text-xs text-slate-300 leading-relaxed">







                                                                <span className="text-rose-400 font-semibold block mb-1">Financial Queries</span>







                                                                "Analyze NVDA's price movement", "Compare AMD vs Intel", "Show me revenue trends for Broadcom..."







                                                            </div>







                                                            <div className="absolute inset-0 rounded-lg bg-gradient-to-tr from-rose-500/5 to-purple-500/5 pointer-events-none" />







                                                        </div>







                                                    </div>















                                                    {/* Plus Sign */}







                                                    <div className="flex flex-col items-center justify-center">







                                                        <div className="text-slate-600 text-2xl font-light">







                                                            +







                                                        </div>







                                                    </div>















                                                    {/* Step: Agent */}































                                                    <div className="flex flex-col items-center gap-3 group relative cursor-help">































                                                        <div className="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center text-3xl shadow-xl group-hover:border-emerald-500/50 transition-colors duration-300">































                                                            🤖































                                                        </div>































                                                        <p className="text-sm font-medium text-slate-400 group-hover:text-emerald-400 transition-colors">Agent</p>































































                                                        {/* Tooltip */}































                                                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 w-64 p-3 bg-slate-900/95 backdrop-blur-xl border border-emerald-500/30 rounded-lg shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 z-50 pointer-events-none transform translate-y-2 group-hover:translate-y-0">































                                                            <div className="text-xs text-slate-300 leading-relaxed">































                                                                <span className="text-emerald-400 font-semibold block mb-1">Agent Loop</span>































                                                                Claude Code-style execution: Plans actions, calls tools (SQL, Search), and iteratively refines the dashboard.































                                                            </div>































                                                            <div className="absolute inset-0 rounded-lg bg-gradient-to-tr from-emerald-500/5 to-cyan-500/5 pointer-events-none" />































                                                        </div>































                                                    </div>















                                                    {/* Equal Sign */}







                                                    <div className="flex flex-col items-center justify-center">







                                                        <div className="text-slate-600 text-2xl font-light">







                                                            =







                                                        </div>







                                                    </div>















                                                    {/* Step 2: Generative Dashboard Visual */}

                                                    <div className="flex flex-col items-center gap-3">

                                                        <motion.div

                                                            className="relative w-64 h-40 bg-slate-900 rounded-xl border border-slate-700 overflow-hidden shadow-2xl group"

                                                            whileHover={{ scale: 1.05 }}

                                                            style={{ boxShadow: '0 0 30px rgba(244, 63, 94, 0.15)' }}

                                                        >

                                                            {/* Abstract UI Elements */}

                                                            <div className="absolute top-3 left-3 right-3 h-2 bg-slate-800 rounded-full w-1/3" />

                                                            <div className="absolute top-8 left-3 w-12 h-12 bg-slate-800/50 rounded-lg border border-slate-700/50" />

                                                            <div className="absolute top-8 left-18 right-3 h-12 bg-slate-800/30 rounded-lg border border-slate-700/30">

                                                                {/* Mock Chart Line */}

                                                                <svg className="w-full h-full p-2 opacity-50" viewBox="0 0 100 40" preserveAspectRatio="none">

                                                                    <path d="M0 30 Q 20 10, 40 25 T 100 5" fill="none" stroke="#f43f5e" strokeWidth="2" />

                                                                </svg>

                                                            </div>

                                                            <div className="absolute bottom-3 left-3 right-3 h-8 bg-slate-800/50 rounded-lg flex items-center gap-2 px-2">

                                                                <div className="w-1/4 h-2 bg-slate-700 rounded-full" />

                                                                <div className="w-1/4 h-2 bg-slate-700 rounded-full" />

                                                            </div>



                                                            {/* Scanning Effect */}

                                                            <motion.div

                                                                className="absolute inset-0 bg-gradient-to-r from-transparent via-rose-500/10 to-transparent"

                                                                animate={{ x: ['-100%', '200%'] }}

                                                                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}

                                                            />

                                                        </motion.div>

                                                        <p className="text-sm font-bold bg-gradient-to-r from-rose-400 to-amber-400 bg-clip-text text-transparent">

                                                            Generative UI

                                                        </p>

                                                    </div>

                                                </motion.div>



                                                {/* Animated Capability Badges - Functional & Tamed */}

                                                <motion.div

                                                    initial={{ y: 20, opacity: 0 }}

                                                    animate={{ y: 0, opacity: 1 }}

                                                    transition={{ delay: 1.2, duration: 0.6 }}

                                                    className="flex flex-wrap justify-center gap-3 mb-4"

                                                >

                                                    {([] as Array<{ label: string; prompt: string; color: string; icon: string }>).map((feature, i) => (

                                                        <motion.button

                                                            key={feature.label}

                                                            initial={{ scale: 0, opacity: 0 }}

                                                            animate={{ scale: 1, opacity: 1 }}

                                                            transition={{

                                                                delay: 1.3 + i * 0.1,

                                                                type: "spring",

                                                                stiffness: 260,

                                                                damping: 20

                                                            }}

                                                            onClick={() => {

                                                                setQuestion(feature.prompt);

                                                                textareaRef.current?.focus();

                                                            }}

                                                            whileHover={{

                                                                scale: 1.05,

                                                                y: -2,

                                                                backgroundColor: feature.color + '15', // Subtle tint on hover

                                                                borderColor: feature.color + '40',

                                                                boxShadow: `0 4px 20px ${feature.color}10`

                                                            }}

                                                            whileTap={{ scale: 0.95 }}

                                                            className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm cursor-pointer transition-all group"

                                                            style={{

                                                                background: 'rgba(255, 255, 255, 0.02)', // Very subtle default

                                                                border: '1px solid rgba(255, 255, 255, 0.05)',

                                                            }}

                                                        >

                                                            <span className="text-lg opacity-60 group-hover:opacity-100 transition-opacity grayscale group-hover:grayscale-0">{feature.icon}</span>

                                                            <span className="text-slate-400 font-medium group-hover:text-slate-100 transition-colors">{feature.label}</span>

                                                            <motion.div

                                                                className="w-1.5 h-1.5 rounded-full opacity-20 group-hover:opacity-100 transition-all"

                                                                style={{ backgroundColor: feature.color }}

                                                            />

                                                        </motion.button>

                                                    ))}

                                                </motion.div>

                                            </motion.div>



                                            {/* CSS Animation for gradient shift */}

                                            <style>{`

                                                            @keyframes gradientShift {

                                                                0%, 100% { background-position: 0% 50%; }

                                                                50% { background-position: 100% 50%; }

                                                            }

                                                        `}</style>

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

                                    {/* A2UI Surface - Wrapped with LayoutProvider for LLM-driven layout control */}
                                    {surface?.root && (
                                        <DashboardWithLayout key={dashboardId}>
                                            <A2UISurface
                                                key={`surface-${dashboardId}`}
                                                surface={surface}
                                                dataModel={dataModel}
                                                onAction={handleAction}
                                            />

                                            {/* Follow-up Suggestions */}
                                            {streamState.isDone && followUpSuggestions.length > 0 && (
                                                <div className="mt-4">
                                                    <FollowUpSuggestions
                                                        suggestions={followUpSuggestions}
                                                        anomalies={anomalies}
                                                        onSelect={handleFollowUpSelect}
                                                    />
                                                </div>
                                            )}
                                        </DashboardWithLayout>
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
                                                handleInput();
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
                                        placeholder={isMobile ? "Ask about stocks..." : "Ask about AMD, NVDA, INTC, QCOM, MU, AVGO, or TXN..."}
                                        rows={1}
                                        className="w-full px-4 py-3 bg-transparent resize-none outline-none text-sm"
                                        style={{ color: theme.colors.text.primary, minHeight: '48px' }}
                                    />
                                </div>

                                {/* Smart Generate/Stop Button */}
                                <AnimatePresence mode="wait">
                                    {streamState.isConnected ? (
                                        // Stop Button (during streaming)
                                        <motion.button
                                            key="stop"
                                            initial={{ scale: 0.8, opacity: 0 }}
                                            animate={{ scale: 1, opacity: 1 }}
                                            exit={{ scale: 0.8, opacity: 0 }}
                                            onClick={() => streamActions.close()}
                                            className="px-6 py-3 rounded-xl font-semibold transition-all flex items-center gap-2"
                                            style={{
                                                background: `linear-gradient(135deg, ${theme.colors.status.error}, #dc2626)`,
                                                color: 'white',
                                                boxShadow: '0 0 20px rgba(239, 68, 68, 0.4)',
                                            }}
                                            whileHover={{ scale: 1.05 }}
                                            whileTap={{ scale: 0.95 }}
                                        >
                                            <motion.div
                                                className="w-4 h-4 rounded-sm"
                                                style={{ backgroundColor: 'white' }}
                                                animate={{ scale: [1, 0.8, 1] }}
                                                transition={{ duration: 0.5, repeat: Infinity }}
                                            />
                                            Stop
                                        </motion.button>
                                    ) : (
                                        // Generate Button
                                        <motion.button
                                            key="generate"
                                            initial={{ scale: 0.8, opacity: 0 }}
                                            animate={{ scale: 1, opacity: 1 }}
                                            exit={{ scale: 0.8, opacity: 0 }}
                                            onClick={() => handleInput()}
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
                                                <span className="flex items-center gap-2">
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                                    </svg>
                                                    Generate
                                                </span>
                                            )}
                                        </motion.button>
                                    )}
                                </AnimatePresence>

                                {/* New Query Button (only when dashboard exists) */}
                                <AnimatePresence>
                                    {dashboardId && !streamState.isConnected && (
                                        <motion.button
                                            initial={{ opacity: 0, x: 20 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            exit={{ opacity: 0, x: 20 }}
                                            onClick={handleReset}
                                            className="px-4 py-3 rounded-xl font-medium transition-all flex items-center gap-2 group"
                                            style={{
                                                backgroundColor: theme.colors.bg.tertiary,
                                                border: `1px solid ${theme.colors.border.subtle}`,
                                                color: theme.colors.text.secondary,
                                            }}
                                            whileHover={{
                                                backgroundColor: theme.colors.bg.elevated,
                                                borderColor: theme.colors.accent.primary + '50',
                                            }}
                                            whileTap={{ scale: 0.95 }}
                                        >
                                            <svg className="w-4 h-4 transition-transform group-hover:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                            </svg>
                                            New Query
                                        </motion.button>
                                    )}
                                </AnimatePresence>
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

                            {/* Rate Limiter Status Bar */}
                            <div className="mt-auto pt-3 border-t border-white/5 flex justify-between items-center text-xs text-gray-400">
                                <div className="flex items-center gap-2">
                                    {authState.user ? (
                                        <>
                                            <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
                                            <span className="font-medium text-slate-300">Member</span>
                                            <span className="text-slate-500">•</span>
                                            <span className="font-mono text-slate-400">{usageStats ? `${usageStats.current_usage}/${usageStats.limit}` : '--/--'} requests</span>
                                            <button
                                                onClick={() => authService.signOut()}
                                                className="ml-2 text-rose-400 hover:text-rose-300 transition-colors font-medium hover:underline decoration-rose-500/30 underline-offset-2"
                                            >
                                                Sign out
                                            </button>
                                        </>
                                    ) : (
                                        <>
                                            <div className="w-1.5 h-1.5 bg-amber-500 rounded-full shadow-[0_0_8px_rgba(245,158,11,0.5)]"></div>
                                            <span className="font-medium text-slate-300">Guest</span>
                                            <span className="text-slate-500">•</span>
                                            <span className="font-mono text-slate-400">{usageStats ? `${usageStats.current_usage}/${usageStats.limit}` : '--/--'} requests</span>
                                            <button
                                                onClick={() => setShowAuthModal(true)}
                                                className="ml-2 text-amber-400 hover:text-amber-300 transition-colors font-medium hover:underline decoration-amber-500/30 underline-offset-2"
                                            >
                                                Sign in
                                            </button>
                                        </>
                                    )}
                                </div>
                            </div>

                        </div>
                    </div>
                </div>

                {/* Floating Tooltip Portal */}
                {activeTooltip && (() => {
                    const colors: any = {
                        blue: { tooltipTitle: 'text-blue-300', tooltipDot: 'bg-blue-400', tooltipBorder: 'border-blue-500/30', tooltipGradient: 'from-blue-500/5 to-purple-500/5' },
                        orange: { tooltipTitle: 'text-orange-300', tooltipDot: 'bg-orange-400', tooltipBorder: 'border-orange-500/30', tooltipGradient: 'from-orange-500/5 to-red-500/5' },
                        emerald: { tooltipTitle: 'text-emerald-300', tooltipDot: 'bg-emerald-400', tooltipBorder: 'border-emerald-500/30', tooltipGradient: 'from-emerald-500/5 to-teal-500/5' },
                        rose: { tooltipTitle: 'text-rose-300', tooltipDot: 'bg-rose-400', tooltipBorder: 'border-rose-500/30', tooltipGradient: 'from-rose-500/5 to-pink-500/5' },
                        cyan: { tooltipTitle: 'text-cyan-300', tooltipDot: 'bg-cyan-400', tooltipBorder: 'border-cyan-500/30', tooltipGradient: 'from-cyan-500/5 to-blue-500/5' },
                    }[activeTooltip.color] || { tooltipTitle: 'text-slate-300', tooltipDot: 'bg-slate-400', tooltipBorder: 'border-slate-500/30', tooltipGradient: 'from-slate-500/5 to-gray-500/5' };

                    return (
                        <div
                            className={`fixed z-[100] w-64 p-3 bg-slate-900/90 backdrop-blur-xl border rounded-lg shadow-2xl transition-opacity duration-200 pointer-events-none text-left whitespace-normal ${colors.tooltipBorder}`}
                            style={{
                                left: activeTooltip.x,
                                top: activeTooltip.y - 12,
                                transform: 'translate(-50%, -100%)'
                            }}
                        >
                            <div className="flex items-center justify-between mb-1">
                                <span className={`text-xs font-mono font-bold tracking-wider ${colors.tooltipTitle}`}>INFO</span>
                                <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${colors.tooltipDot}`}></span>
                            </div>
                            <div className="text-xs text-slate-300 leading-relaxed">
                                {activeTooltip.content}
                            </div>
                            <div className={`absolute inset-0 rounded-lg bg-gradient-to-tr pointer-events-none ${colors.tooltipGradient}`} />
                        </div>
                    );
                })()}

                {/* Debug Panel Portal */}
                {renderDebugPanel()}
            </div>

            {/* Clarification Overlay - OUTSIDE main container to escape stacking context */}
            <ClarificationOverlay
                request={clarificationRequest}
                onSubmit={handleClarificationSubmit}
                onDismiss={handleClarificationDismiss}
                fullScreen={!clarificationRequest?.targetComponentId}
            />

            {/* Authentication Modal */}
            <AuthModal
                isOpen={showAuthModal}
                onClose={() => setShowAuthModal(false)}
                onSuccess={() => {
                    setShowAuthModal(false);
                    fetchUsageStats();
                }}
            />
        </>
    );
}

export default GenerativeUIPage;
