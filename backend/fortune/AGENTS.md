# Ming Engine — Agent Browser & Test Guide

## Stack

| Layer        | Pin                              |
| ------------ | -------------------------------- |
| OpenAI SDK   | `openai>=1.107.3`                |
| Agents SDK   | `openai-agents==0.15.1`          |
| Bazi engine  | `cnlunar>=0.2.4` (deterministic) |
| Default model| `gpt-5-mini-2025-08-07`          |
| Reasoning    | `medium` (intake, chart, classics, narrative); `low` (guardrail) |
| Verbosity    | `low`                            |
| Max tokens   | 6000 (covers reasoning + JSON)   |

The reasoning + model wiring lives in `backend/fortune/config.py` and is read
by `_model_settings()` in `backend/fortune/agents.py`. Override per-stage via
`FORTUNE_NARRATIVE_REASONING=high` etc. in `.env`.

## The 4 customer-facing functions

Each maps to a different combination of `focus` + `question` on
`POST /api/fortune/create`:

| Function       | `focus` shape                                        | `question` |
| -------------- | ---------------------------------------------------- | ---------- |
| compatibility  | `compatibility:<relationship>` (+ `person_b` body)   | optional   |
| occasion       | `occasion:<type>:<startISO>:<endISO>`                | optional   |
| luck_cycle     | `luck_cycle:<focus>:<horizon>`                       | optional   |
| wish           | (anything else, must include `question`)             | required   |

`general` is a 5th catch-all — no `focus` and no `question`.

The narrative agent emits exactly ONE specialized block per
`EnrichedNarrativeOutput` matching the active mode (`compatibility`,
`occasion`, `luck_cycle`, or `wish`). The route handler then "fans out"
that block to per-path A2UI emitters in `stream_bridge.py` so the React
widgets see the right `/data/...` paths.

## How to test

### Unit tests (no network, fast)

```bash
cd ~/ai-portfolio/backend
.venv/bin/pytest tests/fortune/test_four_functions.py -v
```

These check stream-bridge payload shapes and that `DEFAULT_OPENAI_MODEL ==
"gpt-5-mini-2025-08-07"`.

### Live e2e — agent browser style (hits OpenAI)

```bash
cd ~/ai-portfolio/backend
set -a && source .env && set +a
.venv/bin/pytest tests/fortune/test_agent_browser_e2e.py -v -s \
    --log-cli-level=INFO 2>&1 | tee /tmp/fortune-e2e.out
```

The suite drives `run_foundation` + `run_narrative` + `run_guardrail`
directly (the same code path the SSE stream uses) for each of the 4
functions, and asserts:

* model = `gpt-5-mini-2025-08-07`, reasoning effort = `medium`
* the right specialized block populated (e.g. `out.compatibility` for
  compat focus, `out.occasion` for occasion focus)
* end-to-end latency under 90s per function (gpt-5-mini medium baseline)
* guardrail level ∈ {`info`, `warning`, `critical`}

Skips automatically if `OPENAI_API_KEY` is not set.

### Inspect structured logs

Every agent stage emits a single-line key=value record on
`fortune.agent` (`logger = logging.getLogger("fortune.agent")`):

```
[FORTUNE-AGENT] fn=<function> stage=<stage> model=<model>
    reasoning=<effort> latency_ms=<int>
    tokens_in=<int> tokens_out=<int> reasoning_tokens=<int>
    requests=<int> run_id=<uuid> fortune_id=<uuid>
    agent=<name> ok=<true|false> [extra=...]
```

* `fn` ∈ `compatibility | occasion | luck_cycle | wish | general`
* `stage` ∈ `foundation | narrative | narrative_streamed | triage | guardrail`
* per-stream banners use `event=stream_start` / `event=stream_end`

To find slow stages:

```bash
grep "[FORTUNE-AGENT]" backend.log \
    | awk -F'[= ]' '/stage=/ {for(i=1;i<=NF;i++) if($i=="stage") s=$(i+1); for(i=1;i<=NF;i++) if($i=="latency_ms") l=$(i+1); print s, l}' \
    | sort -k2 -n
```

## Where the work happens

```
fortune/
├── config.py            # FortuneSettings — models + reasoning effort
├── agent_logging.py     # classify_function() + structured stage() ctx mgr
├── agents.py            # 5 SDK Agents + run_foundation + run_narrative*
├── triage.py            # follow-up specialists + as_tool() routing
├── routes.py            # FastAPI /create /stream /action /ask /cancel
├── stream_bridge.py     # A2UI emitters for the SPA dashboard
├── bazi_engine.py       # cnlunar wrapper + 藏干/十神/冲合害刑破/旺相休囚死/大运/流年
├── calendar_tool.py     # base 4-pillar chart computation tool
├── classics.py          # hash-cosine retrieval over 滴天髓/子平真诠/三命通会 corpus
├── tracing.py           # GlassBoxTraceProcessor — durable spans → fortune_trace
└── trace_collector.py   # in-memory step trace for the SSE Glass Box
```

## Authenticity (Gemini Pro 3.1 audit, 2026-05-03)

Score: **7/10 — orthodox foundation, modernized shortcuts**. Top gaps:

1. **True solar time (真太阳时)** — IANA TZ only; longitude-based correction missing (P0).
2. **Yong Shen (用神)** — specialists guess favorable element; no central calculation (P0).
3. **Earth-month strength (辰未戌丑)** — uniform; ignores classical 18-day rule (P1).
4. **Luck-pillar precision** — rounds to 3 days = 1 year; misses 1 day = 4 mo, 1 hr = 5 d (P1).
5. **Wu-Wei combo (午未合)** — defaults to fire; should branch on chart heat (P2).
6. **Heuristic harmony score** — gamified; classical 合婚 uses Yong Shen mutuality (P2).

Full report: `~/homer/output/gemini/bazi-authenticity-2026-05-03-1530.md`.

## Cost / perf notes

`gpt-5-mini-2025-08-07` at medium reasoning is roughly:

* **2–3× the latency** of low for the narrative agent (most user-facing wait).
* **5–8× the reasoning tokens** vs low. Output token ceiling stays at 1800.
* Foundation + classics retrieval are deterministic — 0 model cost.
* Guardrail kept at `low` reasoning intentionally to bound stream tail.

If a customer ever needs sub-15s narratives, drop `FORTUNE_NARRATIVE_REASONING=low`
in `.env.production` and rebuild the container.
