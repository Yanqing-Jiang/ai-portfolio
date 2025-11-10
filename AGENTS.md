## Agent Ground Rules & Tooling
Understand the task before editing: read the full function and its direct call sites, and prefer surgical diffs over speculative refactors. 
Do not add fallback code unless requested; 
Prioritize PowerShell over Bash.  
List any unresolved questions at the end, if any.
- For each file, ensure every function has a summary block at the top describing what it does, which modules call it, what it invokes next, and why it exists in the project (e.g., `Function: fetchUserData — called from App.tsx, forwards results to ProfileCard to render user details`).
- Favor JS/TS-aware scripts (e.g. `node -e`) when editing TSX to avoid PowerShell escaping loops.
- Always prioritize `gpt-5-mini-2025-08-07` for agent models and see `docs/gpt5-best-practices.md` for GPT-5 configuration guidance.

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
