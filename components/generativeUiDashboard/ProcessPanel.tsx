// --- Function/Class Map ---
// Component: ProcessPanel
//   Role: Collapsible status panel with separated tabs and pipeline stages.
//   Called from: GenerativeUIPage.tsx
//   Invokes: onViewFullDebug callback
//   Why: Unified status/skill display. Reorder via natural language (no button).
// Component: StatusDot
//   Role: Animated status indicator.
// Component: ExpandableStage
//   Role: Clickable pipeline stage with detailed info (SQL, Layouts).
// --- End Function/Class Map ---

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// ============================================================================
// Types
// ============================================================================

export interface AuditEvent {
    id: string;
    type: 'skill_selected' | 'stream_started' | 'data_received' | 'layout_updated' | 'stream_complete' | 'error';
    label: string;
    timestamp: Date;
    details?: string;
}

export interface ProcessPanelProps {
    isExpanded: boolean;
    onToggle: () => void;
    /** Full data model for JSON export */
    fullDebugData?: Record<string, unknown>;
    streamState: {
        isConnected: boolean;
        isDone: boolean;
        isLoading?: boolean;
        connectionStatus?: string;
        surfaceCount: number;
        componentCount?: number;  // Actual widget count (not just surfaces)
        error?: string | null;
    };
    activeSkill: { id: string; name: string } | null;
    query: string;
    dashboardId: string | null;
    auditTrail: AuditEvent[];
    dataModel: Record<string, unknown>;
    onViewFullDebug: () => void;
}

// ============================================================================
// Theme (matching main page)
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
            info: '#38bdf8',
            positive: '#10b981',
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
            ready: '#10b981',
            streaming: '#3b82f6',
            complete: '#22c55e',
            error: '#ef4444',
            idle: '#64748b',
        },
    },
};

// ============================================================================
// Skill Metadata (embedded from SkillSection)
// ============================================================================

const SKILL_METADATA: Record<string, {
    name: string;
    description: string;
    icon: string;
    tags: { label: string; color: 'positive' | 'info' | 'secondary' }[];
}> = {
    'a2ui_explain_move': {
        name: 'Explain Move',
        description: 'Analyzes price movements by correlating stock data with news events.',
        icon: '📊',
        tags: [
            { label: 'chart: candlestick', color: 'positive' },
            { label: 'data: news API', color: 'info' },
            { label: 'insight: AI', color: 'secondary' },
        ],
    },
    'a2ui_margin_analysis': {
        name: 'Margin Analysis',
        description: 'Deep dive into gross, operating, and net margin trends over time.',
        icon: '📈',
        tags: [
            { label: 'chart: line', color: 'positive' },
            { label: 'data: SQL', color: 'info' },
            { label: 'insight: AI', color: 'secondary' },
        ],
    },
    'a2ui_revenue_trend': {
        name: 'Revenue Trend',
        description: 'Historical revenue analysis with growth metrics and YoY comparisons.',
        icon: '💹',
        tags: [
            { label: 'chart: area', color: 'positive' },
            { label: 'data: SQL', color: 'info' },
            { label: 'insight: AI', color: 'secondary' },
        ],
    },
    'a2ui_peer_compare': {
        name: 'Peer Compare',
        description: 'Compares financial metrics across multiple companies with AI-powered analysis.',
        icon: '⚖️',
        tags: [
            { label: 'chart: line', color: 'positive' },
            { label: 'data: SQL', color: 'info' },
            { label: 'insight: AI', color: 'secondary' },
        ],
    },
    'ming_engine_bazi': {
        name: 'Ming Engine',
        description: 'Computes BaZi chart, interprets pillars, consults classical texts, and composes a personalized reading.',
        icon: '🔮',
        tags: [
            { label: 'chart: BaZi', color: 'positive' },
            { label: 'data: classical texts', color: 'info' },
            { label: 'insight: AI narrative', color: 'secondary' },
        ],
    },
};

// ============================================================================
// Embedded Skill Panel Component
// ============================================================================

interface SkillPanelEmbeddedProps {
    skillId: string;
    skillMeta: {
        name: string;
        description: string;
        icon: string;
        tags: { label: string; color: 'positive' | 'info' | 'secondary' }[];
    };
}

function SkillPanelEmbedded({ skillId, skillMeta }: SkillPanelEmbeddedProps) {
    const [showWhatIs, setShowWhatIs] = useState(false);

    const tagColorMap: Record<string, string> = {
        positive: theme.colors.accent.positive,
        info: theme.colors.accent.info,
        secondary: theme.colors.accent.secondary,
    };

    return (
        <div
            className="mb-4 rounded-xl overflow-hidden"
            style={{
                backgroundColor: theme.colors.bg.tertiary,
                border: `1px solid ${theme.colors.border.medium}`,
            }}
        >
            {/* Header */}
            <div
                className="flex items-center justify-between px-4 py-3"
                style={{
                    borderBottom: `1px solid ${theme.colors.border.subtle}`,
                    backgroundColor: 'rgba(0,0,0,0.2)',
                }}
            >
                <div className="flex items-center gap-2">
                    <span className="text-lg">{skillMeta.icon}</span>
                    <div>
                        <p className="text-xs font-bold" style={{ color: theme.colors.text.primary }}>
                            {skillMeta.name}
                        </p>
                        <p className="text-[10px]" style={{ color: theme.colors.text.muted }}>
                            SKILL.md • {skillId.replace('a2ui_', '')}
                        </p>
                    </div>
                </div>
                <button
                    onClick={() => setShowWhatIs(!showWhatIs)}
                    className="text-[10px] px-2 py-1 rounded hover:bg-white/5 transition-colors"
                    style={{ color: theme.colors.accent.info }}
                >
                    {showWhatIs ? 'Hide' : "What's this?"}
                </button>
            </div>

            {/* Description & Tags */}
            <div className="px-4 py-3">
                <p className="text-xs leading-relaxed mb-3" style={{ color: theme.colors.text.secondary }}>
                    {skillMeta.description}
                </p>
                <div className="flex flex-wrap gap-1.5">
                    {skillMeta.tags.map((tag) => (
                        <span
                            key={tag.label}
                            className="text-[10px] px-2 py-0.5 rounded"
                            style={{
                                backgroundColor: `${tagColorMap[tag.color]}22`,
                                color: tagColorMap[tag.color],
                            }}
                        >
                            {tag.label}
                        </span>
                    ))}
                </div>
            </div>

            {/* What is a Skill? Section */}
            <AnimatePresence>
                {showWhatIs && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        style={{ overflow: 'hidden' }}
                    >
                        <div
                            className="px-4 py-3 text-xs"
                            style={{
                                borderTop: `1px solid ${theme.colors.border.subtle}`,
                                backgroundColor: 'rgba(0,0,0,0.15)',
                            }}
                        >
                            <p className="font-medium mb-2" style={{ color: theme.colors.text.primary }}>
                                📄 What is a SKILL.md file?
                            </p>
                            <p className="leading-relaxed mb-2" style={{ color: theme.colors.text.secondary }}>
                                A <strong>SKILL.md</strong> file is a structured markdown document that defines how the AI
                                agent should handle specific types of requests. It acts as a "playbook" that guides the agent's behavior.
                            </p>
                            <a
                                href="https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials/create-custom-slash-commands"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1"
                                style={{ color: theme.colors.accent.info }}
                            >
                                📚 Learn more about Skills.md →
                            </a>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

// Stage definitions
const STAGES = [
    { id: 'query', label: 'Query', icon: '💬', eventTypes: ['stream_started'] as const },
    { id: 'skill', label: 'Skill', icon: '⚡', eventTypes: ['skill_selected'] as const },
    { id: 'data', label: 'Data', icon: '📊', eventTypes: ['data_received'] as const },
    { id: 'render', label: 'Render', icon: '🎨', eventTypes: ['layout_updated', 'stream_complete'] as const },
];

// ============================================================================
// Status Dot Component
// ============================================================================

interface StatusDotProps {
    status: 'idle' | 'ready' | 'streaming' | 'complete' | 'error';
}

function StatusDot({ status }: StatusDotProps) {
    const getColor = () => {
        switch (status) {
            case 'streaming': return theme.colors.status.streaming;
            case 'complete': return theme.colors.status.complete;
            case 'error': return theme.colors.status.error;
            case 'ready': return theme.colors.status.ready;
            default: return theme.colors.status.idle;
        }
    };

    const isAnimating = status === 'streaming';

    return (
        <div className="relative">
            {isAnimating && (
                <motion.div
                    className="absolute inset-[-4px] rounded-full"
                    animate={{
                        scale: [1, 1.5, 1],
                        opacity: [0.5, 0, 0.5],
                    }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
                    style={{ backgroundColor: getColor() }}
                />
            )}
            <motion.div
                className="w-3 h-3 rounded-full relative z-10"
                animate={isAnimating ? { scale: [1, 1.2, 1] } : {}}
                transition={{ duration: 1, repeat: Infinity }}
                style={{
                    backgroundColor: getColor(),
                    boxShadow: `0 0 8px ${getColor()}`,
                }}
            />
        </div>
    );
}

// ============================================================================
// Expandable Stage Component (Now with Rich Content)
// ============================================================================

interface ExpandableStageProps {
    stage: typeof STAGES[0];
    status: 'pending' | 'active' | 'complete';
    index: number;
    events: AuditEvent[];
    isOpen: boolean;
    onToggle: () => void;
    // Context props for rich content
    userQuery: string;
}

function ExpandableStage({ stage, status, index, events, isOpen, onToggle, userQuery: _userQuery }: ExpandableStageProps) {
    const isActive = status === 'active';
    const isComplete = status === 'complete';
    const hasEvents = events.length > 0;
    const [copied, setCopied] = useState(false);

    const handleCopy = (text: string) => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    // Simulate "Rich Content" based on stage
    const renderRichContent = () => {
        const panelStyle = {
            backgroundColor: theme.colors.bg.elevated,
            borderColor: theme.colors.border.medium,
            boxShadow: `0 4px 20px -2px rgba(0,0,0,0.3)`
        };

        if (stage.id === 'query') {
            const simulatedSQL = `SELECT * FROM financial_metrics\nWHERE ticker IN ('AMD', 'NVDA')\nAND period >= '2023-Q1'\nORDER BY period DESC;`;
            return (
                <div className="mt-3 mb-2 rounded-xl overflow-hidden border w-full md:w-80 transition-all"
                    style={panelStyle}>
                    <div className="flex items-center justify-between px-3 py-2 border-b" style={{ backgroundColor: 'rgba(0,0,0,0.2)', borderColor: theme.colors.border.subtle }}>
                        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-bold" style={{ color: theme.colors.text.muted }}>
                            <span>🤖 Generated SQL</span>
                        </div>
                        <button
                            onClick={(e) => { e.stopPropagation(); handleCopy(simulatedSQL); }}
                            className="text-[10px] px-2 py-1 rounded hover:bg-white/5 transition-colors flex items-center gap-1"
                            style={{ color: theme.colors.text.secondary }}
                        >
                            {copied ? (
                                <><span className="text-emerald-400">✓</span> Copied</>
                            ) : (
                                <><span>📋</span> Copy</>
                            )}
                        </button>
                    </div>
                    <div className="p-3 bg-black/20">
                        <pre className="font-mono text-xs whitespace-pre-wrap leading-relaxed" style={{ color: theme.colors.accent.info }}>
                            {simulatedSQL}
                        </pre>
                    </div>
                </div>
            );
        }
        if (stage.id === 'render') {
            return (
                <div className="mt-3 mb-2 rounded-xl overflow-hidden border w-full md:w-80 transition-all"
                    style={panelStyle}>
                    <div className="flex items-center justify-between px-3 py-2 border-b" style={{ backgroundColor: 'rgba(0,0,0,0.2)', borderColor: theme.colors.border.subtle }}>
                        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-bold" style={{ color: theme.colors.text.muted }}>
                            <span>🎨 UI Composition</span>
                        </div>
                    </div>
                    <div className="p-3 bg-black/20 space-y-2 text-xs">
                        <div className="flex justify-between border-b border-white/5 pb-1">
                            <span style={{ color: theme.colors.text.secondary }}>Layout</span>
                            <span className="font-medium" style={{ color: theme.colors.text.primary }}>DashboardGrid V2</span>
                        </div>
                        <div className="flex justify-between border-b border-white/5 pb-1">
                            <span style={{ color: theme.colors.text.secondary }}>Components</span>
                            <span className="font-medium" style={{ color: theme.colors.text.primary }}>MetricCard, Chart</span>
                        </div>
                        <div className="flex justify-between">
                            <span style={{ color: theme.colors.text.secondary }}>Theme</span>
                            <span className="font-medium" style={{ color: theme.colors.text.primary }}>Dark/Rose</span>
                        </div>
                    </div>
                </div>
            );
        }
        if (stage.id === 'skill') {
            return (
                <div className="mt-3 mb-2 rounded-xl overflow-hidden border w-full md:w-80 transition-all"
                    style={panelStyle}>
                    <div className="flex items-center justify-between px-3 py-2 border-b" style={{ backgroundColor: 'rgba(0,0,0,0.2)', borderColor: theme.colors.border.subtle }}>
                        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-bold" style={{ color: theme.colors.text.muted }}>
                            <span>⚡ Agent Decision</span>
                        </div>
                    </div>
                    <div className="p-3 bg-black/20 text-xs flex items-center justify-between">
                        <div>
                            <p style={{ color: theme.colors.text.secondary }}>Selected Skill</p>
                            <p className="font-bold text-sm" style={{ color: theme.colors.text.primary }}>Peer Compare</p>
                        </div>
                        <div className="text-right">
                            <p style={{ color: theme.colors.text.secondary }}>Confidence</p>
                            <p className="font-bold text-sm text-emerald-400">98.5%</p>
                        </div>
                    </div>
                </div>
            );
        }
        return null;
    };


    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1, type: 'spring', stiffness: 300 }}
            className="flex flex-col w-full sm:w-auto"
        >
            <div className="flex items-center gap-2">
                {/* Connector line */}
                {index > 0 && (
                    <motion.div
                        className="hidden sm:block w-6 h-0.5 rounded-full"
                        initial={{ scaleX: 0 }}
                        animate={{ scaleX: 1 }}
                        transition={{ delay: index * 0.1 + 0.1 }}
                        style={{
                            backgroundColor: isComplete || isActive
                                ? theme.colors.accent.primary
                                : theme.colors.border.medium,
                            transformOrigin: 'left',
                        }}
                    />
                )}
                {/* Clickable Pill */}
                <motion.button
                    onClick={onToggle}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium cursor-pointer w-full sm:w-auto transition-all"
                    animate={isActive ? {
                        boxShadow: [
                            `0 0 0px ${theme.colors.accent.glow}`,
                            `0 0 15px ${theme.colors.accent.glow}`,
                            `0 0 0px ${theme.colors.accent.glow}`,
                        ],
                    } : {}}
                    transition={{ duration: 2, repeat: Infinity }}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    style={{
                        backgroundColor: isComplete
                            ? theme.colors.accent.muted
                            : isActive
                                ? theme.colors.accent.primary + '30'
                                : theme.colors.bg.tertiary,
                        border: `1px solid ${isActive
                            ? theme.colors.accent.primary
                            : isComplete
                                ? theme.colors.accent.primary + '50'
                                : theme.colors.border.subtle
                            }`,
                        color: isComplete || isActive
                            ? theme.colors.accent.primary
                            : theme.colors.text.muted,
                    }}
                >
                    <span>{stage.icon}</span>
                    <span>{stage.label}</span>
                    {isComplete && <span className="text-[10px]">✓</span>}
                    {hasEvents && (
                        <motion.span
                            animate={{ rotate: isOpen ? 180 : 0 }}
                            className="ml-1 text-[10px]"
                        >
                            ▼
                        </motion.span>
                    )}
                </motion.button>
            </div>

            {/* Expanded Events & Details */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden ml-2 sm:ml-0 mt-2 w-full"
                    >
                        {/* Render Rich Content Details */}
                        {renderRichContent()}

                        <div className="space-y-1 pl-4 border-l-2" style={{ borderColor: theme.colors.accent.primary + '30' }}>
                            {events.map((event, idx) => (
                                <motion.div
                                    key={event.id}
                                    initial={{ opacity: 0, x: -5 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: idx * 0.05 }}
                                    className="flex items-center gap-2 px-2 py-1.5 rounded text-xs"
                                    style={{ backgroundColor: theme.colors.bg.tertiary }}
                                >
                                    <span>{event.type === 'error' ? '❌' : '🔹'}</span>
                                    <span className="flex-1" style={{ color: theme.colors.text.primary }}>
                                        {event.label}
                                    </span>
                                    <span className="text-[10px] font-mono" style={{ color: theme.colors.text.muted }}>
                                        {event.timestamp.toLocaleTimeString()}
                                    </span>
                                </motion.div>
                            ))}
                            {!hasEvents && !renderRichContent() && (
                                <p className="text-[10px] text-slate-500 italic pl-2">Pending...</p>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}

// ============================================================================
// Main Process Panel
// ============================================================================

export function ProcessPanel({
    isExpanded,
    onToggle,
    streamState,
    activeSkill,
    query,
    dashboardId,
    auditTrail,
    dataModel: _dataModel,
    onViewFullDebug,
}: ProcessPanelProps) {
    const [expandedStage, setExpandedStage] = useState<string | null>(null);

    // Determine current status
    const getStatus = (): StatusDotProps['status'] => {
        if (streamState.error) return 'error';
        if (streamState.isConnected) return 'streaming';
        if (streamState.isDone) return 'complete';
        if (dashboardId) return 'ready';
        return 'idle';
    };

    const status = getStatus();

    // Get skill metadata
    const skillId = activeSkill?.id || '';
    const skillMeta = SKILL_METADATA[skillId] || {
        name: skillId.replace('a2ui_', '').replace(/_/g, ' ') || 'Unknown',
        description: 'Processing your request...',
        icon: '⚡',
        tags: [],
    };

    // Determine stage statuses
    const getStageStatus = (stageId: string): 'pending' | 'active' | 'complete' => {
        if (!dashboardId) return stageId === 'query' ? 'active' : 'pending';

        switch (stageId) {
            case 'query':
                return dashboardId ? 'complete' : 'active';
            case 'skill':
                if (!activeSkill) return streamState.isConnected ? 'active' : 'pending';
                return 'complete';
            case 'data':
                if (streamState.isDone) return 'complete';
                if (activeSkill) return streamState.isConnected ? 'active' : 'pending';
                return 'pending';
            case 'render':
                return streamState.isDone ? 'complete' : 'pending';
            default:
                return 'pending';
        }
    };

    const getEventsForStage = (stage: typeof STAGES[0]): AuditEvent[] => {
        return auditTrail.filter(event =>
            (stage.eventTypes as readonly string[]).includes(event.type)
        );
    };

    const getStatusLabel = () => {
        if (streamState.error) return 'Error occurred';
        if (streamState.isConnected) return 'AI Analysis Streaming...';
        if (streamState.isDone) return 'Analysis Complete';
        if (dashboardId) return 'Processing...';
        return 'Ready';
    };

    return (
        <div className="relative">
            {/* Collapsed Bar (always visible) */}
            {dashboardId && (
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-4"
                >
                    <motion.button
                        onClick={onToggle}
                        className="w-full flex items-center justify-between px-4 py-3 rounded-xl transition-all group"
                        style={{
                            backgroundColor: theme.colors.bg.tertiary,
                            border: `1px solid ${status === 'streaming'
                                ? theme.colors.accent.primary + '50'
                                : theme.colors.border.medium
                                }`,
                        }}
                        whileHover={{ scale: 1.005 }}
                        whileTap={{ scale: 0.995 }}
                    >
                        <div className="flex items-center gap-4">
                            <StatusDot status={status} />
                            <div className="text-left">
                                <p className="text-xs font-semibold" style={{ color: theme.colors.text.primary }}>
                                    {getStatusLabel()}
                                </p>
                                {activeSkill && (
                                    <p className="text-[10px]" style={{ color: theme.colors.text.muted }}>
                                        {skillMeta.icon} {skillMeta.name} • {streamState.componentCount ?? streamState.surfaceCount} widgets
                                    </p>
                                )}
                            </div>
                        </div>

                        {/* Mini Stage Indicators (Visible when collapsed only) */}
                        {!isExpanded && (
                            <div className="hidden md:flex items-center gap-1">
                                {STAGES.map((stage, idx) => {
                                    const stageStatus = getStageStatus(stage.id);
                                    const connectorStyle = stageStatus !== 'pending' ? theme.colors.accent.primary : theme.colors.border.medium;
                                    const dotStyle = stageStatus === 'complete'
                                        ? theme.colors.status.complete
                                        : stageStatus === 'active'
                                            ? theme.colors.status.streaming
                                            : theme.colors.status.idle;
                                    return (
                                        <div key={stage.id} className="flex items-center">
                                            {idx > 0 && (
                                                <div
                                                    className="w-3 h-0.5 mx-1"
                                                    style={{ backgroundColor: connectorStyle }}
                                                />
                                            )}
                                            <div
                                                className={`w-2 h-2 rounded-full ${stageStatus === 'active' ? 'animate-pulse' : ''}`}
                                                style={{ backgroundColor: dotStyle }}
                                            />
                                        </div>
                                    );
                                })}
                            </div>
                        )}

                        <motion.div
                            animate={{ rotate: isExpanded ? 180 : 0 }}
                            transition={{ type: 'spring', stiffness: 300 }}
                            style={{ color: theme.colors.text.muted }}
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                        </motion.div>
                    </motion.button>
                </motion.div>
            )}

            {/* Expanded Panel */}
            <AnimatePresence>
                {isExpanded && dashboardId && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                        className="overflow-hidden mb-4"
                    >
                        <div
                            className="rounded-xl overflow-hidden"
                            style={{
                                backgroundColor: theme.colors.bg.secondary,
                                border: `1px solid ${theme.colors.border.medium}`,
                                maxHeight: '400px', // Limit height
                            }}
                        >
                            {/* Main Content Area (Scrollable) */}
                            <div className="p-4 overflow-y-auto" style={{ maxHeight: 'calc(500px - 100px)' }}>

                                {/* Embedded Skill Panel - Shows when skill is active */}
                                {activeSkill && (
                                    <SkillPanelEmbedded skillId={activeSkill.id} skillMeta={skillMeta} />
                                )}

                                {/* Pipeline Stages Section */}
                                <div>
                                    <p className="text-[10px] uppercase tracking-wider font-bold mb-3" style={{ color: theme.colors.text.muted }}>
                                        Pipeline Stages
                                    </p>
                                    <div className="flex flex-wrap items-start gap-x-2 gap-y-4">
                                        {STAGES.map((stage, idx) => (
                                            <ExpandableStage
                                                key={stage.id}
                                                stage={stage}
                                                status={getStageStatus(stage.id)}
                                                index={idx}
                                                events={getEventsForStage(stage)}
                                                isOpen={expandedStage === stage.id}
                                                onToggle={() => setExpandedStage(
                                                    expandedStage === stage.id ? null : stage.id
                                                )}
                                                userQuery={query}
                                            />
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {/* Actions Footer with JSON Download */}
                            <div className="flex items-center justify-between px-4 py-3 border-t"
                                style={{ borderColor: theme.colors.border.subtle, backgroundColor: theme.colors.bg.tertiary }}
                            >
                                <div className="flex items-center gap-4 text-xs" style={{ color: theme.colors.text.muted }}>
                                    <span>ID: {dashboardId?.slice(0, 8)}...</span>
                                    <span>{streamState.surfaceCount} surfaces</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    {/* JSON Download Button */}
                                    <button
                                        onClick={() => {
                                            // Extract tool use information from data model
                                            const dataModel = _dataModel as Record<string, unknown>;
                                            const data = (dataModel?.data || {}) as Record<string, unknown>;

                                            // Build tool use summary
                                            const toolUse: Record<string, unknown> = {
                                                tools: [] as string[],
                                            };

                                            // SQL/Database tool usage
                                            const table = data.table as Record<string, unknown> | undefined;
                                            if (table) {
                                                const rows = (table.rows as unknown[]) || [];
                                                const columns = (table.columns as unknown[]) || [];
                                                (toolUse.tools as string[]).push('sql_query');
                                                toolUse.sql = {
                                                    rowCount: rows.length,
                                                    columnCount: columns.length,
                                                    columns: columns.map((c: unknown) =>
                                                        typeof c === 'object' && c !== null ? (c as Record<string, unknown>).key || (c as Record<string, unknown>).label : c
                                                    ),
                                                    sampleData: rows.slice(0, 3), // First 3 rows as sample
                                                };
                                            }

                                            // Chart tool usage
                                            const chart = data.chart as Record<string, unknown> | undefined;
                                            if (chart) {
                                                (toolUse.tools as string[]).push('chart_generation');
                                                const series = (chart.series as unknown[]) || [];
                                                toolUse.chart = {
                                                    seriesCount: series.length,
                                                    series: series.map((s: unknown) => {
                                                        if (typeof s === 'object' && s !== null) {
                                                            const seriesObj = s as Record<string, unknown>;
                                                            return {
                                                                name: seriesObj.name,
                                                                dataPoints: Array.isArray(seriesObj.data) ? seriesObj.data.length : 0,
                                                            };
                                                        }
                                                        return null;
                                                    }).filter(Boolean),
                                                    hasAnnotations: !!chart.annotations,
                                                };
                                            }

                                            // News tool usage
                                            const news = data.news as Record<string, unknown> | undefined;
                                            if (news) {
                                                (toolUse.tools as string[]).push('news_fetch');
                                                const events = (news.events as unknown[]) || [];
                                                toolUse.news = {
                                                    eventCount: events.length,
                                                    events: events.slice(0, 5).map((e: unknown) => {
                                                        if (typeof e === 'object' && e !== null) {
                                                            const eventObj = e as Record<string, unknown>;
                                                            return {
                                                                title: eventObj.title,
                                                                date: eventObj.date,
                                                                sentiment: eventObj.sentiment,
                                                            };
                                                        }
                                                        return null;
                                                    }).filter(Boolean),
                                                };
                                            }

                                            // AI Analysis tool usage
                                            const explanation = data.explanation as Record<string, unknown> | undefined;
                                            if (explanation?.text) {
                                                (toolUse.tools as string[]).push('ai_analysis');
                                                toolUse.aiAnalysis = {
                                                    hasExplanation: true,
                                                    textLength: typeof explanation.text === 'string' ? explanation.text.length : 0,
                                                    hasFactors: !!explanation.factors,
                                                    hasCitations: !!explanation.citations,
                                                };
                                            }

                                            // KPIs
                                            const kpis = data.kpis as Record<string, unknown> | undefined;
                                            if (kpis) {
                                                toolUse.kpis = Object.keys(kpis);
                                            }

                                            const debugPayload = {
                                                exportedAt: new Date().toISOString(),
                                                dashboardId,
                                                query,
                                                activeSkill,
                                                streamState: {
                                                    isConnected: streamState.isConnected,
                                                    isDone: streamState.isDone,
                                                    connectionStatus: streamState.connectionStatus,
                                                    surfaceCount: streamState.surfaceCount,
                                                    componentCount: streamState.componentCount,
                                                    error: streamState.error,
                                                },
                                                // NEW: Structured tool use information
                                                toolUse,
                                                // Audit trail with tool execution events
                                                auditTrail: auditTrail.map(e => ({
                                                    ...e,
                                                    timestamp: e.timestamp.toISOString(),
                                                })),
                                                // Full data model for complete debugging
                                                dataModel: _dataModel,
                                            };
                                            const blob = new Blob([JSON.stringify(debugPayload, null, 2)], { type: 'application/json' });
                                            const url = URL.createObjectURL(blob);
                                            const a = document.createElement('a');
                                            a.href = url;
                                            a.download = `agent-debug-${dashboardId || 'session'}-${Date.now()}.json`;
                                            a.click();
                                            URL.revokeObjectURL(url);
                                        }}
                                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:scale-105"
                                        style={{
                                            backgroundColor: theme.colors.bg.elevated,
                                            border: `1px solid ${theme.colors.border.medium}`,
                                            color: theme.colors.text.secondary,
                                        }}
                                        title="Download all process details as JSON"
                                    >
                                        <span>📥</span>
                                        JSON
                                    </button>
                                    <button
                                        onClick={onViewFullDebug}
                                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:scale-105"
                                        style={{
                                            background: `linear-gradient(135deg, ${theme.colors.accent.primary}, ${theme.colors.accent.secondary})`,
                                            color: 'white',
                                        }}
                                    >
                                        <span>🔍</span>
                                        Full Debug
                                    </button>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

export default ProcessPanel;
