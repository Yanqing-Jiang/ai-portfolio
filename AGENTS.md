## Agent Ground Rules & Tooling
Understand the task before editing: read the full function and its direct call sites, and prefer surgical diffs over speculative refactors. Look into the files, generate a plan of changes first, then execute. Do not add fallback code unless requested; Prioritize PowerShell over Bash. Always do unit test before you mark completion. When generating plan, be more elaborative on concept, use actual examples.

- if user is asking for a plan, write your plan to docs folder for easy read
- Run targeted `pytest` modules after each change to catch missing mocks (Polygon keys, etc.) before the full suite.
- Favor JS/TS-aware scripts (e.g. `node -e`) when editing TSX to avoid PowerShell escaping loops.

## Project Structure & Module Organization
The Vite frontend lives at the repo root, with `App.tsx` routing into feature components. UI pieces sit under `components/`, shared data in `constants/` + `constants.ts`, and network helpers in `services/`. The FastAPI backend is in `backend/`, See `ARCHITECTURE.md` for deeper diagrams.

## Build, Test & Development Commands
Install dependencies with `npm install`, then `npm run dev` for the frontend at http://localhost:5173. `npm run build` emits production assets to `dist/`; `npm run preview` serves that bundle. For the backend, `pip install -r requirements.txt` inside `backend/` and start `py -m uvicorn main:app --reload --port 8000`, restarting before summarizing key changes. Use `pytest backend` for Python checks.

## Quick Startup Workflow (PowerShell)
1. **Prep backend port 8000**
   ```powershell
   Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue }
   if (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue) { throw "Port 8000 still occupied" }
   ```
2. **Launch backend with logging + PID capture**
   ```powershell
   $backend = Start-Process powershell -ArgumentList '-NoLogo','-NoProfile','-Command','Set-Location ''backend''; $env:PYTHONPATH=(Resolve-Path ''..''); py -m uvicorn main:app --reload --port 8000 *> backend_uvicorn.log' -PassThru
   $backend.Id
   ```
3. **Verify backend health**
   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/docs -TimeoutSec 5 | Out-Null
   Get-Content backend\backend_uvicorn.log -Tail 20
   ```
4. **Prep frontend port 5173**
   ```powershell
   Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue }
   ```
5. **Start Vite dev server with log stream**
   ```powershell
   $frontend = Start-Process powershell -ArgumentList '-NoLogo','-NoProfile','-Command','Set-Location ''C:\Users\Y_J\Desktop\ai-portfolio-main''; npm run dev *> vite.log' -PassThru
   $frontend.Id
   ```
6. **Verify frontend**
   ```powershell
   Invoke-WebRequest http://localhost:5173/@vite/client -TimeoutSec 5 -UseBasicParsing | Out-Null
   Get-Content vite.log -Tail 20
   ```
7. **Shutdown reminder**
   ```powershell
   Stop-Process -Id $backend.Id,$frontend.Id
   ```

## Testing Guidelines
Write backend tests with pytest, naming files `test_<feature>.py` beside the code or under `backend/tests/`, mocking Supabase, Gemini, and external HTTP calls. New UI logic should ship with colocated tests such as `ComponentName.test.tsx`; consider Playwright for flow coverage. 

## Environment & Secrets
Copy `.env` templates at the root and inside `backend/` before running servers. Never commit secrets or service-account files.

## Analytics Memory Overview
- Showcases the planner-executor baseline alongside single-agent fan-out and multi-agent orchestration; keep the sequential UX ready as a fallback while surfacing telemetry to ProcessPanel and WorkflowCanvas.
- Session state lives in Redis with a short TTL and enriched SSE metadata (`seq`, `parallel_group`, `tool_group`); review rollout and concurrency tasks in `backend/analytics/TO_DO.md` before editing prompts.
- Execution diagrams, flow wiring, and adapter responsibilities sit in `backend/analytics/ARCHITECTURE.md`; update that file and the TODO whenever analytics memory logic or prompt contracts change.
- Treat prompts as the control surface: align `/api/analytics/memory/stream?flow=<flow>` prompts, flags such as `ANALYTICS_TOOL_PARALLELISM`, and telemetry expectations before merging.

