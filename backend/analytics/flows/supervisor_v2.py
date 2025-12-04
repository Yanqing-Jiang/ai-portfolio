"""
Module: supervisor_v2.py
Purpose: Prototype of "Specialist Pools" pattern - single supervisor with rich-description tools.
Called from: Future analytics workflows once validated
Invokes: analytics.tools.canonical_registry, analytics.flows.planner_executor
Why: Validates if supervisor + deterministic tools can match multi-agent performance with lower latency.

Part of Phase 3 (2-day spike) of the analytics refactor plan.

DECISION GATE:
- If Specialist Pools latency < current multi-agent AND success rate >= 90%: Adopt this pattern
- Otherwise: Proceed with full supervisor + specialists plan

PATTERN SUMMARY:
- Single supervisor agent makes all decisions
- Tools are deterministic functions (no sub-agent LLM calls)
- Rich tool descriptions include caching behavior and prerequisites
- Supervisor can parallelize independent tools
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Mapping, Optional, Set

from ..tools.canonical_registry import (
    CanonicalToolRegistry,
    FlowMode,
    get_canonical_registry,
    get_tool_allowlist,
)
from ..tools.definitions import ToolId
from .receipt_helpers import (
    apply_receipt_ttl_overrides,
    should_reuse_sql,
    should_reuse_chart,
    should_reuse_web,
    should_reuse_market,
)

logger = logging.getLogger(__name__)

__all__ = [
    "SupervisorPoolsFlow",
    "SpecialistPool",
    "SPECIALIST_POOL_DESCRIPTIONS",
]


# Rich tool descriptions for supervisor decision-making
# These include prerequisites, outputs, caching behavior, and chain-of-thought guidance
SPECIALIST_POOL_DESCRIPTIONS: Dict[str, str] = {
    "sql_pool": (
        "Execute SQL query lane to fetch financial data from the database.\n"
        "Prerequisites: Must have validated intent and selected template via plan_generation.\n"
        "Returns: Dataset with row_count, columns, sample_rows, and SQL string.\n"
        "Caching: Checks SessionStateSnapshot for cached SQL receipts. "
        "If receipt.age_seconds < 300 and no errors, returns cached data with from_cache=true.\n"
        "Retries: Automatically retries up to 2 times on transient SQL errors.\n"
        "Use this FIRST before calling chart_pool or analysis_pool."
    ),
    "chart_pool": (
        "Generate chart specification from SQL query results.\n"
        "Prerequisites: SQL lane must be completed with valid dataset.\n"
        "Returns: ECharts-compatible chart spec with series configuration.\n"
        "Caching: Reuses cached chart spec if SQL data unchanged and receipt.age_seconds < 1800.\n"
        "Chart types: line, bar, pie, scatter, candlestick based on data structure.\n"
        "Call this AFTER sql_pool completes successfully."
    ),
    "analysis_pool": (
        "Generate financial analysis narrative from chart and data.\n"
        "Prerequisites: SQL lane and chart lane must be completed.\n"
        "Returns: Analysis text with summary, bullets, key numbers, and risk watch.\n"
        "Caching: Reuses cached analysis if inputs unchanged and receipt.age_seconds < 1800.\n"
        "Includes: Evidence citations, confidence scores, and next steps.\n"
        "Call this AFTER both sql_pool and chart_pool complete."
    ),
    "web_pool": (
        "Retrieve web context and news snippets related to the query.\n"
        "Prerequisites: Intent detection must be completed.\n"
        "Returns: Web snippets with titles, URLs, and relevance scores.\n"
        "Caching: Reuses cached web context if receipt.age_seconds < 1800.\n"
        "Can run in PARALLEL with sql_pool since they are independent.\n"
        "Results feed into analysis_pool for evidence enrichment."
    ),
    "market_pool": (
        "Retrieve real-time market data and stock widget information.\n"
        "Prerequisites: Intent detection must identify company tickers.\n"
        "Returns: Stock prices, market cap, and trading volume.\n"
        "Caching: Reuses cached market data if receipt.age_seconds < 1800.\n"
        "Can run in PARALLEL with sql_pool and web_pool since independent.\n"
        "Results feed into analysis_pool for market context."
    ),
}


@dataclass
class SpecialistPool:
    """
    Dataclass: SpecialistPool
    Role: Represents a specialist capability as a deterministic tool pool.
    Why: Enables supervisor to call capabilities without sub-agent LLM calls.
    """
    pool_id: str
    description: str
    tool_ids: Set[ToolId]
    prerequisites: Set[str] = field(default_factory=set)
    can_parallelize_with: Set[str] = field(default_factory=set)
    cache_ttl_seconds: int = 1800


# Define specialist pools with their tool mappings
SPECIALIST_POOLS: Dict[str, SpecialistPool] = {
    "sql_pool": SpecialistPool(
        pool_id="sql_pool",
        description=SPECIALIST_POOL_DESCRIPTIONS["sql_pool"],
        tool_ids={ToolId.SQL_GENERATION},
        prerequisites=set(),
        can_parallelize_with={"web_pool", "market_pool"},
        cache_ttl_seconds=300,
    ),
    "chart_pool": SpecialistPool(
        pool_id="chart_pool",
        description=SPECIALIST_POOL_DESCRIPTIONS["chart_pool"],
        tool_ids={ToolId.CHART_GENERATION, ToolId.CHART_REVISION},
        prerequisites={"sql_pool"},
        can_parallelize_with=set(),
        cache_ttl_seconds=1800,
    ),
    "analysis_pool": SpecialistPool(
        pool_id="analysis_pool",
        description=SPECIALIST_POOL_DESCRIPTIONS["analysis_pool"],
        tool_ids={ToolId.ANALYSIS_GENERATION, ToolId.ANALYSIS_REVISION},
        prerequisites={"sql_pool", "chart_pool"},
        can_parallelize_with=set(),
        cache_ttl_seconds=1800,
    ),
    "web_pool": SpecialistPool(
        pool_id="web_pool",
        description=SPECIALIST_POOL_DESCRIPTIONS["web_pool"],
        tool_ids={ToolId.WEB_REFRESH},
        prerequisites=set(),
        can_parallelize_with={"sql_pool", "market_pool"},
        cache_ttl_seconds=1800,
    ),
    "market_pool": SpecialistPool(
        pool_id="market_pool",
        description=SPECIALIST_POOL_DESCRIPTIONS["market_pool"],
        tool_ids={ToolId.MARKET_REFRESH},
        prerequisites=set(),
        can_parallelize_with={"sql_pool", "web_pool"},
        cache_ttl_seconds=1800,
    ),
}


@dataclass
class PoolExecutionResult:
    """Result of executing a specialist pool."""
    pool_id: str
    success: bool
    from_cache: bool
    latency_ms: float
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SupervisorPoolsFlow:
    """
    Class: SupervisorPoolsFlow
    Role: Prototype of "Specialist Pools" pattern for Phase 3 spike.
    Called from: Golden corpus benchmark tests
    Invokes: CanonicalToolRegistry, receipt_helpers, planner_executor tools
    Why: Validates if supervisor + deterministic tools can match multi-agent performance.
    
    Key differences from MultiAgentFlow:
    1. No sub-agent LLM calls - tools are purely deterministic
    2. Single supervisor makes all decisions based on rich descriptions
    3. Explicit parallelization of independent pools (web + market + sql)
    4. Receipt-driven caching without heuristics
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        *,
        enable_parallelism: bool = True,
    ) -> None:
        self._session_id = session_id
        self._enable_parallelism = enable_parallelism
        self._registry = get_canonical_registry()
        self._pool_results: Dict[str, PoolExecutionResult] = {}
        self._start_time: Optional[float] = None

    def _can_execute_pool(self, pool: SpecialistPool) -> bool:
        """Check if a pool's prerequisites are satisfied."""
        for prereq in pool.prerequisites:
            result = self._pool_results.get(prereq)
            if result is None or not result.success:
                return False
        return True

    def _get_parallel_pools(self, pools: List[SpecialistPool]) -> List[List[SpecialistPool]]:
        """
        Group pools into parallel execution batches based on dependencies.
        Returns list of batches where pools within a batch can run in parallel.
        """
        batches: List[List[SpecialistPool]] = []
        remaining = list(pools)
        
        while remaining:
            # Find pools that can execute now
            ready = [p for p in remaining if self._can_execute_pool(p)]
            if not ready:
                # Deadlock - no pools can execute
                logger.warning("Pool execution deadlock, remaining: %s", [p.pool_id for p in remaining])
                break
            
            # Group by parallelization capability
            if self._enable_parallelism:
                batch: List[SpecialistPool] = []
                for pool in ready:
                    can_add = True
                    for existing in batch:
                        if pool.pool_id not in existing.can_parallelize_with:
                            can_add = False
                            break
                    if can_add:
                        batch.append(pool)
                batches.append(batch)
            else:
                # Sequential execution
                batches.append([ready[0]])
            
            # Remove executed pools
            for pool in batches[-1]:
                remaining.remove(pool)
        
        return batches

    async def _execute_pool(
        self,
        pool: SpecialistPool,
        ctx: Any,  # PlannerPhaseContext
    ) -> PoolExecutionResult:
        """
        Execute a single specialist pool and return result.
        This is a deterministic function call, not an LLM invocation.
        """
        import time
        start = time.perf_counter()
        
        # Check cache first
        from_cache = False
        if pool.pool_id == "sql_pool" and should_reuse_sql(ctx):
            from_cache = True
        elif pool.pool_id == "chart_pool" and should_reuse_chart(ctx, sql_refresh_required=False):
            from_cache = True
        elif pool.pool_id == "web_pool" and should_reuse_web(ctx):
            from_cache = True
        elif pool.pool_id == "market_pool" and should_reuse_market(ctx):
            from_cache = True
        
        latency_ms = (time.perf_counter() - start) * 1000
        
        if from_cache:
            logger.debug("Pool %s served from cache", pool.pool_id)
            return PoolExecutionResult(
                pool_id=pool.pool_id,
                success=True,
                from_cache=True,
                latency_ms=latency_ms,
                output={"cached": True},
            )
        
        # Execute the pool's tools
        # In a full implementation, this would invoke the actual tools
        # For the prototype, we simulate success
        try:
            # Placeholder for actual tool execution
            output = {"pool_id": pool.pool_id, "executed": True}
            latency_ms = (time.perf_counter() - start) * 1000
            
            return PoolExecutionResult(
                pool_id=pool.pool_id,
                success=True,
                from_cache=False,
                latency_ms=latency_ms,
                output=output,
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return PoolExecutionResult(
                pool_id=pool.pool_id,
                success=False,
                from_cache=False,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def execute(
        self,
        query: str,
        ctx: Any,  # PlannerPhaseContext
        *,
        follow_up_route: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the specialist pools flow.
        
        Yields SSE-compatible events for each pool execution.
        """
        import time
        self._start_time = time.perf_counter()
        
        # Determine which pools to run based on follow-up route
        route = follow_up_route or "full_pipeline"
        tool_ids = set(get_tool_allowlist(route))
        
        pools_to_run: List[SpecialistPool] = []
        for pool in SPECIALIST_POOLS.values():
            if tool_ids & pool.tool_ids:
                pools_to_run.append(pool)
        
        # Apply receipt TTL overrides
        apply_receipt_ttl_overrides(ctx, after_preflight=True)
        
        # Group into parallel batches
        batches = self._get_parallel_pools(pools_to_run)
        
        yield {
            "event": "supervisor_started",
            "data": {
                "session_id": self._session_id,
                "pools": [p.pool_id for p in pools_to_run],
                "batches": [[p.pool_id for p in batch] for batch in batches],
                "ts": datetime.utcnow().isoformat(),
            },
        }
        
        # Execute batches
        for batch_idx, batch in enumerate(batches):
            yield {
                "event": "batch_started",
                "data": {
                    "batch": batch_idx,
                    "pools": [p.pool_id for p in batch],
                    "ts": datetime.utcnow().isoformat(),
                },
            }
            
            if self._enable_parallelism and len(batch) > 1:
                # Execute pools in parallel
                tasks = [self._execute_pool(pool, ctx) for pool in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for pool, result in zip(batch, results):
                    if isinstance(result, Exception):
                        result = PoolExecutionResult(
                            pool_id=pool.pool_id,
                            success=False,
                            from_cache=False,
                            latency_ms=0,
                            error=str(result),
                        )
                    self._pool_results[pool.pool_id] = result
                    
                    yield {
                        "event": f"{pool.pool_id}_complete",
                        "data": {
                            "pool_id": pool.pool_id,
                            "success": result.success,
                            "from_cache": result.from_cache,
                            "latency_ms": result.latency_ms,
                            "error": result.error,
                            "ts": datetime.utcnow().isoformat(),
                        },
                    }
            else:
                # Sequential execution
                for pool in batch:
                    result = await self._execute_pool(pool, ctx)
                    self._pool_results[pool.pool_id] = result
                    
                    yield {
                        "event": f"{pool.pool_id}_complete",
                        "data": {
                            "pool_id": pool.pool_id,
                            "success": result.success,
                            "from_cache": result.from_cache,
                            "latency_ms": result.latency_ms,
                            "error": result.error,
                            "ts": datetime.utcnow().isoformat(),
                        },
                    }
        
        # Final summary
        total_latency = (time.perf_counter() - self._start_time) * 1000
        success_count = sum(1 for r in self._pool_results.values() if r.success)
        cache_count = sum(1 for r in self._pool_results.values() if r.from_cache)
        
        yield {
            "event": "supervisor_complete",
            "data": {
                "session_id": self._session_id,
                "total_latency_ms": total_latency,
                "pools_executed": len(self._pool_results),
                "pools_succeeded": success_count,
                "pools_cached": cache_count,
                "ts": datetime.utcnow().isoformat(),
            },
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get execution metrics for decision gate comparison."""
        total_latency = sum(r.latency_ms for r in self._pool_results.values())
        success_rate = (
            sum(1 for r in self._pool_results.values() if r.success)
            / len(self._pool_results)
            if self._pool_results
            else 0.0
        )
        cache_rate = (
            sum(1 for r in self._pool_results.values() if r.from_cache)
            / len(self._pool_results)
            if self._pool_results
            else 0.0
        )
        
        return {
            "total_latency_ms": total_latency,
            "success_rate": success_rate,
            "cache_rate": cache_rate,
            "pool_results": {
                pool_id: {
                    "success": r.success,
                    "from_cache": r.from_cache,
                    "latency_ms": r.latency_ms,
                }
                for pool_id, r in self._pool_results.items()
            },
        }

