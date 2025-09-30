## Agent Ground Rules & Tooling
Understand the task before editing: read the full function and its direct call sites, and prefer surgical diffs over speculative refactors. Look into the files, generate a plan of changes first, then execute. Do not add fallback code unless requested; Prioritize PowerShell over Bash. Always do unit test before you mark completion. When generating plan, be more elaborative on concept, use actual examples.

## Project Structure & Module Organization
The Vite frontend lives at the repo root, with `App.tsx` routing into feature components. UI pieces sit under `components/`, shared data in `constants/` + `constants.ts`, and network helpers in `services/`. The FastAPI backend is in `backend/`, See `ARCHITECTURE.md` for deeper diagrams.

## Build, Test & Development Commands
Install dependencies with `npm install`, then `npm run dev` for the frontend at http://localhost:5173. `npm run build` emits production assets to `dist/`; `npm run preview` serves that bundle. For the backend, `pip install -r requirements.txt` inside `backend/` and start `uvicorn main:app --reload --port 8000`, restarting before summarizing key changes. Use `pytest backend` for Python checks.

## Testing Guidelines
Write backend tests with pytest, naming files `test_<feature>.py` beside the code or under `backend/tests/`, mocking Supabase, Gemini, and external HTTP calls. New UI logic should ship with colocated tests such as `ComponentName.test.tsx`; consider Playwright for flow coverage. 

## Environment & Secrets
Copy `.env` templates at the root and inside `backend/` before running servers. Snever commit secrets or service-account files.

## Analytics Memory Flow Modes
- Use `/api/analytics/memory/stream?flow=<flow>` to select the demo experience surfaced in the Memory page (legacy `mode` query param is still accepted for backwards compatibility).
- `planner-executor`: deterministic planner/executor baseline that emits ordered SQL + result telemetry from the YAML catalogue.
- `single-agent`: single agent with many tools; wraps the baseline events with `tool_call` start/end payloads to highlight tool orchestration.
- `multi-agent`: lightweight coordinator that layers `agent_turn` and `agent_reasoning` events on top of the planner stream so the frontend can visualize roles handing work off.
- Flow metadata comes from `backend/analytics/flows/workflow.py::get_available_flows()`. Keep frontend selectors in sync with that mapping.

## Streaming Telemetry Reference
- Core SSE events across all flows: `classification_*`, `intent_*`, `clarification_*`, `progress`, `status`, `sql_generated`, `analysis_streaming`, `result`, `final_answer`, `done`, and `error`.
- Demo-specific enrichments: `tool_call` (single-agent), `agent_turn` and `agent_reasoning` (multi-agent) augment the stream for visualization overlays.
- Frontend consumers: `useAnalyticsMemoryStream`, `ProcessPanel`, and `WorkflowCanvas` subscribe to the stream and must handle these payloads.

