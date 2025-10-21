import sys
from pathlib import Path
import asyncio
import copy
from datetime import datetime
import types

sys.path.append(str(Path(__file__).resolve().parents[2]))

google_stub = sys.modules.setdefault("google", types.ModuleType("google"))
google_stub.__path__ = []
genai_stub = types.ModuleType("google.genai")
genai_types_stub = types.ModuleType("google.genai.types")
setattr(genai_stub, "types", genai_types_stub)
setattr(google_stub, "genai", genai_stub)
sys.modules["google.genai"] = genai_stub
sys.modules["google.genai.types"] = genai_types_stub

from analytics.flows.multi_agent import (
    MultiAgentFlow,
    _derive_tasks,
    _planner_agent,
    _query_agent,
    _market_agent,
    _web_research_agent,
)
from analytics.flows.orchestrator import AgentResult, AgentRunContext
from analytics.routing import FollowUpRoute


def test_multi_agent_plan_dependencies():
    flow = MultiAgentFlow()
    plan_map = {task.name: task for task in flow._base_plan}
    assert plan_map["chart_phase"].depends_on == ("query_phase",)
    assert plan_map["market_phase"].depends_on == ("planner_phase",)
    assert plan_map["web_research_phase"].depends_on == ("planner_phase",)
    assert set(plan_map["analyst_phase"].depends_on) == {
        "chart_phase",
        "market_phase",
        "web_research_phase",
    }


class DummyPlannerFlow:
    async def events(self, query: str, session_id: str = None):
        yield {"event": "session_started", "data": {"session_id": session_id or "sess-123"}}
        yield {
            "event": "intent_detection_complete",
            "data": {
                "intent_key": "test_intent",
                "confidence": 0.92,
                "slots_detected": {"company": "NVDA"},
            },
        }
        yield {
            "event": "plan_built",
            "data": {"comparison": "vs_avg", "granularity": "annual"},
        }
        yield {
            "event": "web_search",
            "data": {
                "web_context": {
                    "summary": "NVIDIA guidance commentary",
                    "snippets": [{"title": "Headline"}],
                }
            },
        }
        yield {
            "event": "sql_compiled",
            "data": {
                "template_used": "template_123",
                "sql_length": 42,
                "template_fallback": False,
            },
        }
        yield {
            "event": "sql_generated",
            "data": {
                "sql": "SELECT 1",
                "llm_used": True,
                "template_fallback": False,
            },
        }
        yield {
            "event": "analysis_complete",
            "data": {"analysis": "Done", "analysis_length": 4},
        }
        yield {
            "event": "workflow_complete",
            "data": {"total_elapsed_ms": 100},
        }


def test_accessories_gate_marks_on_criteria_ready():
    flow = MultiAgentFlow()
    flow._prepare_context("NVDA outlook")
    gate = flow._shared_context.get("_runtime", {}).get("accessories_ready")
    assert isinstance(gate, asyncio.Event)
    assert not gate.is_set()
    flow._capture_event({"event": "criteria_ready", "data": {}})
    assert gate.is_set()


def test_multi_agent_flow_handles_web_context(monkeypatch):
    flow = MultiAgentFlow()
    async def fake_orchestration(self, query, session_id):
        self._orchestrated = True
        if False:
            yield None
        return
    monkeypatch.setattr(MultiAgentFlow, "_run_agent_orchestration", fake_orchestration)
    flow._planner = DummyPlannerFlow()
    flow._orchestrated = True  # Skip orchestration for this unit test

    events = []

    async def _collect():
        async for evt in flow.events("NVDA outlook", session_id="session-xyz"):
            events.append(evt)
            if evt.get("event") == "workflow_complete":
                break

    asyncio.run(_collect())

    assert any(evt.get("event") == "web_search" for evt in events)
    assert events[-1]["event"] == "workflow_complete"
    web_context = flow._shared_context.get("web")
    assert web_context is not None
    assert web_context.get("summary") == "NVIDIA guidance commentary"


def test_multi_agent_cohesive_result_payload(monkeypatch):
    flow = MultiAgentFlow()
    flow._prepare_context("AMD market share")
    flow._shared_context["analysis"]["final"] = "TLDR: AMD gains share."
    flow._shared_context["analysis"]["length"] = 24
    flow._shared_context["chart"]["spec"] = {"title": "Share"}
    flow._shared_context["chart"]["spec_id"] = "chart-123"
    flow._shared_context["sql"]["sql"] = "SELECT * FROM market_share"
    flow._shared_context["sql"]["row_count"] = 8
    flow._shared_context["sql"]["sample_data"] = [{"year": 2024, "share": 0.32}]
    flow._shared_context["stock_widget"] = {"symbols": ["NASDAQ:AMD"]}
    flow._shared_context["web"] = {"summary": "Industry roundup"}
    flow._shared_context["tool_manifest"] = [{"name": "stock_tracker"}]
    flow._shared_context["tool_results"] = [{"tool": "stock_tracker", "status": "completed"}]

    async def fake_run(plan, context):
        return {
            "planner_phase": AgentResult(name="planner", output={"bundle": {"query": context.query, "chart_id": "chart-123"}}),
            "chart_phase": AgentResult(name="chart", output={"status": "complete"}),
            "analyst_phase": AgentResult(name="analyst", output={"status": "complete"}),
            "query_phase": AgentResult(name="query", output={"status": "complete"}),
        }

    monkeypatch.setattr(flow._orchestrator, "run", fake_run)

    # _run_agent_orchestration returns an async generator; collect events
    async def collect():
        payloads = []
        async for evt in flow._run_agent_orchestration("AMD market share", session_id="sess-001"):
            payloads.append(evt)
        return payloads

    emitted = asyncio.run(collect())
    cohesive = next(evt for evt in emitted if evt.get("event") == "cohesive_result")
    data = cohesive["data"]
    assert data["analysis"] == "TLDR: AMD gains share."
    assert data["chart_spec"]["title"] == "Share"
    assert data["sql"] == "SELECT * FROM market_share"
    assert data["stock_widget"]["symbols"] == ["NASDAQ:AMD"]
    bundle = data.get("analysis_bundle")
    assert isinstance(bundle, dict)
    assert bundle.get("narrative") == "TLDR: AMD gains share."
    assert bundle.get("sql", {}).get("row_count") == 8
    assert bundle.get("web", {}).get("summary") == "Industry roundup"
    assert "NASDAQ:AMD" in (bundle.get("stock", {}).get("symbols") or [])
    sources = data.get("analysis_sources")
    assert isinstance(sources, dict)
    assert sources["sql"]["lane"] == "sql"
    assert sources["sql"].get("reused") is False
    assert sources["stock"]["lane"] == "stock"
    assert "NASDAQ:AMD" in sources["stock"]["symbols"]
    assert sources["web"]["lane"] == "web"

    stock_ready = next((evt for evt in emitted if evt.get("event") == "stock_ready"), None)
    if stock_ready:
        assert stock_ready["data"]["lane"] == "market"
        assert stock_ready["data"]["parallel_group"] == "multi_supervisor_fanout"
        assert stock_ready["data"]["flow_mode"] == "multi_agent"
        assert stock_ready["data"]["reused"] is False

    web_ready = next((evt for evt in emitted if evt.get("event") == "web_ready"), None)
    if web_ready:
        assert web_ready["data"]["lane"] == "web"
        assert web_ready["data"]["parallel_group"] == "multi_supervisor_fanout"
        assert web_ready["data"]["flow_mode"] == "multi_agent"
        assert web_ready["data"].get("reused", False) is False

    lane_summary = next((evt for evt in emitted if evt.get("event") == "agent_decision"), None)
    assert lane_summary is not None
    lane_data = lane_summary.get("data", {})
    assert lane_data.get("parallel_group") == "multi_supervisor_fanout"
    assert lane_data.get("ts")
    scope = lane_data.get("rerun_scope")
    assert isinstance(scope, dict)
    assert "rerun" in scope and "reuse" in scope


def test_multi_agent_emits_final_answer_when_cannot_cohere(monkeypatch):
    flow = MultiAgentFlow()
    flow._prepare_context("Tell me a joke")
    flow._shared_context["analysis"]["final"] = "Our analytics tools focus on finance. Please ask about markets or company metrics."
    flow._shared_context["analysis"]["length"] = 17
    flow._shared_context["planner"]["tickers"] = []
    flow._shared_context["tool_results"] = [
        {"tool": "web_retriever", "status": "completed", "payload": {"ready": True}}
    ]

    async def fake_run(plan, context):
        return {
            "planner_phase": AgentResult(name="planner", output={}),
            "query_phase": AgentResult(name="query", output={"status": "complete"}),
            "analyst_phase": AgentResult(name="analyst", output={"status": "complete"}),
            "chart_phase": AgentResult(name="chart", output={"status": "skip"}),
            "market_phase": AgentResult(name="market", output={"status": "skip"}),
            "web_research_phase": AgentResult(name="web_research", output={"status": "complete"}),
        }

    monkeypatch.setattr(flow._orchestrator, "run", fake_run)

    async def collect():
        payloads = []
        async for evt in flow._run_agent_orchestration("Tell me a joke", session_id="sess-002"):
            payloads.append(evt)
        return payloads

    emitted = asyncio.run(collect())
    assert any(evt.get("event") == "cohesive_result_error" for evt in emitted)
    final_event = next(evt for evt in emitted if evt.get("event") == "final_answer")
    message = final_event["data"]["message"]
    assert message.startswith("Our analytics tools focus on finance.")
    assert "Pending lanes:" in message
    assert final_event["data"].get("final_answer_only") is True
    assert final_event["data"].get("analysis_available") is True
    assert final_event["data"].get("flow_mode") == "multi_agent"
    missing = set(final_event["data"].get("missing_components", []))
    assert missing == {"sql", "stock", "web"}


def test_multi_agent_chart_revision_plan_skips_web_research():
    planner_ctx = {"tickers": ["NVDA"]}
    sql_ctx = {"status": "success", "row_count": 12}
    analysis_ctx = {}
    chart_ctx = {"spec_summary": {"chart_type": "line"}}
    market_ctx = {}
    plan = _derive_tasks(
        planner_ctx,
        sql_ctx,
        analysis_ctx,
        chart_ctx,
        market_ctx,
        "Please update the chart to a bar view",
        web_ctx={"source": "cache"},
    )
    decisions = {step.name: step.status for step in plan}
    assert decisions["query"] == "skip"
    assert decisions["chart"] == "run"
    assert decisions["analyst"] == "skip"
    assert decisions["market"] == "skip"
    assert decisions["web_research"] == "skip"


def test_multi_agent_chart_revision_final_answer_mentions_reuse():
    flow = MultiAgentFlow()
    flow.set_follow_up_route(FollowUpRoute.REUSE_SQL)
    flow._prepare_context("Reuse snapshot")
    flow._shared_context["sql"]["sql"] = "SELECT symbol, price FROM quotes"
    flow._shared_context["market"]["snapshot"] = {"symbols": [["NASDAQ:NVDA", "NVDA"]]}
    flow._shared_context["web"]["summary"] = "Cached macro commentary."
    flow._shared_context["analysis"]["final"] = "Existing financial analysis stays intact."
    payload = flow._build_final_answer_payload(flow._shared_context["analysis"]["final"])
    assert payload is not None
    assert payload["missing_components"] == []
    message = payload["message"]
    assert "Chart revision applied." in message
    assert "Reused cached datasets for consistency." in message


def test_chart_generated_normalizes_wrapped_spec():
    flow = MultiAgentFlow()
    flow._prepare_context("Normalize chart spec")
    wrapped_spec = {
        "chart_type": "line_multi",
        "chart_spec": {
            "title": {"text": "Market Share"},
            "xAxis": {"type": "category", "data": ["2024 Q1"]},
            "series": [{"name": "Market Share %", "type": "line", "data": [11.9]}],
        },
    }
    event = {"event": "chart_generated", "data": {"chart_spec": wrapped_spec, "chart_type": "line_multi"}}

    flow._capture_event(event)

    stored_spec = flow._shared_context["chart"]["spec"]
    assert isinstance(stored_spec, dict)
    assert stored_spec["series"][0]["data"] == [11.9]
    summary = flow._shared_context["chart"]["spec_summary"]
    assert summary["chart_type"] == "line_multi"
    assert summary["series_count"] == 1
    assert event["data"]["chart_spec"] == stored_spec
    assert "chart_spec_id" in event["data"]


def test_sql_attempts_are_sanitized():
    flow = MultiAgentFlow()
    flow._prepare_context("Sanitize attempts")
    event = {
        "event": "sql_attempts",
        "data": {
            "attempts": [
                {"status": "retry", "window": slice(None, 1200, None)},
            ]
        },
    }

    flow._capture_event(event)

    attempts = flow._shared_context["sql"]["attempts"]
    assert isinstance(attempts, list)
    assert attempts[0]["window"] == {"start": None, "stop": 1200, "step": None}


def test_hedged_accessories_ready_with_seeded_artifacts():
    flow = MultiAgentFlow()
    flow._prepare_context("Accessories reuse")
    flow._shared_context.setdefault("planner", {})["tickers"] = ["NVDA"]
    flow._shared_context["stock_widget"] = {"symbols": ["NASDAQ:NVDA"]}
    flow._shared_context.setdefault("market", {})["source"] = "planner_fanout"
    flow._shared_context["tool_manifest"] = [{"name": "web_retriever"}]
    flow._shared_context["tool_results"] = [
        {
            "tool": "web_retriever",
            "status": "completed",
            "payload": {"ready": True, "summary": "Fan-out context"},
        }
    ]

    assert flow._hedged_accessories_ready() is True


def test_stock_ready_event_carries_source_metadata():
    flow = MultiAgentFlow()
    flow._prepare_context("Stock event source")
    flow._shared_context["stock_widget"] = {"symbols": ["NASDAQ:NVDA"]}
    flow._shared_context.setdefault("market", {})["source"] = "planner_fanout"
    flow._pending_artifact_events.clear()
    flow._maybe_queue_stock_ready()

    assert flow._pending_artifact_events
    stock_event = flow._pending_artifact_events[-1]
    assert stock_event["event"] == "stock_ready"
    assert stock_event["data"]["source"] == "planner_fanout"


def test_multi_agent_supervisor_reuses_planner_fanout():
    flow = MultiAgentFlow()
    flow._prepare_context("NVDA outlook reuse")
    runtime = flow._shared_context["_runtime"]
    runtime["accessories_ready"].set()

    now_iso = datetime.utcnow().isoformat()
    planner_ctx = flow._shared_context["planner"]
    planner_ctx.update({"confidence": 0.88, "tickers": ["NVDA"]})

    sql_ctx = flow._shared_context["sql"]
    sql_ctx.update(
        {
            "status": "success",
            "row_count": 128,
            "sql": "SELECT symbol, close FROM price_history",
            "attempts": [
                {"attempt": 1, "status": "success", "source": "planner_fanout"}
            ],
        }
    )

    analysis_ctx = flow._shared_context["analysis"]
    analysis_ctx["final"] = "Revenue continues to grow with stable margins."
    analysis_ctx["analysis_length"] = len(analysis_ctx["final"])

    chart_ctx = flow._shared_context["chart"]
    chart_ctx.update(
        {
            "spec_summary": {"chart_type": "line", "series_count": 1},
            "spec_id": "chart-abc123",
        }
    )

    market_ctx = flow._shared_context["market"]
    market_ctx.update(
        {
            "snapshot": {
                "symbol": "NVDA",
                "latest_close": 468.12,
                "change_percent": 1.8,
            },
            "tickers": ["NVDA"],
            "source": "planner_fanout",
        }
    )

    web_ctx = flow._shared_context["web"]
    web_ctx.update(
        {
            "snippets": [{"title": "NVDA guidance", "url": "https://example.com"}],
            "query": "nvda outlook reuse",
            "source": "planner_fanout",
        }
    )

    flow._shared_context["stock_widget"] = {
        "symbols": ["NASDAQ:NVDA"],
        "last_close": 468.12,
    }

    flow._shared_context["tool_results"] = [
        {
            "tool": "stock_tracker",
            "status": "completed",
            "payload": {"ready": True},
            "metadata": {"name": "stock_tracker"},
            "elapsed_ms": 1200,
        },
        {
            "tool": "web_retriever",
            "status": "completed",
            "payload": {"ready": True, "snippets": web_ctx["snippets"]},
            "metadata": {"name": "web_retriever"},
            "elapsed_ms": 950,
        },
    ]

    flow._shared_context["tool_receipts"] = {
        "stock_tracker": {"status": "completed", "completed_at": now_iso},
        "web_retriever": {"status": "completed", "completed_at": now_iso},
        "market_question_a": {"status": "completed", "completed_at": now_iso},
        "market_question_b": {"status": "completed", "completed_at": now_iso},
    }
    initial_tool_results = copy.deepcopy(flow._shared_context["tool_results"])

    async def fail_fetch(symbol, client=None):
        raise AssertionError("Planner fan-out cache should prevent market refetch")

    flow._market_fetcher = fail_fetch
    runtime["market_fetcher"] = fail_fetch
    flow._market_client = types.SimpleNamespace(is_configured=True)
    runtime["market_client"] = flow._market_client

    async def orchestrate():
        planner_context = AgentRunContext(
            query="NVDA outlook reuse",
            session_id="sess-multi-agent",
            shared=flow._shared_context,
            dependencies={},
            inputs={},
        )
        planner_result = await _planner_agent(planner_context)
        dependencies = {"planner_phase": planner_result}

        query_context = AgentRunContext(
            query="NVDA outlook reuse",
            session_id="sess-multi-agent",
            shared=flow._shared_context,
            dependencies=dependencies,
            inputs={},
        )
        market_context = AgentRunContext(
            query="NVDA outlook reuse",
            session_id="sess-multi-agent",
            shared=flow._shared_context,
            dependencies=dependencies,
            inputs={},
        )
        web_context_run = AgentRunContext(
            query="NVDA outlook reuse",
            session_id="sess-multi-agent",
            shared=flow._shared_context,
            dependencies=dependencies,
            inputs={},
        )

        query_result = await _query_agent(query_context)
        market_result = await _market_agent(market_context)
        web_result = await _web_research_agent(web_context_run)
        return planner_result, query_result, market_result, web_result

    planner_result, query_result, market_result, web_result = asyncio.run(orchestrate())

    task_status = {task["name"]: task["status"] for task in planner_result.output["tasks"]}
    assert task_status["query"] == "skip"
    assert task_status["market"] == "reuse"
    assert task_status["web_research"] == "skip"
    assert task_status["chart"] == "reuse"
    assert task_status["analyst"] == "reuse"

    assert query_result.output["status"] == "skip"
    assert market_result.output["status"] == "reuse"
    assert market_result.output["refresh"] is False
    assert web_result.output["status"] == "skip"
    assert web_ctx["status"] == "skip"
    assert market_ctx["status"] == "reuse"
    assert flow._shared_context["tool_results"] == initial_tool_results
