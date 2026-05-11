#!/bin/bash
# autodeploy-backend.sh — polls origin/main and rebuilds the backend Docker
# container when backend-relevant paths change. Invoked every 60s by the
# LaunchAgent at ~/Library/LaunchAgents/com.portfolio.autodeploy.plist.
#
# Design notes:
#   - Frontend auto-deploys via GitHub Actions → Cloudflare Pages. The
#     backend lives on this Mac Mini behind CF Tunnel, so we close the gap
#     with a polling daemon rather than a self-hosted GH Actions runner —
#     fewer moving parts, no runner registration tokens, no public ports.
#   - Lock dir prevents two ticks overlapping if a rebuild runs long.
#   - We only rebuild when files under backend/ or docker-compose.yml shift;
#     frontend-only pushes still fast-forward the working tree but skip
#     the (slow, demo-disrupting) docker rebuild.
#   - Build failures leave the previous container running (docker compose
#     --build keeps the live container if the new image fails to build).
#     We log loudly; no auto-rollback per matched-frontend-posture decision.
#
# Disable: launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.portfolio.autodeploy.plist
# Logs:    /Users/yj/scripts/portfolio-autodeploy.log

set -uo pipefail

REPO_DIR="/Users/yj/ai-portfolio"
LOG_FILE="/Users/yj/scripts/portfolio-autodeploy.log"
LOCK_DIR="/tmp/portfolio-autodeploy.lock"
HEALTH_URL="https://portfolio-api.yanqing.app/health"
WATCH_PATHS=("backend/" "docker-compose.yml")

# LaunchAgent runs with a minimal PATH; docker/git/curl all live in places
# that aren't on the default agent PATH.
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"
export GIT_TERMINAL_PROMPT=0

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

# Single-flight: atomic mkdir is the cheapest portable lock on macOS (no flock).
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

# Rotate log if >5MB so the daemon doesn't fill the disk over months.
if [ -f "$LOG_FILE" ] && [ "$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)" -gt 5242880 ]; then
  tail -n 2000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

mkdir -p "$(dirname "$LOG_FILE")"

cd "$REPO_DIR" || { log "FATAL: cd $REPO_DIR failed"; exit 1; }

if ! git fetch origin main --quiet 2>>"$LOG_FILE"; then
  log "git fetch failed (network blip?); will retry next tick"
  exit 0
fi

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
  # No drift — silent exit so the log doesn't churn once per minute.
  exit 0
fi

log "drift: HEAD=${LOCAL:0:7} → origin/main=${REMOTE:0:7}"

# Detect whether backend-relevant paths moved. Path-based filter keeps
# frontend-only pushes from triggering a 60-90s docker rebuild that
# nobody asked for.
CHANGED_FILES=$(git diff --name-only "$LOCAL" "$REMOTE")
NEEDS_REBUILD=false
for path in "${WATCH_PATHS[@]}"; do
  if echo "$CHANGED_FILES" | grep -q "^${path}"; then
    NEEDS_REBUILD=true
    log "  → ${path} touched"
  fi
done

if ! git pull --ff-only origin main >>"$LOG_FILE" 2>&1; then
  log "FATAL: git pull --ff-only failed (non-fast-forward divergence); aborting"
  exit 1
fi

if [ "$NEEDS_REBUILD" = "false" ]; then
  log "pulled ${REMOTE:0:7} — no backend changes, no rebuild needed"
  exit 0
fi

log "rebuilding backend container..."
START=$(date +%s)

if ! docker compose up -d --build backend >>"$LOG_FILE" 2>&1; then
  log "FATAL: docker compose --build failed (see log above); previous container still serving"
  exit 1
fi

ELAPSED=$(( $(date +%s) - START ))
log "rebuild + restart complete in ${ELAPSED}s"

# Give gunicorn workers a moment to bind before the health probe.
sleep 5

if curl -fsS --max-time 10 "$HEALTH_URL" >/dev/null 2>&1; then
  log "health check OK: $HEALTH_URL"
else
  log "WARNING: health check failed at $HEALTH_URL — container may still be warming up; check 'docker compose logs backend'"
fi

log "deploy of ${REMOTE:0:7} complete"
