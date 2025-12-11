/**
 * Function: ProcessPanel — Agent thinking process visualization panel with flowchart diagram
 * Called from: ConversationalAnalyticsPage header (replaces "Connected" status)
 * Invokes: Renders flowchart-style diagram with expandable nodes including Skill section
 * Purpose: Shows real-time agent decision flow with expandable full-screen canvas
 * 
 * 2025 Design Patterns Applied:
 * - Flowchart-style vertical layout with SVG connectors
 * - Expandable nodes with progressive disclosure
 * - Integrated skill visualization (moved from ThinkingProcessBar)
 * - Real-time status animations
 * - Hierarchical tree for multi-agent, linear flow for single-agent
 */

import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ProcessNode, ProcessEdge, AgentInfo, SkillInfo, DebugLog } from './hooks/useSSEStream';
import { theme, motionVariants } from './styles';
import { configService } from '../../services/config';

interface ProcessPanelProps {
  isStreaming: boolean;
  processNodes: ProcessNode[];
  processEdges: ProcessEdge[];
  activeAgent: AgentInfo | null;
  agentMode: string;
  skillInfo?: SkillInfo | null;
  debugLogs: DebugLog[];
  lastAgentLabel?: string | null;
  runId?: string | null;
  permissionState?: string | null;
}

// Node type configuration with icons and colors
const NODE_CONFIG: Record<ProcessNode['node_type'], { icon: string; color: string; bgColor: string; label: string }> = {
  input: { icon: '📥', color: '#3b82f6', bgColor: 'rgba(59, 130, 246, 0.15)', label: 'Input' },
  decision: { icon: '🔀', color: '#f59e0b', bgColor: 'rgba(245, 158, 11, 0.15)', label: 'Decision' },
  action: { icon: '⚡', color: '#8b5cf6', bgColor: 'rgba(139, 92, 246, 0.15)', label: 'Action' },
  tool: { icon: '🔧', color: '#06b6d4', bgColor: 'rgba(6, 182, 212, 0.15)', label: 'Tool' },
  agent: { icon: '🤖', color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.15)', label: 'Agent' },
  routing: { icon: '🔄', color: '#ec4899', bgColor: 'rgba(236, 72, 153, 0.15)', label: 'Routing' },
  output: { icon: '📤', color: '#22c55e', bgColor: 'rgba(34, 197, 94, 0.15)', label: 'Output' },
};

const STATUS_CONFIG: Record<ProcessNode['status'], { color: string; icon: string; label: string }> = {
  pending: { color: '#64748b', icon: '○', label: 'Pending' },
  running: { color: '#f59e0b', icon: '●', label: 'Running' },
  completed: { color: '#10b981', icon: '✓', label: 'Completed' },
  error: { color: '#ef4444', icon: '✕', label: 'Error' },
  skipped: { color: '#94a3b8', icon: '–', label: 'Skipped' },
};

// SVG Connector Component for flowchart-style connections
const FlowConnector: React.FC<{
  animated?: boolean;
  color?: string;
  type?: 'vertical' | 'branch-left' | 'branch-right';
}> = ({ animated = false, color = theme.colors.border.medium, type = 'vertical' }) => {
  if (type === 'vertical') {
    return (
      <div className="flex justify-center" style={{ height: 24 }}>
        <svg width="2" height="24" className="overflow-visible">
          <line
            x1="1" y1="0" x2="1" y2="24"
            stroke={color}
            strokeWidth="2"
            strokeDasharray={animated ? "4 2" : "none"}
          >
            {animated && (
              <animate
                attributeName="stroke-dashoffset"
                from="0"
                to="-12"
                dur="0.5s"
                repeatCount="indefinite"
              />
            )}
          </line>
          {/* Arrow */}
          <polygon points="-3,20 1,24 5,20" fill={color} />
        </svg>
      </div>
    );
  }
  return null;
};

// Skill Details Panel Component (moved from ThinkingProcessBar)
const SkillDetailsPanel: React.FC<{
  skill: SkillInfo;
  isExpanded: boolean;
}> = ({ skill, isExpanded }) => {
  const [activeTab, setActiveTab] = useState<'current' | 'what'>('current');
  const [skillContent, setSkillContent] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isExpanded && skill && !skillContent) {
      setIsLoading(true);
      const backendUrl = configService.getBackendUrl();
      fetch(`${backendUrl}/api/conv-analytics/skills/${skill.id}`)
        .then(res => res.text())
        .then(content => {
          setSkillContent(content);
          setIsLoading(false);
        })
        .catch(() => {
          setSkillContent('Failed to load skill content.');
          setIsLoading(false);
        });
    }
  }, [isExpanded, skill, skillContent]);

  useEffect(() => {
    setSkillContent(null);
  }, [skill?.id]);

  if (!isExpanded) return null;

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.25 }}
      className="overflow-hidden"
    >
      <div
        className="mt-3 rounded-xl overflow-hidden"
        style={{
          backgroundColor: theme.colors.bg.tertiary,
          border: `1px solid ${theme.colors.border.subtle}`,
        }}
      >
        {/* Tabs */}
        <div
          className="flex gap-1 px-3 py-2"
          style={{ borderBottom: `1px solid ${theme.colors.border.subtle}` }}
        >
          <button
            onClick={() => setActiveTab('current')}
            className="px-3 py-1.5 rounded-md text-xs font-medium transition-all"
            style={{
              backgroundColor: activeTab === 'current' ? theme.colors.accent.muted : 'transparent',
              color: activeTab === 'current' ? theme.colors.accent.primary : theme.colors.text.secondary,
            }}
          >
            Current Skill Details
          </button>
          <button
            onClick={() => setActiveTab('what')}
            className="px-3 py-1.5 rounded-md text-xs font-medium transition-all"
            style={{
              backgroundColor: activeTab === 'what' ? theme.colors.accent.muted : 'transparent',
              color: activeTab === 'what' ? theme.colors.accent.primary : theme.colors.text.secondary,
            }}
          >
            What is a Skill?
          </button>
        </div>

        {/* Content */}
        <div className="p-4 max-h-[300px] overflow-y-auto">
          <AnimatePresence mode="wait">
            {activeTab === 'current' ? (
              <motion.div
                key="current"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                transition={{ duration: 0.15 }}
              >
                {isLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="flex items-center gap-2">
                      <motion.div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: theme.colors.accent.primary }}
                        animate={{ scale: [1, 1.2, 1] }}
                        transition={{ duration: 0.6, repeat: Infinity }}
                      />
                      <span className="text-xs" style={{ color: theme.colors.text.secondary }}>Loading...</span>
                    </div>
                  </div>
                ) : (
                  <div 
                    className="prose prose-sm max-w-none prose-invert
                      prose-headings:text-slate-100 prose-headings:font-semibold
                      prose-h1:text-base prose-h2:text-sm prose-h3:text-sm
                      prose-p:text-slate-300 prose-p:leading-relaxed prose-p:text-xs
                      prose-strong:text-amber-400 prose-strong:font-semibold
                      prose-ul:text-slate-300 prose-li:text-slate-300 prose-li:text-xs
                      prose-code:text-amber-400 prose-code:bg-slate-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
                      prose-hr:border-slate-700
                    "
                  >
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {skillContent || ''}
                    </ReactMarkdown>
                  </div>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="what"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.15 }}
              >
                <div className="space-y-3">
                  <div 
                    className="p-3 rounded-lg"
                    style={{ backgroundColor: theme.colors.bg.elevated }}
                  >
                    <h3 
                      className="text-sm font-semibold mb-1.5 flex items-center gap-2"
                      style={{ color: theme.colors.text.primary }}
                    >
                      <span style={{ color: theme.colors.accent.primary }}>📄</span>
                      What is a SKILL.md file?
                    </h3>
                    <p 
                      className="text-xs leading-relaxed mb-2"
                      style={{ color: theme.colors.text.secondary }}
                    >
                      A <strong style={{ color: theme.colors.text.primary }}>SKILL.md</strong> file is a 
                      structured markdown document that defines how the AI agent should handle specific 
                      types of requests. It acts as a "playbook" that guides the agent's behavior.
                    </p>
                    <a
                      href="https://code.claude.com/docs/en/skills"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs font-medium transition-colors"
                      style={{ color: theme.colors.status.info }}
                    >
                      <span>📚</span>
                      <span className="hover:underline">Learn more about Skills.md use →</span>
                    </a>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { icon: '🎯', title: 'Intent & Triggers', desc: 'Keywords that activate this skill' },
                      { icon: '🛡️', title: 'Guardrails', desc: 'Safety rules and constraints' },
                      { icon: '📊', title: 'Chart Guidance', desc: 'Visualization rules' },
                      { icon: '📰', title: 'News Hooks', desc: 'When to fetch context' },
                    ].map((item, idx) => (
                      <div 
                        key={idx}
                        className="p-3 rounded-lg"
                        style={{ backgroundColor: theme.colors.bg.elevated }}
                      >
                        <div className="text-xl mb-1">{item.icon}</div>
                        <h4 
                          className="text-xs font-medium mb-0.5"
                          style={{ color: theme.colors.text.primary }}
                        >
                          {item.title}
                        </h4>
                        <p 
                          className="text-[10px]"
                          style={{ color: theme.colors.text.muted }}
                        >
                          {item.desc}
                        </p>
                      </div>
                    ))}
                  </div>

                  <div 
                    className="p-3 rounded-lg border"
                    style={{ 
                      backgroundColor: theme.colors.thinking.bg,
                      borderColor: theme.colors.thinking.border,
                    }}
                  >
                    <p 
                      className="text-xs"
                      style={{ color: theme.colors.text.secondary }}
                    >
                      <strong style={{ color: theme.colors.accent.primary }}>💡</strong>{' '}
                      Skills ensure accurate, well-formatted responses using the right SQL, chart types, and data formats.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
};

// Flowchart Node Component with proper diagram styling
const FlowchartNode: React.FC<{
  node: ProcessNode;
  isExpanded: boolean;
  onToggle: () => void;
  isLast?: boolean;
  skillInfo?: SkillInfo | null;
  showSkillDetails?: boolean;
}> = ({ node, isExpanded, onToggle, isLast = false, skillInfo, showSkillDetails = false }) => {
  const config = NODE_CONFIG[node.node_type];
  const statusConfig = STATUS_CONFIG[node.status];
  const isSkillNode = node.node_id === 'skill_detection' || node.node_id === 'skill_active';
  const isSpecialistNode = node.node_id.startsWith('specialist_');
  const showSkill = isSkillNode && skillInfo && showSkillDetails;
  
  return (
    <div className="flex flex-col items-center">
      {/* Node Card */}
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md"
      >
        <motion.button
          onClick={onToggle}
          className="w-full relative group"
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
        >
          {/* Main Card */}
          <div
            className="flex items-center gap-4 p-4 rounded-xl transition-all"
            style={{
              backgroundColor: isExpanded ? config.bgColor : theme.colors.bg.elevated,
              border: `2px solid ${isExpanded ? config.color : theme.colors.border.subtle}`,
              boxShadow: node.status === 'running' ? `0 0 20px ${config.color}30` : 'none',
            }}
          >
            {/* Icon with status ring */}
            <div className="relative shrink-0">
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center text-xl"
                style={{ backgroundColor: config.bgColor }}
              >
                {config.icon}
              </div>
              {/* Status indicator */}
              <motion.div
                className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full border-2 flex items-center justify-center text-[10px] font-bold"
                style={{
                  backgroundColor: statusConfig.color,
                  borderColor: theme.colors.bg.elevated,
                  color: 'white',
                }}
                animate={node.status === 'running' ? { 
                  scale: [1, 1.2, 1],
                  boxShadow: [`0 0 0 0 ${statusConfig.color}`, `0 0 0 8px ${statusConfig.color}00`]
                } : {}}
                transition={{ duration: 1, repeat: node.status === 'running' ? Infinity : 0 }}
              >
                {statusConfig.icon}
              </motion.div>
            </div>
            
            {/* Content */}
            <div className="flex-1 min-w-0 text-left">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className="text-sm font-semibold"
                  style={{ color: theme.colors.text.primary }}
                >
                  {node.label}
                </span>
                <span
                  className="text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider font-medium"
                  style={{
                    backgroundColor: config.bgColor,
                    color: config.color,
                    border: `1px solid ${config.color}40`,
                  }}
                >
                  {config.label}
                </span>
                {isSpecialistNode && (
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                    style={{
                      backgroundColor: theme.colors.status.info + '20',
                      color: theme.colors.status.info,
                      border: `1px solid ${theme.colors.status.info}40`,
                    }}
                  >
                    Handoff
                  </span>
                )}
                {/* Skill badge if this is a skill node */}
                {isSkillNode && skillInfo && (
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full font-medium flex items-center gap-1"
                    style={{
                      backgroundColor: theme.colors.accent.muted,
                      color: theme.colors.accent.primary,
                      border: `1px solid ${theme.colors.accent.primary}40`,
                    }}
                  >
                    ⚡ {skillInfo.name}
                  </span>
                )}
              </div>
              
              {node.description && (
                <p
                  className="text-xs mt-1 line-clamp-2"
                  style={{ color: theme.colors.text.muted }}
                >
                  {node.description}
                </p>
              )}
            </div>
            
            {/* Expand indicator */}
            {(node.data || (isSkillNode && skillInfo)) && (
              <motion.div
                className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center"
                style={{ backgroundColor: theme.colors.bg.tertiary }}
                animate={{ rotate: isExpanded ? 180 : 0 }}
                transition={{ duration: 0.2 }}
              >
                <span className="text-xs" style={{ color: theme.colors.text.muted }}>▼</span>
              </motion.div>
            )}
          </div>
        </motion.button>
        
        {/* Expanded Content */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="overflow-hidden"
            >
              {/* Skill Details (if skill node) */}
              {showSkill && (
                <SkillDetailsPanel skill={skillInfo} isExpanded={true} />
              )}
              
              {/* Node Data */}
              {node.data && !showSkill && (
                <div
                  className="mt-2 p-4 rounded-xl text-xs font-mono"
                  style={{
                    backgroundColor: theme.colors.bg.tertiary,
                    border: `1px solid ${theme.colors.border.subtle}`,
                  }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">📋</span>
                    <span
                      className="text-xs font-semibold"
                      style={{ color: theme.colors.text.secondary }}
                    >
                      Node Data
                    </span>
                  </div>
                  <pre
                    className="whitespace-pre-wrap break-words overflow-x-auto"
                    style={{ color: theme.colors.text.muted }}
                  >
                    {JSON.stringify(node.data, null, 2)}
                  </pre>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
      
      {/* Connector to next node */}
      {!isLast && (
        <FlowConnector 
          animated={node.status === 'running'} 
          color={node.status === 'completed' ? theme.colors.status.success : theme.colors.border.medium}
        />
      )}
    </div>
  );
};

/**
 * Function: ProcessPanel — Main component for agent process visualization
 * Shows a compact status indicator that expands to full-screen flowchart diagram
 */
const ProcessPanel: React.FC<ProcessPanelProps> = ({
  isStreaming,
  processNodes,
  processEdges,
  activeAgent,
  agentMode,
  skillInfo,
  debugLogs,
  lastAgentLabel,
  runId,
  permissionState,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [skillExpanded, setSkillExpanded] = useState(false);
  
  // Handle ESC key to close the panel
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isExpanded) {
        setIsExpanded(false);
      }
    };
    
    if (isExpanded) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isExpanded]);
  
  // Build node hierarchy from edges for multi-agent mode
  const { rootNodes, childrenMap } = useMemo(() => {
    const childrenMap = new Map<string, ProcessNode[]>();
    const hasParent = new Set<string>();
    
    processEdges.forEach(edge => {
      hasParent.add(edge.to_node);
      const children = childrenMap.get(edge.from_node) || [];
      const childNode = processNodes.find(n => n.node_id === edge.to_node);
      if (childNode) {
        children.push(childNode);
        childrenMap.set(edge.from_node, children);
      }
    });
    
    const rootNodes = processNodes.filter(n => !hasParent.has(n.node_id));
    return { rootNodes, childrenMap };
  }, [processNodes, processEdges]);
  
  // Sort nodes by timestamp for linear view
  const linearNodes = useMemo(() => {
    return [...processNodes].sort((a, b) => a.timestamp - b.timestamp);
  }, [processNodes]);
  
  // Count stats
  const stats = useMemo(() => {
    const running = processNodes.filter(n => n.status === 'running').length;
    const completed = processNodes.filter(n => n.status === 'completed').length;
    const total = processNodes.length;
    return { running, completed, total };
  }, [processNodes]);

  const isSingleAgent = agentMode === 'single' || !agentMode;
  const isMultiAgent = !isSingleAgent;
  
  const toggleNode = useCallback((nodeId: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);
  
  // Recursive render for hierarchical tree (multi-agent)
  const renderNodeTree = useCallback((nodes: ProcessNode[], depth: number = 0): React.ReactNode => {
    return nodes.map((node, idx) => {
      const children = childrenMap.get(node.node_id) || [];
      const isLast = idx === nodes.length - 1 && children.length === 0;
      const isSkillNode = node.node_id === 'skill_detection' || node.node_id === 'skill_active';
      
      return (
        <div key={node.node_id} style={{ marginLeft: depth > 0 ? 32 : 0 }}>
          <FlowchartNode
            node={node}
            isExpanded={expandedNodes.has(node.node_id)}
            onToggle={() => toggleNode(node.node_id)}
            isLast={isLast && children.length === 0}
            skillInfo={isSkillNode ? skillInfo : null}
            showSkillDetails={false} // Skill details now live in the top skill panel
          />
          {children.length > 0 && (
            <div className="mt-0">
              {renderNodeTree(children, depth + 1)}
            </div>
          )}
        </div>
      );
    });
  }, [childrenMap, expandedNodes, toggleNode, skillInfo]);

  // Lane grouping for multi-agent view
  const supervisorLaneNodes = useMemo(
    () => processNodes.filter(n => n.node_id.startsWith('supervisor') || n.node_id === 'auto_routing'),
    [processNodes]
  );
  const specialistLaneNodes = useMemo(
    () => processNodes.filter(n => !(n.node_id.startsWith('supervisor') || n.node_id === 'auto_routing')),
    [processNodes]
  );
  
  // Get current status text
  const statusText = useMemo(() => {
    if (!isStreaming && processNodes.length === 0) return 'Connected';
    if (isStreaming && stats.running > 0) return 'Processing...';
    if (stats.total > 0 && stats.completed === stats.total) return 'Complete';
    return 'Ready';
  }, [isStreaming, processNodes.length, stats]);
  
  return (
    <>
      {/* Compact Status Indicator */}
      <motion.button
        onClick={() => setIsExpanded(true)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all group"
        style={{
          backgroundColor: theme.colors.bg.elevated,
          border: `1px solid ${theme.colors.border.subtle}`,
        }}
        whileHover={{
          borderColor: theme.colors.accent.primary + '60',
          boxShadow: theme.shadows.glow,
        }}
        whileTap={{ scale: 0.98 }}
      >
        {/* Status dot */}
        <div className="relative">
          {isStreaming ? (
            <motion.div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: theme.colors.accent.primary }}
              animate={{ scale: [1, 1.3, 1], opacity: [1, 0.7, 1] }}
              transition={{ duration: 0.8, repeat: Infinity }}
            />
          ) : (
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: theme.colors.status.success }}
            />
          )}
        </div>
        
        <span className="text-xs" style={{ color: theme.colors.text.muted }}>
          {statusText}
        </span>
        
        {/* Removed badges for counts/skill to declutter header; skill lives in panel */}
        
        <motion.span
          className="text-xs opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ color: theme.colors.accent.primary }}
        >
          →
        </motion.span>
      </motion.button>
      
      {/* Full-screen Panel Overlay */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            className="fixed inset-0 z-50 flex flex-col"
            {...motionVariants.backdrop}
          >
            {/* Backdrop */}
            <motion.div
              className="absolute inset-0"
              style={{
                backgroundColor: 'rgba(10, 15, 26, 0.95)',
                backdropFilter: 'blur(8px)',
              }}
              onClick={() => setIsExpanded(false)}
            />
            
            {/* Panel Content */}
            <motion.div
              className="relative flex flex-col h-full max-w-3xl mx-auto w-full"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              transition={{ duration: 0.3 }}
            >
              {/* Header */}
              <header
                className="flex items-center justify-between px-6 py-4 shrink-0"
                style={{ borderBottom: `1px solid ${theme.colors.border.subtle}` }}
              >
                <div className="flex items-center gap-4">
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center"
                    style={{
                      background: `linear-gradient(135deg, ${theme.colors.accent.muted} 0%, ${theme.colors.bg.elevated} 100%)`,
                      border: `1px solid ${theme.colors.border.medium}`,
                    }}
                  >
                    <span className="text-2xl">🧠</span>
                  </div>
                  <div>
                    <h2
                      className="text-lg font-semibold"
                      style={{ color: theme.colors.text.primary }}
                    >
                      Agent Process Flow
                    </h2>
                    <p className="text-xs" style={{ color: theme.colors.text.muted }}>
                      {isSingleAgent ? 'Single Agent' : 'Multi-agent (Specialist routing)'}
                      {lastAgentLabel ? ` • Active: ${lastAgentLabel}` : activeAgent ? ` • Active: ${activeAgent.name}` : ''}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center gap-4">
                  {/* Stats */}
                  <div className="flex items-center gap-6">
                    <div className="text-center">
                      <div className="text-xl font-bold" style={{ color: theme.colors.status.success }}>
                        {stats.completed}
                      </div>
                      <div className="text-[10px] uppercase tracking-wide" style={{ color: theme.colors.text.muted }}>
                        Done
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-bold" style={{ color: theme.colors.accent.primary }}>
                        {stats.running}
                      </div>
                      <div className="text-[10px] uppercase tracking-wide" style={{ color: theme.colors.text.muted }}>
                        Active
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-bold" style={{ color: theme.colors.text.secondary }}>
                        {stats.total}
                      </div>
                      <div className="text-[10px] uppercase tracking-wide" style={{ color: theme.colors.text.muted }}>
                        Total
                      </div>
                    </div>
                  </div>
                  
                  {/* Close */}
                  <motion.button
                    onClick={() => setIsExpanded(false)}
                    className="w-10 h-10 rounded-xl flex items-center justify-center transition-colors"
                    style={{
                      backgroundColor: theme.colors.bg.elevated,
                      color: theme.colors.text.muted,
                    }}
                    whileHover={{
                      backgroundColor: theme.colors.bg.tertiary,
                      color: theme.colors.text.primary,
                    }}
                    whileTap={{ scale: 0.95 }}
                  >
                    ✕
                  </motion.button>
                </div>
              </header>
              
              {/* Flowchart Area */}
              <div className="flex-1 overflow-y-auto p-6">
                {processNodes.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full">
                    <div
                      className="w-24 h-24 rounded-2xl flex items-center justify-center text-5xl mb-6"
                      style={{
                        background: `linear-gradient(135deg, ${theme.colors.accent.muted} 0%, ${theme.colors.bg.tertiary} 100%)`,
                        border: `2px solid ${theme.colors.border.medium}`,
                      }}
                    >
                      {isStreaming ? (
                        <motion.span
                          animate={{ rotate: 360 }}
                          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                        >
                          🔄
                        </motion.span>
                      ) : '🧠'}
                    </div>
                    <h3
                      className="text-xl font-semibold mb-2"
                      style={{ color: theme.colors.text.primary }}
                    >
                      {isStreaming ? 'Initializing Agent...' : 'Agent Process Visualization'}
                    </h3>
                    <p
                      className="text-sm text-center max-w-md"
                      style={{ color: theme.colors.text.muted }}
                    >
                      {isStreaming
                        ? 'The agent is starting to process your request. Watch the flowchart build in real-time.'
                        : 'Send a message to see the agent\'s decision-making process visualized as an interactive flowchart.'}
                    </p>
                  </div>
                ) : (
                <div className="flex flex-col items-center space-y-4">
                  {/* Skill section replaces status legend */}
                  {skillInfo && (
                    <div
                      className="w-full max-w-2xl"
                    >
                      <button
                        onClick={() => setSkillExpanded(prev => !prev)}
                        className="w-full flex items-center justify-between px-4 py-3 rounded-xl transition-colors"
                        style={{
                          backgroundColor: theme.colors.bg.tertiary,
                          border: `1px solid ${theme.colors.border.subtle}`,
                        }}
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className="text-sm font-semibold px-2 py-1 rounded-lg"
                            style={{
                              backgroundColor: theme.colors.accent.muted,
                              color: theme.colors.accent.primary,
                            }}
                          >
                            ⚡ Active Skill: {skillInfo.name}
                          </span>
                          <span className="text-xs" style={{ color: theme.colors.text.muted }}>
                            Skill guidance is applied to the current run.
                          </span>
                        </div>
                        <motion.span
                          animate={{ rotate: skillExpanded ? 180 : 0 }}
                          transition={{ duration: 0.2 }}
                          className="text-sm"
                          style={{ color: theme.colors.text.muted }}
                        >
                          ▼
                        </motion.span>
                      </button>
                      <AnimatePresence>
                        {skillExpanded && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="mt-2"
                          >
                            <SkillDetailsPanel skill={skillInfo} isExpanded={true} />
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}

                  {/* Flowchart */}
                  {isSingleAgent ? (
                    // Linear flow for single agent
                    linearNodes.map((node, idx) => {
                      const isSkillNode = node.node_id === 'skill_detection' || node.node_id === 'skill_active';
                      return (
                        <FlowchartNode
                          key={node.node_id}
                          node={node}
                          isExpanded={expandedNodes.has(node.node_id)}
                          onToggle={() => toggleNode(node.node_id)}
                          isLast={idx === linearNodes.length - 1}
                          skillInfo={isSkillNode ? skillInfo : null}
                          showSkillDetails={isSkillNode && expandedNodes.has(node.node_id)}
                        />
                      );
                    })
                  ) : (
                    // Multi-lane layout: Supervisor | Specialist(s)
                    <div className="w-full grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="text-sm font-semibold" style={{ color: theme.colors.text.primary }}>
                            Supervisor Lane
                          </h4>
                          <span
                            className="text-[10px] px-2 py-0.5 rounded-full"
                            style={{
                              backgroundColor: theme.colors.accent.muted,
                              color: theme.colors.accent.primary,
                            }}
                          >
                            Routing + Handoff
                          </span>
                        </div>
                        {supervisorLaneNodes.length === 0 ? (
                          <p className="text-xs" style={{ color: theme.colors.text.muted }}>Waiting for supervisor routing...</p>
                        ) : (
                          renderNodeTree(supervisorLaneNodes)
                        )}
                      </div>
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="text-sm font-semibold" style={{ color: theme.colors.text.primary }}>
                            Specialist Lane
                          </h4>
                          {activeAgent && (
                            <span
                              className="text-[10px] px-2 py-0.5 rounded-full"
                              style={{
                                backgroundColor: theme.colors.bg.elevated,
                                color: theme.colors.text.secondary,
                                border: `1px solid ${theme.colors.border.subtle}`,
                              }}
                            >
                              Active: {activeAgent.name}
                            </span>
                          )}
                        </div>
                        {specialistLaneNodes.length === 0 ? (
                          <p className="text-xs" style={{ color: theme.colors.text.muted }}>Awaiting handoff...</p>
                        ) : (
                          renderNodeTree(specialistLaneNodes)
                        )}
                      </div>
                    </div>
                  )}
                </div>
                )}
              </div>
              
              {/* Footer */}
              <footer
                className="px-6 py-4 shrink-0 flex items-center justify-between"
                style={{ borderTop: `1px solid ${theme.colors.border.subtle}` }}
              >
                <button
                  onClick={() => {
                    const supervisorLogs = debugLogs.filter(log =>
                      log.category === 'agent' &&
                      ((log as any).data?.agent_mode === 'supervisor' ||
                        (log.message || '').toLowerCase().includes('supervisor'))
                    );
                    const specialistLogs = debugLogs.filter(log => {
                      const mode = (log as any).data?.agent_mode;
                      return log.category === 'agent' && mode && mode !== 'supervisor';
                    });
                    const payload = {
                      generated_at: new Date().toISOString(),
                      run_id: runId,
                      permission_state: permissionState,
                      blocked: permissionState ? ['permission_denied', 'run_timeout', 'cancelled'].includes(permissionState) : false,
                      process_nodes: processNodes,
                      process_edges: processEdges,
                      supervisor_logs: supervisorLogs,
                      specialist_logs: specialistLogs,
                      all_logs: debugLogs,
                    };
                    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'agent-debug-log.json';
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="px-3 py-2 rounded-lg text-xs font-semibold transition-colors"
                  style={{
                    backgroundColor: theme.colors.accent.muted,
                    color: theme.colors.text.primary,
                    border: `1px solid ${theme.colors.border.subtle}`,
                  }}
                >
                  Download JSON Logs
                </button>
                <div className="flex items-center gap-2">
                  <kbd
                    className="px-2 py-1 rounded text-[10px] font-mono"
                    style={{
                      backgroundColor: theme.colors.bg.elevated,
                      border: `1px solid ${theme.colors.border.subtle}`,
                      color: theme.colors.text.muted,
                    }}
                  >
                    Esc
                  </kbd>
                  <span className="text-xs" style={{ color: theme.colors.text.muted }}>to close</span>
                </div>
              </footer>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export default ProcessPanel;
