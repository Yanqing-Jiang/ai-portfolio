# AI Portfolio Analytics Backend

This backend powers the AI portfolio project's financial analytics system. It orchestrates a LangGraph-based multi-agent workflow that uses LLM-driven schema understanding to parse user questions, generate optimized SQL queries, execute against Supabase Postgres, produce ECharts visualizations, and stream financial analysis in real-time.

## Project Overview

- **Framework**: FastAPI + Server-Sent Events (SSE) for real-time streaming
- **Orchestration**: LangGraph state machine with multi-agent workflow  
- **LLM**: OpenAI GPT-5-mini-2025-08-07 via `langchain_openai`
- **Database**: Supabase Postgres with `asyncpg` for async operations
- **Visualization**: ECharts spec generation with deterministic builders
- **Analytics**: Real-time streaming financial analysis

## Architecture

### Key Files
- `analytics_agent.py` – Core analytics agents, LangGraph workflow, and streaming logic
- `main.py` – FastAPI application with `/api/analytics/stream` SSE endpoint
- `test_supabase_connection.py` – Database connectivity and schema validation tests
- `requirements.txt` – Python dependencies

### Required Environment Variables
```env
DATABASE_URL=postgresql://user:password@host:port/database
OPENAI_API_KEY=sk-...
```

## Analytics Agent Workflow

The analytics system uses a streamlined 3-stage LangGraph workflow that leverages LLM intelligence throughout:

### Stage 1: SQL Agent (`_sql_agent`)
**Purpose**: LLM-driven schema analysis and SQL generation

**Process**:
1. **Schema Understanding**: LLM analyzes user query against `COMP_FINANCIALS_SCHEMA` to determine:
   - Required companies (validated against available tickers: AMD, AVGO, INTC, MU, NVDA, QCOM, TXN)
   - Required financial metrics (48 available metrics including Revenue, Net Income, R&D Expense, etc.)
   - Time dimensions and date ranges. Which time dimension to choose from (date	or calendar_year + calendar_quarter_num)
   - Derived calculations (margins, percentages, ratios)
   - Visualization preferences (line chart, bar chart, pie chart...etc) with business context

2. **SQL Generation**: LLM creates optimized PostgreSQL queries based on schema analysis
   - Targets long-format `comp_financials` table structure
   - Includes safety guardrails (time filters)

3. **Query Execution**: 
   - Execution
   - 15-second statement timeout for retry


**Key Innovation**: No fallback to default schemas - LLM drives all decision-making for maximum flexibility

### Stage 2: ECharts Agent (`_echarts_agent`)
**Purpose**: Convert query results into interactive visualizations

**Features**:
- **Deterministic Chart Building**: Rule-based ECharts option generation
- **Multi-Series Support**: Handles multiple companies, metrics, and time periods
- **Derived Metrics**: Special handling for calculated fields (R&D as % of Revenue, Gross Margin %)
- **Time Axis Intelligence**: Quarter-based vs. date-based visualization depending on user query
- **Light Theme**: Professional financial dashboard styling

**Output**: Complete ECharts configuration with series data, styling, and interactivity

### Stage 3: Analysis Agent (`_analysis_agent`)
**Purpose**: Stream real-time financial insights

**Approach**:
- **Streaming Analysis**: Token-by-token streaming for immediate user feedback
- **Number-Driven**: Focus on exact figures, growth rates, and comparisons
- **Contextual**: References specific time periods and business metrics
- **Concise**: 4-6 bullet points with actionable insights

## Database Schema

The system works with a long-format financial data table:

```sql
TABLE comp_financials (
  ticker TEXT,                    -- Company ticker symbol
  metric TEXT,                    -- Financial metric name  
  value REAL,                     -- Numerical value
  tag_used TEXT,                  -- Data source tag
  date DATE,                      -- Reporting date
  calendar_year INTEGER,          -- Year
  calendar_quarter_num INTEGER,   -- Quarter number (1-4)
  calendar_quarter TEXT          -- Quarter label (Q1 2024, etc.)
)
```

### Supported Data
- **Companies**: 7 semiconductor companies (AMD, AVGO, INTC, MU, NVDA, QCOM, TXN)
- **Metrics**: 48 financial metrics covering income statement, balance sheet, and cash flow
- **Time Range**: Quarterly data from 2022 onwards
- **Structure**: Each row contains one metric value for one company in one quarter

## API Endpoints

### Analytics Streaming
```
GET /api/analytics/stream?query={user_query}
```

**Response**: Server-Sent Events stream with the following event types:

| Event Type | Description | Payload |
|------------|-------------|---------|
| `status` | Workflow step updates | `{step, message, thinking}` |
| `sql_generated` | Generated SQL query | `{sql}` |  
| `data_retrieved` | Query execution results | `{row_count, sample_data}` |
| `chart_generated` | ECharts specification | `{chart_spec}` |
| `analysis_streaming` | Partial analysis text | `{partial_analysis}` |
| `analysis_complete` | Final analysis | `{analysis}` |
| `errors` | Error messages | `{errors}` |
| `workflow_complete` | Success completion | `{message}` |

## Advanced Features

### LLM-Driven Schema Analysis
The system uses sophisticated prompt engineering to let the LLM:
- **Parse Natural Language**: Understand complex financial queries
- **Map to Schema**: Identify relevant companies and metrics from available data
- **Infer Intent**: Determine visualization type and business context
- **Handle Edge Cases**: Gracefully process ambiguous or incomplete queries

### Performance Optimizations
- **Streaming**: Real-time response delivery without buffering
- **Safety Limits**: Timeouts to prevent resource exhaustion

### Error Handling
- **Graceful Degradation**: Workflow continues despite individual agent failures
- **Detailed Logging**: Comprehensive error tracking and debugging information
- **User-Friendly Messages**: Clear error communication to both frontend and backend

## Local Development

### 1. Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)  
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
Create `backend/.env`:
```env
DATABASE_URL=postgresql://username:password@host:port/database
OPENAI_API_KEY=sk-your-openai-api-key-here
```

### 3. Start Backend
```bash
uvicorn main:app --reload
```
Server runs on `http://localhost:8000`

### 4. Test Database Connection
```bash
python test_supabase_connection.py
```

## Example Queries

The system handles sophisticated natural language queries:

- **"Show NVDA revenue growth over the last 8 quarters"**
- **"Compare R&D spending as % of revenue for all semiconductor companies over 5 years"**  
- **"What are the gross margins for AMD vs INTC in the last 4 quarters?"**
- **"Analyze NVDA's cash flow from operations vs capital expenditures"**

## Troubleshooting

### Common Issues

**Database Connection Errors**
- Verify `DATABASE_URL` in `.env` file
- Check network connectivity to Supabase
- Run `test_supabase_connection.py` for diagnostics

**OpenAI API Errors**  
- Confirm `OPENAI_API_KEY` is valid and has sufficient credits
- Check for rate limiting or quota issues

**Query Timeout Issues**
- Long-running queries are automatically terminated after 15 seconds
- Large result sets are limited to 1000 rows for performance

**ECharts Rendering Issues**
- Check browser console for JavaScript errors
- Verify chart specification in network tab
- Frontend has Chart.js fallback for unsupported configurations

### Debug Mode
Enable verbose logging by setting environment variable:
```env
LOG_LEVEL=DEBUG
```

## Production Deployment

### Requirements
- Python 3.9+
- PostgreSQL database (Supabase recommended)
- OpenAI API access
- CORS configuration for frontend domain

### Environment Variables
```env
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-...
CORS_ORIGINS=https://your-frontend-domain.com
```

### Health Checks
- `GET /api/analytics/stream?query=test` - Basic workflow test
- Database connectivity via `test_supabase_connection.py`

## Contributing

### Code Structure
- Follow existing naming conventions
- Add comprehensive docstrings
- Include error handling for all external API calls
- Test with various query types

### Testing
- Unit tests for individual agents
- Integration tests for full workflow
- Database connection tests
- LLM response validation

## Technical Specifications

### Dependencies
```
fastapi>=0.104.0
uvicorn>=0.24.0
asyncpg>=0.29.0
langchain-openai>=0.1.0
langgraph>=0.0.40
pydantic>=2.4.0
python-dotenv>=1.0.0
```

### Performance Metrics
- Average query response time: 3-8 seconds
- Database query timeout: 15 seconds
- Maximum result set: 1000 rows
- Streaming latency: <100ms per chunk

This analytics system provides a robust, scalable foundation for financial data analysis with real-time streaming capabilities and intelligent LLM-driven query understanding.