import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, BACKEND_ROOT):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

import analytics.core.clarify as clarify_module
import pytest
from types import SimpleNamespace

from analytics.flows import planner_executor
from analytics.core import events as events_module


class DummyUnifiedClient:
    async def simple_completion(self, *_, **__):
        return ("SELECT 1 AS revenue", "resp-1")


class FakeChartPlan:
    chart_type = "line"
    series = [{"name": "Revenue"}]

    def dict(self):
        return {"chart_type": self.chart_type, "series": self.series}


async def _run_planner_with_patches(monkeypatch, fetch_impl):
    fake_configs = SimpleNamespace(
        database={"query_defaults": {"max_limit": 5000}},
        charts={},
        metrics={"metrics": {}},
        queries={"query_patterns": {"market_share_all": {"name": "Market Share Template"}}},
        companies={"companies": {"semiconductor": []}},
    )
    monkeypatch.setattr(planner_executor, "CONFIGS", fake_configs, raising=False)

    intent_stub = SimpleNamespace(
        intent_key="market_share_all",
        confidence=0.92,
        slots_detected={"company": "NVDA"},
        clarifications=[],
    )

    def fake_detect_intent(query, configs_dict, session_id=None):
        intent_stub.slots_detected["original_query"] = query
        return intent_stub

    monkeypatch.setattr(
        planner_executor,
        "detect_intent_with_clarifications",
        fake_detect_intent,
    )
    monkeypatch.setattr(planner_executor, "detect_missing_slots", lambda *args, **kwargs: [])
    monkeypatch.setattr(planner_executor, "compute_required_clarifications", lambda *args, **kwargs: [])

    async def fake_merge_answers(intent, plan, answers, configs_dict):
        return intent, plan, []

    monkeypatch.setattr(planner_executor, "merge_answers", fake_merge_answers)
    monkeypatch.setattr(
        planner_executor,
        "intent_to_sql_criteria",
        lambda intent, configs: SimpleNamespace(dict=lambda: {"filters": intent.slots_detected}),
    )

    plan_stub = SimpleNamespace(
        metrics=["Revenue"],
        derived_metrics=[],
        timeframe=SimpleNamespace(years_back=5),
        granularity="annual",
        comparison=None,
        group_by=["calendar_year"],
    )
    monkeypatch.setattr(planner_executor, "build_query_plan", lambda intent, configs: plan_stub)
    monkeypatch.setattr(
        planner_executor,
        "choose_template",
        lambda intent, plan, configs: {"id": "market_share_template", "name": "Market Share Template"},
    )

    captured_templates = []

    async def fake_build_sql_messages(*, templates=None, **kwargs):
        captured_templates.append(list(templates) if templates is not None else None)
        return [
            {"role": "system", "content": "You are a SQL assistant."},
            {"role": "user", "content": "SELECT statement"},
        ]

    monkeypatch.setattr(planner_executor, "build_sql_messages", fake_build_sql_messages)

    async def fake_execute_sql(sql):
        return [{"calendar_year": 2024, "revenue": 100.0}]

    monkeypatch.setattr(planner_executor, "execute_sql", fake_execute_sql)
    monkeypatch.setattr(planner_executor, "validate_sql", lambda *args, **kwargs: (True, []))
    monkeypatch.setattr(planner_executor, "plan_chart_rule_based", lambda *args, **kwargs: FakeChartPlan())
    monkeypatch.setattr(planner_executor, "build_chart_spec", lambda *args, **kwargs: {})

    async def fake_stream_insights_llm(*args, **kwargs):
        yield "intermediate insight"

    monkeypatch.setattr(planner_executor, "stream_insights_llm", fake_stream_insights_llm)
    monkeypatch.setattr(planner_executor, "summarize", lambda analysis, data: analysis)

    class FakeSessionStore:
        async def cleanup_expired(self):
            return None

    async def fake_get_session_store():
        return FakeSessionStore()

    monkeypatch.setattr(clarify_module, "get_session_store", fake_get_session_store)
    monkeypatch.setattr(planner_executor, "fetch_templates_for_intent", fetch_impl)

    flow = planner_executor.PlannerExecutorFlow()
    flow.unified_client = DummyUnifiedClient()

    events = []
    async for event in flow.events("How is NVDA market share?", session_id="sess-1"):
        events.append(event)
        if event.get("event") == "done":
            break

    return events, captured_templates


@pytest.mark.asyncio
async def test_planner_emits_catalog_trace_event(monkeypatch):
    async def fetch_success(intent, *, query, top_k, store):
        return [
            {"id": "market_share_template", "name": "Market Share Template", "score": 0.93, "source": "yaml"}
        ]

    events, captured_templates = await _run_planner_with_patches(monkeypatch, fetch_success)
    catalog_events = [event for event in events if event.get("event") == "catalog_trace"]
    assert catalog_events, "catalog_trace event should be emitted when templates are available"
    catalog_payload = catalog_events[0]["data"]
    assert catalog_payload["selected_template"] == "market_share_template"
    assert catalog_payload["templates"][0]["id"] == "market_share_template"
    assert captured_templates and captured_templates[0][0]["id"] == "market_share_template"


@pytest.mark.asyncio
async def test_planner_catalog_lookup_failure(monkeypatch):
    async def fetch_failure(*args, **kwargs):
        raise RuntimeError("catalog offline")

    events, captured_templates = await _run_planner_with_patches(monkeypatch, fetch_failure)
    assert not any(event.get("event") == "catalog_trace" for event in events)
    assert captured_templates and captured_templates[0] == []
    assert any(event.get("event") == "sql_generated" for event in events)


def test_timed_event_emitter_logs_step(monkeypatch):
    recorded = []

    def fake_step_timing(**kwargs):
        recorded.append(kwargs)

    monkeypatch.setattr(events_module.telemetry, "step_timing", fake_step_timing)

    times = [0.0, 0.1, 0.3]

    def fake_time():
        return times.pop(0)

    monkeypatch.setattr(events_module.time, "time", fake_time)

    emitter = events_module.TimedEventEmitter(session_id="sess-123", flow="planner-executor")
    emitter.start_step("intent_detection")
    elapsed = emitter.end_step("intent_detection")

    assert elapsed in (199, 200)
    assert recorded == [
        {
            "step": "intent_detection",
            "elapsed_ms": elapsed,
            "session_id": "sess-123",
            "flow": "planner-executor",
        }
    ]
