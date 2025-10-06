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
