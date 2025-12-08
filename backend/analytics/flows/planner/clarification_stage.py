# --- Analytics Function/Class Map ---
# Function: run_clarification_stage
#   Role: Delegates clarification phase execution.
#   Called from: analytics.flows.planner_executor.run_clarification
#   Invokes: pipeline._clarification_phase
#   Why: Centralizes clarification handling for reuse across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict


async def run_clarification_stage(
    pipeline: Any, ctx: Any
) -> AsyncGenerator[Dict[str, Any], None]:
    """Run the clarification stage via the pipeline implementation."""
    async for event in pipeline._clarification_phase(ctx):  # type: ignore[attr-defined]
        yield event

