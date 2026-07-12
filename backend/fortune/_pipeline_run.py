"""Internal fortune pipeline body (frame producer).

Split from ``pipeline.py`` to keep the public module under the 800-line budget.
Not part of the public fortune package API — import via ``pipeline``.
"""

from __future__ import annotations

import json as _json
import logging
import time as _time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

try:
    from .agents import (
        DEFAULT_FOLLOW_UP_BUTTONS,
        EnrichedNarrativeOutput,
        FortuneRunContext,
        GUARDRAIL_AGENT,
        GuardrailOutput,
        NARRATIVE_AGENTS,
        _narrative_mode,
        _promote_narrative_to_enriched,
        repair_occasion_narrative,
        run_foundation,
        run_guardrail,
        run_narrative_streamed,
    )
    from .config import get_settings
    from .stream_bridge import FortuneStreamBridge
    from .store import get_repository
    from .triage import run_triage
    from .naming import canonical_function
    from ._thinking_heartbeat import HeartbeatTick, iter_with_heartbeats
    from .state import RuntimeStatus
    from .pipeline import (
        _build_ask_original_input,
        _local_seq_allocator,
        _snapshot_mechanics,
        _snapshot_pillars,
        _snapshot_references,
        _to_jsonable,
    )
except ImportError:  # pragma: no cover
    from agents import (  # type: ignore[no-redef]
        DEFAULT_FOLLOW_UP_BUTTONS,
        EnrichedNarrativeOutput,
        FortuneRunContext,
        GUARDRAIL_AGENT,
        GuardrailOutput,
        NARRATIVE_AGENTS,
        _narrative_mode,
        _promote_narrative_to_enriched,
        repair_occasion_narrative,
        run_foundation,
        run_guardrail,
        run_narrative_streamed,
    )
    from config import get_settings  # type: ignore[no-redef]
    from stream_bridge import FortuneStreamBridge  # type: ignore[no-redef]
    from store import get_repository  # type: ignore[no-redef]
    from triage import run_triage  # type: ignore[no-redef]
    from naming import canonical_function  # type: ignore[no-redef]
    from _thinking_heartbeat import HeartbeatTick, iter_with_heartbeats  # type: ignore[no-redef]
    from state import RuntimeStatus  # type: ignore[no-redef]
    from pipeline import (  # type: ignore[no-redef]
        _build_ask_original_input,
        _local_seq_allocator,
        _snapshot_mechanics,
        _snapshot_pillars,
        _snapshot_references,
        _to_jsonable,
    )

def _extract_stream_event_meta(event: Any) -> dict[str, Any] | None:
    """Translate an SDK stream event into a minimal dict for the UI.

    The Agents SDK's streamed run yields three classes of events:
      * ``RawResponsesStreamEvent`` — token-level text deltas (too noisy for
        JSON output agents; the partial JSON mid-stream is not useful to
        render, so we skip these).
      * ``RunItemStreamEvent`` — higher-level tool calls, tool outputs,
        message outputs. These are the semantic breadcrumbs worth surfacing.
      * ``AgentUpdatedStreamEvent`` — fires on each handoff / specialist switch.

    Returns a small dict describing the event in portable terms, or ``None``
    if the event should be skipped. Kept defensive against minor SDK shape
    drift: attribute lookups use ``getattr`` with fallbacks.
    """
    cls_name = type(event).__name__
    if cls_name == "RawResponsesStreamEvent":
        return None
    if cls_name == "AgentUpdatedStreamEvent":
        new_agent = getattr(event, "new_agent", None)
        return {
            "kind": "handoff",
            "agent": getattr(new_agent, "name", None) or "unknown",
        }
    if cls_name == "RunItemStreamEvent":
        item = getattr(event, "item", None)
        if item is None:
            return None
        raw_item = getattr(item, "raw_item", None)
        tool_name = (
            getattr(raw_item, "name", None)
            or getattr(raw_item, "tool_name", None)
            or (raw_item.get("name") if isinstance(raw_item, dict) else None)
            or (raw_item.get("tool_name") if isinstance(raw_item, dict) else None)
        )
        type_field = getattr(item, "type", None) or ""
        class_token = type(item).__name__ or ""
        tokens = {
            s.replace("_", "").lower() for s in (type_field, class_token) if s
        }
        if not tokens:
            return None
        if "toolcalloutputitem" in tokens or "tooloutputitem" in tokens:
            return {"kind": "tool_output", "tool": tool_name or "tool"}
        if "toolcallitem" in tokens:
            return {"kind": "tool_call", "tool": tool_name or "tool"}
        if "handoffcallitem" in tokens or "handoffoutputitem" in tokens:
            target = (
                getattr(raw_item, "target", None)
                or getattr(raw_item, "handoff_target", None)
            )
            return {"kind": "handoff_call", "target": target}
        if "reasoningitem" in tokens:
            raw_summary = (
                getattr(item, "summary", None)
                or getattr(raw_item, "summary", None)
                or getattr(raw_item, "content", None)
            )

            def _text_of(entry: Any) -> str:
                if entry is None:
                    return ""
                if isinstance(entry, str):
                    return entry
                if isinstance(entry, dict):
                    return str(entry.get("text") or entry.get("content") or "")
                return str(getattr(entry, "text", None) or "")

            if isinstance(raw_summary, list):
                summary_text = " ".join(_text_of(s) for s in raw_summary).strip()
            else:
                summary_text = _text_of(raw_summary)
            return {"kind": "reasoning", "summary": summary_text or None}
        if "messageoutputitem" in tokens:
            return {"kind": "message", "tool": None}
        return None
    return None

_PANEL_DETERMINISTIC_ROWS: tuple[dict[str, Any], ...] = (
    {
        "step_id": "calendar",
        "agent_name": "Calendar",
        "model_id": "deterministic:cnlunar",
        "sequence": 1,
        "reasoning_effort": "deterministic",
    },
    {
        "step_id": "bazi_interpreter",
        "agent_name": "BaZi Interpreter",
        "model_id": "python:bazi-engine",
        "sequence": 2,
        "reasoning_effort": "deterministic",
    },
    {
        "step_id": "classics_retriever",
        "agent_name": "Classics Retriever",
        "model_id": "local:classics-retriever",
        "sequence": 3,
        "reasoning_effort": "deterministic",
    },
)

def _panel_canonical_rows(
    narrative_agent: Any,
    *,
    narrative_model_id: str,
    guardrail_agent: Any | None = None,
) -> list[dict[str, Any]]:
    """Build the 5-row canonical schema for the current stream.

    The deterministic rows are static; the narrative + guardrail rows
    pick up ``model_id`` and ``reasoning_effort`` from the selected
    agent's ``ModelSettings`` so the panel never lies about which tier
    was actually used.
    """
    narrative_effort = (
        narrative_agent.model_settings.reasoning.effort
        if narrative_agent.model_settings.reasoning is not None
        else None
    )
    guardrail_effort = (
        guardrail_agent.model_settings.reasoning.effort
        if guardrail_agent is not None
        and guardrail_agent.model_settings.reasoning is not None
        else None
    )
    rows: list[dict[str, Any]] = [dict(r) for r in _PANEL_DETERMINISTIC_ROWS]
    rows.append(
        {
            "step_id": "narrative",
            "agent_name": "Narrative",
            "model_id": narrative_model_id,
            "sequence": 4,
            "reasoning_effort": narrative_effort,
        }
    )
    rows.append(
        {
            "step_id": "guardrail",
            "agent_name": "Guardrail",
            "model_id": narrative_model_id,  # same model family
            "sequence": 5,
            "reasoning_effort": guardrail_effort,
        }
    )
    return rows

async def _event_generator_impl(session, *, request=None, store=None):
    import time as _time
    import json as _json

    bridge = FortuneStreamBridge(surface_id=session.surface_id)
    ctx = FortuneRunContext(
        fortune_id=session.fortune_id,
        surface_id=session.surface_id,
        run_id=session.run_id,
        question=session.request.question,
        focus=session.request.focus,
        tone=session.request.tone,
        birth_iso=session.request.birth_iso,
        timezone=session.request.timezone or "UTC",
        birth_time_unknown=session.request.birth_time_unknown,
        gender=session.request.gender or "unknown",
    )

    run_id = session.run_id
    fortune_id_str = session.fortune_id
    repo = await get_repository()
    run_uuid: uuid.UUID | None = None
    try:
        run_uuid = uuid.UUID(run_id) if run_id else None
    except (ValueError, TypeError):
        run_uuid = None

    _alloc_seq = _local_seq_allocator()

    async def _emit(payload: str) -> str:
        seq = await _alloc_seq()
        try:
            inner = _json.loads(payload)
        except (ValueError, TypeError):
            inner = {"raw": payload}
        env = {
            "run_id": run_id,
            "fortune_id": fortune_id_str,
            "seq": seq,
            "payload": inner,
        }
        return f"data: {_json.dumps(env)}\n\n"

    pending_cleared = False
    pending_action = session.pending_action_id
    pending_question = session.pending_action_question

    async def _maybe_clear_pending() -> None:
        nonlocal pending_cleared
        if pending_cleared:
            return
        pending_cleared = True
        session.pending_action_id = None
        session.pending_action_question = None

    async def _cancel_event(stage: str, trace_obj: Any | None = None) -> str | None:
        disconnected = False
        if request is not None:
            try:
                disconnected = await request.is_disconnected()
            except Exception:
                disconnected = False
        if store is not None:
            try:
                session.cancel_requested = (
                    await store.is_cancelled(session.fortune_id)
                    or session.cancel_requested
                )
            except Exception:
                pass
        if not session.cancel_requested and not disconnected:
            return None
        reason = "cancelled" if session.cancel_requested else "client_disconnected"
        session.touch(RuntimeStatus.interrupted)
        if trace_obj:
            trace_obj.add_instant(
                "cancelled",
                stage,
                label="Reading Paused",
                output_summary=reason,
            )
        if run_uuid is not None:
            try:
                await repo.update_run_status(
                    run_uuid,
                    "interrupted",
                    error_message=reason,
                )
            except Exception as exc:
                logger.warning("[FORTUNE] interrupted-status update failed: %s", exc)
        message = (
            "Reading paused by user"
            if session.cancel_requested
            else "Client disconnected"
        )
        return await _emit(
            bridge.emit_progress("cancelled", message),
        )

    if run_uuid is not None:
        try:
            await repo.update_run_status(run_uuid, "streaming")
        except Exception as exc:
            logger.warning("[FORTUNE] run status update failed: %s", exc)

    try:
        session.touch(RuntimeStatus.streaming)
        _t_start = _time.monotonic()
        logger.info("[FORTUNE] %s stream start — run=%s focus=%s birth=%s",
                    session.fortune_id, run_id, ctx.focus, ctx.birth_iso)

        try:
            from .agent_logging import classify_function, log_stream_start
        except ImportError:
            from agent_logging import classify_function, log_stream_start  # type: ignore[no-redef]
        _fn_label = classify_function(ctx.focus, ctx.question)
        _settings_for_log = get_settings()
        _stream_start_mode = _narrative_mode(ctx)
        _stream_start_agent = NARRATIVE_AGENTS[_stream_start_mode]
        log_stream_start(
            fortune_id=session.fortune_id,
            run_id=run_id,
            function=_fn_label,
            focus=ctx.focus,
            model=_settings_for_log.narrative_model,
            reasoning=_stream_start_agent.model_settings.reasoning.effort,
            has_person_b=session.request.person_b is not None,
            extra={
                "tone": ctx.tone or "-",
                "has_question": "true" if ctx.question else "false",
                "pending_action": pending_action or "-",
                "mode": _stream_start_mode,
            },
        )

        for msg in bridge.begin_messages(fortune_id=session.fortune_id):
            yield await _emit(msg)

        _panel_rows = _panel_canonical_rows(
            _stream_start_agent,
            narrative_model_id=_settings_for_log.narrative_model,
            guardrail_agent=GUARDRAIL_AGENT,
        )
        yield await _emit(bridge.emit_agent_steps_batch(_panel_rows))
        _panel_t0 = _t_start  # wall-clock anchor for elapsed_ms

        await _maybe_clear_pending()
        cancel_msg = await _cancel_event("begin")
        if cancel_msg:
            yield cancel_msg
            return

        cached = session.latest_foundation
        if cached and cached.get("analysis"):
            logger.info("[FORTUNE] %s reusing cached foundation", session.fortune_id)
            foundation = cached
            analysis = foundation["analysis"]
            trace = foundation.get("trace")
        else:
            yield await _emit(
                bridge.emit_progress("foundation", "Computing Four Pillars..."),
            )
            _t_found = _time.monotonic()
            foundation = await run_foundation(ctx)
            analysis = foundation["analysis"]
            dur_f = round((_time.monotonic() - _t_found) * 1000, 1)
            logger.info("[FORTUNE] %s foundation complete — %0.fms", session.fortune_id, dur_f)
            session.latest_foundation = foundation
            trace = foundation.get("trace")

        cancel_msg = await _cancel_event("foundation", trace)
        if cancel_msg:
            yield cancel_msg
            return

        yield await _emit(bridge.emit_pillars(foundation["pillars"]))
        elements_data = (
            foundation["elements"].model_dump()
            if hasattr(foundation["elements"], "model_dump")
            else foundation["elements"]
        )
        yield await _emit(bridge.emit_elements(elements_data))
        refs_data = [
            r.model_dump() if hasattr(r, "model_dump") else r
            for r in foundation["references"]
        ]
        yield await _emit(bridge.emit_references(refs_data))

        yield await _emit(bridge.emit_hidden_stems(analysis.hidden_stems))
        yield await _emit(bridge.emit_ten_gods(analysis.ten_gods))
        yield await _emit(bridge.emit_interactions(analysis.interactions))
        yield await _emit(bridge.emit_seasonal_strength(analysis.seasonal_strength))
        yield await _emit(bridge.emit_element_by_source(analysis.element_by_source))

        function_id = canonical_function(ctx.focus, session.request.question)
        is_compat = function_id == "compatibility"
        person_b_info = session.request.person_b
        foundation_b: dict[str, Any] | None = None
        if is_compat:
            yield await _emit(bridge.emit_compat_person(
                "personA",
                name=None,
                pillars=foundation["pillars"],
                elements=elements_data,
                ten_gods=analysis.ten_gods,
                hidden_stems=analysis.hidden_stems,
            ))
            if person_b_info is not None:
                yield await _emit(
                    bridge.emit_progress("foundation", "Computing Person B's Four Pillars..."),
                )
                cancel_msg = await _cancel_event("foundation", trace)
                if cancel_msg:
                    yield cancel_msg
                    return
                ctx_b = FortuneRunContext(
                    fortune_id=session.fortune_id,
                    surface_id=session.surface_id,
                    run_id=session.run_id,
                    focus=ctx.focus,
                    birth_iso=person_b_info.birth_iso,
                    timezone=person_b_info.timezone or ctx.timezone,
                    birth_time_unknown=person_b_info.birth_time_unknown,
                    gender=person_b_info.gender or "unknown",
                )
                foundation_b = await run_foundation(ctx_b)
                analysis_b = foundation_b["analysis"]
                cancel_msg = await _cancel_event("foundation", trace)
                if cancel_msg:
                    yield cancel_msg
                    return
                elements_b = (
                    foundation_b["elements"].model_dump()
                    if hasattr(foundation_b["elements"], "model_dump")
                    else foundation_b["elements"]
                )
                yield await _emit(bridge.emit_compat_person(
                    "personB",
                    name=person_b_info.name,
                    pillars=foundation_b["pillars"],
                    elements=elements_b,
                    ten_gods=analysis_b.ten_gods,
                    hidden_stems=analysis_b.hidden_stems,
                ))
                foundation = {**foundation, "person_b": foundation_b}
                session.latest_foundation = foundation
        if analysis.luck_pillars:
            yield await _emit(bridge.emit_luck_pillars(analysis.luck_pillars))
        if analysis.annual_pillars:
            yield await _emit(bridge.emit_annual_pillars(analysis.annual_pillars))
        yield await _emit(bridge.emit_kpi(analysis))

        retrodictions = foundation.get("retrodictions", [])
        if retrodictions:
            yield await _emit(bridge.emit_retrodictions(retrodictions))

        if trace:
            yield await _emit(bridge.emit_trace_steps_batch(trace.steps))

        _panel_found_ms = int(locals().get("dur_f", 0) or 0)
        for _det_row in _PANEL_DETERMINISTIC_ROWS:
            yield await _emit(
                bridge.emit_agent_step(
                    step_id=_det_row["step_id"],
                    agent_name=_det_row["agent_name"],
                    status="done",
                    model_id=_det_row["model_id"],
                    sequence=_det_row["sequence"],
                    reasoning_effort="deterministic",
                    elapsed_ms=_panel_found_ms,
                    reasoning_tokens=0,
                )
            )

        if run_uuid is not None:
            try:
                await repo.upsert_snapshot(
                    uuid.UUID(fortune_id_str),
                    status="partial",
                    mechanics=_snapshot_mechanics(session, analysis),
                    pillars=_snapshot_pillars(session, foundation),
                    references=_snapshot_references(foundation),
                    retrodictions=(
                        {"items": _to_jsonable(retrodictions)}
                        if retrodictions else None
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "[FORTUNE] foundation snapshot persistence failed: %s", exc,
                )

        if not session.request.focus:
            session.request = session.request.model_copy(update={"focus": "general"})
            ctx = FortuneRunContext(
                fortune_id=ctx.fortune_id,
                surface_id=ctx.surface_id,
                run_id=ctx.run_id,
                question=ctx.question,
                focus="general",
                tone=ctx.tone,
                birth_iso=ctx.birth_iso,
                timezone=ctx.timezone,
                birth_time_unknown=ctx.birth_time_unknown,
                gender=ctx.gender,
            )

        cancel_msg = await _cancel_event("narrative", trace)
        if cancel_msg:
            yield cancel_msg
            return

        if pending_action:
            yield await _emit(
                bridge.emit_progress(
                    "narrative", f"Routing follow-up via triage ({pending_action})...",
                ),
            )
            if trace:
                trace.add_instant(
                    "llm_start", "narrative", label="Triage + Specialist",
                    input_summary=f"action={pending_action}",
                )
                yield await _emit(bridge.emit_trace_steps_batch(trace.steps))
            _t_narrative = _time.monotonic()
            logger.info(
                "[FORTUNE] %s triage start — action=%s",
                session.fortune_id, pending_action,
            )
            _panel_narr_row = next(
                r for r in _panel_rows if r["step_id"] == "narrative"
            )
            yield await _emit(
                bridge.emit_agent_step(
                    step_id="narrative",
                    agent_name=_panel_narr_row["agent_name"],
                    status="running",
                    model_id=_panel_narr_row["model_id"],
                    sequence=_panel_narr_row["sequence"],
                    reasoning_effort=_panel_narr_row["reasoning_effort"],
                )
            )
            narrative = await run_triage(
                ctx,
                foundation=foundation,
                action_id=pending_action,
                question=pending_question,
                original_input=_build_ask_original_input(session.request),
                latest_narrative=session.latest_narrative,
            )
            cancel_msg = await _cancel_event("narrative", trace)
            if cancel_msg:
                yield cancel_msg
                return
            _dur_triage = int((_time.monotonic() - _t_narrative) * 1000)
            yield await _emit(
                bridge.emit_agent_step(
                    step_id="narrative",
                    agent_name=_panel_narr_row["agent_name"],
                    status="done",
                    model_id=_panel_narr_row["model_id"],
                    sequence=4,
                    reasoning_effort=_panel_narr_row["reasoning_effort"],
                    elapsed_ms=_dur_triage,
                    reasoning_tokens=0,
                    status_reason="triage",
                )
            )
        else:
            yield await _emit(
                bridge.emit_progress("narrative", "Generating interpretation..."),
            )
            if trace:
                trace.add_instant(
                    "llm_start", "narrative", label="Generating Narrative",
                    input_summary=f"focus={ctx.focus}",
                )
                yield await _emit(bridge.emit_trace_steps_batch(trace.steps))

            _panel_narr_row = next(
                r for r in _panel_rows if r["step_id"] == "narrative"
            )
            yield await _emit(
                bridge.emit_agent_step(
                    step_id="narrative",
                    agent_name=_panel_narr_row["agent_name"],
                    status="running",
                    model_id=_panel_narr_row["model_id"],
                    sequence=_panel_narr_row["sequence"],
                    reasoning_effort=_panel_narr_row["reasoning_effort"],
                )
            )

            _t_narrative = _time.monotonic()
            logger.info(
                "[FORTUNE] %s narrative start — model=%s",
                session.fortune_id,
                get_settings().narrative_model,
            )

            stream_result = await run_narrative_streamed(ctx, foundation=foundation)
            seen_tools: set[str] = set()
            async for event in iter_with_heartbeats(
                stream_result.stream_events(), interval=8.0
            ):
                cancel_msg = await _cancel_event("narrative", trace)
                if cancel_msg:
                    try:
                        stream_result.cancel()
                    except Exception:  # pragma: no cover - SDK drift
                        pass
                    yield cancel_msg
                    return
                if isinstance(event, HeartbeatTick):
                    yield await _emit(
                        bridge.emit_progress(
                            "narrative",
                            f"Still reasoning… ({event.elapsed_s}s)",
                        ),
                    )
                    continue
                meta = _extract_stream_event_meta(event)
                if meta is None:
                    continue
                kind = meta.get("kind")
                if kind == "handoff":
                    msg = f"Agent → {meta.get('agent')}"
                    yield await _emit(bridge.emit_progress("narrative", msg))
                    if trace:
                        trace.add_instant(
                            "handoff", "narrative",
                            label=msg,
                            input_summary=meta.get("agent") or "",
                        )
                        yield await _emit(bridge.emit_trace_steps_batch(trace.steps))
                elif kind == "tool_call":
                    tool = meta.get("tool") or "tool"
                    if tool in seen_tools:
                        continue
                    seen_tools.add(tool)
                    yield await _emit(
                        bridge.emit_progress("narrative", f"Calling tool: {tool}"),
                    )
                    if trace:
                        trace.add_instant(
                            "tool_call", "narrative",
                            tool_name=tool, label=f"Calling {tool}",
                        )
                        yield await _emit(bridge.emit_trace_steps_batch(trace.steps))
                elif kind == "tool_output":
                    tool = meta.get("tool") or "tool"
                    yield await _emit(
                        bridge.emit_progress("narrative", f"Tool returned: {tool}"),
                    )
                    if trace:
                        trace.add_instant(
                            "tool_result", "narrative",
                            tool_name=tool, label=f"{tool} complete",
                        )
                        yield await _emit(bridge.emit_trace_steps_batch(trace.steps))
                elif kind == "reasoning":
                    snippet = (meta.get("summary") or "").strip()
                    label = (
                        f"Reasoning · {snippet[:80]}"
                        if snippet else "Reasoning…"
                    )
                    yield await _emit(
                        bridge.emit_progress("narrative", label),
                    )
                    if trace:
                        trace.add_instant(
                            "reasoning", "narrative",
                            label=label,
                            output_summary=snippet[:240] if snippet else "",
                        )
                        yield await _emit(bridge.emit_trace_steps_batch(trace.steps))
                elif kind == "message":
                    yield await _emit(
                        bridge.emit_progress("narrative", "Model response received"),
                    )

            narrative = _promote_narrative_to_enriched(
                stream_result.final_output
            )

        session.latest_narrative = repair_occasion_narrative(
            ctx,
            narrative.model_dump(),
        )
        guardrail_narrative = EnrichedNarrativeOutput.model_validate(
            session.latest_narrative,
        )

        dur_n = round((_time.monotonic() - _t_narrative) * 1000, 1)
        n_insights = len(narrative.insights) if hasattr(narrative, "insights") else 0
        logger.info("[FORTUNE] %s narrative complete — %d insights, %.0fms",
                    session.fortune_id, n_insights, dur_n)

        try:
            from .agent_logging import (
                classify_function as _classify_fn,
                extract_usage as _extract_usage,
                record_latency as _record_latency,
                UsageSummary as _UsageSummary,
                logger as _agent_logger,
            )
        except ImportError:
            from agent_logging import (  # type: ignore[no-redef]
                classify_function as _classify_fn,
                extract_usage as _extract_usage,
                record_latency as _record_latency,
                UsageSummary as _UsageSummary,
                logger as _agent_logger,
            )
        if not pending_action:
            try:
                _stream_used = _extract_usage(stream_result)
            except Exception:
                _stream_used = _UsageSummary()
            _settings_now = get_settings()
            _stream_fn = _classify_fn(ctx.focus, ctx.question)
            _latency_bucket = _record_latency(
                _stream_fn,
                "narrative_streamed",
                dur_n,
            )
            _selected_mode = _narrative_mode(ctx)
            _selected_agent_obj = NARRATIVE_AGENTS[_selected_mode]
            _selected_agent = _selected_agent_obj.name
            _selected_reasoning = _selected_agent_obj.model_settings.reasoning
            _selected_effort = (
                _selected_reasoning.effort
                if _selected_reasoning is not None
                else _settings_now.narrative_reasoning
            )
            _agent_logger.info(
                "[FORTUNE-AGENT] "
                f"fn={_stream_fn} "
                f"stage=narrative_streamed "
                f"model={_settings_now.narrative_model} "
                f"reasoning={_selected_effort} "
                f"latency_ms={dur_n:.0f} "
                f"latency_bucket_ms={_latency_bucket} "
                f"tokens_in={_stream_used.input_tokens} "
                f"tokens_out={_stream_used.output_tokens} "
                f"reasoning_tokens={_stream_used.reasoning_tokens} "
                f"requests={_stream_used.requests} "
                f"run_id={ctx.run_id or '-'} "
                f"fortune_id={ctx.fortune_id or '-'} "
                f"agent={_selected_agent} mode={_selected_mode} ok=true insights={n_insights} "
                f"streamed=true person_b={'true' if 'person_b' in foundation else 'false'}"
            )

        if trace:
            trace.add_instant(
                "llm_complete", "narrative", label="Narrative Complete",
                output_summary=f"{n_insights} insights, {dur_n:.0f}ms",
            )
            trace.steps[-1].duration_ms = dur_n

        _panel_narr_tokens = int(
            getattr(_stream_used, "reasoning_tokens", 0) or 0
        )
        yield await _emit(
            bridge.emit_agent_step(
                step_id="narrative",
                agent_name=_selected_agent or "Narrative",
                status="done",
                model_id=_settings_now.narrative_model,
                sequence=4,
                reasoning_effort=_selected_effort,
                elapsed_ms=int(dur_n),
                reasoning_tokens=_panel_narr_tokens,
            )
        )

        yield await _emit(
            bridge.emit_narrative_complete(session.latest_narrative),
        )

        compat_block = session.latest_narrative.get("compatibility") if session.latest_narrative else None
        if is_compat and compat_block:
            overview = compat_block.get("overview")
            if overview:
                yield await _emit(bridge.emit_compat_overview(overview))
            pair_interactions = compat_block.get("pair_interactions") or []
            if pair_interactions:
                yield await _emit(bridge.emit_compat_pair_interactions(pair_interactions))
            mechanisms = compat_block.get("mechanisms") or []
            if mechanisms:
                yield await _emit(bridge.emit_compat_mechanisms(mechanisms))

        occasion_block = session.latest_narrative.get("occasion") if session.latest_narrative else None
        is_occasion = function_id == "occasion"
        logger.info(
            "[FORTUNE] %s occasion fan-out: is_occasion=%s block=%s picks=%d mechs=%d",
            session.fortune_id, is_occasion,
            bool(occasion_block),
            len((occasion_block or {}).get("top_picks") or []),
            len((occasion_block or {}).get("mechanisms") or []),
        )
        if is_occasion and occasion_block:
            if occasion_block.get("top_picks"):
                yield await _emit(bridge.emit_occasion_top_picks(
                    occasion_block["top_picks"],
                    fallback_mechanisms=occasion_block.get("mechanisms") or [],
                ))
                yield await _emit(bridge.emit_occasion_calendar(
                    occasion_block["top_picks"],
                ))
            if occasion_block.get("analysis"):
                yield await _emit(bridge.emit_occasion_analysis(occasion_block["analysis"]))
            if occasion_block.get("mechanisms"):
                yield await _emit(bridge.emit_occasion_mechanisms(occasion_block["mechanisms"]))

        luck_block = session.latest_narrative.get("luck_cycle") if session.latest_narrative else None
        is_luck = function_id == "cycle"
        if is_luck:
            yield await _emit(bridge.emit_luck_cycle_timeline(
                luck_pillars=analysis.luck_pillars,
                annual_pillars=analysis.annual_pillars,
            ))
            yield await _emit(bridge.emit_luck_cycle_current_window(
                (luck_block or {}).get("current_window") or {},
                luck_pillars=analysis.luck_pillars,
            ))
            if luck_block and luck_block.get("mechanisms"):
                yield await _emit(bridge.emit_luck_cycle_mechanisms(luck_block["mechanisms"]))

        wish_block = session.latest_narrative.get("wish") if session.latest_narrative else None
        is_wish = function_id == "wish"
        if is_wish and wish_block:
            if wish_block.get("verdict"):
                yield await _emit(bridge.emit_wish_verdict(wish_block["verdict"]))
            if wish_block.get("anchors"):
                yield await _emit(bridge.emit_wish_anchors(wish_block["anchors"]))
            if wish_block.get("mechanisms"):
                yield await _emit(bridge.emit_wish_mechanisms(wish_block["mechanisms"]))

        if run_uuid is not None:
            try:
                await repo.upsert_snapshot(
                    uuid.UUID(fortune_id_str),
                    status="partial",
                    narrative=session.latest_narrative,
                    mechanics=_snapshot_mechanics(session, analysis),
                    pillars=_snapshot_pillars(session, foundation),
                    references=_snapshot_references(foundation),
                    retrodictions={"items": _to_jsonable(retrodictions)} if retrodictions else None,
                )
            except Exception as exc:
                logger.warning("[FORTUNE] partial snapshot persistence failed: %s", exc)

        cancel_msg = await _cancel_event("guardrail", trace)
        if cancel_msg:
            yield cancel_msg
            return
        yield await _emit(
            bridge.emit_progress("guardrail", "Running safety check..."),
        )
        if trace:
            trace.add_instant("llm_start", "guardrail", label="Running Safety Check")

        _panel_guard_row = next(
            r for r in _panel_rows if r["step_id"] == "guardrail"
        )
        yield await _emit(
            bridge.emit_agent_step(
                step_id="guardrail",
                agent_name=_panel_guard_row["agent_name"],
                status="running",
                model_id=_panel_guard_row["model_id"],
                sequence=_panel_guard_row["sequence"],
                reasoning_effort=_panel_guard_row["reasoning_effort"],
            )
        )

        _t_guard = _time.monotonic()
        guardrail = await run_guardrail(ctx, narrative=guardrail_narrative)
        if not guardrail.follow_up_buttons:
            guardrail = GuardrailOutput(
                level=guardrail.level,
                message=guardrail.message,
                disclaimer=guardrail.disclaimer,
                follow_up_buttons=DEFAULT_FOLLOW_UP_BUTTONS,
            )
        session.latest_guardrail = guardrail.model_dump()

        dur_g = round((_time.monotonic() - _t_guard) * 1000, 1)
        logger.info("[FORTUNE] %s guardrail complete — level=%s, %.0fms",
                    session.fortune_id, guardrail.level, dur_g)

        if trace:
            trace.add_instant(
                "llm_complete", "guardrail", label="Safety Check Complete",
                output_summary=f"level={guardrail.level}, {dur_g:.0f}ms",
            )
            trace.steps[-1].duration_ms = dur_g

        yield await _emit(
            bridge.emit_agent_step(
                step_id="guardrail",
                agent_name=_panel_guard_row["agent_name"],
                status="done",
                model_id=_panel_guard_row["model_id"],
                sequence=5,
                reasoning_effort=_panel_guard_row["reasoning_effort"],
                elapsed_ms=int(dur_g),
                reasoning_tokens=0,
            )
        )

        yield await _emit(
            bridge.emit_guardrail(session.latest_guardrail),
        )

        if trace:
            yield await _emit(bridge.emit_trace_steps_batch(trace.steps))
            yield await _emit(
                bridge.emit_trace_summary(trace.summary()),
            )

        total_ms = round((_time.monotonic() - _t_start) * 1000, 1)
        logger.info("[FORTUNE] %s stream complete — total %.0fms", session.fortune_id, total_ms)
        try:
            from .agent_logging import log_stream_end as _log_stream_end
        except ImportError:
            from agent_logging import log_stream_end as _log_stream_end  # type: ignore[no-redef]
        _log_stream_end(
            fortune_id=session.fortune_id,
            run_id=run_id,
            function=_fn_label,
            total_ms=total_ms,
            ok=True,
        )
        session.touch(RuntimeStatus.complete)

        if run_uuid is not None:
            try:
                await repo.upsert_snapshot(
                    uuid.UUID(fortune_id_str),
                    status="done",
                    narrative=session.latest_narrative,
                    mechanics=_snapshot_mechanics(session, analysis),
                    pillars=_snapshot_pillars(session, foundation),
                    references=_snapshot_references(foundation),
                    retrodictions={"items": _to_jsonable(retrodictions)} if retrodictions else None,
                )
                await repo.update_run_status(run_uuid, "done")
            except Exception as exc:
                logger.warning("[FORTUNE] snapshot/status persistence failed: %s", exc)

        for msg in bridge.emit_complete():
            yield await _emit(msg)

    except Exception as exc:
        logger.exception("[FORTUNE] %s stream error: %s", session.fortune_id, exc)
        try:
            from .agent_logging import log_stream_end as _log_stream_end
        except ImportError:
            from agent_logging import log_stream_end as _log_stream_end  # type: ignore[no-redef]
        _log_stream_end(
            fortune_id=session.fortune_id,
            run_id=run_id,
            function=_fn_label,
            total_ms=(_time.monotonic() - _t_start) * 1000,
            ok=False,
            error=str(exc),
        )
        session.touch(RuntimeStatus.error)
        if run_uuid is not None:
            try:
                await repo.update_run_status(
                    run_uuid, "error", error_message=str(exc)[:500],
                )
            except Exception as update_exc:
                logger.warning("[FORTUNE] error-status update failed: %s", update_exc)
        await _maybe_clear_pending()
        for msg in bridge.emit_error(str(exc)):
            yield await _emit(msg)

