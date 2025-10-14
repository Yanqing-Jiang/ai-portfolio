import sys

from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import asyncio

from copy import deepcopy

from types import SimpleNamespace



import pytest



from analytics.flows import planner_executor
from analytics.sql.compiler import compile_sql_from_plan
from analytics.sql.sql_planner import plan_sql_rule_based, choose_template
from analytics.core.state import QueryPlanModel, IntentModel
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

    yield {"event": "clarification_complete", "data": {}}





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

    {"event": "progress", "stage": "chart"},

    {"event": "chart_planned", "stage": "chart", "chart_type": "line"},

    {"event": "chart_generated", "stage": "chart"},

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


def test_market_share_sql_template_emits_annual_columns():
    intent = IntentModel(intent_key='market_share_single', confidence=0.9, slots_detected={'company': 'NVDA'})
    plan_dict = plan_sql_rule_based(intent)
    plan = QueryPlanModel(**plan_dict)
    template = choose_template(intent, plan)
    sql = compile_sql_from_plan(plan, intent, template=template)

    assert 'calendar_quarter_num' not in sql
    assert 'calendar_year' in sql
    assert 'AND 1=1' not in sql

