export type FlowMode = 'planner-executor' | 'single-agent' | 'multi-agent';

export interface FlowVisualTheme {\n  id: FlowMode;\n  accent: string;\n  nodeGradient: [string, string];\n  nodeBorder: string;\n  nodeGlow: string;\n  edgeIdle: string;\n  edgeActive: string;\n  edgeCompleted: string;\n  badgeClass: string;\n  pulseClass: string;\n}\n\n// Shared types for analytics components

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
}

export interface AgentTurnTelemetry {
  role: string;
  status: 'start' | 'complete' | string;
  ts?: string;
  elapsed_ms?: number;
  summary?: Record<string, any> | string;
  sequence?: number;
  parallelGroup?: string;
  latencyBudgetMs?: number;
  concurrencyLimit?: number;
  outputArtifacts?: string[];
  lane?: string;
  reused?: boolean;
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
export interface WebSearchTopic {
  label?: string;
  query: string;
  reason?: string;
  summary?: string;
  search_id?: string;
  latency_ms?: number | null;
  snippets: Array<{
    title?: string;
    url?: string;
    snippet?: string;
    display_url?: string;
    published_at?: string;
  }>;
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
  latencyMs?: number | null;
  ready?: boolean;
  error?: string;
  reason?: string;
  provider?: string;
  model?: string;
  latencyStats?: { total_ms?: number; p50_ms?: number; max_ms?: number; min_ms?: number; samples?: number };
}

export interface AnalysisOverview {
  tldr?: string;
  highlights?: string[];
  keyNumbers?: string[];
  riskWatch?: string[];
  nextSteps?: string[];
  evidence?: AnalysisEvidenceLink[];
}

export interface AnalysisEvidenceLink {
  sourceUrl: string;
  title?: string;
  displayUrl?: string;
  snippet?: string;
  claim?: string;
  publishedAt?: string;
  confidence?: number;
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
  parallelGroup?: string;
  reused?: boolean;
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

export interface ProcessStepDetails {
  sql?: string;
  template?: string;
  template_used?: string;
  row_count?: number;
  rowCount?: number; // Alternative naming
  sample_data?: any[];
  sampleData?: any[]; // Alternative naming
  error?: string;
  args?: any;
  args_summary?: string;
  duration_ms?: number;
  success?: boolean;
  sql_executed?: string;
  columns?: string[];
  confidence?: number;
  category?: string;
  is_financial?: boolean;
  intent_key?: string;
  available_tools?: string[];
  strategy?: string;
  reasoning?: string;
  tool?: string;
  args_preview?: string;
  result?: any;
  sql_length?: number;
  tool_calls?: ToolCallTelemetry[];
  agent_turns?: AgentTurnTelemetry[];
  agent_reasoning?: AgentReasoningTelemetry[];
  tool_manifest?: ToolFanoutManifest[];
  tool_fanout_results?: ToolFanoutResult[];
  concurrency_limit?: number;
  stock_widget?: StockWidgetConfig;
  banner?: FollowUpBanner;
  analysis_overview?: AnalysisOverview;
  specialist_card?: SpecialistCard;
  latency_guardrail?: LatencyGuardrail;
  lane?: string;
  parallel_group?: string;
  reused?: boolean;
  final_answer_only?: boolean;
  missing_components?: string[];
  follow_up_route?: string;
  analysis_available?: boolean;
  final_answer_message?: string;
}

export interface ProcessStep {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'stopped';
  thinking: string[];
  details?: ProcessStepDetails;
  elapsed_ms?: number;
  timestamp?: string;
  sequence?: number;
  parallelGroup?: string;
  scheduleStage?: string;
  flowMode?: FlowMode;
  lane?: string;
  reused?: boolean;
  finalAnswerOnly?: boolean;
  missingComponents?: string[];
  followUpRoute?: string;
  analysisAvailable?: boolean;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'clarification' | 'result' | 'assistant';
  content: string;
  flowMode?: FlowMode;
  timestamp: string;
  clarifications?: ClarifyRequest[];
  answers?: Record<string, any>;
  analysis?: string;
  chartSpec?: any;
  sqlQuery?: string;
  dataSample?: any[];
  stockWidgetConfig?: StockWidgetConfig | null;
  toolFanoutManifest?: ToolFanoutManifest[];
  toolFanoutResults?: ToolFanoutResult[];
  webSearch?: WebSearchResult | null;
  analysisOverview?: AnalysisOverview | null;
  banner?: FollowUpBanner | null;
  specialistCards?: SpecialistCard[];
  latencyGuardrail?: LatencyGuardrail | null;
}

export interface ClarifyRequest {
  session_id: string;
  request_id: string;
  slot: string;
  question: string;
  type: 'single' | 'multi' | 'free';
  options: string[];
  default: any;
  proposed?: any;
  proposed_confidence?: number;
  reason?: string;
  required: boolean;
}

export interface ClarifyAnswer {
  session_id: string;
  request_id: string;
  slot: string;
  value: any;
  ts: string;
}

// Component Props
export interface HeaderProps {
  title: string;
  description: string;
  technologies: string[];
  imageUrl?: string;
  showProcessPanel?: boolean;
  onToggleProcess?: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export interface ChartCardProps {
  chartSpec: any;
  dataSample?: any[] | null;
  useAltChart?: boolean;
  height?: string;
  onError?: (error: any) => void;
  enableDropdown?: boolean;
  enableCsvDownload?: boolean;
}

export interface ProcessPanelProps {
  singleAgentFanout?: SingleAgentFanout | null;
  steps: ProcessStep[];
  flowMode: FlowMode;
  layoutMode?: 'sequential' | 'lanes';
  showVisualization?: boolean;
  show: boolean;
  onClose: () => void;
  showElapsedTime?: boolean;
  followUpBanner?: FollowUpBanner | null;
}

export interface PromptBarProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop?: () => void;
  isLoading: boolean;
  disabled?: boolean;
  placeholder?: string;
  showProcessToggle: boolean;
  onToggleProcess: () => void;
  suggestedQueries?: string[];
}

export interface AnalysisCardProps {
  analysis: string;
}

export interface SqlCardProps {
  sqlQuery: string;
  compact?: boolean;
  showCopy?: boolean;
}

export interface SuggestedQueriesProps {
  queries: string[];
  onPick: (query: string) => void;
}

export interface ClarificationOptionsProps {
  clarification: ClarifyRequest;
  onSubmit: (value: any) => Promise<void>;
  disabled?: boolean;
}

export interface ChatHistoryProps {
  messages: ChatMessage[];
  isLoading?: boolean;
  onSubmitClarification?: (value: any, request: ClarifyRequest) => Promise<void>;
  processSteps?: ProcessStep[];
}

// Hook State Types
export interface AnalyticsState {
  isLoading: boolean;
  error: string;
  chartSpec: any | null;
  analysis: string;
  sqlQuery: string;
  dataSample: any[] | null;
  currentStatus: string;
  useAltChart: boolean;
  streamingText: string;
}

export interface AnalyticsMemoryState extends AnalyticsState {
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





