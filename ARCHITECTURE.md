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
- **Analytics Suite**: `backend/analytics_memory`, `backend/analytics_shared`, and `backend/analytics_supervisor` form one cohesive project that shares configuration, caching, and LangGraph orchestration
- **Standalone Analytics Agent**: `backend/analytics_agent.py` is an independent workflow that should remain untouched unless user-facing frontend changes explicitly depend on it
- **Services**: Gemini AI, TTS, and rate limiting helpers in dedicated modules
- **Rate Limiting**: Redis-backed with in-memory fallback

## Key API Endpoints

### Analytics Endpoints (Suite-Managed)
- **Analytics SQL** (`/api/analytics/stream`)
  - LangGraph SQL workflow for financial analytics driven by the analytics suite
  - Direct SQL generation and execution
  - Real-time streaming with chart generation
  - No clarifications, direct query processing

- **Analytics Memory** (`/api/analytics/memory/stream`)
  - LangGraph memory pipeline with intelligent clarifications maintained by the analytics suite
  - Advanced intent detection and query planning
  - Conversational clarifications for ambiguous queries
  - Session-based memory management

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
- **Streaming**: Server-Sent Events (SSE) for real-time AI responses
- **Error Handling**: Unified error payloads prompting auth when required
- **Config Service**: Centralized environment management through `services/config.ts`

### Analytics Suite Boundaries
- `analytics_memory`, `analytics_shared`, and `analytics_supervisor` share state, prompts, and utilities; update them together to preserve workflow guarantees
- `analytics_agent.py` is completely separate from the suite and should only change if a widely used frontend feature makes it necessary

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
