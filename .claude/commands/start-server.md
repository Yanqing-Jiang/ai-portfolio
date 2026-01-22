---
description: Start backend and frontend development servers
allowed-tools: Bash
argument-hint:
---

# Start Development Servers

## Purpose
Launches both the backend Python server (port 8000) and frontend Node.js dev server (port 5173) in parallel. **Automatically restarts** if servers are already running.

## Usage
```bash
/start-server
```

## Workflow

### Step 1: Kill Existing Servers + Node Modules Check (parallel)
Run these in parallel:

**Check ports and kill if in use:**
```bash
netstat -ano | findstr :8000 | findstr LISTENING
netstat -ano | findstr :5173 | findstr LISTENING
```
If either shows a PID (last column), kill it with: `taskkill //PID <pid> //F`
- Use `//PID` not `/PID` (Git Bash escaping)
- Always kill existing servers before starting new ones (auto-restart behavior)
- Suppress "not found" errors - it's fine if no process exists

**Node modules health check:**
```bash
node -e "require('@rollup/rollup-win32-x64-msvc')" 2>nul && echo OK || echo BROKEN
```
- OK = modules fine, proceed
- BROKEN = run `npm install` (NOT full reinstall)

Only if npm install fails, do full reinstall:
```bash
rm -rf node_modules package-lock.json && npm install
```

### Step 2: Start Both Servers (parallel)
Launch both in same message using `run_in_background: true`:

Backend:
```bash
cd backend && python main.py
```

Frontend:
```bash
npm run dev
```

### Step 3: Verify (single check after 3s)
```bash
sleep 3 && netstat -ano | findstr ":8000 :5173"
```
Both ports should show LISTENING. Output PIDs and URLs.

## Important Notes

### Bash Path Handling
- **Use relative paths** (`cd backend`) not absolute Windows paths
- Backslashes get stripped by bash in WSL environment
- For WSL commands requiring PATH, use single quotes: `wsl bash -c 'PATH="$HOME/.nvm/..." node -v'`

### Process Management
- Both servers run in background with `&` to avoid blocking terminal
- Track process IDs in case user needs to kill servers later
- If npm command fails, verify Node/npm are in PATH

### Troubleshooting
- **Address already in use**: Rerun port check and kill conflicting process
- **Cannot find @rollup/rollup-win32-x64-msvc**: Known npm bug with optional deps. Fix: `npm install`. If persists: delete node_modules + package-lock.json, then reinstall
- Backend requires Python 3.x and dependencies from requirements.txt
- Frontend requires Node.js 18+ and packages from package.json
