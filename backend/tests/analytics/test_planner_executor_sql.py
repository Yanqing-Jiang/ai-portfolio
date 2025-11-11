import sys

from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import asyncio
import time

from copy import deepcopy

from types import SimpleNamespace



import pytest



from analytics.flows import planner_executor
from analytics.flows.planner import fanout as planner_fanout
from analytics.flows.tooling import BaseToolAdapter, ToolAdapterResult
from analytics.sql import prompt_builder
from analytics.sql.compiler import compile_sql_from_plan
from analytics.sql.sql_planner import plan_sql_rule_based, choose_template
from analytics.core.state import QueryPlanModel, IntentModel, TimeframeModel
from analytics.core.intent_impl.models import SlotStatusModel
from analytics.core.session_state import get_session_state_repository
from analytics.routing import FollowUpRoute





class DummyUnifiedClient:

    async def simple_completion(self, *args, **kwargs):

        return (

            '`sql\nSELECT 1 AS value\nFROM financials\nWHERE calendar_year = 2024\nLIMIT 10;\n`',

            'resp-123',

        )





async def _noop_async_generator(*args, **kwargs):

    if False:

        yield None





def _fake_chart_plan(*args, **kwargs):

    plan = SimpleNamespace(chart_type="line", series=[{"metric": "value"}])

    plan.dict = lambda: {"series": [{"metric": "value"}]}

    return plan





def _fake_chart_spec(*args, **kwargs):

    return {"meta": {"chartDesign": {"chart_type": "line"}}}





async def _fake_execute_sql(sql: str):
    assert "SELECT" in sql
    return [{"value": 1}]


async def _fake_analysis_stream(*args, **kwargs):
    yield "Revenue grew 12% year over year with margin expansion.\n"
    yield "- Gross margin expanded 210 bps\n- Operating cash flow increased $120M\nRisk: FX volatility could pressure margins.\nConsider monitoring hedges before next guidance."



def _fake_collect_bundle(**kwargs):

    return {}


async def fake_web_search_phase(self, ctx):

    progress = planner_executor.EventEmitter.progress("web_search", "Stub web search")
    progress["data"]["ts"] = "2025-10-13T00:00:00Z"
    progress["data"]["schedule_stage"] = "accessories_post"
    yield progress

    topic_progress = planner_executor.EventEmitter.progress("web_search", "Search topic: STUB")
    topic_progress["data"]["ts"] = "2025-10-13T00:00:05Z"
    topic_progress["data"]["schedule_stage"] = "accessories_post"
    yield topic_progress

    payload = {
        "ready": True,
        "summary": "Stub summary",
        "snippets": [
            {
                "title": "NVIDIA Q2 2025 earnings beat",
                "url": "https://example.com/nvda-q2",
                "display_url": "example.com/nvda-q2",
                "snippet": "NVIDIA reported revenue up 12% with margin expansion.",
                "published_at": "2025-08-15",
            }
        ],
        "latency_stats": {
          "total_ms": 810,
          "p50_ms": 405,
          "max_ms": 490,
          "min_ms": 320,
          "samples": 2,
        },
    }
    planner_executor._set_web_artifact(ctx, payload=payload, topic=None, search_result=None)
    ctx.web_search = SimpleNamespace(
        latency_ms=810,
        topics=[SimpleNamespace(latency_ms=320), SimpleNamespace(latency_ms=490)],
        to_payload=lambda: payload,
    )

    result = planner_executor.EventEmitter.result(
        "web_search",
        {"web_context": payload, "specialist_card": {"type": "web_context", "state": "ready"}},
    )
    result["data"]["ts"] = "2025-10-13T00:00:01Z"
    result["data"]["specialist_card"] = {"type": "web_context", "state": "ready"}
    result["data"]["schedule_stage"] = "accessories_post"
    yield result





class FakeIntent(SimpleNamespace):

    confidence = 0.9

    intent_key = "test_intent"

    slots_detected = {"company": "NVDA"}





class FakePlan(SimpleNamespace):

    granularity = 'annual'

    derived_metrics = []

    comparison = 'vs_avg'

    metrics = ['revenue']

    group_by = ['calendar_year']

    timeframe = SimpleNamespace(years_back=3)

    statistic = None

    limit = 10





async def fake_classification(self, ctx):

    ctx.is_financial_query = True

    yield {"event": "classification_complete", "data": {}}





async def fake_intent_phase(self, ctx):

    ctx.intent = FakeIntent()

    yield {"event": "intent_detected", "data": {"intent_key": "test_intent"}}





async def fake_clarification_phase(self, ctx):

    yield {"event": "clarification_complete", "data": {"rounds": 0, "missing_slots": []}}





async def fake_plan_phase(self, ctx):

    ctx.plan = FakePlan()

    ctx.provisional_plan = ctx.plan

    ctx.template = {"id": "template_123"}

    ctx.candidate_templates = [{"id": "template_123"}]

    ctx.selected_template_id = "template_123"

    yield {"event": "plan_ready", "data": {}}





def _setup_planner_flow(monkeypatch):

    flow = planner_executor.PlannerExecutorFlow()

    flow.unified_client = DummyUnifiedClient()

    monkeypatch.setattr(planner_executor, '_classification_phase', fake_classification)

    monkeypatch.setattr(planner_executor, '_intent_phase', fake_intent_phase)

    monkeypatch.setattr(planner_executor, '_clarification_phase', fake_clarification_phase)

    monkeypatch.setattr(planner_executor, '_plan_phase', fake_plan_phase)

    monkeypatch.setattr(

        planner_executor,

        'run_tool_parallelism',

        lambda ctx, adapters=(), concurrency_override=None: _noop_async_generator(),

    )

    monkeypatch.setattr(planner_executor, 'get_default_tool_adapters', lambda: [])

    monkeypatch.setattr(planner_executor, 'plan_chart_rule_based', _fake_chart_plan)
    monkeypatch.setattr(planner_executor, 'build_chart_spec', _fake_chart_spec)
    monkeypatch.setattr(planner_executor, 'execute_sql', _fake_execute_sql)
    monkeypatch.setattr(planner_executor, 'collect_tool_bundle', _fake_collect_bundle)
    monkeypatch.setattr(planner_executor, 'stream_insights_llm', _fake_analysis_stream)
    monkeypatch.setattr(planner_executor.PlannerPipeline, '_web_search_phase', fake_web_search_phase)
    monkeypatch.setattr(planner_executor, '_validate_sql', lambda sql: (True, [], 0))
    return flow




def _collect_events(flow):

    async def _run_flow():

        events = []

        async for event in flow.events('NVDA revenue trend', session_id='session-test'):

            events.append(event)

            if event.get('event') == 'workflow_complete':

                break

        return events



    return asyncio.run(_run_flow())





def _sanitize_events(events):

    sanitized = []

    for event in events:

        data = event.get("data") or {}

        entry = {"event": event.get("event")}

        step = event.get("step")

        if step:

            entry["step"] = step

        stage = data.get("schedule_stage") or data.get("stage")

        if stage:

            entry["stage"] = stage

        if "tool" in data:

            entry["tool"] = data["tool"]

        if "chart_type" in data:

            entry["chart_type"] = data["chart_type"]

        if "template_used" in data:

            entry["template_used"] = data["template_used"]

        if "sql_length" in data:
            entry["sql_length"] = data["sql_length"]
        if "analysis_length" in data:
            entry["analysis_length"] = data["analysis_length"]
        card = data.get("specialist_card")
        if isinstance(card, dict):
            entry["card"] = card.get("type")
            entry["card_state"] = card.get("state")
        analysis_block = data.get("analysis")
        if isinstance(analysis_block, dict):
            if "analysis_length" in analysis_block:
                entry["analysis_length"] = analysis_block["analysis_length"]
        banner = data.get("banner")
        if isinstance(banner, dict):
            entry["banner_route"] = banner.get("route")
        sanitized.append(entry)
    return sanitized



def test_ingest_tool_event_emits_stock_ready_lane(monkeypatch):
    pipeline = planner_executor.PlannerPipeline(flow_mode=planner_executor.FlowMode.SINGLE_AGENT)
    ctx = planner_executor.PlannerPhaseContext(
        query="Concurrent lanes",
        session_id="ctx-stock",
        workflow_start=time.time(),
        timed_emitter=planner_executor.TimedEventEmitter(session_id="ctx-stock", flow="test"),
        flow_mode=planner_executor.FlowMode.SINGLE_AGENT,
        parallelism_enabled=True,
    )
    payload = {
        "stock_widget": {
            "symbols": [["NASDAQ:NVDA", "NVDA"]],
            "generated_at": "2025-10-20T00:00:00Z",
        },
    }
    event = {
        "event": "tool_parallel_result",
        "data": {
            "tool": "stock_tracker",
            "status": "completed",
            "payload": payload,
            "completed_at": "2025-10-20T00:00:01Z",
            "parallel_group": "tool_fanout",
            "schedule_stage": "hedged_accessories",
        },
    }

    derived_events = pipeline._ingest_tool_event(ctx, event)
    stock_ready = next((evt for evt in derived_events if evt.get("event") == "stock_ready"), None)
    assert stock_ready is not None, "Expected stock_ready event from accessory ingestion"
    stock_data = stock_ready["data"]
    assert stock_data.get("lane") == "market"
    assert stock_data.get("reused") is False
    assert ctx.stock_ready_emitted is True
    assert ctx.tool_parallel_results and ctx.tool_parallel_results[0].get("tool") == "stock_tracker"

    # Second ingestion with the same payload should not emit a duplicate ready event
    duplicate_events = pipeline._ingest_tool_event(ctx, event)
    assert all(evt.get("event") != "stock_ready" for evt in duplicate_events)


def test_ingest_tool_event_emits_web_ready_lane():
    pipeline = planner_executor.PlannerPipeline(flow_mode=planner_executor.FlowMode.SINGLE_AGENT)
    ctx = planner_executor.PlannerPhaseContext(
        query="Concurrent lanes",
        session_id="ctx-web",
        workflow_start=time.time(),
        timed_emitter=planner_executor.TimedEventEmitter(session_id="ctx-web", flow="test"),
        flow_mode=planner_executor.FlowMode.SINGLE_AGENT,
        parallelism_enabled=True,
    )
    payload = {
        "ready": True,
        "summary": "Stubbed market commentary",
        "snippets": [{"title": "NVDA report", "snippet": "Revenue up year over year."}],
    }
    event = {
        "event": "tool_parallel_result",
        "data": {
            "tool": "web_retriever",
            "status": "completed",
            "payload": payload,
            "completed_at": "2025-10-20T00:00:02Z",
            "parallel_group": "tool_fanout",
            "schedule_stage": "hedged_accessories",
        },
    }

    derived_events = pipeline._ingest_tool_event(ctx, event)
    web_ready = next((evt for evt in derived_events if evt.get("event") == "web_ready"), None)
    assert web_ready is not None, "Expected web_ready event from accessory ingestion"
    web_data = web_ready["data"]
    assert web_data.get("lane") == "web"
    assert web_data.get("reused") is False
    assert ctx.web_ready_emitted is True
    assert ctx.tool_parallel_results and ctx.tool_parallel_results[0].get("tool", "").startswith("web_retriever")


def test_agent_tool_events_emitted_for_parallel_payload():
    pipeline = planner_executor.PlannerPipeline(flow_mode=planner_executor.FlowMode.SINGLE_AGENT)
    ctx = planner_executor.PlannerPhaseContext(
        query="Agent lanes",
        session_id="ctx-agent-web",
        workflow_start=time.time(),
        timed_emitter=planner_executor.TimedEventEmitter(session_id="ctx-agent-web", flow="test"),
        flow_mode=planner_executor.FlowMode.SINGLE_AGENT,
        parallelism_enabled=True,
    )
    ctx.agentic_revision_mode = True
    event = {
        "event": "tool_parallel_result",
        "data": {
            "tool": "web_retriever",
            "status": "completed",
            "payload": {"summary": "cached insights", "ready": True},
            "metadata": {"question_id": "web-q1"},
            "lane": "web",
            "parallel_group": "single_agent_web",
            "attempt": 1,
            "reused": True,
        },
    }
    start_event = pipeline._build_agent_tool_event_from_payload(ctx, event, status="start")
    complete_event = pipeline._build_agent_tool_event_from_payload(ctx, event, status="completed")
    assert start_event is not None
    assert complete_event is not None
    assert start_event["event"] == "agent_tool_call"
    assert complete_event["event"] == "agent_tool_complete"
    assert complete_event["data"]["result"]["summary"] == "cached insights"
    assert complete_event["data"]["lane"] == "web"


@pytest.mark.asyncio
async def test_tool_parallel_manifest_emits_agent_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = _setup_planner_flow(monkeypatch)
    ctx = await flow.initialize_context("NVDA follow-up", session_id="session-agent-manifest")
    ctx.agentic_revision_mode = True
    manifest_event = {
        "event": "tool_parallel_start",
        "data": {
            "parallel_group": "tool_fanout",
            "tools": [
                {"name": "web_retriever", "display_name": "Web Search - NVDA", "summary": "Queued NVDA SERP refresh"},
                {"name": "stock_tracker", "display_name": "Market Watch", "summary": "Refreshing NVDA widget"},
            ],
        },
    }
    agent_events = flow._build_agent_tool_events_from_manifest(ctx, manifest_event)
    assert len(agent_events) == 2
    assert all(evt["event"] == "agent_tool_call" for evt in agent_events)
    reasoning = ctx.revision_reasoning
    assert "web_retriever" in reasoning
    assert reasoning["web_retriever"]["summary"] == "Queued NVDA SERP refresh"
    assert reasoning["stock_tracker"]["lane"] == "market"


def test_concurrent_lanes_emit_before_sql(monkeypatch):
    flow = _setup_planner_flow(monkeypatch)
    flow.flow_mode = planner_executor.FlowMode.SINGLE_AGENT
    flow.parallelism_enabled = True

    async def _parallelism(ctx, adapters=(), concurrency_override=None):
        yield {
            "event": "tool_parallel_result",
            "data": {
                "tool": "stock_tracker",
                "status": "completed",
                "payload": {
                    "stock_widget": {"symbols": [["NASDAQ:NVDA", "NVDA"]]},
                },
                "completed_at": "2025-10-20T00:00:01Z",
                "parallel_group": "tool_fanout",
                "schedule_stage": "hedged_accessories",
            },
        }
        yield {
            "event": "tool_parallel_result",
            "data": {
                "tool": "web_retriever",
                "status": "completed",
                "payload": {
                    "ready": True,
                    "summary": "Stubbed commentary",
                    "snippets": [],
                },
                "completed_at": "2025-10-20T00:00:02Z",
                "parallel_group": "tool_fanout",
                "schedule_stage": "hedged_accessories",
            },
        }

    monkeypatch.setattr(planner_executor, 'run_tool_parallelism', _parallelism)

    events = _collect_events(flow)
    lane_events = [evt["event"] for evt in events if evt.get("event") in {"stock_ready", "web_ready", "sql_ready"}]
    assert "stock_ready" in lane_events
    assert "web_ready" in lane_events
    assert "sql_ready" in lane_events
    assert lane_events.index("stock_ready") < lane_events.index("sql_ready")
    assert lane_events.index("web_ready") < lane_events.index("sql_ready")


@pytest.mark.asyncio
async def test_planner_fanout_package_smoke(monkeypatch):
    pipeline = planner_executor.PlannerPipeline(flow_mode=planner_executor.FlowMode.SINGLE_AGENT)
    ctx = planner_executor.PlannerPhaseContext(
        query="Adapter fan-out smoke",
        session_id="ctx-fanout",
        workflow_start=time.time(),
        timed_emitter=planner_executor.TimedEventEmitter(session_id="ctx-fanout", flow="test"),
        flow_mode=planner_executor.FlowMode.SINGLE_AGENT,
        parallelism_enabled=True,
    )

    async def _fake_parallelism(ctx, adapters=(), concurrency_override=None):
        yield {
            "event": "tool_parallel_result",
            "data": {
                "tool": "stock_tracker",
                "status": "completed",
                "payload": {
                    "stock_widget": {"symbols": [["NASDAQ:NVDA", "NVDA"]]},
                    "from_cache": False,
                },
                "parallel_group": "tool_fanout",
                "schedule_stage": "hedged_accessories",
                "completed_at": "2025-10-21T12:00:00Z",
            },
        }

    monkeypatch.setattr(planner_fanout, "run_tool_parallelism", _fake_parallelism)

    runtime = planner_fanout.start_tool_parallelism(
        ctx,
        ingest_tool_event=pipeline._ingest_tool_event,
        adapters=None,
        concurrency_override=None,
    )

    observed = []
    sentinel = None
    while sentinel is None:
        item = await asyncio.wait_for(runtime.queue.get(), timeout=0.1)
        if item is planner_fanout.TOOL_QUEUE_SENTINEL:
            sentinel = item
            break
        observed.append(item)

    assert sentinel is planner_fanout.TOOL_QUEUE_SENTINEL
    runner_exc = runtime.runner.exception() if runtime.runner else None
    dispatcher_exc = runtime.dispatcher.exception() if runtime.dispatcher else None
    assert runner_exc is None, f"runner failed with {runner_exc}"
    assert dispatcher_exc is None, f"dispatcher failed with {dispatcher_exc}"
    assert any(isinstance(event, dict) and event.get("event") == "tool_parallel_result" for event in observed)

    derived_event = next(
        (event for event in observed if isinstance(event, dict) and event.get("event") == "stock_ready"),
        None,
    )
    assert derived_event is not None
    assert derived_event["data"]["lane"] == "market"
    assert derived_event["data"]["delta"] is True

    await asyncio.wait_for(runtime.close(), timeout=0.1)


def test_limit_sample_rows_caps_rows_to_fifty():
    rows = [{"row": idx} for idx in range(65)]

    limited = planner_executor.limit_sample_rows(rows)

    assert len(limited) == 50
    assert limited[0]["row"] == 0
    assert limited[-1]["row"] == 49


@pytest.mark.asyncio
async def test_stream_with_tool_state_emits_queue_events_during_sql():
    pipeline = planner_executor.PlannerPipeline(flow_mode=planner_executor.FlowMode.SINGLE_AGENT)
    ctx = planner_executor.PlannerPhaseContext(
        query="Delayed accessory lane",
        session_id="ctx-delayed",
        workflow_start=time.time(),
        timed_emitter=planner_executor.TimedEventEmitter(session_id="ctx-delayed", flow="test"),
        flow_mode=planner_executor.FlowMode.SINGLE_AGENT,
        parallelism_enabled=True,
    )

    queue: asyncio.Queue = asyncio.Queue()
    runtime = planner_executor.ToolParallelRuntime(
        runner=None,
        dispatcher=None,
        raw_queue=queue,
        queue=queue,
    )
    tool_state = {"queue": queue, "active": True, "runtime": runtime}

    async def sql_stream():
        yield {
            "event": "progress",
            "data": {"stage": "sql", "step": "compiling"},
        }
        await asyncio.sleep(0.05)
        yield {
            "event": "sql_ready",
            "data": {"stage": "sql"},
        }

    async def emit_accessory():
        await asyncio.sleep(0.01)
        await queue.put(
            {
                "event": "stock_ready",
                "data": {
                    "lane": "market",
                    "payload": {"stock_widget": {"symbols": [["NASDAQ:NVDA", "NVDA"]]}},
                },
            }
        )
        await queue.put(planner_executor._TOOL_QUEUE_SENTINEL)

    producer = asyncio.create_task(emit_accessory())

    events = []
    async for event in pipeline._stream_with_tool_state(sql_stream(), tool_state, ctx):
        events.append(event)

    await producer

    event_names = [evt.get("event") for evt in events]
    assert "stock_ready" in event_names
    assert "sql_ready" in event_names
    assert event_names.index("stock_ready") < event_names.index("sql_ready")
    stock_event = next(evt for evt in events if evt.get("event") == "stock_ready")
    assert stock_event["data"].get("delta") is True


@pytest.mark.asyncio
async def test_tool_parallelism_streams_results_immediately():
    class FastAdapter(BaseToolAdapter):
        name = "market_question_a"
        display_name = "Market Question A"

        async def execute(self, context):
            await asyncio.sleep(0.05)
            return ToolAdapterResult(
                name=self.name,
                status="completed",
                payload={"question_id": "fast", "summary": "fast lane ready"},
                metadata={"alias": self.name},
                fatal=False,
            )

    class SlowAdapter(BaseToolAdapter):
        name = "web_retriever"
        display_name = "Web Retriever"

        async def execute(self, context):
            await asyncio.sleep(0.12)
            return ToolAdapterResult(
                name=self.name,
                status="completed",
                payload={"ready": True, "summary": "slow lane ready"},
                metadata={"alias": self.name},
                fatal=False,
            )

    ctx = planner_executor.PlannerPhaseContext(
        query="stream accessories early",
        session_id="stream-session",
        workflow_start=time.time(),
        timed_emitter=planner_executor.TimedEventEmitter(session_id="stream-session", flow="test"),
        flow_mode=planner_executor.FlowMode.SINGLE_AGENT,
        parallelism_enabled=True,
    )
    ctx.intent = SimpleNamespace(intent_key="market")
    ctx.plan = SimpleNamespace(name="plan")

    events: list[tuple[str, float]] = []
    start = time.perf_counter()
    async for event in planner_executor.run_tool_parallelism(
        ctx,
        adapters=(FastAdapter(), SlowAdapter()),
        concurrency_override=2,
    ):
        if event.get("event") == "tool_parallel_result":
            tool = event["data"]["tool"]
            events.append((tool, time.perf_counter() - start))

    tools = [entry[0] for entry in events]
    assert tools[0] == "market_question_a"
    assert tools[1].startswith("web_retriever")
    # Ensure the fast adapter's result surfaced meaningfully earlier than the slow adapter.
    assert events[1][1] - events[0][1] >= 0.04
    assert len(ctx.tool_parallel_results) == 2
    assert ctx.tool_parallel_results[0]["tool"] == "market_question_a"


def test_stock_revision_targets_emit_without_sql(monkeypatch):
    flow = _setup_planner_flow(monkeypatch)
    flow.flow_mode = planner_executor.FlowMode.SINGLE_AGENT
    flow.parallelism_enabled = True
    flow.set_revision_targets({"stock"})

    async def _parallelism(ctx, adapters=(), concurrency_override=None):
        yield {
            "event": "tool_parallel_result",
            "data": {
                "tool": "stock_tracker",
                "status": "completed",
                "payload": {
                    "stock_widget": {
                        "symbols": [["NASDAQ:AAPL", "AAPL"]],
                        "generated_at": "2025-10-21T18:00:00Z",
                    },
                },
                "completed_at": "2025-10-21T18:00:02Z",
                "parallel_group": "tool_fanout",
                "schedule_stage": "hedged_accessories",
            },
        }

    monkeypatch.setattr(planner_executor, "run_tool_parallelism", _parallelism)

    events = _collect_events(flow)
    event_names = [evt.get("event") for evt in events]

    assert "revision_request" in event_names
    assert "stock_revision_ready" in event_names
    assert "sql_ready" not in event_names
    assert "sql_revision_ready" not in event_names
    stock_index = event_names.index("stock_revision_ready")
    workflow_index = event_names.index("workflow_complete")
    assert stock_index < workflow_index


def test_sql_revision_ready_events_are_renamed(monkeypatch):
    flow = _setup_planner_flow(monkeypatch)
    flow.flow_mode = planner_executor.FlowMode.SINGLE_AGENT
    flow.parallelism_enabled = True
    flow.set_revision_targets({"sql", "chart"})

    events = _collect_events(flow)
    event_names = [evt.get("event") for evt in events]

    assert "sql_revision_ready" in event_names
    assert "chart_revision_ready" in event_names
    assert "sql_ready" not in event_names
    assert "chart_ready" not in event_names
def test_planner_fanout_manifest_contains_accessory_lanes(monkeypatch):
    captured = {}

    def _capture_start(self, ctx, *, adapters=(), concurrency_override=None):
        captured["names"] = [adapter.name for adapter in (adapters or ())]
        queue = asyncio.Queue()
        return planner_executor.ToolParallelRuntime(
            runner=None,
            dispatcher=None,
            raw_queue=queue,
            queue=queue,
        )

    monkeypatch.setattr(planner_executor.PlannerPipeline, "_start_tool_parallelism", _capture_start)
    flow = _setup_planner_flow(monkeypatch)
    flow.flow_mode = planner_executor.FlowMode.SINGLE_AGENT
    flow.parallelism_enabled = True

    async def _run():
        async for event in flow.events("NVDA revenue trend - fanout manifest", session_id="fanout-session"):
            if event.get("event") == "sql_ready":
                break

    asyncio.run(_run())
    assert captured.get("names") == [
        "market_question_a",
        "market_question_b",
        "stock_tracker",
        "web_retriever",
    ]


GOLDEN_EVENTS = [

    {"event": "session_started"},

    {"event": "classification_complete", "stage": "classification"},

    {"event": "intent_detected"},

    {"event": "clarification_complete"},

    {"event": "plan_ready"},

    {"event": "progress", "stage": "sql"},

    {"event": "sql_compiled", "stage": "sql", "template_used": "template_123", "sql_length": 77},

    {"event": "sql_generated", "stage": "sql"},

    {"event": "progress"},

    {"event": "sql_validated", "stage": "sql"},

    {"event": "progress", "stage": "sql"},
    {"event": "execution_stats", "stage": "sql"},
    {"event": "data_retrieved", "stage": "sql"},
    {"event": "sql_ready", "stage": "sql"},

    {"event": "progress", "stage": "chart"},

    {"event": "chart_planned", "stage": "chart", "chart_type": "line"},

    {"event": "chart_generated", "stage": "chart"},

    {"event": "chart_ready", "stage": "chart"},

    {"event": "progress", "stage": "analysis"},
    {"event": "analysis_streaming", "stage": "analysis"},
    {"event": "analysis_streaming", "stage": "analysis"},
    {"event": "analysis_complete", "stage": "analysis", "analysis_length": 217},
    {"event": "progress", "stage": "analysis", "banner_route": "full_pipeline"},

    {"event": "progress", "stage": "accessories_post"},

    {"event": "progress", "stage": "accessories_post"},

    {"event": "result", "stage": "accessories_post", "card": "web_context", "card_state": "ready"},

    {"event": "planner_result"},

    {"event": "workflow_complete", "stage": "analysis"},

]





def test_sql_compilation_emits_template(monkeypatch):

    flow = _setup_planner_flow(monkeypatch)

    events = _collect_events(flow)



    sql_events = [evt for evt in events if evt.get('event') == 'sql_compiled']

    assert sql_events, 'Expected sql_compiled event'

    sql_data = sql_events[0]['data']

    assert sql_data['template_used'] == 'template_123'

    assert sql_data['sql_length'] > 0



    generated = [evt for evt in events if evt.get('event') == 'sql_generated']

    assert generated, 'Expected sql_generated event'



    artifacts = flow.latest_artifacts()

    assert artifacts is not None

    execution = artifacts.sql_execution

    assert execution is not None

    assert execution.dataset == [{"value": 1}]

    assert execution.dataset_preview == [{"value": 1}]





def test_planner_event_stream_golden(monkeypatch):

    flow = _setup_planner_flow(monkeypatch)

    events = _collect_events(flow)

    sanitized = _sanitize_events(events)

    assert sanitized == GOLDEN_EVENTS

    planner_event = next(evt for evt in events if evt.get("event") == "planner_result")
    payload = planner_event.get("data") or {}
    metadata = payload.get("metadata") or {}
    overview = metadata.get("analysis_overview")
    assert overview and overview.get("tldr"), "Expected analysis_overview.tldr in planner_result metadata"
    assert overview.get("key_numbers") and "12% year over year" in overview["key_numbers"][0]
    assert overview.get("risk_watch") and "risk" in overview["risk_watch"][0].lower()
    assert overview.get("next_steps") and "monitoring hedges" in overview["next_steps"][0].lower()
    evidence = overview.get("evidence")
    assert evidence and evidence[0]["source_url"] == "https://example.com/nvda-q2"
    assert "nvidia" in evidence[0].get("title", "").lower()
    assert "confidence" in evidence[0] and 0.0 <= evidence[0]["confidence"] <= 1.0
    assert metadata.get("follow_up_route") == FollowUpRoute.FULL_PIPELINE.value
    schema_meta = metadata.get("schema_clarifier")
    assert schema_meta and "action" in schema_meta
    latency_meta = metadata.get("web_search_latency")
    assert latency_meta and latency_meta.get("p50_ms") == 405 and latency_meta.get("samples") == 2
    guardrail_meta = metadata.get("web_search_guardrail")
    assert guardrail_meta and guardrail_meta.get("status") == "ok"


def test_web_search_latency_guardrail_violation(monkeypatch):
    monkeypatch.setattr(planner_executor, "_DEFAULT_GUARDRAIL_P50", 100)
    monkeypatch.setattr(planner_executor, "_DEFAULT_GUARDRAIL_P95", 200)
    flow = _setup_planner_flow(monkeypatch)
    events = _collect_events(flow)
    planner_event = next(evt for evt in events if evt.get("event") == "planner_result")
    metadata = planner_event.get("data", {}).get("metadata", {})
    guardrail_meta = metadata.get("web_search_guardrail")
    assert guardrail_meta is not None
    assert guardrail_meta["status"] == "violation"
    assert "p50_ms" in guardrail_meta.get("violations", [])
def test_follow_up_route_persisted(monkeypatch):
    repo = get_session_state_repository()
    session_id = "session-follow-up"
    flow = _setup_planner_flow(monkeypatch)
    flow.follow_up_route = FollowUpRoute.REUSE_SQL

    async def _run():
        async for event in flow.events('Follow-up route persisted', session_id=session_id):
            if event.get('event') == 'workflow_complete':
                break

    asyncio.run(_run())
    snapshot = asyncio.run(repo.load(session_id))
    assert snapshot is not None
    metadata = snapshot.tool_cache.get('planner_metadata', {})
    assert metadata.get('follow_up_route') == FollowUpRoute.REUSE_SQL.value
    asyncio.run(repo.delete(session_id))


def test_revision_snapshot_persisted(monkeypatch):
    repo = get_session_state_repository()
    session_id = "session-revision-snapshot"
    flow = _setup_planner_flow(monkeypatch)

    async def _run():
        async for event in flow.events('Revision snapshot persistence', session_id=session_id):
            if event.get('event') == 'workflow_complete':
                break

    asyncio.run(_run())
    snapshot = asyncio.run(repo.load(session_id))
    try:
        assert snapshot is not None
        analytics_cache = snapshot.tool_cache.get('analytics', {})
        revision_snapshot = analytics_cache.get('revision_snapshot')
        assert isinstance(revision_snapshot, dict), "revision_snapshot should be stored in analytics cache"
        assert revision_snapshot.get('intent_signature'), "intent_signature missing from revision snapshot"
        assert revision_snapshot.get('sql'), "sql missing from revision snapshot"
        assert revision_snapshot.get('chart_spec'), "chart_spec missing from revision snapshot"
        assert revision_snapshot.get('data_sample') is None or isinstance(revision_snapshot.get('data_sample'), list)
    finally:
        asyncio.run(repo.delete(session_id))

def test_follow_up_reuses_snapshot_metadata(monkeypatch):
    repo = get_session_state_repository()
    session_id = "session-reuse-metadata"
    flow = _setup_planner_flow(monkeypatch)

    async def _run(query: str):
        collected = []
        async for event in flow.events(query, session_id=session_id):
            collected.append(event)
            if event.get('event') == 'workflow_complete':
                break
        return collected

    asyncio.run(_run('NVDA revenue trend'))
    flow.follow_up_route = FollowUpRoute.REUSE_SQL
    reuse_events = asyncio.run(_run('NVDA revenue trend'))
    try:
        planner_event = next(evt for evt in reuse_events if evt.get('event') == 'planner_result')
        metadata = planner_event.get('data', {}).get('metadata', {})
        reuse_meta = metadata.get('snapshot_reuse') or metadata.get('reuse_snapshot')
        assert reuse_meta, 'Expected snapshot_reuse metadata'
        assert reuse_meta.get('reused_sql') is True
        assert 'snapshot_age_seconds' in reuse_meta
        sql_ready_event = next(evt for evt in reuse_events if evt.get('event') == 'sql_ready')
        assert sql_ready_event['data'].get('reused') is True
        assert 'snapshot_age_seconds' in sql_ready_event['data']
    finally:
        asyncio.run(repo.delete(session_id))


def test_reused_analysis_event_contains_summary_and_reuse_flag():
    timed_emitter = planner_executor.TimedEventEmitter(session_id="session-stock-only", flow="test")
    ctx = planner_executor.PlannerPhaseContext(
        query="Stock follow-up",
        session_id="session-stock-only",
        workflow_start=time.time(),
        timed_emitter=timed_emitter,
        flow_mode=planner_executor.FlowMode.MULTI_AGENT,
        configs={},
    )
    ctx.artifacts.analysis = planner_executor.AnalysisArtifact(
        query="Stock follow-up",
        analysis_text="Reuse the prior analysis narrative.",
        summary="Quick take reuse",
        highlights=["Revenue steady", "Margins consistent"],
        key_numbers=["Revenue: $10B", "YoY Growth: 8%"],
        risk_watch=["FX volatility"],
        next_steps=["Track NVDA hedges"],
        stock_widget={"symbols": [["NASDAQ:NVDA", "NVDA"]]},
        web_context={"summary": "Cached web context"},
        evidence=[
            {
                "source_url": "https://example.com/nvda",
                "title": "NVDA earnings recap",
                "confidence": 0.85,
            }
        ],
    )

    event = planner_executor._build_reused_analysis_event(planner_executor.FlowMode.MULTI_AGENT, ctx)
    assert event is not None
    assert event["event"] == "analysis_complete"
    data = event["data"]
    assert data.get("reused") is True
    assert data.get("flow_mode") == planner_executor.FlowMode.MULTI_AGENT.value
    analysis_payload = data.get("analysis") or {}
    assert analysis_payload.get("analysis") == "Reuse the prior analysis narrative."
    assert analysis_payload.get("analysis_length") == 35
    assert analysis_payload.get("tldr") == "Quick take reuse"
    assert analysis_payload.get("bullets") == ["Revenue steady", "Margins consistent"]
    assert analysis_payload.get("key_numbers") == ["Revenue: $10B", "YoY Growth: 8%"]
    assert analysis_payload.get("risk_watch") == ["FX volatility"]
    assert analysis_payload.get("next_steps") == ["Track NVDA hedges"]
    evidence = analysis_payload.get("evidence")
    assert evidence and evidence[0]["source_url"] == "https://example.com/nvda"


def test_market_share_sql_template_emits_annual_columns():
    intent = IntentModel(intent_key='market_share_single', confidence=0.9, slots_detected={'company': 'NVDA'})
    plan_dict = plan_sql_rule_based(intent)
    plan = QueryPlanModel(**plan_dict)
    template = choose_template(intent, plan)
    sql = compile_sql_from_plan(plan, intent, template=template)

    assert 'calendar_quarter_num' not in sql
    assert 'calendar_year' in sql
    assert 'AND 1=1' not in sql


def test_margin_growth_template_quarterly_includes_quarter_fields():
    intent = IntentModel(
        intent_key='margin_growth_vs_peers',
        confidence=0.9,
        slots_detected={'company': 'NVDA', 'granularity': 'quarterly', 'metric': 'Gross Margin', 'metrics': ['Gross Margin']},
    )
    plan_dict = plan_sql_rule_based(intent)
    plan = QueryPlanModel(**plan_dict)
    template = choose_template(intent, plan)
    sql = compile_sql_from_plan(plan, intent, template=template)
    normalized = " ".join(sql.split())

    assert "calendar_quarter_num" in normalized
    assert "calendar_quarter" in normalized
    assert "calendar_quarter_num IS NOT NULL" in normalized
    assert "OVER (PARTITION BY ticker ORDER BY calendar_year, calendar_quarter_num)" in normalized
    assert "JOIN peer_avg p USING (calendar_year, calendar_quarter_num, calendar_quarter)" in normalized
    assert "ORDER BY calendar_year, calendar_quarter_num" in normalized
    assert "company_operating_margin_change_pp" not in normalized
    assert "peer_avg_operating_margin_change_pp" not in normalized
    assert "company_gross_margin_change_pp" in normalized


def test_margin_growth_template_annual_strips_quarter_fields():
    intent = IntentModel(
        intent_key='margin_growth_vs_peers',
        confidence=0.9,
        slots_detected={'company': 'NVDA', 'metric': 'Gross Margin', 'metrics': ['Gross Margin']},
    )
    plan_dict = plan_sql_rule_based(intent)
    plan_dict['granularity'] = 'annual'
    plan_dict['group_by'] = ['calendar_year']
    plan = QueryPlanModel(**plan_dict)
    template = choose_template(intent, plan)
    sql = compile_sql_from_plan(plan, intent, template=template)
    normalized = " ".join(sql.split())

    assert "calendar_quarter_num" not in normalized
    assert "calendar_quarter" not in normalized
    assert "JOIN peer_avg p USING (calendar_year)" in normalized
    assert "ORDER BY calendar_year" in normalized
    assert "company_operating_margin_change_pp" not in normalized
    assert "peer_avg_operating_margin_change_pp" not in normalized
    assert "company_gross_margin_change_pp" in normalized


def test_margins_template_projects_single_selected_margin():
    intent = IntentModel(
        intent_key='margins_vs_peers',
        confidence=0.9,
        slots_detected={'company': 'NVDA', 'metric': 'Operating Margin', 'metrics': ['Operating Margin']},
    )
    plan_dict = plan_sql_rule_based(intent)
    plan = QueryPlanModel(**plan_dict)
    template = choose_template(intent, plan)
    sql = compile_sql_from_plan(plan, intent, template=template)
    normalized = " ".join(sql.split())

    assert "company_operating_margin" in normalized
    assert "peer_avg_operating_margin" in normalized
    assert "company_gross_margin" not in normalized
    assert "peer_avg_gross_margin" not in normalized


def test_revenue_comparison_template_uses_between_and_custom_tickers():
    timeframe = TimeframeModel(start_year=2021, end_year=2024, granularity='annual')
    intent = IntentModel(
        intent_key='revenue_comparison',
        confidence=0.92,
        slots_detected={
            'tickers': ['AMD', 'NVDA'],
            'company_candidates': ['AMD', 'NVDA'],
            'timeframe': {'start_year': 2021, 'end_year': 2024},
            'granularity': 'annual',
        },
    )
    plan = QueryPlanModel(
        metrics=['Revenue'],
        derived_metrics=[],
        timeframe=timeframe,
        granularity='annual',
        group_by=['calendar_year'],
        limit=500,
    )
    template = choose_template(intent, plan)
    sql = compile_sql_from_plan(plan, intent, template=template)

    assert "calendar_year BETWEEN 2021 AND 2024" in sql
    assert "ticker IN ('AMD','NVDA')" in sql
    assert "calendar_quarter_num" not in sql


def test_prompt_constraints_enforce_annual_without_quarterly_hints():
    plan = QueryPlanModel(metrics=['revenue'], granularity='annual')
    constraints = prompt_builder._render_constraints(plan)
    assert 'aggregate by calendar_year only' in constraints
    assert 'calendar_quarter' not in constraints


def test_auto_fill_missing_slots_defaulted_from_suggestions():
    emitter = planner_executor.TimedEventEmitter()
    ctx = planner_executor.PlannerPhaseContext(
        query="How's Nvidia margin growth compare to industry average?",
        session_id="session-123",
        workflow_start=time.time(),
        timed_emitter=emitter,
    )
    ctx.slot_statuses = {
        "timeframe": SlotStatusModel(status="missing", value=None, reason=None, suggestions=["last_5_years"], allow_custom=False),
        "metric": SlotStatusModel(status="missing", value=None, reason=None, suggestions=["Revenue"], allow_custom=False),
    }
    assumptions: list[str] = []

    remaining = planner_executor._auto_fill_missing_slots(ctx, assumptions)

    assert remaining == []
    assert ctx.slot_statuses["timeframe"].status in {"assumed", "defaulted"}
    assert ctx.slot_statuses["timeframe"].value == "last_5_years"
    assert ctx.slot_statuses["metric"].status in {"assumed", "defaulted"}
    assert ctx.slot_statuses["metric"].value == "Revenue"
    assert any(entry.startswith("Using timeframe: last_5_years") for entry in assumptions)
    assert any(entry.startswith("Using metric") for entry in assumptions)


def test_progress_events_include_thought_ids() -> None:
    flow = planner_executor.PlannerExecutorFlow()
    first = flow._annotate({"event": "progress", "data": {"step": "classification"}})
    second = flow._annotate({"event": "progress", "data": {"step": "classification"}})
    third = flow._annotate({"event": "status", "data": {"step": "classification"}})
    assert first["data"]["thought_id"] == "classification:1"
    assert second["data"]["thought_id"] == "classification:2"
    assert third["data"]["thought_id"] == "classification:3"
    result_event = flow._annotate({"event": "result", "data": {"step": "analysis_generation"}})
    assert "thought_id" not in result_event["data"]
