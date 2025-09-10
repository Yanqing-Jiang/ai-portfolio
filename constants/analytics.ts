// Shared constants for analytics pages

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