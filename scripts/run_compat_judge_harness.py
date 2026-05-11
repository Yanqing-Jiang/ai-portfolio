#!/usr/bin/env python3
"""PR-1B judge harness — compat-mode reasoning-floor sweep.

Runs every compat fixture × every effort tier (none/low/medium by default)
through the live compatibility narrative agent, then scores each output via
N judge runs against gemini-3-pro-preview. Aggregates median + p25 per cell.

The result table tells us whether to ship ``low`` or ``none`` in PR-3:
    median ≥ 6.5 AND p25 ≥ 6.3 across 12/12 fixtures → ship that effort.
    Prefer ``low`` over ``none`` when both pass (richer reasoning-tokens
    signal for the thinking panel).

Concurrency: ``asyncio.Semaphore(8)`` bounds parallel LLM calls (both
narrative and judge). Walls 12×3 narrative + 12×3×5 judge calls down
from ~30 min sequential to ~3-5 min.

Cost ballpark at defaults (12 fixtures × 3 efforts × 5 judge runs):
    Narrative: 36 calls × ~$0.03  ≈ $1
    Judge:     180 calls × ~$0.10 ≈ $18
    Total:     ~$20 per full sweep

Usage::

    cd ~/ai-portfolio/backend
    OPENAI_API_KEY=$OPENAI_API_KEY \\
    GEMINI_API_KEY=$GEMINI_API_KEY \\
        ../.venv/bin/python ../scripts/run_compat_judge_harness.py \\
            --efforts none,low,medium --judge-runs 5

    # Cheap smoke (3 fixtures × 3 efforts × 1 judge, ~$2):
    OPENAI_API_KEY=$OPENAI_API_KEY \\
    GEMINI_API_KEY=$GEMINI_API_KEY \\
        ../.venv/bin/python ../scripts/run_compat_judge_harness.py --smoke

Output:
    ~/homer/output/claude/compat-harness-<ts>.json    (full result rows)
    Stdout: human-readable summary table + promotion verdict.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# --- repo path wiring (script runs from anywhere) -------------------------
_THIS = Path(__file__).resolve()
_REPO = _THIS.parent.parent
_BACKEND = _REPO / "backend"
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_REPO))

# Self-load .env.production so users don't have to source it manually.
# We deliberately use python-dotenv (which strips trailing CR/whitespace
# from values) instead of shell ``set -a && . backend/.env.production``,
# which leaves a literal ``\r`` on every value and breaks the OpenAI
# ``Bearer`` header.
try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore
    _PROD_ENV = _BACKEND / ".env.production"
    if _PROD_ENV.exists():
        _load_dotenv(_PROD_ENV, override=False)
except Exception:
    pass

# Heavy imports are deferred into ``main()`` so ``--help`` is fast and
# doesn't require the venv to load openai/agents/genai unnecessarily.


FIXTURES_DIR = _BACKEND / "tests" / "fortune" / "fixtures" / "compat"
OUTPUT_DIR = Path.home() / "homer" / "output" / "claude"
DEFAULT_EFFORTS = ("none", "low", "medium")
DEFAULT_JUDGE_RUNS = 5
DEFAULT_CONCURRENCY = 8
JUDGE_MODEL = "gemini-3-pro-preview"


# --------------------------------------------------------------------------
# Result dataclasses
# --------------------------------------------------------------------------


@dataclass
class CellResult:
    fixture_id: str
    effort: str
    latency_s: float
    pair_int_count: int
    mech_count: int
    reasoning_tokens: int | None
    output_tokens: int | None
    judge_scores: list[float] = field(default_factory=list)
    judge_median: float | None = None
    judge_p25: float | None = None
    error: str | None = None
    # PR-1B hardening: first judge exception text (debug only, not export-stable).
    judge_error: str | None = None

    def passes_promotion(self, *, latency_budget_s: float = 30.0) -> bool:
        if self.error or self.judge_median is None or self.judge_p25 is None:
            return False
        return (
            self.latency_s <= latency_budget_s
            and self.pair_int_count >= 3
            and self.mech_count >= 4
            and self.judge_median >= 6.5
            and self.judge_p25 >= 6.3
        )


# --------------------------------------------------------------------------
# Fixture loading
# --------------------------------------------------------------------------


def load_fixtures(limit: int | None = None) -> list[dict[str, Any]]:
    paths = sorted(FIXTURES_DIR.glob("compat_*.json"))
    if limit is not None:
        paths = paths[:limit]
    out: list[dict[str, Any]] = []
    for p in paths:
        with p.open() as fh:
            out.append(json.load(fh))
    if not out:
        raise SystemExit(
            f"No fixtures found under {FIXTURES_DIR}. Run from repo root after PR-1B fixtures land."
        )
    return out


# --------------------------------------------------------------------------
# Compat narrative call (live OpenAI)
# --------------------------------------------------------------------------


async def _run_compat_narrative(
    fixture: dict[str, Any],
    effort: str,
    sem: asyncio.Semaphore,
) -> CellResult:
    """Build a one-off compat narrative agent at the given effort and run.

    Bypasses NARRATIVE_AGENTS so we don't have to mutate FortuneSettings or
    reload modules across cells.
    """
    from agents import Agent, Runner
    from openai.types.shared.reasoning import Reasoning
    from agents.model_settings import ModelSettings

    from fortune.agents import (
        CompatibilityNarrativeOutput,
        FortuneRunContext,
        NARRATIVE_INSTRUCTIONS,
        _build_narrative_prompt,
        _run_config,
        run_foundation,
    )
    from fortune.config import DEFAULT_OPENAI_MODEL

    fixture_id = fixture["fixture_id"]
    pa = fixture["person_a"]
    pb = fixture["person_b"]
    focus = fixture["focus"]

    ctx = FortuneRunContext(
        fortune_id=f"harness-{fixture_id}",
        surface_id="fortune_main",
        run_id=f"harness-run-{fixture_id}-{effort}",
        focus=focus,
        tone="reflective",
        birth_iso=pa["birth_iso"],
        timezone=pa["timezone"],
        birth_time_unknown=False,
        gender=pa["gender"],
    )

    cell = CellResult(
        fixture_id=fixture_id, effort=effort,
        latency_s=0.0, pair_int_count=0, mech_count=0,
        reasoning_tokens=None, output_tokens=None,
    )

    try:
        async with sem:
            foundation = await run_foundation(ctx)
            ctx_b = FortuneRunContext(
                fortune_id=ctx.fortune_id,
                surface_id=ctx.surface_id,
                run_id=ctx.run_id,
                focus=ctx.focus,
                birth_iso=pb["birth_iso"],
                timezone=pb["timezone"],
                gender=pb["gender"],
            )
            foundation["person_b"] = await run_foundation(ctx_b)

            prompt = _build_narrative_prompt(ctx, foundation)
            agent = Agent(
                name=f"harness_compat_{effort}",
                model=DEFAULT_OPENAI_MODEL,
                model_settings=ModelSettings(
                    reasoning=Reasoning(effort=effort, summary=None),
                    verbosity="low",
                ),
                instructions=NARRATIVE_INSTRUCTIONS,
                output_type=CompatibilityNarrativeOutput,
            )

            t0 = time.monotonic()
            result = await Runner.run(
                agent, input=prompt, context=ctx, run_config=_run_config(ctx),
            )
            cell.latency_s = time.monotonic() - t0

        output = result.final_output  # CompatibilityNarrativeOutput
        compat = output.compatibility
        cell.pair_int_count = len(compat.pair_interactions) if compat else 0
        cell.mech_count = len(compat.mechanisms) if compat else 0
        usage = getattr(result, "raw_responses", None)
        if usage:
            # Sum tokens across raw_responses for the run.
            try:
                cell.output_tokens = sum(
                    (r.usage.output_tokens or 0) for r in usage if getattr(r, "usage", None)
                )
                cell.reasoning_tokens = sum(
                    (getattr(r.usage, "reasoning_tokens", 0) or 0)
                    for r in usage if getattr(r, "usage", None)
                )
            except Exception:
                pass

        # Stash the JSON-dumped output on the cell for the judge stage.
        cell._payload_json = output.model_dump_json()  # type: ignore[attr-defined]

    except Exception as e:
        cell.error = f"{type(e).__name__}: {e}"

    return cell


# --------------------------------------------------------------------------
# Judge (live Gemini)
# --------------------------------------------------------------------------


_JUDGE_PROMPT = """\
You are an expert evaluator of Chinese BaZi (八字) compatibility readings.

Score the following compatibility narrative on a 0-10 scale where:
  10 = master-level classical accuracy, specific to the chart pair, no
       generic fortune-cookie language
  8  = solid classical grounding with one or two minor specificity gaps
  6  = acceptable but generic in places (this is the AGENTS.md floor)
  4  = noticeably generic or shallow
  0  = no real BaZi reasoning, pure fortune-cookie advice

Evaluation criteria, in order of weight:
1. Classical grounding: does it reference real BaZi mechanisms (combinations,
   clashes, harms, 10-gods, element flow, day-master interactions) accurately?
2. Specificity: does each insight cite a specific chart signal (day master,
   pillar, element) rather than generic relationship advice?
3. Mechanism rigor: are pair_interactions tied to real stem/branch pairs?
   Are mechanism titles in plain English (not pinyin like "Ji卯" or "Bing-Ren")?
4. Coherence: do strengths and frictions tell a consistent story without
   internal contradiction?

Return ONLY a numeric score in the format ``SCORE: X.Y`` where X.Y is one
decimal place between 0.0 and 10.0. No explanation, no preamble.

------- NARRATIVE OUTPUT -------
{payload}
-------------------------------
"""


async def _judge_once(
    payload_json: str,
    client: Any,
    sem: asyncio.Semaphore,
) -> tuple[float | None, str | None]:
    """One judge call. Returns ``(score, error_text)``.

    Retries up to 3 times with exponential backoff on transient gemini
    failures (429/503/504). The first sweep silently lost 31/36 cells to
    these — the harness now captures the exception text so we can see
    what's happening when scores are missing.
    """
    prompt = _JUDGE_PROMPT.format(payload=payload_json)
    last_err: str | None = None
    for attempt in range(3):
        try:
            async with sem:
                # Wall-clock budget: gemini-3-pro-preview at our prompt
                # size returns in ~3-6s healthy; 45s is a generous cap
                # that still bounds the worst case so a hung TCP socket
                # can't permanently consume a concurrency slot (the bug
                # that hung sweep v2). ``asyncio.wait_for`` cancels the
                # underlying thread future on timeout.
                resp = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.models.generate_content,
                        model=JUDGE_MODEL,
                        contents=prompt,
                    ),
                    timeout=45.0,
                )
            text = (resp.text or "").strip()
            # Tolerate ``SCORE: 7.2`` or just ``7.2``
            for tok in text.replace(":", " ").split():
                try:
                    v = float(tok)
                    if 0 <= v <= 10:
                        return v, None
                except ValueError:
                    continue
            last_err = f"parse_fail: {text[:80]!r}"
            return None, last_err  # parse failure isn't retryable
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:160]}"
            transient = any(
                code in last_err
                for code in ("429", "503", "504", "RESOURCE_EXHAUSTED",
                             "DEADLINE_EXCEEDED", "UNAVAILABLE",
                             "TimeoutError")
            )
            if not transient or attempt == 2:
                return None, last_err
            await asyncio.sleep(2 ** attempt + (attempt * 0.5))  # 1s, 2.5s
    return None, last_err


async def _score_cell(
    cell: CellResult,
    judge_runs: int,
    client: Any,
    sem: asyncio.Semaphore,
) -> None:
    payload = getattr(cell, "_payload_json", None)
    if cell.error or not payload:
        return
    results = await asyncio.gather(
        *(_judge_once(payload, client, sem) for _ in range(judge_runs))
    )
    cell.judge_scores = [s for s, _ in results if s is not None]
    # Record the first error so missing-scores cells aren't silent any more.
    for _, err in results:
        if err:
            cell.judge_error = err
            break
    if cell.judge_scores:
        sorted_s = sorted(cell.judge_scores)
        cell.judge_median = float(statistics.median(sorted_s))
        # p25 via floor-index quantile to avoid scipy dep
        idx = max(0, int(0.25 * (len(sorted_s) - 1)))
        cell.judge_p25 = float(sorted_s[idx])


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


async def run_sweep(
    fixtures: list[dict[str, Any]],
    efforts: tuple[str, ...],
    judge_runs: int,
    concurrency: int,
) -> list[CellResult]:
    """Run every (fixture, effort) cell in parallel under a global semaphore."""
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) is not set; judge needs it."
        )
    client = genai.Client(api_key=api_key)

    sem = asyncio.Semaphore(concurrency)

    # Stage 1: narrative calls in parallel.
    print(f"Running {len(fixtures)} × {len(efforts)} = "
          f"{len(fixtures) * len(efforts)} narrative calls "
          f"at concurrency={concurrency}...")
    narrative_tasks = [
        _run_compat_narrative(fx, eff, sem)
        for fx in fixtures
        for eff in efforts
    ]
    cells = await asyncio.gather(*narrative_tasks)

    # Stage 2: judge each successful narrative N times.
    print(f"Judging {len([c for c in cells if not c.error])} successful cells "
          f"× {judge_runs} runs each...")
    judge_tasks = [_score_cell(c, judge_runs, client, sem) for c in cells]
    await asyncio.gather(*judge_tasks)

    return cells


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def _verdict_for_effort(cells: list[CellResult], effort: str) -> tuple[bool, dict[str, Any]]:
    cells_e = [c for c in cells if c.effort == effort]
    passing = [c for c in cells_e if c.passes_promotion()]
    return (
        len(passing) == len(cells_e) and len(cells_e) > 0,
        {
            "effort": effort,
            "total_cells": len(cells_e),
            "passing_cells": len(passing),
            "median_judge_median": (
                statistics.median([c.judge_median for c in cells_e if c.judge_median is not None])
                if any(c.judge_median is not None for c in cells_e)
                else None
            ),
            "median_latency_s": (
                statistics.median([c.latency_s for c in cells_e if not c.error])
                if any(not c.error for c in cells_e)
                else None
            ),
        },
    )


def _print_summary(cells: list[CellResult], efforts: tuple[str, ...]) -> None:
    print()
    print("=" * 88)
    print(f"{'fixture':14s} {'effort':8s} {'latency':>9s} {'pair':>4s} {'mech':>4s} "
          f"{'rt_tok':>7s} {'judge_med':>10s} {'judge_p25':>10s} {'PASS?':>6s}")
    print("-" * 88)
    for c in sorted(cells, key=lambda c: (c.fixture_id, c.effort)):
        if c.error:
            print(f"{c.fixture_id:14s} {c.effort:8s}  ERROR: {c.error[:60]}")
            continue
        passes = "YES" if c.passes_promotion() else "no"
        rt = "-" if c.reasoning_tokens is None else f"{c.reasoning_tokens:>7d}"
        jm = "-" if c.judge_median is None else f"{c.judge_median:>10.2f}"
        jp = "-" if c.judge_p25 is None else f"{c.judge_p25:>10.2f}"
        print(
            f"{c.fixture_id:14s} {c.effort:8s} {c.latency_s:>8.1f}s "
            f"{c.pair_int_count:>4d} {c.mech_count:>4d} {rt:>7s} "
            f"{jm:>10s} {jp:>10s} {passes:>6s}"
        )
    print("=" * 88)
    # PR-1B hardening: surface judge errors so silent quota failures stop hiding.
    judge_failures = [
        (c.fixture_id, c.effort, c.judge_error)
        for c in cells
        if not c.error and not c.judge_scores and c.judge_error
    ]
    if judge_failures:
        print()
        print(f"⚠️  {len(judge_failures)} cells had judge errors:")
        err_counts: dict[str, int] = {}
        for _, _, err in judge_failures:
            key = (err or "")[:60]
            err_counts[key] = err_counts.get(key, 0) + 1
        for err, cnt in sorted(err_counts.items(), key=lambda kv: -kv[1]):
            print(f"  ({cnt}x) {err}")
    print()
    print("Promotion verdict (median ≥ 6.5 AND p25 ≥ 6.3 across all cells):")
    chosen: str | None = None
    # Prefer ``low`` over ``none`` when both pass — richer panel audit surface.
    preference_order = ["low", "none", "medium"]
    for eff in preference_order:
        if eff not in efforts:
            continue
        passes, stats = _verdict_for_effort(cells, eff)
        marker = "✅ SHIP" if passes else "❌ HOLD"
        print(
            f"  {marker} effort={eff}  "
            f"{stats['passing_cells']}/{stats['total_cells']} cells pass  "
            f"median_judge={stats['median_judge_median']}  "
            f"median_latency={stats['median_latency_s']}"
        )
        if passes and chosen is None and eff != "medium":
            chosen = eff
    print()
    if chosen:
        print(f"==> Recommend shipping PR-3 with FORTUNE_NARRATIVE_REASONING_COMPATIBILITY={chosen}")
    else:
        print("==> NO promotion: PR-3 blocked. Investigate PR-5 two-stage path.")
    print()


def _save_results(cells: list[CellResult], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for c in cells:
        d = asdict(c)
        # Strip the heavy payload before serializing.
        d.pop("_payload_json", None)
        rows.append(d)
    with out_path.open("w") as fh:
        json.dump(
            {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "rows": rows,
            },
            fh,
            indent=2,
        )
    print(f"Wrote {len(rows)} rows → {out_path}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--fixtures", type=int, default=None,
        help="Limit to first N fixtures (default: all 12)",
    )
    ap.add_argument(
        "--efforts", type=str, default=",".join(DEFAULT_EFFORTS),
        help="Comma-separated reasoning efforts (default: none,low,medium)",
    )
    ap.add_argument(
        "--judge-runs", type=int, default=DEFAULT_JUDGE_RUNS,
        help=f"Judge runs per cell (default: {DEFAULT_JUDGE_RUNS})",
    )
    ap.add_argument(
        "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
        help=f"Max concurrent LLM calls (default: {DEFAULT_CONCURRENCY})",
    )
    ap.add_argument(
        "--smoke", action="store_true",
        help="Cheap sanity run: 3 fixtures × 3 efforts × 1 judge (~$2)",
    )
    ap.add_argument(
        "--output", type=Path, default=None,
        help=f"Output JSON path (default: {OUTPUT_DIR}/compat-harness-<ts>.json)",
    )
    args = ap.parse_args(argv)

    if args.smoke:
        args.fixtures = 3
        args.judge_runs = 1

    efforts = tuple(e.strip() for e in args.efforts.split(",") if e.strip())
    fixtures = load_fixtures(limit=args.fixtures)
    out_path = args.output or (
        OUTPUT_DIR / f"compat-harness-{time.strftime('%Y-%m-%d-%H%M')}.json"
    )

    # Lift the OpenAI client timeout the same way the live e2e suite does.
    try:
        from openai import AsyncOpenAI
        from agents import set_default_openai_client
        key = os.getenv("OPENAI_API_KEY") or os.getenv("FORTUNE_OPENAI_API_KEY")
        if key:
            set_default_openai_client(
                AsyncOpenAI(api_key=key, timeout=1200.0),
                use_for_tracing=True,
            )
    except Exception as e:
        print(f"WARNING: could not pin OpenAI client timeout: {e}")

    t0 = time.monotonic()
    cells = asyncio.run(
        run_sweep(fixtures, efforts, args.judge_runs, args.concurrency)
    )
    wall = time.monotonic() - t0

    _print_summary(cells, efforts)
    _save_results(cells, out_path)
    print(f"Total wall time: {wall:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
