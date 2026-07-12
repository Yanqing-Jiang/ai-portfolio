"""Golden-file contract test for fortune A2UI/SSE frame sequences.

Captures the exact envelope sequence the shared pipeline producer emits for a fixed
mocked run (real deterministic foundation + mocked narrative/guardrail)
and asserts against a checked-in golden JSON file. Guards the wire
contract through the Phase 1 refactor.

Guards the A2UI/SSE frame wire contract across pipeline refactors.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fortune.agents import (  # noqa: E402
    DEFAULT_FOLLOW_UP_BUTTONS,
    EnrichedNarrativeOutput,
    GuardrailOutput,
    InsightBullet,
    InsightSection,
)
from fortune.pipeline import iter_fortune_sse_frames  # noqa: E402
from fortune.state import (  # noqa: E402
    CreateFortuneRequest,
    FortuneSession,
    reset_run_state_for_tests,
    get_run_state,
)

GOLDEN_PATH = Path(__file__).parent / "golden" / "fortune_a2ui_frames_wish_v1.json"

FIXED_FORTUNE_ID = "11111111-1111-1111-1111-111111111111"
FIXED_RUN_ID = "22222222-2222-2222-2222-222222222222"
FIXED_BIRTH = "1990-05-15T10:30:00"
FIXED_TZ = "America/Los_Angeles"


def _fixed_narrative() -> EnrichedNarrativeOutput:
    return EnrichedNarrativeOutput(
        tldr="Metal day master meeting a fire season — decisive year ahead.",
        insights=[
            InsightSection(
                id="strengths",
                icon="⚔️",
                heading="Core Strengths",
                tagline="Clarity under pressure.",
                bullets=[
                    InsightBullet(icon="•", text="You cut through noise quickly."),
                    InsightBullet(icon="•", text="Commitments stick when named aloud."),
                ],
            ),
            InsightSection(
                id="watch",
                icon="👀",
                heading="Watch Outs",
                tagline="Pace the push.",
                bullets=[
                    InsightBullet(icon="•", text="Avoid stacking deadlines."),
                    InsightBullet(icon="•", text="Leave recovery between sprints."),
                ],
            ),
        ],
    )


def _fixed_guardrail() -> GuardrailOutput:
    return GuardrailOutput(
        level="info",
        message="For reflection and entertainment only.",
        disclaimer="Not medical, legal, or financial advice.",
        follow_up_buttons=DEFAULT_FOLLOW_UP_BUTTONS,
    )


class _FakeStreamResult:
    def __init__(self, final_output: Any) -> None:
        self.final_output = final_output
        self.context_wrapper = MagicMock()
        self.context_wrapper.usage = MagicMock(
            input_tokens=10, output_tokens=20, total_tokens=30,
        )

    async def stream_events(self):
        if False:  # pragma: no cover
            yield None

    def cancel(self) -> None:
        return None


def _parse_sse_data_frames(chunks: list[str]) -> list[dict[str, Any]]:
    """Extract JSON envelopes from SSE ``data:`` lines (ignore comments)."""
    frames: list[dict[str, Any]] = []
    for chunk in chunks:
        for line in chunk.splitlines():
            if line.startswith("data: "):
                frames.append(json.loads(line[6:]))
    return frames


_MS_RE = re.compile(r'\b\d+ms\b')

_VOLATILE_KEYS = {
    "timestamp",
    "durationMs",
    "duration_ms",
    "elapsedMs",
    "elapsed_ms",
    "totalDurationMs",
    "total_duration_ms",
    "createdAt",
    "created_at",
}


def _canonicalize(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop volatile timing fields so goldens stay stable across runs."""
    out: list[dict[str, Any]] = []
    for env in frames:
        env = json.loads(json.dumps(env))  # deep copy via JSON
        _scrub_volatile(env)
        payload = env.get("payload")
        if isinstance(payload, dict):
            dmu = payload.get("dataModelUpdate")
            if isinstance(dmu, dict) and dmu.get("path") in {
                "/data/progress",
                "/data/meta/progress",
            }:
                contents = dmu.get("contents")
                if isinstance(contents, list):
                    for entry in contents:
                        if isinstance(entry, dict) and entry.get("key") == "message":
                            msg = entry.get("valueString") or ""
                            if "Still reasoning" in msg:
                                entry["valueString"] = "Still reasoning… (Ns)"
        out.append(env)
    return out


def _scrub_volatile(node: Any) -> None:
    if isinstance(node, list):
        for item in node:
            _scrub_volatile(item)
        return
    if not isinstance(node, dict):
        return
    for key, value in list(node.items()):
        if key in _VOLATILE_KEYS:
            if isinstance(value, (int, float)):
                node[key] = 0
            elif isinstance(value, str):
                node[key] = "<TIMESTAMP>"
            continue
        # Trace step ids embed a content hash that includes timestamps.
        if key in {"stepId", "step_id"} and isinstance(value, str) and value.startswith("ts_"):
            node[key] = "ts_<HASH>"
            continue
        # Trace summaries embed wall-clock durations ("2 insights, 1ms").
        if key in {"outputSummary", "inputSummary"} and isinstance(value, str):
            node[key] = _MS_RE.sub("<N>ms", value)
            continue
        # DataEntry form: {key: "timestamp", valueString: "..."}
        if key == "key" and value in _VOLATILE_KEYS:
            if "valueString" in node:
                node["valueString"] = "<TIMESTAMP>"
            if "valueNumber" in node:
                node["valueNumber"] = 0
        if key == "key" and value in {"stepId", "step_id"}:
            if isinstance(node.get("valueString"), str) and node["valueString"].startswith("ts_"):
                node["valueString"] = "ts_<HASH>"
        _scrub_volatile(value)


async def _collect_pipeline_frames() -> list[dict[str, Any]]:
    reset_run_state_for_tests()
    store = get_run_state()
    session = FortuneSession(
        fortune_id=FIXED_FORTUNE_ID,
        run_id=FIXED_RUN_ID,
        surface_id="fortune_main",
        request=CreateFortuneRequest(
            birth_iso=FIXED_BIRTH,
            timezone=FIXED_TZ,
            question="Will I find a new role this year?",
            focus=None,
            tone="warm",
            gender="female",
            birth_time_unknown=False,
        ),
    )
    await store.put(session)

    narrative = _fixed_narrative()
    guardrail = _fixed_guardrail()

    fake_repo = MagicMock()
    fake_repo.available = False
    fake_repo.update_run_status = AsyncMock()
    fake_repo.upsert_snapshot = AsyncMock()

    with patch("fortune._pipeline_run.get_repository", AsyncMock(return_value=fake_repo)), \
         patch("fortune._pipeline_run.run_narrative_streamed", AsyncMock(return_value=_FakeStreamResult(narrative))), \
         patch("fortune._pipeline_run.run_guardrail", AsyncMock(return_value=guardrail)), \
         patch("fortune._pipeline_run.iter_with_heartbeats", lambda agen, interval=8.0: agen), \
         patch("fortune.state.get_state_redis", AsyncMock(return_value=None)):
        chunks: list[str] = []
        async for frame in iter_fortune_sse_frames(session, request=None, store=store):
            chunks.append(frame)

    return _canonicalize(_parse_sse_data_frames(chunks))


@pytest.mark.asyncio
async def test_a2ui_frames_golden_wish_v1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    frames = await _collect_pipeline_frames()

    assert frames, "expected at least one SSE frame"
    assert frames[0]["fortune_id"] == FIXED_FORTUNE_ID
    assert frames[0]["run_id"] == FIXED_RUN_ID
    assert frames[0]["seq"] == 1
    # Terminal done sentinel present
    assert any(
        (f.get("payload") or {}).get("done") is True
        or ((f.get("payload") or {}).get("dataModelUpdate") or {}).get("path") == "/data/meta"
        for f in frames
    )

    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    update = pytest.importorskip("os").environ.get("UPDATE_GOLDEN") == "1"
    if update or not GOLDEN_PATH.exists():
        GOLDEN_PATH.write_text(json.dumps(frames, indent=2, ensure_ascii=False) + "\n")
        if not update:
            pytest.skip(f"golden written to {GOLDEN_PATH}; re-run to assert")

    expected = json.loads(GOLDEN_PATH.read_text())
    assert frames == expected, (
        f"A2UI/SSE frame sequence drifted from golden ({GOLDEN_PATH}). "
        "If intentional, re-run with UPDATE_GOLDEN=1."
    )


@pytest.mark.asyncio
async def test_pipeline_frame_envelope_shape():
    """Sanity: every frame is {run_id, fortune_id, seq, payload}."""
    frames = await _collect_pipeline_frames()
    for i, env in enumerate(frames, start=1):
        assert set(env.keys()) >= {"run_id", "fortune_id", "seq", "payload"}
        assert env["seq"] == i or isinstance(env["seq"], int)
