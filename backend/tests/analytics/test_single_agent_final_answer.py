from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.append(str(Path(__file__).resolve().parents[2]))

google_stub = sys.modules.setdefault("google", types.ModuleType("google"))
genai_stub = types.ModuleType("google.genai")
genai_types_stub = types.ModuleType("google.genai.types")
setattr(genai_stub, "types", genai_types_stub)
setattr(google_stub, "genai", genai_stub)
sys.modules["google.genai"] = genai_stub
sys.modules["google.genai.types"] = genai_types_stub

from analytics.artifacts import AnalysisArtifact, PipelineArtifacts
from analytics.flows.single_agent_tools import SingleAgentController, _SingleAgentToolHooks
from analytics.flows.revision_directive import RevisionDirective
from analytics.routing import FollowUpRoute


async def _collect_async(gen):
    results = []
    async for item in gen:
        results.append(item)
    return results


def test_single_agent_fallback_final_answer_when_data_incomplete() -> None:
    controller = SingleAgentController()

    artifacts = PipelineArtifacts(
        analysis=AnalysisArtifact(
            query="Compare NVDA and AMD revenue in FY24",
            analysis_text="Preliminary narrative for comparison.",
        )
    )
    controller._planner._latest_artifacts = artifacts  # type: ignore[attr-defined]

    hooks = _SingleAgentToolHooks(controller)
    hooks._last_analysis_payload = {"analysis": "Preliminary narrative for comparison."}
    hooks._emitted_cohesive = False

    async def collect():
        results = []
        async for event in hooks.on_flow_end({"session_id": "sess-123"}):
            results.append(event)
        return results

    events = asyncio.run(collect())

    assert len(events) == 1
    event = events[0]
    assert event["event"] == "final_answer"
    data = event["data"]
    assert data["final_answer_only"] is True
    assert data["analysis_available"] is True
    assert data["flow_mode"] == "single_agent"
    assert set(data.get("missing_components", [])) == {"sql", "stock", "web"}
    assert data.get("follow_up_route") == controller.follow_up_route.value

    message = data["message"]
    assert message.startswith("Preliminary narrative for comparison.")
    # Redundant pending-lanes banner removed; ensure it is not present.
    assert "Pending lanes:" not in message


def test_single_agent_chart_revision_final_answer_mentions_reuse() -> None:
    controller = SingleAgentController()
    controller.set_follow_up_route(FollowUpRoute.REUSE_SQL)

    hooks = _SingleAgentToolHooks(controller)
    hooks._last_analysis_payload = {
        "analysis": "Existing analysis retained.",
        "sql": "SELECT * FROM equities;",
        "stock_widget": {"symbols": [["NASDAQ:NVDA", "NVDA"]]},
        "web_context": {"summary": "Earnings preview already captured."},
    }

    payload = hooks._build_final_answer_payload()
    assert payload is not None
    assert payload["missing_components"] == []
    message = payload["message"]
    assert "Chart revision applied." in message
    assert "Reused cached datasets for consistency." in message


def test_agentic_revision_reuses_cached_components() -> None:
    controller = SingleAgentController()
    directive = RevisionDirective.from_payload(
        raw_text="Rewrite the analysis to highlight customer adoption signals for NVDA",
        targets={"analysis"},
        requested_focus="Highlight customer adoption signals",
        chart_patch=None,
        agentic=True,
    )
    controller.set_revision_directive(directive)

    hooks = _SingleAgentToolHooks(controller)
    hooks._last_analysis_payload = {"analysis": "Updated analysis with customer adoption signals."}

    payload = hooks._build_final_answer_payload()
    assert payload is not None
    assert payload["missing_components"] == []
    message = payload["message"]
    assert "Revision applied. Reused cached datasets for untouched lanes." in message
    assert controller.follow_up_route == FollowUpRoute.REUSE_SQL


def test_tool_telemetry_dedup() -> None:
    controller = SingleAgentController()
    hooks = _SingleAgentToolHooks(controller)

    async def _drain(gen):
        results = []
        async for item in gen:
            results.append(item)
        return results

    async def _run_sequence():
        ctx = {"session_id": "sess-telemetry"}
        emitted: List[Dict[str, Any]] = []
        async for _ in hooks.on_flow_start(ctx):
            pass
        emitted.extend(
            await _drain(
                hooks.before_event(
                    ctx,
                    {"event": "progress", "data": {"step": "classification"}},
                )
            )
        )
        emitted.extend(
            await _drain(
                hooks.after_event(
                    ctx,
                    {
                        "event": "classification_complete",
                        "data": {
                            "intent_key": "ai.research",
                            "confidence": 0.74,
                            "clarifications_needed": True,
                        },
                    },
                )
            )
        )
        emitted.extend(
            await _drain(
                hooks.before_event(
                    ctx,
                    {"event": "progress", "data": {"step": "intent_detection"}},
                )
            )
        )
        emitted.extend(
            await _drain(
                hooks.after_event(
                    ctx,
                    {
                        "event": "intent_detection_complete",
                        "data": {
                            "intent_key": "ai.research",
                            "confidence": 0.82,
                            "clarifications_needed": False,
                        },
                    },
                )
            )
        )
        return emitted

    events = asyncio.run(_run_sequence())
    tool_calls = [event for event in events if event.get("event") == "tool_call"]
    starts = [event for event in tool_calls if event["data"].get("status") == "start"]
    ends = [event for event in tool_calls if event["data"].get("status") == "end"]

    assert len(starts) == 1, "classification and intent detection should share one start"
    assert len(ends) == 1, "multi-phase tool should emit a single completion"
    details = ends[0]["data"].get("details") or {}
    assert details.get("intent_key") == "ai.research"
    assert details.get("confidence") == 0.82
    assert details.get("clarifications_needed") is False


def test_sql_multi_phase_emits_single_completion() -> None:
    controller = SingleAgentController()
    hooks = _SingleAgentToolHooks(controller)

    async def _collect(gen):
        results = []
        async for payload in gen:
            results.append(payload)
        return results

    async def _run_sequence():
        ctx = {"session_id": "sess-sql"}
        emitted: List[Dict[str, Any]] = []
        async for _ in hooks.on_flow_start(ctx):
            pass
        emitted.extend(
            await _collect(
                hooks.before_event(
                    ctx,
                    {"event": "progress", "data": {"step": "sql_compilation"}},
                )
            )
        )
        emitted.extend(
            await _collect(
                hooks.before_event(
                    ctx,
                    {"event": "progress", "data": {"step": "sql_validation"}},
                )
            )
        )
        emitted.extend(
            await _collect(
                hooks.after_event(
                    ctx,
                    {
                        "event": "sql_generated",
                        "data": {
                            "sql": "select * from revenues",
                            "llm_used": True,
                            "attempt": 2,
                            "elapsed_ms": 1800,
                        },
                    },
                )
            )
        )
        emitted.extend(
            await _collect(
                hooks.after_event(
                    ctx,
                    {
                        "event": "sql_validated",
                        "data": {
                            "ok": True,
                            "issues_count": 0,
                            "attempt": 2,
                            "elapsed_ms": 240,
                        },
                    },
                )
            )
        )
        return emitted

    events = asyncio.run(_run_sequence())
    tool_ends = [
        event
        for event in events
        if event.get("event") == "tool_call" and event["data"].get("status") == "end"
    ]
    sql_generator_ends = [evt for evt in tool_ends if evt["data"].get("tool") == "sql_generator"]
    sql_validator_ends = [evt for evt in tool_ends if evt["data"].get("tool") == "sql_validator"]
    assert len(sql_generator_ends) == 1
    assert len(sql_validator_ends) == 1
    generator_details = sql_generator_ends[0]["data"].get("details") or {}
    assert generator_details.get("validated") is True
    assert generator_details.get("issues_count") == 0
    assert generator_details.get("attempt") == 2


def test_chart_multi_phase_collapses_patch_events() -> None:
    controller = SingleAgentController()
    hooks = _SingleAgentToolHooks(controller)

    async def _collect(gen):
        bucket = []
        async for payload in gen:
            bucket.append(payload)
        return bucket

    async def _run_sequence():
        ctx = {"session_id": "sess-chart"}
        emitted: List[Dict[str, Any]] = []
        async for _ in hooks.on_flow_start(ctx):
            pass
        emitted.extend(
            await _collect(
                hooks.before_event(
                    ctx,
                    {"event": "progress", "data": {"step": "chart_revision"}},
                )
            )
        )
        emitted.extend(
            await _collect(
                hooks.after_event(
                    ctx,
                    {
                        "event": "chart_patch",
                        "data": {
                            "chart_type": "line",
                            "chart_spec": {"meta": {"chartDesign": {"chart_type": "line", "series": [1, 2, 3]}}},
                        },
                    },
                )
            )
        )
        emitted.extend(
            await _collect(
                hooks.after_event(
                    ctx,
                    {
                        "event": "chart_generated",
                        "data": {
                            "chart_type": "line",
                            "chart_spec": {"meta": {"chartDesign": {"chart_type": "line", "series": [1, 2]}}},
                        },
                    },
                )
            )
        )
        return emitted

    events = asyncio.run(_run_sequence())
    chart_ends = [
        evt
        for evt in events
        if evt.get("event") == "tool_call"
        and evt["data"].get("tool") == "chart_designer"
        and evt["data"].get("status") == "end"
    ]
    assert len(chart_ends) == 1
    details = chart_ends[0]["data"].get("details") or {}
    assert details.get("revision_applied") is True
    assert details.get("series_count") == 2
    assert "spec_hash" in details


def test_analysis_multi_phase_emits_single_completion() -> None:
    controller = SingleAgentController()
    hooks = _SingleAgentToolHooks(controller)

    async def _collect(gen):
        bucket = []
        async for payload in gen:
            bucket.append(payload)
        return bucket

    async def _run_sequence():
        ctx = {"session_id": "sess-analysis"}
        emitted: List[Dict[str, Any]] = []
        async for _ in hooks.on_flow_start(ctx):
            pass
        emitted.extend(
            await _collect(
                hooks.before_event(
                    ctx,
                    {"event": "progress", "data": {"step": "analysis_revision"}},
                )
            )
        )
        emitted.extend(
            await _collect(
                hooks.after_event(
                    ctx,
                    {
                        "event": "analysis_revision",
                        "data": {
                            "analysis_length": 120,
                            "analysis": "Rewrite intro paragraph",
                            "refresh_mode": "light",
                        },
                    },
                )
            )
        )
        emitted.extend(
            await _collect(
                hooks.after_event(
                    ctx,
                    {
                        "event": "analysis_complete",
                        "data": {
                            "analysis": "Final narrative about NVDA vs AMD",
                            "analysis_sources": [{"source": "10-K"}],
                            "analysis_length": 420,
                        },
                    },
                )
            )
        )
        return emitted

    events = asyncio.run(_run_sequence())
    analysis_ends = [
        evt
        for evt in events
        if evt.get("event") == "tool_call"
        and evt["data"].get("tool") == "analysis_writer"
        and evt["data"].get("status") == "end"
    ]
    assert len(analysis_ends) == 1
    details = analysis_ends[0]["data"].get("details") or {}
    assert details.get("revision_event") is True
    assert details.get("analysis_length") == 420
    assert details.get("source_count") == 1


def test_forward_with_hooks_emits_cancellation_when_stream_incomplete() -> None:
    controller = SingleAgentController()
    hooks = _SingleAgentToolHooks(controller)

    async def _stream():
        yield {"event": "progress", "data": {"step": "classification"}}

    async def _consume():
        events: List[Dict[str, Any]] = []
        async for event in controller._forward_with_hooks(_stream(), hooks, session_id="sess-cancel"):
            events.append(event)
        return events

    events = asyncio.run(_consume())
    cancellations = [
        evt for evt in events if evt.get("event") == "workflow_complete" and evt.get("data", {}).get("status") == "cancelled"
    ]
    assert cancellations, "expected synthetic cancellation event when stream ends without workflow_complete"


def test_forward_with_hooks_requests_sequencer_cancellation() -> None:
    controller = SingleAgentController()
    hooks = _SingleAgentToolHooks(controller)

    class _StubSequencer:
        def __init__(self) -> None:
            self.cancelled: bool = False
            self.reason: Optional[str] = None

        def abort_pending_lanes(self, reason: str = "cancelled") -> List[str]:
            self.cancelled = True
            self.reason = reason
            return ["sql", "analysis"]

        def lane_presentations(self) -> Dict[str, str]:
            return {"sql": "running", "analysis": "pending"}

    stub_sequencer = _StubSequencer()
    controller._active_sequencer = stub_sequencer  # type: ignore[assignment]

    async def _empty_stream():
        if False:
            yield {}

    async def _consume():
        events: List[Dict[str, Any]] = []
        async for event in controller._forward_with_hooks(_empty_stream(), hooks, session_id="sess-stub"):
            events.append(event)
        return events

    events = asyncio.run(_consume())
    assert stub_sequencer.cancelled is True
    assert stub_sequencer.reason == "stream_disconnected"
    assert controller._active_sequencer is None, "active sequencer should be cleared after cancellation"
    cancellation_events = [evt for evt in events if evt.get("event") == "workflow_complete"]
    assert cancellation_events
    assert cancellation_events[-1]["data"]["pending_lanes"] == ["sql", "analysis"]


def test_agentic_revision_emits_agent_tool_events() -> None:
    controller = SingleAgentController()
    controller._agentic_revision_mode = True  # type: ignore[attr-defined]
    controller._agentic_lane_targets = {"analysis"}  # type: ignore[attr-defined]
    hooks = _SingleAgentToolHooks(controller)
    hooks._agentic_revision_mode = True  # type: ignore[attr-defined]
    ctx = {"session_id": "sess-agent"}

    async def _run():
        events: List[Dict[str, Any]] = []
        async for _ in hooks.on_flow_start(ctx):
            pass
        events.extend(
            await _collect_async(
                hooks.before_event(
                    ctx,
                    {"event": "progress", "data": {"step": "analysis_generation"}},
                )
            )
        )
        events.extend(
            await _collect_async(
                hooks.after_event(
                    ctx,
                    {
                        "event": "analysis_complete",
                        "data": {
                            "analysis": "Revised narrative",
                            "analysis_length": 128,
                        },
                    },
                )
            )
        )
        return events

    events = asyncio.run(_run())
    agent_calls = [evt for evt in events if evt.get("event") == "agent_tool_call"]
    agent_completions = [evt for evt in events if evt.get("event") == "agent_tool_complete"]
    assert agent_calls, "expected agent_tool_call event"
    assert agent_completions, "expected agent_tool_complete event"
    call_payload = agent_calls[0]["data"]
    assert call_payload["tool_call"]["name"] == "analysis_writer"
    assert call_payload["status"] == "start"
    assert agent_completions[0]["data"]["tool_call"]["status"] == "completed"


def test_accessory_lane_warning_emitted_when_missing() -> None:
    controller = SingleAgentController()
    controller.set_follow_up_route(FollowUpRoute.FULL_PIPELINE)
    hooks = _SingleAgentToolHooks(controller)
    hooks._accessory_lane_requirements = {"web", "market"}  # type: ignore[attr-defined]
    hooks._accessory_lane_hits.clear()  # type: ignore[attr-defined]
    ctx = {"session_id": "sess-accessory"}

    async def _run():
        async for _ in hooks.on_flow_start(ctx):
            pass
        return await _collect_async(
            hooks.after_event(
                ctx,
                {"event": "workflow_complete", "data": {}},
            )
        )

    events = asyncio.run(_run())
    assert any(evt.get("event") == "status" and (evt.get("data") or {}).get("step") == "accessory_lane_warning" for evt in events)


def test_accessory_lane_warning_suppressed_when_lanes_ready() -> None:
    controller = SingleAgentController()
    controller.set_follow_up_route(FollowUpRoute.FULL_PIPELINE)
    hooks = _SingleAgentToolHooks(controller)
    hooks._accessory_lane_requirements = {"web", "market"}  # type: ignore[attr-defined]
    hooks._accessory_lane_hits.clear()  # type: ignore[attr-defined]
    ctx = {"session_id": "sess-accessory-ok"}

    async def _run():
        async for _ in hooks.on_flow_start(ctx):
            pass
        await _collect_async(
            hooks.after_event(
                ctx,
                {"event": "web_ready", "data": {"lane": "web"}},
            )
        )
        await _collect_async(
            hooks.after_event(
                ctx,
                {"event": "stock_ready", "data": {"lane": "market"}},
            )
        )
        return await _collect_async(
            hooks.after_event(
                ctx,
                {"event": "workflow_complete", "data": {}},
            )
        )

    events = asyncio.run(_run())
    assert not any(evt.get("event") == "status" and (evt.get("data") or {}).get("step") == "accessory_lane_warning" for evt in events)


def test_forward_with_hooks_emits_session_started_once() -> None:
    controller = SingleAgentController()
    hooks = _SingleAgentToolHooks(controller)

    async def _stream():
        yield {"event": "workflow_complete", "data": {}}

    async def _run():
        results: List[Dict[str, Any]] = []
        async for event in controller._forward_with_hooks(
            _stream(),
            hooks,
            session_id="sess-synthetic",
            ensure_session_event=True,
        ):
            results.append(event)
        return results

    events = asyncio.run(_run())
    assert events[0]["event"] == "session_started"
    assert events[0]["data"]["session_id"] == "sess-synthetic"
    workflow_events = [evt for evt in events if evt.get("event") == "workflow_complete"]
    assert workflow_events
    assert workflow_events[0]["data"]["session_id"] == "sess-synthetic"


def test_session_metadata_attached_to_analysis_ready() -> None:
    controller = SingleAgentController()
    hooks = _SingleAgentToolHooks(controller)

    async def _stream():
        yield {"event": "analysis_ready", "data": {"lane": "analysis"}}
        yield {"event": "workflow_complete", "data": {}}

    async def _run():
        collector: List[Dict[str, Any]] = []
        async for event in controller._forward_with_hooks(
            _stream(),
            hooks,
            session_id="sess-analysis",
            ensure_session_event=True,
        ):
            collector.append(event)
        return collector

    events = asyncio.run(_run())
    analysis_events = [evt for evt in events if evt.get("event") == "analysis_ready"]
    assert analysis_events
    assert analysis_events[0]["data"]["session_id"] == "sess-analysis"
