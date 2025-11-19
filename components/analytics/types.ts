export type FlowMode = 'planner-executor' | 'single-agent' | 'multi-agent';

export interface FlowVisualTheme {
  id: FlowMode;
  accent: string;
  nodeGradient: [string, string];
  nodeBorder: string;
  nodeGlow: string;
  edgeIdle: string;
  edgeActive: string;
  edgeCompleted: string;
  badgeClass: string;
  pulseClass: string;
}

// Shared types for analytics components

export interface ToolCallTelemetry {
  tool: string;
  status: 'start' | 'end' | string;
  ts?: string;
  elapsed_ms?: number;
  details?: Record<string, any>;
  sequence?: number;
  parallelGroup?: string;
  toolGroup?: string;
  latencyBudgetMs?: number;
  concurrencyLimit?: number;
  outputArtifacts?: string[];
  lane?: string;
  reused?: boolean;
  guardrail?: Record<string, any>;
}

export interface LaneReuseNotice {
  lane: string;
  message: string;
  reason?: string;
  ts?: string;
  ageSeconds?: number;
  source?: string;
  fastPathLatencyMs?: number;
  guardrail?: Record<string, any>;
}

export type FreshLanePhase = 'started' | 'completed' | 'failed';

export interface FreshLaneStatus {
  lane: string;
  status: FreshLanePhase;
  ts?: string;
  reason?: string;
  reasoningEffort?: string;
}

export interface AgentTurnTelemetry {
  id?: string;
  role: string;
  status: 'start' | 'complete' | string;
  ts?: string;
  elapsed_ms?: number;
  summary?: Record<string, any> | string;
  sequence?: number;
  parallelGroup?: string;
  tool?: string;
  specialist?: string;
  latencyBudgetMs?: number;
  concurrencyLimit?: number;
  outputArtifacts?: string[];
  lane?: string;
  reused?: boolean;
}

export interface AgentReasoningTelemetry {
  role: string;
  thought: string;
  ts?: string;
  sequence?: number;
  parallelGroup?: string;
}

export interface ToolFanoutManifest {
  name: string;
  display_name?: string;
  description?: string;
  preview_only?: boolean;
  capabilities?: string[];
  outputs?: string[];
  summary?: string;
  preview_keys?: string[];
  sample_metrics?: string[];
}

export interface ToolFanoutResult {
  tool: string;
  status: string;
  elapsed_ms?: number;
  started_at?: string | null;
  completed_at?: string | null;
  fatal?: boolean;
  error?: string | null;
  metadata?: Record<string, any>;
  payload?: Record<string, any>;
}


export type FanoutBranchStatus = 'queued' | 'running' | 'completed' | 'failed' | 'stopped';

export interface SingleAgentFanoutBranch {
  id: string;
  tool: string;
  label: string;
  description?: string;
  status: FanoutBranchStatus;
  startedAt?: string | null;
  completedAt?: string | null;
  elapsedMs?: number;
  error?: string | null;
  metadata?: Record<string, any>;
  payload?: Record<string, any>;
}

export interface SingleAgentFanout {
  hasFanout: boolean;
  branches: SingleAgentFanoutBranch[];
  concurrencyLimit?: number;
  activeCount: number;
  completedCount: number;
  failedCount: number;
  queuedCount: number;
  stoppedCount: number;
  runningCount: number;
  lastUpdated?: string;
}
export interface AgentEvidence {
  status: 'agent_run' | 'agent_disabled' | 'agent_fallback';
  turns?: AgentTurnTelemetry[];
  reason?: string;
}

export interface WebSearchTopic {
  label?: string;
  query: string;
  reason?: string;
  summary?: string;
  search_id?: string;
  latency_ms?: number | null;
  topic_index?: number | null;
  topicIndex?: number | null;
  topic_position?: number | null;
  topicPosition?: number | null;
  topic_label?: string;
  topicLabel?: string;
  display_name?: string;
  displayName?: string;
  question_kind?: string;
  questionKind?: string;
  snippets: Array<{
    title?: string;
    url?: string;
    snippet?: string;
    display_url?: string;
    published_at?: string;
  }>;
}

export type WebTopicBranchStatus = 'queued' | 'running' | 'ready' | 'error';

export interface WebTopicBranchProgress {
  id: string;
  questionKind?: string;
  label?: string;
  status: WebTopicBranchStatus;
  latencyMs?: number | null;
  startedAt?: string | null;
  completedAt?: string | null;
  error?: string | null;
}

export interface WebSearchTopicProgress {
  total: number;
  completed: number;
  pending: number;
  pendingSince?: string;
  lastUpdated?: string;
  guardrailStatus?: 'idle' | 'pending' | 'ready' | 'timeout';
  branches: Record<string, WebTopicBranchProgress>;
}

export interface WebSearchResult {
  query?: string;
  queryTerms?: string;
  searchTopic?: string;
  searchTopics?: string[];
  summary?: string;
  snippets: Array<{
    title?: string;
    url?: string;
    snippet?: string;
    display_url?: string;
    published_at?: string;
  }>;
  annotations?: Array<Record<string, any>>;
  topics?: WebSearchTopic[];
  searchId?: string;
  fromCache?: boolean;
  fetchedAt?: string;
  topicTotal?: number;
  topicIndex?: number | null;
  topicPosition?: number | null;
  topicLabel?: string;
  latencyMs?: number | null;
  ready?: boolean;
  error?: string;
  reason?: string;
  provider?: string;
  model?: string;
  latencyStats?: { total_ms?: number; p50_ms?: number; max_ms?: number; min_ms?: number; samples?: number };
  questions?: {
    keywordFocus?: string | null;
    user?: string | null;
    industry?: string | null;
  };
  topicProgress?: WebSearchTopicProgress | null;
}

export interface AnalysisSourceInsight {
  id: string;
  lane?: string;
  label?: string;
  summary?: string;
  reused?: boolean;
  rowCount?: number;
  columns?: string[];
  snippetCount?: number;
  symbols?: string[];
  latestClose?: number;
  changePercent?: number;
  topic?: string;
}

export type AnalysisSources = Record<string, AnalysisSourceInsight>;

export interface AnalysisEvidenceLink {
  sourceUrl: string;
  title?: string;
  displayUrl?: string;
  snippet?: string;
  claim?: string;
  publishedAt?: string;
  confidence?: number;
}

export interface AnalysisOverview {
  tldr?: string;
  highlights?: string[];
  keyNumbers?: string[];
  riskWatch?: string[];
  nextSteps?: string[];
  evidence?: AnalysisEvidenceLink[];
  sources?: AnalysisSources;
}

export interface LatencyGuardrail {
  status: 'ok' | 'violation';
  violations?: string[];
  observed?: {
    total_ms?: number;
    p50_ms?: number;
    p95_ms?: number;
    max_ms?: number;
    samples?: number;
  };
  thresholds: {
    p50_ms: number;
    p95_ms: number;
  };
}

export interface FollowUpBanner {
  title: string;
  message: string;
  route: string;
  flowMode?: FlowMode;
  finalAnswerOnly?: boolean;
  missingComponents?: string[];
  analysisAvailable?: boolean;
  summary?: string;
  refreshMode?: 'light' | 'full';
  reason?: string;
  questions?: {
    keywordFocus?: string | null;
    user?: string | null;
    industry?: string | null;
  };
}

export interface SpecialistCard {
  type: string;
  state?: string;
  title?: string;
  message?: string;
  topic?: string;
  summary?: string;
  snippets?: Array<{
    title?: string;
    snippet?: string;
    url?: string;
    display_url?: string;
    published_at?: string;
  }>;
  symbols?: string[];
  ready?: boolean;
  ts?: string;
  meta?: Record<string, any>;
  lane?: string;
  source?: string;
  parallelGroup?: string;
  reused?: boolean;
  sessionId?: string;
  revisionId?: string;
  revision?: boolean;
  revisionEvent?: boolean;
  payloadHash?: string;
}

export interface StockWidgetConfig {
  symbols: (string | [string, string])[];
  original?: string[];
  generated_at?: string;
  locale?: string;
  colorTheme?: 'light' | 'dark';
  height?: number;
  chartType?: string;
  showVolume?: boolean;
  showMA?: boolean;
  autosize?: boolean;
  bars?: {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[];
}

export interface ClarifyRequest {
  request_id: string;
  question: string;
  slot: string;
  reason?: string;
  options?: string[];
  allow_custom?: boolean;
  session_id?: string;
}

export interface ClarifyAnswer {
  session_id: string;
  request_id: string;
  slot: string;
  value: string;
  ts: string;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant' | 'result' | 'clarification';
  content: string;
  timestamp: string;
  chartSpec?: any;
  sqlQuery?: string | null;
  dataSample?: any[] | null;
  stockWidgetConfig?: StockWidgetConfig | null;
  toolFanoutManifest?: ToolFanoutManifest[];
  toolFanoutResults?: ToolFanoutResult[];
  webSearch?: WebSearchResult | null;
  analysisOverview?: AnalysisOverview | null;
  analysisSources?: AnalysisSources | null;
  analysisBundle?: Record<string, any> | null;
  banner?: FollowUpBanner | null;
  specialistCards?: SpecialistCard[];
  latencyGuardrail?: LatencyGuardrail | null;
  revision?: boolean;
  revisionId?: string;
  revisionFocus?: string | null;
  flowMode?: FlowMode;
  scheduleStage?: string;
  parallelGroup?: string;
  sequence?: number;
  clarifications?: ClarifyRequest[];
  analysis?: string;
  progressiveAnalysis?: string;
  progressiveText?: string;
}

export interface ProcessStep {
  id: string;
  label: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error';
  messages: string[];
  details?: Record<string, any>;
  elapsedMs?: number;
  ts?: string;
}

export interface SlotStatusPayload {
  status: 'missing' | 'filled' | 'confirmed';
  value?: any;
  reason?: string;
  suggestions?: string[];
  allow_custom?: boolean;
}

export type SlotStatusMap = Record<string, SlotStatusPayload>;

export interface AnalyticsMemoryState {
  sessionId: string;
  pendingClarification: ClarifyRequest | null;
  chatHistory: ChatMessage[];
}

export interface StepConfig {
  stepNames: Record<string, string>;
  stepOrder: string[];
}

// Project Data
export interface ProjectData {
  title: string;
  description: string;
  technologies: string[];
  imageUrl: string;
}
