# System Architecture

This is a full-stack AI-powered portfolio application with a React frontend and FastAPI backend.

## Frontend (React + TypeScript + Vite)
- **Main App**: `App.tsx` manages routing and layout
- **Components**: Individual page components in `/components`
- **Services**: API communication layer in `/services`
- **Types**: TypeScript definitions in `types.ts`
- **Constants**: Project data in `constants.ts`

## Backend (FastAPI + Python)
- **Main API**: `backend/main.py` exposes all FastAPI endpoints
- **Unified Analytics Suite**: `backend/analytics/` houses `core/`, `sql/`, `flows/`, `tools/`, and `streaming/`. The former `analytics_memory/*`, `analytics_shared/*`, and `analytics_supervisor/*` packages have been removed now that consumers import from this namespace.
- **Workflow Dispatcher**: `backend/analytics/flows/workflow.py` selects the active analytics flow (`planner-executor`, `single-agent`, or `multi-agent`) and invokes the Responses API-first pipeline used by `/api/analytics/memory/stream`.
- **SQL Catalogue**: `backend/analytics/sql/` compiles YAML templates from `backend/config/schemas/*.yaml` to propose, validate, and execute database queries with deterministic fallbacks.
- **Standalone Analytics Agent**: `backend/analytics_agent.py` remains an independent workflow unless a shared frontend pathway requires changes.
- **Shared Services**: Gemini AI, TTS, and rate limiting helpers in dedicated modules.
- **Rate Limiting**: Redis-backed with in-memory fallback

## Key API Endpoints

### Analytics Endpoints (Suite-Managed)
- **Analytics SQL** (`/api/analytics/stream`)
  - LangGraph SQL workflow for financial analytics driven by the analytics suite
  - Direct SQL generation and execution
  - Real-time streaming with chart generation
  - No clarifications, direct query processing

- **Analytics Memory** (`/api/analytics/memory/stream`)
  - Responses API-first planner that hydrates YAML-guided SQL suggestions before validation and execution
  - `flow` query param selects demo experiences (`planner-executor` default, `single-agent`, `multi-agent`); the legacy `mode` alias remains for backwards compatibility
  - Streams SSE telemetry (`progress`, `sql_generated`, `tool_call`, `agent_turn`, `agent_reasoning`, `final_answer`) for visualization overlays
  - Session-based memory management with clarification loops

- **Memory Clarifications** (`/api/analytics/memory/clarify`)
  - Handles user responses to clarification requests
  - Session-based clarification tracking
  - Supports single/multi/free-form responses

### Other Endpoints
- `/api/research/stream` - Research agent with web search
- `/api/resume-search/stream` - Resume-specific queries
- `/api/gemini/chat/*` - Gemini AI chat sessions
- `/api/tts` - Text-to-speech generation
- `/api/rate-limit/*` - Usage tracking and limits

## Code Architecture

### Frontend-Backend Communication
- **Authentication**: Supabase JWT tokens sent via `apiService.streamWithAuth()`
- **Rate Limiting**: Guest users (5/day) vs authenticated users (20/day)
- **Streaming**: Server-Sent Events (SSE) deliver `progress`, `sql_generated`, `tool_call`, `agent_turn`, `agent_reasoning`, and result/final_answer payloads for analytics flows
- **Error Handling**: Unified error payloads prompting auth when required
- **Config Service**: Centralized environment management through `services/config.ts`

### Analytics Suite Boundaries
- `backend/analytics/` is the canonical package; no legacy proxies remain in the repository.
- YAML catalogues in `backend/config/schemas/*.yaml` drive the planner, validator, and executor under `analytics/sql/`.
- Planner-executor, single-agent, and multi-agent flows reuse `analytics.core` services for state, cache, events, and config.
- `analytics_agent.py` stays separate and only changes when a shared frontend experience explicitly depends on it.

### AI Integration
- **Research Agent**: LangChain + OpenAI for web research
- **Resume Agent**: Vector-backed resume queries
- **Gemini Chat**: Backend-hosted Gemini 2.5 Flash conversations
- **Analytics Suite**: Cohesive LangGraph workflows spanning memory, shared tooling, and supervisor orchestration

### Authentication Flow
1. Frontend: Supabase Auth for user sign-in
2. Backend: JWT validation using the Supabase secret
3. Rate limiting applied based on authentication status

## Development Commands

### Frontend Development
- **Start development server**: `npm run dev` (http://localhost:5173)
- **Build for production**: `npm run build`
- **Preview production build**: `npm run preview`
- **Install dependencies**: `npm install`

### Backend Development
- **Install Python dependencies**:
  1. `cd backend`
  2. `pip install -r requirements.txt`
- **Start backend server**:
  1. `cd backend`
  2. `uvicorn main:app`
  3. Use `uvicorn main:app --reload` for auto-reload during development
- **Alternative start**:
  1. `cd backend`
  2. `python main.py`

### Full Stack Development
1. Start backend:
   - `cd backend`
   - `uvicorn main:app`
2. Start frontend: `npm run dev`
3. Access the application at http://localhost:5173

## Git Sync Rules
- **Do not overwrite local `.env` files** when syncing from GitHub
- `.env` files contain sensitive API keys and environment-specific configuration
- If `.env` templates require updates, adjust documentation rather than committed secrets
- Preserve existing local environment settings

## Adding New Features
1. Frontend changes go in appropriate `/components` or `/services`
2. Backend changes go in `backend/` with new endpoints in `main.py`
3. Update TypeScript types in `types.ts` if needed
4. Test with both frontend and backend running
