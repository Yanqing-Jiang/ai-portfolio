from datetime import datetime

from analytics.core.session_state import SessionStateSnapshot
from analytics.flows.revision_directive import RevisionDirective


def test_revision_directive_serialization() -> None:
    directive = RevisionDirective.from_payload(
        raw_text="Rewrite to highlight retention",
        targets={"analysis", "chart"},
        requested_focus="Highlight customer retention trends",
        chart_patch={"kind": "update", "field": "color"},
        agentic=True,
        search_topics=[{"label": "Retention metrics", "query": "customer retention drivers"}],
    )

    payload = directive.to_dict()
    assert payload["raw_text"] == "Rewrite to highlight retention"
    assert set(payload["targets"]) == {"analysis", "chart"}
    assert payload["agentic"] is True
    assert payload["mode"] == "agentic_revision"
    assert payload["chart_patch"] == {"kind": "update", "field": "color"}
    assert payload["search_topics"] == [{"label": "Retention metrics", "query": "customer retention drivers"}]

    event = directive.to_event(session_id="session-123")
    assert event["event"] == "revision_request"
    assert event["data"]["mode"] == "agentic_revision"
    assert event["data"]["source"] == "agentic_revision"
    assert event["data"]["session_id"] == "session-123"
    assert set(event["data"]["lanes"]) == {"analysis", "chart"}
    assert event["data"]["search_topics"] == ["customer retention drivers"]
    assert "ts" in event["data"]
    # Timestamp should parse as ISO 8601
    datetime.fromisoformat(event["data"]["ts"])


def test_snapshot_records_revision_directive() -> None:
    snapshot = SessionStateSnapshot(session_id="snap-1")
    directive = RevisionDirective.from_payload(
        raw_text="Refresh analysis",
        targets=["analysis"],
        requested_focus="Mention new KPIs",
        chart_patch=None,
        agentic=True,
        search_topics=["kpi expansion plans"],
    )

    snapshot.record_revision_directive(directive, metadata={"flow": "single-agent"})
    stored = snapshot.last_revision_directive
    assert stored is not None
    assert stored["flow"] == "single-agent"
    assert stored["raw_text"] == "Refresh analysis"
    assert stored["requested_focus"] == "Mention new KPIs"
    assert stored["search_topics"] == [{"label": "kpi expansion plans", "query": "kpi expansion plans"}]
    assert stored["agentic"] is True
    assert "recorded_at" in stored

    snapshot.record_revision_directive(None)
    assert snapshot.last_revision_directive is None
