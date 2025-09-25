// Shared types for analytics components

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
}

export interface ProcessStep {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'stopped';
  thinking: string[];
  details?: ProcessStepDetails;
  elapsed_ms?: number;
  timestamp?: string;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'clarification' | 'result' | 'assistant';
  content: string;
  timestamp: string;
  clarifications?: ClarifyRequest[];
  answers?: Record<string, any>;
  analysis?: string;
  chartSpec?: any;
  sqlQuery?: string;
  dataSample?: any[];
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
  steps: ProcessStep[];
  show: boolean;
  onClose: () => void;
  showElapsedTime?: boolean;
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
