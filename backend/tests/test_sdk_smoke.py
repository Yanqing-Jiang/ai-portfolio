"""Offline compatibility smoke test for the pinned Agents SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import agents
import pytest
from agents import Agent, RunConfig, Runner
from agents.extensions.memory.sqlalchemy_session import SQLAlchemySession
from agents.items import ModelResponse
from agents.models.interface import Model, ModelTracing
from agents.usage import Usage
from openai.types.responses import ResponseOutputMessage, ResponseOutputText
from sqlalchemy.ext.asyncio import create_async_engine


class _MockModel(Model):
    def __init__(self) -> None:
        self.previous_response_ids: list[str | None] = []

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
        self.previous_response_ids.append(previous_response_id)
        message = ResponseOutputMessage(
            id="msg_smoke",
            content=[
                ResponseOutputText(
                    annotations=[], text="offline ok", type="output_text",
                )
            ],
            role="assistant",
            status="completed",
            type="message",
        )
        return ModelResponse(
            output=[message], usage=Usage(), response_id="resp_smoke",
        )

    def stream_response(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        async def _empty() -> AsyncIterator[Any]:
            if False:  # pragma: no cover
                yield None
        return _empty()


@pytest.mark.asyncio
async def test_openai_agents_0220_sdk_surface_without_network() -> None:
    assert agents.__version__ == "0.22.0"

    model = _MockModel()
    agent = Agent(name="sdk_smoke", instructions="Reply briefly.", model=model)
    runner = Runner()
    engine = create_async_engine(
        "postgresql+asyncpg://sdk:sdk@127.0.0.1:9/sdk",
    )
    session = SQLAlchemySession(
        "fortune_sdk_smoke", engine=engine, create_tables=False,
    )

    # 0.22.0 public surface: exercise it against a mock model, without
    # enabling it in Fortune (SQLAlchemySession remains our sole spine).
    result = await runner.run(
        agent,
        "ping",
        auto_previous_response_id=True,
        run_config=RunConfig(tracing_disabled=True),
    )

    assert result.final_output == "offline ok"
    assert model.previous_response_ids == [None]
    assert session.session_id == "fortune_sdk_smoke"
    await engine.dispose()
