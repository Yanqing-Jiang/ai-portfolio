"""Ask path done-gate + output guardrail (final-gate B3)."""

from __future__ import annotations

import uuid
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from agents import OutputGuardrailTripwireTriggered
from fastapi import HTTPException

from fortune.agents import (
    EnrichedNarrativeOutput,
    InsightBullet,
    InsightSection,
)
from fortune.routes import AskRequest, _ask_fortune_locked, ask_fortune
from fortune.state import (
    CreateFortuneRequest,
    FortuneSession,
    get_run_state,
    reset_run_state_for_tests,
)

FORTUNE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
RUN_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
REJECTED_ASK = "REJECTED_ASK_never_echo_7c2e"


def _safe_foundation() -> dict:
    return {
        "pillars": {"day": {"stem": "Metal", "branch": "Tiger"}},
        "elements": {"Metal": 2, "Wood": 1},
        "references": [],
    }


def _answer(tldr: str = "Grounded follow-up answer.") -> EnrichedNarrativeOutput:
    return EnrichedNarrativeOutput(
        tldr=tldr,
        insights=[
            InsightSection(
                id="signal_one",
                icon="•",
                heading="Signal One",
                tagline="Grounded follow-up.",
                bullets=[
                    InsightBullet(icon="•", text="Use the established reading context."),
                    InsightBullet(icon="•", text="Stay reflective and practical."),
                ],
            ),
            InsightSection(
                id="signal_two",
                icon="•",
                heading="Signal Two",
                tagline="Second card.",
                bullets=[
                    InsightBullet(icon="•", text="Cite only supplied references."),
                    InsightBullet(icon="•", text="Keep continuity with prior turns."),
                ],
            ),
        ],
    )


def _repo(*, available: bool = True) -> MagicMock:
    repo = MagicMock()
    repo.available = available
    repo.pool = MagicMock() if available else None
    repo.create_run = AsyncMock(
        return_value=MagicMock(id=uuid.UUID(RUN_ID)),
    )
    repo.update_run_status = AsyncMock()
    repo.get_fortune = AsyncMock(return_value={"id": FORTUNE_ID})
    repo.get_snapshot = AsyncMock(return_value=None)
    return repo


async def _seed_session_with_foundation() -> None:
    reset_run_state_for_tests()
    store = get_run_state()
    session = FortuneSession(
        fortune_id=FORTUNE_ID,
        run_id=str(uuid.uuid4()),
        surface_id="fortune_main",
        request=CreateFortuneRequest(
            birth_iso="1990-01-15T08:00:00",
            timezone="America/Los_Angeles",
            question="Will this plan work?",
            focus="wish",
            gender="unknown",
        ),
        latest_foundation=_safe_foundation(),
        latest_narrative={"tldr": "Prior reading summary."},
    )
    await store.put(session)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_status", ["failed_guardrail", "error"])
async def test_ask_returns_409_when_latest_initial_not_done(monkeypatch, bad_status):
    await _seed_session_with_foundation()
    store = get_run_state()
    monkeypatch.setattr(store, "_redis", AsyncMock(return_value=None))

    repo = _repo()
    import fortune.routes as routes

    monkeypatch.setattr(routes, "smart_rate_limit", AsyncMock())
    monkeypatch.setattr(routes, "get_repository", AsyncMock(return_value=repo))
    monkeypatch.setattr(
        routes,
        "_latest_non_ask_run_status",
        AsyncMock(return_value=bad_status),
    )
    triage = AsyncMock(side_effect=AssertionError("triage must not run"))
    monkeypatch.setattr(routes, "run_triage", triage)

    with pytest.raises(HTTPException) as exc_info:
        await ask_fortune(
            FORTUNE_ID,
            AskRequest(question="What supports this?"),
            MagicMock(),
        )

    assert exc_info.value.status_code == 409
    assert "Reading not complete" in str(exc_info.value.detail)
    triage.assert_not_awaited()


@pytest.mark.asyncio
async def test_ask_tripwire_returns_safe_rejection_never_echoes_model(monkeypatch):
    await _seed_session_with_foundation()
    store = get_run_state()
    monkeypatch.setattr(store, "_redis", AsyncMock(return_value=None))

    repo = _repo()
    import fortune.routes as routes

    monkeypatch.setattr(routes, "smart_rate_limit", AsyncMock())
    monkeypatch.setattr(routes, "get_repository", AsyncMock(return_value=repo))
    monkeypatch.setattr(
        routes, "_latest_non_ask_run_status", AsyncMock(return_value="done"),
    )
    monkeypatch.setattr(routes, "get_ask_session", AsyncMock(return_value=None))
    monkeypatch.setattr(
        routes,
        "run_triage",
        AsyncMock(return_value=_answer(REJECTED_ASK)),
    )
    monkeypatch.setattr(
        routes,
        "ensure_narrative_guardrail",
        AsyncMock(side_effect=OutputGuardrailTripwireTriggered(MagicMock())),
    )

    response = await _ask_fortune_locked(
        FORTUNE_ID,
        AskRequest(question="Tell me something unsafe?"),
        store=store,
    )

    narrative = response.narrative
    dumped = str(narrative)
    assert REJECTED_ASK not in dumped
    assert "safely present this reading" in narrative["tldr"]
    repo.update_run_status.assert_any_await(
        ANY,
        "failed_guardrail",
        error_message="output_guardrail_tripwire",
    )
    done_calls = [
        call for call in repo.update_run_status.await_args_list
        if len(call.args) >= 2 and call.args[1] == "done"
    ]
    assert done_calls == []


@pytest.mark.asyncio
async def test_ask_happy_path_returns_narrative(monkeypatch):
    await _seed_session_with_foundation()
    store = get_run_state()
    monkeypatch.setattr(store, "_redis", AsyncMock(return_value=None))

    repo = _repo()
    import fortune.routes as routes

    monkeypatch.setattr(routes, "smart_rate_limit", AsyncMock())
    monkeypatch.setattr(routes, "get_repository", AsyncMock(return_value=repo))
    monkeypatch.setattr(
        routes, "_latest_non_ask_run_status", AsyncMock(return_value="done"),
    )
    monkeypatch.setattr(routes, "get_ask_session", AsyncMock(return_value=None))
    expected = _answer("Happy path ask answer.")
    monkeypatch.setattr(routes, "run_triage", AsyncMock(return_value=expected))
    monkeypatch.setattr(
        routes, "ensure_narrative_guardrail", AsyncMock(return_value=MagicMock()),
    )

    response = await _ask_fortune_locked(
        FORTUNE_ID,
        AskRequest(question="What should I watch for?"),
        store=store,
    )

    assert response.narrative["tldr"] == "Happy path ask answer."
    repo.update_run_status.assert_any_await(ANY, "done")
