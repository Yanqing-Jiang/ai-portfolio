from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fortune.agents import (  # noqa: E402
    EnrichedNarrativeOutput,
    FortuneRunContext,
    GuardrailOutput,
    InsightBullet,
    InsightSection,
    run_foundation,
)
from fortune.pipeline import iter_fortune_sse_frames  # noqa: E402
from fortune.state import (  # noqa: E402
    CreateFortuneRequest,
    FortuneSession,
    RuntimeStatus,
    get_run_state,
    reset_run_state_for_tests,
)
from fortune.tracing import GlassBoxTraceProcessor  # noqa: E402


BIRTH_CANARY = "1987-04-03T09:17:00"
QUESTION_CANARY = "CANARY_QUESTION_river-glass-917"
REJECTED_NARRATIVE = "REJECTED_NARRATIVE_never_publish_4f91"
FORTUNE_ID = "11111111-1111-1111-1111-111111111111"
RUN_ID = "22222222-2222-2222-2222-222222222222"


class _Pool:
    def __init__(self) -> None:
        self.rows: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, *args: object) -> str:
        self.rows.append((query, args))
        return "INSERT 0 1"


@pytest.mark.asyncio
async def test_trace_redaction_canaries_absent_from_live_and_db(monkeypatch):
    processor = GlassBoxTraceProcessor()
    pool = _Pool()
    repo = SimpleNamespace(available=True, pool=pool)
    published: list[dict] = []

    async def _publish(_run_id: str, envelope: dict, **_kwargs):
        published.append(envelope)
        return f"1000-{len(published)}"

    ctx = FortuneRunContext(
        fortune_id=FORTUNE_ID,
        run_id=RUN_ID,
        surface_id="fortune_main",
        birth_iso=BIRTH_CANARY,
        question=QUESTION_CANARY,
        focus="wish",
        timezone="America/Los_Angeles",
    )
    with patch("fortune.agents.get_trace_processor", return_value=processor), \
         patch("fortune.store.get_repository", AsyncMock(return_value=repo)), \
         patch("fortune.events.publish_envelope", _publish):
        foundation = await run_foundation(ctx)
        trace = foundation["trace"]
        with trace.step(
            "tool_call",
            "narrative",
            tool_name="retrieve_classics",
            input_summary=f"{BIRTH_CANARY} {QUESTION_CANARY}",
        ) as step:
            step.output_summary = f"result for {QUESTION_CANARY} born {BIRTH_CANARY}"
        await processor.aflush(run_id=RUN_ID)

    trace_frames = [p for p in published if p.get("payload", {}).get("kind") == "trace"]
    assert trace_frames
    assert pool.rows
    live_json = json.dumps(trace_frames, ensure_ascii=False, default=str)
    db_json = json.dumps(pool.rows, ensure_ascii=False, default=str)
    for canary in (BIRTH_CANARY, BIRTH_CANARY[:10], QUESTION_CANARY):
        assert canary not in live_json
        assert canary not in db_json
    projection = trace_frames[-1]["payload"]["trace"]
    assert projection["eventId"] == (
        f"{projection['runId']}:{projection['spanId']}:{projection['phase']}"
    )


class _FakeStreamResult:
    def __init__(self, final_output: EnrichedNarrativeOutput) -> None:
        self.final_output = final_output
        self.context_wrapper = MagicMock()
        self.context_wrapper.usage = MagicMock(
            input_tokens=1,
            output_tokens=1,
            total_tokens=2,
        )

    async def stream_events(self):
        if False:
            yield None

    def cancel(self) -> None:
        return None


def _rejected_output() -> EnrichedNarrativeOutput:
    return EnrichedNarrativeOutput(
        tldr=REJECTED_NARRATIVE,
        insights=[
            InsightSection(
                id="unsafe",
                icon="x",
                heading="Unsafe",
                tagline=REJECTED_NARRATIVE,
                bullets=[
                    InsightBullet(icon="x", text=REJECTED_NARRATIVE),
                    InsightBullet(icon="x", text="second rejected detail"),
                ],
            ),
            InsightSection(
                id="unsafe_two",
                icon="x",
                heading="Unsafe two",
                tagline="must stay buffered",
                bullets=[
                    InsightBullet(icon="x", text="third rejected detail"),
                    InsightBullet(icon="x", text="fourth rejected detail"),
                ],
            ),
        ],
    )


@pytest.mark.asyncio
async def test_guardrail_tripwire_never_publishes_or_snapshots_narrative(monkeypatch):
    reset_run_state_for_tests()
    store = get_run_state()
    session = FortuneSession(
        fortune_id=FORTUNE_ID,
        run_id=RUN_ID,
        surface_id="fortune_main",
        request=CreateFortuneRequest(
            birth_iso=BIRTH_CANARY,
            timezone="America/Los_Angeles",
            question=QUESTION_CANARY,
            focus="wish",
            gender="female",
        ),
    )
    await store.put(session)

    fake_repo = MagicMock()
    fake_repo.available = False
    fake_repo.update_run_status = AsyncMock()
    fake_repo.upsert_snapshot = AsyncMock()
    critical = GuardrailOutput(
        level="critical",
        message=f"unsafe quote: {REJECTED_NARRATIVE}",
        disclaimer=f"unsafe disclaimer: {REJECTED_NARRATIVE}",
        follow_up_buttons=[],
    )

    with patch("fortune._pipeline_run.get_repository", AsyncMock(return_value=fake_repo)), \
         patch(
             "fortune._pipeline_run.run_narrative_streamed",
             AsyncMock(return_value=_FakeStreamResult(_rejected_output())),
         ), \
         patch("fortune._pipeline_run.run_guardrail", AsyncMock(return_value=critical)), \
         patch("fortune._pipeline_run.get_ask_session", AsyncMock(return_value=None)), \
         patch("fortune.state.get_state_redis", AsyncMock(return_value=None)):
        chunks = [
            frame
            async for frame in iter_fortune_sse_frames(session, request=None, store=store)
        ]

    wire = "".join(chunks)
    assert REJECTED_NARRATIVE not in wire
    assert "safely present this reading" in wire
    assert "Reading withheld by safety check." in wire
    assert session.latest_narrative is None
    assert session.status is RuntimeStatus.failed_guardrail

    snapshot_json = json.dumps(
        [call.kwargs for call in fake_repo.upsert_snapshot.await_args_list],
        ensure_ascii=False,
        default=str,
    )
    assert REJECTED_NARRATIVE not in snapshot_json
    assert all(call.kwargs.get("narrative") is None for call in fake_repo.upsert_snapshot.await_args_list)
    fake_repo.update_run_status.assert_any_await(
        ANY,
        "failed_guardrail",
        error_message="output_guardrail_tripwire",
    )
