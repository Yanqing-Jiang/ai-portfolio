#!/usr/bin/env bash
# Canary watch — tails docker logs + Supabase status checks every 5 min.
# Run in a separate terminal after canary_deploy.sh; Ctrl-C to stop.
#
# Outputs to ~/homer/output/claude/canary-watch-$(date +%F-%H%M).log
# so the post-canary writeup has a paper trail.

set -uo pipefail

OUT="${HOME}/homer/output/claude/canary-watch-$(date +%F-%H%M).log"
mkdir -p "$(dirname "$OUT")"
echo "==> Watch log: $OUT"

# Background: docker logs filtered to anything actionable
(docker compose logs -f --tail=0 backend 2>&1 \
  | grep --line-buffered -E "ERROR|Exception|Traceback|FORTUNE-AGENT|status=error|guardrail|narrative_complete" \
  | tee -a "$OUT") &
DOCKER_PID=$!

cleanup() { kill $DOCKER_PID 2>/dev/null || true; }
trap cleanup EXIT

# Periodic Supabase fortune_runs status check (assumes psql + DATABASE_URL).
# If you don't have psql locally, swap in a curl call to the Supabase REST API.
echo "==> 5-min polling Supabase fortune_runs..." | tee -a "$OUT"
while true; do
  TS="$(date -Iseconds)"
  if [ -n "${DATABASE_URL:-}" ] && command -v psql >/dev/null 2>&1; then
    Q="SELECT status, count(*) FROM fortune_runs WHERE created_at > now() - interval '15 min' GROUP BY status;"
    OUT_LINE=$(psql "$DATABASE_URL" -At -c "$Q" 2>&1 | tr '\n' ' ')
    echo "[$TS] supabase: $OUT_LINE" | tee -a "$OUT"
  else
    echo "[$TS] (skip supabase poll — DATABASE_URL or psql not configured)" | tee -a "$OUT"
  fi

  # Also poll the local /health and a couple of metrics endpoints
  H=$(curl -fsS http://localhost:8100/health 2>/dev/null || echo "DOWN")
  echo "[$TS] backend health: $H" | tee -a "$OUT"

  sleep 300
done
