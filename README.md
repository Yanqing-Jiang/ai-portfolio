# AI Portfolio - Yanqing's Interactive Portfolio

This is a full-stack AI-powered portfolio application featuring intelligent chat agents, research capabilities, and dynamic content presentation.

## Architecture Overview

### System Architecture

The application follows a modern full-stack architecture with clear separation between frontend and backend:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │  External APIs  │
│   (React/Vite)  │◄──►│   (FastAPI)     │◄──►│  Gemini, OpenAI │
│                 │    │                 │    │  Search APIs    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Static Dist   │    │    Redis        │    │   Supabase      │
│   (Deployment)  │    │  (Rate Limit)   │    │   (Auth)        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Frontend Architecture

**Technology Stack:**
- **React 19** with TypeScript for the user interface
- **Vite** as the build tool and development server
- **React Router DOM** for client-side routing
- **Framer Motion** for animations and transitions
- **React Markdown** for content rendering
- **Supabase Client** for authentication

**Key Components:**
- `App.tsx` - Main application router and layout manager
- `LandingPage.tsx` - Portfolio homepage with project showcase
- `ProjectView.tsx` - Individual project detail pages
- `Chat.tsx` - AI-powered chat interface
- `Sidebar.tsx` - Navigation and project browser
- `AuthModal.tsx` - User authentication interface

**Frontend Services:**
- `apiService.ts` - HTTP client with rate limiting and auth handling
- `backendGeminiService.ts` - Gemini AI chat service integration
- `auth.ts` - Supabase authentication management

### Backend Architecture

**Technology Stack:**
- **FastAPI** with Python for high-performance async API
- **LangChain** for AI agent orchestration
- **Redis** for rate limiting and session management
- **Supabase** for user authentication and JWT validation
- **Google Gemini API** for AI chat capabilities
- **Various AI APIs** (OpenAI, search services) for research agents

**Core Services:**
- `main.py` - FastAPI application with route definitions
- `research_agent.py` - Web research and information gathering agent
- `resume_agent.py` - Resume-specific question answering agent
- `gemini_service.py` - Gemini AI chat session management
- `rate_limiter.py` - Redis-based rate limiting with fallback
- `tts.py` - Text-to-speech generation service

**API Endpoints:**
- `/api/research` - Research agent for web search and analysis
- `/api/resume-search` - Resume-specific information queries
- `/api/gemini/chat/*` - Gemini AI chat sessions
- `/api/tts` - Text-to-speech generation
- `/api/rate-limit/*` - Usage tracking and limits
- `/api/user-input` - Input counting for rate limiting

### Frontend-Backend Communication

**Authentication Flow:**
1. User signs in through Supabase Auth on frontend
2. Frontend receives JWT token and stores it securely
3. All API requests include JWT token in Authorization header
4. Backend validates JWT using Supabase secret key
5. Rate limiting applied based on user authentication status

**Request/Response Patterns:**

**Standard HTTP Requests:**
```typescript
// Frontend API service
const response = await apiService.post('/api/user-input', data)
if (!response.success) {
  if (response.needsAuth) showAuthModal()
  else handleError(response.error)
}
```

**Server-Sent Events (SSE) Streaming:**
```typescript
// Real-time streaming for AI responses
await apiService.streamWithAuth(
  '/api/research/stream?query=...',
  (data) => {
    if (data.type === 'status') updateStatus(data.message)
    else if (data.type === 'response') appendResponse(data.text)
    else if (data.type === 'done') completeResponse()
  },
  (error, needsAuth) => handleError(error, needsAuth)
)
```

**Rate Limiting Integration:**
- Guest users: 5 requests per day (IP-based)
- Authenticated users: 20 requests per day (user-based)
- Frontend tracks usage and shows auth prompts when limits hit
- Backend enforces limits with Redis counters and fallback

**Data Flow:**
1. Frontend makes authenticated request to backend
2. Backend validates JWT and checks rate limits
3. AI agents process requests with streaming responses
4. Real-time updates sent via SSE to frontend
5. Frontend updates UI reactively with received data

**Error Handling:**
- HTTP 401: Authentication required → Show login modal
- HTTP 429: Rate limit exceeded → Show usage information
- Stream errors: Graceful degradation with error messages
- Network errors: Retry logic with exponential backoff

### Deployment Architecture

**Frontend:**
- Built as static assets with Vite
- Deployed to static hosting (Vercel/Netlify compatible)
- Environment variables for API endpoints

**Backend:**
- FastAPI server with uvicorn ASGI server
- Docker containerization support
- Environment-based configuration
- Redis for production rate limiting
- Health check endpoints for monitoring

**External Dependencies:**
- Supabase for authentication and user management
- Redis for rate limiting (with in-memory fallback)
- Google Gemini API for AI chat capabilities
- OpenAI API for research agents
- Various search APIs for web research

## Run Locally

**Prerequisites:** Node.js, Python 3.8+, Redis (optional)

### Frontend Setup
1. Install dependencies: `npm install`
2. Set environment variables in `.env`:
   ```
   VITE_SUPABASE_URL=your_supabase_url
   VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
   VITE_BACKEND_URL=http://localhost:8000
   ```
3. Run the app: `npm run dev`

### Backend Setup
1. Navigate to backend: `cd backend`
2. Install Python dependencies: `pip install -r requirements.txt`
3. Set environment variables in `backend/.env`:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   OPENAI_API_KEY=your_openai_api_key
   SUPABASE_JWT_SECRET=your_supabase_jwt_secret
   REDIS_URL=redis://localhost:6379/0
   ```
4. Run the backend: `uvicorn main:app --reload`
