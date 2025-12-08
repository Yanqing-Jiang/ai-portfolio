# --- Analytics Function/Class Map ---
# Function: run_classification_stage
#   Role: Delegates classification phase execution.
#   Called from: analytics.flows.planner_executor.run_classification
#   Invokes: pipeline._classification_phase
#   Why: Exposes a reusable entrypoint for classification across flows.
# Function: run_intent_stage
#   Role: Delegates intent resolution phase execution.
#   Called from: analytics.flows.planner_executor.run_intent
#   Invokes: pipeline._intent_phase
#   Why: Shares intent resolution logic with other orchestrators.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict


async def run_classification_stage(
    pipeline: Any, ctx: Any
) -> AsyncGenerator[Dict[str, Any], None]:
    """Run the classification stage through the pipeline's implementation."""
    async for event in pipeline._classification_phase(ctx):  # type: ignore[attr-defined]
        yield event


async def run_intent_stage(pipeline: Any, ctx: Any) -> AsyncGenerator[Dict[str, Any], None]:
    """Run the intent stage through the pipeline's implementation."""
    async for event in pipeline._intent_phase(ctx):  # type: ignore[attr-defined]
        yield event

