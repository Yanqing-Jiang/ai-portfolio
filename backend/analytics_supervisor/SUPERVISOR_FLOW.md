# Supervisor Flow Reference (Refactored & Optimized)

This document describes the fully refactored and optimized single‑agent supervisor flow for next‑gen‑analytics‑memory. The flow features a streamlined 2-layer fallback architecture, centralized Redis caching, and progressive frontend rendering. Classification and intent detection run BEFORE agent involvement, with smart schema validation to minimize unnecessary clarifications.

## Refactored Architecture (v2.0)

### Backend Optimizations
- **2-Layer Fallback**: Simplified from 3-layer (RAG → Template Store → YAML) to 2-layer (RAG → YAML)
- **Centralized Caching**: Redis-based cache service with circuit breaker pattern and in-memory fallback
- **Connection Pooling**: Enhanced PostgreSQL connection pooling with asyncpg (pool size: 5)
- **Unified Response Client**: Consolidated supervisor-specific and general response clients
- **Legacy Cleanup**: Removed 1,104 lines of unused code (config_loaders.py, template_store.py)

### Frontend Enhancements
- **Progressive Rendering**: 50ms debounced updates for smooth real-time streaming
- **Chart Generation Fix**: Corrected lazy loading imports for ChartCard component
- **Enhanced Memory Stream**: Added progressive analysis and text state management

### Performance Improvements
- **Reduced Memory Footprint**: Eliminated duplicate caching layers
- **Faster Config Resolution**: Direct RAG-to-YAML fallback without intermediate stores
- **Circuit Breaker**: Graceful Redis failures with automatic fallback to in-memory cache

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

## Technical Implementation Details

### Cache Service Architecture
```python
class CacheService:
    - Redis client with connection pooling
    - Circuit breaker pattern (5 failure threshold)
    - Automatic fallback to in-memory cache
    - TTL-based cache management
    - Async/await support for FastAPI integration
```

### Config Store (2-Layer Fallback)
```python
class ConfigSource(Enum):
    RAG_SERVICE = "rag_service"     # Primary: Vector search
    YAML_CONFIG = "yaml_config"     # Fallback: Static configs
    EMPTY_FALLBACK = "empty_fallback"  # Final fallback
```

### Progressive Frontend Rendering
```typescript
// 50ms debounced updates for smooth streaming
const scheduleProgressiveUpdate = (updates) => {
    Object.assign(pendingUpdatesRef.current, updates);
    updateTimeoutRef.current = setTimeout(() => {
        // Batch updates for performance
        applyPendingUpdates();
    }, 50);
};
```

## Performance Optimizations
- **Fast Classification**: `gpt-5-nano-2025-08-07` for 50-70% faster non-financial query handling
- **Early Exit**: Non-financial queries exit before expensive processing
- **Structured Validation**: Deterministic schema checking before LLM clarifications
- **Agent Efficiency**: Agent only handles tool planning, not classification/validation
- **Centralized Caching**: Redis cache with 15-minute TTL and circuit breaker resilience
- **Connection Pooling**: Optimized PostgreSQL connections with asyncpg pool management

## UI/UX Improvements
- **Side Panel**: Process visualization moved to right-side panel with show/hide toggle
- **Real-time Updates**: Enhanced SSE events provide detailed progress tracking
- **Clean Chat**: Removed embedded thinking panels from message bubbles
- **Timing Metrics**: All phases include elapsed time measurements

