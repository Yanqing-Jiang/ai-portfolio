from __future__ import annotations

import asyncio
import pathlib
import sys
import types
from typing import Any, Dict, Optional

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Provide a stub for google.genai so optional dependency tests can run offline.
google_stub = sys.modules.setdefault("google", types.ModuleType("google"))
genai_stub = types.ModuleType("google.genai")
genai_types_stub = types.ModuleType("google.genai.types")
setattr(genai_stub, "types", genai_types_stub)
setattr(google_stub, "genai", genai_stub)
sys.modules["google.genai"] = genai_stub
sys.modules["google.genai.types"] = genai_types_stub

from analytics.agents.schema_clarifier import ClarifierDecision  # noqa: E402
from analytics.core.intent import IntentModel, OffTopicClassifierSchema  # noqa: E402
from analytics.core.state import QueryPlanModel  # noqa: E402
from analytics.flows import planner_executor  # noqa: E402


def test_classification_phase_populates_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        pipeline = planner_executor.PlannerPipeline()

        async def fake_classify(query: str, *, session_id: str, model: str, reasoning_effort: str):
            return OffTopicClassifierSchema(
                is_financial_query=True,
                confidence=0.92,
                topic_category="financial_analytics",
                polite_decline_message=None,
                suggested_rephrase=None,
            )

        monkeypatch.setattr(planner_executor, "classify_query_async", fake_classify)

        ctx = await pipeline.initialize_context("How is NVDA performing?", session_id="test-session")

        async for _ in pipeline.run_classification(ctx):
            pass

        artifact = ctx.artifacts.classification
        assert artifact is not None
        assert artifact.category == "financial_analytics"
        assert artifact.is_financial is True
        assert artifact.model == "gpt-5-mini-2025-08-07"
        assert artifact.raw.get("topic_category") == "financial_analytics"

    asyncio.run(_run())


def test_pipeline_events_runs_tools_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        pipeline = planner_executor.PlannerPipeline()
        order: list[str] = []

        async def fake_run_classification(ctx):
            order.append("classification")
            ctx.is_financial_query = True
            yield {"event": "classification_complete"}

        async def fake_run_intent(ctx):
            order.append("intent_detection")
            ctx.intent = IntentModel(intent_key="test_intent", confidence=1.0, slots_detected={})
            yield {"event": "intent_complete"}

        async def fake_run_clarification(ctx):
            order.append("clarification")
            yield {"event": "clarification_complete"}

        async def fake_run_plan(ctx):
            order.append("plan_generation")
            ctx.plan = QueryPlanModel(metrics=["revenue"])
            ctx.provisional_plan = ctx.plan
            yield {"event": "plan_complete"}

        async def fake_run_sql(ctx, intent, plan, candidate_templates, selected_template_id):
            order.append("sql_generation")
            ctx.halted = False
            yield {"event": "sql_compiled"}

        async def fake_run_chart(ctx, intent, plan):
            order.append("chart_generation")
            yield {"event": "chart_generated"}

        async def fake_web_search(ctx):
            order.append("web_search")
            yield {"event": "web_search_complete"}

        async def fake_run_analysis(ctx):
            order.append("analysis_generation")
            yield {"event": "analysis_complete"}

        monkeypatch.setattr(pipeline, "run_classification", fake_run_classification)
        monkeypatch.setattr(pipeline, "run_intent", fake_run_intent)
        monkeypatch.setattr(pipeline, "run_clarification", fake_run_clarification)
        monkeypatch.setattr(pipeline, "run_plan", fake_run_plan)
        monkeypatch.setattr(pipeline, "run_sql_pipeline", fake_run_sql)
        monkeypatch.setattr(pipeline, "run_chart_phase", fake_run_chart)
        monkeypatch.setattr(pipeline, "_web_search_phase", fake_web_search)
        monkeypatch.setattr(pipeline, "run_analysis_phase", fake_run_analysis)

        async for _ in pipeline.events("test pipeline ordering"):
            pass

        expected = [
            "classification",
            "intent_detection",
            "clarification",
            "plan_generation",
            "sql_generation",
            "chart_generation",
            "analysis_generation",
        ]

        assert order == expected, f"order={order!r}"

    asyncio.run(_run())


def test_intent_phase_populates_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        pipeline = planner_executor.PlannerPipeline()

        def fake_detect(query: str, configs, session_id=None, **kwargs):
            return IntentModel(
                intent_key="margin_growth_vs_peers",
                confidence=0.77,
                slots_detected={"tickers": ["NVDA"], "granularity": "annual"},
                assumptions=[],
            )

        monkeypatch.setattr(planner_executor, "detect_intent_with_clarifications", fake_detect)
        monkeypatch.setattr(planner_executor, "build_query_plan", lambda intent, configs: QueryPlanModel(metrics=["metric"]))
        monkeypatch.setattr(planner_executor, "choose_template", lambda intent, plan, configs: None)
        monkeypatch.setattr(planner_executor, "SCHEMA_CLARIFIER_ENABLED", False)
        monkeypatch.setattr(planner_executor, "compute_required_clarifications", lambda *args, **kwargs: [])

        ctx = await pipeline.initialize_context("Compare NVDA margins vs peers", session_id="intent-session")

        async for _ in pipeline.run_intent(ctx):
            pass

        artifact = ctx.artifacts.intent
        assert artifact is not None
        assert artifact.intent_key == "margin_growth_vs_peers"
        assert artifact.confidence == pytest.approx(0.77)
        assert artifact.slots.get("tickers") == ["NVDA"]
        assert artifact.clarifications_needed is False

    asyncio.run(_run())


def test_clarification_artifact_records_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        pipeline = planner_executor.PlannerPipeline()
        ctx = await pipeline.initialize_context("Query needing clarification", session_id="clarify-session")
        ctx.intent = IntentModel(intent_key="margin_growth_vs_peers", confidence=0.8, slots_detected={}, assumptions=[])
        ctx.provisional_plan = QueryPlanModel(metrics=["gross_margin"])
        ctx.template = None
        ctx.assumptions = []
        ctx.clarifications = []
        ctx.schema_clarifier_decision = ClarifierDecision(action="not_required", missing_slots=[], slot=None)

        async for _ in pipeline.run_clarification(ctx):
            pass

        artifact = ctx.artifacts.clarification
        assert artifact is not None
        assert artifact.clarifier_action == "not_required"
        assert artifact.resolved is True
        assert artifact.pending == []
        assert artifact.rounds == 0

    asyncio.run(_run())


def test_plan_phase_populates_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        pipeline = planner_executor.PlannerPipeline()
        ctx = await pipeline.initialize_context("Plan query", session_id="plan-session")
        ctx.intent = IntentModel(
            intent_key="margin_growth_vs_peers",
            confidence=0.82,
            slots_detected={"tickers": ["NVDA", "AMD"]},
            assumptions=["assume fiscal year"],
        )
        ctx.provisional_plan = QueryPlanModel(metrics=["gross_margin", "operating_margin"])
        ctx.template = {"id": "template-1", "name": "Margin Template"}
        ctx.assumptions = ["assume fiscal year"]
        ctx.parallelism_enabled = False

        async def fake_fetch(intent, query, top_k, store):
            return [{"id": "cand-1", "name": "Candidate 1"}, {"id": "cand-2", "name": "Candidate 2"}]

        async def fake_tool_parallelism(_ctx):
            if False:
                yield None

        monkeypatch.setattr(planner_executor, "fetch_templates_for_intent", fake_fetch)
        monkeypatch.setattr(planner_executor, "run_tool_parallelism", fake_tool_parallelism)

        async for _ in pipeline.run_plan(ctx):
            pass

        artifact = ctx.artifacts.plan
        assert artifact is not None
        assert artifact.plan is not None
        assert artifact.metrics_count == 2
        assert artifact.candidate_templates
        assert artifact.parallelism_enabled is False
        assert artifact.criteria is not None

    asyncio.run(_run())


def test_sql_pipeline_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeChartPlan:
        def __init__(self):
            self.chart_type = "line_multi"
            self.series = [
                {"id": "gross_margin", "metric": "gross_margin", "axis": "left"},
            ]

        def dict(self) -> Dict[str, Any]:
            return {"series": self.series}

    def fake_build_chart_spec(data, plan_dict, charts_config, intent_key, comparison, statistic=None):
        return {
            "datasets": [
                {"id": "gross_margin", "label": "Gross Margin", "metric": "gross_margin"}
            ],
            "meta": {},
        }

    class FakeSearchResult:
        def __init__(self):
            self.metadata = {"cache_hit": False}

        def to_payload(self) -> Dict[str, Any]:
            return {
                "summary": "Latest industry headlines",
                "snippets": [{"title": "Headline"}],
                "search_id": "search-123",
                "from_cache": False,
            }

    async def fake_perform_search(query: str, session_id: str, context: Optional[str], search_topic: Optional[str]):
        return FakeSearchResult()

    async def fake_stream_insights_llm(*args, **kwargs):
        for chunk in ["First chunk. ", "Second chunk."]:
            yield chunk

    class FakeUnifiedClient:
        async def simple_completion(self, messages, reasoning_effort):
            return ("```sql\nSELECT ticker, metric, calendar_year, period_date, value FROM margins\n```", {})

    async def fake_execute_sql(sql: str):
        return [
            {
                "ticker": "NVDA",
                "metric": "gross_margin",
                "calendar_year": 2023,
                "period_date": "2023-03-31",
                "value": 72.1,
            },
            {
                "ticker": "NVDA",
                "metric": "gross_margin",
                "calendar_year": 2024,
                "period_date": "2024-03-31",
                "value": 70.0,
            },
            {
                "ticker": "AMD",
                "metric": "gross_margin",
                "calendar_year": 2024,
                "period_date": "2024-03-31",
                "value": 46.2,
            },
        ]

    async def _run() -> None:
        pipeline = planner_executor.PlannerPipeline()
        pipeline.unified_client = FakeUnifiedClient()

        monkeypatch.setattr(planner_executor, "_validate_sql", lambda sql: (True, [], 4))
        monkeypatch.setattr(planner_executor, "execute_sql", fake_execute_sql)
        monkeypatch.setattr(
            planner_executor,
            "plan_chart_rule_based",
            lambda data, query, intent_key, statistic=None: FakeChartPlan(),
        )
        monkeypatch.setattr(
            planner_executor,
            "build_chart_spec",
            fake_build_chart_spec,
        )
        monkeypatch.setattr(planner_executor, "has_search_api_key", lambda: True)
        monkeypatch.setattr(planner_executor, "generate_search_topic", lambda query, session_id=None: "margin topic")
        monkeypatch.setattr(planner_executor, "perform_response_search", fake_perform_search)
        monkeypatch.setattr(planner_executor, "collect_tool_bundle", lambda *args, **kwargs: {"stock_widget": {"symbols": ["NVDA"]}})
        monkeypatch.setattr(planner_executor, "stream_insights_llm", fake_stream_insights_llm)

        ctx = await pipeline.initialize_context("SQL query", session_id="sql-session")
        intent = IntentModel(
            intent_key="margin_growth_vs_peers",
            confidence=0.85,
            slots_detected={"tickers": ["NVDA", "AMD"]},
            assumptions=[],
        )
        plan = QueryPlanModel(metrics=["gross_margin"])

        async for _ in pipeline.run_sql_pipeline(
            ctx,
            intent=intent,
            plan=plan,
            candidate_templates=[],
            selected_template_id=None,
        ):
            pass
        ctx.plan = plan

        gen_artifact = ctx.artifacts.sql_generation
        exec_artifact = ctx.artifacts.sql_execution

        assert gen_artifact is not None
        assert gen_artifact.status == "validated"
        assert gen_artifact.sql and "SELECT ticker" in gen_artifact.sql
        assert gen_artifact.attempts

        assert exec_artifact is not None
        assert exec_artifact.status == "success"
        assert exec_artifact.row_count == 3
        assert "ticker" in exec_artifact.columns
        assert exec_artifact.tickers == ["AMD", "NVDA"]
        assert exec_artifact.metrics == ["gross_margin"]
        assert exec_artifact.timeframe["years"]["min"] == 2023
        assert exec_artifact.timeframe["years"]["max"] == 2024
        assert exec_artifact.timeframe["dates"]["start"] == "2023-03-31"
        assert exec_artifact.sample_rows and len(exec_artifact.sample_rows) <= 5

        async for _ in pipeline.run_chart_phase(ctx, intent=intent, plan=plan):
            pass
        chart_artifact = ctx.artifacts.chart
        assert chart_artifact is not None
        assert chart_artifact.chart_type == "line_multi"
        assert chart_artifact.series_count == 1
        assert chart_artifact.datasets_summary[0]["metric"] == "gross_margin"

        async for _ in pipeline._web_search_phase(ctx):
            pass
        web_artifact = ctx.artifacts.web
        assert web_artifact is not None
        assert web_artifact.summary == "Latest industry headlines"
        assert web_artifact.metadata.get("cache_hit") is False

        async for _ in pipeline.run_analysis_phase(ctx):
            pass
        analysis_artifact = ctx.artifacts.analysis
        assert analysis_artifact is not None
        assert analysis_artifact.analysis_text == "First chunk. Second chunk."
        assert len(analysis_artifact.fragments) == 2
        assert analysis_artifact.web_context is not None
        assert analysis_artifact.stock_widget == {"symbols": ["NVDA"]}

        market_artifact = ctx.artifacts.market
        assert market_artifact is not None
        assert market_artifact.tickers == ["NVDA"]

    asyncio.run(_run())
