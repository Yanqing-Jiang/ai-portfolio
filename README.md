# AI Portfolio

Live site: [yanqing.app](https://yanqing.app)

Yanqing Jiang's portfolio is a React and FastAPI application that combines
prerendered project pages with a small set of live AI experiences.

## Active Experiences

- Conversational Analytics: Claude-driven financial analysis with SQL, charts,
  clarifications, and SSE progress at `/api/conv-analytics`.
- Agent to UI: generative dashboards rendered from A2UI messages.
- Fortune Agent: streamed BaZi readings, replayable snapshots, corrections,
  follow-up actions, and an Ask workflow.
- LinkedIn Photo: image validation, prompt expansion, and Gemini image editing.
- Project chat: Gemini-backed Q&A for portfolio entries. Retired projects such
  as Research GPT and Ask My Resume are presented as historical case studies;
  they no longer have dedicated backend agents.

The old analytics workflow, research agent, resume agent, and their streaming
routes were retired in June 2026. The `next-gen-analytics-agent` project slug
now opens the canonical Conversational Analytics experience.

## Repository Layout

```text
.
|-- App.tsx                         React router and application shell
|-- components/
|   |-- conversationalAnalytics/    Canonical analytics UI
|   |-- generativeUiDashboard/      A2UI dashboard and Fortune UI
|   |-- linkedinPhoto/              Headshot workflow
|   `-- Chat.tsx                    Shared Gemini project chat
|-- backend/
|   |-- conversational_analytics/   Analytics agent and API routes
|   |-- generative_ui/              A2UI dashboard runtime
|   |-- fortune/                    Fortune runtime and persistence
|   |-- linkedin_photo/             Headshot service
|   `-- main.py                     FastAPI application
|-- constants.ts                    Project catalog and project SEO
|-- scripts/prerender.mjs           Static route generation
|-- ssr/                            Vite SSR entry
`-- public/                         Static assets and generated feeds
```

## Local Development

Prerequisites:

- Node.js 20+
- Python 3.12
- Redis for production-like rate limiting and ephemeral shared state

Frontend:

```bash
npm install
npm run dev
```

Backend:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/uvicorn main:app --app-dir backend --reload --port 8000
```

Common environment variables:

```text
VITE_BACKEND_URL=http://localhost:8000
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
CLAUDE_API_KEY=...
GEMINI_API_KEY=...
OPENAI_API_KEY=...
SUPABASE_DB_URL=...
SUPABASE_JWT_SECRET=...
REDIS_URL=redis://localhost:6379/0
```

Feature-specific integrations degrade or stay disabled when their keys are not
configured. Secrets belong in local environment files and must not be committed.

## Verification

```bash
npm run test
npx tsc --noEmit
npm run build
backend/.venv/bin/python -m pytest backend/tests
backend/.venv/bin/python -m compileall -q backend scripts
```

`npm run build` creates the client bundle, SSR bundle, prerendered project
pages, sitemaps, and public JSON feeds.

## Deployment

The frontend deploys to Cloudflare Pages through
`.github/workflows/deploy.yml`.

The backend and Redis run on the Mac Mini through Docker Compose:

```bash
docker compose up -d --build
docker compose logs -f backend
curl https://portfolio-api.yanqing.app/health
```

Cloudflare Tunnel exposes the backend at
`https://portfolio-api.yanqing.app`. The backend intentionally runs one
gunicorn worker because active Fortune streams still use process-local session
state.

See `ARCHITECTURE.md` for component boundaries and request flows.
