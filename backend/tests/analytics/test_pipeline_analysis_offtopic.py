from __future__ import annotations

import asyncio
import pathlib
import sys
import types

from analytics.artifacts import (
    ChartArtifact,
    PipelineArtifacts,
    SQLExecutionArtifact,
    SQLGenerationArtifact,
)

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Stub optional google.genai dependency used by response_search imports.
google_stub = sys.modules.setdefault("google", types.ModuleType("google"))
genai_stub = types.ModuleType("google.genai")
genai_types_stub = types.ModuleType("google.genai.types")
setattr(genai_stub, "types", genai_types_stub)
setattr(google_stub, "genai", genai_stub)
sys.modules["google.genai"] = genai_stub
sys.modules["google.genai.types"] = genai_types_stub

from analytics.flows import planner_executor  # noqa: E402


def test_analysis_runs_with_empty_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_stream(
        data,
        sql,
        query,
        *,
        chart_spec=None,
        search_result=None,
        session_id=None,
        focus=None,
    ):
        if False:
            yield  # pragma: no cover
        yield "Finance-only reminder."

    monkeypatch.setattr(planner_executor, "stream_insights_llm", fake_stream)
    monkeypatch.setattr(planner_executor, "has_search_api_key", lambda: False)

    async def _exercise():
        pipeline = planner_executor.PlannerPipeline()
        ctx = await pipeline.initialize_context("Tell me a story", session_id="sess-offtopic")
        ctx.artifacts = PipelineArtifacts(
            sql_generation=SQLGenerationArtifact(query=ctx.query, sql=""),
            sql_execution=SQLExecutionArtifact(
                query=ctx.query,
                dataset=[],
                dataset_preview=[],
                sample_rows=[],
                status="success",
            ),
            chart=ChartArtifact(query=ctx.query, spec=None),
        )

        events = []
        async for event in pipeline.run_analysis_phase(ctx):
            events.append(event)
        return events, ctx

    events, ctx = asyncio.run(_exercise())

    assert any(evt.get("event") == "analysis_streaming" for evt in events)
    analysis_complete = next(evt for evt in events if evt.get("event") == "analysis_complete")
    analysis_payload = analysis_complete["data"]["analysis"]
    assert analysis_payload["analysis"] == "Finance-only reminder."
    receipt = ctx.tool_receipts.get("analysis_synthesis")
    assert receipt is not None
    assert receipt.status == "completed"
