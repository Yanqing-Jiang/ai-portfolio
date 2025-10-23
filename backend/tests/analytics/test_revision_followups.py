import pytest
from typing import Optional
from types import SimpleNamespace

from analytics.core.session_state import SessionStateSnapshot
from analytics.routing import FollowUpRoute
from analytics.routing.follow_up_classifier import FollowUpClassifier

from backend.analytics.flows import planner_executor
from backend.analytics.flows.planner.revision import derive_revision_targets
from backend.analytics.flows.multi_agent import _derive_tasks


def _make_context(
    intent_key: Optional[str] = None,
    follow_up: FollowUpRoute = FollowUpRoute.FULL_PIPELINE,
    *,
    with_snapshot: bool = False,
    hint_active: bool = False,
):
    intent = SimpleNamespace(intent_key=intent_key) if intent_key else None
    return SimpleNamespace(
        revision_targets=set(),
        follow_up_route=follow_up,
        intent=intent,
        revision_snapshot={"id": "snapshot"} if with_snapshot else None,
        revision_hint_active=hint_active,
    )


def test_intent_lane_map_recognizes_market_share():
    ctx = _make_context('market_share_single', with_snapshot=True, hint_active=True)
    targets = derive_revision_targets(ctx, intent_lane_map=planner_executor._INTENT_LANE_HINTS)
    assert targets == {'sql', 'chart', 'analysis'}


def test_intent_lane_map_adds_web_for_news():
    ctx = _make_context('breaking_news_flash', with_snapshot=True, hint_active=True)
    targets = derive_revision_targets(ctx, intent_lane_map=planner_executor._INTENT_LANE_HINTS)
    assert 'web' in targets


def test_intent_lane_map_requires_hint():
    ctx = _make_context('market_share_single', with_snapshot=True, hint_active=False)
    targets = derive_revision_targets(ctx, intent_lane_map=planner_executor._INTENT_LANE_HINTS)
    assert targets == set()


def test_multi_agent_guardrail_reuses_completed_web_lane():
    planner_ctx = {
        'analysis_revision': None,
        'tickers': ['NVDA'],
        'result': None,
    }
    sql_ctx = {
        'status': 'success',
        'row_count': 20,
        'attempts': [{'attempt': 1, 'status': 'success'}],
    }
    analysis_ctx = {'final': 'analysis ready'}
    chart_ctx = {'spec_summary': 'chart ready'}
    market_ctx = {}
    plan = _derive_tasks(
        planner_ctx,
        sql_ctx,
        analysis_ctx,
        chart_ctx,
        market_ctx,
        'latest market news',
        web_ctx={'summary': 'cached'},
        revision_completed=['web'],
    )
    status_by_name = {step.name: step.status for step in plan.steps}
    reason_by_name = {step.name: step.reason for step in plan.steps}
    assert status_by_name.get('web_research') == 'reuse'
    assert reason_by_name.get('web_research') in {'revision_completed', 'revision_guardrail'}


def test_revision_targets_skip_without_snapshot():
    classifier = FollowUpClassifier()
    assert classifier.detect_revision_targets("market share analysis", snapshot=None) == set()


def test_revision_targets_filter_by_snapshot_lanes():
    classifier = FollowUpClassifier()
    snapshot = SessionStateSnapshot(session_id="test-session")
    snapshot.last_sql = "SELECT 1"
    snapshot.last_analysis = "Some summary"
    analytics_cache = {
        "artifacts": {
            "market": {"snapshot": {"tickers": ["QCOM"]}},
            "analysis": {"analysis_text": "Some summary"},
            "sql_generation": {"sql": "SELECT 1"},
        }
    }
    snapshot.tool_cache["analytics"] = analytics_cache
    lanes = classifier.detect_revision_targets("market share analysis", snapshot)
    assert lanes == {"analysis", "market"}
