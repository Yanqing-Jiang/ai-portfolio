# AI Portfolio (Yanqing Jiang)

Interactive AI portfolio that combines a Vite-powered React frontend, a FastAPI backend, and multiple agentic workflows (analytics copilots, resume Q&A, LinkedIn headshot generator, and research assistants). The site prerenders static pages, streams live AI responses, and exposes JSON-LD/SEO metadata for every project.

> For deeper diagrams and sequence flows, see `ARCHITECTURE.md`, `docs/linkedin-photo-*`, and `backend/analytics/ARCHITECTURE.md`.

## Repository Layout

```
.
├── App.tsx                  # Client router and layout wrapper
├── components/              # React feature modules (analytics, LinkedIn photo, chat, UI)
├── constants/               # Project catalog, SEO config, structured data builders
├── services/                # Frontend API clients (Gemini, REST, config)
├── backend/                 # FastAPI app, analytics suite, LinkedIn photo pipeline
├── docs/                    # Design notes, rate-limit plans, roadmap material
├── scripts/                 # Prerender output, demo clients, automation helpers
├── ssr/                     # Server-side rendering entry for Vite build
├── public/                  # Static assets served by Vite
└── tests/ / backend/tests/  # Frontend (vitest) and backend (pytest) harnesses
```

## Key Features

- **Agent showcase landing page** – Rich project grid, animations, and SEO tags (Open Graph, Twitter, JSON-LD) driven by `constants.ts` and `components/LandingPage.tsx`.
- **Analytics copilot demos** – `/components/analytics` renders three flows (`planner-executor`, `single-agent`, `multi-agent`) backed by FastAPI streaming endpoints for SQL planning, charting, and insight narration.
- **LinkedIn Photo generator** – `/components/linkedinPhoto/Page.tsx` integrates the FastAPI `linkedin_photo` router to expand style prompts, call Gemini image editing, and manage user-facing transparency.
- **Resume & research agents** – Backend endpoints in `backend/resume_agent.py` and `backend/research_agent.py` answer targeted queries with streaming reasoning.
- **Structured SEO + prerendering** – `ProjectHelmet` and `constants/structuredData.ts` inject page-level metadata, while `scripts/prerender.mjs` prebuilds static HTML, sitemaps, and JSON assets.
- **Rate limiting & payments ready** – Redis-backed limiter (`backend/rate_limiter.py`) with Stripe/PayPal hooks for token packs; docs outline the future safeguard plan.

## Frontend Overview

- **Stack**: React 19 + TypeScript, Vite 6, Tailwind utilities (via `tailwind-merge`), Framer Motion animations, React Router 6.
- **Data & services**:
  - `services/apiService.ts` centralizes authenticated REST calls (JWT from Supabase).
  - `services/config.ts` exposes runtime backend URLs.
  - `services/backendGeminiService.ts` handles Gemini text streaming.
- **Feature modules**:
  - `components/analytics/**` for SQL/memory demos, charts, and process timelines.
  - `components/linkedinPhoto/**` for the 3-step headshot wizard.
  - `components/Chat.tsx` for shared agent chat UI.
  - `components/ProjectHelmet.tsx` for head/meta tags and schema injection.
- **Routing**: `App.tsx` mounts the landing page at `/` and project pages at `/project/:id`. SSR builds reuse `ssr/entry-server.tsx`.
- **SEO**: `constants/seo.ts` tracks canonical tags, sameAs profiles, default OG images, and AI crawler policies. Project-specific SEO lives in `constants.ts`.

## Backend Overview

- **FastAPI app** (`backend/main.py`):
  - Loads `.env`, configures CORS, registers routers for analytics, research, resume, text-to-speech, payments, and LinkedIn photo flows.
  - Streams Server-Sent Events for analytics workflows (progress, tool calls, reasoning traces).
  - Serves pre-render assets (`public/ai-projects.json`) and health endpoints.
- **Analytics suite** (`backend/analytics/`):
  - `flows/workflow.py` orchestrates planner-executor, single-agent, and multi-agent pipelines.
  - SQL templates sourced from `backend/config/schemas/*.yaml`.
  - Uses LangGraph-inspired task graphs, ECharts-ready payloads, and telemetry for the frontend process panel.
- **LinkedIn photo pipeline** (`backend/linkedin_photo/`):
  - Validates uploads (Pillow), enforces prompt quotas, expands style instructions, and calls Gemini image editing via Banana-hosted Nano models.
  - `docs/linkedin-photo-rate-limit-plan.md` and `docs/linkedin-photo-next-steps.md` track rate-limit rollout and backlog.
- **Shared services**:
  - `gemini_service.py` – session manager for Gemini text agents.
  - `rate_limiter.py` – Redis + in-memory fallback for global/per-user quotas with scopes.
  - `analytics_agent.py` – legacy standalone orchestrator kept for compatibility.
  - `tts.py` – text-to-speech synthesis.
- **Integrations**: Supabase JWT validation, Stripe and PayPal tokens, optional external search APIs, Gemini SDK.

## Setup & Development

### Prerequisites
- Node.js 20+
- Python 3.11+
- PowerShell (scripts expect PS; adjust if using another shell)
- Optional: Redis for production-like rate limiting

### Frontend Setup
```powershell
# from repo root
npm install
Copy-Item .env.example .env        # supply VITE_* values if needed
npm run dev                        # dev server at http://localhost:5173
```

Environment keys (`.env`):
```
VITE_BACKEND_URL=http://localhost:8000
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

### Backend Setup
```powershell
Set-Location backend
pip install -r requirements.txt
Copy-Item .env.example .env        # populate API keys and secrets
py -m uvicorn main:app --reload --port 8000
```

`backend/.env` expects (subset):
```
GEMINI_API_KEY=...
OPENAI_API_KEY=...
SUPABASE_JWT_SECRET=...
REDIS_URL=redis://localhost:6379/0
STRIPE_SECRET_KEY=...
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
```

### Quick PowerShell Workflow
The repo root contains a ready-made sequence (see user instructions above):
1. Clear ports 8000/5173.
2. Launch FastAPI with logging and capture PID.
3. Verify `/docs` health check and tail `backend_uvicorn.log`.
4. Start Vite dev server with logs to `vite.log`.
5. Validate `http://localhost:5173/@vite/client`.
6. Stop both processes when finished.

## Builds, Tests, and Quality

| Target | Command | Notes |
|--------|---------|-------|
| Client bundle | `npm run build` | Runs Vite client build, SSR bundle, and `scripts/prerender.mjs` (generates `dist`, `dist-ssr`, `sitemap*.xml`). |
| SSR only | `npm run build:ssr` | Produces server bundle at `dist-ssr/entry-server.js`. |
| Static prerender | `npm run prerender` | Recreates HTML snapshots for every project route. |
| Unit tests (frontend) | `npm run test` | Uses Vitest (see `components/**/__tests__`). |
| Backend tests | `pytest backend` | Mocks Gemini, Supabase, and HTTP calls via fixtures. |
| Type check (TS) | `npx tsc --noEmit` | Validates TypeScript across components and services. |

Continuous integration should run `npm run build` and `pytest backend` before deployment; large analytics bundles may trigger Vite chunk warnings (see build logs).

## Deployment Notes

- **Frontend**: Static assets from `dist/` can be hosted on Vercel, Netlify, or Azure Static Web Apps. Upload `dist-ssr/entry-server.js` if SSR is required.
- **Backend**: Deploy FastAPI with Uvicorn/Gunicorn. Configure Redis, Supabase keys, Gemini/OpenAI tokens, and payment providers. Keep `backend/.env` synchronized with production secrets (never commit keys).
- **Sitemaps & SEO**: `scripts/prerender.mjs` writes `sitemap.xml`, `sitemap-pages.xml`, `sitemap-projects.xml`. Ensure `SITE_BASE_URL` in `constants/seo.ts` points to the deployed domain before running the build.
- **Rate limiting**: Enable Redis or provide `DISABLE_REDIS=true` for in-memory fallback; Stripe/PayPal enable paid token packs per docs.

## Additional Resources

- `ARCHITECTURE.md` – high-level diagrams and module references.
- `backend/analytics/ARCHITECTURE.md` – detailed analytics flow documentation.
- `docs/linkedin-photo-rate-limit-plan.md` – rollout plan for global/regional safeguards.
- `docs/linkedin-photo-next-steps.md` – backlog for the LinkedIn generator.
- `docs/analytics-agent-openai-sdk-roadmap.md` – future work on the analytics OpenAI SDK integration.

## Support & Maintainers

- Maintainer: Yanqing Jiang (`https://www.linkedin.com/in/jiangyanqing/`)
- Issues and feature requests: open GitHub issues on `Yanqing-Jiang/ai-portfolio`.

