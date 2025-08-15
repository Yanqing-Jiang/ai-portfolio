# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Frontend Development
- **Start development server**: `npm run dev` (runs on localhost:5173)
- **Build for production**: `npm run build`
- **Preview production build**: `npm preview`
- **Install dependencies**: `npm install`

### Backend Development
- **Install Python dependencies**: `cd backend && pip install -r requirements.txt`
- **Start backend server**: `cd backend && uvicorn main:app --reload` (runs on localhost:8000)
- **Alternative start**: `cd backend && python main.py`

### Full Stack Development
1. Start backend: `cd backend && uvicorn main:app --reload`
2. Start frontend: `npm run dev`
3. Access application at http://localhost:5173

## Architecture Overview

This is a full-stack AI-powered portfolio application with a React frontend and FastAPI backend.

### Frontend (React + TypeScript + Vite)
- **Main App**: `App.tsx` - Router and layout management
- **Components**: Individual page components in `/components`
- **Services**: API communication layer in `/services`
- **Types**: TypeScript definitions in `types.ts`
- **Constants**: Project data in `constants.ts`

### Backend (FastAPI + Python)
- **Main API**: `backend/main.py` - FastAPI application with all endpoints
- **AI Agents**: Specialized agents for research, resume, and analytics
- **Services**: Gemini AI, TTS, and rate limiting services
- **Rate Limiting**: Redis-based with in-memory fallback

### Key API Endpoints
- `/api/research/stream` - Research agent with web search
- `/api/resume-search/stream` - Resume-specific queries
- `/api/gemini/chat/*` - Gemini AI chat sessions
- `/api/tts` - Text-to-speech generation
- `/api/analytics/stream` - Analytics with SQL capabilities
- `/api/rate-limit/*` - Usage tracking and limits

## Code Architecture

### Frontend-Backend Communication
- **Authentication**: Supabase JWT tokens in Authorization headers
- **Rate Limiting**: Guest users (5/day), authenticated users (20/day)
- **Streaming**: Server-Sent Events (SSE) for real-time AI responses
- **Error Handling**: Unified error responses with auth prompts

### AI Integration
- **Research Agent**: Uses LangChain + OpenAI for web research
- **Resume Agent**: Processes resume queries with vector search
- **Gemini Chat**: Backend-hosted Gemini 2.5 Flash for conversations
- **Analytics Agent**: LangGraph workflow for SQL analytics

### Authentication Flow
1. Frontend: Supabase Auth for user sign-in
2. Backend: JWT validation using Supabase secret
3. Rate limiting applied based on authentication status

## Environment Variables

### Frontend (.env)
```
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
VITE_BACKEND_URL=http://localhost:8000
```

### Backend (backend/.env)
```
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
SUPABASE_JWT_SECRET=your_supabase_jwt_secret
REDIS_URL=redis://localhost:6379/0
ELEVEN_LABS_API_KEY=your_elevenlabs_key
ELEVEN_LABS_VOICE_ID=your_voice_id
```

## Important Implementation Details

### Streaming Responses
- Backend uses `await asyncio.sleep(0)` for immediate chunk flushing
- SSE headers include `X-Accel-Buffering: no` to prevent nginx buffering
- Frontend processes SSE streams with `@microsoft/fetch-event-source`

### Rate Limiting
- Redis-based counters with daily limits
- Fallback to in-memory storage if Redis unavailable
- Auth required after guest quota exceeded

### Component Structure
- `LandingPage.tsx`: Portfolio homepage with project showcase
- `ProjectView.tsx`: Individual project detail pages
- `Chat.tsx`: AI chat interface with multiple agents
- `Sidebar.tsx`: Navigation and project browser
- `AnalyticsPage.tsx`: SQL analytics and data visualization

### Recent Migration Notes
- Gemini functionality moved from frontend to backend (see MIGRATION_SUMMARY.md)
- Uses latest Gemini 2.5 Flash model via Python SDK
- Enhanced audio player with full controls for TTS
- Removed unused icon components to reduce bundle size

## Development Workflow

### Adding New Features
1. Frontend changes go in appropriate `/components` or `/services`
2. Backend changes go in `backend/` with new endpoints in `main.py`
3. Update TypeScript types in `types.ts` if needed
4. Test with both frontend and backend running

### Testing Considerations
- No specific test framework configured
- Manual testing requires both servers running
- Backend testing needs proper API keys in environment
- Frontend testing can use mock backend responses

### Build and Deployment
- Frontend builds to `/dist` directory
- Backend serves via uvicorn ASGI server
- Static assets can be deployed separately from API
- Environment variables must be configured for production