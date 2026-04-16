#!/usr/bin/env bash
# Test Ming Engine under 4 scenarios (v2 — fixed curl handling).
# Requires: backend running on localhost:8000

BASE="http://localhost:8000"
PASS=0
FAIL=0
RESULTS=()

log() { printf "\n\033[1;36m── %s ──\033[0m\n" "$1"; }
ok()  { PASS=$((PASS+1)); RESULTS+=("✅ $1"); printf "\033[32m  ✅ %s\033[0m\n" "$1"; }
err() { FAIL=$((FAIL+1)); RESULTS+=("❌ $1"); printf "\033[31m  ❌ %s\033[0m\n" "$1"; }

create_fortune() {
  curl -s -X POST "$BASE/api/fortune/create" \
    -H "Content-Type: application/json" -d "$1" | \
    python3 -c "import sys,json; print(json.load(sys.stdin)['fortune_id'])" 2>/dev/null
}

stream_fortune() {
  local fid="$1" timeout="${2:-30}" out="/tmp/ming_test_$fid.txt"
  curl -s -N --max-time "$timeout" "$BASE/api/fortune/$fid/stream" > "$out" 2>/dev/null || true
  echo "$out"
}

check() {
  local label="$1" file="$2" pattern="$3"
  if grep -q "$pattern" "$file" 2>/dev/null; then ok "$label"; else err "$label"; fi
}

check_absent() {
  local label="$1" file="$2" pattern="$3"
  if grep -q "$pattern" "$file" 2>/dev/null; then err "$label"; else ok "$label"; fi
}

###########################################################
log "SCENARIO 1: Backend health check"
###########################################################
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health")
[ "$CODE" = "200" ] && ok "S1: /health returns 200" || err "S1: /health returned $CODE"

###########################################################
log "SCENARIO 2: General Reading (no focus) — clarification"
###########################################################
FID=$(create_fortune '{"birth_iso":"1990-06-15T09:00:00","timezone":"Asia/Shanghai"}')
if [ -z "$FID" ]; then err "S2: Failed to create session"; else
  ok "S2: Created fortune $FID"
  OUT=$(stream_fortune "$FID" 30)
  check   "S2: Pillars received"        "$OUT" "pillars"
  check   "S2: Elements received"       "$OUT" "elements"
  check   "S2: Clarification sent"      "$OUT" "clarification_request"
  check   "S2: Done signal sent"        "$OUT" '"done"'
fi

###########################################################
log "SCENARIO 3: Focused Reading (career) — full pipeline"
###########################################################
FID2=$(create_fortune '{"birth_iso":"1990-06-15T09:00:00","timezone":"Asia/Shanghai","focus":"career","question":"Should I change jobs?"}')
if [ -z "$FID2" ]; then err "S3: Failed to create session"; else
  ok "S3: Created fortune $FID2"
  OUT2=$(stream_fortune "$FID2" 120)
  check "S3: Pillars received"        "$OUT2" "pillars"
  check "S3: Narrative received"      "$OUT2" "narrative"
  check "S3: Guardrail received"      "$OUT2" "guardrail"
  check "S3: stream_complete audit"   "$OUT2" "stream_complete"
  check "S3: Done signal sent"        "$OUT2" '"done"'
fi

###########################################################
log "SCENARIO 4: Action after clarification → re-stream"
###########################################################
if [ -n "$FID" ]; then
  ACTION_CODE=$(curl -s -o /tmp/ming_action.json -w "%{http_code}" -X POST \
    "$BASE/api/fortune/$FID/action" \
    -H "Content-Type: application/json" -d '{"action_id":"career_focus","payload":{}}')
  [ "$ACTION_CODE" = "200" ] && ok "S4: Action accepted (200)" || err "S4: Action returned $ACTION_CODE"
  check "S4: Focus updated to career" "/tmp/ming_action.json" '"career"'

  OUT4=$(stream_fortune "$FID" 120)
  check "S4: Narrative on re-stream"  "$OUT4" "narrative"
  check "S4: Guardrail on re-stream"  "$OUT4" "guardrail"
  check "S4: Done signal on re-stream" "$OUT4" '"done"'
else
  err "S4: Skipped — no fortune_id from S2"
fi

###########################################################
log "SUMMARY"
###########################################################
echo ""
for r in "${RESULTS[@]}"; do echo "  $r"; done
echo ""
printf "  \033[1mTotal: %d passed, %d failed\033[0m\n\n" "$PASS" "$FAIL"
