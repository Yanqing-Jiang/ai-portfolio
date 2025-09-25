## Agent Ground Rules & Tooling
Understand the task before editing: read the full function and its direct call sites, and prefer surgical diffs over speculative refactors. Plan first, then execute. Do not add fallback code unless requested; keep behaviour stable. When using GPT Mini tooling, target `gpt-5-mini-2025-08-07`. Always restart relevant services after code changes and before reporting status. Prioritize PowerShell over Bash. Always do unit test before you mark completion. 

## Project Structure & Module Organization
The Vite frontend lives at the repo root, with `App.tsx` routing into feature components. UI pieces sit under `components/`, shared data in `constants/` + `constants.ts`, and network helpers in `services/`. The FastAPI backend is in `backend/`, See `ARCHITECTURE.md` for deeper diagrams.

## Build, Test & Development Commands
Install dependencies with `npm install`, then `npm run dev` for the frontend at http://localhost:5173. `npm run build` emits production assets to `dist/`; `npm run preview` serves that bundle. For the backend, `pip install -r requirements.txt` inside `backend/` and start `uvicorn main:app --reload --port 8000`, restarting before summarizing key changes. Use `pytest backend` for Python checks.

## Testing Guidelines
Write backend tests with pytest, naming files `test_<feature>.py` beside the code or under `backend/tests/`, mocking Supabase, Gemini, and external HTTP calls. New UI logic should ship with colocated tests such as `ComponentName.test.tsx`; consider Playwright for flow coverage. 


## Environment & Secrets
Copy `.env` templates at the root and inside `backend/` before running servers. Snever commit secrets or service-account files. 