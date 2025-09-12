// Shared constants for analytics pages

// Memory pipeline steps (with clarifications)
export const STEP_NAME: Record<string, string> = {
  intent_detection: 'Intent Detection',
  plan_generation: 'Query Planning',
  template_selection: 'Template Selection',
  clarification: 'Requirements Clarification',
  sql_compilation: 'SQL Compilation',
  sql_validation: 'SQL Validation',
  sql_execution: 'Data Retrieval',
  chart_generation: 'Chart Generation',
  analysis_generation: 'Analysis Generation',
};

export const STEP_ORDER = [
  'intent_detection',
  'plan_generation',
  'template_selection',
  'clarification',
  'sql_compilation',
  'sql_validation',
  'sql_execution',
  'chart_generation',
  'analysis_generation',
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