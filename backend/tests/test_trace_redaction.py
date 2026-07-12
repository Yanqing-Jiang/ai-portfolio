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


# ---------------------------------------------------------------------------
# Endpoint-level canaries (Phase 4 Glass Box / MemoryPanel)
# ---------------------------------------------------------------------------

from datetime import datetime, timezone  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _fortune_test_app():
    """Minimal app mounting fortune routes without the full main lifespan."""
    from fortune.routes import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_trace_endpoint_excludes_birth_and_question_canaries(monkeypatch):
    """GET /trace must serve only allowlisted redacted projections."""
    from fortune import routes as fortune_routes

    seeded_events = [
        {
            "eventId": f"{RUN_ID}:span-1:end",
            "runId": RUN_ID,
            "spanId": "span-1",
            "phase": "end",
            "parentSpanId": None,
            "spanType": "function",
            "agentName": "fortune_narrative_wish",
            "toolName": "retrieve_classics",
            "model": "gpt-5.6-luna",
            "durationMs": 12,
            "status": "success",
            # Intentionally include canaries in a field that should never be
            # returned from a correctly-redacted store projection. The route
            # must not invent birth/question content; we assert the response
            # JSON never contains them either way.
            "argSummary": "[redacted] classics lookup",
            "resultSummary": "5 references",
            "startedAt": "2026-07-12T00:00:00+00:00",
            "endedAt": "2026-07-12T00:00:01+00:00",
        }
    ]

    fake_repo = SimpleNamespace(
        available=True,
        get_fortune=AsyncMock(return_value=SimpleNamespace(id=FORTUNE_ID)),
        list_trace_projections=AsyncMock(return_value=(RUN_ID, seeded_events)),
    )

    async def _no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(fortune_routes, "smart_rate_limit", _no_limit)
    monkeypatch.setattr(fortune_routes, "get_repository", AsyncMock(return_value=fake_repo))

    client = TestClient(_fortune_test_app())
    res = client.get(f"/api/fortune/{FORTUNE_ID}/trace")
    assert res.status_code == 200, res.text
    body = res.json()
    wire = json.dumps(body, ensure_ascii=False)
    for canary in (BIRTH_CANARY, BIRTH_CANARY[:10], QUESTION_CANARY):
        assert canary not in wire
    assert body["fortune_id"] == FORTUNE_ID
    assert body["run_id"] == RUN_ID
    assert body["events"][0]["eventId"] == f"{RUN_ID}:span-1:end"
    assert set(body["events"][0].keys()) >= {
        "eventId", "runId", "spanId", "phase", "spanType",
        "agentName", "toolName", "durationMs", "status",
        "argSummary", "resultSummary", "startedAt", "endedAt",
    }


@pytest.mark.asyncio
async def test_conversation_endpoint_excludes_tool_and_reasoning_items(monkeypatch):
    """GET /conversation returns only user/assistant MESSAGE turns."""
    from fortune import routes as fortune_routes
    from fortune.session_store import filter_conversation_turns

    now = datetime.now(timezone.utc)
    rows = [
        (json.dumps({"role": "user", "content": "Why is metal weak?"}), now),
        (json.dumps({"type": "function_call", "name": "retrieve_classics", "arguments": "{}"}), now),
        (json.dumps({"type": "function_call_output", "call_id": "1", "output": "refs"}), now),
        (json.dumps({"type": "reasoning", "summary": [{"text": "hidden chain"}]}), now),
        (
            json.dumps({
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Metal is comparatively soft this decade."}],
            }),
            now,
        ),
        (json.dumps({"role": "tool", "content": "should skip"}), now),
    ]
    turns = filter_conversation_turns(rows)
    assert [t["role"] for t in turns] == ["user", "assistant"]
    assert turns[0]["text"] == "Why is metal weak?"
    assert "Metal is comparatively soft" in turns[1]["text"]
    assert all("hidden chain" not in t["text"] for t in turns)
    assert all("retrieve_classics" not in t["text"] for t in turns)

    async def _no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(fortune_routes, "smart_rate_limit", _no_limit)
    monkeypatch.setattr(
        fortune_routes,
        "list_conversation_turns",
        AsyncMock(return_value=turns),
    )

    client = TestClient(_fortune_test_app())
    res = client.get(f"/api/fortune/{FORTUNE_ID}/conversation")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["fortune_id"] == FORTUNE_ID
    assert [t["role"] for t in body["turns"]] == ["user", "assistant"]
    wire = json.dumps(body, ensure_ascii=False)
    assert "function_call" not in wire
    assert "hidden chain" not in wire
    for canary in (BIRTH_CANARY, QUESTION_CANARY):
        assert canary not in wire
