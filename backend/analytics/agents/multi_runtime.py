"""Tool-native multi-agent runtime orchestrating specialist tool usage."""
from __future__ import annotations

import asyncio
import inspect
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

from analytics.agents.tool_registry import ToolRegistry
from analytics.agents.tools import register_default_tools
from analytics.core.context import get_configs
from analytics.core.intent import detect_intent_with_clarifications_async
from analytics.core.telemetry import agent_handoff, tool_iteration
from analytics.core.events import EventEmitter
from analytics.core.types import IntentModel, QueryPlanModel
from analytics.sql.sql_planner import plan_sql_rule_based

from unified_responses_client import get_unified_client, ResponseMessage

logger = logging.getLogger(__name__)

EventCallback = Callable[[Dict[str, Any]], Awaitable[None] | None]


@dataclass
class SpecialistConfig:
    """Configuration metadata for specialists."""

    name: str
    system_prompt: str
    tools: List[str] = field(default_factory=list)


DEFAULT_SPECIALISTS: Dict[str, SpecialistConfig] = {
    "planner": SpecialistConfig(
        name="planner",
        system_prompt=(
            "You orchestrate the analytics workflow. Gather missing slots, outline the plan, and hand off tasks to other specialists."
        ),
        tools=["clarification.ask_missing_slots"],
    ),
    "query": SpecialistConfig(
        name="query",
        system_prompt=(
            "You draft and execute SQL. Use sql.build_messages to generate prompts and sql.execute to run them."
        ),
        tools=["sql.build_messages", "sql.execute"],
    ),
    "analyst": SpecialistConfig(
        name="analyst",
        system_prompt="You summarize SQL results into concise financial takeaways.",
        tools=["analysis.summarize"],
    ),
    "chart": SpecialistConfig(
        name="chart",
        system_prompt="You produce charts from data. Call chart.generate with the SQL output.",
        tools=["chart.generate"],
    ),
    "market": SpecialistConfig(
        name="market",
        system_prompt="You fetch market snapshots or tickers when requested by the planner.",
        tools=["market.snapshot"],
    ),
    "web": SpecialistConfig(
        name="web",
        system_prompt="You perform web searches for recency or coverage checks when requested.",
        tools=["web.search"],
    ),
}


RECENCY_KEYWORDS = (
    "today",
    "latest",
    "recent",
    "news",
    "headline",
    "update",
    "guidance",
    "current",
    "filing",
    "quarter",
    "earnings",
)


class MultiAgentRuntime:
    """Orchestrates runtime specialists with tool registry support."""

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        reasoning_effort: str = "medium",
    ) -> None:
        self._specialists: Dict[str, SpecialistConfig] = dict(DEFAULT_SPECIALISTS)
        self._tool_registry = ToolRegistry()
        register_default_tools(self._tool_registry)
        self._event_callback: Optional[EventCallback] = None
        self._sequence: int = 0
        self._last_response_id: Optional[str] = None
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._configs = get_configs()
        self._responses_client = None

    def set_event_callback(self, callback: Optional[EventCallback]) -> None:
        self._event_callback = callback

    def register_specialist(self, config: SpecialistConfig) -> None:
        self._specialists[config.name] = config

    def list_specialists(self) -> List[str]:
        return sorted(self._specialists)

    async def run(self, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        self._sequence = 0
        self._last_response_id = None
        context: Dict[str, Any] = {"query": query}

        agent_handoff(
            role="coordinator",
            status="pending",
            session_id=session_id,
            flow="multi-agent-runtime",
            metadata={"query": query, "specialists": self.list_specialists()},
        )

        try:
            planner_ctx = await self._run_planner_specialist(query, session_id)
            context.update(planner_ctx)

            sql_ctx = await self._run_query_specialist(query, planner_ctx, session_id)
            context.update(sql_ctx)

            tickers = self._resolve_market_tickers(query, planner_ctx, sql_ctx)
            if tickers:
                context["market_tickers"] = tickers

            parallel_specs: Sequence[Tuple[str, Callable[[], Awaitable[Dict[str, Any]]], Callable[[List[str]], Dict[str, Any]]]] = []

            parallel_specs = [
                (
                    "chart",
                    lambda: self._run_chart_specialist(query, planner_ctx, sql_ctx, session_id),
                    self._chart_fallback,
                ),
                (
                    "analyst",
                    lambda: self._run_analyst_specialist(query, planner_ctx, sql_ctx, session_id),
                    self._analysis_fallback,
                ),
            ]

            if tickers or self._market_snapshot_enabled():
                parallel_specs += [
                    (
                        "market",
                        lambda: self._run_market_specialist(query, tickers, session_id),
                        lambda errors: self._market_fallback(tickers, errors),
                    )
                ]

            should_run_web = self._should_run_web(query)
            if should_run_web or self._web_search_forced():
                parallel_specs += [
                    (
                        "web",
                        lambda: self._run_web_specialist(query, planner_ctx, sql_ctx, session_id, force=not should_run_web),
                        self._web_fallback,
                    )
                ]

            parallel_results = await self._execute_parallel(parallel_specs, session_id)
            for payload in parallel_results:
                if payload:
                    context.update(payload)

            final_payload = self._build_final_payload(context)
            final_event = EventEmitter.result("agent_reply", final_payload)
            if "data" in final_event:
                final_event["data"].setdefault("response_id", self._last_response_id)
            await self._emit_event(final_event)
            await self._emit_event(EventEmitter.complete("workflow", summary="Multi-agent runtime finished"))
            return context
        except Exception as exc:
            logger.exception("Multi-agent runtime failed")
            await self._emit_event(EventEmitter.error("multi_agent_runtime", exc))
            raise

    async def _run_planner_specialist(self, query: str, session_id: Optional[str]) -> Dict[str, Any]:
        await self._emit_agent_turn("planner", "thinking", detail="intent_detection")
        intent: IntentModel = await detect_intent_with_clarifications_async(
            query,
            self._configs.__dict__ if hasattr(self._configs, "__dict__") else self._configs,
            session_id=session_id,
        )
        plan_dict = plan_sql_rule_based(intent)
        plan = QueryPlanModel.model_validate(plan_dict)

        clarifications = await self._invoke_tool(
            session_id,
            "clarification.ask_missing_slots",
            {"intent": intent.model_dump(), "plan": plan.model_dump(), "template": None},
        )

        metadata = {
            "intent_key": intent.intent_key,
            "confidence": intent.confidence,
            "clarification_count": clarifications.get("count", 0),
        }
        await self._emit_agent_turn("planner", "completed", detail="intent_detection", metadata=metadata)
        return {
            "intent": intent,
            "plan": plan,
            "clarifications": clarifications,
        }

    async def _run_query_specialist(
        self,
        query: str,
        planner_ctx: Dict[str, Any],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        await self._emit_agent_turn("query", "thinking", detail="sql_generation")
        intent: IntentModel = planner_ctx["intent"]
        plan: QueryPlanModel = planner_ctx["plan"]
        messages_payload = await self._invoke_tool(
            session_id,
            "sql.build_messages",
            {
                "original_query": query,
                "intent": intent.model_dump(),
                "plan": plan.model_dump(),
                "templates": None,
            },
        )
        messages = messages_payload.get("messages") or []
        sql_text, response_id = await self._draft_sql(messages, session_id)
        self._last_response_id = response_id or self._last_response_id

        sql_result = await self._invoke_tool(
            session_id,
            "sql.execute",
            {
                "sql": sql_text,
                "max_rows": getattr(plan, "limit", 10000) or 10000,
                "timeout": 20.0,
            },
        )
        row_count = sql_result.get("row_count", len(sql_result.get("rows") or []))
        metadata = {"row_count": row_count, "response_id": response_id}
        await self._emit_agent_turn("query", "completed", detail="sql_generation", metadata=metadata)
        return {
            "sql": sql_text,
            "sql_rows": sql_result.get("rows") or [],
            "row_count": row_count,
            "sql_messages": messages,
        }

    async def _run_chart_specialist(
        self,
        query: str,
        planner_ctx: Dict[str, Any],
        sql_ctx: Dict[str, Any],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        rows = sql_ctx.get("sql_rows") or []
        if not rows:
            await self._emit_agent_turn("chart", "skipped", detail="chart.generate", metadata={"reason": "no_data"})
            return {"chart": None}
        await self._emit_agent_turn("chart", "thinking", detail="chart.generate")
        plan: QueryPlanModel = planner_ctx["plan"]
        chart_payload = await self._invoke_tool(
            session_id,
            "chart.generate",
            {
                "data": rows,
                "query": query,
                "intent_key": planner_ctx.get("intent").intent_key if planner_ctx.get("intent") else None,
                "comparison": plan.comparison,
            },
        )
        await self._emit_agent_turn(
            "chart",
            "completed",
            detail="chart.generate",
            metadata={"has_chart": bool(chart_payload.get("chart_spec"))},
        )
        return {"chart": chart_payload}

    async def _run_analyst_specialist(
        self,
        query: str,
        planner_ctx: Dict[str, Any],
        sql_ctx: Dict[str, Any],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        rows = sql_ctx.get("sql_rows") or []
        sql_text = sql_ctx.get("sql")
        if not rows or not sql_text:
            await self._emit_agent_turn("analyst", "skipped", detail="analysis.summarize", metadata={"reason": "no_data"})
            return {"analysis": None}
        await self._emit_agent_turn("analyst", "thinking", detail="analysis.summarize")
        analysis_payload = await self._invoke_tool(
            session_id,
            "analysis.summarize",
            {
                "data": rows,
                "sql": sql_text,
                "query": query,
            },
        )
        await self._emit_agent_turn(
            "analyst",
            "completed",
            detail="analysis.summarize",
            metadata={"summary_length": len(analysis_payload.get("summary") or "")},
        )
        return {"analysis": analysis_payload}

    async def _run_market_specialist(
        self,
        query: str,
        tickers: Sequence[str],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        normalized = [ticker for ticker in tickers if ticker]
        if not normalized:
            await self._emit_agent_turn("market", "skipped", detail="market.snapshot", metadata={"reason": "no_tickers"})
            return {"market": None}
        await self._emit_agent_turn(
            "market",
            "thinking",
            detail="market.snapshot",
            metadata={"tickers": normalized},
        )
        market_payload = await self._invoke_tool(
            session_id,
            "market.snapshot",
            {"tickers": list(normalized)},
        )
        await self._emit_agent_turn(
            "market",
            "completed",
            detail="market.snapshot",
            metadata={
                "tickers": normalized,
                "status": market_payload.get("status"),
                "count": len(market_payload.get("snapshots") or []),
            },
        )
        return {"market": market_payload, "market_tickers": list(normalized)}

    async def _run_web_specialist(
        self,
        query: str,
        planner_ctx: Dict[str, Any],
        sql_ctx: Dict[str, Any],
        session_id: Optional[str],
        *,
        force: bool = False,
    ) -> Dict[str, Any]:
        should_run = force or self._should_run_web(query)
        if not should_run:
            await self._emit_agent_turn("web", "skipped", detail="web.search", metadata={"reason": "passive"})
            return {}
        await self._emit_agent_turn("web", "thinking", detail="web.search")
        web_payload = await self._invoke_tool(
            session_id,
            "web.search",
            {"query": query, "session_id": session_id},
        )
        await self._emit_agent_turn(
            "web",
            "completed",
            detail="web.search",
            metadata={"snippets": len(web_payload.get("snippets") or [])},
        )
        return {"web": web_payload}

    def _should_run_web(self, query: str) -> bool:
        normalized = (query or "").strip().lower()
        if any(keyword in normalized for keyword in RECENCY_KEYWORDS):
            return True
        if self._web_search_forced():
            return True
        return False

    def _web_search_forced(self) -> bool:
        return os.getenv("ANALYTICS_ENABLE_WEB_SEARCH", "0").strip().lower() in {"1", "true", "yes", "on"}

    def _market_snapshot_enabled(self) -> bool:
        return os.getenv("ANALYTICS_MARKET_WIDGET", "0").strip().lower() in {"1", "true", "yes", "on"}

    async def _draft_sql(
        self,
        messages: List[Dict[str, Any]],
        session_id: Optional[str],
    ) -> Tuple[str, Optional[str]]:
        client = self._get_responses_client()
        response: ResponseMessage = await client.tool_calling_turn(
            messages,
            tools=[],
            tool_choice="none",
            reasoning_effort=self._reasoning_effort,
            session_id=session_id,
            model=self._model,
        )
        content = response.content or ""
        sql_text = self._extract_sql(content)
        if not sql_text:
            raise RuntimeError("SQL draft was empty")
        return sql_text, response.response_id

    def _extract_sql(self, content: str) -> str:
        if not content:
            return ""
        fenced = re.findall(r"```(?:sql)?\s*(.*?)```", content, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            return fenced[-1].strip()
        return content.strip()

    def _build_final_payload(self, context: Dict[str, Any]) -> Dict[str, Any]:
        intent: Optional[IntentModel] = context.get("intent")
        plan: Optional[QueryPlanModel] = context.get("plan")
        clarifications = context.get("clarifications") or {}
        analysis = context.get("analysis") or {}
        summary = analysis.get("summary") if isinstance(analysis, dict) else None
        chart = context.get("chart") or {}
        final_rows = context.get("sql_rows") or []
        payload: Dict[str, Any] = {
            "intent": intent.model_dump() if intent else None,
            "plan": plan.model_dump() if plan else None,
            "clarifications": clarifications,
            "analysis": analysis,
            "chart": chart,
            "market": context.get("market"),
            "market_tickers": context.get("market_tickers") or [],
            "row_count": context.get("row_count", len(final_rows)),
            "web_search": context.get("web"),
            "sql": context.get("sql"),
        }
        if summary:
            payload["content"] = summary
        elif final_rows:
            payload["content"] = f"Fetched {len(final_rows)} rows."
        else:
            payload["content"] = "No data returned; review clarifications or query."
        if self._last_response_id:
            payload["response_id"] = self._last_response_id
        return payload

    async def _invoke_tool(
        self,
        session_id: Optional[str],
        tool_name: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload_keys = list((payload or {}).keys())
        start = time.perf_counter()
        await self._emit_event(
            {
                "event": "tool_call",
                "data": {
                    "tool": tool_name,
                    "status": "start",
                    "step": tool_name,
                    "payload_keys": payload_keys,
                    "ts": datetime.utcnow().isoformat(),
                },
            }
        )
        tool_iteration(
            tool=tool_name,
            status="start",
            step=tool_name,
            session_id=session_id,
            flow="multi-agent-runtime",
            details={"payload_keys": payload_keys},
        )
        try:
            result = await self._tool_registry.invoke(tool_name, payload)
            elapsed = int((time.perf_counter() - start) * 1000)
            result_keys = list((result or {}).keys())
            tool_iteration(
                tool=tool_name,
                status="end",
                step=tool_name,
                elapsed_ms=elapsed,
                session_id=session_id,
                flow="multi-agent-runtime",
                details={"result_keys": result_keys},
            )
            await self._emit_event(
                {
                    "event": "tool_call",
                    "data": {
                        "tool": tool_name,
                        "status": "end",
                        "step": tool_name,
                        "result_keys": result_keys,
                        "elapsed_ms": elapsed,
                        "ts": datetime.utcnow().isoformat(),
                    },
                }
            )
            return result
        except Exception as exc:
            elapsed = int((time.perf_counter() - start) * 1000)
            tool_iteration(
                tool=tool_name,
                status="error",
                step=tool_name,
                elapsed_ms=elapsed,
                session_id=session_id,
                flow="multi-agent-runtime",
                details={"error": str(exc)},
            )
            await self._emit_event(
                {
                    "event": "tool_call",
                    "data": {
                        "tool": tool_name,
                        "status": "error",
                        "step": tool_name,
                        "error": str(exc),
                        "elapsed_ms": elapsed,
                        "ts": datetime.utcnow().isoformat(),
                    },
                }
            )
            raise

    async def _emit_agent_turn(
        self,
        role: str,
        status: str,
        *,
        detail: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "role": role,
            "status": status,
            "step": detail,
            "ts": datetime.utcnow().isoformat(),
        }
        if metadata:
            payload.update(metadata)
        await self._emit_event({"event": "agent_turn", "data": payload})

    async def _emit_event(self, event: Optional[Dict[str, Any]]) -> None:
        if not event or self._event_callback is None:
            return
        data = event.get("data")
        if isinstance(data, dict) and "sequence" not in data:
            self._sequence += 1
            data["sequence"] = self._sequence
        try:
            result = self._event_callback(event)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception("Multi-agent event callback failed", extra={"event": event.get("event")})

    async def _execute_parallel(
        self,
        tasks: Sequence[Tuple[str, Callable[[], Awaitable[Dict[str, Any]]], Callable[[List[str]], Dict[str, Any]]]],
        session_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        if not tasks:
            return []
        coroutines = [
            self._run_with_retry(role, factory, fallback, session_id=session_id)
            for role, factory, fallback in tasks
        ]
        return await asyncio.gather(*coroutines)

    async def _run_with_retry(
        self,
        role: str,
        factory: Callable[[], Awaitable[Dict[str, Any]]],
        fallback: Callable[[List[str]], Dict[str, Any]],
        *,
        session_id: Optional[str],
        max_attempts: int = 2,
    ) -> Dict[str, Any]:
        errors: List[str] = []
        attempt = 0
        while attempt < max_attempts:
            try:
                return await factory()
            except Exception as exc:  # noqa: BLE001 - propagate via fallback
                attempt += 1
                errors.append(str(exc))
                await self._emit_agent_turn(
                    role,
                    "retry",
                    detail=f"{role}_retry",
                    metadata={"attempt": attempt, "error": str(exc)},
                )
                await asyncio.sleep(min(0.6 * attempt, 1.2))
        await self._emit_agent_turn(
            role,
            "failed",
            detail="fallback",
            metadata={"errors": errors},
        )
        return fallback(errors)

    def _chart_fallback(self, errors: List[str]) -> Dict[str, Any]:
        return {
            "chart": {
                "chart_plan": None,
                "chart_spec": None,
                "status": "failed",
                "errors": errors,
            }
        }

    def _analysis_fallback(self, errors: List[str]) -> Dict[str, Any]:
        return {
            "analysis": {
                "summary": "",
                "length": 0,
                "status": "failed",
                "errors": errors,
            }
        }

    def _market_fallback(self, tickers: Sequence[str], errors: List[str]) -> Dict[str, Any]:
        resolved = list(tickers)
        return {
            "market": {
                "status": "unavailable",
                "tickers": resolved,
                "errors": errors,
            },
            "market_tickers": resolved,
        }

    def _web_fallback(self, errors: List[str]) -> Dict[str, Any]:
        return {
            "web": {
                "status": "failed",
                "snippets": [],
                "ready": False,
                "errors": errors,
            }
        }

    def _resolve_market_tickers(
        self,
        query: str,
        planner_ctx: Dict[str, Any],
        sql_ctx: Dict[str, Any],
    ) -> List[str]:
        candidates: List[str] = []
        intent: Optional[IntentModel] = planner_ctx.get("intent")
        if intent and getattr(intent, "slots_detected", None):
            slots = intent.slots_detected
            slot_tickers = slots.get("tickers") if isinstance(slots, dict) else None
            candidates.extend(self._normalize_ticker_values(slot_tickers))
            company = slots.get("company") if isinstance(slots, dict) else None
            normalized_company = self._normalize_ticker_value(company)
            if normalized_company:
                candidates.append(normalized_company)
        rows = sql_ctx.get("sql_rows") or []
        if rows:
            first_row = rows[0]
            for key in ("ticker", "symbol", "ticker_symbol"):
                normalized = self._normalize_ticker_value(first_row.get(key))
                if normalized:
                    candidates.append(normalized)
                    break
        candidates.extend(self._extract_tickers_from_query(query))
        seen = set()
        ordered: List[str] = []
        for ticker in candidates:
            if ticker and ticker not in seen:
                seen.add(ticker)
                ordered.append(ticker)
        return ordered[:3]

    def _normalize_ticker_values(self, value: Any) -> List[str]:
        if isinstance(value, (list, tuple, set)):
            return [ticker for ticker in (self._normalize_ticker_value(v) for v in value) if ticker]
        normalized = self._normalize_ticker_value(value)
        return [normalized] if normalized else []

    def _normalize_ticker_value(self, value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        candidate = value.strip().upper()
        if not candidate:
            return None
        if re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z]{1,2})?", candidate):
            return candidate
        return None

    def _extract_tickers_from_query(self, query: str) -> List[str]:
        if not query:
            return []
        raw_matches = re.findall(r"\b[A-Z]{2,5}\b", query)
        blacklist = {"WITH", "FROM", "AND", "THE", "OVER", "WHERE"}
        tickers = [match for match in raw_matches if match not in blacklist]
        return tickers[:3]

    def _get_responses_client(self):
        if self._responses_client is None:
            self._responses_client = get_unified_client()
        return self._responses_client


__all__ = ["MultiAgentRuntime", "SpecialistConfig"]
