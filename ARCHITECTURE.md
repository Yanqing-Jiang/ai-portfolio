# System Architecture

## Runtime Topology

```text
Browser
  |-- yanqing.app ----------------------> Cloudflare Pages
  `-- portfolio-api.yanqing.app --------> Cloudflare Tunnel
                                             |
                                             v
                                      Mac Mini / Docker
                                      |-- FastAPI :8000
                                      `-- Redis :6379
                                             |
                                             v
                                          Supabase
```

The frontend is a prerendered Vite application. Interactive project pages call
the FastAPI backend over JSON or Server-Sent Events. Redis provides rate-limit
and ephemeral shared state; Supabase stores durable application data.

## Frontend

`App.tsx` defines the landing and project routes. `components/ProjectView.tsx`
selects a dedicated live experience when one exists and otherwise renders the
shared project chat.

Primary feature boundaries:

- `components/conversationalAnalytics/`: canonical analytics chat, charts,
  tables, process traces, and clarification UI.
- `components/generativeUiDashboard/`: A2UI renderer, dashboard widgets, and
  Fortune screens.
- `components/linkedinPhoto/`: upload, style, generation, and review workflow.
- `components/Chat.tsx`: generic Gemini chat for portfolio case studies.
- `constants.ts` and `constants/`: project metadata, SEO, and structured data.
- `ssr/entry-server.tsx` and `scripts/prerender.mjs`: static rendering,
  sitemaps, and project feeds.

The historical `next-gen-analytics-agent` slug is an alias for the canonical
Conversational Analytics UI. Research GPT and Ask My Resume remain portfolio
entries but use generic project chat; no dedicated research or resume API
exists.

## Backend

`backend/main.py` owns application setup, CORS, health checks, shared Gemini
chat, text-to-speech, payments, and router registration.

Mounted feature routers:

- `backend/conversational_analytics/` at `/api/conv-analytics`
- `backend/generative_ui/` for generative dashboard APIs
- `backend/fortune/` at `/api/fortune`
- `backend/linkedin_photo/` at `/api/linkedin-photo`

`GET /api/analytics/canonical` is the discovery endpoint for the canonical
analytics implementation.

### Conversational Analytics

The browser opens an SSE request to `/api/conv-analytics/stream`. The backend
selects tools, queries the financial database, creates analysis and chart
artifacts, and streams typed events. The React process panel projects those
events into user-visible progress and results.

### Generative UI

The generative UI runtime converts agent output into A2UI messages. The
frontend message processor updates a normalized surface and the component
registry renders the requested standard or domain widget.

### Fortune

Fortune creation computes the foundation and opens a streamed agent run.
Supabase snapshots provide durable replay, including user corrections.
Redis-backed response chains and SQL-backed Ask sessions preserve follow-up
context.

Active stream coordination still uses `FortuneStore`, a process-local cache.
For that reason `backend/Dockerfile` runs exactly one gunicorn worker. Raising
the worker count before moving that state to a shared store would reintroduce
cross-worker 404s.

### LinkedIn Photo

The service validates uploaded images, expands the selected style into a
photography prompt, calls Gemini image editing, and returns the generated image
with prompt metadata for review.

## State And Persistence

| State | Store | Lifetime |
|---|---|---|
| Project catalog and SEO | Source files / prerendered output | Build |
| Rate limits and response chains | Redis | Ephemeral |
| Fortune active stream state | Process memory | Active run |
| Fortune snapshots and corrections | Supabase PostgreSQL | Durable |
| Analytics sessions and financial data | Supabase PostgreSQL | Durable |
| Browser auth | Supabase JWT | Session |

Fortune SSE sequence numbers are reserved atomically in `fortune_run`.
Snapshots, not an event-log mirror, are the replay contract.

## Build And Deployment

`npm run build` runs:

1. Vite client build
2. Vite SSR build
3. Static prerendering

GitHub Actions runs frontend tests and the build before deploying `dist/` to
Cloudflare Pages. `docker-compose.yml` runs the backend and Redis locally on
the production Mac Mini, with Cloudflare Tunnel providing the public API
hostname.

## Verification Boundaries

- `tests/seo/`: prerender, metadata, sitemap, and structured-data contracts.
- `backend/tests/test_provider_health.py`: provider configuration checks.
- `backend/tests/test_route_contract.py`: active and retired route contract.
- `npm run build`: TypeScript bundling, SSR, and prerender integration.
- `python -m compileall -q backend scripts`: Python import and syntax sweep.
