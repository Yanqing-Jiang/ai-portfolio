# System Architecture

Yanqing Jiang’s AI portfolio is a full-stack system that pairs a Vite + React experience with a FastAPI backend. The platform showcases multiple AI workflows (analytics copilots, research agents, resume Q&A, LinkedIn headshot generation) while prerendering static assets and streaming real-time insights.

## Infrastructure

```
                         Cloudflare Network
                    ┌──────────────────────────┐
    Users ────────▶ │  yanqing.app             │──▶  Cloudflare Pages (static frontend)
                    │  portfolio-api.yanqing.app│──▶  Cloudflare Tunnel ──┐
                    └──────────────────────────┘                         │
                                                                         ▼
                                                              Mac Mini (Apple Silicon)
                                                         ┌────────────────────────────┐
                                                         │  Docker Compose            │
                                                         │  ├─ portfolio-backend :8100│
                                                         │  │  (gunicorn + uvicorn)   │
                                                         │  └─ portfolio-redis        │
                                                         │                            │
                                                         │  launchd services          │
                                                         │  ├─ cloudflared (tunnel)   │
                                                         │  └─ com.portfolio.monitor  │
                                                         └────────────────────────────┘
```

| Component | Host | URL |
|-----------|------|-----|
| Frontend (static) | Cloudflare Pages | `https://yanqing.app` (`ai-portfolio-6jm.pages.dev`) |
| Backend API | Mac Mini (Docker) | `https://portfolio-api.yanqing.app` → `localhost:8100` |
| Redis | Mac Mini (Docker) | `redis://redis:6379/0` (internal Docker network) |
| Database | Supabase (AWS us-west-1) | PostgreSQL via `asyncpg` connection pool |
| DNS | Cloudflare (zones: `yanqing.app`, `jiangyanqing.com`) | Authoritative nameservers |
| Tunnel | Cloudflare Tunnel (`homer-tunnel`) | Routes `portfolio-api.yanqing.app` → local backend |
| Redirect | Cloudflare Pages | `jiangyanqing.com` / `www.jiangyanqing.com` → 301 to `yanqing.app` |

## Application Architecture

```
┌──────────────┐      HTTPS / SSE       ┌──────────────────────────┐
│  React 19 /  │  ───────────────────▶  │  FastAPI (gunicorn)       │
│  Vite client │   Auth, REST, Streams  │  - Analytics suite        │
│  (SSR-ready) │  ◀───────────────────  │  - LinkedIn photo router  │
└──────┬───────┘      JSON / events     │  - Research & resume      │
       │                                │  - Rate limiting & auth   │
       │                                └────────────┬──────────────┘
       │                                             │
       │        External APIs / Services             │
       ├───────────────┬─────────────────────────────┘
       │               │
  Supabase Auth   Gemini / OpenAI / Search APIs   Redis / Stripe / PayPal
```

## Platform Overview

- **Frontend**: React 19 with TypeScript, Vite 6, Tailwind utility classes (via `tailwind-merge`), Framer Motion, React Router 6, and `react-helmet-async` for SEO.
- **Backend**: FastAPI with Python 3.11, orchestrating analytics LangGraph-style flows, Gemini integrations, research/resume agents, LinkedIn image editing, and payments-aware rate limiting.
- **Static delivery**: Vite builds both SPA and SSR bundles; `scripts/prerender.mjs` renders HTML snapshots and sitemaps for every project page.
- **Docs**: Deep-dives live in `backend/analytics/ARCHITECTURE.md`, `docs/linkedin-photo-*.md`, and `docs/analytics-agent-openai-sdk-roadmap.md`.

## Frontend Architecture

### App Shell & Routing

- `App.tsx` mounts the React Router hierarchy inside a `HelmetProvider`. It renders the landing page at `/` and project pages at `/project/:projectId`.
- `components/Sidebar.tsx` drives navigation. `components/ProjectView.tsx` selects feature modules (analytics demos, LinkedIn Photo page, legacy markdown content) and renders `ProjectHelmet`.
- `components/LandingPage.tsx` builds the animated project grid, injecting metadata via `useMemo` and `LANDING_SEO`.

### Feature Modules

- **Analytics demos** (`components/analytics/**`):
  - `memory/`, `sql/`, `common/`, and `visualization/` combine to render planner-executor, single-agent, and multi-agent flows.
  - UI surfaces streaming telemetry (progress lanes, SQL output, charts, topic cards) that maps onto backend SSE events.
- **LinkedIn Photo generator** (`components/linkedinPhoto/**`):
  - `Page.tsx` hosts the three-step wizard (upload, style, review), using `fetch` calls against `/api/linkedin-photo/*` routes.
  - `CustomStyleBuilder`, `VariationControls`, and `ImageVariationGallery` let users craft and download Gemini-edited iterations.
- **Chat surface** (`components/Chat.tsx`) powers conversations with selected agents, managing message state and typing indicators.
- **Shared UI** lives in `components/ui/` (cards, buttons, progress) and `components/icons/`.

### State, Services, and Utilities

- `services/apiService.ts` centralizes REST + SSE calls, attaches Supabase JWTs, and normalizes error handling (`needsAuth`, rate-limit flags).
- `services/backendGeminiService.ts` handles Gemini text streaming for chat experiences.
- `services/auth.ts` wraps Supabase client helpers.
- `services/config.ts` exposes environment-driven backend URLs, cached in refs for runtime overrides.
- Project metadata, SEO, and stats come from `constants.ts`, `constants/seo.ts`, and `constants/structuredData.ts`.

### Styling, Animations, and Accessibility

- Tailwind-style class composition handled by `tailwind-merge`.
- Transitions and layout animations run through Framer Motion (`components/ProjectView.tsx`, analytics panels).
- Inputs and ARIA-friendly patterns leveraged from Radix UI (`@radix-ui/react-progress` etc.).

### SEO, SSR, and Prerendering

- `components/ProjectHelmet.tsx` assembles canonical, Open Graph, Twitter, and schema.org metadata per project using the shared SEO constants.
- `constants/structuredData.ts` builds JSON-LD payloads (Website, OfferCatalog, BreadcrumbList, Article).
- `ssr/entry-server.tsx` renders routes server-side for the prerender step; exports sitemap helpers that rely on project metadata.
- `scripts/prerender.mjs` crawls every route, writes `dist/` HTML snapshots, `sitemap*.xml`, and normalized JSON assets.

## Backend Architecture

### FastAPI Entry Point

- `backend/main.py` loads `.env`, configures CORS, initializes logging, and includes routers:
  - Analytics suite endpoints (`/api/analytics/...`)
  - LinkedIn photo routes (`/api/linkedin-photo/...`)
  - Research agent, resume agent, Gemini chat proxy, TTS service
  - Rate-limit counters, payments endpoints, health checks
- SSE responses stream via `StreamingResponse` with async generators feeding analytics telemetry.

### Analytics Suite (`backend/analytics/`)

- **Core** modules manage session state, caching, telemetry events, and output normalization shared across flows.
- **Flows** (`flows/workflow.py`) orchestrate:
  - `planner-executor` (deterministic tool chain)
  - `single-agent` (adaptive LangGraph agent)
  - `multi-agent` (supervisor + specialists)
- **SQL** (`sql/`) compiles YAML templates from `backend/config/schemas/*.yaml`, validates proposed queries, and coordinates execution/caching.
- **Streaming** utilities map backend events to structured payloads consumed by the frontend process panel.
- Legacy packages (`analytics_memory`, `analytics_shared`, `analytics_supervisor`) were replaced; this repo imports exclusively from `backend/analytics/`.
- `backend/analytics/ARCHITECTURE.md` documents flow diagrams and component-level contracts.

### LinkedIn Photo Service (`backend/linkedin_photo/`)

- `router.py` hosts endpoints:
  - `GET /prompts` returns canonical preset expansions.
  - `POST /generate` validates image uploads (Pillow), expands style prompts with Gemini, and returns headshot + metadata.
  - `POST /variation` produces follow-up edits.
- `service.py` manages storage, Gemini API orchestration (Nano Banana endpoint), and output packaging.
- `fixed_prompts.py` maintains curated style presets used by the frontend wizard.
- Docs in `docs/linkedin-photo-rate-limit-plan.md` and `docs/linkedin-photo-next-steps.md` describe upcoming quotas, DB schema migrations, and backlog.

### Agent APIs and Shared Services

- `research_agent.py` executes web searches (via configured APIs), performs summarization, and streams responses.
- `resume_agent.py` loads resume embeddings and answers candidate-specific queries.
- `gemini_service.py` wraps Gemini text sessions with caching and token accounting.
- `tts.py` produces speech assets for front-of-house demos.
- `token_store.py`, `rate_limiter.py`, and `analytics_agent.py` provide shared utilities for session quotas and legacy workflows.
- Payments: optional Stripe and PayPal integrations (configured via `.env`) grant additional token balances; Stripe webhooks validated when keys are present.

### Configuration and Environment

- `.env` files at repo root and `backend/.env` control Supabase, Gemini, OpenAI, Redis, Stripe, PayPal, and rate-limit toggles.
- `backend/.env.production` contains production-specific settings (used by Docker via `docker-compose.yml`).
- `backend/config/schemas/` stores YAML definitions for analytics catalogues and SQL scaffolding.
- `public/` holds static assets (project images, OG banners, JSON feeds) served by the frontend build and referenced in SEO metadata.

### Testing

- Backend tests live in `backend/tests/`, leveraging pytest fixtures to mock Gemini, Supabase, HTTP clients, and storage.
- Frontend unit tests use Vitest within `components/**/__tests__`.
- E2E and playwright screenshots in the repo demonstrate UI regression steps (e.g., `playwright_snapshot.png`).

## Data & Interaction Flows

### Authentication & Rate Limiting

```
Browser                    Frontend API                 FastAPI Backend            Supabase / Redis
   |  Sign in via Supabase UI   |                            |                          |
   |--------------------------->|                            |                          |
   |   receives JWT (client)    |                            |                          |
   |                            |  request + Authorization   |                          |
   |                            |--------------------------->|                          |
   |                            |                            | verify JWT via Supabase |
   |                            |                            | check rate limits (Redis)|
   |                            |                            |------------------------->|
   |                            |                            |<-------------------------|
   |                            |<---------------------------| JSON / SSE payload       |
```

- Guest quota: 5 requests/day (IP-based). Authenticated quota: 20 requests/day (user-based). Token purchases merge through `token_store.py`.

### Analytics Streaming Pipeline

1. Frontend calls `apiService.streamWithAuth('/api/analytics/memory/stream')`.
2. `backend/analytics/flows/workflow.py` selects the configured flow (`flow` query parameter).
3. Planner builds task graph, invokes SQL template builder, executes queries, and emits telemetry events.
4. `StreamingResponse` yields event types (`progress`, `sql_generated`, `tool_call`, `agent_turn`, `agent_reasoning`, `final_answer`).
5. `components/analytics/common/ProcessPanel.tsx` maps events into lanes, charts, and summaries in real time.

### LinkedIn Photo Pipeline

```
Upload Photo (Step 1)
   ↓ validate file type/size via FastAPI + Pillow
Style Prompt (Step 2)
   ↓ Gemini text expansion → prompt transparency copy
Generate / Variation (Step 3)
   ↓ Gemini image edit (Nano Banana) → PNG response
Review & Download
   ↓ Frontend stores preview URLs, exposes share/download actions
```

- Additional preset requests (`GET /prompts`) hydrate Step 2 cards with curated style text.
- Variation endpoint reuses base metadata and produces iterative assets for gallery download.

### Research & Resume Agents

- `/api/research/stream`:
  1. Frontend streams query.
  2. Backend performs HTTP search, collects snippets, and summarizes with OpenAI/Gemini.
  3. SSE responses feed `components/analytics/common/WebSearchCard`.
- `/api/resume-search/stream`:
  - Uses vector recall against stored resume data, returning structured answers with citations.

## Build, Tooling, and Deployment

- **Frontend commands** (`package.json`):
  - `npm run dev` – Vite dev server (`http://localhost:5173`).
  - `npm run build` – client + SSR builds plus prerender step.
  - `npm run preview` – serve production bundle.
  - `npm run test` – Vitest unit suite.
- **Backend commands**:
  - `pip install -r backend/requirements.txt`
  - `py -m uvicorn main:app --reload --port 8000`
  - `pytest backend`
- **Prerender**: `node scripts/prerender.mjs` (invoked by build) emits `dist/`, `dist-ssr/`, `sitemap.xml`, `sitemap-pages.xml`, `sitemap-projects.xml`, and project JSON caches.
### Production Deployment

**Frontend** – Cloudflare Pages (static site)
- Deployed via GitHub Actions on push to `main` (`.github/workflows/deploy.yml`)
- Build: `npm run build` → output `dist/`
- Environment variables set in CF Pages dashboard (VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_APP_URL, VITE_BACKEND_URL, NODE_VERSION)
- Custom domain: `yanqing.app` (CNAME → `ai-portfolio-6jm.pages.dev`)

**Backend** – Mac Mini via Docker Compose + Cloudflare Tunnel
- `docker-compose.yml` runs FastAPI (gunicorn, 2 uvicorn workers) + Redis 7
- Container `portfolio-backend` on port 8100, `portfolio-redis` on internal network
- Exposed via Cloudflare Tunnel at `portfolio-api.yanqing.app`
- Health monitor: `com.portfolio.monitor.plist` (launchd, checks every 5 min)
- Backend rebuild: `docker compose up -d --build`

**DNS & CDN** – Cloudflare
- Zone `yanqing.app`: `yanqing.app` → CF Pages (proxied CNAME), `portfolio-api.yanqing.app` → CF Tunnel → `localhost:8100`
- Zone `jiangyanqing.com`: `jiangyanqing.com` + `www` → CF Pages redirect project (`jiangyanqing-redirect`) → 301 to `yanqing.app`

**Domain Redirect** – `jiangyanqing.com`
- Separate CF Pages project (`jiangyanqing-redirect`) with a `_redirects` file: `/* https://yanqing.app/:splat 301`
- Custom domains `jiangyanqing.com` and `www.jiangyanqing.com` attached to that project
- All paths preserved in redirect (e.g., `/project/agent-to-ui` → `https://yanqing.app/project/agent-to-ui`)

**Key deployment notes**:
- `SITE_BASE_URL` in `constants/seo.ts` must match the deployed domain.
- SSE streams require heartbeats every 20s (`backend/sse_utils.py`). CF Tunnel Free plan has 100s idle timeout. The heartbeat wrapper uses `asyncio.wait` (not `wait_for`) to avoid cancelling upstream generators.
- Backend `.env.production` is mounted by Docker; never commit secrets.
- Render is fully decommissioned — no services remain on Render.

## Observability & Assets

- Backend logs: `docker compose logs -f backend`
- Health monitor log: `~/scripts/portfolio-monitor.log`
- Prerender logs and analytics demo replays live in `backend/baseline_log.txt`, `scripts/replay_revision.py`, and `scripts/report_slot_catalog_usage.py`.
- Sitemap and SSR outputs reside in `dist/`, `dist-ssr/`, and `docs/` snapshots for verification.

## Documentation Map

- `README.md` – Quickstart, repository layout, commands, deployment.
- `ARCHITECTURE.md` (this file) – System-wide overview.
- `backend/analytics/ARCHITECTURE.md` – Deep dive into analytics flows, agents, and telemetry event contracts.
- `docs/linkedin-photo-rate-limit-plan.md` – Proposed database schema and smart rate limit guardrails for the headshot generator.
- `docs/linkedin-photo-next-steps.md` – Implementation backlog, UX enhancements, and monitoring tasks.
- `docs/analytics-agent-openai-sdk-roadmap.md` – Future plan for OpenAI SDK integration within analytics agents.

---

This document should be updated whenever new agents, payment flows, or frontend modules land so that diagrams and references stay accurate.
