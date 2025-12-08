# --- Analytics Function/Class Map ---
# Function: _normalize_calendar_filters
#   Role: Cleanses SQL snippets to avoid null calendar filters when aggregations are present.
#   Called from: analytics.flows.planner_executor SQL generation
#   Invokes: re.sub
#   Why: Prevents calendar gaps from null filters in generated SQL.
# Function: _set_sql_generation_artifact
#   Role: Persist SQL generation attempts and metadata to artifacts.
#   Called from: analytics.flows.planner_executor SQL generation
#   Invokes: analytics.artifacts.SQLGenerationArtifact
#   Why: Centralizes artifact construction for generation status.
# Function: _set_sql_execution_artifact
#   Role: Persist SQL execution results and previews to artifacts.
#   Called from: analytics.flows.planner_executor SQL execution
#   Invokes: analytics.artifacts.SQLExecutionArtifact, _summarize_sql_rows
#   Why: Centralizes execution artifact construction and preview sizing.
# Function: _validate_sql
#   Role: Validate generated SQL with timing metadata.
#   Called from: run_sql_pipeline_stage
#   Invokes: analytics.sql.validator.validate_sql
#   Why: Keeps SQL generation loop deterministic and testable.
# Function: run_sql_pipeline_stage
#   Role: Generate, validate, and execute SQL, emitting planner events.
#   Called from: PlannerPipeline.run_sql_pipeline
#   Invokes: build_sql_messages, execute_sql, _set_sql_generation_artifact
#   Why: Moves SQL lane logic out of planner_executor.
# Function: run_sql_stage
#   Role: Streams SQL lane via existing lane helpers.
#   Called from: analytics.flows.planner_executor._plan_phase
#   Invokes: analytics.flows.planner.sql_lane.stream_sql_lane
#   Why: Provides a reusable SQL lane entrypoint for single-/multi-agent flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence, Set, Tuple

from analytics.artifacts import SQLExecutionArtifact, SQLGenerationArtifact
from analytics.core.context import get_configs
from analytics.core.events import EventEmitter
from analytics.sql.executor import execute_sql
from analytics.sql.prompt_builder import build_sql_messages, build_sql_retry_messages, extract_sql_from_response
from analytics.sql.validator import validate_sql
from unified_responses_client import get_unified_client

from .stage_helpers import _summarize_sql_rows, ensure_tool_receipt, hash_payload
from .sql_lane import stream_sql_lane

logger = logging.getLogger(__name__)
CONFIGS = get_configs()

AGGREGATE_METRIC_MARKERS = (
    "'r&d expense'",
    "'revenue'",
    "'operating cash flow'",
    "'capex'",
    "'capital expenditures'",
    "'operating income'",
    "'net income'",
)
SQL_DATASET_PREVIEW_LIMIT = 200
_hash_payload = hash_payload


def _normalize_calendar_filters(sql: str) -> str:
    if not sql:
        return sql
    lower_sql = sql.lower()
    if "calendar_quarter_num is null" not in lower_sql:
        return sql
    if "sum(" not in lower_sql:
        return sql
    if not any(marker in lower_sql for marker in AGGREGATE_METRIC_MARKERS):
        return sql
    return re.sub(
        r"calendar_quarter_num\s+IS\s+NULL",
        "calendar_quarter_num IS NOT NULL",
        sql,
        flags=re.IGNORECASE,
    )


def _set_sql_generation_artifact(
    ctx: Any,
    *,
    sql: Optional[str],
    template_id: Optional[str],
    attempts: Sequence[Dict[str, Any]],
    llm_used: bool,
    last_error_code: Optional[str],
    last_error_detail: Optional[str],
    status: str,
) -> None:
    ctx.artifacts.sql_generation = SQLGenerationArtifact(
        query=ctx.query,
        sql=sql,
        template_id=template_id,
        attempts=list(attempts),
        llm_used=llm_used,
        last_error=last_error_detail,
        last_error_code=last_error_code,
        last_error_detail=last_error_detail,
        status=status,
    )


def _set_sql_execution_artifact(
    ctx: Any,
    *,
    data: Optional[List[Dict[str, Any]]],
    elapsed_ms: Optional[int],
    status: str,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
) -> None:
    dataset: List[Dict[str, Any]] = list(data or [])
    summary = _summarize_sql_rows(dataset)
    row_count = len(dataset) if dataset else None
    dataset_preview = dataset[:SQL_DATASET_PREVIEW_LIMIT] if dataset else []
    ctx.artifacts.sql_execution = SQLExecutionArtifact(
        query=ctx.query,
        row_count=row_count,
        columns=summary["columns"],
        tickers=summary["tickers"],
        metrics=summary["metrics"],
        timeframe=summary["timeframe"],
        sample_rows=summary["sample_rows"],
        dataset_preview=dataset_preview,
        dataset=dataset,
        elapsed_ms=elapsed_ms,
        status=status,
        error=error,
        error_code=error_code,
    )


def _validate_sql(sql: str) -> Tuple[bool, List[str], int]:
    start = time.time()
    ok, issues = validate_sql(sql)
    elapsed = int((time.time() - start) * 1000)
    return ok, issues, elapsed


async def run_sql_pipeline_stage(
    pipeline: Any,
    ctx: Any,
    *,
    intent: Any,
    plan: Any,
    candidate_templates: List[Dict[str, Any]],
    selected_template_id: Optional[str],
) -> AsyncGenerator[Dict[str, Any], None]:
    timed_emitter = ctx.timed_emitter
    workflow_start = ctx.workflow_start
    session_id = ctx.session_id
    query = ctx.query

    plan_payload: Optional[Dict[str, Any]] = None
    if hasattr(plan, "model_dump"):
        plan_payload = plan.model_dump()
    elif hasattr(plan, "dict"):
        plan_payload = plan.dict()
    input_payload = {
        "query": query,
        "intent": getattr(intent, "intent_key", None),
        "plan": plan_payload,
        "selected_template_id": selected_template_id,
    }
    receipt = ensure_tool_receipt(
        ctx,
        "sql_chain",
        status="running",
        reused=False,
        attempts=0,
        input_hash=_hash_payload(input_payload),
    )
    start_time = time.time()

    sql = ""
    llm_used = False
    attempt_logs: List[Dict[str, Any]] = []
    validated_attempt: Optional[int] = None
    last_error_code: Optional[str] = None
    last_error_detail: Optional[str] = None
    previous_sql: Optional[str] = None

    progress_message = "Generating SQL with Responses API..."
    deterministic_result: Optional[Dict[str, Any]] = None

    try:
        deterministic_result, deterministic_elapsed_ms = await pipeline._maybe_run_deterministic_sql(
            ctx,
            plan=plan,
            templates=candidate_templates,
        )
    except Exception:
        deterministic_result = None
        deterministic_elapsed_ms = None

    if deterministic_result and isinstance(deterministic_result.get("sql"), str):
        candidate_sql = (deterministic_result.get("sql") or "").strip()
        if candidate_sql:
            sql = candidate_sql
            progress_message = "Using deterministic template SQL"
            template_from_result = deterministic_result.get("template")
            if template_from_result:
                selected_template_id = template_from_result.get("id") or selected_template_id
                ctx.template = template_from_result
            attempt_logs.append(
                {
                    "attempt": 1,
                    "status": "deterministic",
                    "elapsed_ms": deterministic_elapsed_ms or 0,
                    "llm_used": False,
                }
            )
            receipt.attempts = 1
            validated_attempt = 1

    sql_progress = EventEmitter.progress("sql_compilation", progress_message)
    sql_progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield sql_progress
    timed_emitter.start_step("sql_generation")

    if sql and attempt_logs and attempt_logs[-1].get("status") == "deterministic":
        compiled_event = EventEmitter.result(
            "sql_compiled",
            {
                "sql_length": len(sql),
                "template_fallback": False,
                "template_used": selected_template_id,
                "attempt": attempt_logs[-1].get("attempt", 1),
                "fallback_reason": None,
                "llm_used": False,
            },
        )
        compiled_event["event"] = "sql_compiled"
        compiled_event["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": attempt_logs[-1].get("elapsed_ms"),
            }
        )
        yield compiled_event
        generated_event = EventEmitter.sql_generated(sql)
        generated_event["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": attempt_logs[-1].get("elapsed_ms"),
                "llm_used": False,
                "attempt": attempt_logs[-1].get("attempt", 1),
            }
        )
        yield generated_event
    if not sql:
        MAX_SQL_ATTEMPTS = 3

        messages = await build_sql_messages(
            original_query=query,
            intent=intent,
            plan=plan,
            config_store=pipeline.config_store,
            templates=candidate_templates,
        )

        for attempt in range(1, MAX_SQL_ATTEMPTS + 1):
            attempt_start = time.time()
            attempt_record: Dict[str, Any] = {"attempt": attempt, "status": "started"}
            candidate_sql = ""
            receipt.attempts += 1
            try:
                if not pipeline.unified_client:
                    pipeline.unified_client = get_unified_client()
                if not pipeline.unified_client:
                    raise RuntimeError("Unified Responses client is not configured")
                llm_response, _ = await pipeline.unified_client.simple_completion(
                    messages=messages,
                    reasoning_effort="low",
                )
                candidate_sql = (extract_sql_from_response(llm_response) or "").strip()
                candidate_sql = _normalize_calendar_filters(candidate_sql)
            except Exception as exc:
                last_error_code = "SQL_GENERATION_ERROR"
                last_error_detail = str(exc)
                attempt_record.update(
                    status="error",
                    error_code=last_error_code,
                    error_detail=last_error_detail,
                    elapsed_ms=int((time.time() - attempt_start) * 1000),
                )
                attempt_logs.append(attempt_record)
                error_event = EventEmitter.error(
                    "sql_compilation",
                    "SQL generation failed",
                    details={"attempt": attempt, "error": last_error_detail},
                    code=last_error_code,
                )
                error_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield error_event
            else:
                if not candidate_sql:
                    last_error_code = "SQL_EMPTY"
                    last_error_detail = "Responses API returned no SQL content."
                    attempt_record.update(
                        status="empty",
                        error_code=last_error_code,
                        error_detail=last_error_detail,
                        elapsed_ms=int((time.time() - attempt_start) * 1000),
                    )
                    attempt_logs.append(attempt_record)
                    empty_notice = EventEmitter.progress(
                        "sql_compilation",
                        "SQL attempt returned no content; retrying with additional guidance.",
                    )
                    empty_notice["data"].update(
                        {"ts": datetime.utcnow().isoformat(), "attempt": attempt}
                    )
                    yield empty_notice
                else:
                    ok, issues, validate_elapsed = _validate_sql(candidate_sql)
                    attempt_record.update(
                        status="valid" if ok else "invalid",
                        elapsed_ms=int((time.time() - attempt_start) * 1000),
                        validation_elapsed_ms=validate_elapsed,
                        issues=issues,
                    )
                    if not ok:
                        last_error_code = "SQL_VALIDATION_FAILED"
                        last_error_detail = "; ".join(issues) if issues else "Validation failed"
                    attempt_logs.append(attempt_record)
                    if ok:
                        sql = candidate_sql
                        validated_attempt = attempt
                        llm_used = True
                        compiled_event = EventEmitter.result(
                            "sql_compiled",
                            {
                                "sql_length": len(sql),
                                "template_fallback": False,
                                "template_used": selected_template_id,
                                "attempt": attempt,
                                "fallback_reason": None,
                                "llm_used": True,
                            },
                        )
                        compiled_event["event"] = "sql_compiled"
                        compiled_event["data"].update(
                            {
                                "ts": datetime.utcnow().isoformat(),
                                "elapsed_ms": attempt_record.get("elapsed_ms"),
                            }
                        )
                        yield compiled_event
                        generated_event = EventEmitter.sql_generated(sql)
                        generated_event["data"].update(
                            {
                                "ts": datetime.utcnow().isoformat(),
                                "elapsed_ms": attempt_record.get("elapsed_ms"),
                                "llm_used": True,
                                "attempt": attempt,
                            }
                        )
                        yield generated_event
                        break
                    validation_event = EventEmitter.error(
                        "sql_validation",
                        "Generated SQL failed validation",
                        details={"attempt": attempt, "issues": issues},
                        code=last_error_code,
                    )
                    validation_event["data"]["ts"] = datetime.utcnow().isoformat()
                    yield validation_event
                    previous_sql = candidate_sql
            if sql:
                break
            if attempt < MAX_SQL_ATTEMPTS:
                retry_notice = EventEmitter.progress(
                    "sql_compilation",
                    f"Retrying SQL generation (attempt {attempt + 1}/{MAX_SQL_ATTEMPTS})",
                )
                retry_notice["data"].update(
                    {"ts": datetime.utcnow().isoformat(), "last_error": last_error_code}
                )
                yield retry_notice
                messages = await build_sql_retry_messages(
                    original_query=query,
                    intent=intent,
                    plan=plan,
                    error_code=last_error_code or "unknown_error",
                    error_detail=last_error_detail or "",
                    previous_sql=previous_sql,
                    attempts=attempt_logs,
                    config_store=pipeline.config_store,
                    templates=candidate_templates,
                )

    generation_status = "generated" if sql else "failed"
    _set_sql_generation_artifact(
        ctx,
        sql=sql if sql else None,
        template_id=selected_template_id,
        attempts=attempt_logs,
        llm_used=llm_used,
        last_error_code=last_error_code,
        last_error_detail=last_error_detail,
        status=generation_status,
    )
    pipeline._capture_artifacts(ctx)
    if sql:
        await pipeline._persist_session_state(ctx, record_sql=True)
    if not sql:
        failure_event = EventEmitter.error(
            "sql_compilation",
            "Unable to generate valid SQL after 3 attempts",
            details={"attempts": attempt_logs, "last_error": last_error_code, "last_detail": last_error_detail},
            code=last_error_code or "SQL_RETRY_EXHAUSTED",
        )
        failure_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield failure_event
        receipt.status = "failed"
        receipt.error = last_error_detail or last_error_code or "SQL_RETRY_EXHAUSTED"
        receipt.elapsed_ms = int((time.time() - start_time) * 1000)
        workflow_abort = EventEmitter.result(
            "workflow_complete",
            {
                "status": "sql_generation_failed",
                "total_elapsed_ms": int((time.time() - workflow_start) * 1000),
            },
        )
        workflow_abort["event"] = "workflow_complete"
        workflow_abort["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_abort
        ctx.halted = True
        ctx.halt_reason = "sql_generation_failed"
        logger.error(
            "Planner executor halted during SQL generation",
            extra={
                "session_id": ctx.session_id,
                "selected_template": ctx.selected_template_id,
                "attempts": len(attempt_logs),
                "elapsed_ms": int((time.time() - workflow_start) * 1000),
            },
        )
        return

    validation_progress = EventEmitter.progress(
        "sql_validation", "Validating SQL..."
    )
    validation_progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield validation_progress
    ok, issues, validate_elapsed = _validate_sql(sql)
    latest_attempt = validated_attempt
    if latest_attempt is None:
        for entry in reversed(attempt_logs):
            if isinstance(entry, dict) and "attempt" in entry:
                latest_attempt = entry.get("attempt")
                break
    validation_event = EventEmitter.result(
        "sql_validated",
        {
            "ok": ok,
            "issues_count": len(issues),
            "attempt": latest_attempt,
            "issues": issues,
        },
    )
    validation_event["event"] = "sql_validated"
    validation_event["data"].update(
        {"ts": datetime.utcnow().isoformat(), "elapsed_ms": validate_elapsed}
    )
    yield validation_event
    if not ok:
        _set_sql_generation_artifact(
            ctx,
            sql=sql,
            template_id=selected_template_id,
            attempts=attempt_logs,
            llm_used=llm_used,
            last_error_code="SQL_VALIDATION_FINAL",
            last_error_detail="; ".join(issues) if issues else None,
            status="validation_failed",
        )
        pipeline._capture_artifacts(ctx)
        error_event = EventEmitter.error(
            "sql_validation",
            "SQL failed validation after retries",
            details={"attempts": attempt_logs, "issues": issues},
            code="SQL_VALIDATION_FINAL",
        )
        error_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield error_event
        workflow_error = EventEmitter.error(
            "workflow_error",
            "SQL query failed validation. Please rephrase your request.",
            code="sql_validation_failed",
            details={
                "issues": issues,
                "selected_template": selected_template_id,
                "attempts": attempt_logs,
            },
        )
        workflow_error["event"] = "workflow_error"
        workflow_error.setdefault("data", {})
        workflow_error["data"]["issues"] = issues
        workflow_error["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_error
        receipt.status = "failed"
        receipt.error = "; ".join(issues) if issues else "SQL validation failed"
        receipt.elapsed_ms = int((time.time() - start_time) * 1000)
        workflow_abort = EventEmitter.result(
            "workflow_complete",
            {
                "status": "sql_validation_failed",
                "total_elapsed_ms": int((time.time() - workflow_start) * 1000),
            },
        )
        workflow_abort["event"] = "workflow_complete"
        workflow_abort["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_abort
        ctx.halted = True
        ctx.halt_reason = "sql_validation_failed"
        logger.error(
            "Planner executor halted during SQL validation",
            extra={
                "session_id": ctx.session_id,
                "selected_template": ctx.selected_template_id,
                "issues": issues,
                "elapsed_ms": int((time.time() - workflow_start) * 1000),
            },
        )
        return
    else:
        _set_sql_generation_artifact(
            ctx,
            sql=sql,
            template_id=selected_template_id,
            attempts=attempt_logs,
            llm_used=llm_used,
            last_error_code=None,
            last_error_detail=None,
            status="validated",
        )
        pipeline._capture_artifacts(ctx)
    if not ctx.halted:
        receipt.status = "completed"
        receipt.elapsed_ms = int((time.time() - start_time) * 1000)
        receipt.error = None
        if sql:
            receipt.output_hash = _hash_payload({"sql": sql})
    execution_progress = EventEmitter.progress(
        "sql_execution", "Executing query..."
    )
    execution_progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield execution_progress
    exec_start = time.time()
    try:
        data = await execute_sql(sql)
        exec_elapsed = int((time.time() - exec_start) * 1000)
        _set_sql_execution_artifact(
            ctx,
            data=data,
            elapsed_ms=exec_elapsed,
            status="success",
        )
        pipeline._capture_artifacts(ctx)
        await pipeline._persist_session_state(
            ctx,
            record_dataset_preview=True,
            record_artifacts=True,
        )

        execution_artifact = getattr(ctx.artifacts, "sql_execution", None)
        row_count = getattr(execution_artifact, "row_count", None) if execution_artifact else None
        columns: List[str] = []
        sample_rows: List[Dict[str, Any]] = []
        if execution_artifact:
            columns = list(getattr(execution_artifact, "columns", []) or [])[:12]
            preview = getattr(execution_artifact, "dataset_preview", None)
            sample_rows = list(preview or getattr(execution_artifact, "sample_rows", []) or [])[:20]

        execution_event = EventEmitter.result(
            "execution_stats",
            {
                "row_count": row_count,
                "columns": columns,
                "columns_count": len(columns),
            },
        )
        execution_event["event"] = "execution_stats"
        execution_event["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": exec_elapsed,
                "schedule_stage": "sql",
                "parallel_group": "core_sequential",
                "flow_mode": pipeline.flow_mode.value,
                "lane": "sql",
                "reused": False,
            }
        )
        yield execution_event

        data_event = EventEmitter.result(
            "data_retrieved",
            {
                "row_count": row_count,
                "sample_data": sample_rows,
            },
        )
        data_event["event"] = "data_retrieved"
        data_event["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": exec_elapsed,
                "schedule_stage": "sql",
                "parallel_group": "core_sequential",
                "flow_mode": pipeline.flow_mode.value,
                "lane": "sql",
                "reused": False,
            }
        )
        yield data_event

    except Exception as exec_exc:
        exec_elapsed = int((time.time() - exec_start) * 1000)
        _set_sql_execution_artifact(
            ctx,
            data=None,
            elapsed_ms=exec_elapsed,
            status="error",
            error=str(exec_exc),
            error_code="SQL_EXECUTION_ERROR",
        )
        pipeline._capture_artifacts(ctx)
        logger.error(
            "[SQL_EXECUTION] Execution failed: %s",
            exec_exc,
            extra={
                "error_code": "SQL_EXECUTION_ERROR",
                "flow": pipeline.flow_label,
                "session_id": session_id,
                "intent_key": intent.intent_key,
            },
        )
        error_event = EventEmitter.error(
            "sql_execution",
            "SQL execution failed",
            details={"error": str(exec_exc)},
            code="SQL_EXECUTION_ERROR",
        )
        error_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield error_event
        receipt.status = "failed"
        receipt.error = str(exec_exc)
        receipt.elapsed_ms = int((time.time() - start_time) * 1000)
        workflow_abort = EventEmitter.result(
            "workflow_complete",
            {
                "status": "sql_execution_failed",
                "total_elapsed_ms": int((time.time() - workflow_start) * 1000),
            },
        )
        workflow_abort["event"] = "workflow_complete"
        workflow_abort["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_abort
        ctx.halted = True
        ctx.halt_reason = "sql_execution_failed"
        logger.error(
            "Planner executor halted during SQL execution",
            extra={
                "session_id": ctx.session_id,
                "selected_template": ctx.selected_template_id,
                "elapsed_ms": int((time.time() - workflow_start) * 1000),
            },
        )
        return


async def run_sql_stage(
    pipeline: Any,
    *,
    ctx: Any,
    registry: Any,
    executed: Set[str],
    tool_state: Optional[Dict[str, Any]],
    run_sql_lane: bool,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Run the SQL lane using the shared lane helper."""
    async for event in stream_sql_lane(
        pipeline,
        ctx=ctx,
        registry=registry,
        executed=executed,
        tool_state=tool_state,
        run_sql_lane=run_sql_lane,
    ):
        yield event
