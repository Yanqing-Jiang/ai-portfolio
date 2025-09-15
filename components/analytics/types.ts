// Shared types for analytics components

export interface ProcessStep {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'stopped';
  thinking: string[];
  details?: any;
  elapsed_ms?: number;
  timestamp?: string;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'clarification' | 'result' | 'assistant' | 'approval_request';
  content: string;
  timestamp: string;
  clarifications?: ClarifyRequest[];
  answers?: Record<string, any>;
  analysis?: string;
  chartSpec?: any;
  sqlQuery?: string;
  dataSample?: any[];
  // Approval request fields
  approvalSessionId?: string;
  previewSql?: string;
  applyTargets?: string[];
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
  onApproveWorkflow?: (sessionId: string) => Promise<void>;
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