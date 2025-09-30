from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .session_state import (
    SessionStateSnapshot,
    SessionStateRepository,
    get_session_state_repository,
)
from .telemetry import memory_gate_decision as log_memory_gate_decision

ToolName = Literal[
    "sql_planner",
    "chart_builder",
    "web_retriever",
    "stock_tracker",
    "narrative_synthesizer",
]


class ToolDirective(BaseModel):
    """Directive describing how a tool should execute for this turn."""

    enabled: bool = True
    reuse_previous: bool = False
    reason: Optional[str] = None
    parallel_group: Optional[str] = None


class MemoryGateDecision(BaseModel):
    """Decision payload emitted by MemoryGate."""

    session_id: str
    policy: Literal["cold_start", "reuse", "refresh"]
    reasons: List[str] = Field(default_factory=list)
    reuse_sql: bool = False
    reuse_chart: bool = False
    reuse_analysis: bool = False
    tool_directives: Dict[ToolName, ToolDirective] = Field(default_factory=dict)
    state: SessionStateSnapshot

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "abc123",
                    "policy": "cold_start",
                    "reasons": ["No existing session state"],
                    "reuse_sql": False,
                    "tool_directives": {
                        "sql_planner": {"enabled": True, "parallel_group": "primary"}
                    },
                }
            ]
        }
    }


class MemoryGate:
    """MemoryGate orchestrates session policy decisions before execution."""

    def __init__(self, repository: Optional[SessionStateRepository] = None) -> None:
        self.repository = repository or get_session_state_repository()

    async def evaluate(
        self,
        *,
        session_id: str,
        query: str,
        flow_label: str,
    ) -> MemoryGateDecision:
        snapshot = await self.repository.load(session_id)
        if snapshot is None:
            snapshot = SessionStateSnapshot(session_id=session_id)
            reasons: List[str] = ["No existing session state"]
            policy: Literal["cold_start", "reuse", "refresh"] = "cold_start"
        else:
            reasons = []
            policy = "refresh"

        directives: Dict[ToolName, ToolDirective] = {}

        if snapshot.last_query:
            similarity = _similarity(query, snapshot.last_query)
            if similarity >= 0.9:
                policy = "reuse"
                reasons.append(
                    f"Detected high similarity to previous query (score={similarity:.2f})"
                )
            elif similarity >= 0.7:
                reasons.append(
                    f"Partial similarity to previous query (score={similarity:.2f}); refreshing tools"
                )
            else:
                reasons.append(
                    f"Query diverged from previous intent (score={similarity:.2f}); scheduling fresh run"
                )
        else:
            reasons.append("New conversation turn without prior context")

        reuse_sql = policy == "reuse" and bool(snapshot.last_sql)
        reuse_chart = policy == "reuse" and bool(snapshot.last_chart_spec)
        reuse_analysis = policy == "reuse" and bool(snapshot.last_analysis)

        directives["sql_planner"] = ToolDirective(
            enabled=not reuse_sql,
            reuse_previous=reuse_sql,
            reason="Reusing prior SQL" if reuse_sql else "Generating new SQL",
            parallel_group="primary",
        )
        directives["chart_builder"] = ToolDirective(
            enabled=not reuse_chart,
            reuse_previous=reuse_chart,
            reason="Reusing cached chart" if reuse_chart else "Building chart",
            parallel_group="visualization",
        )

        should_web_refresh = snapshot.should_trigger_web_refresh(query)
        web_cache_present = bool(snapshot.tool_cache.get("web_retriever"))
        directives["web_retriever"] = ToolDirective(
            enabled=should_web_refresh,
            reuse_previous=not should_web_refresh and web_cache_present,
            reason="Fresh web context" if should_web_refresh else "Cached web results reused",
            parallel_group="web",
        )

        requires_stocks = _requires_stocks(query)
        directives["stock_tracker"] = ToolDirective(
            enabled=requires_stocks,
            reuse_previous=False,
            reason="Query references ticker/price" if requires_stocks else "No stock context detected",
            parallel_group="market",
        )

        directives["narrative_synthesizer"] = ToolDirective(
            enabled=True,
            reuse_previous=reuse_analysis,
            reason="Reusing cached analysis" if reuse_analysis else "Generate updated narrative",
            parallel_group="narrative",
        )

        decision = MemoryGateDecision(
            session_id=session_id,
            policy=policy,
            reasons=reasons,
            reuse_sql=reuse_sql,
            reuse_chart=reuse_chart,
            reuse_analysis=reuse_analysis,
            tool_directives=directives,
            state=snapshot,
        )

        snapshot.routing["last_decision"] = decision.model_dump(
            exclude={"state"},
        )
        await self.repository.save(snapshot)

        log_memory_gate_decision(
            session_id=session_id,
            flow=flow_label,
            decision=policy,
            reasons=reasons,
            reuse_sql=reuse_sql,
            reuse_chart=reuse_chart,
            reuse_analysis=reuse_analysis,
            tool_directives={
                name: directive.model_dump()
                for name, directive in directives.items()
            },
        )

        return decision


def _similarity(new_query: str, previous_query: str) -> float:
    from difflib import SequenceMatcher

    return SequenceMatcher(None, new_query.lower(), previous_query.lower()).ratio()


def _requires_stocks(query: str) -> bool:
    lowered = query.lower()
    return any(
        token in lowered
        for token in ["stock", "price", "ticker", "share", "market cap", "nasdaq", "nyse"]
    )
