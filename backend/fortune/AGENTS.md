# Ming Engine — Agent Browser & Test Guide

## Stack

| Layer        | Pin                              |
| ------------ | -------------------------------- |
| OpenAI SDK   | `openai>=1.107.3`                |
| Agents SDK   | `openai-agents==0.15.1`          |
| Bazi engine  | `cnlunar>=0.2.4` (deterministic) |
| Default model| `gpt-5.4-mini`                   |
| Reasoning    | `medium` (compatibility); `low` (occasion, luck_cycle, wish, guardrail); foundation is deterministic. Legacy `narrative_reasoning` default remains `medium` for `general` fallback. |
| Verbosity    | `low`                            |
| Max tokens   | compat=10000, occasion=9000, wish=6000, luck_cycle=4500, guardrail=1200 |

The reasoning + model wiring lives in `backend/fortune/config.py` and is read
by `_model_settings()` in `backend/fortune/agents.py`. Override live LLM stages
via `FORTUNE_NARRATIVE_REASONING=high` etc. in `.env`.

**PR2 (latency refactor) note:** `_model_settings` now passes
`Reasoning(effort=…, summary=None)` — the reasoning summary stream was
adding 3-8 s of TTFB and 10-15 % of reasoning tokens with no model-quality
benefit. The ThinkingPanel UX role it served is replaced by the synthetic
heartbeat (`_thinking_heartbeat`) wired in PR5 plus the existing
`trace_collector` breadcrumbs. Do NOT re-introduce `summary="auto"`
without coordinating a frontend fallback.

## The 5 narrative agents (per-mode)

PR2 of the latency refactor split the single `NARRATIVE_AGENT` into a
keyed `NARRATIVE_AGENTS` dict so each mode binds a narrow `output_type`:

| Key            | Agent name                          | Output schema                  |
| -------------- | ----------------------------------- | ------------------------------ |
| compatibility  | `fortune_narrative_compatibility`   | `CompatibilityNarrativeOutput` |
| occasion       | `fortune_narrative_occasion`        | `OccasionNarrativeOutput`      |
| luck_cycle     | `fortune_narrative_luck_cycle`      | `LuckCycleNarrativeOutput`     |
| wish           | `fortune_narrative_wish`            | `WishNarrativeOutput`          |
| general        | `fortune_narrative` (legacy)        | `EnrichedNarrativeOutput`      |

The merged `EnrichedNarrativeOutput` is still the canonical type the route
handler / fan-out / snapshot pipeline reads. `_promote_narrative_to_enriched`
in `agents.py` converts each narrow output back into the merged shape
right after the SDK call returns, so downstream code sees one layout.

Mode is picked by `_narrative_mode(ctx)` from `ctx.focus` — same prefix
rules that drive the per-mode emit fan-out at `routes.py:1316-1411`.
**Do not regress the schema split.** Per-mode compact JSON schemas land
54-72 % smaller than the union (regression-tested by
`tests/fortune/test_narrative_schemas.py`).

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

## Prompt-cache prefix-ordering rule

`_build_narrative_prompt` orders dict keys **stable-first → volatile-last**
so OpenAI Responses API automatic prompt cache (≥1024-token prefix match)
fires on repeat queries by the same user. Order:

1. Schema / foundation version markers (global stable).
2. Person A chart data (stable per user).
3. Person B chart (when present, stable per pair).
4. `occasion_window`.
5. `current_year`.
6. `focus` / `tone` / `question` / `references` (volatile per call).

`tests/fortune/test_prompt_cache_prefix.py` enforces this. **Do not
insert a volatile field above a stable one** — the cache prefix breaks at
the first divergent byte and the win disappears.

## How to test

### Unit tests (no network, fast)

```bash
cd ~/ai-portfolio/backend
.venv/bin/pytest tests/fortune/test_four_functions.py -v
```

These check stream-bridge payload shapes and that `DEFAULT_OPENAI_MODEL ==
"gpt-5.4-mini"`.

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

* narrative model = `gpt-5.4-mini`, reasoning effort = `medium`
* the right specialized block populated (e.g. `out.compatibility` for
  compat focus, `out.occasion` for occasion focus)
* end-to-end latency under the per-function ceilings in the test file
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
* `stage` ∈ `foundation | narrative | narrative_streamed | direct_dispatch | triage | guardrail`
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
├── agents.py            # deterministic foundation + narrative/guardrail SDK agents
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

`gpt-5.4-mini` at medium reasoning is roughly:

* **2–3× the latency** of low for the narrative agent (most user-facing wait).
* **5–8× the reasoning tokens** vs low. Output token ceiling stays at 1800.
* Foundation + classics retrieval are deterministic — 0 model cost.
* Guardrail kept at `low` reasoning intentionally to bound stream tail.

If a customer ever needs sub-15s narratives, drop `FORTUNE_NARRATIVE_REASONING=low`
in `.env.production` and rebuild the container.
