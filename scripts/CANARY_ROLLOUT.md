# Fortune-Engine Latency Refactor — Canary Rollout Playbook

5-PR sequence with 24 h watch windows between each. Total wall time ≈
**5 days** (one canary per day). The plan is at
`/Users/yj/.claude/plans/purring-watching-raven.md`; this file is the
operator runbook.

## Pre-flight (once)

```bash
cd ~/ai-portfolio
chmod +x scripts/canary_deploy.sh scripts/canary_watch.sh
# Make sure ~/.env points DATABASE_URL at Supabase (canary_watch.sh reads it).
# psql is optional — without it the watcher just polls /health.
pip install pytest-timeout                 # silences the "missing plugin" warning
backend/.venv/bin/pytest backend/tests/fortune/ -q   # must be clean
```

> **Stale-backend trap:** if you have a dev uvicorn running, confirm its
> uptime is shorter than the most recent `backend/fortune/agents.py`
> mtime before any audit, otherwise you'll be measuring the OLD code
> path:
>
> ```bash
> ps -o pid,etime,command -p $(lsof -ti :8000) 2>/dev/null
> ls -la backend/fortune/agents.py
> ```
>
> Long-running uvicorn started without `--reload` does not pick up file
> changes. Restart with `--reload` if uptime is older than the agents.py
> mtime.

## Sequence

| Day | PR | Action | Watch | Promotion gate |
|---|---|---|---|---|
| D0 | PR1 | `scripts/canary_deploy.sh PR1` | 24 h | error rate < 1%, P50 latency on `/api/fortune/*` no worse than baseline |
| D1 | PR2 | `scripts/canary_deploy.sh PR2` | 24 h | narrative TTFB drops by 3–8 s; structured-output validation 100% |
| D2 | PR4 | `scripts/canary_deploy.sh PR4` | 24 h | Ask miss-path latency drops 30+ s; ≥ 90% direct-dispatch |
| D3 | PR3 | `scripts/canary_deploy.sh PR3` | 24 h | run authenticity audit (`AGENTS.md`-2026-05-03 harness); ≥ 6.5/10 |
| D4 | PR5 | `scripts/canary_deploy.sh PR5` | 24 h | headed UI smoke: narrative_complete gates render; banner + heartbeat visible |

> Note: PR4 ships **before** PR3 because the Ask path is independent of
> per-mode reasoning. This lets us prove Ask routing before we touch the
> compat/occasion reasoning floor.

## Watch (per PR)

In a separate terminal after `canary_deploy.sh`:

```bash
scripts/canary_watch.sh
# Logs to ~/homer/output/claude/canary-watch-<timestamp>.log
# Tail filtered to ERROR / Exception / Traceback / FORTUNE-AGENT lines.
# Polls Supabase fortune_runs every 5 min for status=error counts.
```

Leave running for the full 24 h. Promote only if the watch log is clean.

## Per-PR special steps

### PR1 — Hotfix micro-opts

No special action. After 24 h clean → ship PR2.

### PR2 — Schema split + drop `summary="auto"`

Manual smoke after deploy (before letting the canary breathe for 24 h):

```bash
cd ~/ai-portfolio/backend
.venv/bin/pytest tests/fortune/test_narrative_schemas.py -v
```

Expect compat ≤ 6000 chars, occasion ≤ 5000, luck ≤ 3500, wish ≤ 4500.
If any schema busts the ceiling, **revert** before PR3 lands.

### PR4 — Ask miss-path

Smoke 5 free-form Ask questions known to miss the heuristic:

```bash
.venv/bin/pytest tests/fortune/test_ask_routing.py -v
```

Expect ≥ 18 / 20 direct-dispatch.

### PR3 — Per-mode reasoning + occasion prefilter (compat fixture A/B)

After 24 h clean canary, **before** flipping compat to `low`:

```bash
.venv/bin/pytest tests/fortune/test_compat_reasoning_floor.py -v
```

If 12 / 12 pass at low → follow-up commit:

```python
# backend/fortune/config.py
narrative_reasoning_compatibility: str = "low"   # was "medium"
```

Re-deploy with the same `canary_deploy.sh PR3` flow + 24 h watch.

If any of the 12 fail → leave at medium and document the regressing
fixture(s) in `backend/fortune/AGENTS.md` (per the plan's escape hatch).

### PR5 — Frontend gate + synthetic heartbeat

Manual headed-Chromium smoke (5 min):

```bash
# Terminal 1
docker compose up -d --build
# Terminal 2
npm run dev    # frontend at :5173
# Terminal 3
backend/.venv/bin/python scripts/audit_sse_pr5.py
```

Confirm in the script's stdout:
- `narrative_complete @ <Ns>` appears for each flow
- `complete @ <Ms>` appears 3.5–4.5 s later (guardrail tail)
- `heartbeat_count` ≥ 2 on flows where narrative > 16 s
- `heartbeat_intervals_s` cluster around 8 s

Then in the browser at `http://localhost:5173/project/fortune-agent/explore`:

- Pick any flow → submit → watch the ThinkingPanel
  - "Still reasoning… (Ns)" updates ~every 8 s
  - Reading appears as soon as `narrative_complete` fires
  - Small "Verifying Safety" / pulsing Shield banner shows for ~3.5–4.5 s
  - Banner clears on `complete`

## Post-rollout (once all 5 are live)

Update `~/memory/work.md` "AI portfolio" section with:

```md
## 2026-05-XX — Fortune engine latency refactor (5 PRs)
- Baseline P50: compat 115s · occasion 110s · wish 84s · luck 54s · ask 60–110s
- Post-refactor P50: compat <FILL> · occasion <FILL> · wish <FILL> · luck <FILL> · ask <FILL>
- Authenticity score (gemini-3-pro audit): <FILL>/10 (target ≥ 6.5)
- compat reasoning tier: <medium | low — note fixture A/B outcome>
- Lessons: <…>
```

Then archive the plan:

```bash
mv /Users/yj/.claude/plans/purring-watching-raven.md \
   /Users/yj/.claude/plans/archive/2026-05-09-fortune-latency-refactor.md
```

## Rollback (any PR)

```bash
git checkout main
git revert <PR-merge-sha>
git push origin main
docker compose up -d --build backend
# Watch /health and the canary_watch.sh log for 30 min before walking away.
```

If the rollback target is PR3 with the compat=low flip already shipped,
revert the flip alone first (smaller blast radius) before reverting the
full PR3.
