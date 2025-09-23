# Supervisor Flow Reference (Optimized)

This document describes the optimized single‑agent supervisor flow for next‑gen‑analytics‑memory. The flow runs classification and intent detection BEFORE agent involvement, with smart schema validation to minimize unnecessary clarifications. Agent is only used for tool planning and execution.

## High‑Level Phases
- **Classification Phase** (BEFORE Agent)
  - Small‑talk guard for obvious non-queries
  - Fast classification using `gpt-5-nano-2025-08-07` model
  - Heuristic keyword/ticker fallback for reliability
  - Off‑topic queries get polite decline and exit early

- **Intent Detection Phase** (BEFORE Agent)
  - `detect_intent_with_clarifications` extracts intent and slots
  - Enhanced logic prevents unnecessary clarifications for specific companies
  - Post-processing adds missing companies from query text

- **Schema Validation Phase** (BEFORE Agent)
  - Validates required fields for detected intent using structured schema
  - Only requests clarifications for genuinely missing required fields
  - Skips clarification loop if all required fields are present

- **Agent Tool Planning & Execution** (AFTER Validation)
  - Agent receives complete, validated intent with all required fields
  - Agent focuses on tool selection and execution strategy
  - Sequential execution: `provisional_plan` → `retrieve_templates_rag` → `validate_sql` → `apply_execute_sql` → `plan_chart` → `build_chart`

- **Analysis + Finalization**
  - Streaming analysis and final summary via the Responses API

## Optimized Flow Order
1. **Classification**: `gpt-5-nano-2025-08-07` classification (fast, lightweight)
2. **Intent Detection**: LLM-based intent extraction with smart clarification logic
3. **Schema Validation**: Structured validation of required fields
4. **Clarification**: Only if schema validation fails
5. **Agent Planning**: Agent receives validated intent and plans tool execution
6. **Tool Execution**: Agent executes tools sequentially
7. **Analysis**: Streaming financial analysis
8. **Finalization**: Summary and completion

## Enhanced Events (SSE)

### Classification Events
- `classification_started`: Classification phase begins with model info
- `classification_reasoning`: Real-time classification thinking/confidence
- `classification_complete`: Classification result with confidence scores
- `classification_error`: Classification failures with error details
- `classification_fallback`: Heuristic fallback activation

### Intent Detection Events
- `intent_detection_started`: Intent detection phase begins
- `intent_detection_complete`: Intent extracted with confidence and slots
- `intent_finalized`: Intent and schema validation complete

### Schema Validation Events
- `schema_validation_started`: Schema validation begins
- `schema_validation_complete`: Validation results with missing fields
- `clarification_needed`: Lists missing required fields
- `clarification_skipped`: All fields present, no clarification needed

### Agent Planning Events
- `tool_planning_started`: Agent planning phase begins
- `tool_selection_reasoning`: Agent's tool selection strategy

### Execution Events
- `tool_start`, `tool_end`, `tool_error`: Tool execution lifecycle
- `sql_executed`, `data_retrieved`, `chart_generated`: Data pipeline
- `analysis_streaming`, `analysis_complete`: Real-time analysis

### Completion Events
- `final_summary`, `workflow_complete`: Workflow completion

## Smart Clarification Logic

### Reduced Clarifications
- **Market Share Queries**: No longer asks "single vs all" when company is specified
- **Schema-Driven**: Only requests clarifications for truly missing required fields
- **Post-Processing**: Automatically detects companies from query text

### Intent Requirements
```
market_share_single: requires [company]
market_share_all: requires []
margins_vs_peers: requires [company]
revenue_growth_analysis: requires []
rnd_intensity_vs_peers: requires [company]
```

## Performance Optimizations
- **Fast Classification**: `gpt-5-nano-2025-08-07` for 50-70% faster non-financial query handling
- **Early Exit**: Non-financial queries exit before expensive processing
- **Structured Validation**: Deterministic schema checking before LLM clarifications
- **Agent Efficiency**: Agent only handles tool planning, not classification/validation

## UI/UX Improvements
- **Side Panel**: Process visualization moved to right-side panel with show/hide toggle
- **Real-time Updates**: Enhanced SSE events provide detailed progress tracking
- **Clean Chat**: Removed embedded thinking panels from message bubbles
- **Timing Metrics**: All phases include elapsed time measurements

