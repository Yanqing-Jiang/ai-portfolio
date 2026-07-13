"""Regressions for session-only Ask continuity and writer serialization."""

from __future__ import annotations

import copy
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from agents import RunConfig
from agents.items import ModelResponse
from agents.models.interface import Model, ModelTracing
from agents.usage import Usage
from fastapi import HTTPException
from openai.types.responses import ResponseOutputMessage, ResponseOutputText

from fortune.agents import (
    EnrichedNarrativeOutput,
    FortuneRunContext,
    InsightBullet,
    InsightSection,
)
from fortune.routes import AskRequest, ask_fortune
from fortune.state import get_run_state, reset_run_state_for_tests
from fortune.triage import ASK_AGENT, _build_triage_prompt, run_triage


class _MemorySession:
    session_id = "fortune_same"
    session_settings = None

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    async def get_items(self, limit: int | None = None):
        items = self.items[-limit:] if limit is not None else self.items
        return copy.deepcopy(items)

    async def add_items(self, items):
        self.items.extend(copy.deepcopy(items))

    async def pop_item(self):
        return self.items.pop() if self.items else None

    async def clear_session(self):
        self.items.clear()


def _answer(turn: int) -> EnrichedNarrativeOutput:
    sections = [
        InsightSection(
            id=f"turn_{turn}_{idx}",
            icon="•",
            heading=f"Signal {idx}",
            tagline="Grounded follow-up.",
            bullets=[
                InsightBullet(icon="•", text="Use the established reading context."),
                InsightBullet(icon="•", text="Carry the prior answer forward."),
            ],
        )
        for idx in (1, 2)
    ]
    return EnrichedNarrativeOutput(tldr=f"Answer turn {turn}.", insights=sections)


class _RecordingModel(Model):
    def __init__(self) -> None:
        self.inputs: list[Any] = []

    async def get_response(
        self,
        system_instructions,
        input,
        model_settings,
        tools,
        output_schema,
        handoffs,
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt,
    ) -> ModelResponse:
        self.inputs.append(copy.deepcopy(input))
        turn = len(self.inputs)
        message = ResponseOutputMessage(
            id=f"msg_{turn}",
            content=[
                ResponseOutputText(
                    annotations=[],
                    text=_answer(turn).model_dump_json(),
                    type="output_text",
                )
            ],
            role="assistant",
            status="completed",
            type="message",
        )
        return ModelResponse(
            output=[message], usage=Usage(), response_id=f"resp_{turn}",
        )

    def stream_response(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        async def _empty() -> AsyncIterator[Any]:
            if False:  # pragma: no cover
                yield None
        return _empty()


@pytest.mark.asyncio
async def test_two_consecutive_asks_share_sql_session_history(monkeypatch) -> None:
    model = _RecordingModel()
    monkeypatch.setattr(ASK_AGENT, "model", model)
    import fortune.triage as triage
    monkeypatch.setattr(
        triage, "_run_config", lambda _ctx: RunConfig(tracing_disabled=True),
    )
    session = _MemorySession()
    ctx = FortuneRunContext(
        fortune_id="same",
        surface_id="fortune_main",
        focus="custom_wish",
        question="Will this plan work?",
    )
    foundation = {
        "pillars": {"day": {"stem": "Metal", "branch": "Tiger"}},
        "elements": {"Metal": 2, "Wood": 1},
        "references": [],
    }

    first = await run_triage(
        ctx, foundation=foundation, question="What supports it?",
        session=session, ask_mode=True,
    )
    second = await run_triage(
        ctx, foundation=foundation, question="What should I do next?",
        session=session, ask_mode=True,
    )

    assert first.tldr == "Answer turn 1."
    assert second.tldr == "Answer turn 2."
    assert len(model.inputs) == 2
    assert isinstance(model.inputs[1], list)
    second_input = json.dumps(model.inputs[1])
    assert "What supports it?" in second_input
    assert "Answer turn 1." in second_input


@pytest.mark.asyncio
async def test_concurrent_ask_returns_409_busy(monkeypatch) -> None:
    reset_run_state_for_tests()
    store = get_run_state()
    monkeypatch.setattr(store, "_redis", AsyncMock(return_value=None))
    token = await store.acquire_lock("busy-fortune")
    assert token is not None

    import fortune.routes as routes
    monkeypatch.setattr(routes, "smart_rate_limit", AsyncMock())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await ask_fortune(
                "busy-fortune",
                AskRequest(
                    question="Can you answer now?", client_request_id=uuid.uuid4(),
                ),
                MagicMock(),
            )
        assert exc_info.value.status_code == 409
        assert "busy" in str(exc_info.value.detail).lower()
        assert exc_info.value.headers == {"Retry-After": "3"}
    finally:
        await store.release_lock("busy-fortune", token)


def test_selected_section_is_projected_from_trusted_narrative() -> None:
    ctx = FortuneRunContext(
        fortune_id="same",
        surface_id="fortune_main",
        focus="custom_wish",
        question="What does this mean?",
    )
    prompt = _build_triage_prompt(
        ctx,
        {"pillars": {"day": {"stem": "Metal"}}},
        action_id=None,
        question="What does this mean?",
        latest_narrative={
            "tldr": "Stored summary",
            "wish": {
                "verdict": "Proceed carefully",
                "anchors": [
                    {"id": "anchor-1", "label": "Choose timing"},
                    {"id": "anchor-2", "label": "Keep scope small"},
                ],
            },
        },
        selected_section={
            "section_id": "anchor",
            "selection_id": "anchor-1",
            "data": "untrusted browser payload must be ignored",
        },
    )

    payload = json.loads(prompt)
    selected = payload["intent"]["selected_section"]
    assert selected["section_id"] == "anchor"
    assert selected["selection_id"] == "anchor-1"
    assert selected["data"] == {"id": "anchor-1", "label": "Choose timing"}
    assert "untrusted browser payload" not in prompt
