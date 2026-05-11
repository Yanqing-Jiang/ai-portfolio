#!/usr/bin/env python3
"""Post-PR5 SSE-route audit — exercises the *full* customer-facing path.

The pytest e2e harness (`test_agent_browser_e2e.py`) calls
``run_narrative`` directly and skips the FastAPI route, so it never
exercises the new pieces PR5 introduced:

* the ``narrative_complete`` gate event the frontend now consumes
* the 8 s synthetic heartbeat helper
* PR1's batched ``_alloc_seq`` against a real running backend
* the guardrail tail rendering as a banner update rather than blocking
  the reading

This script POSTs to ``/api/fortune/create`` for each of the four
customer-facing flows + an Ask follow-up, listens to
``/api/fortune/{id}/stream``, and emits a per-event timing log.

Run with the dev backend already up on :8000:

    python3 scripts/audit_sse_pr5.py

Outputs JSON-lines to ``~/homer/output/claude/audit_sse_pr5.jsonl`` so
the consolidator can stitch it into the post-refactor baseline doc.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")
OUT_PATH = Path.home() / "homer/output/claude/audit_sse_pr5.jsonl"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Flow payloads — match the pytest e2e harness exactly
# ---------------------------------------------------------------------------

BIRTH_A = "1990-06-15T08:30:00"
BIRTH_B = "1992-03-21T14:00:00"
TIMEZONE = "Asia/Shanghai"

FLOWS: dict[str, dict[str, Any]] = {
    "luck_cycle": {
        "birth_iso": BIRTH_A,
        "timezone": TIMEZONE,
        "focus": "luck_cycle:career:1y",
        "tone": "reflective",
        "gender": "male",
    },
    "wish": {
        "birth_iso": BIRTH_A,
        "timezone": TIMEZONE,
        "question": "Will my next career move pay off?",
        "tone": "reflective",
        "gender": "male",
    },
    "occasion": {
        "birth_iso": BIRTH_A,
        "timezone": TIMEZONE,
        "focus": "occasion:wedding:2026-06-08:2026-06-14",
        "tone": "reflective",
        "gender": "male",
    },
    "compatibility": {
        "birth_iso": BIRTH_A,
        "timezone": TIMEZONE,
        "focus": "compatibility:romance",
        "tone": "reflective",
        "gender": "male",
        "person_b": {
            "birth_iso": BIRTH_B,
            "timezone": TIMEZONE,
            "gender": "female",
        },
    },
}

# P50 targets from the plan TL;DR
TARGETS_S: dict[str, float] = {
    "luck_cycle": 30.0,
    "wish": 35.0,
    "occasion": 35.0,
    "compatibility": 50.0,
}


@dataclass
class EventStamp:
    name: str
    t_offset_s: float
    seq: int | None = None


@dataclass
class FlowResult:
    flow: str
    fortune_id: str
    create_ok: bool
    target_s: float
    events: list[EventStamp] = field(default_factory=list)
    narrative_complete_at: float | None = None
    guardrail_complete_at: float | None = None
    complete_at: float | None = None
    heartbeat_count: int = 0
    heartbeat_intervals: list[float] = field(default_factory=list)
    error: str | None = None
    verdict: str = "PENDING"

    def summarize(self) -> dict[str, Any]:
        narrative_s = self.narrative_complete_at
        guardrail_tail = (
            (self.guardrail_complete_at - self.narrative_complete_at)
            if self.guardrail_complete_at and self.narrative_complete_at
            else None
        )
        hit = (
            self.narrative_complete_at is not None
            and self.narrative_complete_at <= self.target_s
        )
        verdict = "HIT" if hit else "MISS"
        if self.error:
            verdict = "ERROR"
        if self.heartbeat_count == 0 and (narrative_s or 0) > 12:
            # narrative ran long enough that we should have seen ≥1 heartbeat
            verdict += "+NO_HEARTBEAT"
        self.verdict = verdict
        return {
            "flow": self.flow,
            "fortune_id": self.fortune_id,
            "narrative_complete_s": narrative_s,
            "guardrail_tail_s": guardrail_tail,
            "complete_s": self.complete_at,
            "target_s": self.target_s,
            "heartbeat_count": self.heartbeat_count,
            "heartbeat_intervals_s": self.heartbeat_intervals,
            "event_count": len(self.events),
            "first_event": self.events[0].name if self.events else None,
            "last_event": self.events[-1].name if self.events else None,
            "error": self.error,
            "verdict": verdict,
        }


async def _create_fortune(client: httpx.AsyncClient, payload: dict[str, Any]) -> str:
    r = await client.post(f"{BACKEND}/api/fortune/create", json=payload, timeout=30.0)
    r.raise_for_status()
    body = r.json()
    return body["fortune_id"]


async def _run_one(client: httpx.AsyncClient, flow: str) -> FlowResult:
    payload = FLOWS[flow]
    target = TARGETS_S[flow]
    print(f"[{flow}] POST /create...", file=sys.stderr)
    try:
        fortune_id = await _create_fortune(client, payload)
    except Exception as e:
        print(f"[{flow}] create FAILED: {e}", file=sys.stderr)
        return FlowResult(flow=flow, fortune_id="", create_ok=False, target_s=target,
                          error=f"create: {e}")

    res = FlowResult(flow=flow, fortune_id=fortune_id, create_ok=True, target_s=target)
    t0 = time.monotonic()
    last_progress_at: float | None = None

    print(f"[{flow}] streaming /stream fortune_id={fortune_id}...", file=sys.stderr)
    try:
        async with client.stream(
            "GET",
            f"{BACKEND}/api/fortune/{fortune_id}/stream",
            timeout=httpx.Timeout(connect=10.0, read=400.0, write=10.0, pool=10.0),
            headers={"Accept": "text/event-stream"},
        ) as resp:
            resp.raise_for_status()
            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    raw, buffer = buffer.split("\n\n", 1)
                    if not raw.strip() or raw.startswith(":"):
                        continue  # SSE comment / heartbeat at transport layer
                    payload_str = None
                    for line in raw.splitlines():
                        if line.startswith("data:"):
                            payload_str = line[5:].strip()
                            break
                    if not payload_str:
                        continue
                    try:
                        env = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue
                    body = env.get("payload") or env
                    seq = env.get("seq")
                    t = time.monotonic() - t0

                    # The fortune stream wraps a2ui ``dataModelUpdate`` shapes;
                    # there is no top-level ``event`` key on the wire. Classify
                    # by message kind + path.
                    kind = "unknown"
                    path = None
                    contents_kv: dict = {}
                    if isinstance(body, dict):
                        if "dataModelUpdate" in body:
                            kind = "dataModelUpdate"
                            dmu = body["dataModelUpdate"] or {}
                            path = dmu.get("path")
                            for c in dmu.get("contents", []) or []:
                                k = c.get("key")
                                if k is None:
                                    continue
                                # Flatten one level — sufficient for our gates.
                                if "valueBoolean" in c:
                                    contents_kv[k] = c["valueBoolean"]
                                elif "valueString" in c:
                                    contents_kv[k] = c["valueString"]
                                elif "valueNumber" in c:
                                    contents_kv[k] = c["valueNumber"]
                                elif "valueMap" in c:
                                    contents_kv[k] = "<map>"
                                elif "valueArray" in c:
                                    contents_kv[k] = "<array>"
                        elif "surfaceUpdate" in body:
                            kind = "surfaceUpdate"
                        elif "beginRendering" in body:
                            kind = "beginRendering"
                        elif "audit" in body:
                            kind = "audit"
                        elif body.get("done") is True:
                            kind = "done"

                    name = f"{kind}{':' + path if path else ''}"
                    res.events.append(
                        EventStamp(name=name, t_offset_s=round(t, 3), seq=seq)
                    )

                    # Heartbeat: emit_progress on /data/meta/progress with
                    # message "Still reasoning…".
                    if path == "/data/meta/progress":
                        msg = str(contents_kv.get("message", ""))
                        if "Still reasoning" in msg or "still reasoning" in msg.lower():
                            res.heartbeat_count += 1
                            if last_progress_at is not None:
                                res.heartbeat_intervals.append(round(t - last_progress_at, 2))
                            last_progress_at = t

                    # narrative_complete: dataModelUpdate at /data/narrative
                    # with isComplete=True (set in emit_narrative_complete).
                    if (
                        path == "/data/narrative"
                        and contents_kv.get("isComplete") is True
                        and res.narrative_complete_at is None
                    ):
                        res.narrative_complete_at = round(t, 3)
                        print(
                            f"[{flow}] narrative_complete @ {t:.2f}s",
                            file=sys.stderr,
                        )

                    # guardrail_complete: any dataModelUpdate at /data/guardrail
                    # carrying a level/message (emit_guardrail).
                    if path == "/data/guardrail" and res.guardrail_complete_at is None:
                        res.guardrail_complete_at = round(t, 3)

                    # Terminal complete: /data/meta with status=complete.
                    if (
                        path == "/data/meta"
                        and contents_kv.get("status") == "complete"
                    ):
                        res.complete_at = round(t, 3)
                        print(f"[{flow}] complete @ {t:.2f}s", file=sys.stderr)
                        return res
                    if kind == "done":
                        # Backstop: SSE hard-close. If we somehow missed the
                        # /data/meta status=complete event, the {"done": true}
                        # terminator marks end-of-stream.
                        if res.complete_at is None:
                            res.complete_at = round(t, 3)
                        return res
            # stream ended without explicit complete — treat as done
            return res
    except Exception as e:
        res.error = f"stream: {e}"
        return res


async def _run_ask(client: httpx.AsyncClient, fortune_id: str) -> dict[str, Any]:
    """PR4: Ask follow-up miss-path should default to expand_classics directly."""
    print(f"[ask] POST /action fortune_id={fortune_id}...", file=sys.stderr)
    t0 = time.monotonic()
    try:
        r = await client.post(
            f"{BACKEND}/api/fortune/{fortune_id}/action",
            json={"action_id": "ask", "payload": {"question": "explain the day-master interplay"}},
            timeout=120.0,
        )
        r.raise_for_status()
        elapsed = time.monotonic() - t0
        return {"flow": "ask_followup", "elapsed_s": round(elapsed, 2),
                "status": r.status_code, "verdict": "HIT" if elapsed <= 25 else "MISS"}
    except Exception as e:
        return {"flow": "ask_followup", "error": str(e), "verdict": "ERROR"}


async def main():
    timeout = httpx.Timeout(connect=10.0, read=400.0, write=30.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Run flows sequentially — parallel would hit OpenAI rate caps and
        # confound timing. Each is independent.
        results: list[FlowResult] = []
        for flow in ["luck_cycle", "wish", "occasion", "compatibility"]:
            res = await _run_one(client, flow)
            print(json.dumps(res.summarize(), indent=2))
            results.append(res)

        ask = None
        if results and results[-1].fortune_id:
            ask = await _run_ask(client, results[-1].fortune_id)
            print(json.dumps(ask, indent=2))

        # Persist machine-readable record
        with OUT_PATH.open("w") as fh:
            for r in results:
                fh.write(json.dumps({"summary": r.summarize(),
                                     "events": [asdict(e) for e in r.events]}) + "\n")
            if ask:
                fh.write(json.dumps({"summary": ask, "events": []}) + "\n")
        print(f"\nWrote {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
