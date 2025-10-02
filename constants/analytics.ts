// Shared constants for analytics pages

// Memory pipeline steps (streamlined agent-forward)
export const STEP_NAME: Record<string, string> = {
  classify: 'Topic Classification',
  intent_detection: 'Intent Detection',
  schema_validation: 'Schema & Criteria Validation',
  tool_execution: 'Agent Tool Execution',
  tool_fanout: 'Tool Fan-Out Telemetry',
  agent_coordination: 'Agent Coordination',
  plan_and_select_template: 'Query Planning & Template Selection',
  planner_agent: 'Planner Agent Lane',
  query_agent: 'Query Agent Lane',
  analyst_agent: 'Analyst Agent Lane',
  chart_agent: 'Chart Agent Lane',
  web_research_agent: 'Web Research Agent Lane',
  market_agent: 'Market Agent Lane',
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
  'clarification',
  'plan_and_select_template',
  'planner_agent',
  'query_agent',
  'analyst_agent',
  'chart_agent',
  'web_research_agent',
  'market_agent',
  'tool_execution',
  'tool_fanout',
  'agent_coordination',
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
