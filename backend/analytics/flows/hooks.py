# --- Analytics Function/Class Map ---
# Class: AnalyticsFlowHooks
#   Role: Async hook surface for planner pipeline observers.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner_executor, analytics.flows.single_agent_tools
#   Collaborators: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on AnalyticsFlowHooks.
# Class: NullFlowHooks
#   Role: Default no-op hooks.
#   Called from: analytics.flows.planner_executor
#   Collaborators: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on NullFlowHooks.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional


class AnalyticsFlowHooks:
    """Async hook surface for planner pipeline observers."""

    async def on_flow_start(self, ctx: Any) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}

    async def before_event(self, ctx: Any, event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}

    async def after_event(self, ctx: Any, event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}

    async def on_flow_end(
        self,
        ctx: Any,
        *,
        error: Optional[BaseException] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}


class NullFlowHooks(AnalyticsFlowHooks):
    """Default no-op hooks."""

    pass
