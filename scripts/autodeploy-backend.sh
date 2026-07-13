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
STATE_FILE="/Users/yj/.local/state/portfolio-autodeploy-backend.sha"
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

# Track the revision whose backend deployment actually completed. Git HEAD is
# only the checked-out source revision: a migration/build may fail after the
# pull, so using HEAD as the baseline would suppress every later retry.
mkdir -p "$(dirname "$STATE_FILE")"
LOCAL=$(git rev-parse HEAD)
if [ ! -s "$STATE_FILE" ]; then
  # Seed one revision behind so the first run of this stateful script also
  # retries a commit that an older script may already have pulled before its
  # migration failed. One conservative extra rebuild is safer than silently
  # treating an un-deployed checkout as deployed.
  git rev-parse HEAD^ > "$STATE_FILE" 2>/dev/null || printf '%s\n' "$LOCAL" > "$STATE_FILE"
fi
DEPLOYED=$(cat "$STATE_FILE")
if ! git cat-file -e "${DEPLOYED}^{commit}" 2>/dev/null; then
  log "WARNING: invalid deployment state; resetting baseline to ${LOCAL:0:7}"
  DEPLOYED="$LOCAL"
  printf '%s\n' "$DEPLOYED" > "$STATE_FILE"
fi

if ! git fetch origin main --quiet 2>>"$LOG_FILE"; then
  log "git fetch failed (network blip?); will retry next tick"
  exit 0
fi

REMOTE=$(git rev-parse origin/main)

if [ "$DEPLOYED" = "$REMOTE" ]; then
  # No drift — silent exit so the log doesn't churn once per minute.
  exit 0
fi

log "drift: deployed=${DEPLOYED:0:7}, HEAD=${LOCAL:0:7} → origin/main=${REMOTE:0:7}"

# Detect whether backend-relevant paths moved. Path-based filter keeps
# frontend-only pushes from triggering a 60-90s docker rebuild that
# nobody asked for.
CHANGED_FILES=$(git diff --name-only "$DEPLOYED" "$REMOTE")
NEEDS_REBUILD=false
for path in "${WATCH_PATHS[@]}"; do
  if echo "$CHANGED_FILES" | grep -q "^${path}"; then
    NEEDS_REBUILD=true
    log "  → ${path} touched"
  fi
done

if [ "$LOCAL" != "$REMOTE" ]; then
  if ! git pull --ff-only origin main >>"$LOG_FILE" 2>&1; then
    log "FATAL: git pull --ff-only failed (non-fast-forward divergence); aborting"
    exit 1
  fi
fi

if [ "$NEEDS_REBUILD" = "false" ]; then
  printf '%s\n' "$REMOTE" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
  log "pulled ${REMOTE:0:7} — no backend changes, no rebuild needed"
  exit 0
fi

# Database changes must land before code that requires them. Run only the SQL
# migrations introduced/changed by this fast-forward, using the existing
# backend image for its asyncpg dependency and production env. Any failure is a
# hard gate: the live container stays untouched and the next poll retries.
MIGRATIONS=$(echo "$CHANGED_FILES" | grep '^backend/migrations/[^/]*\.sql$' | sort || true)
if [ -n "$MIGRATIONS" ]; then
  while IFS= read -r migration; do
    migration_name=$(basename "$migration")
    log "applying migration ${migration_name} before backend restart..."
    if ! docker compose run --rm --no-deps -T \
      -v "$REPO_DIR/backend:/workspace:ro" \
      backend python /workspace/scripts/apply_migration.py \
      "/workspace/migrations/${migration_name}" >>"$LOG_FILE" 2>&1; then
      log "FATAL: migration ${migration_name} failed; backend deployment blocked"
      exit 1
    fi
    log "migration ${migration_name} applied"
  done <<< "$MIGRATIONS"
fi

log "rebuilding backend container..."
START=$(date +%s)

if ! docker compose up -d --build backend >>"$LOG_FILE" 2>&1; then
  log "FATAL: docker compose --build failed (see log above); previous container still serving"
  exit 1
fi

ELAPSED=$(( $(date +%s) - START ))
log "rebuild + restart complete in ${ELAPSED}s"

# Give gunicorn workers a moment to bind, then require health before advancing
# the deployed-SHA marker. A failed probe leaves the old marker intact so the
# daemon retries this revision on its next poll.
sleep 5
HEALTHY=false
for attempt in 1 2 3 4 5 6; do
  if curl -fsS --max-time 10 "$HEALTH_URL" >/dev/null 2>&1; then
    HEALTHY=true
    break
  fi
  log "health check attempt ${attempt}/6 failed; retrying in 5s"
  sleep 5
done

if [[ "$HEALTHY" != "true" ]]; then
  log "FATAL: health check failed at $HEALTH_URL; deployment marker not advanced"
  exit 1
fi
log "health check OK: $HEALTH_URL"

log "deploy of ${REMOTE:0:7} complete"
printf '%s\n' "$REMOTE" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
