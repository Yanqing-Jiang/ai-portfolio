// Shared constants for analytics pages

// Memory pipeline steps (streamlined agent-forward)
export const STEP_NAME: Record<string, string> = {
  classify: 'Topic Classification',
  intent_detection: 'Intent Detection',
  schema_validation: 'Schema & Criteria Validation',
  tool_execution: 'Agent Tool Execution',
  plan_and_select_template: 'Query Planning & Template Selection',
  planning: 'Supervisor Planning',
  clarification: 'Requirements Clarification',
  sql_compilation: 'SQL Compilation',
  sql_validation: 'SQL Validation',
  sql_execution: 'Data Retrieval',
  short_financial_analysis: 'Financial Analysis',
  chart_generation: 'Chart Generation',
  analysis_generation: 'Final Analysis',
  finalization: 'Workflow Finalization',
};

export const STEP_ORDER = [
  'classify',
  'intent_detection',
  'schema_validation',
  'tool_execution',
  'clarification',
  'plan_and_select_template',
  'planning',
  'sql_compilation',
  'sql_validation',
  'sql_execution',
  'short_financial_analysis',
  'chart_generation',
  'analysis_generation',
  'finalization',
];

// SQL pipeline steps (direct workflow)
export const STEP_NAME_SQL: Record<string, string> = {
  table: 'Table Selection',
  schema: 'Schema Analysis',
  sql: 'SQL Generation',
  chart: 'Chart Creation',
  analysis: 'Analysis Generation',
};

export const STEP_ORDER_SQL = [
  'table',
  'schema',
  'sql',
  'chart',
  'analysis',
];
