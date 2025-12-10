# Conversational Analytics (canonical)

- Primary analytics stack: `backend/conversational_analytics` (FastAPI router mounted at `/api/conv-analytics`) with the React UI in `components/conversationalAnalytics`.
- Legacy agent UI is archived under `analytics-legacy/next-gen-analytics-agent`; SQL demo remains in `components/analytics/sql` for comparison.
- Architecture reference: `docs/architecture-conversational-analytics.md`.

## Quick start (PowerShell)
```powershell
# backend
Set-Location backend
pip install -r requirements.txt
Copy-Item .env.example .env  # supply keys; reuse SUPABASE_JWT_SECRET and GEMINI keys
py -m uvicorn main:app --reload --port 8000

# frontend (new UI)
Set-Location ..
npm install
$env:VITE_BACKEND_URL="http://localhost:8000"
npm run dev
```

## Required environment keys
- `CLAUDE_API_KEY` – Claude API key for the agent
- `DATABASE_URL` – PostgreSQL URL for comp_financials data
- `CONV_ANALYTICS_DEBUG` – optional, set `true` to surface verbose events to the UI

## Frontend API targets
- Stream: `POST /api/conv-analytics/stream` (SSE)
- Non-stream: `POST /api/conv-analytics/chat`
- Session history: `GET /api/conv-analytics/sessions/{session_id}/history`
- Selection resume: `POST /api/conv-analytics/selection`
- Health: `GET /api/conv-analytics/health`

## What changed
- The `project/next-gen-analytics-agent` slug now routes to the Conversational Analytics experience.
- Memory-flow artifacts and tests live in `analytics-legacy/next-gen-analytics-agent` for reference only.
- Marketing/SEO links should prefer `conversational-analytics` naming; see `constants/seo.ts` and `constants.ts`.

