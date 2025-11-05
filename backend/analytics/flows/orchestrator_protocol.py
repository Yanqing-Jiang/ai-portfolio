from __future__ import annotations

import abc
from typing import Any, AsyncGenerator, Dict, Iterable, Optional, Protocol, runtime_checkable


@runtime_checkable
class FlowOrchestrator(Protocol):
    """
    Defines the contract between the planner sequencer and concrete flow controllers.

    Implementations (single-agent or supervisor-led multi-agent) supply the actual
    execution strategy for each lane while the sequencer enforces ordering.
    """

    @abc.abstractmethod
    async def run_intent_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute intent classification / clarification before any tool fan-out."""

    @abc.abstractmethod
    async def run_sql_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Produce SQL plan + execution events, including chart synthesis as needed."""

    @abc.abstractmethod
    async def run_web_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Refresh web research artifacts for current revision lanes."""

    @abc.abstractmethod
    async def run_market_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Refresh market / stock lane artifacts."""

    @abc.abstractmethod
    async def run_analysis_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate the final analysis once upstream lanes complete."""

    @abc.abstractmethod
    def pending_lanes(self) -> Iterable[str]:
        """Return lane identifiers still outstanding (for telemetry / guardrails)."""

    @abc.abstractmethod
    def lane_complete(
        self,
        lane: str,
        *,
        success: bool,
        reused: bool = False,
        reason: Optional[str] = None,
    ) -> None:
        """
        Notify the orchestrator that a lane finished. Success indicates whether
        downstream analysis can proceed without retries.
        """

    @abc.abstractmethod
    def event_metadata(self) -> Dict[str, Any]:
        """Expose metadata that should accompany sequencer-produced events."""
