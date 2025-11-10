# --- Analytics Function/Class Map ---
# Function: _normalize_targets
#   Role: Handles normalize targets logic for analytics.flows.revision_directive.
#   Called from: Internal to analytics.flows.revision_directive
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.revision_directive from duplicating normalize targets behavior across flows.
# Class: RevisionDirective
#   Role: Lightweight container for agentic revision metadata.
#   Called from: analytics.core.session_state, analytics.flows.multi_agent, analytics.flows.planner_executor, analytics.flows.single_agent_tools, +3 more
#   Collaborators: dataclasses.field, analytics.flows.revision_directive._normalize_targets
#   Why: Supports downstream analytics workflows that rely on RevisionDirective.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

from analytics.services.response_search import SearchTopicPlan


def _normalize_targets(targets: Iterable[str]) -> List[str]:
    normalized: Set[str] = set()
    for target in targets or []:
        if not target:
            continue
        normalized.add(str(target).strip().lower())
    return sorted(normalized)


@dataclass
class RevisionDirective:
    """Lightweight container for agentic revision metadata."""

    raw_text: str
    targets: List[str] = field(default_factory=list)
    requested_focus: Optional[str] = None
    chart_patch: Optional[Dict[str, Any]] = None
    mode: str = "manual"
    agentic: bool = False
    search_topics: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_payload(
        cls,
        *,
        raw_text: str,
        targets: Iterable[str],
        requested_focus: Optional[str],
        chart_patch: Optional[Dict[str, Any]],
        agentic: bool = False,
        mode: Optional[str] = None,
        search_topics: Optional[Iterable[Any]] = None,
    ) -> "RevisionDirective":
        normalized_targets = _normalize_targets(targets)
        resolved_mode = mode or ("agentic_revision" if agentic else "manual")
        topic_entries: List[Dict[str, Any]] = []
        for topic in search_topics or []:
            if isinstance(topic, SearchTopicPlan):
                topic_entries.append({"label": topic.label, "query": topic.query, "reason": topic.reason})
            elif isinstance(topic, dict):
                query_value = str(topic.get("query") or topic.get("label") or "").strip()
                if not query_value:
                    continue
                entry = {
                    "label": str(topic.get("label") or query_value).strip(),
                    "query": query_value,
                }
                reason = topic.get("reason")
                if isinstance(reason, str) and reason.strip():
                    entry["reason"] = reason.strip()
                topic_entries.append(entry)
            elif isinstance(topic, str):
                query_value = topic.strip()
                if query_value:
                    topic_entries.append({"label": query_value, "query": query_value})

        return cls(
            raw_text=str(raw_text or ""),
            targets=normalized_targets,
            requested_focus=str(requested_focus).strip() or None if requested_focus else None,
            chart_patch=chart_patch if chart_patch else None,
            mode=resolved_mode,
            agentic=agentic,
            search_topics=topic_entries,
        )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "raw_text": self.raw_text,
            "targets": list(self.targets),
            "mode": self.mode,
            "agentic": self.agentic,
        }
        if self.requested_focus:
            payload["requested_focus"] = self.requested_focus
        if self.chart_patch:
            payload["chart_patch"] = self.chart_patch
        if self.search_topics:
            payload["search_topics"] = [dict(item) for item in self.search_topics]
        return payload

    def to_event(self, *, session_id: Optional[str] = None) -> Dict[str, Any]:
        event: Dict[str, Any] = {
            "event": "revision_request",
            "data": {
                "lanes": list(self.targets),
                "mode": self.mode,
                "source": "agentic_revision" if self.agentic else "analytics_memory_workflow",
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        }
        if session_id:
            event["data"]["session_id"] = session_id
        if self.requested_focus:
            event["data"]["focus"] = self.requested_focus
        if self.search_topics:
            event["data"]["search_topics"] = [item.get("query") for item in self.search_topics if item.get("query")]
        return event
