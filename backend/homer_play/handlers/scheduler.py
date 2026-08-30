from __future__ import annotations

from dataclasses import dataclass

from ..bridge import BridgeClient
from ..models import SchedulerData, SchedulerQueryRequest
from ..parsers import SchedulerParseResult


@dataclass(frozen=True)
class HandlerResult:
    data: dict


async def run_scheduler_query(
    payload: SchedulerQueryRequest,
    parsed: SchedulerParseResult,
    bridge: BridgeClient,
    *,
    request_id: str,
) -> HandlerResult:
    # Bridge contract is flat: {status, since_hours, include_next_run, job_ids,
    # max_jobs, max_runs_per_job} — see ~/homer/src/public-bridge/schema.ts.
    interpreted = parsed.query.model_dump(mode="json")
    normalized_input = {
        # API/model vocabulary is all|success|failed|running; bridge enum is any|ok|failed|running.
        "status": {"all": "any", "success": "ok"}.get(interpreted["status"], interpreted["status"]),
        "since_hours": interpreted["since_hours"],
        "include_next_run": interpreted["include_next_run"],
        "job_ids": interpreted.get("job_ids") or [],
        "max_jobs": payload.input.max_jobs,
        "max_runs_per_job": payload.input.max_runs_per_job,
    }
    raw = await bridge.execute(
        "scheduler.query",
        normalized_input,
        request_id=request_id,
        timeout_seconds=0.75,
    )
    # The classifier output remains the public source of truth even if a bridge
    # build accidentally echoes a different interpretation.
    raw["interpreted_query"] = parsed.query.model_dump(mode="json")
    data = SchedulerData.model_validate(raw)
    return HandlerResult(data.model_dump(mode="json"))
