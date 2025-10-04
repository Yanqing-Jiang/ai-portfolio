## Agent Ground Rules & Tooling
Understand the task before editing: read the full function and its direct call sites, and prefer surgical diffs over speculative refactors. Look into the files, generate a plan of changes first, then execute. Do not add fallback code unless requested; Prioritize PowerShell over Bash. Do not run automated tests yourself; before completion, explicitly remind the user to execute the necessary suites. When generating plan, be more elaborative on concept, use actual examples.

- Snapshot baseline files (e.g. `git show`) before deep edits so expectations like `_sql_phase` stay visible.
- After each change, tell the user which targeted `pytest` module to run (e.g., `pytest backend/test_api.py`) so missing mocks (Polygon keys, etc.) are caught before the full suite.
- Favor JS/TS-aware scripts (e.g. `node -e`) when editing TSX to avoid PowerShell escaping loops.


## Project Structure & Module Organization
The Vite frontend lives at the repo root, with `App.tsx` routing into feature components. UI pieces sit under `components/`, shared data in `constants/` + `constants.ts`, and network helpers in `services/`. The FastAPI backend is in `backend/`, See `ARCHITECTURE.md` for deeper diagrams.

## Build, Test & Development Commands
Install dependencies with `npm install`, then `npm run dev` for the frontend at http://localhost:5173. `npm run build` emits production assets to `dist/`; `npm run preview` serves that bundle. For the backend, `pip install -r requirements.txt` inside `backend/` and start `uvicorn main:app --reload --port 8000`, restarting before summarizing key changes. Use `pytest backend` for Python checks.

## Local Server Startup Cheatsheet

### Backend (FastAPI)
- Stop stale listeners on port 8000: `Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue }`.
- Double-check the port really released before relaunching: `if (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue) { throw "Port 8000 still occupied" }` (rerun the stop command if needed).
- Launch from `backend/` using PowerShell so we honor repo instructions: `Set-Location "backend"; $env:PYTHONPATH="$(Resolve-Path ..)"; python -m uvicorn main:app --reload --port 8000` and keep that window open (Ctrl+C to stop). If you do background it, store the returned PID from `$backend = Start-Process ... -PassThru` so you can `Stop-Process` later and avoid ghost uvicorns.
- Verify the server: `Invoke-RestMethod http://127.0.0.1:8000/docs -TimeoutSec 5 | Out-Null` (returns HTTP 200 when healthy).

### Frontend (Vite)
- Ensure no old Vite job owns port 5173: `Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue }`.
- Start from the repo root with logging to watch output later: `npm run dev *> vite.log`.
- Confirm readiness: open `http://localhost:5173/` in a browser or curl `http://localhost:5173/@vite/client` (expect a 200).

### Shutdown
- Stop both services cleanly when finished: `Stop-Process -Id <uvicorn_pid>,<vite_pid>` and clear the logs if they are no longer needed.

## Testing Guidelines
Tell user how to test in prod. Only test when user instruct to create test file.

## Environment & Secrets
Copy `.env` templates at the root and inside `backend/` before running servers. Snever commit secrets or service-account files.

## Analytics Memory Overview
- Showcases the planner-executor baseline alongside single-agent fan-out and multi-agent orchestration; keep the sequential UX ready as a fallback while surfacing telemetry to ProcessPanel and WorkflowCanvas.
- Session state lives in Redis with a short TTL and enriched SSE metadata (`seq`, `parallel_group`, `tool_group`); review rollout and concurrency tasks in `backend/analytics/TO_DO.md` before editing prompts.
- Execution diagrams, flow wiring, and adapter responsibilities sit in `backend/analytics/ARCHITECTURE.md`; update that file and the TODO whenever analytics memory logic or prompt contracts change.
- Treat prompts as the control surface: align `/api/analytics/memory/stream?flow=<flow>` prompts, flags such as `ANALYTICS_TOOL_PARALLELISM`, and telemetry expectations before merging.
