"""Shared tool registry and interfaces for agent-managed flows."""
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSpec:
    """Metadata describing a tool the agent runtime can invoke."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


class AnalyticsTool:
    """Abstract tool contract followed by concrete analytics helpers."""

    def __init__(self, spec: ToolSpec) -> None:
        self.spec = spec

    @property
    def name(self) -> str:
        return self.spec.name

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool asynchronously."""

        raise NotImplementedError


class ToolRegistry:
    """Lightweight lookup for analytics agent tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, AnalyticsTool] = {}
        self._hooks: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[None] | None]] = {}

    def register(self, tool: AnalyticsTool) -> None:
        if tool.name in self._tools:
            logger.warning("Replacing existing tool registration", extra={"tool": tool.name})
        self._tools[tool.name] = tool

    def register_hook(
        self,
        tool_name: str,
        hook: Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[None] | None],
    ) -> None:
        """Optional hook fires after a tool returns for observability."""

        self._hooks[tool_name] = hook

    def get(self, tool_name: str) -> Optional[AnalyticsTool]:
        return self._tools.get(tool_name)

    async def invoke(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.get(tool_name)
        if not tool:
            raise KeyError(f"Tool '{tool_name}' is not registered")
        result = await tool.ainvoke(payload)
        hook = self._hooks.get(tool_name)
        if hook:
            try:
                hook_result = hook(payload, result)
                if inspect.isawaitable(hook_result):
                    await hook_result
            except Exception:  # pragma: no cover - guard hooks
                logger.exception("Tool hook failed", extra={"tool": tool_name})
        return result

    def list_specs(self) -> Dict[str, ToolSpec]:
        return {name: tool.spec for name, tool in self._tools.items()}
