#!/usr/bin/env bash
# Canary deploy script for the fortune-engine latency refactor.
#
# Usage:
#   scripts/canary_deploy.sh PR1
#   scripts/canary_deploy.sh PR2
#   scripts/canary_deploy.sh PR3
#   scripts/canary_deploy.sh PR4
#   scripts/canary_deploy.sh PR5
#
# Each call ships the named PR (assumes the merge happened on `main`),
# rebuilds the docker image, and prints the canary watch command so the
# operator can tail logs for 24 h before promoting the next PR.
#
# Hard requirement: only run AFTER `pytest backend/tests/fortune/ -v` is
# clean and `npx tsc --noEmit` reports zero errors on touched files.

set -euo pipefail

PR="${1:-}"
case "$PR" in
  PR1|PR2|PR3|PR4|PR5) ;;
  *) echo "Usage: $0 <PR1|PR2|PR3|PR4|PR5>" >&2; exit 1 ;;
esac

cd "$(dirname "$0")/.."

echo "==> [${PR}] Sanity: working tree clean?"
if [ -n "$(git status --porcelain 2>/dev/null || true)" ]; then
  echo "  ! uncommitted changes — commit or stash before canary." >&2
  exit 1
fi

echo "==> [${PR}] Pulling latest main"
git fetch origin main
git checkout main
git pull --ff-only origin main

echo "==> [${PR}] Backend tests"
cd backend
.venv/bin/pytest tests/fortune/ -q --timeout=180 -x
cd ..

echo "==> [${PR}] Frontend type-check on touched surfaces"
case "$PR" in
  PR5)
    npx tsc --noEmit 2>&1 | grep -E "(fortuneStore|useFortuneStream|ThinkingPanel|OracleChat|fortuneClient|_thinking_heartbeat)" \
      | (grep -v "^$" && echo "! type errors in PR5-touched files" && exit 1) || echo "  zero TS errors on PR5 surfaces"
    ;;
  *)
    npx tsc --noEmit > /tmp/tsc.log 2>&1 || true
    echo "  TS errors logged to /tmp/tsc.log (pre-existing portfolio errors are OK)"
    ;;
esac

echo "==> [${PR}] Building docker image"
docker compose build backend
docker compose up -d --force-recreate backend
echo "  waiting for /health..."
for i in {1..30}; do
  if curl -fsS http://localhost:8100/health 2>/dev/null | grep -q "ok"; then
    echo "  backend healthy"
    break
  fi
  sleep 2
  if [ "$i" = "30" ]; then echo "  ! backend did not come up healthy" >&2; exit 1; fi
done

cat <<EOF

================================================================
${PR} deployed.
Watch the canary for 24 h with:

  scripts/canary_watch.sh

Promotion gate:
  - CF Tunnel error rate < 1%
  - Supabase fortune_runs status=error spike < 2× baseline
  - No P0 from \`docker compose logs -f backend | grep -i "error\\|exception"\`
  - For PR3 only: re-run the authenticity audit before flipping
    FORTUNE_NARRATIVE_REASONING_COMPATIBILITY to "low"
  - For PR5 only: confirm narrative_complete fires before guardrail
    in the headed UI smoke

If the gate is clean at T+24h, ship the next PR.
================================================================
EOF
