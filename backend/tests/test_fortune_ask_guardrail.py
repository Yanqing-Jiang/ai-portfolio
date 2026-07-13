"""Ask path done-gate + output guardrail (final-gate B3)."""

from __future__ import annotations

import copy
import asyncio
import json
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
from fortune.routes import (
    ASK_REQUEST_TIMEOUT_SECONDS,
    AskContextRequest,
    AskRequest,
    _ask_fortune_locked,
    _hydrate_foundation_from_snapshot,
    _merge_ask_foundation,
    ask_fortune,
)
from fortune.store import ASK_LEASE_TTL_SECONDS
from fortune.state import (
    CreateFortuneRequest,
    FortuneSession,
    get_run_state,
    reset_run_state_for_tests,
)

FORTUNE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
RUN_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
LEASE_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
DELIVERY_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
REJECTED_ASK = "REJECTED_ASK_never_echo_7c2e"


class _MemorySession:
    session_id = "fortune_guardrail"
    session_settings = None

    def __init__(self) -> None:
        self.items = [{"role": "assistant", "content": "approved prior answer"}]

    async def get_items(self, limit=None):
        items = self.items[-limit:] if limit is not None else self.items
        return copy.deepcopy(items)

    async def add_items(self, items):
        self.items.extend(copy.deepcopy(items))

    async def pop_item(self):
        return self.items.pop() if self.items else None

    async def clear_session(self):
        self.items.clear()

    async def _serialize_item(self, item):
        return json.dumps(item, sort_keys=True)


def _safe_foundation() -> dict:
    return {
        "analysis": MagicMock(),
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
    repo.get_ask_request = AsyncMock(return_value=None)
    async def _claim(**kwargs):
        return {
            "claimed": True,
            "status": "running",
            "payload_hash": kwargs["payload_hash"],
            "lease_token": LEASE_ID,
            "delivery_id": DELIVERY_ID,
            "response_json": None,
        }
    repo.claim_ask_request = AsyncMock(side_effect=_claim)
    repo.ensure_ask_run = AsyncMock(return_value=uuid.UUID(RUN_ID))
    repo.complete_ask_request = AsyncMock()
    repo.mark_ask_conversation_committed = AsyncMock()
    repo.commit_ask_conversation = AsyncMock()
    repo.complete_ask_with_conversation = AsyncMock()
    repo.reconcile_completed_ask_run = AsyncMock()
    repo.fail_ask_request = AsyncMock()
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
async def test_cold_snapshot_accepts_empty_interactions_and_restores_request_context():
    complete_mechanics = {
        "pillars": {},
        "hidden_stems": {},
        "ten_gods": [],
        "interactions": [],
        "seasonal_strength": {
            "day_master_element": "metal",
            "month_branch": "子",
            "season": "winter",
            "strength": "resting",
            "score": 0.5,
        },
        "luck_pillars": [],
        "annual_pillars": [],
        "enhanced_element_counts": {},
        "element_by_source": {},
        "harmony_score": 50.0,
    }
    repo = _repo()
    repo.get_snapshot = AsyncMock(return_value={
        "latest_mechanics": complete_mechanics,
        "latest_pillars": {
            "pillars": {},
            "elements": {},
            "person_b": {
                "pillars": {},
                "elements": {"Wood": 2},
                "mechanics": complete_mechanics,
            },
        },
        "latest_references": {"items": []},
        "request_context": {
            "focus": "compatibility",
            "original_question": "How do we work together?",
            "person_b": {"birth_iso": "1992-03-04T12:00:00"},
        },
    })

    hydrated = await _hydrate_foundation_from_snapshot(repo, FORTUNE_ID)

    assert hydrated is not None
    assert hydrated["analysis"].interactions == []
    assert hydrated["request_context"]["focus"] == "compatibility"
    assert "person_b" in hydrated["request_context"]
    assert hydrated["person_b"]["analysis"].interactions == []
    assert hydrated["person_b"]["elements"] == {"Wood": 2}


@pytest.mark.asyncio
async def test_cold_snapshot_derives_legacy_person_b_mechanics_from_stored_chart():
    from fortune.bazi_engine import compute_full_analysis

    primary = compute_full_analysis("1990-01-15T08:00:00", "UTC")
    person_b = compute_full_analysis("1992-03-04T12:00:00", "UTC")
    repo = _repo()
    repo.get_snapshot = AsyncMock(return_value={
        "latest_mechanics": primary.model_dump(),
        "latest_pillars": {
            "pillars": primary.pillars,
            "elements": primary.enhanced_element_counts,
            "person_b": {
                "pillars": person_b.pillars,
                "elements": person_b.enhanced_element_counts,
                # Legacy compatibility snapshots only persisted the chart.
                "mechanics": {"pillars": person_b.pillars},
            },
        },
        "latest_references": {"items": []},
        "request_context": {"focus": "compatibility"},
    })

    hydrated = await _hydrate_foundation_from_snapshot(repo, FORTUNE_ID)

    assert hydrated is not None
    assert hydrated["person_b"]["analysis"].pillars["day_master"] == "己"
    assert hydrated["person_b"]["analysis"].hidden_stems
    assert isinstance(hydrated["person_b"]["analysis"].interactions, list)


def test_hot_person_b_overlay_preserves_hydrated_analysis():
    durable_analysis = MagicMock()
    hydrated = {
        "analysis": MagicMock(),
        "person_b": {
            "analysis": durable_analysis,
            "pillars": {"day": "durable"},
            "elements": {"Wood": 2},
        },
    }
    hot = {
        "person_b": {
            "pillars": {"day": "live"},
            "elements": {"Wood": 3},
        },
    }

    merged = _merge_ask_foundation(hydrated, hot)

    assert merged["person_b"]["analysis"] is durable_analysis
    assert merged["person_b"]["pillars"] == {"day": "live"}


@pytest.mark.asyncio
async def test_ask_uses_crash_recovery_lease_for_serialization_lock(monkeypatch):
    import fortune.routes as routes

    store = MagicMock()
    store.acquire_lock = AsyncMock(return_value="lease")
    store.release_lock = AsyncMock()
    monkeypatch.setattr(routes, "smart_rate_limit", AsyncMock())
    monkeypatch.setattr(routes, "get_run_state", MagicMock(return_value=store))
    monkeypatch.setattr(
        routes,
        "_ask_fortune_locked",
        AsyncMock(return_value=_answer()),
    )

    await ask_fortune(
        FORTUNE_ID,
        AskRequest(question="What supports this?", client_request_id=uuid.uuid4()),
        MagicMock(),
    )

    store.acquire_lock.assert_awaited_once_with(
        FORTUNE_ID, ttl=ASK_LEASE_TTL_SECONDS,
    )


@pytest.mark.asyncio
async def test_ask_times_out_before_serialization_lease_expires(monkeypatch):
    import fortune.routes as routes

    store = MagicMock()
    store.acquire_lock = AsyncMock(return_value="lease")
    store.release_lock = AsyncMock()

    async def _slow_ask(*args, **kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(routes, "smart_rate_limit", AsyncMock())
    monkeypatch.setattr(routes, "get_run_state", MagicMock(return_value=store))
    monkeypatch.setattr(routes, "ASK_REQUEST_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(routes, "_ask_fortune_locked", _slow_ask)

    with pytest.raises(HTTPException) as exc_info:
        await ask_fortune(
            FORTUNE_ID,
            AskRequest(question="What supports this?", client_request_id=uuid.uuid4()),
            MagicMock(),
        )

    assert exc_info.value.status_code == 504
    assert ASK_REQUEST_TIMEOUT_SECONDS < ASK_LEASE_TTL_SECONDS
    store.release_lock.assert_awaited_once_with(FORTUNE_ID, "lease")


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
            AskRequest(question="What supports this?", client_request_id=uuid.uuid4()),
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
    durable_session = _MemorySession()
    monkeypatch.setattr(routes, "get_ask_session", AsyncMock(return_value=durable_session))

    async def rejected_triage(*args, **kwargs):
        await kwargs["session"].add_items([
            {"role": "user", "content": "unsafe question"},
            {"role": "assistant", "content": REJECTED_ASK},
        ])
        return _answer(REJECTED_ASK)

    monkeypatch.setattr(routes, "run_triage", AsyncMock(side_effect=rejected_triage))
    monkeypatch.setattr(
        routes,
        "ensure_narrative_guardrail",
        AsyncMock(side_effect=OutputGuardrailTripwireTriggered(MagicMock())),
    )

    response = await _ask_fortune_locked(
        FORTUNE_ID,
        AskRequest(
            question="Tell me something unsafe?", client_request_id=uuid.uuid4(),
        ),
        store=store,
    )

    narrative = response.narrative
    dumped = str(narrative)
    assert REJECTED_ASK not in dumped
    assert "safely present this reading" in narrative["tldr"]
    safe_commit = repo.complete_ask_with_conversation.await_args.kwargs
    assert safe_commit["run_status"] == "failed_guardrail"
    assert safe_commit["session_items"] == [
        {"role": "user", "content": "Tell me something unsafe?"},
        {"role": "assistant", "content": narrative["tldr"]},
    ]
    assert REJECTED_ASK not in str(safe_commit["session_items"])
    done_calls = [
        call for call in repo.update_run_status.await_args_list
        if len(call.args) >= 2 and call.args[1] == "done"
    ]
    assert done_calls == []
    assert durable_session.items == [
        {"role": "assistant", "content": "approved prior answer"},
    ]


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
    triage = AsyncMock(return_value=expected)
    monkeypatch.setattr(routes, "run_triage", triage)
    monkeypatch.setattr(
        routes, "ensure_narrative_guardrail", AsyncMock(return_value=MagicMock()),
    )

    response = await _ask_fortune_locked(
        FORTUNE_ID,
        AskRequest(
            question="What should I watch for?",
            client_request_id=uuid.uuid4(),
            context=AskContextRequest(section_id="anchor", selection_id="anchor-1"),
        ),
        store=store,
    )

    assert response.narrative["tldr"] == "Happy path ask answer."
    assert triage.await_args.kwargs["selected_section"] == {
        "section_id": "anchor",
        "selection_id": "anchor-1",
    }
    repo.complete_ask_request.assert_awaited_once()
    assert repo.complete_ask_request.await_args.kwargs["run_status"] == "done"
    assert repo.complete_ask_request.await_args.kwargs["run_id"] == uuid.UUID(RUN_ID)
    assert repo.complete_ask_request.await_args.kwargs["session_items"] == [
        {"role": "user", "content": "What should I watch for?"},
        {"role": "assistant", "content": "Happy path ask answer."},
    ]
    assert repo.complete_ask_request.await_args.kwargs["conversation_committed"] is False


@pytest.mark.asyncio
async def test_idempotency_completion_failure_does_not_commit_session_turn(monkeypatch):
    await _seed_session_with_foundation()
    store = get_run_state()
    monkeypatch.setattr(store, "_redis", AsyncMock(return_value=None))
    repo = _repo()
    repo.complete_ask_with_conversation = AsyncMock(side_effect=RuntimeError("db write failed"))
    durable_session = _MemorySession()

    import fortune.routes as routes
    monkeypatch.setattr(routes, "get_repository", AsyncMock(return_value=repo))
    monkeypatch.setattr(routes, "_latest_non_ask_run_status", AsyncMock(return_value="done"))
    monkeypatch.setattr(routes, "get_ask_session", AsyncMock(return_value=durable_session))

    async def completed_triage(*args, **kwargs):
        await kwargs["session"].add_items([
            {"role": "user", "content": "new question"},
            {"role": "assistant", "content": "new answer"},
        ])
        return _answer("new answer")

    monkeypatch.setattr(routes, "run_triage", AsyncMock(side_effect=completed_triage))
    monkeypatch.setattr(routes, "ensure_narrative_guardrail", AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        await _ask_fortune_locked(
            FORTUNE_ID,
            AskRequest(question="new question", client_request_id=uuid.uuid4()),
            store=store,
        )

    assert exc_info.value.status_code == 503
    assert durable_session.items == [
        {"role": "assistant", "content": "approved prior answer"},
    ]
    repo.fail_ask_request.assert_awaited_once()
    statuses = [call.args[1] for call in repo.update_run_status.await_args_list]
    assert "done" not in statuses
    assert "error" in statuses


@pytest.mark.asyncio
async def test_completed_retry_replays_before_cold_readiness_hydration(monkeypatch):
    reset_run_state_for_tests()
    store = get_run_state()
    monkeypatch.setattr(store, "_redis", AsyncMock(return_value=None))
    repo = _repo()
    request_id = uuid.uuid4()
    question = "Can I recover this answer?"
    request = AskRequest(question=question, client_request_id=request_id)
    import fortune.routes as routes

    saved = {
        "fortune_id": FORTUNE_ID,
        "run_id": RUN_ID,
        "narrative": _answer("Recovered before readiness.").model_dump(),
        "degraded_memory": False,
        "chain_status": "disabled",
    }
    repo.get_ask_request = AsyncMock(return_value={
        "status": "done",
        "payload_hash": routes._ask_payload_hash(request),
        "lease_token": LEASE_ID,
        "delivery_id": DELIVERY_ID,
        "response_json": saved,
        "session_items": None,
        "conversation_committed": True,
    })
    repo.get_snapshot = AsyncMock(
        side_effect=AssertionError("completed replay must precede snapshot hydration"),
    )
    monkeypatch.setattr(routes, "get_repository", AsyncMock(return_value=repo))
    triage = AsyncMock(side_effect=AssertionError("completed replay must not call a model"))
    monkeypatch.setattr(routes, "run_triage", triage)

    response = await _ask_fortune_locked(FORTUNE_ID, request, store=store)

    assert response.narrative["tldr"] == "Recovered before readiness."
    repo.get_snapshot.assert_not_awaited()
    repo.claim_ask_request.assert_not_awaited()
    triage.assert_not_awaited()


@pytest.mark.asyncio
async def test_ask_retry_replays_saved_response_without_second_model_call(monkeypatch):
    await _seed_session_with_foundation()
    store = get_run_state()
    monkeypatch.setattr(store, "_redis", AsyncMock(return_value=None))
    repo = _repo()
    request_id = uuid.uuid4()
    saved = {
        "fortune_id": FORTUNE_ID,
        "run_id": RUN_ID,
        "narrative": _answer("Already completed.").model_dump(),
        "degraded_memory": False,
        "chain_status": "disabled",
    }

    async def _replay(**kwargs):
        return {
            "claimed": False,
            "status": "done",
            "payload_hash": kwargs["payload_hash"],
            "lease_token": LEASE_ID,
            "delivery_id": DELIVERY_ID,
            "response_json": saved,
            "session_items": None,
            "conversation_committed": True,
        }

    repo.claim_ask_request = AsyncMock(side_effect=_replay)
    import fortune.routes as routes
    monkeypatch.setattr(routes, "get_repository", AsyncMock(return_value=repo))
    monkeypatch.setattr(routes, "_latest_non_ask_run_status", AsyncMock(return_value="done"))
    triage = AsyncMock(side_effect=AssertionError("replay must not run triage"))
    monkeypatch.setattr(routes, "run_triage", triage)

    response = await _ask_fortune_locked(
        FORTUNE_ID,
        AskRequest(question="Same question", client_request_id=request_id),
        store=store,
    )

    assert response.run_id == RUN_ID
    assert response.narrative["tldr"] == "Already completed."
    triage.assert_not_awaited()
    repo.create_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_saved_response_repairs_unacknowledged_session_without_duplicates(monkeypatch):
    await _seed_session_with_foundation()
    store = get_run_state()
    monkeypatch.setattr(store, "_redis", AsyncMock(return_value=None))
    repo = _repo()
    request_id = uuid.uuid4()
    saved = {
        "fortune_id": FORTUNE_ID,
        "run_id": RUN_ID,
        "narrative": _answer("Recovered answer.").model_dump(),
        "degraded_memory": False,
        "chain_status": "disabled",
    }
    pending = [
        {"role": "user", "content": "Recovered question"},
        {"role": "assistant", "content": "Recovered answer"},
    ]

    async def _replay(**kwargs):
        return {
            "claimed": False,
            "status": "done",
            "payload_hash": kwargs["payload_hash"],
            "lease_token": LEASE_ID,
            "delivery_id": DELIVERY_ID,
            "response_json": saved,
            "session_items": pending,
            "conversation_committed": False,
        }

    repo.claim_ask_request = AsyncMock(side_effect=_replay)
    durable_session = _MemorySession()
    delivered: set[uuid.UUID] = set()

    async def _commit(**kwargs):
        if kwargs["delivery_id"] in delivered:
            return
        delivered.add(kwargs["delivery_id"])
        durable_session.items.extend(
            json.loads(item) for item in kwargs["serialized_items"]
        )

    repo.commit_ask_conversation = AsyncMock(side_effect=_commit)
    import fortune.routes as routes
    monkeypatch.setattr(routes, "get_repository", AsyncMock(return_value=repo))
    monkeypatch.setattr(routes, "_latest_non_ask_run_status", AsyncMock(return_value="done"))
    monkeypatch.setattr(routes, "get_ask_session", AsyncMock(return_value=durable_session))

    request = AskRequest(question="Recovered question", client_request_id=request_id)
    await _ask_fortune_locked(FORTUNE_ID, request, store=store)
    await _ask_fortune_locked(FORTUNE_ID, request, store=store)

    assert durable_session.items == [
        {"role": "assistant", "content": "approved prior answer"},
        *pending,
    ]
    assert repo.commit_ask_conversation.await_count == 2


@pytest.mark.asyncio
async def test_ask_failed_attempt_releases_idempotency_key(monkeypatch):
    await _seed_session_with_foundation()
    store = get_run_state()
    monkeypatch.setattr(store, "_redis", AsyncMock(return_value=None))
    repo = _repo()
    request_id = uuid.uuid4()
    import fortune.routes as routes
    monkeypatch.setattr(routes, "get_repository", AsyncMock(return_value=repo))
    monkeypatch.setattr(routes, "_latest_non_ask_run_status", AsyncMock(return_value="done"))
    monkeypatch.setattr(routes, "get_ask_session", AsyncMock(return_value=None))
    monkeypatch.setattr(routes, "run_triage", AsyncMock(side_effect=RuntimeError("model down")))

    with pytest.raises(HTTPException) as exc_info:
        await _ask_fortune_locked(
            FORTUNE_ID,
            AskRequest(question="Try once", client_request_id=request_id),
            store=store,
        )

    assert exc_info.value.status_code == 500
    repo.fail_ask_request.assert_awaited_once_with(
        fortune_id=uuid.UUID(FORTUNE_ID), client_request_id=request_id,
        lease_token=LEASE_ID,
    )
